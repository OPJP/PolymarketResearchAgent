"""Iteration 3: the maker ladder's TOP price against the server-clock book (price component, burst unit).

Dev block 10-31 (dev-unit markets the wallet traded). Wallet maker orders from calldata_dev (filled orders only, so
deeper levels are censored); bursts = its maker orders on the same token signed within 200 ms; burst top = the highest
price. Book (tommy_cs2_near where available, else clob_wallets) at sign - 50 ms of the burst's first order, server
clock: best bid / ask of that token. Reported: top minus best bid (cents), top vs best ask, spread; also for single
orders that are not in a burst. Output: results/burst_top_price.json
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, T0, read  # noqa: E402
from taker_price_size_server import books  # noqa: E402


def main():
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    m = m[m.wallet_trades > 0]
    tok = {}
    for r in m.itertuples():
        tok[r.tok0] = (r.tok0, 0)
        tok[r.tok1] = (r.tok0, 1)
    tok0 = set(m.tok0)
    sh = read("clob_wallets", tok0, T0 + 12 * 3600, time.time())
    ow = read("tommy_cs2_near", tok0, T0 + 12 * 3600, time.time())
    B = {a: books(sh, ow, a) for a in tok0}
    S = {a: np.array([x[0] for x in v], float) for a, v in B.items()}
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    wm = d[(d.idx >= 0) & (d.maker == WALLET) & (d.sign_ms > 1.79e12) & (d.sign_ms < 1.8e12) & d.token_id.astype(str).isin(tok)]
    wm = wm.drop_duplicates(["salt", "sign_ms"]).sort_values("sign_ms")
    rows = []
    for t, g in wm.groupby(wm.token_id.astype(str)):
        s = g.sign_ms.to_numpy()
        bid = np.concatenate([[0], np.cumsum(np.diff(s) > 200)])
        for b, gg in g.groupby(bid):
            a, k = tok[t]
            t0 = gg.sign_ms.min()
            if len(S[a]) == 0 or t0 < S[a][0] + 1000:
                continue
            i = np.searchsorted(S[a], t0 - 50, side="right") - 1
            _, bd, od = B[a][i]
            if k == 0:
                bb, ba = (max(bd) if bd else np.nan), (min(od) if od else np.nan)
            else:
                bb, ba = (1 - min(od) if od else np.nan), (1 - max(bd) if bd else np.nan)
            rows.append({"n": len(gg), "top": gg.price.max(), "bb": bb, "ba": ba})
    x = pd.DataFrame(rows).dropna()
    x["rel_bid"] = ((x.top - x.bb) * 100).round()
    x["rel_ask"] = ((x.top - x.ba) * 100).round()
    x["spr"] = ((x.ba - x.bb) * 100).round()
    out = {}
    for lab, g in (("bursts_ge2", x[x.n >= 2]), ("single", x[x.n == 1]), ("all", x)):
        out[lab] = {"n": int(len(g)), "top_minus_bid_cents": {str(int(k)): round(float(v), 3) for k, v in g.rel_bid.value_counts(normalize=True).sort_index().items() if abs(k) <= 6},
                    "top_at_bid": round(float((g.rel_bid == 0).mean()), 3), "top_bid_plus1": round(float((g.rel_bid == 1).mean()), 3),
                    "top_within_1c_of_bid": round(float((g.rel_bid.abs() <= 1).mean()), 3),
                    "top_at_ask_minus1": round(float((g.rel_ask == -1).mean()), 3), "spread_median": float(g.spr.median()),
                    "spread1_share": round(float((g.spr == 1).mean()), 3)}
        g1 = g[g.spr >= 2]
        out[lab]["when_spread_ge2"] = {"n": int(len(g1)), "at_bid": round(float((g1.rel_bid == 0).mean()), 3) if len(g1) else None,
                                      "bid_plus1": round(float((g1.rel_bid == 1).mean()), 3) if len(g1) else None,
                                      "ask_minus1": round(float((g1.rel_ask == -1).mean()), 3) if len(g1) else None}
    json.dump(out, open(RES / "burst_top_price.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
