"""Iteration 8 (Q2): are the wallet's "alone" take clusters co-signed in a SIBLING market of the same event (another
map or the match, the same team) by one of the 19 fixed-lag subscribers (cs2_cosign_scan.json)? Token -> (event, team)
from the universe outcomes; a subscriber BUY of the same team in any market of the event inside that subscriber's
lag window (its same-token q1 - 25 .. q3 + 25 ms) counts. Null: the same with a 30-s shift. Output:
results/cross_market_cosign.json"""
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


def main():
    u = pd.read_parquet(OUT / "universe.parquet", columns=["event_slug", "cid", "smt", "tokens", "outcomes"])
    u = u[u.smt.isin(["moneyline", "child_moneyline"])]
    tt = {}
    for r in u.itertuples():
        try:
            toks = json.loads(r.tokens) if isinstance(r.tokens, str) else list(r.tokens)
            outs = json.loads(r.outcomes) if isinstance(r.outcomes, str) else list(r.outcomes)
        except Exception:  # noqa: BLE001
            continue
        for t, o in zip(toks, outs):
            tt[str(t)] = (r.event_slug, str(o).strip().lower())
    sc = json.load(open(RES / "cs2_cosign_scan.json"))["fixed_lag_cosigners"]
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)
    b = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted(glob.glob(str(OUT / "calldata_pub" / "*.parquet")))])
    T = pd.concat([a, b]).drop_duplicates(["tx", "idx"])
    T["maker"] = T.maker.str.lower()
    T["token_id"] = T.token_id.astype(str)
    T = T[(T.idx == -1) & (T.side == 0) & (T.sign_ms > 1.79e12) & (T.sign_ms < H * 1000) & T.token_id.isin(tt)]
    T["key"] = T.token_id.map(tt)
    wt = T[T.maker == W].sort_values("sign_ms").copy()
    S = T[T.maker.isin(set(sc))]
    # per-subscriber window around its same-token lag after the wallet: median +- max(IQR, 50) ms
    win = {w_: (v["median_ms"] - max(v["iqr_ms"], 50.0), v["median_ms"] + max(v["iqr_ms"], 50.0)) for w_, v in sc.items()}
    byk = {}
    for r in S.itertuples():
        byk.setdefault(r.key, []).append((r.sign_ms, r.maker, r.token_id))
    byk = {k: (np.array([x[0] for x in v], float), np.array([x[1] for x in v]), np.array([x[2] for x in v])) for k, v in byk.items()}
    cl = (wt.sign_ms.diff().fillna(1e9) > 500).cumsum().to_numpy()
    nC = cl.max() + 1

    def hits(shift):
        same, cross = np.zeros(nC, bool), np.zeros(nC, bool)
        for c, r in zip(cl, wt.itertuples()):
            x = byk.get(r.key)
            if x is None:
                continue
            d = x[0] - (r.sign_ms + shift)
            for dd, w_, tk in zip(d, x[1], x[2]):
                lo, hi = win[w_]
                if lo <= dd <= hi:
                    if tk == r.token_id:
                        same[c] = True
                    else:
                        cross[c] = True
        return same, cross
    s0, c0 = hits(0.0)
    s1, c1 = hits(30000.0)
    s2, c2 = hits(-30000.0)
    res = {"clusters": int(nC), "same_token_share": round(float(s0.mean()), 3), "cross_market_only_share": round(float((c0 & ~s0).mean()), 3),
           "any_share": round(float((s0 | c0).mean()), 3),
           "null_any_share": round(float(((s1 | c1).mean() + (s2 | c2).mean()) / 2), 3),
           "null_same_token_share": round(float((s1.mean() + s2.mean()) / 2), 3)}
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "cross_market_cosign.json", "w"), indent=1)


if __name__ == "__main__":
    main()
