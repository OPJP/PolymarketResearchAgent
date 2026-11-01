"""Iteration 11 (assumptions P2 = X111 step (a); information I10-4 = X104): is the favourite-share drift of the cluster's
fills a change in WHO takes from it? Taker of each cluster maker BUY fill = the taker order's maker address in the lot
calldata (b1_takers_*). Per split: concentration (top-10 / top-50 taker share of fills), the share of VALIDATE fills from
takers already seen on STUDY, and the favourite share of the cluster's fills (fill price > 0.5) by taker group and by day.
No taker address is printed for VALIDATE (aggregates only).
    python code11/takers_drift.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
SPLIT_V = 1793059200


def main():
    F = pd.read_parquet(C / "exam" / "fills_holdout.parquet")
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet")
    F = F[(F.role == "maker") & (F.side == "BUY") & F.cid.isin(set(W.cid))].copy()
    F["txh"] = F.txh.str.lower()
    tk = pd.concat([pd.read_parquet(C / f"b1_takers_{s}.parquet", columns=["maker", "sig_type", "tx", "oside", "token_id"]) for s in ("study", "valid")])
    tk["tx"] = tk.tx.str.lower()
    tk = tk.drop_duplicates("tx").set_index("tx")
    F["taker"] = F.txh.map(tk.maker.str.lower())
    F["sig_type"] = F.txh.map(tk.sig_type)
    F["fav"] = F.price > 0.5
    F["day"] = pd.to_datetime(F.ts, unit="s").dt.date.astype(str)
    F = F.dropna(subset=["taker"])
    st, va = F[F.ts < SPLIT_V], F[F.ts >= SPLIT_V]
    out = {"fills_with_taker": {"study": int(len(st)), "validate": int(len(va))}}
    for sp, d in (("study", st), ("validate", va)):
        c = d.taker.value_counts()
        top10, top50 = set(c.index[:10]), set(c.index[:50])
        out[sp] = {"takers": int(c.size), "top10_share": round(float(c.iloc[:10].sum() / c.sum()), 4), "top50_share": round(float(c.iloc[:50].sum() / c.sum()), 4),
                   "fav_share_all": round(float(d.fav.mean()), 4), "fav_share_top10": round(float(d.fav[d.taker.isin(top10)].mean()), 4),
                   "fav_share_rest": round(float(d.fav[~d.taker.isin(top10)].mean()), 4),
                   "sig_type_share": d.sig_type.value_counts(normalize=True).round(4).to_dict(),
                   "fav_by_sig_type": d.groupby("sig_type").fav.mean().round(4).to_dict()}
    seen = set(st.taker)
    va_old = va.taker.isin(seen)
    out["validate"]["share_from_takers_seen_on_study"] = round(float(va_old.mean()), 4)
    out["validate"]["fav_share_takers_seen_on_study"] = round(float(va.fav[va_old].mean()), 4)
    out["validate"]["fav_share_new_takers"] = round(float(va.fav[~va_old].mean()), 4)
    # same takers, both halves: does a STUDY taker's fill side move too?
    both = set(st.taker) & set(va.taker)
    out["takers_in_both"] = int(len(both))
    out["fav_share_same_takers"] = {"study": round(float(st.fav[st.taker.isin(both)].mean()), 4), "validate": round(float(va.fav[va.taker.isin(both)].mean()), 4)}
    vtop10 = set(va.taker.value_counts().index[:10])
    out["by_day"] = {d: {"fills": int(len(g)), "fav_share": round(float(g.fav.mean()), 3), "share_validate_top10_takers": round(float(g.taker.isin(vtop10).mean()), 3),
                         "fav_share_excluding_validate_top10": round(float(g.fav[~g.taker.isin(vtop10)].mean()), 3)} for d, g in F.groupby("day")}
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter11_takers_drift.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
