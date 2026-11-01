"""E2 / E7: shape of the out-of-fold BUILD residual of the FULL presence model (GroupKFold by game).

Misses = positive cells (RN1 filled) in the lowest OOF-score third of positives; false alarms = negative cells in
the top decile of OOF scores. Characterized by market type, family, time in game, hour of day, price level.
E7: residual_clustering of the misses' RN1 fill times (seconds, from the tape), market label = game (event), so
sibling markets of one game do not count as synchrony; only misses > 30 min after the game start.
Writes results/e2_residuals_iter1.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import indicators as ind  # noqa: E402
from common import BUILD, C, R, W  # noqa: E402


def main():
    b = pd.read_parquet(C / "oof_build_iter1.parquet")
    pos = b[b["y"] == 1]
    thr_miss = pos["oof"].quantile(1 / 3)
    miss = pos[pos["oof"] <= thr_miss]
    neg = b[b["y"] == 0]
    thr_fa = neg["oof"].quantile(0.9)
    fa = neg[neg["oof"] >= thr_fa]
    out = {"n_cells": int(len(b)), "n_pos": int(len(pos)), "miss_threshold": float(thr_miss), "n_miss": int(len(miss)),
           "fa_threshold": float(thr_fa), "n_fa": int(len(fa))}

    def prof(df, col, bins=None):
        x = pd.cut(df[col], bins) if bins is not None else df[col]
        allx = pd.cut(b[col], bins) if bins is not None else b[col]
        posx = pd.cut(pos[col], bins) if bins is not None else pos[col]
        return {str(k): {"share_of_set": round(float(v), 3), "share_of_pos": round(float(posx.value_counts(normalize=True).get(k, 0)), 3),
                         "share_of_cells": round(float(allx.value_counts(normalize=True).get(k, 0)), 3)}
                for k, v in x.value_counts(normalize=True).sort_index().items()}
    b["hour"] = (b["t"] // 3600) % 24
    for df, name in ((miss, "miss"), (fa, "false_alarm")):
        df = df.assign(hour=(df["t"] // 3600) % 24)
        out[name] = {"smt": prof(df, "smt"), "fam": prof(df, "fam"),
                     "t_rel": prof(df, "t_rel", [-121, 0, 15, 45, 90, 150, 301]),
                     "p_last": prof(df, "p_last", [0, 0.1, 0.3, 0.7, 0.9, 1.0]),
                     "hour": {str(k): round(float(v), 3) for k, v in df["hour"].value_counts(normalize=True).sort_index().items()}}
    pos = pos.assign(hour=(pos["t"] // 3600) % 24)
    out["pos_hour"] = {str(k): round(float(v), 3) for k, v in pos["hour"].value_counts(normalize=True).sort_index().items()}
    # E7: RN1 fill seconds of the missed cells, > 30 min after start
    smp = json.load(open(C / f"tape_sample_{BUILD[0]}_{BUILD[1]}.json"))["sample"]
    rows = []
    mk = set(zip(miss["cid"], miss["t"]))
    for slug in smp:
        f = C / "tapes" / f"{slug}.parquet"
        if not f.exists():
            continue
        tp = pd.read_parquet(f, columns=["cid", "ts", "wallet", "role"])
        r = tp[(tp["wallet"] == W) & (tp["role"] == "maker")]
        rows.append(r.assign(event=slug))
    rf = pd.concat(rows)
    # map each fill second to its bin start (bins are aligned to gst - 2h per market, as in presence.py)
    gst = b.groupby("cid")["gst"].first()
    rf = rf[rf["cid"].isin(gst.index)].copy()
    rf["a"] = rf["cid"].map(gst) - 7200
    rf["t"] = rf["a"] + ((rf["ts"] - rf["a"]) // 60) * 60
    rf["key"] = list(zip(rf["cid"], rf["t"]))
    rf["is_miss"] = rf["key"].isin(mk)
    rf["t_rel"] = (rf["ts"] - rf["cid"].map(gst)) / 60.0
    mm = rf[rf["is_miss"] & (rf["t_rel"] > 30)].drop_duplicates(["cid", "ts"])
    out["e7_n_miss_fills"] = int(len(mm))
    if len(mm) > 10 and mm["event"].nunique() > 2:
        rc = ind.residual_clustering(mm["ts"].to_numpy(float), mm["event"].to_numpy(), delta_s=2.0, n_null=1000)
        out["e7_residual_clustering"] = {k: rc[k] for k in ("near_pairs", "band_pairs", "expected_near", "ratio", "p", "n", "n_markets", "null")}
        out["e7_top_clusters"] = rc["top_clusters"][:8]
        allf = rf[rf["t_rel"] > 30].drop_duplicates(["cid", "ts"])
        rc2 = ind.residual_clustering(allf["ts"].to_numpy(float), allf["event"].to_numpy(), delta_s=2.0, n_null=1000)
        out["e7_all_fills_reference"] = {k: rc2[k] for k in ("near_pairs", "expected_near", "ratio", "p", "n", "n_markets")}
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(R / "results" / "e2_residuals_iter1.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
