"""Iteration 9 (X72): how predictable is the SELECTION among flagged instants? Lab feeds, decision label. FULL hazard fit on all
of A; flagged = top 3% of its score (threshold from A, applied to A and C). On A's flagged instants, a logistic of taken vs
skipped from public features (fee-aware edge V at k = 1 and 8, gain, cost, tick, other trades, rel, |ask - 0.5|, ask change,
touch age) and, separately, + own state (the operator's unpaired shares of the other outcome and the pair cost; own state,
reported only); scored on C's flagged instants (never refit).
Usage: python select9.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9, fee9
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C
EX = {"0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"}


def own_state(df, a, b):
    f = pd.read_parquet(C + "/it9/own_1231_12_18.parquet")
    f = f[(f.ts >= a - 400) & (f.ts < b + 60)].copy()
    tok = {}; txms = {}
    for r in L.recs("btc5m_clob_raw2", a - 600, b + 60):
        k = r.get("k")
        if k == "S":
            tok[str(r["u"])] = (int(r["m"]), True); tok[str(r["d"])] = (int(r["m"]), False)
        elif k == "x" and r.get("h"):
            h = r["h"].lower(); txms[h] = min(txms.get(h, 10 ** 18), int(r["s"]))
    f["token"] = f.token.astype(str)
    f["st"] = f.token.map(lambda t: tok.get(t, (np.nan, None))[0]); f["up"] = f.token.map(lambda t: tok.get(t, (np.nan, None))[1])
    f["ms"] = f.tx.str.lower().map(txms); f = f[f.st.notna() & f.ms.notna()].copy()
    f["sh"] = f.tamt / 1e6; f["usd"] = f.mamt / 1e6
    hold = {}
    for (s0, u), g in f.groupby(["st", "up"]):
        g = g.sort_values("ms"); hold[(int(s0), bool(u))] = (g.ms.to_numpy(np.int64), np.cumsum(g.sh.to_numpy()), np.cumsum(g.usd.to_numpy()))
    t = df.t.to_numpy(np.int64); st = df.st.to_numpy(np.int64); o = df.o.to_numpy(bool); ask = df.ask.to_numpy(float)
    Ho = np.zeros(len(t)); Hx = np.zeros(len(t)); Cx = np.full(len(t), np.nan)
    for i in range(len(t)):
        for own, nm in ((o[i], "o"), (not o[i], "x")):
            h = hold.get((int(st[i]), bool(own)))
            if h is None:
                continue
            j = np.searchsorted(h[0], t[i] - 300, "left") - 1
            if j < 0:
                continue
            if nm == "o":
                Ho[i] = h[1][j]
            else:
                Hx[i] = h[1][j]; Cx[i] = h[2][j] / h[1][j]
    unp = np.maximum(Hx - Ho, 0); pair = np.nan_to_num(ask + Cx, nan=1.1)
    return unp, pair


def feats(d, k8):
    V1 = d.gain.to_numpy() - d.cost.to_numpy(); V8 = 8 * d.gain.to_numpy() - d.cost.to_numpy()
    la = np.log1p(np.nan_to_num(d.age.to_numpy(float), nan=1e5) / 100)
    return np.c_[np.clip(V1, -10, 10), V1 > 0, np.clip(V8, -20, 20), V8 > 0, np.clip(d.gain, -10, 10), d.cost, np.tanh(d.tick), np.log1p(d.act),
                 d.rel_, np.abs(d.ask - 0.5), d.rp, la].astype(float)


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    F = {}
    for nm in ("A", "C"):
        gd, tk, S = stale9.grid(*stale9.IV[nm], lost)
        df = fee9.frame(gd, S)
        df["rel_"] = (df.t / 1000 - df.st) / 300
        F[nm] = df
    A, Cc = F["A"], F["C"]
    XA, XC = stale9.X_of(A, "full"), stale9.X_of(Cc, "full")
    mu, sd = XA.mean(0), XA.std(0) + 1e-9
    lr = LogisticRegression(max_iter=3000).fit((XA - mu) / sd, A.y_dec)
    pA = lr.predict_proba((XA - mu) / sd)[:, 1]; pC = lr.predict_proba((XC - mu) / sd)[:, 1]
    thr = np.quantile(pA, 0.97)
    kA = pA >= thr; kC = pC >= thr
    a0, a1 = stale9.IV["A"]; c0, c1 = stale9.IV["C"]
    uA, prA = own_state(A, a0, a1); uC, prC = own_state(Cc, c0, c1)
    fA, fC = feats(A, 8)[kA], feats(Cc, 8)[kC]
    yA, yC = A.y_dec.to_numpy()[kA], Cc.y_dec.to_numpy()[kC]
    res = {"flagged_A": int(kA.sum()), "flagged_C": int(kC.sum()), "P(dec|flagged) A / C": [round(float(yA.mean()), 4), round(float(yC.mean()), 4)]}
    for nm, (xa, xc) in (("public", (fA, fC)), ("public+own_set_state", (np.c_[fA, np.tanh(uA[kA] / 100), np.clip(prA[kA], 0.8, 1.2)], np.c_[fC, np.tanh(uC[kC] / 100), np.clip(prC[kC], 0.8, 1.2)])),
                         ("own_set_state_only", (np.c_[np.tanh(uA[kA] / 100), np.clip(prA[kA], 0.8, 1.2)], np.c_[np.tanh(uC[kC] / 100), np.clip(prC[kC], 0.8, 1.2)]))):
        m2, s2 = xa.mean(0), xa.std(0) + 1e-9
        p = LogisticRegression(max_iter=3000, C=0.5).fit((xa - m2) / s2, yA).predict_proba((xc - m2) / s2)[:, 1]
        res[f"auc_C_{nm}"] = round(float(roc_auc_score(yC, p)), 4)
    # the FULL score itself within the flagged set (how much of the selection the hazard already ranks)
    res["auc_C_full_score_within_flagged"] = round(float(roc_auc_score(yC, pC[kC])), 4)
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
