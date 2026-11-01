"""Iteration 12 (panel iter11 assumptions P2 step 4 / E2 vs E4): structural regressions of the cluster's net bought per
window-minute on the BTC path (Binance 1-s closes, minute moves w0..w4 inside the window, pre-open M1 = [open-300,
open-60), M2 = [open-60, open)), the previous window's outcome (published priceToBeat pair) and the exact-strike
distance at the minute's start, separately on BUILD and VALIDATE (OLS, HC1 t-values). Also: does a fair value with a
different strike explain the opening lean? For each FV variant the minute-0 net is regressed on the variant's FV minus
the priceToBeat digital at the window open."""
import os, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
import statsmodels.api as sm
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
VAL0, H = 1792108800, 1792713600

b = pd.read_parquet(f"{C}/binance_1s.parquet")
s0 = int(b.sec.min()); px = b.set_index("sec").close.reindex(np.arange(s0, int(b.sec.max()) + 1)).ffill().to_numpy(float)
lp = np.log(px)
L = lambda t: lp[np.clip(np.asarray(t, np.int64) - s0, 0, len(lp) - 1)]
win = pd.read_parquet(f"{C}/windows.parquet")
win = win[win.up_payout.notna()].sort_values("start_ts").reset_index(drop=True)
pt = pd.read_parquet(f"{C}/ptb.parquet").set_index("start").priceToBeat.astype(float)
fl = pd.read_parquet(f"{C}/fills.parquet", columns=["wallet", "shares", "cid", "rel", "is_up"])
fl["sg"] = np.where(fl.is_up, 1.0, -1.0) * fl.shares
fl = fl[(fl.rel >= 0) & (fl.rel < 300)]
fl["m"] = (fl.rel // 60).astype(int)
nm = fl.groupby(["cid", "m"]).sg.sum().unstack(fill_value=0).reindex(win.cid).fillna(0)
st = win.start_ts.to_numpy(np.int64)
D = pd.DataFrame({"cid": win.cid, "start_ts": st})
D["M1"] = (L(st - 61) - L(st - 301)) * 1e4
D["M2"] = (L(st - 1) - L(st - 61)) * 1e4
for j in range(5):
    D[f"w{j}"] = (L(st + 60 * j + 59) - L(st + 60 * j - 1)) * 1e4
k = pt.reindex(st).to_numpy(float); kp = pt.reindex(st - 300).to_numpy(float)
D["prev_up"] = np.sign(k - kp)
D["gap_open"] = (L(st - 1) - np.log(k)) * 1e4    # spot at the open vs the strike (bp)
for j in range(5):
    D[f"n{j}"] = nm[j].to_numpy() if j in nm.columns else 0.0
D = D[np.isfinite(D[["M1", "M2", "prev_up", "gap_open"]]).all(1)]
out = {}
for per, m in (("BUILD", D.start_ts < VAL0), ("VALIDATE", (D.start_ts >= VAL0) & (D.start_ts < H))):
    Dm = D[m]
    rr = {}
    for j in range(5):
        cols = ["M1", "M2", "prev_up", "gap_open"] + [f"w{i}" for i in range(j + 1)]
        X = sm.add_constant(Dm[cols].astype(float))
        f = sm.OLS(Dm[f"n{j}"].astype(float), X).fit(cov_type="HC1")
        rr[f"minute{j}"] = {"R2": round(float(f.rsquared), 4), "t": {c: round(float(f.tvalues[c]), 1) for c in cols}, "coef": {c: round(float(f.params[c]), 2) for c in cols}}
    # window net on the whole path
    cols = ["M1", "M2", "prev_up", "gap_open"] + [f"w{i}" for i in range(5)]
    X = sm.add_constant(Dm[cols].astype(float))
    tot = Dm[[f"n{i}" for i in range(5)]].sum(1)
    f = sm.OLS(tot.astype(float), X).fit(cov_type="HC1")
    rr["window_total"] = {"R2": round(float(f.rsquared), 4), "t": {c: round(float(f.tvalues[c]), 1) for c in cols}}
    out[per] = rr
# out-of-sample: BUILD-fitted window-total model scored on VALIDATE (uses the whole path: a description, not PIT)
cols = ["M1", "M2", "prev_up", "gap_open"] + [f"w{i}" for i in range(5)]
mb, mv = D.start_ts < VAL0, (D.start_ts >= VAL0) & (D.start_ts < H)
f = sm.OLS(D.loc[mb, [f"n{i}" for i in range(5)]].sum(1), sm.add_constant(D.loc[mb, cols])).fit()
pv = f.predict(sm.add_constant(D.loc[mv, cols]))
out["window_total_build_fit_validate_r"] = round(float(np.corrcoef(pv, D.loc[mv, [f"n{i}" for i in range(5)]].sum(1))[0, 1]), 4)
json.dump(out, open(f"{R}/fvnet12.json", "w"), indent=1)
for per in ("BUILD", "VALIDATE"):
    for kk, v in out[per].items():
        print(per, kk, v["R2"], v["t"])
print("oos r", out["window_total_build_fit_validate_r"])
