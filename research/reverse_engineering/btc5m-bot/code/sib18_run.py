"""Iteration 18 run (vectorized): fit the frozen smach17 transition model on FIT (true state+side), score the size state on SCO under
states menu / class_oracle / smach_own / smach_sib / smach_hyb / smach_true_state. See pre-registration 15 in NOTES.md.
Usage: python -I sib18_run.py FITDAYS SCOREDAYS"""
import os, sys, json, time
import numpy as np, pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score as auc

S = os.environ["RE16_SCRATCH"]
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = ROOT + "/.cache/re/btc5m-bot"
FIT = sys.argv[1].split(","); SCO = sys.argv[2].split(",")
R = 150; W3 = ("DS", "GF", "XM"); rng = np.random.default_rng(18); t0 = time.time()
p = pd.read_parquet(S + r"/it18/sib_frame.parquet")
LSZ = float(p[p.dd.isin(FIT) & (p.L == 1)].orig.mean())

def rel(side, Sx):
    return np.where(Sx == 0, 0, np.where(Sx == side, 1, 2))
def design(slot, rl, E, tb, wal):
    n = len(slot); X = np.zeros((n, 17))
    X[np.arange(n), slot * 3 + rl] = 1
    X[:, 9] = (rl == 1) * np.log1p(E); X[:, 10] = (rl == 2) * np.log1p(E)
    for b in (1, 2, 3):
        X[:, 10 + b] = tb == b
    for i, w in enumerate(W3):
        X[:, 14 + i] = wal == w
    return X
f = p[p.dd.isin(FIT)]
M = LogisticRegression(C=1.0, max_iter=2000).fit(
    design(f.slot.to_numpy(), rel(f.sg.to_numpy(), f.S.to_numpy()), f.E.to_numpy(), f.tb.to_numpy(), f.wallet.to_numpy()), f.L.to_numpy())
coef, b0 = M.coef_[0], M.intercept_[0]
c9, c10 = coef[9], coef[10]

def plogit_vec(slot, rl, E, tb, wal_term):  # slot scalar, rl/E arrays, tb scalar, wal_term scalar
    z = b0 + wal_term + coef[slot * 3 + rl] + (rl == 1) * c9 * np.log1p(E) + (rl == 2) * c10 * np.log1p(E)
    z = z + (coef[10 + tb] if tb > 0 else 0.0)
    return 1.0 / (1.0 + np.exp(-z))
def plogit_arr(slot, rl, E, tb, wal):  # all arrays (deterministic scorers)
    z = b0 + coef[slot * 3 + rl] + (rl == 1) * c9 * np.log1p(E) + (rl == 2) * c10 * np.log1p(E)
    z = z + np.where(tb > 0, coef[np.clip(10 + tb, 11, 13)], 0.0)
    z = z + coef[np.array([14 + W3.index(w) for w in wal])]
    return 1.0 / (1.0 + np.exp(-z))

sc = p[p.dd.isin(SCO)].copy().reset_index(drop=True)
WT = {w: coef[14 + i] for i, w in enumerate(W3)}
p_sib = plogit_arr(sc.slot.to_numpy(), rel(sc.sh.to_numpy(), sc.Spub.to_numpy()), sc.Epub.to_numpy(), sc.tb.to_numpy(), sc.wallet.to_numpy())
p_true = plogit_arr(sc.slot.to_numpy(), rel(sc.sh.to_numpy(), sc.S.to_numpy()), sc.E.to_numpy(), sc.tb.to_numpy(), sc.wallet.to_numpy())

out_own = np.zeros(len(sc)); out_hyb = np.zeros(len(sc)); agree_own = []; agree_hyb = []; agree_sib = []
for st, g in sc.groupby("start_ts", sort=False):
    n = len(g); sh = g.sh.to_numpy(); sl = g.slot.to_numpy(); tb = g.tb.to_numpy()
    wt = g.wallet.map(WT).to_numpy(float); mm = g.m.to_numpy(np.int64)
    St = g.S.to_numpy(); Sp = g.Spub.to_numpy(); Ep = g.Epub.to_numpy(); Tp = g.Tpub.to_numpy()
    ii = g.index.to_numpy()
    for mode in ("own", "hyb"):
        Sown = np.zeros(R, int); Eown = np.zeros(R); town = np.full(R, -1, np.int64)
        Lh = np.zeros((n, R), bool); applied = 0
        for k in range(n):
            while applied < k and mm[applied] < mm[k]:
                Ld = Lh[applied]; s_ = sh[applied]; flip = Ld & (Sown != s_)
                Sown = np.where(flip, s_, Sown); Eown = np.where(flip, 0.0, Eown); Eown += Ld * LSZ
                town = np.where(Ld, mm[applied], town); applied += 1
            if mode == "hyb" and Tp[k] >= 0:
                up = Tp[k] > town; Seff = np.where(up, Sp[k], Sown); Eeff = np.where(up, Ep[k], Eown)
            else:
                Seff, Eeff = Sown, Eown
            pk = plogit_vec(sl[k], rel(sh[k], Seff), Eeff, tb[k], wt[k])
            Ld = rng.random(R) < pk; Lh[k] = Ld
            (out_own if mode == "own" else out_hyb)[ii[k]] = pk.mean()
            if St[k] != 0:
                (agree_own if mode == "own" else agree_hyb).append(float((Seff == St[k]).mean()))
    for k in range(n):
        if St[k] != 0:
            agree_sib.append(float(Sp[k] == St[k]))
print("replica done t", round(time.time() - t0, 1), flush=True)

