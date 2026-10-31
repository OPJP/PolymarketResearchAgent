"""Decision-level match tests for quote-pulling hypotheses built only from public tape data.

Population: every taker order that hit resting BUY interest at the touch in RN1's sampled markets
(events_lat1.pkl). Label: RN1 was among the makers filled at the touch level.

H-A  own-market tape calm: score from PIT features of the market's own taker tape
     (seconds since last >=J move in 30 s, 30 s / 120 s range, print counts), fitted on FIT.
H-B  sibling-market lead-lag: seconds since a >=J jump in the two most-traded sibling markets of
     the same event (public tape), alone and added to H-A.

Score fitted (logistic regression) on FIT only; AUC measured on TEST. Null: within each TEST
market, rotate the label vector by a random offset (10-90 % of the market's events), which keeps
market-level label rates, feature distributions and autocorrelation and destroys only the timing
link. 2000 rotations; p = (1 + #null >= obs) / (1 + N).
"""
import json, sys
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from common import S
from grid_maker import jump_times, since

E = pd.read_pickle(S / "events_lat1.pkl").sort_values(["condition_id", "ts"]).reset_index(drop=True)
LAT = 1
sib_path = S / "sibling_taker.pkl"
has_sib = sib_path.exists()
if has_sib:
    sib = pd.read_pickle(sib_path)
    for J in (0.03, 0.05, 0.10):
        col = np.full(len(E), 1e7)
        for cid, idx in E.groupby("condition_id").groups.items():
            s = sib[sib.target == cid]
            jt = []
            for _, sg in s.groupby("sib"):
                sg = sg[sg.outcome >= 0].sort_values("ts")
                if len(sg) < 2:
                    continue
                sts = sg.ts.to_numpy().astype(np.int64)
                sp0 = np.where(sg.outcome.to_numpy() == 0, sg.price.to_numpy(), 1 - sg.price.to_numpy())
                jt.append(jump_times(sts, sp0, J, 30))
            jt = np.sort(np.concatenate(jt)) if jt else np.array([], dtype=np.int64)
            col[idx] = since(jt, E.loc[idx, "ts"].to_numpy().astype(np.int64) - LAT - 1)
        E[f"sib_sj{int(J*100)}"] = col
    E["has_sib"] = E.condition_id.isin(sib.target.unique())


def feats(df, which):
    X = {}
    if "A" in which:
        X["l_sj"] = np.log1p(np.minimum(df.since_jump, 1e4))
        X["rng30"] = df.rng30.fillna(0)
        X["rng120"] = df.rng120.fillna(0)
        X["l_n30"] = np.log1p(df.n30)
        X["l_n120"] = np.log1p(df.n120)
    if "B" in which:
        for J in (3, 5, 10):
            X[f"l_sib_sj{J}"] = np.log1p(np.minimum(df[f"sib_sj{J}"], 1e4))
    return pd.DataFrame(X)


def rot_null(y, score, groups, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    idx_by = [np.flatnonzero(groups == g) for g in np.unique(groups)]
    out = np.empty(n)
    for b in range(n):
        yy = y.copy()
        for ix in idx_by:
            m = len(ix)
            if m < 3:
                continue
            k = rng.integers(max(1, int(0.1 * m)), max(2, int(0.9 * m)))
            yy[ix] = np.roll(y[ix], k)
        out[b] = roc_auc_score(yy, score)
    return out


def run(name, which, mask=None):
    D = E if mask is None else E[mask]
    F, T = D[D.period == "fit"], D[D.period == "test"]
    Xf, Xt = feats(F, which), feats(T, which)
    mu, sd = Xf.mean(), Xf.std().replace(0, 1)
    clf = LogisticRegression(max_iter=2000).fit((Xf - mu) / sd, F.rn1_at_q)
    st = clf.decision_function((Xt - mu) / sd)
    y = T.rn1_at_q.to_numpy().astype(int)
    auc = roc_auc_score(y, st)
    null = rot_null(y, st, T.condition_id.to_numpy())
    p = (1 + (null >= auc).sum()) / (1 + len(null))
    # decision metrics at FIT-chosen threshold (top-quantile with FIT RN1 base rate * 1)
    sf = clf.decision_function((Xf - mu) / sd)
    thr = np.quantile(sf, 0.5)
    pred = st >= thr
    prec = y[pred].mean() if pred.any() else float("nan")
    rec = pred[y == 1].mean()
    res = {"n_fit": int(len(F)), "n_test": int(len(T)), "test_markets": int(T.condition_id.nunique()), "test_rn1_rate": float(y.mean()),
           "coef": dict(zip(Xf.columns, np.round(clf.coef_[0], 3).tolist())), "test_auc": float(auc),
           "null_mean": float(null.mean()), "null_p99": float(np.quantile(null, 0.99)), "perm_p": float(p),
           "precision_top_half": float(prec), "recall_top_half": float(rec), "lift_top_half": float(prec / y.mean())}
    print(name, json.dumps(res))
    return res

out = {"A_own_tape_calm": run("A", "A")}
# single-feature, sign fixed a priori (calm -> RN1 present): no fitting at all
T = E[E.period == "test"]; y = T.rn1_at_q.to_numpy().astype(int)
for col in ("since_jump", "rng30"):
    sc = np.log1p(np.minimum(T[col].fillna(0), 1e4)) * (1 if col == "since_jump" else -1)
    auc = roc_auc_score(y, sc); null = rot_null(y, sc.to_numpy(), T.condition_id.to_numpy(), n=2000, seed=1)
    out[f"A_single_{col}"] = {"test_auc": float(auc), "null_mean": float(null.mean()), "null_p99": float(np.quantile(null, 0.99)), "perm_p": float((1 + (null >= auc).sum()) / (1 + len(null)))}
    print(col, out[f"A_single_{col}"])
if has_sib:
    m = E.has_sib
    out["B_sibling_only"] = run("B", "B", m)
    out["AB_own_plus_sibling"] = run("AB", "AB", m)
    out["A_on_sibling_subset"] = run("A_sub", "A", m)
json.dump(out, open(S / "match_test.json", "w"), indent=1)
