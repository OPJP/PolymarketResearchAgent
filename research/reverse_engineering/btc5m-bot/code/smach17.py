"""Iteration 17, PRE-REGISTRATION 12 (NOTES.md, written 09:45 UTC 11-01 before this runs): the bot's DECISION MEMORY as a hysteresis
state machine for the size class (panel iter16 mechanics P1 = X169 steps 1, 2, 4; assumptions P1 step 3 = X173: size drawn per
decision, no wallet identity), run on the replica's OWN sent orders.
Record: operator taker orders of 10-20..22 (it14 dcfit14 frame), exact calldata classes (large = original size >= 90).
State (frozen): slot class from the gap g to the previous operator taker order on the same (window, outcome): fast < 150 ms, seq
150-400 ms, first otherwise; S = outcome of the most recent large order (any of the three wallets) matched strictly before m; E =
large original shares sent on S since S was last set; rel = none / with / against the order's side.
Transition model: logistic regression, one-hot (slot x rel), log1p(E) x with / against, window-time bins; version 'dec' (no wallet)
and 'wal' (+ wallet one-hots; reported only: the true carrier leaks the class). FIT with the TRUE state and TRUE side.
Replica on SCORE days: the operator's true orders (timing, slot class and carrier from the record: an oracle for those parts only),
side = dc14 (p_dc14_spot_own), S_own / E_own from the replica's own drawn classes on its own sides, R redraws (vectorized), expected
window net x = sum side x E[fill | class, wallet] (lean16's convention); also the argmax replica. Measures: agreement of S_own with
the operator's S, AUC of the replica's P(large) for the large class, window-net r and the PnL proxy (Pearson / Spearman).
Usage: python smach17.py FITDAYS SCOREDAYS"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score as auc

S = os.environ["RE16_SCRATCH"]
FIT = sys.argv[1].split(","); SCO = sys.argv[2].split(",")
R = 200
W3 = ("DS", "GF", "XM")
rng = np.random.default_rng(17)
cols = ["tx", "role", "taker_amt", "oside"]
cds = [pd.read_parquet(".cache/re/btc5m-bot/calldata_sample.parquet", columns=cols), pd.read_parquet(S + "/it15/cl_orders.parquet", columns=cols)]
for d in sorted(set(FIT + SCO)):
    fn = f"{S}/it16/cdfull_{d}.parquet"
    if os.path.exists(fn):
        cds.append(pd.read_parquet(fn, columns=cols))
cd = pd.concat(cds); cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["tx"] = cd.tx.str.lower(); cd = cd.drop_duplicates("tx")
mp = pd.concat([pd.read_parquet(f"{S}/it15/l2ord_2026-{d}.parquet", columns=["tx", "cid", "wallet", "m"]) for d in sorted(set(FIT + SCO))])
mp["tx"] = mp.tx.str.lower(); mp = mp.merge(cd[["tx", "taker_amt"]], on="tx", how="left").drop_duplicates(["cid", "wallet", "m"])
p = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "osz", "start_ts", "p_dc14_spot_own"])
p["dd"] = pd.to_datetime(p.start_ts, unit="s").dt.strftime("%m-%d")
p = p[p.dd.isin(FIT + SCO)].merge(mp[["cid", "wallet", "m", "taker_amt"]], on=["cid", "wallet", "m"], how="left")
p["orig"] = p.taker_amt
p = p[p.orig.notna()].copy()
p["L"] = (p.orig >= 90).astype(int)
p["sg"] = np.where(p.up == 1, 1, -1); p["sh"] = np.where(p.p_dc14_spot_own > 0.5, 1, -1)
p = p.sort_values(["start_ts", "m"]).reset_index(drop=True)
print("orders", len(p), p.groupby("dd").size().to_dict(), flush=True)
# slot class
q = p.sort_values(["cid", "up", "m"])
gap = q.m - q.groupby(["cid", "up"]).m.shift()
p.loc[q.index, "gap"] = gap
p["slot"] = np.where(p.gap < 150, 2, np.where(p.gap < 400, 1, 0))      # 0 first, 1 seq, 2 fast
p["tb"] = np.digitize(p.m / 1000.0 - p.start_ts, [30, 60, 120])
LSZ = float(p[p.dd.isin(FIT) & (p.L == 1)].orig.mean())


def true_state(g):
    """S (last large outcome strictly before m), E (large original shares sent on S since S was last set), per order."""
    mm = g.m.to_numpy(); L = g.L.to_numpy(); sg = g.sg.to_numpy(); oz = g.orig.to_numpy()
    Sv = np.zeros(len(g), int); Ev = np.zeros(len(g))
    s_cur, e_cur = 0, 0.0
    pend = []   # orders matched at the same ms are not 'strictly before'
    j = 0
    for k in range(len(g)):
        while j < k and mm[j] < mm[k]:
            if L[j]:
                if sg[j] != s_cur:
                    s_cur, e_cur = sg[j], 0.0
                e_cur += oz[j]
            j += 1
        Sv[k], Ev[k] = s_cur, e_cur
    return Sv, Ev


p["S"] = 0; p["E"] = 0.0
for st, g in p.groupby("start_ts", sort=False):
    Sv, Ev = true_state(g)
    p.loc[g.index, "S"] = Sv; p.loc[g.index, "E"] = Ev


def rel(side, Sx):
    return np.where(Sx == 0, 0, np.where(Sx == side, 1, 2))


def design(slot, rl, E, tb, wal=None):
    n = len(slot)
    X = np.zeros((n, 9 + 2 + 3 + (3 if wal is not None else 0)))
    X[np.arange(n), slot * 3 + rl] = 1
    X[:, 9] = (rl == 1) * np.log1p(E); X[:, 10] = (rl == 2) * np.log1p(E)
    for b in (1, 2, 3):
        X[:, 10 + b] = tb == b
    if wal is not None:
        for i, w in enumerate(W3):
            X[:, 14 + i] = wal == w
    return X


f = p[p.dd.isin(FIT)]
res = {"fit": FIT, "score": SCO, "R": R, "large_size_mean_fit": round(LSZ, 1)}
models = {}
for ver in ("dec", "wal"):
    X = design(f.slot.to_numpy(), rel(f.sg.to_numpy(), f.S.to_numpy()), f.E.to_numpy(), f.tb.to_numpy(), f.wallet.to_numpy() if ver == "wal" else None)
    models[ver] = LogisticRegression(C=1.0, max_iter=2000).fit(X, f.L.to_numpy())
    res[f"fit_auc_{ver}"] = round(float(auc(f.L, models[ver].predict_proba(X)[:, 1])), 4)
# descriptive table on FIT (true side, true state)
f2 = f.assign(rl=rel(f.sg.to_numpy(), f.S.to_numpy()))
res["fit_table_P_large_slot_rel"] = {f"{sl}|{r_}": [round(float(x.L.mean()), 3), int(len(x))] for (sl, r_), x in f2.groupby(["slot", "rl"])}
sc = p[p.dd.isin(SCO)].copy()
# step 1: state definitions scored on SCORE days (true side): AUC of S-relation vs the class, per wallet x slot
s1 = {}
rl_true = rel(sc.sg.to_numpy(), sc.S.to_numpy())
for w in W3:
    for sl in (0, 1, 2):
        mk = (sc.wallet == w).to_numpy() & (sc.slot == sl).to_numpy()
        if mk.sum() > 50 and sc.L[mk].nunique() == 2:
            s1[f"{w}|slot{sl}"] = round(float(auc(sc.L[mk], np.where(rl_true[mk] == 1, 2, np.where(rl_true[mk] == 0, 1, 0)))), 4)
res["step1_auc_Srel_true_side"] = s1
coef = {v: (models[v].coef_[0], models[v].intercept_[0]) for v in models}


def plogit(v, slot, rl, E, tb, wal):
    c, b0 = coef[v]
    z = b0 + c[slot * 3 + rl] + (rl == 1) * c[9] * np.log1p(E) + (rl == 2) * c[10] * np.log1p(E) + np.where(tb > 0, c[np.clip(10 + tb, 11, 13)], 0.0)
    if v == "wal":
        z = z + c[14 + W3.index(wal)]
    return 1 / (1 + np.exp(-z))


fill = p[p.dd.isin(FIT)].groupby(["wallet", "L"]).osz.mean().unstack().to_dict("index")
EF = {w: (fill[w][0], fill[w][1]) for w in W3}
out_p = {v: np.zeros(len(sc)) for v in models}; out_x = {v: np.zeros(len(sc)) for v in models}
agree = {v: [] for v in models}; out_pmax = {v: np.zeros(len(sc)) for v in models}
pos = {ix: k for k, ix in enumerate(sc.index)}
for st, g in sc.groupby("start_ts", sort=False):
    sh = g.sh.to_numpy(); sl = g.slot.to_numpy(); tb = g.tb.to_numpy(); ww = g.wallet.to_numpy(); St = g.S.to_numpy(); mm = g.m.to_numpy()
    ii = np.array([pos[i] for i in g.index])
    for v in models:
        Sown = np.zeros(R, int); Eown = np.zeros(R)
        Sm, Em = 0, 0.0                                   # argmax replica
        hist = []                                          # (m, draws L, side) of earlier orders not yet applied
        applied = 0
        L_hist = np.zeros((len(g), R), bool)
        for k in range(len(g)):
            while applied < k and mm[applied] < mm[k]:      # apply earlier orders' classes (strictly before m)
                Ld = L_hist[applied]; s_ = sh[applied]
                flip = Ld & (Sown != s_)
                Sown = np.where(flip, s_, Sown); Eown = np.where(flip, 0.0, Eown)
                Eown = Eown + Ld * LSZ
                applied += 1
            rl_ = rel(sh[k], Sown)
            pk = plogit(v, np.full(R, sl[k]), rl_, Eown, np.full(R, tb[k]), ww[k])
            Ld = rng.random(R) < pk
            L_hist[k] = Ld
            out_p[v][ii[k]] = pk.mean()
            if St[k] != 0:
                agree[v].append(float((Sown == St[k]).mean()))
            # argmax replica (deterministic)
            pm = plogit(v, np.array([sl[k]]), rel(sh[k], np.array([Sm])), np.array([Em]), np.array([tb[k]]), ww[k])[0]
            out_pmax[v][ii[k]] = float(pm > 0.5)
            if pm > 0.5:
                if Sm != sh[k]:
                    Sm, Em = sh[k], 0.0
                Em += LSZ
# oracle state (operator's TRUE S / E, replica side)
p_or = {v: np.array([plogit(v, np.array([a]), rel(b, np.array([c])), np.array([d]), np.array([e]), w_)[0]
                     for a, b, c, d, e, w_ in zip(sc.slot, sc.sh, sc.S, sc.E, sc.tb, sc.wallet)]) for v in models}
f3 = pd.read_parquet(".cache/re/btc5m-bot/fills.parquet", columns=["wallet", "is_up", "shares", "price", "fee_usd", "start_ts", "up_payout"])
f3 = f3[f3.start_ts.isin(sc.start_ts.unique())].copy()
f3["sgs"] = np.where(f3.is_up, 1.0, -1.0) * f3.shares
f3["pay"] = np.where(f3.is_up, f3.up_payout, 1 - f3.up_payout); f3["pnl"] = f3.shares * (f3.pay - f3.price) - f3.fee_usd
Wn = f3.groupby("start_ts").agg(N=("sgs", "sum"), pnl=("pnl", "sum"), up=("up_payout", "first"))
menu = float(f.L.mean())


def esize(pl):
    a = np.array([EF[x][0] for x in sc.wallet]); b = np.array([EF[x][1] for x in sc.wallet])
    return (1 - pl) * a + pl * b


variants = {"menu": esize(np.full(len(sc), menu)), "class_oracle": esize(sc.L.to_numpy().astype(float))}
for v in models:
    variants[f"smach_own_{v}"] = esize(out_p[v]); variants[f"smach_own_argmax_{v}"] = esize(out_pmax[v]); variants[f"smach_true_state_{v}"] = esize(p_or[v])
lad = {}
for side in ("sh", "sg"):
    for nm, sz in variants.items():
        x = pd.Series(sc[side].to_numpy() * sz, index=sc.index).groupby(sc.start_ts).sum()
        J = Wn.join(x.rename("x"), how="inner").fillna(0); qq = J.x * (J.up - 0.5)
        lad[f"{side}|{nm}"] = {"rN": round(float(pearsonr(J.x, J.N)[0]), 4), "pnl_P": round(float(pearsonr(qq, J.pnl)[0]), 4),
                               "pnl_S": round(float(spearmanr(qq, J.pnl)[0]), 4), "n": int(len(J))}
        print(side, nm, lad[f"{side}|{nm}"], flush=True)
res["ladder"] = lad
res["S_own_agreement_with_operator_S"] = {v: round(float(np.mean(agree[v])), 4) for v in models}
res["auc_large_class"] = {}
for v in models:
    rr = {"pooled_own": round(float(auc(sc.L, out_p[v])), 4), "pooled_true_state": round(float(auc(sc.L, p_or[v])), 4)}
    for w in W3:
        mk = (sc.wallet == w).to_numpy()
        rr[f"{w}_own"] = round(float(auc(sc.L[mk], out_p[v][mk])), 4); rr[f"{w}_true_state"] = round(float(auc(sc.L[mk], p_or[v][mk])), 4)
    res["auc_large_class"][v] = rr
mn = lad["sh|menu"]["rN"]
res["claim_window_net_r_ge_menu_plus_0.05"] = {v: bool(lad[f"sh|smach_own_{v}"]["rN"] >= mn + 0.05) for v in models}
res["claim_S_agreement_ge_0.75"] = {v: bool(res["S_own_agreement_with_operator_S"][v] >= 0.75) for v in models}
print(json.dumps({k: res[k] for k in ("S_own_agreement_with_operator_S", "auc_large_class", "claim_window_net_r_ge_menu_plus_0.05", "step1_auc_Srel_true_side")}, indent=0), flush=True)
json.dump(res, open(f"research/reverse_engineering/btc5m-bot/results/smach17_{'_'.join(SCO)}.json", "w"), indent=1, default=str)
