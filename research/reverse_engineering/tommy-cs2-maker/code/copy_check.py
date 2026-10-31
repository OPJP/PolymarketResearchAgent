"""C2 strong form / confound check for the taker 'next jump' result: are the public takers buying the same team in the
0-60 s after the wallet's taker orders a concentrated set of followers (copy traders), compared with takers buying in
random 60-s windows of the same markets? Uses the windowed taker tapes (proxyWallet = taker). Development data."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RES, WALLET, H, TAPES, SPLIT  # noqa: E402

def main():
    o = pd.read_parquet(OUT / "orders.parquet"); tk = o[o.role == "taker"]
    rng = np.random.default_rng(4)
    after, ctrl = [], []
    for cid, g in tk.groupby("cid"):
        p = TAPES / f"{cid}_tkw.parquet"
        if not p.exists(): continue
        d = pd.read_parquet(p); d = d[(d.timestamp < H) & (d.proxyWallet != WALLET)].sort_values("timestamp")
        if len(d) == 0: continue
        ts = d.timestamp.to_numpy(np.int64); oi = d.outcomeIndex.astype(int).to_numpy(); wal = d.proxyWallet.to_numpy()
        usd = (d.price.astype(float) * d["size"].astype(float)).to_numpy()
        for t, team in zip(g.sign_ts, g.oi):
            for lst, t0 in ((after, t), (ctrl, t + rng.uniform(-900, 900))):
                a, b = np.searchsorted(ts, t0 + 3), np.searchsorted(ts, t0 + 60)
                sel = slice(a, b)
                same = oi[sel] == team
                for w_, u_, s_ in zip(wal[sel], usd[sel], same):
                    lst.append((w_, u_, bool(s_)))
    A = pd.DataFrame(after, columns=["w", "usd", "same"]); Cc = pd.DataFrame(ctrl, columns=["w", "usd", "same"])
    res = {"after_prints": len(A), "ctrl_prints": len(Cc),
           "after_same_team_usd_share": round(float(A.loc[A.same, "usd"].sum() / max(A.usd.sum(), 1)), 3),
           "ctrl_same_team_usd_share": round(float(Cc.loc[Cc.same, "usd"].sum() / max(Cc.usd.sum(), 1)), 3)}
    sa = A[A.same].groupby("w").usd.sum().sort_values(ascending=False)
    sc = Cc[Cc.same].groupby("w").usd.sum()
    res["after_top10_same_team_share"] = round(float(sa.head(10).sum() / max(sa.sum(), 1)), 3)
    res["ctrl_top10_same_team_share"] = round(float(sc.sort_values(ascending=False).head(10).sum() / max(sc.sum(), 1)), 3)
    top = sa.head(10)
    res["top_followers"] = {k[:10]: {"after_usd": round(float(v), 0), "ctrl_usd": round(float(sc.get(k, 0.0)), 0)} for k, v in top.items()}
    json.dump(res, open(RES / "results/copy_check.json", "w"), indent=1)
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
