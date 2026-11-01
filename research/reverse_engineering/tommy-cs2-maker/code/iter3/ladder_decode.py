"""Iteration 3, assumptions panel P4 step 2 (X33): decode the wallet's FULL maker ladder (filled and unfilled levels)
from the own recorder, anchored on its filled orders.

Own recorder tommy_cs2_near (10-31 14:50 UTC on, server clock), the wallet's dev-unit markets. Book changes per
token-0 level are rebuilt; an "add100" is a level increase of exactly +100 shares at a whole-cent price. Anchors: the
wallet's filled CS2 maker orders (calldata_dev) on token k at price q: the matching add100 on the mirrored token-0 side
(token 0 BUY q -> BUY side q; token 1 BUY q -> SELL side 1 - q) in [sign, sign + 400 ms] confirms the order reached the
book (latency = server stamp - sign). Ladder = all add100 on the same side within +-60 ms of the confirmed add (same
burst). Reported: confirmation rate and latency, ladder size, spacing, top relative to the pre-burst best bid of that
token (book 1 ms before the first add of the burst), and whether a ladder appears on the other token in the same burst.
Output: results/ladder_decode.json
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, read  # noqa: E402

OWN0 = 1793458232000


def main():
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    m = m[(m.wallet_trades > 0) & m.event.str.startswith("cs2")]
    tok = {}
    for r in m.itertuples():
        tok[r.tok0] = (r.tok0, 0)
        tok[r.tok1] = (r.tok0, 1)
    tok0 = set(m.tok0)
    ow = read("tommy_cs2_near", tok0, OWN0 / 1000, time.time())
    adds = defaultdict(list)  # (a, side) -> [(s, p)]
    snaps = defaultdict(list)  # a -> [(s, best bid, best ask)] after each change
    books = {}
    for r in sorted([r for r in ow if r["k"] in ("f", "pc")], key=lambda r: (r["s"], r["t"])):
        a = r["a"]
        if r["k"] == "f":
            books[a] = ({float(p): float(z) for p, z in r["b"]}, {float(p): float(z) for p, z in r["o"]})
        elif a in books:
            bd, od = books[a]
            for side, p, z in r["c"]:
                bk = bd if side == "BUY" else od
                p, z = float(p), float(z)
                dz = round(z - bk.get(p, 0.0), 2)
                if dz == 100 and abs(p * 100 - round(p * 100)) < 1e-6:
                    adds[(a, side)].append((r["s"], p))
                if z == 0:
                    bk.pop(p, None)
                else:
                    bk[p] = z
        else:
            continue
        bd, od = books[a]
        snaps[a].append((r["s"], max(bd) if bd else np.nan, min(od) if od else np.nan))
    A = {k: np.array(v) for k, v in adds.items()}
    SN = {a: np.array(v) for a, v in snaps.items()}
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    wm = d[(d.idx >= 0) & (d.maker == WALLET) & (d.sign_ms >= OWN0 + 2000) & (d.sign_ms < 1.8e12) & d.token_id.astype(str).isin(tok)]
    wm = wm.drop_duplicates(["salt", "sign_ms"])
    wt = d[(d.idx == -1) & (d.maker == WALLET) & (d.sign_ms > 1.79e12) & (d.sign_ms < 1.8e12) & d.token_id.astype(str).isin(tok)].drop_duplicates("tx")
    wt_a = defaultdict(list)
    for q in wt.itertuples():
        wt_a[tok[str(q.token_id)][0]].append(q.sign_ms)
    wt_a = {a: np.sort(np.array(v)) for a, v in wt_a.items()}
    rows = []
    for r in wm.itertuples():
        a, k = tok[str(r.token_id)]
        side, p0 = ("BUY", round(r.price, 2)) if k == 0 else ("SELL", round(1 - r.price, 2))
        arr = A.get((a, side))
        if arr is None or len(arr) == 0:
            rows.append({"confirmed": False})
            continue
        sel = (arr[:, 0] >= r.sign_ms) & (arr[:, 0] <= r.sign_ms + 400) & (np.abs(arr[:, 1] - p0) < 1e-6)
        if not sel.any():
            rows.append({"confirmed": False, "shares": r.shares})
            continue
        s_add = arr[sel][0, 0]
        burst = arr[(arr[:, 0] >= s_add - 60) & (arr[:, 0] <= s_add + 60)]
        prices = np.sort(np.unique(burst[:, 1]))
        # in token-k terms
        lv = prices if k == 0 else np.sort(1 - prices)
        top = lv.max()
        sn = SN[a]
        i = np.searchsorted(sn[:, 0], burst[:, 0].min() - 1, side="right") - 1
        if i < 0:
            continue
        bb0, ba0 = sn[i, 1], sn[i, 2]
        bb, ba = (bb0, ba0) if k == 0 else (1 - ba0, 1 - bb0)
        other = A.get((a, "SELL" if side == "BUY" else "BUY"))
        both = bool(other is not None and len(other) and ((other[:, 0] >= s_add - 60) & (other[:, 0] <= s_add + 60)).any())
        ts_ = wt_a.get(a, np.array([]))
        j = np.searchsorted(ts_, r.sign_ms) - 1
        since_take = (r.sign_ms - ts_[j]) if j >= 0 else np.inf
        rows.append({"confirmed": True, "lat": s_add - r.sign_ms, "since_take_ms": since_take, "spr": round((ba - bb) * 100), "levels": len(lv), "top_rel_bid": round((top - bb) * 100),
                     "top_rel_ask": round((top - ba) * 100), "spacing1": bool(len(lv) < 2 or np.allclose(np.diff(lv), 0.01, atol=1e-6)),
                     "order_level": int(round((top - round(r.price, 2)) * 100)), "both_tokens": both, "shares": r.shares})
    x = pd.DataFrame(rows)
    c = x[x.confirmed == True]  # noqa: E712
    out = {"filled_maker_orders": int(len(x)), "confirmed_share": round(float(x.confirmed.mean()), 3),
           "confirmed_share_100_shares": round(float(x[x.get("shares", pd.Series(dtype=float)) == 100].confirmed.mean()), 3) if "shares" in x else None}
    if len(c):
        out.update({"latency_ms_p10_p50_p90": [int(np.percentile(c.lat, q)) for q in (10, 50, 90)],
                    "levels_dist": {str(int(k)): round(float(v), 3) for k, v in c.levels.value_counts(normalize=True).sort_index().items()},
                    "spacing_1c_share": round(float(c.spacing1.mean()), 3),
                    "top_minus_prebid_cents": {str(int(k)): round(float(v), 3) for k, v in c.top_rel_bid.value_counts(normalize=True).sort_index().items() if abs(k) <= 6},
                    "top_at_prebid": round(float((c.top_rel_bid == 0).mean()), 3),
                    "top_prebid_plus1": round(float((c.top_rel_bid == 1).mean()), 3),
                    "top_at_preask_minus1": round(float((c.top_rel_ask == -1).mean()), 3),
                    "filled_order_level_dist": {str(int(k)): round(float(v), 3) for k, v in c.order_level.value_counts(normalize=True).sort_index().items() if 0 <= k <= 8},
                    "ladder_on_both_tokens_in_burst": round(float(c.both_tokens.mean()), 3)})
        rp = c[(c.since_take_ms >= 900) & (c.since_take_ms <= 1400)]
        nr = c[~((c.since_take_ms >= 900) & (c.since_take_ms <= 1400))]
        out["repair_bursts_0.9_1.4s_after_own_take"] = {"n": int(len(rp)), "top_minus_prebid": {str(int(k)): round(float(v), 3) for k, v in rp.top_rel_bid.value_counts(normalize=True).sort_index().items()}}
        out["other_bursts"] = {"n": int(len(nr)), "top_minus_prebid": {str(int(k)): round(float(v), 3) for k, v in nr.top_rel_bid.value_counts(normalize=True).sort_index().items()}}
        # rule scores on burst tops (within one in-play tick = 1c)
        rules = {"R1_top=bid": c.top_rel_bid, "R2_top=ask-1c": c.top_rel_ask + 1,
                 "R3_top=bid+1c_if_spread>=2_else_bid": c.top_rel_bid - np.where(c.spr >= 2, 1, 0)}
        out["rule_within_1c_of_top"] = {k: round(float((v.abs() <= 1).mean()), 3) for k, v in rules.items()}
        out["rule_exact_top"] = {k: round(float((v == 0).mean()), 3) for k, v in rules.items()}
    json.dump(out, open(RES / "ladder_decode.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
