"""Iteration 3, X21 (event clock): in fan-out pairs (the wallet's taker orders in two markets of one event signed within
50 ms), do other makers' cancels start at the same offset after its signing in both markets?

Own recorder (server clock, 14:50 UTC on), the wallet's CS2 dev-unit markets. For each leg: the first consumed-side
cancel that is not exactly 100 shares (not its own ladder) and has no trade within 150 ms, in [0, 1000] ms after the
leg's signing. Reported per pair: the two onsets and their difference. Output: results/fanout_waves.json
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
    tok, ev = {}, {}
    for r in m.itertuples():
        tok[r.tok0] = (r.tok0, 0)
        tok[r.tok1] = (r.tok0, 1)
        ev[r.tok0] = r.event
    tok0 = set(m.tok0)
    ow = read("tommy_cs2_near", tok0, OWN0 / 1000, time.time())
    trades = defaultdict(list)
    for r in ow:
        if r["k"] == "x":
            trades[r["a"]].append(r["s"])
    trades = {a: np.sort(np.array(v, float)) for a, v in trades.items()}
    canc = defaultdict(list)
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
            dz = round(z - bk.get(p, 0.0), 2)
            if dz < 0 and dz != -100:
                tr = trades.get(a, np.array([]))
                k = np.searchsorted(tr, r["s"] - 150)
                if not (k < len(tr) and tr[k] <= r["s"] + 150):
                    canc[(a, side)].append(r["s"])
            if z == 0:
                bk.pop(p, None)
            else:
                bk[p] = z
    canc = {k: np.sort(np.array(v, float)) for k, v in canc.items()}
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    w = d[(d.idx == -1) & (d.maker == WALLET) & (d.sign_ms >= OWN0 + 2000) & (d.sign_ms < 1.8e12) & d.token_id.astype(str).isin(tok)].drop_duplicates("tx").copy()
    w["a"] = w.token_id.astype(str).map(lambda t: tok[t][0])
    w["k"] = w.token_id.astype(str).map(lambda t: tok[t][1])
    w["team"] = np.where(w.side == 0, w.k, 1 - w.k)
    w["event"] = w.a.map(ev)

    def onset(a, team, s):
        c = canc.get((a, "SELL" if team == 0 else "BUY"))
        if c is None:
            return None
        i = np.searchsorted(c, s)
        return float(c[i] - s) if i < len(c) and c[i] - s <= 1000 else None
    pairs = []
    w = w.sort_values("sign_ms")
    for e_, g in w.groupby("event"):
        rows = list(g.itertuples())
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                if rows[j].sign_ms - rows[i].sign_ms > 50:
                    break
                if rows[j].a == rows[i].a:
                    continue
                o1, o2 = onset(rows[i].a, rows[i].team, rows[i].sign_ms), onset(rows[j].a, rows[j].team, rows[j].sign_ms)
                pairs.append({"gap_ms": rows[j].sign_ms - rows[i].sign_ms, "onset1": o1, "onset2": o2})
    x = pd.DataFrame(pairs)
    res = {"pairs": int(len(x))}
    if len(x):
        both = x.dropna()
        res.update({"pairs_with_both_onsets": int(len(both)), "onset_ms_leg1": both.onset1.round().tolist(), "onset_ms_leg2": both.onset2.round().tolist(),
                    "abs_diff_ms_median": float((both.onset1 - both.onset2).abs().median()) if len(both) else None})
    json.dump(res, open(RES / "fanout_waves.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
