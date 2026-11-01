"""Iteration 13 (X117 = information panel P5): does short-dated IMPLIED vol scale the buy-back in the window net path? Deribit BTC
DVOL at 1-minute resolution (public get_volatility_index_data, resolution 60, 10-09..22, end < H) vs the 15-min realized vol of
Binance 1-s returns before the window open: z = log(DVOL per second / RV15). Window-minute panel (minutes 1..4, fvnet12 layout):
the operator's net bought in minute j on the current minute's move w_j, the sum of the earlier minutes' moves E_j, their
interactions with z, controls (M1, M2, prev_up, gap_open, minute FE); OLS with window-clustered t, BUILD and VALIDATE separately.
Signature (pre-registered by the panel): the E_j x z interaction significant with the same sign in both."""
import os, sys, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT)
import numpy as np, pandas as pd
import statsmodels.api as sm
from polyrea.adapters.http import shared_client
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
VAL0, H = 1792108800, 1792713600
T0 = 1791504000 - 3600


def dvol_minutes():
    cl = shared_client(); rows = []
    t = T0
    while t < H:
        e = min(t + 900 * 60, H) - 1
        js, _ = cl.get_json("https://www.deribit.com/api/v2/public/get_volatility_index_data",
                            {"currency": "BTC", "start_timestamp": t * 1000, "end_timestamp": e * 1000, "resolution": 60}, adapter="deribit", max_age=None)
        data = js["result"]["data"]
        rows += [r for r in data if r[0] // 1000 < H]
        t = e + 1
        time.sleep(0.2)
    d = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c"]).drop_duplicates("t").sort_values("t")
    return pd.Series(d.c.to_numpy(float) / 100.0, index=(d.t // 1000).to_numpy(np.int64))


def main():
    dv = dvol_minutes()
    b = pd.read_parquet(f"{C}/binance_1s.parquet")
    s0 = int(b.sec.min()); px = b.set_index("sec").close.reindex(np.arange(s0, int(b.sec.max()) + 1)).ffill().to_numpy(float)
    lp = np.log(px); L = lambda t: lp[np.clip(np.asarray(t, np.int64) - s0, 0, len(lp) - 1)]
    r1 = np.r_[0.0, np.diff(lp)]; c2 = np.cumsum(r1 ** 2)
    win = pd.read_parquet(f"{C}/windows.parquet"); win = win[win.up_payout.notna() & (win.start_ts < H)].sort_values("start_ts").reset_index(drop=True)
    pt = pd.read_parquet(f"{C}/ptb.parquet").set_index("start").priceToBeat.astype(float)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["shares", "cid", "rel", "is_up"])
    fl["sg"] = np.where(fl.is_up, 1.0, -1.0) * fl.shares
    fl = fl[(fl.rel >= 0) & (fl.rel < 300)]; fl["m"] = (fl.rel // 60).astype(int)
    nm = fl.groupby(["cid", "m"]).sg.sum().unstack(fill_value=0).reindex(win.cid).fillna(0)
    st = win.start_ts.to_numpy(np.int64)
    rv15 = np.sqrt(np.maximum((c2[np.clip(st - 2 - s0, 0, None)] - c2[np.clip(st - 902 - s0, 0, None)]) / 900.0, 1e-14))
    dvm = dv.reindex(((st - 60) // 60) * 60).to_numpy(float) / np.sqrt(365.0 * 86400.0)  # minute closed before the open
    z = np.log(dvm / rv15)
    k = pt.reindex(st).to_numpy(float); kp = pt.reindex(st - 300).to_numpy(float)
    base = pd.DataFrame({"cid": win.cid, "st": st, "z": z, "M1": (L(st - 61) - L(st - 301)) * 1e4, "M2": (L(st - 1) - L(st - 61)) * 1e4,
                         "prev_up": np.sign(k - kp), "gap_open": (L(st - 1) - np.log(k)) * 1e4})
    for j in range(5):
        base[f"w{j}"] = (L(st + 60 * j + 59) - L(st + 60 * j - 1)) * 1e4
        base[f"n{j}"] = nm[j].to_numpy() if j in nm.columns else 0.0
    rows = []
    for j in range(1, 5):
        d = base[["cid", "st", "z", "M1", "M2", "prev_up", "gap_open"]].copy()
        d["j"] = j; d["w"] = base[f"w{j}"]; d["E"] = base[[f"w{i}" for i in range(j)]].sum(1); d["n"] = base[f"n{j}"]
        rows.append(d)
    P = pd.concat(rows, ignore_index=True)
    P = P[np.isfinite(P[["z", "M1", "M2", "prev_up", "gap_open", "w", "E"]]).all(1)]
    P["zc"] = P.z - P.z.mean()
    P["w_z"] = P.w * P.zc; P["E_z"] = P.E * P.zc
    for j in (2, 3, 4):
        P[f"fe{j}"] = (P.j == j).astype(float)
    res = {"dvol_minutes": int(len(dv)), "z_q": [round(float(x), 3) for x in np.nanpercentile(z, [5, 25, 50, 75, 95])]}
    cols = ["M1", "M2", "prev_up", "gap_open", "w", "E", "zc", "w_z", "E_z", "fe2", "fe3", "fe4"]
    for per, m in (("BUILD", P.st < VAL0), ("VALIDATE", P.st >= VAL0)):
        d = P[m]
        f = sm.OLS(d.n.astype(float), sm.add_constant(d[cols].astype(float))).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.cid)[0]})
        res[per] = {"n": int(len(d)), "coef": {c: round(float(f.params[c]), 3) for c in ["w", "E", "zc", "w_z", "E_z"]},
                    "t": {c: round(float(f.tvalues[c]), 2) for c in ["w", "E", "zc", "w_z", "E_z"]}, "R2": round(float(f.rsquared), 4)}
    json.dump(res, open(f"{R}/iv13.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
