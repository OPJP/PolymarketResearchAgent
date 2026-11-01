"""Iteration 13 (X118 step 2 at the decision clock; own state, reported with and without): adds the operator's realized
LARGE-order net (decayed 60 s, block ts in [a - 180 s, a - 2 s]; side13.kern) and the same for its SMALL orders to the
decision-clock side frame of dcside13 (10-20 / 10-21, fit one day, score the other; a disclosed deviation from pre-registration
3, which needs 10-17..19). Usage: python dcown13.py FRAME_TAG"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
from side13 import kern
import dcside13 as dc
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
tag = sys.argv[1]
X = pd.read_parquet(f"{C}/it13/dcside13_frame{tag}.parquet")
win = pd.read_parquet(f"{C}/windows.parquet").set_index("cid")
fl = pd.read_parquet(f"{C}/fills.parquet", columns=["oh", "shares", "cid", "rel", "is_up", "start_ts"])
fl = fl[fl.cid.isin(set(X.cid))]
fl["osz"] = fl.groupby("oh").shares.transform("sum"); fl["large"] = fl.osz >= 45
fl["sg"] = np.where(fl.is_up, 1.0, -1.0) * fl.shares
KL, KS = np.zeros(len(X)), np.zeros(len(X))
g = {c: d.sort_values("rel") for c, d in fl.groupby("cid")}
for cid, idx in X.groupby("cid").indices.items():
    s_arr = X.rel.to_numpy()[idx]
    d = g.get(cid)
    if d is None:
        continue
    for big, out in ((True, KL), (False, KS)):
        h = d[d.large == big]
        out[idx] = kern(h.rel.to_numpy(float), h.sg.to_numpy(float), s_arr)
X["KL"], X["KS"] = KL, KS
pm = ["rel", "askU_0", "askD_0", "daskU_500", "daskD_500", "daskU_3000", "daskD_3000", "dist"]
ven = [c for c in X.columns if any(c.startswith(p) for p in ("bs_", "by_", "bf_", "ok_"))]
days = sorted(X.day.unique()); res = {"days": days}
y = X.up.to_numpy(); wal = X.wallet.to_numpy(); lg = X.osz.to_numpy() >= 45
for fd in days:
    fm = (X.day == fd).to_numpy(); sm_ = ~fm; o = {}
    for nm, cols in (("full", pm + ven), ("full_own", pm + ven + ["KL", "KS"]), ("own_only", ["rel", "KL", "KS"])):
        m = lgb.train(dc.PARAMS, lgb.Dataset(X.loc[fm, cols], y[fm]), num_boost_round=dc.ROUNDS)
        ok = (m.predict(X.loc[sm_, cols], num_threads=4) > 0.5).astype(int) == y[sm_]
        o[nm] = {"acc": round(float(ok.mean()), 4), "by_wallet": {w: round(float(ok[wal[sm_] == w].mean()), 4) for w in ("DS", "GF", "XM")},
                 "small": round(float(ok[~lg[sm_]].mean()), 4), "large": round(float(ok[lg[sm_]].mean()), 4)}
    # accuracy of the full model by decision time in the window (opening decisions: X124)
    rel = X.rel.to_numpy()[sm_]
    m = lgb.train(dc.PARAMS, lgb.Dataset(X.loc[fm, pm + ven], y[fm]), num_boost_round=dc.ROUNDS)
    ok = (m.predict(X.loc[sm_, pm + ven], num_threads=4) > 0.5).astype(int) == y[sm_]
    o["full_by_rel"] = {f"{a}-{b}": [round(float(ok[(rel >= a) & (rel < b)].mean()), 4), int(((rel >= a) & (rel < b)).sum())] for a, b in ((-60, 15), (15, 60), (60, 120), (120, 180), (180, 240), (240, 300))}
    o["share_large_by_rel"] = {f"{a}-{b}": round(float(lg[sm_][(rel >= a) & (rel < b)].mean()), 4) for a, b in ((-60, 15), (15, 60), (60, 300))}
    res["fit_" + fd] = o
    print(fd, json.dumps(o), flush=True)
json.dump(res, open(f"{R}/dcown13{tag}.json", "w"), indent=1)
