"""Iteration 10 (A1 = X97, regime vs version): the sigma-free region D on the development block 10-31 00:00-06:00 UTC
(no live recording; block clock, which reproduced the match-clock truth on 10-31 14:06-16:30: 0.952 vs 0.965).
Fills: the cluster's BTC 5m BUY trades of the block (activity), maker role = the tape's taker wallet in that tx is not
a cluster wallet. Market favourite: last clean data-api taker print with ts <= b - 3 (prints in cluster txs removed).
Report: Chainlink stamped b - 4 (endpoint). Strike: Gamma priceToBeat. Usage: a1_0006.py stamps | score"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402
import cl_source  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
A, B = 1793404800, 1793426400
CLU = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
       "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}


def fills():
    act = pd.read_parquet(C / "live_activity_1793404800_1793426400.parquet")
    act = act[(act.type == "TRADE") & (act.side == "BUY") & act.slug.str.startswith("btc-updown-5m-")].copy()
    act["st"] = act.slug.str.split("-").str[-1].astype(np.int64)
    act = act[(act.st >= A) & (act.st < B)]
    return act


def main(mode):
    act = fills()
    if mode == "stamps":
        st = pd.DataFrame({"stamp": (act.timestamp.astype(np.int64) - 4).unique()})
        st["split"] = "dev1031_0006"
        st["pri"] = -1
        st["ord"] = np.arange(len(st))
        q = pd.read_parquet(C / "a1_queue10.parquet")
        q = pd.concat([st, q]).drop_duplicates("stamp")
        q.to_parquet(C / "a1_queue10.parquet", index=False)
        print("queued", len(st))
        return
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    w = F._windows(A - 300, B + 300)
    w = w[(w.start_ts >= A) & (w.start_ts < B)]
    ptb = F._ptb(w)
    tk = F._tapes(w, pm, B + 600, local=False)
    ctx = set(F._txint(act.transactionHash.str.lower()))
    taker_w = tk.groupby("tx").wallet.first()
    act["txi"] = F._txint(act.transactionHash.str.lower())
    act["taker_wallet"] = act.txi.map(taker_w).astype(str)
    act = act[~act.taker_wallet.isin(set(CLU))]
    clean = tk[~tk.tx.isin(ctx)].copy()
    up = dict(zip(w.cid, w.up_token.astype(str)))
    clean["pup"] = np.where(clean.asset.astype(str) == clean.cid.astype(str).map(up), clean.price.astype(float), 1 - clean.price.astype(float))
    G = {k: (g.ts.to_numpy(), g.pup.to_numpy()) for k, g in clean.sort_values("ts", kind="stable").groupby("cid", observed=True)}
    act["is_up"] = (act.outcome == "Up").astype(int)
    mids = []
    for r in act.itertuples(index=False):
        g = G.get(r.conditionId)
        if g is None:
            mids.append(np.nan)
            continue
        j = np.searchsorted(g[0], int(r.timestamp) - 3, side="right") - 1
        mids.append(g[1][j] if j >= 0 and g[0][j] >= r.st - 60 else np.nan)
    act["mid_up"] = mids
    act["K"] = act.st.map(ptb)
    act["stamp"] = act.timestamp.astype(np.int64) - 4
    clv = cl_source.cl_values(act.stamp.unique(), fetch=False)
    act["cl"] = act.stamp.map(clv)
    h = act.dropna(subset=["cl", "K", "mid_up"]).copy()
    x = np.log(h.cl / h.K).to_numpy()
    m = h.mid_up.to_numpy()
    y = h.is_up.to_numpy() == 1
    D = (x > 0) != (m > 0.5)
    out = {"n_fills": int(len(act)), "n_scored": int(len(h)), "share_D": float(D.mean()), "n_D": int(D.sum()),
           "acc_D_bought_cl_favourite": float(np.mean(((x > 0) == y)[D])) if D.any() else None,
           "acc_A_bought_common_favourite": float(np.mean(((x > 0) == y)[~D])) if (~D).any() else None,
           "per_hour_D": {int(hh): {"n": int(g.sum()), "acc": float(np.mean(((x > 0) == y)[D & (h.timestamp.to_numpy() // 3600 == hh)])) if (D & (h.timestamp.to_numpy() // 3600 == hh)).any() else None}
                          for hh, g in pd.Series(D).groupby(h.timestamp.to_numpy() // 3600)},
           "per_wallet_D": {CLU.get(str(wl).lower(), str(wl)): float(np.mean(((x > 0) == y)[D & (h.w.to_numpy() == wl)])) if (D & (h.w.to_numpy() == wl)).any() else None for wl in h.w.unique()}}
    # Chainlink noise on this block from consecutive stamps that happen to be cached
    cc = pd.Series(cl_source._cache()).sort_index()
    cc = cc[(cc.index >= A) & (cc.index < B)]
    dd = cc.diff()
    consec = dd[(pd.Series(cc.index, index=cc.index).diff() == 1)]
    out["cl_1s_changes"] = {"n": int(len(consec)), "sd": float(consec.std()) if len(consec) > 10 else None,
                            "lag1_ac": float(consec.autocorr()) if len(consec) > 20 else None}
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_a1_dev1031_0006.json", "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
