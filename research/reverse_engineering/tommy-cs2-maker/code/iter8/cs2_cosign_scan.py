"""Iteration 8 (Q2, the 74% "alone" takes): a general co-signer scan of the wallet's CS2 takes over ALL public takers
(16-22 Oct full matched-order record: calldata_all + calldata_pub), not only the six known subscribers. Per wallet:
same-token BUY taker orders within +-1 s of a wallet take, against a 30-s shift null (20 draws), median lag and IQR.
Fixed-lag co-signers = n >= 10, n >= 5 x null, IQR <= 300 ms. Then the share of the wallet's take clusters (500-ms gap)
with any fixed-lag co-signer inside its own +-IQR window around its median lag, with and without the six known
subscribers. Output: results/cs2_cosign_scan.json
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
H = 1792713600
SIX = {"0x4ebc2722adc772bde8680792d0a6fdf15499a33d", "0x2005d16a84ceefa912d4e380cd32e7ff827875ea",
       "0x8a80528dce46711a54aa3455c2cc81dea51e11c5", "0xddb6e6246546230503f153506ac1e9914978b9b3",
       "0xf1ee4842fa0c7283632185e42577027452d4519c", "0x93078b5dd1c34d0f288d2f51b23f1347520d9da3"}


def main():
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["cid"])
    ud = pd.read_parquet(OUT / "universe_dota.parquet", columns=["cid"])
    a = a[~a.cid.isin(set(ud.cid))]
    b = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted(glob.glob(str(OUT / "calldata_pub" / "*.parquet")))])
    T = pd.concat([a[cols], b]).drop_duplicates(["tx", "idx"])
    T["maker"] = T.maker.str.lower()
    T["token_id"] = T.token_id.astype(str)
    T = T[(T.idx == -1) & (T.side == 0) & (T.sign_ms > 1.79e12) & (T.sign_ms < H * 1000)]
    wt = T[T.maker == W].sort_values("sign_ms")
    ot = T[T.maker != W]
    g = {k: (v.sign_ms.to_numpy(float), v.maker.to_numpy()) for k, v in ot.groupby("token_id")}
    rng = np.random.default_rng(12)
    lag, who = [], []
    for r in wt.itertuples():
        x = g.get(r.token_id)
        if x is None:
            continue
        d = x[0] - r.sign_ms
        m = np.abs(d) <= 1000
        lag += list(d[m])
        who += list(x[1][m])
    nul = {}
    for _ in range(20):
        sh = rng.choice([-1, 1], len(wt)) * 30000
        for r, s_ in zip(wt.itertuples(), sh):
            x = g.get(r.token_id)
            if x is None:
                continue
            d = x[0] - (r.sign_ms + s_)
            for w_ in x[1][np.abs(d) <= 1000]:
                nul[w_] = nul.get(w_, 0) + 1 / 20
    L = pd.DataFrame({"lag": lag, "who": who})
    st = L.groupby("who").lag.agg(n="size", med="median", q1=lambda v: np.percentile(v, 25), q3=lambda v: np.percentile(v, 75))
    st["null"] = st.index.map(lambda w_: nul.get(w_, 0.0))
    st["iqr"] = st.q3 - st.q1
    fixed = st[(st.n >= 10) & (st.n >= 5 * np.maximum(st.null, 0.2)) & (st.iqr <= 300)].sort_values("n", ascending=False)
    res = {"wallet_cs2_takes": int(len(wt)), "fixed_lag_cosigners": {w_: {"n": int(r.n), "null": round(float(r.null), 2), "median_ms": round(float(r.med), 1),
                                                                          "iqr_ms": round(float(r.iqr), 1), "known_six": w_ in SIX}
                                                                     for w_, r in fixed.head(25).iterrows()}}
    # cluster-level share with any fixed-lag co-signer in its window
    cl = (wt.sign_ms.diff().fillna(1e9) > 500).cumsum().to_numpy()
    win = {w_: (r.q1 - 25, r.q3 + 25) for w_, r in fixed.iterrows()}
    hit_all, hit_new = np.zeros(cl.max() + 1, bool), np.zeros(cl.max() + 1, bool)
    for c, r in zip(cl, wt.itertuples()):
        x = g.get(r.token_id)
        if x is None:
            continue
        d = x[0] - r.sign_ms
        for dd, w_ in zip(d, x[1]):
            if w_ in win and win[w_][0] <= dd <= win[w_][1]:
                hit_all[c] = True
                if w_ not in SIX:
                    hit_new[c] = True
    res["clusters"] = int(cl.max() + 1)
    res["share_clusters_with_any_fixed_lag_cosigner"] = round(float(hit_all.mean()), 3)
    res["share_clusters_with_a_new_fixed_lag_cosigner"] = round(float(hit_new.mean()), 3)
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "cs2_cosign_scan.json", "w"), indent=1)


if __name__ == "__main__":
    main()
