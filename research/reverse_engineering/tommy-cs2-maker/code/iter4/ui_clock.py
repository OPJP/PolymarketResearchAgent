"""Iteration 4, X40 (information iter3 P4): Polymarket's slow (retail / UI) takers as a historical broadcast clock.

16-22 Oct. Public taker orders of the wallet's markets (calldata_pub + the non-wallet takers of calldata_all), signing
ms. Classes by the address's number of taker orders in these markets: retail <= 20, mid 21-200, heavy > 200.
For each wallet take (BUY team X at signing t): net same-team flow of each class (+1 for BUY X or SELL the complement,
-1 for BUY the complement or SELL X) per 4-s bin of (sign - t) from -20 to +120 s, minus the same around t + shift
(shifts +-300, +-600, +-900 s, averaged) = excess. Takes are split by the time from t to the next >= 4c public jump of
the market (tape, wallet txs excluded): NEAR (<= 10 s, the take is close to a round end) vs FAR (> 40 s).
Reading: if the retail turn tracks the next jump, retail reacts to round ends (the broadcast shows the result); if the
turn lag is the same in both groups, it is a fixed delay (broadcast delay) after the wallet's event.
Output: results/ui_clock.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
BINS = np.arange(-20, 124, 4)
SHIFTS = (-900, -600, -300, 300, 600, 900)


def main():
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)
    b = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted((OUT / "calldata_pub").glob("*.parquet"))])
    cd = pd.concat([a, b[~b.tx.isin(set(a.tx))]], ignore_index=True)
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "token_id", "oi"]).drop_duplicates("token_id")
    tok = {str(k): v for k, v in zip(o.token_id, zip(o.cid, o.oi))}
    cd["tok"] = cd.token_id.astype(str)
    cd = cd[cd.tok.isin(tok) & (cd.idx == -1) & (cd.sign_ms > 1.7e12) & (cd.sign_ms < 1.8e12)].drop_duplicates("tx").copy()
    cd["cid"] = cd.tok.map(lambda t: tok[t][0])
    cd["oi"] = cd.tok.map(lambda t: tok[t][1]).astype(int)
    W = cd[(cd.maker == WALLET) & (cd.side == 0)]
    P = cd[cd.maker != WALLET].copy()
    cnt = P.maker.value_counts()
    P["cls"] = np.where(P.maker.map(cnt) <= 20, "retail", np.where(P.maker.map(cnt) <= 200, "mid", "heavy"))
    # +1 = demand for outcome 0
    P["d0"] = np.where(((P.side == 0) & (P.oi == 0)) | ((P.side == 1) & (P.oi == 1)), 1, -1)
    own_tx = set(a.loc[a.maker == WALLET, "tx"])
    # next >= 4c jump time per wallet take from the windowed tapes (block time, wallet txs excluded)
    nxt = {}
    for cid, g in W.groupby("cid"):
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p, columns=["transactionHash", "timestamp", "outcomeIndex", "price"])
        d = d[~d.transactionHash.isin(own_tx)].sort_values("timestamp", kind="stable")
        ts = d.timestamp.to_numpy(float)
        p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        for r in g.itertuples():
            t = r.sign_ms / 1000
            k = np.searchsorted(ts, t, side="left")
            if k == 0 or k >= len(ts):
                continue
            ref = p0[k - 1]
            mv = np.abs(p0[k:] - ref) >= 0.04 - 1e-9
            j = np.flatnonzero(mv)
            nxt[r.tx] = ts[k + j[0]] - t if len(j) else np.inf
    W = W[W.tx.isin(nxt)].copy()
    W["to_jump"] = W.tx.map(nxt)
    by = {c: g for c, g in P.groupby("cid")}
    res = {"wallet_takes": int(len(W)), "classes": P.cls.value_counts().to_dict(), "groups": {}}
    for grp, sel in (("all", W.to_jump >= 0), ("near_jump_le10s", W.to_jump <= 10), ("far_jump_gt40s", W.to_jump > 40)):
        G = W[sel]
        out = {"takes": int(len(G))}
        for cls in ("retail", "mid", "heavy"):
            obs = np.zeros(len(BINS) - 1)
            ctl = np.zeros(len(BINS) - 1)
            for r in G.itertuples():
                g = by.get(r.cid)
                if g is None:
                    continue
                g = g[g.cls == cls]
                sgn = 1 if r.oi == 0 else -1
                rel = (g.sign_ms.to_numpy(float) - r.sign_ms) / 1000
                dd = g.d0.to_numpy() * sgn
                obs += np.histogram(rel, BINS, weights=dd)[0]
                for sh in SHIFTS:
                    ctl += np.histogram(rel - sh, BINS, weights=dd)[0] / len(SHIFTS)
            ex = obs - ctl
            cum = np.cumsum(ex[BINS[:-1] >= 0])
            pos = np.flatnonzero(cum > 0)
            out[cls] = {"excess_per_4s_bin": {str(int(x)): round(float(v), 1) for x, v in zip(BINS[:-1], ex)},
                        "first_bin_with_cum_excess_pos_s": int(BINS[:-1][BINS[:-1] >= 0][pos[0]]) if len(pos) else None,
                        "excess_0_12s": round(float(ex[(BINS[:-1] >= 0) & (BINS[:-1] < 12)].sum()), 1),
                        "excess_12_60s": round(float(ex[(BINS[:-1] >= 12) & (BINS[:-1] < 60)].sum()), 1),
                        "excess_60_120s": round(float(ex[(BINS[:-1] >= 60) & (BINS[:-1] < 120)].sum()), 1)}
        res["groups"][grp] = out
    json.dump(res, open(RES / "ui_clock.json", "w"), indent=1)
    for grp, v in res["groups"].items():
        print(grp, v["takes"], {c: (v[c]["first_bin_with_cum_excess_pos_s"], v[c]["excess_0_12s"], v[c]["excess_12_60s"], v[c]["excess_60_120s"]) for c in ("retail", "mid", "heavy")})


if __name__ == "__main__":
    main()
