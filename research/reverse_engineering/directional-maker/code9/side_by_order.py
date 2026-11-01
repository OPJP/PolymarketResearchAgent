"""Iteration 9: which of the cluster's orders carry the posture? Per-fill side (match clock, 10-31 12:00-18:00 table
side_D) joined to the filled order's original size from the V2 calldata (live1031 / liveall1031 / it9sw), by order class
(exact 500 shares vs other) and vol regime, frozen sigma (1.4 x v300) vs slow (v3600, k 1). Development, descriptive."""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"
A, B = 1793448000, 1793469600


def main():
    D = pd.read_parquet(C / "it9" / f"side_D_{A}_{B}.parquet").reset_index(drop=True)
    xs = [pd.read_parquet(p, columns=["h", "s"]) for p in glob.glob(str(C / "it6" / "x_*.parquet"))]
    X = pd.concat(xs).drop_duplicates()
    X["h"] = X.h.str.lower()
    cd = pd.concat([pd.read_parquet(p, columns=["tx", "maker", "role", "maker_amount", "taker_amount", "oside"]) for p in
                    glob.glob(str(C / "calldata" / "*1031_*.parquet")) + glob.glob(str(C / "calldata" / "it9sw_*.parquet"))])
    cd["tx"] = cd.tx.str.lower()
    cd["maker"] = cd.maker.str.lower()
    cd = cd[cd.role == "maker"]
    cd["shares"] = np.where(cd.oside == 0, cd.taker_amount, cd.maker_amount) / 1e6
    ms2h = X.groupby("s").h.apply(list).to_dict()
    sz = []
    for T, w in zip(D["T"], D.wallet.str.lower()):
        size = np.nan
        for h in ms2h.get(int(T), []):
            g = cd[(cd.tx == h) & (cd.maker == w)]
            if len(g):
                size = float(g.shares.iloc[0])
                break
        sz.append(size)
    D["order_shares"] = sz
    base_sp = pd.read_parquet(C / "it9" / f"spot1s_rest_{A - 7200}_{B}.parquet").sort_values("sec")
    b0 = int(base_sp.sec.iloc[0])
    px = np.full(int(base_sp.sec.iloc[-1]) - b0 + 1, np.nan)
    px[base_sp.sec.astype(int).to_numpy() - b0] = base_sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    r = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(r * r)]
    ti = (D["T"].to_numpy() // 1000) - 1 - b0
    v = lambda L: np.sqrt((cs[ti + 1] - cs[ti + 1 - L]) / L)  # noqa: E731
    v300, v3600 = v(300), v(3600)
    tau = np.maximum(D.en.to_numpy() - D["T"].to_numpy() / 1000, 1.0)
    x = np.log(D.cl.to_numpy(float) / D.K.to_numpy(float))
    y = D.is_up.to_numpy() == 1
    m = D.mid_up.to_numpy()
    okF = (norm.cdf(x / (1.4 * v300 * np.sqrt(tau))) > m) == y
    okS = (norm.cdf(x / (v3600 * np.sqrt(tau))) > m) == y
    fav = ((m > 0.5) == y)
    burst = (v300 / v3600) > 1.5
    cls = np.select([D.order_shares.isna(), np.isclose(D.order_shares, 500, atol=0.6), D.order_shares >= 100], ["unknown", "500", ">=100"], "<100")
    out = {"n": int(len(D)), "matched": int(D.order_shares.notna().sum())}
    for c in ("500", ">=100", "<100", "unknown"):
        for lab, g in (("all", np.ones(len(D), bool)), ("burst", burst), ("calm", ~burst)):
            k = (cls == c) & g
            if k.sum() >= 10:
                out[f"{c}|{lab}"] = {"n": int(k.sum()), "frozen": round(float(okF[k].mean()), 3), "slow": round(float(okS[k].mean()), 3),
                                     "bought_favourite": round(float(fav[k].mean()), 3)}
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter9_side_by_order.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
