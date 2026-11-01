"""Iteration 9: train the frozen v5 price model (final_rule._price_feats features, public, point-in-time) on the wallet's
CS2 maker orders: build = game start in BUILD (10-16..10-20), exam = all development orders before H (same recipe).
LightGBM multiclass over k = round(100 (price - last print)) clipped to [-10, 3]; 200 trees, 15 leaves, max_bin 63.
Writes code/final_rule_v5_price_gbm_{build,exam}.txt and prints the VALIDATE score of the build model."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
import final_rule as F
OUT = ROOT / ".cache/re/tommy-cs2-maker"
W = F.WALLET
VAL0 = 1792540800
GP = set(F.V5["members"]); GG = set(F.V5["group_G"])
a = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "cid", "oi", "price", "sign_ms", "salt", "gs_ts", "smt", "event"])
a["maker"] = a.maker.str.lower()
wtx = set(a.loc[a.maker == W, "tx"])
mo = a[(a.maker == W) & (a.idx >= 0)].drop_duplicates(["salt", "sign_ms"])
mo = mo[(mo.sign_ms > 1.79e12) & mo.cid.notna() & ~mo.event.astype(str).str.startswith("dota2")]
parts = []
for cid, g in mo.groupby("cid"):
    p = OUT / "tapes" / f"{cid}_tkw.parquet"
    if not p.exists():
        continue
    d = pd.read_parquet(p)
    d = d[~d.transactionHash.isin(wtx)]
    if len(d) < 5:
        continue
    f = F._price_feats(d, g, float(g.gs_ts.iloc[0]), GP, GG)
    f["price"] = g.price.to_numpy(float); f["gs"] = float(g.gs_ts.iloc[0])
    parts.append(f)
X = pd.concat(parts).dropna(subset=["lp"])
X["k"] = np.clip(np.round((X.price - X.lp) * 100), F.PRICE_KMIN, F.PRICE_KMAX).astype(int) - F.PRICE_KMIN
import lightgbm as lgb
for name, d in (("build", X[X.gs < VAL0]), ("exam", X)):
    ds = lgb.Dataset(d[F.PRICE_FEATS].to_numpy(float), label=d.k.to_numpy(), params={"max_bin": 63})
    bst = lgb.train({"objective": "multiclass", "num_class": F.PRICE_KMAX - F.PRICE_KMIN + 1, "learning_rate": 0.05, "num_leaves": 15,
                     "min_data_in_leaf": 50, "bagging_fraction": 0.8, "bagging_freq": 1, "feature_fraction": 0.8, "verbose": -1, "seed": 7},
                    ds, num_boost_round=200)
    bst.save_model(str(F.HERE / f"final_rule_v5_price_gbm_{name}.txt"))
F.CONSTANTS = "build"
v = X[X.gs >= VAL0]
pred = F.price_predict(v)
lp = v.lp.to_numpy()
tick = np.where((lp >= 0.04) & (lp <= 0.96), 0.01, 0.001)
print("VALIDATE CS2 orders", len(v), "model within tick", round(float((np.abs(pred - v.price) <= tick + 1e-9).mean()), 4),
      "last print", round(float((np.abs(lp - v.price) <= tick + 1e-9).mean()), 4))
imp = sorted(zip(F.PRICE_FEATS, lgb.Booster(model_file=str(F.HERE / "final_rule_v5_price_gbm_build.txt")).feature_importance("gain")), key=lambda x: -x[1])
print([(f, round(float(g))) for f, g in imp[:8]])
