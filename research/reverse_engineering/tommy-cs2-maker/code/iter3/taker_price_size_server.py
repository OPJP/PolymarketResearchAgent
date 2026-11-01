"""Iteration 3: the taker limit price and size against the SERVER-clock book just before signing (X13 redo).

Dev block 10-31 (dev-unit markets the wallet traded), books from tommy_cs2_near where available else clob_wallets,
indexed by the server field s. For each wallet taker BUY (team X): the best ask of X and the depth of X asks up to its
limit, 50 ms before signing (the pre-event book: the book is flat until its signing), and the same 900 ms after
signing (after the cancel wave, before its match at +1.04 s). Reported: limit minus pre-event best ask (cents), size /
pre-event depth up to the limit, size / post-wave depth, and the filled share. Output: results/taker_price_size_server.json
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, T0, read  # noqa: E402


def books(recs_sh, recs_own, a):
    out = []
    bd = od = None
    own = sorted([r for r in recs_own if r["a"] == a and r["k"] in ("f", "pc")], key=lambda r: (r["s"], r["t"]))
    t_own0 = own[0]["s"] if own else np.inf
    for r in sorted([r for r in recs_sh if r["a"] == a and r["k"] in ("q", "f") and r["s"] < t_own0], key=lambda r: r["s"]):
        out.append((r["s"], {float(p): float(z) for p, z in r["b"]}, {float(p): float(z) for p, z in r["o"]}))
    for r in own:
        if r["k"] == "f":
            bd = {float(p): float(z) for p, z in r["b"]}
            od = {float(p): float(z) for p, z in r["o"]}
        elif bd is not None:
            for side, p, z in r["c"]:
                bk = bd if side == "BUY" else od
                if float(z) == 0:
                    bk.pop(float(p), None)
                else:
                    bk[float(p)] = float(z)
        else:
            continue
        out.append((r["s"], dict(bd), dict(od)))
    return out


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
    w = d[(d.idx == -1) & (d.maker == WALLET) & (d.side == 0) & (d.sign_ms > 1.79e12) & (d.sign_ms < 1.8e12)
          & d.token_id.astype(str).isin(tok)].drop_duplicates("tx")
    rows = []
    for r in w.itertuples():
        a, k = tok[str(r.token_id)]
        if len(S[a]) == 0 or r.sign_ms < S[a][0] + 1000:
            continue
        res = {"limit": r.price, "size": r.shares, "fill": r.fill}
        for lab, off in (("pre", -50), ("post", 900)):
            i = np.searchsorted(S[a], r.sign_ms + off, side="right") - 1
            _, bd, od = B[a][i]
            # asks of the bought token: token 0 -> od; token 1 -> mirrored token-0 bids at 1 - p
            asks = od if k == 0 else {round(1 - p, 4): z for p, z in bd.items()}
            if not asks:
                continue
            ba = min(asks)
            res[f"ask_{lab}"] = ba
            res[f"depth_{lab}"] = sum(z for p, z in asks.items() if p <= r.price + 1e-9)
        rows.append(res)
    x = pd.DataFrame(rows).dropna()
    x["prem"] = ((x.limit - x.ask_pre) * 100).round()
    out = {"orders": int(len(x)),
           "limit_minus_pre_ask_cents": {str(int(k)): round(float(v), 3) for k, v in x.prem.value_counts(normalize=True).sort_index().items()},
           "limit_at_or_above_pre_ask": round(float((x.prem >= 0).mean()), 3),
           "size_over_pre_depth_median": round(float((x["size"] / x.depth_pre.replace(0, np.nan)).median()), 3),
           "size_over_post_depth_median": round(float((x["size"] / x.depth_post.replace(0, np.nan)).median()), 3),
           "post_over_pre_depth_median": round(float((x.depth_post / x.depth_pre.replace(0, np.nan)).median()), 3),
           "fill_over_pre_depth_median": round(float((x.fill / x.depth_pre.replace(0, np.nan)).median()), 3),
           "fill_over_post_depth_median": round(float((x.fill / x.depth_post.replace(0, np.nan)).median()), 3),
           "pre_ask_moved_by_post_share": round(float((x.ask_post > x.ask_pre + 1e-9).mean()), 3)}
    json.dump(out, open(RES / "taker_price_size_server.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
