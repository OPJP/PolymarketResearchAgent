"""Iteration 18 PIVOT (NOTES.md pre-registration 15, written before this runs): the operator's size-class DECISION MEMORY read from
the SIBLING wallets' public large prints (W4 / W5), a NEW DATA SOURCE for the size state. Mechanics panel iter17 P1 = X170 / X66 / X169.

Paradigm vs iteration 17: iter17 drove the state S from the replica's OWN drawn classes (agreement 0.55). Here the state is driven by
W4 / W5's public large taker prints, lagged, which the operator's shared decision memory leaks on chain. Everything else (the smach17
transition model, slot, E, dc14 side, the window-net / PnL proxy) is unchanged and frozen.

Sibling state (PIT): a W4 / W5 taker BUY leg filled >= 60 shares is a confirmed large print; usable at block_ts + 2 s (on-chain lag);
txs that also contain a cluster wallet (DS/GF/XM) are excluded (shared-tx rule). S_pub = side of the most recent public W4/W5 large
print in the window before the order; E_pub its accumulated large shares since the last flip.
States compared, per split: menu, class_oracle (ceiling), smach_own (iter17 reproduce), smach_sib (public W4/W5 only, deterministic),
smach_hyb (own draws whose S/E are overwritten by a more-recent public print), true_state (operator's own S/E, ceiling).
Measures: agreement of each state's S with the operator's TRUE S; AUC of P(large); window-net r(N) and PnL proxy Pearson/Spearman.
Usage: python -I sib18.py FITDAYS SCOREDAYS  (e.g. 10-20 10-21,10-22)."""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score as auc