fill = p[p.dd.isin(FIT)].groupby(["wallet", "L"]).osz.mean().unstack().to_dict("index")
EF = {w: (fill[w][0], fill[w][1]) for w in W3}
def esize(pl):
    a = sc.wallet.map(lambda x: EF[x][0]).to_numpy(); b = sc.wallet.map(lambda x: EF[x][1]).to_numpy(); return (1 - pl) * a + pl * b
f3 = pd.read_parquet(C + "/fills.parquet", columns=["wallet", "is_up", "shares", "price", "fee_usd", "start_ts", "up_payout"])
f3 = f3[f3.start_ts.isin(sc.start_ts.unique())].copy()
f3["sgs"] = np.where(f3.is_up, 1.0, -1.0) * f3.shares  # signed net shares (smach17 convention)
f3["pay"] = np.where(f3.is_up, f3.up_payout, 1 - f3.up_payout); f3["pnl"] = f3.shares * (f3.pay - f3.price) - f3.fee_usd
Wn = f3.groupby("start_ts").agg(N=("sgs", "sum"), pnl=("pnl", "sum"), up=("up_payout", "first"))
menu = float(f.L.mean())
variants = {"menu": esize(np.full(len(sc), menu)), "class_oracle": esize(sc.L.to_numpy().astype(float)),
            "smach_own": esize(out_own), "smach_sib": esize(p_sib), "smach_hyb": esize(out_hyb), "smach_true_state": esize(p_true)}
res = {"fit": FIT, "score": SCO, "R": R, "LSZ": round(LSZ, 1), "menu_rate": round(menu, 4),
       "pub_coverage_sco": round(float((sc.Tpub >= 0).mean()), 3),
       "agreement_with_true_S": {"smach_own": round(float(np.mean(agree_own)), 4), "smach_sib": round(float(np.mean(agree_sib)), 4),
                                 "smach_hyb": round(float(np.mean(agree_hyb)), 4), "n_states": len(agree_own)},
       "auc_large": {"own": round(float(auc(sc.L, out_own)), 4), "sib": round(float(auc(sc.L, p_sib)), 4),
                     "hyb": round(float(auc(sc.L, out_hyb)), 4), "true_state": round(float(auc(sc.L, p_true)), 4)}}
for w in W3:
    mk = (sc.wallet == w).to_numpy()
    if sc.L[mk].nunique() == 2:
        for nm, arr in (("hyb", out_hyb), ("own", out_own), ("sib", p_sib), ("true_state", p_true)):
            res["auc_large"][f"{w}_{nm}"] = round(float(auc(sc.L[mk], arr[mk])), 4)
lad = {}; WX = {}
for nm, sz in variants.items():
    x = pd.Series(sc.sh.to_numpy() * sz, index=sc.index).groupby(sc.start_ts).sum()
    J = Wn.join(x.rename("x"), how="inner").fillna(0); qq = J.x * (J.up - 0.5)
    lad[nm] = {"rN": round(float(pearsonr(J.x, J.N)[0]), 4), "pnl_P": round(float(pearsonr(qq, J.pnl)[0]), 4),
               "pnl_S": round(float(spearmanr(qq, J.pnl)[0]), 4), "n": int(len(J))}
    WX[nm] = J.assign(qq=qq)  # per-window frame aligned on the same index
res["pnl_proxy"] = lad
# paired 2-h block bootstrap of the gain (variant - menu) on the PnL-proxy Spearman and signed-net rN
base = WX["menu"]; blk = (base.index.to_numpy() // 7200); ub = np.unique(blk); idxby = {b: np.where(blk == b)[0] for b in ub}
rngb = np.random.default_rng(18); boot = {}
for nm in ("smach_sib", "smach_hyb", "smach_own", "smach_true_state"):
    Jv = WX[nm]; gS = []; gN = []
    for _ in range(400):
        take = np.concatenate([idxby[b] for b in rngb.choice(ub, len(ub))])
        a = Jv.iloc[take]; m = base.iloc[take]
        gS.append(spearmanr(a.qq, a.pnl)[0] - spearmanr(m.qq, m.pnl)[0])
        gN.append(pearsonr(a.x, a.N)[0] - pearsonr(m.x, m.N)[0])
    boot[nm] = {"pnlS_gain_vs_menu": round(float(np.mean(gS)), 4), "pnlS_CI": [round(float(np.percentile(gS, 2.5)), 4), round(float(np.percentile(gS, 97.5)), 4)],
                "rN_gain_vs_menu": round(float(np.mean(gN)), 4), "rN_CI": [round(float(np.percentile(gN, 2.5)), 4), round(float(np.percentile(gN, 97.5)), 4)]}
res["gain_vs_menu_block_boot"] = boot
res["claims"] = {"S_agree_ge_0.75_hyb": bool(res["agreement_with_true_S"]["smach_hyb"] >= 0.75),
                 "rN_ge_menu+0.05_hyb": bool(lad["smach_hyb"]["rN"] >= lad["menu"]["rN"] + 0.05),
                 "rN_ge_menu+0.05_sib": bool(lad["smach_sib"]["rN"] >= lad["menu"]["rN"] + 0.05)}
print(json.dumps({k: res[k] for k in ("agreement_with_true_S", "auc_large", "pnl_proxy", "claims", "pub_coverage_sco")}, indent=1), flush=True)
json.dump(res, open(f"research/reverse_engineering/btc5m-bot/results/sib18_{'_'.join(SCO)}.json", "w"), indent=1, default=str)
