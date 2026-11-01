"""Iteration 12: panel iter11 assumptions P1 step 1 (X109) and mechanics P3 step 1 (X106) on the iteration-11 onset tables
(clean Binance USD-M onsets, 10-31 A = 14:55-16:04 and C = 16:33-17:55; decisions = it11/large_dec.parquet, 2,155 operator
decisions at the arrival clock a).
(1) Fixed-effect scan: linear probability model of the take label y on log(1 + rec30) (operator decisions on the window in
    [tau - 30 s, tau)), log|bp| and the event class, with segment fixed effects of length L = 300 / 120 / 60 / 30 s; a REDRAW
    null (200 draws): each onset's time is redrawn uniformly inside its (window, L-segment), the clean filter (no operator
    decision on the window in [tau - 600, tau + 150) ms) is enforced, rec30 and the label (a decision on o in [tau + 150,
    tau + 700) ms) are recomputed from the actual decisions; the event's own features stay.
(2) Where the state lives: per wallet w, y_w = w decides on o in [tau + 150, tau + 700) on rec_own (w's decisions on the
    window in the last 30 s) and rec_other (the other wallets'), with 120-s segment FE; beta_own vs beta_other.
Own state is a mechanism measurement here, never a rule feature."""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
rng = np.random.default_rng(12)
D = pd.read_parquet(f"{C}/it11/large_dec.parquet")
D["a"] = D.a.astype(float)
DEC = {}
for (st, w), g in D.groupby(["st", "w"]):
    DEC[(int(st), w)] = (np.sort(g.a.to_numpy()), g.sort_values("a").up.to_numpy(bool))
ALL = {int(st): (g.sort_values("a").a.to_numpy(float), g.sort_values("a").up.to_numpy(bool), g.sort_values("a").w.to_numpy()) for st, g in D.groupby("st")}
WAL = sorted(D.w.unique())


def counts(st, tau, o):
    """rec30 (all operator decisions on the window in [tau - 30 s, tau)), clean flag, label y (decision on o in [tau+150, tau+700))."""
    a, up, w = ALL.get(int(st), (np.zeros(0), np.zeros(0, bool), np.zeros(0)))
    i0, i1 = np.searchsorted(a, tau - 30000), np.searchsorted(a, tau)
    rec = i1 - i0
    c0, c1 = np.searchsorted(a, tau - 600), np.searchsorted(a, tau + 150)
    clean = (c1 - c0) == 0
    j0, j1 = np.searchsorted(a, tau + 150), np.searchsorted(a, tau + 700)
    y = bool(np.any(up[j0:j1] == o)) if j1 > j0 else False
    return rec, clean, y


def lpm_fe(y, x, seg):
    """within-segment demeaned OLS slope of y on the columns of x (first column reported)."""
    df = pd.DataFrame(x); df["y"] = y; df["seg"] = seg
    g = df.groupby("seg")
    dm = df.drop(columns="seg") - g.transform("mean")
    X = dm.drop(columns="y").to_numpy(float); Y = dm.y.to_numpy(float)
    b, *_ = np.linalg.lstsq(X, Y, rcond=None)
    return b


def main():
    res = {}
    for nm in ("A", "C"):
        e = pd.read_parquet(f"{C}/it11/onset_{nm}.parquet")
        e = e[e.clean.astype(bool) & e.st.isin(list(ALL))].reset_index(drop=True)
        o = (e.sgn > 0).to_numpy()
        tau = e.tau.to_numpy(float); st = e.st.to_numpy(np.int64)
        base = np.c_[np.log(np.abs(e.bp.to_numpy(float)) + 1e-3), (e.cls == "PRICE").to_numpy(float), (e.cls == "DEPLETE").to_numpy(float)]
        rec = np.zeros(len(e)); yy = np.zeros(len(e)); cl = np.zeros(len(e), bool)
        for i in range(len(e)):
            rec[i], cl[i], yy[i] = counts(st[i], tau[i], o[i])
        out = {"n": int(len(e)), "label_agreement_with_table": round(float((yy == e.y.to_numpy()).mean()), 4), "clean_recomputed": round(float(cl.mean()), 4)}
        y = e.y.to_numpy(float)
        relms = tau - st * 1000.0
        for L in (300, 120, 60, 30):
            seg = st * 1000 + (relms // (L * 1000))
            b_obs = lpm_fe(y, np.c_[np.log1p(rec), base], seg)[0]
            r = {"coef_obs": round(float(b_obs), 4)}
            if L in (120, 60):
                null = []
                for _ in range(200):
                    lo = (relms // (L * 1000)) * L * 1000
                    t2 = st * 1000.0 + lo + rng.random(len(e)) * L * 1000
                    rr = np.zeros(len(e)); y2 = np.zeros(len(e)); c2 = np.zeros(len(e), bool)
                    for i in range(len(e)):
                        rr[i], c2[i], y2[i] = counts(st[i], t2[i], o[i])
                    m = c2
                    if m.sum() > 100:
                        null.append(lpm_fe(y2[m], np.c_[np.log1p(rr[m]), base[m]], seg[m])[0])
                null = np.array(null)
                r.update({"null_mean": round(float(null.mean()), 4), "null_sd": round(float(null.std()), 4), "null_q025": round(float(np.quantile(null, 0.025)), 4),
                          "null_q975": round(float(np.quantile(null, 0.975)), 4), "p_two_sided": round(float(min(1.0, 2 * min((null >= b_obs).mean(), (null <= b_obs).mean()))), 4), "draws": int(len(null))})
            out[f"L{L}"] = r
        # (2) per-wallet own vs other recent decisions, 120-s segment FE
        seg = st * 1000 + (relms // 120000)
        pw = {}
        for w in WAL:
            yw = np.zeros(len(e)); ro = np.zeros(len(e)); rx = np.zeros(len(e))
            for i in range(len(e)):
                a, up = DEC.get((int(st[i]), w), (np.zeros(0), np.zeros(0, bool)))
                j0, j1 = np.searchsorted(a, tau[i] + 150), np.searchsorted(a, tau[i] + 700)
                yw[i] = float(np.any(up[j0:j1] == o[i])) if j1 > j0 else 0.0
                ro[i] = np.searchsorted(a, tau[i]) - np.searchsorted(a, tau[i] - 30000)
            rx = rec - ro
            b = lpm_fe(yw, np.c_[np.log1p(ro), np.log1p(rx), base], seg)
            b0 = lpm_fe(yw, np.c_[np.log1p(ro), np.log1p(rx), base], st)
            pw[w] = {"take_rate": round(float(yw.mean()), 4), "beta_own_120s_fe": round(float(b[0]), 4), "beta_other_120s_fe": round(float(b[1]), 4),
                     "beta_own_window_fe": round(float(b0[0]), 4), "beta_other_window_fe": round(float(b0[1]), 4)}
        out["per_wallet_own_vs_other"] = pw
        res[nm] = out
        print(nm, json.dumps(out), flush=True)
    json.dump(res, open(f"{R}/regime12.json", "w"), indent=1)


if __name__ == "__main__":
    main()
