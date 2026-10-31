"""Secondary: spot+tape model WITH own-state (cluster net inventory in the window up to s-1; no own fill counts/times)."""
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
wb = wb[wb.cid.isin(set(f.cid)) | True]


def add_inv(cells):
    # shares bought of each outcome by the cluster with block ts <= s-1, per window
    g = f[(f.rel >= 0) & (f.rel < 300)]
    a = g.groupby(["cid", "is_up", "rel"]).agg(sh=("shares", "sum"), usd=("usdc", "sum")).reset_index()
    out_sh = np.zeros(len(cells)); out_sh_other = np.zeros(len(cells)); out_cost = np.full(len(cells), np.nan)
    key = pd.MultiIndex.from_arrays([cells.cid, cells.is_up, cells.rel.astype(np.int64)])
    full = a.set_index(["cid", "is_up", "rel"])
    tmp = pd.DataFrame({"sh": 0.0, "usd": 0.0}, index=key)
    tmp.loc[full.index.intersection(key), ["sh", "usd"]] = full.loc[full.index.intersection(key), ["sh", "usd"]].to_numpy()
    tmp = tmp.reset_index()
    tmp.columns = ["cid", "is_up", "rel", "sh", "usd"]
    tmp = tmp.sort_values(["cid", "is_up", "rel"])
    tmp["csh"] = tmp.groupby(["cid", "is_up"]).sh.cumsum() - tmp.sh   # strictly before s
    tmp["cusd"] = tmp.groupby(["cid", "is_up"]).usd.cumsum() - tmp.usd
    m = cells[["cid", "is_up", "rel"]].merge(tmp[["cid", "is_up", "rel", "csh", "cusd"]], on=["cid", "is_up", "rel"], how="left")
    oth = tmp[["cid", "is_up", "rel", "csh", "cusd"]].copy(); oth["is_up"] = ~oth.is_up
    m2 = cells[["cid", "is_up", "rel"]].merge(oth.rename(columns={"csh": "csh_o", "cusd": "cusd_o"}), on=["cid", "is_up", "rel"], how="left")
    cells["inv_o"] = m.csh.to_numpy(); cells["inv_other"] = m2.csh_o.to_numpy()
    cells["inv_net"] = cells.inv_o - cells.inv_other
    with np.errstate(invalid="ignore", divide="ignore"):
        cells["avg_o"] = m.cusd.to_numpy() / m.csh.to_numpy(); cells["avg_other"] = m2.cusd_o.to_numpy() / m2.csh_o.to_numpy()
    cells["pair_if_buy"] = cells.ask_o + cells.avg_other
    return cells


cb = add_inv(add_tape_feats(build_cells(wb, f, sp), f, sp)); cv = add_inv(add_tape_feats(build_cells(wv, f, sp), f, sp))
OWN = ["inv_o", "inv_other", "inv_net", "avg_o", "avg_other", "pair_if_buy"]
params = dict(objective="binary", learning_rate=0.1, num_leaves=63, min_data_in_leaf=300, feature_fraction=0.8, bagging_fraction=0.5, bagging_freq=1, verbose=-1, num_threads=2)
feats = FEATS + TAPE_FEATS + OWN
m = lgb.train(params, lgb.Dataset(cb[feats], cb.y), num_boost_round=150)
p = m.predict(cv[feats])
imp = sorted(zip(feats, m.feature_importance("gain")), key=lambda t: -t[1]); tot = sum(v for _, v in imp)
res = {"with_own_state:y": round(float(roc_auc_score(cv.y, p)), 4), "top_gain_share": [(a, round(float(b / tot), 3)) for a, b in imp[:12]]}
print(res, flush=True)
json.dump(res, open(f"{R}/results_own_state.json", "w"), indent=1)
