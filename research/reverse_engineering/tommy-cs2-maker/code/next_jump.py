"""Do the wallet's taker orders anticipate the NEXT public price jump (round-end proxy)?  For each order: the first
public move of >= 4c within 15 s that starts after the order's signing time; its direction relative to the team
bought, and the time until it. Controls: random times in the same markets (+-15 min), and the maker orders.
Public prints only (wallet transactions excluded). Development data; BUILD and VALIDATE separately."""
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
    rng = np.random.default_rng(11)
    rows = []
    for cid, g in o.groupby("cid"):
        p = TAPES / f"{cid}_tkw.parquet"
        if not p.exists(): continue
        d = pd.read_parquet(p); d = d[(d.timestamp < H) & ~d.transactionHash.isin(bad)].sort_values("timestamp")
        if len(d) < 5: continue
        ts = d.timestamp.to_numpy(np.int64); p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        j = np.searchsorted(ts, ts - 15, side="left"); prev = np.where(j > 0, p0[np.maximum(j - 1, 0)], np.nan)
        mv = p0 - prev
        bigk = np.where(np.abs(mv) >= 0.04)[0]
        if len(bigk) == 0: continue
        bt, bd = ts[bigk], np.sign(mv[bigk])
        for r in g.itertuples():
            for ctrl in (False, True):
                t = r.sign_ts if not ctrl else r.sign_ts + rng.uniform(-900, 900)
                k = np.searchsorted(bt, t + 0.0, side="right")
                # skip a jump already in progress: require the jump's window start (bt-15) after t - 5
                while k < len(bt) and bt[k] - 15 < t - 5: k += 1
                if k >= len(bt): continue
                dirn = bd[k] if r.oi == 0 else -bd[k]
                rows.append({"role": r.role, "ctrl": ctrl, "gs": r.gs_ts, "dt": bt[k] - t, "fav": dirn > 0, "shares": r.shares})
    x = pd.DataFrame(rows)
    res = {}
    for (role, ctrl, sp), s in x.groupby(["role", "ctrl", x.gs >= SPLIT]):
        k = f"{role}_{'ctrl' if ctrl else 'real'}_{'VALIDATE' if sp else 'BUILD'}"
        res[k] = {"n": len(s), "next_jump_in_favour": round(float(s.fav.mean()), 3), "dt_med": round(float(s.dt.median()), 1),
                  "fav_if_dt_lt_60": round(float(s.loc[s.dt < 60, "fav"].mean()), 3), "n_dt_lt_60": int((s.dt < 60).sum())}
    json.dump(res, open(RES / "results/next_jump.json", "w"), indent=1)
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
