"""Iteration 11 (information I10-4 = X104 step 3 / mechanics P1 entry): a market-only taker-flow baseline for the
window's entry side. For each BTC 5m window with cluster maker fills: the side of the first cluster maker BUY fill and the
terminal net side; predictor = the net clean-tape taker demand for Up over the L seconds before the first fill's block
second (strictly earlier seconds; demand +size for BUY Up or SELL Down, -size for BUY Down or SELL Up), L in {10, 30, 60}.
'complement' predicts the cluster buys the outcome the takers were NOT buying; 'with' the one they were. VALIDATE aggregate.
    python code11/entry_flow.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
SPLIT_V = 1793059200


def main():
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet").set_index("cid")
    CW = pd.read_parquet(C / "it11" / "cluster_windows.parquet")
    mk = CW[CW.role == "maker"]
    first = mk.sort_values("first_ts").groupby("cid").first()[["first_ts", "first_up"]]
    tot = mk.groupby("cid").agg(up=("up", "sum"), dn=("dn", "sum"))
    first = first.join(tot)
    F = pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["txh"])
    cl_tx = set(F.txh.str.lower())
    for n in ("bosona", "almach", "momoney"):
        cl_tx |= set(pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["transactionHash"]).transactionHash.str.lower())
    rows = []
    for day in sorted(set((W.start_ts // 86400 * 86400).astype(int))):
        T = pd.read_parquet(C / "exam" / f"taker5m_day_{day}.parquet", columns=["cid", "ts", "side", "asset", "size", "tx"])
        T = T[~T.tx.str.lower().isin(cl_tx) & T.cid.isin(first.index)]
        for cid, g in T.groupby("cid"):
            if cid not in first.index:
                continue
            f0 = int(first.at[cid, "first_ts"])
            up = str(W.at[cid, "up_token"])
            isu = g.asset.astype(str).to_numpy() == up
            buy = g.side.to_numpy() == "BUY"
            dem = np.where(buy == isu, 1.0, -1.0) * g["size"].to_numpy(float)
            ts = g.ts.to_numpy()
            rec = {"cid": cid, "st": int(W.at[cid, "start_ts"]), "first_up": int(first.at[cid, "first_up"]),
                   "up": float(first.at[cid, "up"]), "dn": float(first.at[cid, "dn"]), "rel": f0 - int(W.at[cid, "start_ts"])}
            for L in (10, 30, 60):
                m = (ts < f0) & (ts >= f0 - L)
                rec[f"d{L}"] = float(dem[m].sum())
            rows.append(rec)
    D = pd.DataFrame(rows)
    D.to_parquet(C / "it11" / "entry_flow_rows.parquet")
    out = {}
    for sp, d in (("study", D[D.st < SPLIT_V]), ("validate", D[D.st >= SPLIT_V])):
        tot = d.up + d.dn
        one = (np.maximum(d.up, d.dn) / tot.where(tot > 0, 1)) >= 0.7
        net_up = (d.up > d.dn).astype(int)
        rec = {"windows": int(len(d)), "one_sided": int(one.sum())}
        for L in (10, 30, 60):
            x = d[f"d{L}"].to_numpy()
            nz = x != 0
            comp = (x < 0).astype(int)  # takers bought Down (net) -> cluster bought Up
            rec[f"L{L}"] = {"coverage": round(float(nz.mean()), 4),
                            "first_fill_complement": round(float((comp == d.first_up)[nz].mean()), 4),
                            "net_side_complement_one_sided": round(float((comp == net_up)[nz & one].mean()), 4)}
        out[sp] = rec
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter11_entry_flow.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