S = os.environ["RE16_SCRATCH"]
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = ROOT + "/.cache/re/btc5m-bot"
FIT = sys.argv[1].split(","); SCO = sys.argv[2].split(",")
R = 200
W3 = ("DS", "GF", "XM")
W45 = {"0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}
rng = np.random.default_rng(18)

# ---- operator frame p (smach17 logic) ----
cols = ["tx", "role", "taker_amt", "oside"]
cds = [pd.read_parquet(C + "/calldata_sample.parquet", columns=cols), pd.read_parquet(S + r"/it15/cl_orders.parquet", columns=cols)]
for d in sorted(set(FIT + SCO)):
    fn = f"{S}/it16/cdfull_{d}.parquet"
    if os.path.exists(fn):
        cds.append(pd.read_parquet(fn, columns=cols))
cd = pd.concat(cds); cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["tx"] = cd.tx.str.lower(); cd = cd.drop_duplicates("tx")
mp = pd.concat([pd.read_parquet(f"{S}/it15/l2ord_2026-{d}.parquet", columns=["tx", "cid", "wallet", "m"]) for d in sorted(set(FIT + SCO))])
mp["tx"] = mp.tx.str.lower(); mp = mp.merge(cd[["tx", "taker_amt"]], on="tx", how="left").drop_duplicates(["cid", "wallet", "m"])
p = pd.read_parquet(S + r"/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "osz", "start_ts", "p_dc14_spot_own"])
p["dd"] = pd.to_datetime(p.start_ts, unit="s").dt.strftime("%m-%d")
p = p[p.dd.isin(FIT + SCO)].merge(mp[["cid", "wallet", "m", "taker_amt"]], on=["cid", "wallet", "m"], how="left")
p = p[p.taker_amt.notna()].copy(); p["orig"] = p.taker_amt
p["L"] = (p.orig >= 90).astype(int)
p["sg"] = np.where(p.up == 1, 1, -1); p["sh"] = np.where(p.p_dc14_spot_own > 0.5, 1, -1)
p = p.sort_values(["start_ts", "m"]).reset_index(drop=True)
q = p.sort_values(["cid", "up", "m"]); gap = q.m - q.groupby(["cid", "up"]).m.shift(); p.loc[q.index, "gap"] = gap
p["slot"] = np.where(p.gap < 150, 2, np.where(p.gap < 400, 1, 0))
p["tb"] = np.digitize(p.m / 1000.0 - p.start_ts, [30, 60, 120])
LSZ = float(p[p.dd.isin(FIT) & (p.L == 1)].orig.mean())
print("operator orders", len(p), p.groupby("dd").size().to_dict(), "LSZ", round(LSZ, 1), flush=True)

# ---- true operator S / E (smach17) ----
def true_state(g):
    mm = g.m.to_numpy(); L = g.L.to_numpy(); sg = g.sg.to_numpy(); oz = g.orig.to_numpy()
    Sv = np.zeros(len(g), int); Ev = np.zeros(len(g)); s_cur, e_cur = 0, 0.0; j = 0
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
    Sv, Ev = true_state(g); p.loc[g.index, "S"] = Sv; p.loc[g.index, "E"] = Ev

# ---- W4/W5 public large prints per window ----
fl = pd.read_parquet(C + "/fills.parquet", columns=["tx"]); clus_tx = set(fl.tx.str.lower())
need = p.cid.unique()
pub = {}  # start_ts -> sorted arrays (t_ms_usable, side_sign, size)
cid2st = p.drop_duplicates("cid").set_index("cid").start_ts.to_dict()
nfiles = 0; npr = 0
for cc in need:
    fn = f"{S}/it16/tapes/{cc}.parquet"
    if not os.path.exists(fn):
        continue
    nfiles += 1
    t = pd.read_parquet(fn, columns=["proxyWallet", "side", "size", "timestamp", "outcome", "transactionHash"])
    t = t[(t.side == "BUY") & (t["size"] >= 60)].copy()
    t["w"] = t.proxyWallet.str.lower()
    t = t[t.w.isin(W45)]
    if len(t):
        t = t[~t.transactionHash.str.lower().isin(clus_tx)]
    if not len(t):
        continue
    st = cid2st.get(cc)
    sgn = np.where(t.outcome.to_numpy() == "Up", 1, -1)
    tu = (t.timestamp.to_numpy().astype(np.int64) + 2) * 1000  # usable block ts + 2 s, in ms (compare with order m in ms)
    o = np.argsort(tu, kind="stable")
    pub[st] = (tu[o], sgn[o], t["size"].to_numpy()[o].astype(float)); npr += len(t)
print("tapes read", nfiles, "W4/W5 large prints", npr, flush=True)

# deterministic public state at each operator order: S_pub, E_pub, t_pub (ms)
Spub = np.zeros(len(p), int); Epub = np.zeros(len(p)); Tpub = np.full(len(p), -1, np.int64)
for st, g in p.groupby("start_ts", sort=False):
    arr = pub.get(st)
    if arr is None:
        continue
    tu, sgn, sz = arr
    # running state over the print stream
    runS = np.zeros(len(tu), int); runE = np.zeros(len(tu)); s_c, e_c = 0, 0.0
    for i in range(len(tu)):
        if sgn[i] != s_c:
            s_c, e_c = sgn[i], 0.0
        e_c += sz[i]; runS[i] = s_c; runE[i] = e_c
    m = g.m.to_numpy(np.int64); j = np.searchsorted(tu, m, "left") - 1  # last print strictly before m
    ok = j >= 0
    idx = g.index.to_numpy()
    Spub[idx[ok]] = runS[j[ok]]; Epub[idx[ok]] = runE[j[ok]]; Tpub[idx[ok]] = tu[j[ok]]
p["Spub"] = Spub; p["Epub"] = Epub; p["Tpub"] = Tpub
cov = float((p.dd.isin(SCO) & (p.Tpub >= 0)).mean() / max(p.dd.isin(SCO).mean(), 1e-9))
print("SCO orders with a prior public W4/W5 large print:", round(cov, 3), flush=True)

# ---- transition model (smach17), fit on TRUE state + TRUE side ----
def rel(side, Sx):
    return np.where(Sx == 0, 0, np.where(Sx == side, 1, 2))
def design(slot, rl, E, tb, wal):
    n = len(slot); X = np.zeros((n, 9 + 2 + 3 + 3))
    X[np.arange(n), slot * 3 + rl] = 1
    X[:, 9] = (rl == 1) * np.log1p(E); X[:, 10] = (rl == 2) * np.log1p(E)
    for b in (1, 2, 3):
        X[:, 10 + b] = tb == b
    for i, w in enumerate(W3):
        X[:, 14 + i] = wal == w
    return X
f = p[p.dd.isin(FIT)]
Xf = design(f.slot.to_numpy(), rel(f.sg.to_numpy(), f.S.to_numpy()), f.E.to_numpy(), f.tb.to_numpy(), f.wallet.to_numpy())
M = LogisticRegression(C=1.0, max_iter=2000).fit(Xf, f.L.to_numpy())
coef, b0 = M.coef_[0], M.intercept_[0]
def plogit(slot, rl, E, tb, wal):
    z = b0 + coef[slot * 3 + rl] + (rl == 1) * coef[9] * np.log1p(E) + (rl == 2) * coef[10] * np.log1p(E) + np.where(tb > 0, coef[np.clip(10 + tb, 11, 13)], 0.0)
    z = z + coef[np.array([14 + W3.index(w) for w in wal])]
    return 1 / (1 + np.exp(-z))

sc = p[p.dd.isin(SCO)].copy()
# per-wallet fill means for E[size]
fill = p[p.dd.isin(FIT)].groupby(["wallet", "L"]).osz.mean().unstack().to_dict("index")
EF = {w: (fill[w][0], fill[w][1]) for w in W3}
def esize(pl):
    a = np.array([EF[x][0] for x in sc.wallet]); b = np.array([EF[x][1] for x in sc.wallet]); return (1 - pl) * a + pl * b

# deterministic scorers: public-only and true-state and oracle-class
p_sib = plogit(sc.slot.to_numpy(), rel(sc.sh.to_numpy(), sc.Spub.to_numpy()), sc.Epub.to_numpy(), sc.tb.to_numpy(), sc.wallet.to_numpy())
p_true = plogit(sc.slot.to_numpy(), rel(sc.sh.to_numpy(), sc.S.to_numpy()), sc.E.to_numpy(), sc.tb.to_numpy(), sc.wallet.to_numpy())

# ---- replica with own memory (smach_own) and hybrid (smach_hyb) ----
pos = {ix: k for k, ix in enumerate(sc.index)}
out_own = np.zeros(len(sc)); out_hyb = np.zeros(len(sc))
agree_own = []; agree_hyb = []; agree_sib = []
for st, g in sc.groupby("start_ts", sort=False):
    n = len(g); sh = g.sh.to_numpy(); sl = g.slot.to_numpy(); tb = g.tb.to_numpy(); ww = g.wallet.to_numpy()
    mm = g.m.to_numpy(np.int64); St = g.S.to_numpy(); Sp = g.Spub.to_numpy(); Ep = g.Epub.to_numpy(); Tp = g.Tpub.to_numpy()
    ii = np.array([pos[i] for i in g.index])
    for mode in ("own", "hyb"):
        Sown = np.zeros(R, int); Eown = np.zeros(R); town = np.full(R, -1, np.int64)
        Lh = np.zeros((n, R), bool); applied = 0
        for k in range(n):
            while applied < k and mm[applied] < mm[k]:
                Ld = Lh[applied]; s_ = sh[applied]; flip = Ld & (Sown != s_)
                Sown = np.where(flip, s_, Sown); Eown = np.where(flip, 0.0, Eown); Eown = Eown + Ld * LSZ
                town = np.where(Ld, mm[applied], town); applied += 1
            if mode == "hyb" and Tp[k] >= 0:
                use_pub = Tp[k] > town  # public print more recent than own last large event
                Seff = np.where(use_pub, Sp[k], Sown); Eeff = np.where(use_pub, Ep[k], Eown)
            else:
                Seff, Eeff = Sown, Eown
            pk = plogit(np.full(R, sl[k]), rel(sh[k], Seff), Eeff, np.full(R, tb[k]), np.full(R, ww[k], object))
            Ld = rng.random(R) < pk; Lh[k] = Ld
            (out_own if mode == "own" else out_hyb)[ii[k]] = pk.mean()
            if St[k] != 0:
                (agree_own if mode == "own" else agree_hyb).append(float((Seff == St[k]).mean()))
    # sib agreement (deterministic)
    for k in range(n):
        if St[k] != 0:
            agree_sib.append(float(Sp[k] == St[k]))

# ---- PnL proxy ----
f3 = pd.read_parquet(C + "/fills.parquet", columns=["wallet", "is_up", "shares", "price", "fee_usd", "start_ts", "up_payout"])
f3 = f3[f3.start_ts.isin(sc.start_ts.unique())].copy()
f3["pay"] = np.where(f3.is_up, f3.up_payout, 1 - f3.up_payout); f3["pnl"] = f3.shares * (f3.pay - f3.price) - f3.fee_usd
Wn = f3.groupby("start_ts").agg(N=("shares", "sum"), pnl=("pnl", "sum"), up=("up_payout", "first"))
menu = float(f.L.mean())
variants = {"menu": esize(np.full(len(sc), menu)), "class_oracle": esize(sc.L.to_numpy().astype(float)),
            "smach_own": esize(out_own), "smach_sib": esize(p_sib), "smach_hyb": esize(out_hyb), "smach_true_state": esize(p_true)}
res = {"fit": FIT, "score": SCO, "R": R, "LSZ": round(LSZ, 1), "menu_rate": round(menu, 4),
       "pub_coverage_sco": round(cov, 3), "n_pub_prints": npr,
       "agreement_with_true_S": {"smach_own": round(float(np.mean(agree_own)), 4), "smach_sib": round(float(np.mean(agree_sib)), 4),
                                 "smach_hyb": round(float(np.mean(agree_hyb)), 4)},
       "auc_large": {"own": round(float(auc(sc.L, out_own)), 4), "sib": round(float(auc(sc.L, p_sib)), 4),
                     "hyb": round(float(auc(sc.L, out_hyb)), 4), "true_state": round(float(auc(sc.L, p_true)), 4)}}
for w in W3:
    mk = (sc.wallet == w).to_numpy()
    if sc.L[mk].nunique() == 2:
        res["auc_large"][f"{w}_hyb"] = round(float(auc(sc.L[mk], out_hyb[mk])), 4)
        res["auc_large"][f"{w}_own"] = round(float(auc(sc.L[mk], out_own[mk])), 4)
lad = {}
for nm, sz in variants.items():
    x = pd.Series(sc.sh.to_numpy() * sz, index=sc.index).groupby(sc.start_ts).sum()
    J = Wn.join(x.rename("x"), how="inner").fillna(0); qq = J.x * (J.up - 0.5)
    lad[nm] = {"rN": round(float(pearsonr(J.x, J.N)[0]), 4), "pnl_P": round(float(pearsonr(qq, J.pnl)[0]), 4),
               "pnl_S": round(float(spearmanr(qq, J.pnl)[0]), 4), "n": int(len(J))}
res["pnl_proxy"] = lad
print(json.dumps({k: res[k] for k in ("agreement_with_true_S", "auc_large", "pnl_proxy", "pub_coverage_sco")}, indent=1), flush=True)
json.dump(res, open(f"research/reverse_engineering/btc5m-bot/results/sib18_{'_'.join(SCO)}.json", "w"), indent=1, default=str)
