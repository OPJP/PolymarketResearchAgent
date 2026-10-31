"""Iteration 10: H-VOL-500 (pre-registered in NOTES 23:34 UTC). Frozen 1.4 x v300 vs slow v3600 x 1 in the Chainlink
posture, on the 500-class fills of the lot with the real Chainlink value on the calibrated match clock (r7_side.table)."""
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
        vv = pd.read_parquet(C / f"it9/volhist_{sp}.parquet", columns=["txh", "wallet", "token", "b", "v3600"])
        vv["txh"] = vv.txh.str.lower()
        h = h.merge(vv.drop_duplicates(["txh", "wallet", "token", "b"]), on=["txh", "wallet", "token", "b"], how="left")
        h = h[(h.cls == "500") & h.v3600.notna()].copy()
        x = np.log(h.cl.to_numpy(float) / h.K.to_numpy(float))
        tau = np.maximum(h.en.to_numpy() - h.T_hat.to_numpy() / 1000.0, 1.0)
        m = h.mid_up.to_numpy(float)
        h["p_slow"] = norm.cdf(x / (h.v3600.to_numpy(float) * np.sqrt(tau))) > m
        gain, ci = R.boot(h, "p_slow", "p_chainlink")
        D = ((x > 0) != (m > 0.5)) & (x != 0)
        out[sp] = {"n": int(len(h)), "frozen": float(np.mean(h.p_chainlink == h.y)), "slow_v3600": float(np.mean(h.p_slow == h.y)), "gain": gain, "ci_2h_blocks": ci,
                   "region_A_frozen": float(np.mean((h.p_chainlink == h.y)[~D])), "region_A_slow": float(np.mean((h.p_slow == h.y)[~D])),
                   "cheaper_side": float(np.mean((m < 0.5) == h.y.to_numpy()))}
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_hvol500.json", "w"), indent=1)


if __name__ == "__main__":
    main()
