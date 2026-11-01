"""Iteration 6, historical analog of finding 21 (16-22 Oct, development): does 0x51dbdd2b re-quote right after the
PACK's informed takes as it does after the wallet's?

Full matched-order record of the wallet's markets (calldata_all + calldata_pub). Anchors: the wallet's in-play BUY FAKs;
the pack's in-play BUY FAKs with no wallet take on the same market within 3 s. For each anchor (signing p, market, bought
token X), the number of 0x51dbdd2b's FILLED maker orders signed in [p, p+100), [p+100, p+500), [p+500, p+1000),
[p+1000, p+1150) ms on the bought token and on its complement, as a rate ratio to 0x51dbdd2b's average in-play signing
rate in that market. (Filled orders only: a censored view of its quoting, the same for both anchor types.)
Output: results/cosub_hist.json
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
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
COSUB = "0x51dbdd2b19427dc8e88bb15a4046a38d8427f9b3"
WINS = [(0, 100), (100, 500), (500, 1000), (1000, 1150)]


def main():
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)
    b = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(OUT / "calldata_pub/*.parquet")))])
    D = pd.concat([a, b], ignore_index=True).drop_duplicates(["tx", "idx"])
    D["tok"] = D.token_id.astype(str)
    D["mk"] = D.maker.str.lower()
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "token_id", "oi", "gs_ts"]).drop_duplicates("token_id")
    tmap = {str(t): (c, int(i), float(g)) for t, c, i, g in zip(o.token_id, o.cid, o.oi, o.gs_ts)}
    D = D[D.tok.isin(tmap) & (D.sign_ms > 1.7e12) & (D.sign_ms < 1.8e12)].copy()
    D["cid"] = D.tok.map(lambda t: tmap[t][0])
    D["oi"] = D.tok.map(lambda t: tmap[t][1])
    D["gs"] = D.tok.map(lambda t: tmap[t][2])
    D = D[D.sign_ms / 1000 >= D.gs]
    pack = set(pd.read_parquet(OUT / "pack_orders.parquet", columns=["maker"]).maker.str.lower()) - {WALLET}
    tk = D[(D.idx == -1) & (D.side == 0)]
    wt = tk[tk.mk == WALLET]
    pt = tk[tk.mk.isin(pack)]
    wts = {c: np.sort(g.sign_ms.to_numpy(float)) for c, g in wt.groupby("cid")}

    def far(c, s):
        x = wts.get(c)
        if x is None or len(x) == 0:
            return True
        j = np.searchsorted(x, s)
        return min(abs(x[j] - s) if j < len(x) else 1e18, abs(x[j - 1] - s) if j > 0 else 1e18) > 3000

    pt = pt[[far(r.cid, r.sign_ms) for r in pt.itertuples()]]
    cs = D[(D.mk == COSUB) & (D.idx >= 0)].drop_duplicates(["tx", "idx"])
    cs_by = {(c, i): np.sort(g.sign_ms.to_numpy(float)) for (c, i), g in cs.groupby(["cid", "oi"])}
    span = D.groupby("cid").sign_ms.agg(["min", "max"])
    rate = {}
    for (c, i), x in cs_by.items():
        dur = max(span.loc[c, "max"] - span.loc[c, "min"], 1.0)
        rate[(c, i)] = len(x) / dur
    res = {"cosub_filled_maker_orders": int(len(cs))}
    for nm, A in (("after_wallet_takes", wt.drop_duplicates("tx")), ("after_pack_only_takes", pt.drop_duplicates("tx"))):
        out = {"anchors": int(len(A))}
        for which in ("bought", "complement"):
            rr = {}
            for lo, hi in WINS:
                cnt = 0.0
                exp = 0.0
                for r in A.itertuples():
                    k = (r.cid, int(r.oi) if which == "bought" else 1 - int(r.oi))
                    x = cs_by.get(k)
                    if x is None:
                        continue
                    cnt += np.searchsorted(x, r.sign_ms + hi) - np.searchsorted(x, r.sign_ms + lo)
                    exp += rate[k] * (hi - lo)
                rr[f"{lo}-{hi}ms"] = round(float(cnt / exp), 2) if exp > 0 else None
            out[which] = rr
        res[nm] = out
    (RES / "cosub_hist.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
