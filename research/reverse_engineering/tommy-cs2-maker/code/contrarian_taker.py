"""Public-data contrarian taker rule (candidate for the wallet's informed taker component).
Trigger: team X's public price (last print) fell by >= D within the last W s (in-play). Entry: last public print of X
at trigger + LAT s (+ SLIP). Settlement edge = 1{X wins} - entry. One trigger per market per 60 s.
Compare with the wallet's own taker orders and test the overlap (does the wallet take within 10 s of a trigger?).
Grid on BUILD only; VALIDATE reported for the BUILD-best parameters. Development data."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RES, WALLET, H, TAPES, SPLIT  # noqa: E402

def main():
    m = json.load(open(OUT / "markets_dev.json"))
    win = {}
    for cid, x in m.items():
        op = x.get("outcomePrices"); op = json.loads(op) if isinstance(op, str) else op
        v = [float(a) for a in op]; win[cid] = int(np.argmax(v)) if max(v) > 0.9 else -1
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    bad = set(cd.loc[cd.maker == WALLET, "tx"])
    o = pd.read_parquet(OUT / "orders.parquet")
    tk = o[o.role == "taker"]
    gs_of = o.groupby("cid").gs_ts.first().to_dict()
    tapes = {}
    for cid in gs_of:
        p = TAPES / f"{cid}_tkw.parquet"
        if not p.exists(): continue
        d = pd.read_parquet(p); d = d[(d.timestamp < H) & ~d.transactionHash.isin(bad)].sort_values("timestamp")
        if len(d) < 10: continue
        p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        tapes[cid] = (d.timestamp.to_numpy(np.int64), p0)
    def run(D, Wn, LAT=2, SLIP=0.01, lo=0.1, hi=0.9):
        rows = []
        for cid, (ts, p0) in tapes.items():
            gs = gs_of[cid]; wv = win.get(cid, -1)
            if wv < 0: continue
            # evaluate at each print time (trigger checks happen when a print arrives)
            j = np.searchsorted(ts, ts - Wn, side="left")
            prev = np.where(j > 0, p0[np.maximum(j - 1, 0)], np.nan)
            last_t = -1e18
            for k in range(len(ts)):
                if ts[k] < gs or ts[k] - last_t < 60 or not np.isfinite(prev[k]): continue
                for team in (0, 1):
                    now_p = p0[k] if team == 0 else 1 - p0[k]
                    pr = prev[k] if team == 0 else 1 - prev[k]
                    if pr - now_p >= D and lo <= now_p <= hi:
                        i2 = np.searchsorted(ts, ts[k] + LAT, side="right")
                        e = (p0[i2 - 1] if team == 0 else 1 - p0[i2 - 1]) + SLIP
                        rows.append({"cid": cid, "t": ts[k], "team": team, "entry": e, "edge": float(wv == team) - e, "gs": gs})
                        last_t = ts[k]
                        break
        return pd.DataFrame(rows)
    res = {"wallet_taker_edge_pct": {}}
    for sp, s in (("BUILD", tk[tk.gs_ts < SPLIT]), ("VALIDATE", tk[tk.gs_ts >= SPLIT])):
        s = s.assign(win=s.cid.map(win)); s = s[s.win >= 0]
        res["wallet_taker_edge_pct"][sp] = round(float(((s.win == s.oi) - s.price).mul(s.filled).sum() / (s.price * s.filled).sum() * 100), 2)
    grid = []
    for D in (0.03, 0.05, 0.08, 0.12):
        for Wn in (10, 30, 60):
            r = run(D, Wn)
            if len(r) == 0: continue
            b = r[r.gs < SPLIT]
            grid.append({"D": D, "W": Wn, "n_build": len(b), "edge_build_pct": round(float(b.edge.sum() / b.entry.sum() * 100), 2)})
    g = pd.DataFrame(grid).sort_values("edge_build_pct", ascending=False)
    res["grid_build"] = g.to_dict("records")
    best = g.iloc[0]
    r = run(best.D, int(best.W))
    v = r[r.gs >= SPLIT]
    res["best"] = {"D": float(best.D), "W": int(best.W), "val_n": len(v), "val_edge_pct": round(float(v.edge.sum() / v.entry.sum() * 100), 2),
                   "val_mean_edge_c": round(float(v.edge.mean() * 100), 2)}
    # overlap: share of wallet taker orders within 10 s after a trigger of the same team (best params), VALIDATE
    tv = tk[tk.gs_ts >= SPLIT]
    hits = 0
    for rr in tv.itertuples():
        q = v[(v.cid == rr.cid) & (v.team == rr.oi)]
        if len(q) and ((rr.sign_ts - q.t >= -2) & (rr.sign_ts - q.t <= 10)).any(): hits += 1
    res["best"]["wallet_taker_recall_10s"] = round(hits / max(len(tv), 1), 3)
    res["best"]["trigger_share_followed_by_wallet"] = None
    json.dump(res, open(RES / "results/contrarian_taker.json", "w"), indent=1)
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
