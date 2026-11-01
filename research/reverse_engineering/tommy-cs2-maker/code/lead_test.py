"""T1 lead test: does the wallet's bid (top of each signing burst, relative to the last public print) predict the
future public price beyond tape momentum?  Development data; future prices exclude every wallet transaction."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import H, OUT, RES, TAPES, WALLET, SPLIT  # noqa: E402
from price_timing import load_tape  # noqa: E402

def main():
    o = pd.read_parquet(OUT / "orders.parquet")
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    bad = set(cd.loc[cd["maker"] == WALLET, "tx"])
    mk = o[o["role"] == "maker"].sort_values(["cid", "sign_ms"]).copy()
    d = mk.groupby("cid")["sign_ms"].diff()
    mk["burst"] = (d.isna() | (d > 200)).cumsum()
    top = mk.groupby(["burst", "oi"]).agg(cid=("cid", "first"), t=("sign_ts", "first"), p=("price", "max"),
                                         n=("price", "size"), gs=("gs_ts", "first"), smt=("smt", "first")).reset_index()
    out = []
    for cid, g in top.groupby("cid"):
        tp = load_tape(cid, bad)
        if tp is None:
            continue
        ts = tp["timestamp"].to_numpy(np.int64); p0 = tp["p0"].to_numpy(float)
        t = g["t"].to_numpy(float); oi = g["oi"].to_numpy(int)
        def px(at):
            i = np.searchsorted(ts, at, side="left")
            v = np.where(i > 0, p0[np.maximum(i - 1, 0)], np.nan)
            return np.where(oi == 0, v, 1 - v)
        r = pd.DataFrame({"cid": cid, "t": t, "oi": oi, "p": g["p"].to_numpy(), "n": g["n"].to_numpy(),
                          "gs": g["gs"].to_numpy(), "smt": g["smt"].to_numpy(), "last": px(t), "m30": px(t) - px(t - 30)})
        for h in (5, 10, 30, 60, 120, 300):
            r[f"f{h}"] = px(t + h) - r["last"]
        out.append(r)
    x = pd.concat(out, ignore_index=True).dropna(subset=["last"])
    x["x"] = x["p"] - x["last"]
    res = {"n_bursts": len(x)}
    import statsmodels.api as sm
    for split, s in (("BUILD", x[x.gs < SPLIT]), ("VALIDATE", x[x.gs >= SPLIT])):
        rr = {}
        for h in (5, 10, 30, 60, 120, 300):
            y = s[f"f{h}"]; m = y.notna() & s["m30"].notna()
            X = sm.add_constant(s.loc[m, ["x", "m30"]])
            fit = sm.OLS(y[m], X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(s.loc[m, "cid"])[0]})
            rr[h] = {"n": int(m.sum()), "corr_x": round(float(np.corrcoef(s.loc[m, "x"], y[m])[0, 1]), 3),
                     "corr_m30": round(float(np.corrcoef(s.loc[m, "m30"], y[m])[0, 1]), 3),
                     "b_x": round(float(fit.params["x"]), 3), "t_x": round(float(fit.tvalues["x"]), 1),
                     "b_m30": round(float(fit.params["m30"]), 3), "t_m30": round(float(fit.tvalues["m30"]), 1)}
        res[split] = rr
        # sign of the move vs sign of x when |x| >= 2c
        big = s[(s["x"].abs() >= 0.02) & s["f60"].notna() & (s["f60"] != 0)]
        res[split + "_sign_agree_x2c_f60"] = round(float((np.sign(big["x"]) == np.sign(big["f60"])).mean()), 3)
        res[split + "_n_x2c"] = int(len(big))
        pos = s[s["x"] >= 0.02]
        res[split + "_aggr_bids_share"] = round(float((s["x"] >= 0.01).mean()), 3)
        res[split + "_aggr_f60_mean_c"] = round(float(pos["f60"].mean() * 100), 2)
    json.dump(res, open(RES / "results/lead_test.json", "w"), indent=1)
    print(json.dumps(res, indent=1))
    x.to_parquet(OUT / "bursts_lead.parquet", index=False)

if __name__ == "__main__":
    main()
