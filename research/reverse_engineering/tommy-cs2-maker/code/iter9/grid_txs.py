"""Iteration 9, X120 / X128 (information P3, assumptions P2): the public taker transactions of GRID CS2 events of
16-22 Oct around group G's prints (+-3 s of any group-G member print), for the 25 GRID events with the most group-G
prints. Group G = the BUILD fixed-lag co-signers of P4e excluded from group P by their GRID share (selection_groupP.json).
Output: .cache/re/tommy-cs2-maker/grid_txs.parquet (tx, bts) for fetch_calldata.py"""
import glob, json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
r = json.load(open(ROOT / "research/reverse_engineering/tommy-cs2-maker/results/selection_groupP.json"))
G = {w for w, v in r["candidates"].items() if not v["member"] and (v["build_grid_share"] or 0) >= 0.2}
u = pd.read_parquet(OUT / "universe.parquet")
u = u[u.smt.isin(["moneyline", "child_moneyline"])]
em = pd.read_parquet(OUT / "events_meta.parquet")[["event_slug", "grid_series_id"]]
u = u.merge(em, on="event_slug", how="left")
grid_cids = dict(zip(u.loc[u.grid_series_id.notna(), "cid"], u.loc[u.grid_series_id.notna(), "event_slug"]))
rows = []
for f in glob.glob(str(OUT / "tapes" / "*_tkw.parquet")):
    cid = Path(f).name.split("_")[0]
    if cid not in grid_cids:
        continue
    d = pd.read_parquet(f, columns=["proxyWallet", "timestamp", "transactionHash"])
    d["w"] = d.proxyWallet.str.lower()
    d["e"] = grid_cids[cid]
    d["cid"] = cid
    rows.append(d)
P = pd.concat(rows, ignore_index=True)
P = P[(P.timestamp >= 1792108800) & (P.timestamp < 1792713600)]
gcount = P[P.w.isin(G)].groupby("e").size().sort_values(ascending=False)
top = list(gcount.index[:25])
Q = P[P.e.isin(top)].copy()
keep = []
for cid, g in Q.groupby("cid"):
    gt = np.sort(g.loc[g.w.isin(G), "timestamp"].to_numpy(float))
    if len(gt) == 0:
        continue
    t = g.timestamp.to_numpy(float)
    k = np.searchsorted(gt, t)
    near = np.zeros(len(t), bool)
    for q in (k - 1, k):
        ok = (q >= 0) & (q < len(gt))
        near[ok] |= np.abs(gt[np.clip(q, 0, len(gt) - 1)][ok] - t[ok]) <= 3
    keep.append(g[near])
K = pd.concat(keep).drop_duplicates("transactionHash")
pd.DataFrame({"tx": K.transactionHash, "bts": K.timestamp.astype(float)}).to_parquet(OUT / "grid_txs.parquet", index=False)
print("group G", len(G), "grid events", P.e.nunique(), "top25 group-G prints", int(gcount.iloc[:25].sum()), "txs", len(K))
json.dump({"group_G": sorted(G), "events": top}, open(OUT / "grid_txs_meta.json", "w"), indent=1)
