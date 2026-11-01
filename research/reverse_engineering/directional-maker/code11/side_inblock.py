"""Iteration 11 (pre-registered H11-SIDE-INBLOCK, NOTES 01:06 UTC): the per-fill Chainlink posture on the lot with the
in-block mid (the last clean trade before the fill in execution order) vs the iteration-10 mid (last clean print at
b - 3). Inputs as code10/a1_score.py lot(): volhist (Binance v300, block second), taker sign_ms -> T_hat, Chainlink
from the detached fetch (cl_source._cache), Gamma strike (cl/ptb_lot.parquet). VALIDATE aggregate only.
    python code11/side_inblock.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import cl_source  # noqa: E402

C = ROOT / ".cache/re/directional-maker"


def that(sign_ms, bms):
    sign_ms = np.asarray(sign_ms, dtype=float)
    bms = np.asarray(bms, dtype=float)
    ok = np.isfinite(sign_ms) & (sign_ms > 0) & (bms - sign_ms < 60000) & (bms - sign_ms > -1000)
    return np.where(ok, np.clip(np.nan_to_num(sign_ms) + 620, bms - 3000, bms - 1500), bms - 2285)


def main():
    ptb = pd.read_parquet(C / "cl/ptb_lot.parquet")
    K = dict(zip(ptb.start_ts.astype(int), ptb.ptb.astype(float)))
    clv = cl_source._cache()
    IB = pd.read_parquet(C / "it11" / "inblock_scored_all.parquet")
    IB["txh"] = IB.txh.str.lower()
    IB = IB.drop_duplicates(["txh", "token"]).set_index(["txh", "token"])
    out = {}
    rng = np.random.default_rng(11)
    for sp, fn in (("study", "b1_takers_study"), ("validate", "b1_takers_valid")):
        v = pd.read_parquet(C / f"it9/volhist_{sp}.parquet", columns=["txh", "wallet", "b", "st", "en", "is_up", "price", "mid_up", "v300", "token"])
        t = pd.read_parquet(C / f"{fn}.parquet", columns=["tx", "sign_ms"])
        t["tx"] = t.tx.str.lower()
        t = t.drop_duplicates("tx").set_index("tx")
        v["txh"] = v.txh.str.lower()
        v["T_hat"] = that(v.txh.map(t.sign_ms), v.b.astype(float) * 1000)
        v["cl"] = ((v.T_hat - 1432) // 1000).astype(np.int64).map(lambda s: clv.get(int(s), np.nan))
        v["K"] = v.st.map(K)
        v["tau"] = np.maximum(v.en - v.T_hat / 1000.0, 1.0)
        key = list(zip(v.txh, v.token.astype(str)))
        a_in = IB["a_in"].reindex(key).to_numpy()
        v["mid_in"] = np.where(v.is_up == 1, a_in, 1 - a_in)
        h = v.dropna(subset=["cl", "K", "mid_in", "mid_up"]).copy()
        x = np.log(h.cl / h.K).to_numpy()
        f = norm.cdf(x / (1.4 * h.v300.to_numpy() * np.sqrt(h.tau.to_numpy())))
        y = h.is_up.to_numpy() == 1
        acc_a = (f > h.mid_up.to_numpy()) == y
        acc_i = (f > h.mid_in.to_numpy()) == y
        blocks = (h.b // 7200).to_numpy()
        ub = np.unique(blocks)
        idx = {u: np.nonzero(blocks == u)[0] for u in ub}
        g = []
        for _ in range(2000):
            pick = np.concatenate([idx[u] for u in rng.choice(ub, len(ub), replace=True)])
            g.append(acc_i[pick].mean() - acc_a[pick].mean())
        g = np.array(g)

        def regD(mid):
            m = mid
            ok = np.isfinite(m) & (np.abs(m - 0.5) > 0) & (x != 0)
            D = ok & ((x > 0) != (m > 0.5))
            return {"n_D": int(D.sum()), "acc_D": float(np.mean(((x > 0) == y)[D])) if D.any() else None}
        o = {"n_fills_with_cl": int(len(h)), "n_fills": int(len(v)), "posture_mid_b3": round(float(acc_a.mean()), 4),
             "posture_mid_inblock": round(float(acc_i.mean()), 4), "gain": round(float(acc_i.mean() - acc_a.mean()), 4),
             "gain_ci95_2h_blocks": [round(float(np.quantile(g, 0.025)), 4), round(float(np.quantile(g, 0.975)), 4)],
             "regionD_mid_b3": regD(h.mid_up.to_numpy()), "regionD_mid_inblock": regD(h.mid_in.to_numpy()),
             "per_wallet_inblock": {str(w): round(float(acc_i[(h.wallet == w).to_numpy()].mean()), 4) for w in h.wallet.unique()}}
        if sp == "validate":
            h1 = (h.b < 1793232000).to_numpy()
            o["halves_inblock"] = [round(float(acc_i[h1].mean()), 4), round(float(acc_i[~h1].mean()), 4)]
        o["adopt"] = bool(o["gain"] >= 0.02 and o["gain_ci95_2h_blocks"][0] > 0) if sp == "validate" else None
        out[sp] = o
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter11_side_inblock.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
