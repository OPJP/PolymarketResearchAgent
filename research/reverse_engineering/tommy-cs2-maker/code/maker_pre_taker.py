"""Are its maker fills informed when they precede its own taker orders?  Maker orders signed within 30 s before a
taker order on the same team (same market) vs all other maker orders: next >= 4c public jump in favour (next_jump
logic). Own-state split (descriptive only: it conditions on the wallet's later action, not a point-in-time feature)."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RES, WALLET, H, TAPES, SPLIT  # noqa: E402

def main():
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    bad = set(cd.loc[cd.maker == WALLET, "tx"])
    o = pd.read_parquet(OUT / "orders.parquet")
    rows = []
    for cid, g in o.groupby("cid"):
        p = TAPES / f"{cid}_tkw.parquet"
        if not p.exists(): continue
        d = pd.read_parquet(p); d = d[(d.timestamp < H) & ~d.transactionHash.isin(bad)].sort_values("timestamp")
        if len(d) < 5: continue
        ts = d.timestamp.to_numpy(np.int64); p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        j = np.searchsorted(ts, ts - 15, side="left"); prev = np.where(j > 0, p0[np.maximum(j - 1, 0)], np.nan)
        mv = p0 - prev; bigk = np.where(np.abs(mv) >= 0.04)[0]
        if len(bigk) == 0: continue
        bt, bd = ts[bigk], np.sign(mv[bigk])
        tk = g[g.role == "taker"]
        for r in g[g.role == "maker"].itertuples():
            k = np.searchsorted(bt, r.sign_ts, side="right")
            while k < len(bt) and bt[k] - 15 < r.sign_ts - 5: k += 1
            if k >= len(bt): continue
            fav = (bd[k] if r.oi == 0 else -bd[k]) > 0
            dt = tk.sign_ts.to_numpy() - r.sign_ts
            pre_same = bool(np.any((dt > 0) & (dt <= 30) & (tk.oi.to_numpy() == r.oi)))
            pre_opp = bool(np.any((dt > 0) & (dt <= 30) & (tk.oi.to_numpy() != r.oi)))
            rows.append({"gs": r.gs_ts, "fav": fav, "pre_same": pre_same, "pre_opp": pre_opp, "price": r.price, "filled": r.filled})
    x = pd.DataFrame(rows)
    res = {}
    for sp, s in (("BUILD", x[x.gs < SPLIT]), ("VALIDATE", x[x.gs >= SPLIT])):
        res[sp] = {"pre_same_taker": {"n": int(s.pre_same.sum()), "fav": round(float(s.loc[s.pre_same, "fav"].mean()), 3)},
                   "pre_opp_taker": {"n": int(s.pre_opp.sum()), "fav": round(float(s.loc[s.pre_opp, "fav"].mean()), 3)},
                   "other": {"n": int((~s.pre_same & ~s.pre_opp).sum()), "fav": round(float(s.loc[~s.pre_same & ~s.pre_opp, "fav"].mean()), 3)}}
    json.dump(res, open(RES / "results/maker_pre_taker.json", "w"), indent=1)
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
