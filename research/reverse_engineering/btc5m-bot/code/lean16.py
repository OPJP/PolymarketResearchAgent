"""Iteration 16 (X152 / X157 / X156 step 2): the size as a LEAN CONTROLLER (two-stream account of iteration 13 at the order level).
Fit on the complete calldata record of FIT days (exact original sizes): P(large | wallet, state) where state = the order's side
relative to the operator's LARGE net so far in the window (orders matched before m - LAG; 'none' if zero, 'with' if the same sign,
'against' otherwise). Score: on SCORE days walk the operator's TRUE taker orders (timing and carrier known: an oracle for those two
parts only) with the dc14 side (pre-registration 5 exam route) and a SIMULATED lean (the rule's own expected large net, no operator
size or fill information); window x = sum side x E[size]; r with the window net N and the PnL proxy r. Variants: menu, per-wallet
constant, lean controller (simulated state), lean controller with the operator's TRUE state (oracle state), class oracle.
Usage: python lean16.py FITDAYS SCOREDAYS"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import pearsonr, spearmanr

S = os.environ["RE16_SCRATCH"]
FIT = sys.argv[1].split(","); SCO = sys.argv[2].split(",")
LAG = 300
W3 = ("DS", "GF", "XM")
WM = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
cols = ["tx", "role", "taker_amt", "oside"]
cds = [pd.read_parquet(".cache/re/btc5m-bot/calldata_sample.parquet", columns=cols), pd.read_parquet(S + "/it15/cl_orders.parquet", columns=cols)]
for d in sorted(set(FIT + SCO)):
    fn = f"{S}/it16/cdfull_{d}.parquet"
    if os.path.exists(fn):
        cds.append(pd.read_parquet(fn, columns=cols))
cd = pd.concat(cds); cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["tx"] = cd.tx.str.lower(); cd = cd.drop_duplicates("tx")
maps = [pd.read_parquet(f"{S}/it15/l2ord_2026-{d}.parquet", columns=["tx", "cid", "wallet", "m"]) for d in sorted(set(FIT + SCO))]
mp = pd.concat(maps); mp["tx"] = mp.tx.str.lower(); mp = mp.merge(cd[["tx", "taker_amt"]], on="tx", how="left").drop_duplicates(["cid", "wallet", "m"])
p = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "osz", "start_ts", "p_dc14_spot_own"])
p["dd"] = pd.to_datetime(p.start_ts, unit="s").dt.strftime("%m-%d")
p = p[p.dd.isin(FIT + SCO)].merge(mp[["cid", "wallet", "m", "taker_amt"]], on=["cid", "wallet", "m"], how="left")
p["orig"] = p.taker_amt
p["L"] = np.where(p.orig.notna(), (p.orig >= 90).astype(float), np.nan)
p["sg"] = np.where(p.up == 1, 1.0, -1.0); p["ps"] = 2 * p.p_dc14_spot_own - 1; p["sh"] = np.sign(p.ps)
p = p.sort_values("m").reset_index(drop=True)
print("orders", len(p), "with exact size", int(p.L.notna().sum()), "by day", p.groupby("dd").L.apply(lambda s: round(float(s.notna().mean()), 3)).to_dict(), flush=True)
res = {"fit": FIT, "score": SCO, "lag_ms": LAG}


def true_state(g):
    """operator large net (true sizes x realized total fill osz) from orders matched before m - LAG, per order, within a window"""
    mm = g.m.to_numpy(); v = (g.L.fillna(0).to_numpy() * g.sg.to_numpy() * g.osz.to_numpy())
    cs = np.cumsum(v); j = np.searchsorted(mm, mm - LAG, "right") - 1
    return np.where(j >= 0, cs[np.clip(j, 0, len(cs) - 1)], 0.0)


p["lean_true"] = np.concatenate([true_state(g) for _, g in p.groupby("start_ts", sort=False)]) if False else 0.0
for st, g in p.groupby("start_ts"):
    p.loc[g.index, "lean_true"] = true_state(g)


def rel(side, lean):
    return np.where(lean == 0, 0, np.where(np.sign(lean) == side, 1, 2))   # 0 none, 1 with, 2 against


f = p[p.dd.isin(FIT) & p.L.notna()].copy()
f["rel"] = rel(f.sg.to_numpy(), f.lean_true.to_numpy())
tab = f.groupby(["wallet", "rel"]).L.mean().unstack()
cnt = f.groupby(["wallet", "rel"]).L.size().unstack()
res["P(large|wallet,rel)_fit"] = tab.round(4).to_dict("index"); res["n_fit"] = cnt.to_dict("index")
pw = f.groupby("wallet").L.mean().to_dict(); res["P(large|wallet)_fit"] = {k: round(v, 4) for k, v in pw.items()}
fill = f.groupby(["wallet", "L"]).osz.mean().unstack().to_dict("index")   # mean realized total fill by wallet and class
res["mean_fill_by_class"] = {w: {int(k): round(v, 2) for k, v in d.items()} for w, d in fill.items()}
print(json.dumps({k: res[k] for k in ("P(large|wallet,rel)_fit", "P(large|wallet)_fit", "mean_fill_by_class")}, indent=0), flush=True)
T = {w: [tab.loc[w, c] for c in (0, 1, 2)] for w in W3}
EF = {w: (fill[w][0.0], fill[w][1.0]) for w in W3}
sc = p[p.dd.isin(SCO)].copy()
# simulated lean: the rule's own expected large net from its own E[large] and expected fill, with the dc14 side
xs_sim = np.zeros(len(sc)); xs_tr = np.zeros(len(sc)); pl_sim = np.zeros(len(sc))
for st, g in sc.groupby("start_ts"):
    ii = g.index.to_numpy(); mm = g.m.to_numpy(); sh = g.sh.to_numpy(); ww = g.wallet.to_numpy()
    lean_t = g.lean_true.to_numpy()
    contrib = np.zeros(len(g)); pls = np.zeros(len(g))
    for k in range(len(g)):
        j = np.searchsorted(mm, mm[k] - LAG, "right")       # orders matched before m - LAG
        lean = contrib[:j].sum()
        r_ = 0 if abs(lean) < 1e-9 else (1 if np.sign(lean) == sh[k] else 2)
        pL = T[ww[k]][r_]; pls[k] = pL
        ef_small, ef_large = EF[ww[k]]
        contrib[k] = pL * ef_large * sh[k]                   # expected LARGE net contribution (own state of the rule)
    pl_sim[np.searchsorted(sc.index.to_numpy(), ii)] = pls
sc["pL_sim"] = pl_sim
sc["pL_true_state"] = [T[w][r_] for w, r_ in zip(sc.wallet, rel(sc.sh.to_numpy(), sc.lean_true.to_numpy()))]
sc["pL_wallet"] = sc.wallet.map(pw)
f2 = pd.read_parquet(".cache/re/btc5m-bot/fills.parquet", columns=["wallet", "is_up", "shares", "price", "fee_usd", "start_ts", "up_payout"])
f2 = f2[f2.start_ts.isin(sc.start_ts.unique())].copy()
f2["sgs"] = np.where(f2.is_up, 1.0, -1.0) * f2.shares
f2["pay"] = np.where(f2.is_up, f2.up_payout, 1 - f2.up_payout); f2["pnl"] = f2.shares * (f2.pay - f2.price) - f2.fee_usd
Wn = f2.groupby("start_ts").agg(N=("sgs", "sum"), pnl=("pnl", "sum"), up=("up_payout", "first"))
Wl = {w: g.groupby("start_ts").agg(N=("sgs", "sum"), pnl=("pnl", "sum")) for w, g in f2.groupby("wallet")}
menu = float(p[p.dd.isin(FIT)].L.mean())


def esize(pl, w):
    a = np.array([EF[x][0] for x in w]); b = np.array([EF[x][1] for x in w])
    return (1 - pl) * a + pl * b


variants = {"menu": esize(np.full(len(sc), menu), sc.wallet), "wallet_const": esize(sc.pL_wallet.to_numpy(), sc.wallet),
            "lean_sim": esize(sc.pL_sim.to_numpy(), sc.wallet), "lean_true_state": esize(sc.pL_true_state.to_numpy(), sc.wallet)}
if sc.L.notna().mean() > 0.95:
    variants["class_oracle"] = esize(sc.L.fillna(menu).to_numpy(), sc.wallet)
    variants["true_fill"] = sc.osz.to_numpy()
out = {}
for side in ("sg", "ps"):
    for nm, sz in variants.items():
        x = pd.Series(sc[side].to_numpy() * sz, index=sc.index).groupby(sc.start_ts).sum()
        J = Wn.join(x.rename("x"), how="inner").fillna(0); q = J.x * (J.up - 0.5)
        rec = {"rN": round(pearsonr(J.x, J.N)[0], 4), "pnl_P": round(pearsonr(q, J.pnl)[0], 4), "pnl_S": round(spearmanr(q, J.pnl)[0], 4), "n": len(J)}
        for w in W3:
            mw = (sc.wallet == w).to_numpy()
            xw = pd.Series(sc[side].to_numpy()[mw] * sz[mw], index=sc.index[mw]).groupby(sc.start_ts[mw]).sum()
            Jw = Wl[w].join(xw.rename("x"), how="inner").join(Wn[["up"]]).fillna(0)
            rec[f"{w}_rN"] = round(pearsonr(Jw.x, Jw.N)[0], 4)
            rec[f"{w}_pnl_P"] = round(pearsonr(Jw.x * (Jw.up - 0.5), Jw.pnl)[0], 4)
        out[f"{side}|{nm}"] = rec
        print(side, nm, rec, flush=True)
res["ladder"] = out
if sc.L.notna().mean() > 0.5:
    from sklearn.metrics import roc_auc_score as auc
    m = sc.L.notna()
    res["auc_score_days"] = {w: {k: round(float(auc(sc.L[m & (sc.wallet == w)], sc[k][m & (sc.wallet == w)])), 4) for k in ("pL_sim", "pL_true_state")} for w in W3}
    print(res["auc_score_days"])
json.dump(res, open(f"research/reverse_engineering/btc5m-bot/results/lean16_{'_'.join(SCO)}.json", "w"), indent=1, default=str)
