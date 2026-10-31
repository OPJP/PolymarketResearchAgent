"""Iteration 9, selectivity follow-up of flag9 (the bot skips ~3 of 4 flagged instants and decides more at cheap asks): is the
decision gated by a FEE-AWARE, DELTA-SCALED edge of the tick? At grid point t for outcome o:
  move = mean BTC microprice move toward o over [t - 600, t - 100) ms (bf, bs, ok, by; bp) - the vote window;
  gain = 100 * Delta_o * move   [cents], Delta_o = phi(Phi^-1(mid_o)) / (sigma sqrt(tau)), sigma = 0.67 bp / sqrt(s);
  cost = 100 * ((ask_o - mid_o) + 0.035 * ask_o * (1 - ask_o))   [the half spread + the taker fee net of the 50% rebate];
  V = gain - cost.
Hazard by V; FULL vs FULL + V (fit on A, scored on C, decision label = matches + lost-race insertions); and inside the top 3%
of the FULL score, does V separate the instants the cluster takes from those it skips?
Usage: python fee9.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import norm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9
from lag7 import mv
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C


def frame(gd, S):
    t = gd["t"]
    acc = np.zeros(len(t)); n = np.zeros(len(t))
    for key in stale9.BTCK:
        if key in S:
            r = mv(S, key, t - 600, t - 100); acc += np.nan_to_num(r); n += np.isfinite(r)
    move = np.where(n > 0, acc / np.maximum(n, 1), np.nan)
    rows = []
    for o, sg in ((True, 1.0), (False, -1.0)):
        D = gd[o]
        keep = gd["oka"] & np.isfinite(D["ask"]) & np.isfinite(D["ask5"]) & (D["ask"] > 0.03) & (D["ask"] < 0.97) & np.isfinite(D["mid"]) & np.isfinite(move)
        mid = np.clip(D["mid"], 0.01, 0.99)
        delta = norm.pdf(norm.ppf(mid)) / (stale9.SIG * np.sqrt(gd["tau"]))
        gain = 100 * delta * sg * move
        cost = 100 * ((D["ask"] - mid) + 0.035 * D["ask"] * (1 - D["ask"]))
        rows.append(pd.DataFrame({"y_match": D["y_match"][keep], "y_dec": D["y_dec"][keep], "tick": sg * gd["tick"][keep],
                                  "rp": np.sign(np.round((D["ask"][keep] - D["ask5"][keep]) * 100)), "age": D["age"][keep], "act": gd["act"][keep],
                                  "ask": D["ask"][keep], "E": 0.0, "V": (gain - cost)[keep], "gain": gain[keep], "cost": cost[keep],
                                  "st": gd["st"][keep], "t": t[keep], "o": o}))
    return pd.concat(rows, ignore_index=True)


def Xv(df):
    V = np.clip(df.V.to_numpy(float), -20, 20)
    return np.c_[V, np.clip(V, 0, None), V > 0, V > 1, V > 3, np.clip(df.gain.to_numpy(float), -20, 20), df.cost.to_numpy(float)]


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    F = {}
    for nm in ("A", "C"):
        gd, tk, S = stale9.grid(*stale9.IV[nm], lost)
        F[nm] = frame(gd, S)
        print(nm, len(F[nm]), flush=True)
    res = {}
    for nm, df in F.items():
        res.setdefault("univariate_auc_V", {})[nm] = {"y_dec": round(float(roc_auc_score(df.y_dec, df.V)), 4),
                                                      "y_match": round(float(roc_auc_score(df.y_match, df.V)), 4),
                                                      "gain_only_y_dec": round(float(roc_auc_score(df.y_dec, df.gain)), 4)}
        bins = pd.cut(df.V, [-100, -5, -2, -1, 0, 1, 2, 5, 10, 100])
        tab = df.groupby(bins, observed=False).agg(p=("y_dec", "mean"), n=("y_dec", "size"))
        res.setdefault("hazard_by_V_cents_ydec", {})[nm] = {str(i): [round(float(r.p), 4), int(r.n)] for i, r in tab.iterrows()}
    A, Cc = F["A"], F["C"]
    XA_full, XC_full = stale9.X_of(A, "full"), stale9.X_of(Cc, "full")
    XA2, XC2 = np.c_[XA_full, Xv(A)], np.c_[XC_full, Xv(Cc)]
    P = {}
    for nm, (xa, xc) in (("full", (XA_full, XC_full)), ("full+V", (XA2, XC2)), ("base+V", (np.c_[stale9.X_of(A, "base"), Xv(A)], np.c_[stale9.X_of(Cc, "base"), Xv(Cc)])),
                         ("base", (stale9.X_of(A, "base"), stale9.X_of(Cc, "base")))):
        mu, sd = xa.mean(0), xa.std(0) + 1e-9
        lr = LogisticRegression(max_iter=3000).fit((xa - mu) / sd, A.y_dec)
        P[nm] = lr.predict_proba((xc - mu) / sd)[:, 1]
    y = Cc.y_dec.to_numpy()
    res["models_fit_A_on_C_ydec"] = {k: round(float(roc_auc_score(y, v)), 4) for k, v in P.items()}
    res["gain_fullV_vs_full_CI"] = stale9.boot_gain(y, P["full+V"], P["full"], Cc.st.to_numpy())
    res["gain_baseV_vs_base_CI"] = stale9.boot_gain(y, P["base+V"], P["base"], Cc.st.to_numpy())
    q97 = np.quantile(P["full"], 0.97)
    k = P["full"] >= q97
    res["top3pct_full"] = {"n": int(k.sum()), "P(decision)": round(float(y[k].mean()), 4),
                           "auc_V_taken_vs_skipped": round(float(roc_auc_score(y[k], Cc.V.to_numpy()[k])), 4),
                           "auc_cost_taken_vs_skipped(neg=cheaper)": round(float(roc_auc_score(y[k], -Cc.cost.to_numpy()[k])), 4),
                           "auc_gain_taken_vs_skipped": round(float(roc_auc_score(y[k], Cc.gain.to_numpy()[k])), 4),
                           "auc_act_taken_vs_skipped": round(float(roc_auc_score(y[k], Cc.act.to_numpy()[k])), 4),
                           "P(decision) by V": {}}
    for lo, hi in ((-100, 0), (0, 2), (2, 5), (5, 10), (10, 100)):
        kk = k & (Cc.V.to_numpy() >= lo) & (Cc.V.to_numpy() < hi)
        res["top3pct_full"]["P(decision) by V"][f"{lo}..{hi}"] = [round(float(y[kk].mean()), 4) if kk.any() else None, int(kk.sum())]
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x)))


if __name__ == "__main__":
    main(sys.argv[1])
