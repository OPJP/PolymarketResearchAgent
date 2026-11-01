"""Iteration 12, PR12-A scoring (X124): the full-machine replay vs the cluster per window. STUDY case by case,
VALIDATE aggregate only (per wallet, per half, locked / residual parts, 2-h block bootstrap of the gain over R7's
one-sided replay = main posture, no pairing, L = 2).
    python code12/replay_machine_score.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
SPLIT_V, HALF_V = 1793059200, 1793232000
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return [None, None]
    return [round(float(np.corrcoef(a, b)[0, 1]), 4), round(float(pd.Series(a).corr(pd.Series(b), method="spearman")), 4)]


def cluster_windows(roles=("maker",)):
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet").set_index("cid")
    F = pd.read_parquet(C / "exam" / "fills_holdout.parquet")
    F = F[F.cid.isin(W.index) & (F.side == "BUY") & F.role.isin(roles)].copy()
    up = np.array([str(t) == str(W.at[c, "up_token"]) for t, c in zip(F.token_id, F.cid)])
    payu = W.loc[F.cid, "up_payout"].to_numpy().astype(float)
    F["U"] = np.where(up, F.shares, 0.0)
    F["D"] = np.where(up, 0.0, F.shares)
    F["cu"] = np.where(up, F.shares * F.price, 0.0)
    F["cd"] = np.where(up, 0.0, F.shares * F.price)
    F["payu"] = payu
    F["w"] = F.wallet.str.lower().map(CLUSTER)

    def agg(g):
        U, D, cu, cd, pu = g.U.sum(), g.D.sum(), g.cu.sum(), g.cd.sum(), g.payu.iloc[0]
        pnl = U * pu + D * (1 - pu) - cu - cd
        P = min(U, D)
        locked = P * (1 - (cu / U if U > 0 else 0) - (cd / D if D > 0 else 0)) if P > 0 else 0.0
        return pd.Series({"pnl": pnl, "locked": locked, "resid": pnl - locked})

    pooled = F.groupby("cid").apply(agg)
    per_w = {w: g.groupby("cid").apply(agg) for w, g in F.groupby("w")}
    return pooled, per_w


def boot_gain(st, a, b, cl, n=2000, seed=12):
    """2-h block bootstrap of mean(P, S)(a, cl) - mean(P, S)(b, cl)."""
    blk = (st // 7200).astype(int)
    ub = np.unique(blk)
    rng = np.random.default_rng(seed)
    idx = {k: np.nonzero(blk == k)[0] for k in ub}
    g = []
    for _ in range(n):
        s = rng.choice(ub, size=len(ub), replace=True)
        ii = np.concatenate([idx[k] for k in s])
        ca, cb = corr(a[ii], cl[ii]), corr(b[ii], cl[ii])
        if None in ca or None in cb:
            continue
        g.append((ca[0] + ca[1]) / 2 - (cb[0] + cb[1]) / 2)
    g = np.array(g)
    return [round(float(np.percentile(g, 2.5)), 4), round(float(np.percentile(g, 97.5)), 4), round(float((g <= 0).mean()), 4)]


def main():
    import sys
    TAG = sys.argv[1] if len(sys.argv) > 1 else ""
    R = pd.read_parquet(C / "it12" / ("machine_windows_touch.parquet" if TAG == "touch" else "machine_windows.parquet"))
    pooled, per_w = cluster_windows()
    pooled_all, _ = cluster_windows(("maker", "taker"))
    sts = R.drop_duplicates("cid").set_index("cid").st
    res = {"n_windows_cluster": int(len(pooled))}
    cfgs = sorted(set(zip(R.L, R.main, R.pair)))
    table = {}
    for L, m, p in cfgs:
        g = R[(R.L == L) & (R.main == m) & (R.pair == p)].set_index("cid")
        rec = {}
        for sp, lo, hi in (("study", 0, SPLIT_V), ("validate", SPLIT_V, 2 ** 40), ("validate_h1", SPLIT_V, HALF_V), ("validate_h2", HALF_V, 2 ** 40)):
            ids = [c for c in pooled.index if c in sts.index and lo <= sts[c] < hi]
            cl = pooled.loc[ids]
            rp = g.reindex(ids)[["pnl", "locked", "resid"]].fillna(0.0)
            rec[sp] = {"pnl": corr(rp.pnl, cl.pnl), "locked": corr(rp.locked, cl.locked), "resid": corr(rp.resid, cl.resid),
                       "pnl_vs_cluster_incl_taker": corr(rp.pnl, pooled_all.reindex(ids).pnl.fillna(0.0)),
                       "replay_pnl": round(float(rp.pnl.sum()), 1), "replay_locked": round(float(rp.locked.sum()), 1),
                       "replay_return": round(float(g.reindex(ids).pnl.sum() / max(g.reindex(ids).eval("cu + cd").sum(), 1e-9)), 4),
                       "cluster_pnl": round(float(cl.pnl.sum()), 1), "cluster_locked": round(float(cl.locked.sum()), 1),
                       "windows": len(ids)}
            if sp == "validate":
                for w, cw in per_w.items():
                    idw = [c for c in cw.index if c in sts.index and lo <= sts[c] < hi]
                    rec[sp][w] = corr(g.reindex(idw).pnl.fillna(0.0), cw.loc[idw].pnl)
        table[f"L{L}_{m}_pair{p}"] = rec
    res["configs"] = table
    # pre-registered choice on STUDY among public L = 2 candidates
    cand = [k for k in table if k.startswith("L2_") and ("posture" in k or "held" in k)]
    score = {k: float(np.mean(table[k]["study"]["pnl"])) for k in cand}
    best = max(score, key=score.get)
    res["study_scores"] = {k: round(v, 4) for k, v in score.items()}
    res["chosen"] = best
    ids = [c for c in pooled.index if c in sts.index and sts[c] >= SPLIT_V]
    a = R[(R.L == 2) & (R.main == best.split("_")[1]) & (R.pair == int(best[-1]))].set_index("cid").reindex(ids).pnl.fillna(0.0).to_numpy()
    b = R[(R.L == 2) & (R.main == "posture") & (R.pair == 0)].set_index("cid").reindex(ids).pnl.fillna(0.0).to_numpy()
    res["validate_gain_boot_vs_R7"] = boot_gain(sts.loc[ids].to_numpy(), a, b, pooled.loc[ids].pnl.to_numpy())
    out = HERE.parent / "results" / ("iter12_replay_machine_touch.json" if TAG == "touch" else "iter12_replay_machine.json")
    out.write_text(json.dumps(res, indent=1))
    for k, v in table.items():
        print(k, "STUDY", v["study"]["pnl"], v["study"]["locked"], "VAL", v["validate"]["pnl"], "lock", v["validate"]["locked"],
              "res", v["validate"]["resid"], "ret", v["validate"]["replay_return"], "rp_lock", v["validate"]["replay_locked"])
    print("chosen", best, res["study_scores"], "boot", res["validate_gain_boot_vs_R7"])


if __name__ == "__main__":
    main()
