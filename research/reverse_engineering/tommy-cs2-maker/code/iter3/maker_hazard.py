"""Iteration 3, mechanics panel P2 (X26, hazards): what triggers the wallet's maker signings?

16-22 Oct calldata (wallet txs: calldata_all; every public taker tx of its markets: calldata_pub), signing clocks
(the wallet's and the fast takers' clocks match the server within ~40 ms). For each trigger type, the histogram of
(wallet maker sign_ms - trigger taker sign_ms) in 20-ms bins over [-0.5, +2.5] s, as a rate ratio to the same
market's baseline (offsets in [-60, -30] s):
  own_take    the wallet's own taker orders;
  hit_me      other takers' orders that filled a wallet maker order;
  others      other takers' orders that filled only other makers.
A peak at +1.04-1.12 s means the wallet reacts to the match message (its FAK response or the public trade at match
time, = taker sign + 1.04 s); a peak near 0 means it reacts to the same game event as the taker. Same token vs the
complement token of the trigger's bought team are split. Output: results/maker_hazard.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET  # noqa: E402


def main():
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "token_id", "oi", "role", "sign_ms"])
    oi = dict(zip(o.token_id.astype(str), o.oi))
    cidof = dict(zip(o.token_id.astype(str), o.cid))
    mk = o[o.role == "maker"].copy()
    mk["tok"] = mk.token_id.astype(str)
    parts = [pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "side", "token_id", "sign_ms"])]
    for p in (OUT / "calldata_pub").glob("*.parquet"):
        parts.append(pd.read_parquet(p, columns=["tx", "idx", "maker", "side", "token_id", "sign_ms"]))
    cd = pd.concat(parts)
    cd["tok"] = cd.token_id.astype(str)
    cd = cd[cd.tok.isin(oi) & (cd.sign_ms > 1.7e12) & (cd.sign_ms < 1.8e12)]
    tk = cd[cd.idx == -1].drop_duplicates("tx").copy()
    hit = set(cd[(cd.idx >= 0) & (cd.maker == WALLET)].tx)
    tk["cid"] = tk.tok.map(cidof)
    tk["team"] = np.where(tk.side == 0, tk.tok.map(oi), 1 - tk.tok.map(oi))
    tk["typ"] = np.where(tk.maker == WALLET, "own_take", np.where(tk.tx.isin(hit), "hit_me", "others"))
    mk["team"] = mk.tok.map(oi)
    edges = np.arange(-500, 2501, 20)
    res = {}
    by_cid = {c: g for c, g in mk.groupby("cid")}
    for typ in ("own_take", "hit_me", "others"):
        T = tk[tk.typ == typ]
        if typ == "others" and len(T) > 40000:
            T = T.sample(40000, random_state=1)
        for rel in ("same_team", "other_team"):
            h = np.zeros(len(edges) - 1)
            base = 0.0
            for c, g in T.groupby("cid"):
                M = by_cid.get(c)
                if M is None:
                    continue
                for team in (0, 1):
                    tt = g[g.team == team].sign_ms.to_numpy()
                    mt = np.sort(M[M.team == (team if rel == "same_team" else 1 - team)].sign_ms.to_numpy())
                    if len(tt) == 0 or len(mt) == 0:
                        continue
                    for t in tt:
                        lo, hi = np.searchsorted(mt, t - 500), np.searchsorted(mt, t + 2500)
                        if hi > lo:
                            h += np.histogram(mt[lo:hi] - t, edges)[0]
                        base += (np.searchsorted(mt, t - 30000) - np.searchsorted(mt, t - 60000)) / 30000 * 20
            ratio = h / max(base, 1e-9)
            top = np.argsort(ratio)[::-1][:5]
            res[f"{typ}|{rel}"] = {"triggers": int(len(T)), "baseline_per_20ms_bin": round(base / max(len(T), 1), 5),
                                   "peak_bins_ms": [[int(edges[i]), round(float(ratio[i]), 1)] for i in sorted(top)],
                                   "ratio_by_window": {f"[{a},{b})": round(float(h[(edges[:-1] >= a) & (edges[:-1] < b)].sum() /
                                                                                 max(base * (b - a) / 20, 1e-9)), 2)
                                                       for a, b in ((-500, 0), (0, 100), (100, 500), (500, 1000), (1000, 1140), (1140, 1500), (1500, 2500))}}
    json.dump(res, open(RES / "maker_hazard.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
