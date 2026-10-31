"""Iteration 5: the Polygon block clock. Fills can only happen in blocks, and Polygon produced a block every 1.5 s, so
one second in three has no block and can never hold a fill. Those structural zeros are free AUC for any model that can
infer the block phase (the market-activity baseline does it through the timing of other traders' prints). This script
fits the chain clock per UTC hour from (block number, block timestamp) pairs (chain data; the cluster's fills are used
only as a source of such pairs): ts = floor(phi + 1.5 * (block - b_ref)); an hour is LOCKED when one phi explains >= 98%
of its pairs. Presence AUC is then recomputed over block seconds only (every second of an unlocked hour is kept).
Writes results_block_bins_iter5.json."""
import os, sys, json
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
V0, V1 = 1792108800, 1792713600


def block_seconds(f):
    """dict hour -> (locked, set of block seconds) from (block, ts) pairs."""
    b = f.drop_duplicates("block")[["block", "ts"]].sort_values("block")
    out = {}
    for h, g in b.groupby(b.ts // 3600):
        bl = g.block.to_numpy(np.int64); ts = g.ts.to_numpy(np.int64)
        bref = bl[0]; x = 1.5 * (bl - bref)
        best, bphi = -1, None
        for phi in np.arange(ts[0] - 1.5, ts[0] + 1.5, 0.01):
            k = int((np.floor(phi + x) == ts).sum())
            if k > best:
                best, bphi = k, phi
        share = best / len(bl)
        locked = share >= 0.98 and len(bl) >= 50
        secs = set()
        if locked:
            allb = np.arange(bl.min() - 5, bl.max() + 6)
            secs = set(np.floor(bphi + 1.5 * (allb - bref)).astype(np.int64).tolist())
        out[int(h)] = (locked, secs, round(share, 4), len(bl))
    return out


if __name__ == "__main__":
    f = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "ts"])
    bs = block_seconds(f[(f.ts >= V0 - 3600) & (f.ts < V1)])
    a = pd.read_parquet(f"{C}/val_pred_it4b.parquet", columns=["start_ts", "rel"])
    b = pd.read_parquet(f"{C}/val_decision_presence.parquet")
    t = (a.start_ts.to_numpy() + a.rel.to_numpy()).astype(np.int64)
    hrs = t // 3600
    keep = np.ones(len(t), bool)
    for h in np.unique(hrs):
        lk, secs, sh, n = bs.get(int(h), (False, set(), 0, 0))
        if lk:
            idx = np.where(hrs == h)[0]
            keep[idx] = np.isin(t[idx], np.fromiter(secs, np.int64))
    y = b.y0.to_numpy()
    locked_hours = sum(1 for v in bs.values() if v[0]); n_hours = len(bs)
    res = {"hours": n_hours, "locked_hours": locked_hours, "share_cells_kept": round(float(keep.mean()), 4),
           "positives_dropped_share": round(float(1 - y[keep].sum() / y.sum()), 4),
           "base_rate_all": round(float(y.mean()), 4), "base_rate_block_seconds": round(float(y[keep].mean()), 4)}
    for nm, col in (("full", "f0"), ("pure", "b0"), ("full_k1", "f1"), ("pure_k1", "b1")):
        yy = b.y0.to_numpy() if not nm.endswith("k1") else b.y1.to_numpy()
        res[f"auc_{nm}_all"] = round(float(roc_auc_score(yy, b[col])), 4)
        # for k1 the label is the fill at s+1: keep the cells whose s+1 is a block second
        kk = keep if not nm.endswith("k1") else np.r_[keep[1:], False]
        res[f"auc_{nm}_block_seconds"] = round(float(roc_auc_score(yy[kk], b[col].to_numpy()[kk])), 4)
    res["gain_block_seconds"] = round(res["auc_full_block_seconds"] - res["auc_pure_block_seconds"], 4)
    res["gain_block_seconds_k1"] = round(res["auc_full_k1_block_seconds"] - res["auc_pure_k1_block_seconds"], 4)
    np.save(f"{C}/val_block_keep.npy", keep)
    json.dump(res, open(f"{R}/results_block_bins_iter5.json", "w"), indent=1)
    print(json.dumps(res, indent=1))
