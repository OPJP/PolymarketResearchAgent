"""Block bootstrap (by event) of the taker 'next jump in favour' gain over random-time controls (next_jump.py logic),
BUILD and VALIDATE separately; one-sided p-value with 4000 draws."""
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
    o = o[o.role == "taker"]
    rng = np.random.default_rng(5)
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
        def nxt(t, oi):
            k = np.searchsorted(bt, t, side="right")
            while k < len(bt) and bt[k] - 15 < t - 5: k += 1
            if k >= len(bt): return np.nan
            return float((bd[k] if oi == 0 else -bd[k]) > 0)
        for r in g.itertuples():
            real = nxt(r.sign_ts, r.oi)
            ctrl = np.nanmean([nxt(r.sign_ts + rng.uniform(-900, 900), r.oi) for _ in range(5)])
            rows.append({"event": r.event, "gs": r.gs_ts, "real": real, "ctrl": ctrl})
    x = pd.DataFrame(rows).dropna()
    res = {}
    for sp, s in (("BUILD", x[x.gs < SPLIT]), ("VALIDATE", x[x.gs >= SPLIT])):
        ev = s.groupby("event").agg(r=("real", "sum"), c=("ctrl", "sum"), n=("real", "size"))
        gain = (ev.r.sum() - ev.c.sum()) / ev.n.sum()
        idx = np.arange(len(ev)); boots = []
        for _ in range(4000):
            b = ev.iloc[rng.choice(idx, len(idx))]
            boots.append((b.r.sum() - b.c.sum()) / b.n.sum())
        boots = np.array(boots)
        res[sp] = {"n": int(len(s)), "events": int(len(ev)), "real": round(float(s.real.mean()), 3), "ctrl": round(float(s.ctrl.mean()), 3),
                   "gain": round(float(gain), 3), "ci95": [round(float(np.quantile(boots, .025)), 3), round(float(np.quantile(boots, .975)), 3)],
                   "p_one_sided": float((boots <= 0).mean())}
    json.dump(res, open(RES / "results/next_jump_boot.json", "w"), indent=1)
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
