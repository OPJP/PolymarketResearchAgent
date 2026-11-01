"""Iteration 12, E9 (new, own state across markets): does the cluster's ENTRY side in a BTC 5m window follow its position
in the overlapping BTC 15m window (the 15m window that contains the 5m window), or its position in the previous 5m window?
Entry fills = BTC 5m maker BUY fills of the lot with no cluster position in the 5m window before the fill's second
(it12/typed_fills.parquet, inv_c == 0). Cluster positions from the lot activity (three wallets, maker + taker BUY rows,
strictly before the fill's second). STUDY case by case, VALIDATE as aggregates. Exploratory.
    python code12/xmarket_entry.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"


def main():
    V = pd.read_parquet(C / "it12" / "typed_fills.parquet")
    acts = []
    for n in ("bosona", "almach", "momoney"):
        a = pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["timestamp", "type", "side", "outcome", "size", "slug"])
        acts.append(a)
    A = pd.concat(acts)
    A = A[(A.type == "TRADE") & (A.side == "BUY")]
    A15 = A[A.slug.str.startswith("btc-updown-15m-", na=False)].copy()
    A15["st15"] = A15.slug.str.split("-").str[-1].astype(int)
    A15["sgn"] = np.where(A15.outcome == "Up", 1.0, -1.0) * A15["size"]
    A5 = A[A.slug.str.startswith("btc-updown-5m-", na=False)].copy()
    A5["st5"] = A5.slug.str.split("-").str[-1].astype(int)
    A5["sgn"] = np.where(A5.outcome == "Up", 1.0, -1.0) * A5["size"]
    G15 = {k: (g.timestamp.to_numpy(), np.cumsum(g.sort_values("timestamp").sgn.to_numpy())) for k, g in A15.sort_values("timestamp").groupby("st15")}
    G5 = {k: g.sgn.sum() for k, g in A5.groupby("st5")}
    E = V[(V.inv_c == 0) & (np.abs(V.mid_up - 0.5) <= 0.4)].copy()
    pos15, prev5 = [], []
    for st, b in zip(E.st.astype(int), E.b.astype(int)):
        s15 = st - (st % 900)
        g = G15.get(s15)
        if g is None:
            pos15.append(0.0)
        else:
            i = np.searchsorted(g[0], b, side="left") - 1
            pos15.append(float(g[1][i]) if i >= 0 else 0.0)
        prev5.append(float(G5.get(st - 300, 0.0)))
    E["pos15"] = pos15
    E["prev5"] = prev5
    y = (E.is_up == 1).to_numpy()
    mid = E.mid_up.to_numpy()
    post = np.where(np.isfinite(E.f_cl) & np.isfinite(mid), E.f_cl > mid, E.f_bn > mid)
    out = {}
    for sp in ("study", "validate"):
        m = (E.sp == sp).to_numpy()
        h15 = m & (E.pos15.to_numpy() != 0)
        hp = m & (E.prev5.to_numpy() != 0)
        agree = post == (E.pos15.to_numpy() > 0)
        out[sp] = {"entry_fills": int(m.sum()), "posture": round(float((post == y)[m].mean()), 4),
                   "share_with_15m_position": round(float(h15.sum() / max(m.sum(), 1)), 4),
                   "follow_15m_position": round(float(((E.pos15.to_numpy() > 0) == y)[h15].mean()), 4) if h15.any() else None,
                   "posture_where_15m_position": round(float((post == y)[h15].mean()), 4) if h15.any() else None,
                   "agree_share": round(float(agree[h15].mean()), 4) if h15.any() else None,
                   "acc_where_agree": round(float((post == y)[h15 & agree].mean()), 4) if (h15 & agree).any() else None,
                   "follow_15m_where_disagree": round(float(((E.pos15.to_numpy() > 0) == y)[h15 & ~agree].mean()), 4) if (h15 & ~agree).any() else None,
                   "share_with_prev5_position": round(float(hp.sum() / max(m.sum(), 1)), 4),
                   "follow_prev5_net": round(float(((E.prev5.to_numpy() > 0) == y)[hp].mean()), 4) if hp.any() else None}
    (HERE.parent / "results" / "iter12_xmarket_entry.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
