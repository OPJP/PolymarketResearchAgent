"""Iteration 17 (X168 = information panel P5, lite form with DVOL; the binding size coin of finding 5): does a VALUATION edge pick WHICH
decisions are large? Operator taker orders of 10-20..22 with exact calldata classes (as smach17). At the decision (knee X = m - 260 ms):
spot S = Binance 1-s close of the last second ending before X (cache binance_1s), strike K = the window's priceToBeat (known at the
start), tau = end - X; sigma_IV = DVOL / 100 annualized (Deribit 1-min index, the last complete minute; iv13.dvol_minutes, cached),
sigma_RV = std of 1-s log returns over the last 300 s; digital fair value of the bought outcome under each sigma; market price p =
the last Polymarket trade on o with server ms <= m - 230 from the public capture, operator transactions excluded. Features: edge_IV,
edge_RV, |edge|, sigma_IV / sigma_RV, fair value distance from 0.5. Logistic models FIT on 10-20, AUC on 10-21..22 (and reverse):
public base (slot class, window-time bins) vs + edge features; operator-state base (+ S-relation and E, the true decision memory) vs
+ edge features; per wallet and pooled. A measurement (not pre-registered as a claim). Usage: python iv17.py"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score as auc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
S = os.environ["RE16_SCRATCH"]
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
DAYS = ["10-20", "10-21", "10-22"]; W3 = ("DS", "GF", "XM")
cols = ["tx", "role", "taker_amt", "oside"]
cds = [pd.read_parquet(C + "/calldata_sample.parquet", columns=cols), pd.read_parquet(S + "/it15/cl_orders.parquet", columns=cols)]
cds += [pd.read_parquet(f"{S}/it16/cdfull_{d}.parquet", columns=cols) for d in DAYS]
cd = pd.concat(cds); cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["tx"] = cd.tx.str.lower(); cd = cd.drop_duplicates("tx")
mp = pd.concat([pd.read_parquet(f"{S}/it15/l2ord_2026-{d}.parquet", columns=["tx", "cid", "wallet", "m", "token"]) for d in DAYS])
mp["tx"] = mp.tx.str.lower(); mp = mp.merge(cd[["tx", "taker_amt"]], on="tx", how="left").drop_duplicates(["cid", "wallet", "m"])
p = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "start_ts"])
p["dd"] = pd.to_datetime(p.start_ts, unit="s").dt.strftime("%m-%d")
p = p[p.dd.isin(DAYS)].merge(mp[["cid", "wallet", "m", "taker_amt", "token"]], on=["cid", "wallet", "m"], how="left")
p = p[p.taker_amt.notna()].copy(); p["L"] = (p.taker_amt >= 90).astype(int); p["sg"] = np.where(p.up == 1, 1, -1)
p = p.sort_values(["start_ts", "m"]).reset_index(drop=True)
q = p.sort_values(["cid", "up", "m"]); p.loc[q.index, "gap"] = q.m - q.groupby(["cid", "up"]).m.shift()
p["slot"] = np.where(p.gap < 150, 2, np.where(p.gap < 400, 1, 0)); p["tb"] = np.digitize(p.m / 1000.0 - p.start_ts, [30, 60, 120])
# true decision memory (as smach17)
Sv = np.zeros(len(p), int); Ev = np.zeros(len(p))
for st, g in p.groupby("start_ts", sort=False):
    mm = g.m.to_numpy(); L = g.L.to_numpy(); sg = g.sg.to_numpy(); oz = g.taker_amt.to_numpy(); s_cur, e_cur, j = 0, 0.0, 0
    for k in range(len(g)):
        while j < k and mm[j] < mm[k]:
            if L[j]:
                if sg[j] != s_cur:
                    s_cur, e_cur = sg[j], 0.0
                e_cur += oz[j]
            j += 1
        Sv[g.index[k]], Ev[g.index[k]] = s_cur, e_cur
p["S"] = Sv; p["E"] = Ev; p["rel_"] = np.where(p.S == 0, 0, np.where(p.S == p.sg, 1, 2))
# spot, strike, tau, sigmas
sp = pd.read_parquet(C + "/binance_1s.parquet").set_index("sec").close
X = (p.m.to_numpy() - 260) // 1000 - 1
p["Sx"] = sp.reindex(X).to_numpy()
lr = np.log(sp).diff()
rv = lr.rolling(300, min_periods=200).std()
p["sig_rv"] = rv.reindex(X).to_numpy()
ptb = pd.read_parquet(C + "/ptb.parquet").set_index("start").priceToBeat
p["K"] = ptb.reindex(p.start_ts.to_numpy()).to_numpy()
p["tau"] = np.maximum(p.start_ts + 300 - (p.m - 260) / 1000.0, 1.0)
import iv13
dv = iv13.dvol_minutes()
mi = ((p.m.to_numpy() - 260) // 60000) * 60 - 60
p["dvol"] = dv.reindex(mi).ffill().to_numpy()
p["sig_iv"] = p.dvol / np.sqrt(365 * 86400.0)
# Polymarket last trade on o (operator txs excluded)
fl = pd.read_parquet(C + "/fills.parquet", columns=["tx"]); excl = set(fl.tx.str.lower())
lt = []
for d in DAYS:
    tr = pd.read_parquet(f"{S}/it13/hf_dl/pm_trades_2026-{d}.parquet", columns=["exchangeTimestampMs", "transactionHash", "tokenId", "tradePrice"])
    tr = tr[~tr.transactionHash.str.lower().isin(excl)]; tr["tokenId"] = tr.tokenId.astype(str); lt.append(tr.drop(columns=["transactionHash"]))
tr = pd.concat(lt).sort_values("exchangeTimestampMs", kind="stable")
byt = {k: (g.exchangeTimestampMs.to_numpy(np.int64), g.tradePrice.to_numpy(float)) for k, g in tr.groupby("tokenId")}
pl = np.full(len(p), np.nan)
for tok, g in p.groupby(p.token.astype(str)):
    if tok in byt:
        T, P_ = byt[tok]; i = np.searchsorted(T, g.m.to_numpy() - 230, "right") - 1
        ok = i >= 0; v = np.full(len(g), np.nan); v[ok] = P_[i[ok]]; pl[g.index.to_numpy()] = v
p["p_last"] = pl
z = np.log(p.Sx / p.K)
for nm, sg_ in (("iv", p.sig_iv), ("rv", p.sig_rv)):
    fu = norm.cdf(z / (sg_ * np.sqrt(p.tau)))
    p[f"fv_{nm}"] = np.where(p.up == 1, fu, 1 - fu)
    p[f"edge_{nm}"] = p[f"fv_{nm}"] - p.p_last
p["ivrv"] = p.sig_iv / p.sig_rv
p = p.dropna(subset=["edge_iv", "edge_rv", "ivrv"]).reset_index(drop=True)
res = {"orders": int(len(p)), "by_day": p.groupby("dd").size().to_dict()}


def des(df, base, extra):
    M = [np.eye(3)[df.slot.to_numpy()], np.eye(4)[df.tb.to_numpy()]]
    if base == "state":
        M += [np.eye(3)[df.rel_.to_numpy()], (df.rel_ == 1).to_numpy()[:, None] * np.log1p(df.E.to_numpy())[:, None], (df.rel_ == 2).to_numpy()[:, None] * np.log1p(df.E.to_numpy())[:, None]]
    if extra:
        e1, e2 = df.edge_iv.to_numpy(), df.edge_rv.to_numpy()
        M += [np.column_stack([e1, np.abs(e1), e2, np.abs(e2), np.log(df.ivrv.clip(0.05, 50).to_numpy()), np.abs(df.fv_iv.to_numpy() - 0.5)])]
    return np.column_stack(M)


for split, fit_d, sco_d in (("fwd", ["10-20"], ["10-21", "10-22"]), ("rev", ["10-21", "10-22"], ["10-20"])):
    f = p[p.dd.isin(fit_d)]; s_ = p[p.dd.isin(sco_d)]
    rr = {}
    for base in ("public", "state"):
        for extra in (False, True):
            key = f"{base}{'+edge' if extra else ''}"
            out = {}
            for w in ("ALL",) + W3:
                ff = f if w == "ALL" else f[f.wallet == w]; ss = s_ if w == "ALL" else s_[s_.wallet == w]
                mdl = LogisticRegression(C=1.0, max_iter=3000).fit(des(ff, base, extra), ff.L)
                out[w] = round(float(auc(ss.L, mdl.predict_proba(des(ss, base, extra))[:, 1])), 4)
            rr[key] = out
    res[split] = rr
    print(split, json.dumps(rr), flush=True)
# direct: |edge| deciles vs P(large) on all days, within wallet
p["absedge"] = p.edge_iv.abs()
res["P_large_by_absedge_iv_quintile"] = {w: [round(float(x), 4) for x in p[p.wallet == w].groupby(pd.qcut(p[p.wallet == w].absedge, 5, labels=False, duplicates="drop")).L.mean()] for w in W3}
res["P_large_by_edge_iv_sign_toward_o"] = {w: {"edge>0": round(float(p[(p.wallet == w) & (p.edge_iv > 0)].L.mean()), 4), "edge<=0": round(float(p[(p.wallet == w) & (p.edge_iv <= 0)].L.mean()), 4)} for w in W3}
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/iv17.json", "w"), indent=1, default=str)
print(json.dumps({k: res[k] for k in ("P_large_by_absedge_iv_quintile", "P_large_by_edge_iv_sign_toward_o")}))
