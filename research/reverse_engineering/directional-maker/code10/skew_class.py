"""Iteration 10: is the off-session 62/250 ladder unskewed? For each scored lot fill (r7_side.table: real Chainlink,
calibrated match clock), the distance of the fill (= the rung's limit price) below the bought token's last clean print,
d = mid_token - price, regressed on the token's Chainlink edge e = fair_CL(token) - mid_token, per rung class. A skewed
ladder (rungs raised on the side Chainlink favours) gives a negative slope (fills closer to or above the mid when e > 0);
an unskewed ladder a slope near 0. STUDY case by case; VALIDATE as the aggregate slope only. Also the share of fills
priced at or above the last print (price >= mid_token) by class and sign of e."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(ROOT))
import r7_side as R  # noqa: E402
import cl_source  # noqa: E402
import m1_pair_lot as M1  # noqa: E402

C = ROOT / ".cache/re/directional-maker"


def main():
    ptb = pd.read_parquet(C / "cl/ptb_lot.parquet")
    K = dict(zip(ptb.start_ts.astype(int), ptb.ptb.astype(float)))
    clv = cl_source._cache()
    A5 = M1.load_act()
    out = {}
    for sp, fn, ofn in (("study", "b1_takers_study", "b1_cluster_orders_study"), ("validate", "b1_takers_valid", "b1_cluster_orders_valid")):
        h = R.table(sp, fn, ofn, A5, K, clv)
        pr = pd.read_parquet(C / f"it9/volhist_{sp}.parquet", columns=["txh", "wallet", "token", "b", "price"])
        pr["txh"] = pr.txh.str.lower()
        pr = pr.drop_duplicates(["txh", "wallet", "token"])
        h = h.merge(pr, on=["txh", "wallet", "token", "b"], how="left")
        x = np.log(h.cl.to_numpy(float) / h.K.to_numpy(float))
        tau = np.maximum(h.en.to_numpy() - h.T_hat.to_numpy() / 1000.0, 1.0)
        f_up = norm.cdf(x / (1.4 * h.v300.to_numpy(float) * np.sqrt(tau)))
        up = h.is_up.to_numpy() == 1
        mid_tok = np.where(up, h.mid_up.to_numpy(float), 1 - h.mid_up.to_numpy(float))
        f_tok = np.where(up, f_up, 1 - f_up)
        e = f_tok - mid_tok
        d = mid_tok - h.price.to_numpy(float)
        o = {}
        for c in ("500", "62", "250", "pair"):
            k = (h.cls == c).to_numpy() & np.isfinite(e) & np.isfinite(d) & (np.abs(e) < 0.6)
            if k.sum() < 30:
                continue
            sl, ic = np.polyfit(e[k], d[k], 1)
            o[c] = {"n": int(k.sum()), "slope_d_on_e": round(float(sl), 4), "intercept": round(float(ic), 4),
                    "median_d_e_pos": round(float(np.median(d[k & (e > 0.02)])), 4) if (k & (e > 0.02)).any() else None,
                    "median_d_e_neg": round(float(np.median(d[k & (e < -0.02)])), 4) if (k & (e < -0.02)).any() else None,
                    "share_e_pos": round(float(np.mean(e[k] > 0)), 3)}
        out[sp] = o
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_skew_class.json", "w"), indent=1)


if __name__ == "__main__":
    main()
