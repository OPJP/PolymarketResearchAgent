"""Iteration 9, X131 (assumptions panel iter8 P5): attribute the wallet's maker fills (16-22 Oct, calldata) to the
transaction's taker class: group P (BUILD-fixed members), group G (BUILD fixed-lag co-signers of P4e with >= 20% of their
BUILD prints in GRID events), other. Per market: regress settlement PnL and its residual part (PnL - locked margin) on
paired shares and maker shares taken by each class; drop-one partial R^2. Output: results/residual_attrib.json"""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
r = json.load(open(RES / "selection_groupP.json"))
GP = set(r["members"])
GG = {w for w, v in r["candidates"].items() if not v["member"] and (v["build_grid_share"] or 0) >= 0.2}
a = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "cid", "oi", "fill", "price", "sign_ms"])
a["maker"] = a.maker.str.lower()
tk = a[a.idx == -1][["tx", "maker"]].rename(columns={"maker": "taker"}).drop_duplicates("tx")
m = a[(a.maker == W) & (a.idx >= 0)].merge(tk, on="tx", how="left")
m["cls"] = np.where(m.taker.isin(GP), "P", np.where(m.taker.isin(GG), "G", "O"))
pm = pd.read_parquet(OUT / "per_market.parquet")
pm["margin"] = pm.pairs * (1 - pm.pair_cost)
pm["resid"] = pm.pnl - pm.margin
sh = m.pivot_table(index="cid", columns="cls", values="fill", aggfunc="sum").fillna(0)
X = pm.set_index("cid").join(sh, how="left").fillna({"P": 0, "G": 0, "O": 0})
out = {"markets": int(len(X)), "maker_shares_by_class": {c: round(float(m.loc[m.cls == c, "fill"].sum()), 0) for c in "PGO"},
       "maker_share_frac": {c: round(float(m.loc[m.cls == c, "fill"].sum() / m.fill.sum()), 4) for c in "PGO"},
       "avg_price_by_class": {c: round(float((m.loc[m.cls == c, "fill"] * m.loc[m.cls == c, "price"]).sum() / max(m.loc[m.cls == c, "fill"].sum(), 1)), 4) for c in "PGO"}}
def ols(y, cols):
    Z = np.column_stack([np.ones(len(X))] + [X[c].to_numpy(float) for c in cols])
    b, *_ = np.linalg.lstsq(Z, y, rcond=None)
    e = y - Z @ b
    return 1 - e.var() / y.var(), b
for tgt in ("pnl", "resid"):
    y = X[tgt].to_numpy(float)
    cols = ["pairs", "P", "G", "O"]
    r2, b = ols(y, cols)
    part = {}
    for c in cols:
        r2c, _ = ols(y, [k for k in cols if k != c])
        part[c] = round(float(r2 - r2c), 4)
    out[tgt] = {"r2": round(float(r2), 4), "coef_per_share": dict(zip(["icpt"] + cols, [round(float(v), 5) for v in b])), "drop_one_partial_r2": part,
                "corr": {c: round(float(np.corrcoef(X[c], y)[0, 1]), 3) for c in cols}}
print(json.dumps(out, indent=1))
json.dump(out, open(RES / "residual_attrib.json", "w"), indent=1)
