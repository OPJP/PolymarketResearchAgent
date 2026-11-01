"""Iteration 8, X104 (information panel iter7 P4): re-score the untriggered-pull effect (X94 / Z4) on public trade
PRINTS instead of the book mid, so that other makers who copy its pulls on the book cannot produce it. BUILD-live
pull bursts (own_bursts_markouts_dev, validated label) and ground-truth wallet cancels (gt_markouts inputs). Print price
normalised to token 0 (data-api trades of the dev markets, wallet transactions excluded, block-time stamps).
markout_h = sign x (VWAP of prints in (t + h0, t + h1] - last print at or before t), windows (+5, +15], (+25, +35],
(+100, +140] s; sign = +1 for token-0 bids pulled (expects a fall), -1 for token-1 bids. Null: 1,000 within-book shifts
of +-U(60, 600) s. Output: results/print_markout.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
WIN = ((5, 15), (25, 35), (100, 140))
SUF = os.environ.get("TOMMY_BLOCK_SUFFIX", "")
END = int(os.environ.get("TOMMY_BLOCK_END", 1793469600))
rng = np.random.default_rng(13)


def main():
    B = pd.read_parquet(OUT / f"own_bursts_markouts_dev{SUF}.parquet")
    dm = pd.read_parquet(OUT / f"dev_markets{SUF}.parquet")
    cid_of = {str(r.tok0): r.cid for r in dm.itertuples()}
    gs_of = {str(r.tok0): r.gs for r in dm.itertuples()}
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet", columns=["tx", "maker"])
    wtx = set(cd.loc[cd.maker.str.lower() == WALLET, "tx"])
    pm = PolymarketData()
    PR = {}
    for a in set(B.a):
        x, _, _ = pm.market_trades(cid_of[a], start=int(gs_of[a]) - 3600, end=END + 600, taker_only=True)
        d = pd.DataFrame(x)
        d = d[~d.transactionHash.isin(wtx) & (d.proxyWallet.str.lower() != WALLET)]
        d["p0"] = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        d = d.sort_values("timestamp")
        PR[a] = (d.timestamp.to_numpy(float), d.p0.to_numpy(float), d["size"].astype(float).to_numpy())

    def mk(a, t, sg):
        ts, p, z = PR[a]
        j = np.searchsorted(ts, t, side="right") - 1
        if j < 0:
            return [np.nan] * len(WIN)
        out = []
        for h0, h1 in WIN:
            m = (ts > t + h0) & (ts <= t + h1)
            out.append(sg * (np.average(p[m], weights=z[m]) - p[j]) if m.any() else np.nan)
        return out
    res = {}
    groups = {"untrig_all": B[(B.kind == "pull") & (B.trig_code == 0)], "untrig_multi": B[(B.kind == "pull") & (B.trig_code == 0) & (B.n >= 2)],
              "untrig_single": B[(B.kind == "pull") & (B.trig_code == 0) & (B.n == 1)], "trig": B[(B.kind == "pull") & (B.trig_code == 1)]}
    G = OUT / f"gt_cancels_dev{SUF}.parquet"
    if G.exists():
        g = pd.read_parquet(G)
        groups["gt_wallet_all"] = g[g.owner == "wallet"]
        groups["gt_other_all"] = g[g.owner != "wallet"]
    for name, g in groups.items():
        sg = np.where(g.side.to_numpy() == "BUY", 1.0, -1.0)
        M = np.array([mk(a, s / 1000, s_) for a, s, s_ in zip(g.a, g.s, sg)], float)
        o = {"n": int(len(g))}
        for k, (h0, h1) in enumerate(WIN):
            v = M[:, k]
            o[f"mk_{h0}_{h1}_c"] = round(float(np.nanmean(v) * 100), 3) if np.isfinite(v).any() else None
            o[f"n_{h0}_{h1}"] = int(np.isfinite(v).sum())
        if len(g) >= 10:
            nul = []
            for _ in range(1000):
                sh = rng.choice([-1, 1], len(g)) * rng.uniform(60, 600, len(g))
                Mn = np.array([mk(a, s / 1000 + d, s_) for a, s, s_, d in zip(g.a, g.s, sg, sh)], float)
                nul.append(np.nanmean(Mn[:, 0]))
            nul = np.array(nul)
            o["null_mk_5_15_c"] = round(float(np.nanmean(nul) * 100), 3)
            o["p_lower_5_15"] = round(float((nul <= np.nanmean(M[:, 0])).mean()), 4)
        res[name] = o
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / f"print_markout{SUF}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
