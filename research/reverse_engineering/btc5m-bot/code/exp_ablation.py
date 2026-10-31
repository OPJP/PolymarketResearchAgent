"""Ablation: spot+tape model without the 1-2 s tape-activity features (n1, n2, flow1, flow2, age_last) -> how much is race co-occurrence."""
import sys, os, time, json
sys.path.insert(0, "/home/user/PolymarketResearchAgent/research/reverse_engineering/btc5m-bot/code")
import numpy as np, pandas as pd
from spot import Spot
from cells import build_cells, FEATS
from tape_feats import add_tape_feats, TAPE_FEATS
from sklearn.metrics import roc_auc_score
import lightgbm as lgb
C = "/home/user/PolymarketResearchAgent/.cache/re/btc5m-bot"
R = "/home/user/PolymarketResearchAgent/research/reverse_engineering/btc5m-bot"
V0, V1 = 1792108800, 1792713600
sp = Spot(); f = pd.read_parquet(f"{C}/fills.parquet"); win = pd.read_parquet(f"{C}/windows.parquet")
has = lambda d: d[[os.path.exists(f"{C}/tapes/{c}.parquet") for c in d.cid]]
wb = has(win[(win.start_ts >= 1791504000) & (win.start_ts < V0)]); wv = has(win[(win.start_ts >= V0) & (win.end_ts <= V1)])
cb = add_tape_feats(build_cells(wb, f, sp), f, sp); cv = add_tape_feats(build_cells(wv, f, sp), f, sp)
params = dict(objective="binary", learning_rate=0.1, num_leaves=63, min_data_in_leaf=300, feature_fraction=0.8, bagging_fraction=0.5, bagging_freq=1, verbose=-1, num_threads=2)
res = {}
for name, drop in (("no_short_activity", {"n1", "n2", "flow1", "flow2", "age_last", "age_ask", "age_bid"}), ("market_only_no_spot", set(FEATS) - {"rel", "tau"})):
    feats = [x for x in FEATS + TAPE_FEATS if x not in drop]
    m = lgb.train(params, lgb.Dataset(cb[feats], cb.y), num_boost_round=150)
    res[name] = round(float(roc_auc_score(cv.y, m.predict(cv[feats]))), 4)
    print(name, res[name], flush=True)
json.dump(res, open(f"{R}/results_ablation.json", "w"), indent=1)
