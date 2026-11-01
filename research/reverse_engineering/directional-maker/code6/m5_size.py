"""Iteration 6, panel iter5 mechanics M5 (X34): is the off-session 500-share size class switched on by futures vol?
Per BTC 5m window of the released lot: base size class = the mode of the original sizes (calldata) of the cluster's
filled orders in the window (b1_orders_lot.parquet; STUDY case by case, VALIDATE aggregate). Outside the weekday
12-21 UTC session, label = class 500. Features known at the window open: Binance USD-M futures realised 1-s vol over
the last 60 / 300 / 900 s and |return| over 60 / 300 s. AUC per half; also the class transition times across wallets.
    python code6/m5_size.py"""
import json
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
o = pd.read_parquet(C / "b1_orders_lot.parquet", columns=["cond", "sz", "bts", "tag", "w", "maker"])
w = pd.read_parquet(C / "exam" / "windows_5m.parquet")
st = dict(zip(w.cid, w.start_ts))
o["st"] = o.cond.map(st)
o = o.dropna(subset=["st"])
o["cls"] = o.sz.round(0)
g = o.groupby("cond").agg(st=("st", "first"), tag=("tag", "first"), cls=("cls", lambda s: s.value_counts().index[0]), n=("cls", "size"))
g = g[g.n >= 2]
fut = []
for d in sorted(set(pd.to_datetime(g.st, unit="s").dt.strftime("%Y-%m-%d"))):
    p = C / "fut1s" / f"{d}.parquet"
    if p.exists():
        fut.append(pd.read_parquet(p, columns=["sec", "px"]))
    pp = C / "fut1s" / (pd.Timestamp(d) - pd.Timedelta(days=1)).strftime("%Y-%m-%d.parquet")
    if pp.exists():
        fut.append(pd.read_parquet(pp, columns=["sec", "px"]))
F = pd.concat(fut).drop_duplicates("sec").sort_values("sec").set_index("sec").px
lr = np.log(F).diff()
def feats(t):
    o_ = {}
    for L in (60, 300, 900):
        o_[f"vol{L}"] = float(lr.loc[t - L:t - 1].std())
    for L in (60, 300):
        a_, b_ = F.get(t - L, np.nan), F.get(t - 1, np.nan)
        o_[f"absret{L}"] = abs(np.log(b_ / a_)) if a_ == a_ and b_ == b_ else np.nan
    return o_
X = pd.DataFrame([feats(int(t)) for t in g.st], index=g.index)
g = g.join(X)
ts = pd.to_datetime(g.st, unit="s")
g["session"] = (ts.dt.weekday < 5) & (ts.dt.hour >= 12) & (ts.dt.hour < 21)
out = {}
for tag, h in g.groupby("tag"):
    off = h[~h.session]
    r = {"windows": int(len(h)), "off_session_windows": int(len(off)), "off_session_500_share": round(float((off.cls == 500).mean()), 3),
         "session_500_share": round(float((h[h.session].cls == 500).mean()), 3), "class_counts_off": off.cls.value_counts().head(6).to_dict()}
    y = (off.cls == 500).astype(int)
    if y.nunique() == 2:
        for c in ("vol60", "vol300", "vol900", "absret60", "absret300"):
            v = off[[c]].assign(y=y).dropna()
            r[f"auc_{c}"] = round(float(roc_auc_score(v.y, v[c])), 3)
    out[tag] = r
# thresholds fitted on STUDY applied to VALIDATE (aggregate)
s_ = g[(g.tag == "study") & ~g.session]; v_ = g[(g.tag == "valid") & ~g.session]
if len(s_) and len(v_):
    thr = float(s_.vol300.quantile(1 - (s_.cls == 500).mean())) if (s_.cls == 500).any() else np.nan
    pred = v_.vol300 >= thr
    yv = v_.cls == 500
    out["study_threshold_vol300"] = thr
    out["validate_with_study_threshold"] = {"recall": round(float(pred[yv].mean()), 3) if yv.any() else None,
                                            "precision": round(float(yv[pred].mean()), 3) if pred.any() else None,
                                            "share_500_explained": round(float((pred & yv).sum() / max(yv.sum(), 1)), 3)}
(HERE.parent / "results" / "iter6_m5_size.json").write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str))
