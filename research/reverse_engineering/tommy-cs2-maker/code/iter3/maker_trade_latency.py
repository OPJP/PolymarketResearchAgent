"""Iteration 3, X26: does the wallet's maker re-signing follow the PUBLIC trade message (server clock)?

Dev block 10-31 (dev-unit markets the wallet traded), CLOB trade messages x (server time s, both recorders, deduped by
tx hash) and the wallet's maker orders from calldata_dev (sign_ms, the wallet's clock = server within ~40 ms). For each
maker order: offset to the latest trade message in the same market before its signing; the histogram of offsets in
[0, 300) ms (5-ms bins) against a uniform baseline (orders' offsets if trade times are shifted by -7 s). Also split by
whether that trade filled the wallet itself (its own fills arrive on its user channel) or only others.
Output: results/maker_trade_latency.json
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, T0, read  # noqa: E402


def main():
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    m = m[m.wallet_trades > 0]
    tok = {}
    for r in m.itertuples():
        tok[r.tok0] = (r.cid, 0)
        tok[r.tok1] = (r.cid, 1)
    tok0 = set(m.tok0)
    recs = read("clob_wallets", tok0, T0 + 12 * 3600, time.time()) + read("tommy_cs2_near", tok0, T0 + 12 * 3600, time.time())
    X = {}
    for r in recs:
        if r.get("k") == "x":
            h = (r.get("h") or "").lower()
            if h and (h not in X or r["s"] < X[h][0]):
                X[h] = (r["s"], tok[r["a"]][0])
    xt = pd.DataFrame([(h, s, c) for h, (s, c) in X.items()], columns=["tx", "s", "cid"])
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    d = d[(d.sign_ms > 1.79e12) & (d.sign_ms < 1.8e12) & d.token_id.astype(str).isin(tok)]
    d["tx"] = d.tx.str.lower()
    mine = set(d[d.maker == WALLET].tx)
    xt["mine"] = xt.tx.isin(mine)
    wm = d[(d.idx >= 0) & (d.maker == WALLET)].drop_duplicates(["salt", "sign_ms"]).copy()
    wm["cid"] = wm.token_id.astype(str).map(lambda t: tok[t][0])
    res = {"maker_orders": int(len(wm)), "trade_msgs": int(len(xt))}
    for shift, lab in ((0, "actual"), (-7000, "shifted_-7s")):
        offs, own = [], []
        for c, g in wm.groupby("cid"):
            x = xt[xt.cid == c].sort_values("s")
            if len(x) == 0:
                continue
            S = x.s.to_numpy() + shift
            mi = x.mine.to_numpy()
            k = np.searchsorted(S, g.sign_ms.to_numpy(), side="left") - 1
            ok = k >= 0
            offs += list((g.sign_ms.to_numpy() - S[np.maximum(k, 0)])[ok])
            own += list(mi[np.maximum(k, 0)][ok])
        offs = np.array(offs)
        own = np.array(own, bool)
        h = np.histogram(offs, np.arange(0, 305, 5))[0]
        res[lab] = {"n": int(len(offs)), "share_within_50ms": round(float((offs < 50).mean()), 3),
                    "share_within_100ms": round(float((offs < 100).mean()), 3),
                    "share_within_50ms_after_own_fill_msg": round(float(((offs < 50) & own).mean()), 3),
                    "share_within_50ms_after_others_msg": round(float(((offs < 50) & ~own).mean()), 3),
                    "offset_ms_p10_p25_p50": [int(np.percentile(offs, q)) for q in (10, 25, 50)],
                    "hist_5ms_first_20_bins": h[:20].tolist()}
    json.dump(res, open(RES / "maker_trade_latency.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
