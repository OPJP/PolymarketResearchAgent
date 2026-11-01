"""Iteration 3, X21 / X34 (first cut): who cancels in the wave right after the wallet signs?

Own recorder tommy_cs2_near (unthrottled price changes within 5c, 10-31 14:50 UTC on), the wallet's dev-unit markets,
SERVER clock. Per token-0 book level, every size decrease that is not within 150 ms of a trade print on that token is a
cancel of that size (the remaining size of one or more orders). Waves: decreases on the consumed side within 5c of the
touch in [sign, sign + 500 ms] after each wallet taker order; control: the same side in 500-ms windows at random times.
Attribution by size fingerprint: a maker's order sizes in public calldata of the same market (original shares, used at
least twice), excluding the size 100 shared by many makers... (reported separately). A cancel of size z is attributed to
the makers whose fingerprint contains z (within 0.01 share). Output: results/canceller_id.json
"""
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, PACK, T0, read  # noqa: E402

OWN0 = 1793458232000


def main():
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    m = m[m.wallet_trades > 0]
    tok = {}
    for r in m.itertuples():
        tok[r.tok0] = (r.cid, 0, r.tok0)
        tok[r.tok1] = (r.cid, 1, r.tok0)
    tok0 = set(m.tok0)
    ow = read("tommy_cs2_near", tok0, OWN0 / 1000, time.time())
    trades = defaultdict(list)
    for r in ow:
        if r["k"] == "x":
            trades[r["a"]].append(r["s"])
    trades = {a: np.sort(np.array(v, float)) for a, v in trades.items()}
    dec = []  # (a, side, s, price, dz)
    books = {}
    for r in sorted([r for r in ow if r["k"] in ("f", "pc")], key=lambda r: (r["s"], r["t"])):
        a = r["a"]
        if r["k"] == "f":
            books[a] = ({float(p): float(z) for p, z in r["b"]}, {float(p): float(z) for p, z in r["o"]})
            continue
        if a not in books:
            continue
        bd, od = books[a]
        for side, p, z in r["c"]:
            bk = bd if side == "BUY" else od
            p, z = float(p), float(z)
            old = bk.get(p, 0.0)
            if z < old - 1e-9:
                tr = trades.get(a, np.array([]))
                k = np.searchsorted(tr, r["s"] - 150)
                if not (k < len(tr) and tr[k] <= r["s"] + 150):
                    dec.append((a, side, r["s"], p, round(old - z, 2)))
            if z == 0:
                bk.pop(p, None)
            else:
                bk[p] = z
    D = pd.DataFrame(dec, columns=["a", "side", "s", "p", "dz"])
    # fingerprints from public calldata of these markets
    cd = pd.concat([pd.read_parquet(OUT / "calldata_dev.parquet")])
    cd = cd[(cd.idx >= 0) & cd.token_id.astype(str).isin(tok)]
    fp = defaultdict(set)
    for (mk, a), g in cd.assign(a=cd.token_id.astype(str).map(lambda t: tok[t][2])).groupby(["maker", "a"]):
        c = Counter(np.round(g.shares, 2))
        for z, n in c.items():
            if n >= 2:
                fp[(a, z)].add(mk)
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    w = d[(d.idx == -1) & (d.maker == WALLET) & (d.sign_ms >= OWN0 + 2000) & d.token_id.astype(str).isin(tok)].drop_duplicates("tx")
    rng = np.random.default_rng(5)

    def window_cancels(a, side, t0):
        x = D[(D.a == a) & (D.side == side) & (D.s >= t0) & (D.s <= t0 + 500)]
        return x

    res = {"cancels_total": int(len(D)), "wallet_orders": int(len(w))}
    for lab in ("wave", "control"):
        cnt, att, nwin, ncan, sz = Counter(), Counter(), 0, 0, []
        for r in w.itertuples():
            a, oi = tok[str(r.token_id)][2], tok[str(r.token_id)][1]
            team = oi if r.side == 0 else 1 - oi
            side = "SELL" if team == 0 else "BUY"
            starts = [r.sign_ms] if lab == "wave" else list(r.sign_ms + rng.uniform(-900000, -60000, 10))
            for t0 in starts:
                x = window_cancels(a, side, t0)
                nwin += 1
                ncan += len(x)
                for z in x.dz:
                    sz.append(z)
                    who = fp.get((a, round(z, 2)), set())
                    if z == 100:
                        att["(size 100: shared)"] += 1
                    elif len(who) == 1:
                        att[next(iter(who))[:10]] += 1
                    elif len(who) > 1:
                        att["(ambiguous)"] += 1
                    else:
                        att["(no fingerprint)"] += 1
        res[lab] = {"windows": nwin, "cancels_per_window": round(ncan / max(nwin, 1), 2),
                    "cancel_size_median": float(np.median(sz)) if sz else None,
                    "attributed_top": att.most_common(12)}
    json.dump(res, open(RES / "canceller_id.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__" and len(sys.argv) == 1:
    main()


def offsets():
    """Offsets (server ms after the wallet's signing) of wave cancels by attribution class, and the wallet's own
    complement ladder at those levels (its filled maker orders on the cancelled side's token at that price, signed in
    the 10 min before the wave)."""
    import importlib
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    m = m[m.wallet_trades > 0]
    tok = {}
    for r in m.itertuples():
        tok[r.tok0] = (r.cid, 0, r.tok0)
        tok[r.tok1] = (r.cid, 1, r.tok0)
    tok0 = set(m.tok0)
    ow = read("tommy_cs2_near", tok0, OWN0 / 1000, time.time())
    trades = defaultdict(list)
    for r in ow:
        if r["k"] == "x":
            trades[r["a"]].append(r["s"])
    trades = {a: np.sort(np.array(v, float)) for a, v in trades.items()}
    dec, books = [], {}
    for r in sorted([r for r in ow if r["k"] in ("f", "pc")], key=lambda r: (r["s"], r["t"])):
        a = r["a"]
        if r["k"] == "f":
            books[a] = ({float(p): float(z) for p, z in r["b"]}, {float(p): float(z) for p, z in r["o"]})
            continue
        if a not in books:
            continue
        bd, od = books[a]
        for side, p, z in r["c"]:
            bk = bd if side == "BUY" else od
            p, z = float(p), float(z)
            old = bk.get(p, 0.0)
            if z < old - 1e-9:
                tr = trades.get(a, np.array([]))
                k = np.searchsorted(tr, r["s"] - 150)
                if not (k < len(tr) and tr[k] <= r["s"] + 150):
                    dec.append((a, side, r["s"], p, round(old - z, 2)))
            if z == 0:
                bk.pop(p, None)
            else:
                bk[p] = z
    D = pd.DataFrame(dec, columns=["a", "side", "s", "p", "dz"])
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    w = d[(d.idx == -1) & (d.maker == WALLET) & (d.sign_ms >= OWN0 + 2000) & d.token_id.astype(str).isin(tok)].drop_duplicates("tx")
    wm = d[(d.idx >= 0) & (d.maker == WALLET) & d.token_id.astype(str).isin(tok)].drop_duplicates(["salt", "sign_ms"])
    out = {"s100": [], "s2e3c": [], "other": []}
    own_level = []
    for r in w.itertuples():
        a, oi = tok[str(r.token_id)][2], tok[str(r.token_id)][1]
        team = oi if r.side == 0 else 1 - oi
        side = "SELL" if team == 0 else "BUY"
        x = D[(D.a == a) & (D.side == side) & (D.s >= r.sign_ms) & (D.s <= r.sign_ms + 500)]
        comp_tok = [t for t, v in tok.items() if v[2] == a and v[1] == 1 - team][0]
        for q in x.itertuples():
            off = q.s - r.sign_ms
            if q.dz == 100:
                out["s100"].append(off)
                # the cancelled level as a price on the complement token: token-0 ask p (team 0) = team-1 bid 1 - p
                cp = round(1 - q.p, 2) if team == 0 else round(q.p, 2)
                mine = wm[(wm.token_id.astype(str) == comp_tok) & (np.abs(wm.price - cp) < 1e-6) & (wm.sign_ms < r.sign_ms) & (wm.sign_ms > r.sign_ms - 600000)]
                own_level.append(len(mine) > 0)
            else:
                out["other"].append(off)
    res = {k: {"n": len(v), "off_ms_p10_p25_p50_p75": [int(np.percentile(v, q)) for q in (10, 25, 50, 75)] if len(v) >= 5 else v} for k, v in out.items()}
    res["s100_level_has_own_filled_complement_bid_in_prior_10min"] = round(float(np.mean(own_level)), 3) if own_level else None
    return res


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "offsets":
    r = offsets()
    json.dump(r, open(RES / "canceller_offsets.json", "w"), indent=1)
    print(json.dumps(r, indent=1))
