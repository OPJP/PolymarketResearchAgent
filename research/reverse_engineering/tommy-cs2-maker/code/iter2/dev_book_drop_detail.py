"""Detail of the consumed-side depth collapse before the wallet's taker signings (dev block 10-31 12-18 UTC):
time profile of near-touch depth, which levels lost size and how much (multiples of 100 = the wallet's own 100-share
quotes on the complement?), and public trades on the consumed side in [-3, 0) s (clob_wallets 'x' records)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from dev_books import BLOCK0, OUT, RES, WALLET  # noqa: E402
from dev_book_trigger import PACK, depth  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import live  # noqa: E402


def main():
    a = pd.read_parquet(OUT / "activity_devblocks.parquet")
    cids = sorted(a.conditionId.unique())
    mk, _ = PolymarketData().markets_by_condition(cids)
    tok = {}
    for cid, x in mk.items():
        t = x["clobTokenIds"]
        t = json.loads(t) if isinstance(t, str) else t
        tok[str(t[0])] = (cid, 0, str(t[0]))
        tok[str(t[1])] = (cid, 1, str(t[0]))
    tok0 = {v[2] for v in tok.values()}
    end = min(time.time() - 60, BLOCK0 + 6 * 3600)
    recs, trades = [], []
    h = BLOCK0
    while h < end:
        try:
            for r in live.iter_live("clob_wallets", h, min(h + 3600, end)):
                if r.get("a") in tok0:
                    if r.get("k") in ("q", "f"):
                        recs.append((r["t"], r["a"], [(float(p), float(z)) for p, z in (r.get("b") or [])], [(float(p), float(z)) for p, z in (r.get("o") or [])]))
                    elif r.get("k") == "x":
                        trades.append((r["t"], r["a"], float(r.get("p", 0)), float(r.get("z", 0)), r.get("d")))
        except Exception as e:  # noqa: BLE001
            print("hour stopped", type(e).__name__)
        h += 3600
    bk = pd.DataFrame(recs, columns=["t", "a", "b", "o"]).sort_values("t")
    tr = pd.DataFrame(trades, columns=["t", "a", "p", "z", "d"]).sort_values("t")
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    d = d[(d.idx == -1) & (d.sign_ms > 1.79e12) & (d.sign_ms < 1.8e12) & d.token_id.astype(str).isin(tok)]
    d = d[(d.maker == WALLET) | d.maker.isin(PACK)]
    prof = {}
    rows = []
    offs = [-5000, -3000, -2000, -1500, -1000, -700, -500, -300, -200, -100, 0, 300, 600, 1000, 2000, 3000]
    for _, o in d.iterrows():
        cid, oi, t0 = tok[str(o.token_id)]
        b = bk[bk.a == t0]
        if len(b) < 50:
            continue
        tt = b.t.to_numpy()
        bought0 = (oi == 0) == (o.side == 0)
        sd = "o" if bought0 else "b"
        s = o.sign_ms
        prof_row = []
        for dt in offs:
            j = np.searchsorted(tt, s + dt, side="left") - 1
            prof_row.append(depth(b[sd].iloc[j], sd, None) if j >= 0 else np.nan)
        j2 = np.searchsorted(tt, s - 2000, side="left") - 1
        j0 = np.searchsorted(tt, s - 100, side="left") - 1
        if j2 < 0 or j0 < 0:
            continue
        L2 = dict(b[sd].iloc[j2]); L0 = dict(b[sd].iloc[j0])
        lost = {p: L2[p] - L0.get(p, 0.0) for p in L2 if L2[p] - L0.get(p, 0.0) > 0.5}
        # public trades on the consumed side in [-3, 0) s: a taker BUY of the bought token (token-0 'BUY' if bought0)
        tw = tr[(tr.a == t0) & (tr.t >= s - 3000) & (tr.t < s)]
        rows.append({"who": "W" if o.maker == WALLET else "pack", "lost_total": sum(lost.values()), "lost_levels": len(lost),
                     "lost_mult100": float(np.mean([abs(v / 100 - round(v / 100)) < 0.01 for v in lost.values()])) if lost else np.nan,
                     "trades_pre3s": len(tw), "trade_size_pre3s": float(tw.z.sum()), "depth_m2": prof_row[offs.index(-2000)],
                     "depth_m01": prof_row[offs.index(-100)], **{f"p{dt}": v for dt, v in zip(offs, prof_row)}})
    x = pd.DataFrame(rows)
    res = {}
    for w, s in x.groupby("who"):
        base = s["p-5000"].replace(0, np.nan)
        res[w] = {"n": len(s), "depth_profile_rel_to_-5s_median": {dt: round(float((s[f"p{dt}"] / base).median()), 3) for dt in offs},
                  "lost_total_q": s.lost_total.quantile([.25, .5, .75]).round(0).tolist(), "lost_levels_median": float(s.lost_levels.median()),
                  "lost_multiple_of_100_share": round(float(s.lost_mult100.mean()), 3),
                  "trades_in_prev3s_share": round(float((s.trades_pre3s > 0).mean()), 3),
                  "trade_size_vs_lost_median": round(float((s.trade_size_pre3s / s.lost_total.replace(0, np.nan)).median()), 3)}
    json.dump(res, open(RES / "results/dev_book_drop_detail.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
