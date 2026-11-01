"""Iteration 8: are the newly found fixed-lag co-signers (cs2_cosign_scan.json) feed subscribers or followers of the
wallet? Their same-token BUY lag behind P4e's takes on P4e-alone events (no wallet take within +-1 s) vs on events the
wallet also takes, with a 30-s shift null (16-22 Oct, CS2). A subscriber shows the same fixed lag on both; a follower of
the wallet's book trace co-signs mainly when the wallet acts. Output: results/cosigner_vs_p4e.json"""
from __future__ import annotations
import glob, json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
P4E = "0x4ebc2722adc772bde8680792d0a6fdf15499a33d"
H = 1792713600


def main():
    sc = json.load(open(RES / "cs2_cosign_scan.json"))["fixed_lag_cosigners"]
    new = [w for w, v in sc.items() if not v["known_six"]]
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)
    b = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted(glob.glob(str(OUT / "calldata_pub" / "*.parquet")))])
    T = pd.concat([a, b]).drop_duplicates(["tx", "idx"])
    T["maker"] = T.maker.str.lower()
    T["token_id"] = T.token_id.astype(str)
    T = T[(T.idx == -1) & (T.side == 0) & (T.sign_ms > 1.79e12) & (T.sign_ms < H * 1000)]
    p4 = T[T.maker == P4E]
    wg = {k: v.sign_ms.to_numpy(float) for k, v in T[T.maker == W].groupby("token_id")}
    p4 = p4.assign(wal=[bool(wg.get(t) is not None and np.any(np.abs(wg[t] - s) <= 1000)) for t, s in zip(p4.token_id, p4.sign_ms)])
    rng = np.random.default_rng(1)
    res = {"p4e_takes": int(len(p4)), "p4e_alone": int((~p4.wal).sum())}
    for w_ in new:
        g = {k: v.sign_ms.to_numpy(float) for k, v in T[T.maker == w_].groupby("token_id")}
        o = {}
        for name, sub in (("p4e_alone", p4[~p4.wal]), ("with_wallet", p4[p4.wal])):
            lags, nn = [], 0.0
            for r in sub.itertuples():
                x = g.get(r.token_id)
                if x is None:
                    continue
                d = x - r.sign_ms
                d = d[(d >= 0) & (d <= 1000)]
                if len(d):
                    lags.append(float(d.min()))
                dn = x - (r.sign_ms + rng.choice([-1, 1]) * 30000)
                nn += float(((dn >= 0) & (dn <= 1000)).any())
            o[name] = {"anchors": int(len(sub)), "cosigns": len(lags), "null": round(nn, 1),
                       "share": round(len(lags) / max(len(sub), 1), 4),
                       "median_lag_ms": round(float(np.median(lags)), 1) if lags else None,
                       "iqr_ms": round(float(np.subtract(*np.percentile(lags, [75, 25]))), 1) if len(lags) >= 4 else None}
        res[w_] = o
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "cosigner_vs_p4e.json", "w"), indent=1)


if __name__ == "__main__":
    main()
