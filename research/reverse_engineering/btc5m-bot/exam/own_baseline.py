"""Examiner r1: the EXAMINER'S OWN market-activity baseline for block-second presence, fitted with the RE's model class and tuning
budget on the RE's BUILD data only (development, read-only from .cache/re/btc5m-bot):
  - BUILD = the 7 cell days 10-09..10-15 (the days model_it5_blk_full / _pure were trained on), block seconds only
    (block_bins.block_seconds over the BUILD fills, block_presence.keep_mask), positives + 30% negatives (weight 1/0.3, seed 0),
    LightGBM train3.PARAMS, 200 rounds (identical to block_presence.py).
  - Feature sets (no reference feed, no own state, no wallet print):
      PURE  = decision_presence.MKT_PURE (refit, sanity check of the procedure)
      AUG   = MKT_PURE + blkaug9.AUG (the RE's iteration-9 'stronger' baseline features, refit)
      MKTX  = AUG + lagged per-second print counts / flows of both outcomes, the other outcome's print age, total activity,
              1-2 s touch changes of both outcomes (examiner's additions).
Saves models to .cache/exam/btc5m-bot/models/ and a json of in-sample sizes."""
import os, sys, json, time
ROOT = os.getcwd(); CODE = f"{ROOT}/research/reverse_engineering/btc5m-bot/code"; sys.path.insert(0, CODE)
sys.argv = [sys.argv[0], "four"] + sys.argv[1:]
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
import train3 as t3
import blkaug9 as ba
from block_bins import block_seconds
from block_presence import keep_mask
from decision_presence import MKT_PURE

C = f"{ROOT}/.cache/re/btc5m-bot"; EX = f"{ROOT}/.cache/exam/btc5m-bot"; OUT = f"{EX}/models"; os.makedirs(OUT, exist_ok=True)
V0 = 1792108800
BUILD_DAYS = [1791504000 + 86400 * k for k in range(7)]
OTH = ba.OTH
EXTRA_O = ["age_last", "spread", "m_last"]


def mktx(c: pd.DataFrame) -> pd.DataFrame:
    """c: cells of whole windows (wi, is_up, rel, MKT_PURE + OTH columns). Returns c with AUG + MKTX columns."""
    c = ba.add_aug(c)  # sorts by wi, is_up, rel; adds dm1, dm2, O_*, ask_sum
    o = c[["wi", "rel", "is_up"] + EXTRA_O].copy(); o["is_up"] = ~o.is_up.astype(bool)
    o = o.rename(columns={k: "OX_" + k for k in EXTRA_O})
    c = c.merge(o, on=["wi", "rel", "is_up"], how="left")
    c = c.sort_values(["wi", "is_up", "rel"]).reset_index(drop=True)
    g = c.groupby(["wi", "is_up"], sort=False)
    for k in (1, 2, 3):
        c[f"n1_l{k}"] = g.n1.shift(k).astype(np.float32); c[f"On1_l{k}"] = g.O_n1.shift(k).astype(np.float32)
    for k in (1, 2):
        c[f"fl1_l{k}"] = g.flow1.shift(k).astype(np.float32)
        c[f"dask{k}"] = (c.ask_o - g.ask_o.shift(k)).astype(np.float32); c[f"Odask{k}"] = (c.O_ask_o - g.O_ask_o.shift(k)).astype(np.float32)
        c[f"dbid{k}"] = (c.bid_o - g.bid_o.shift(k)).astype(np.float32)
    c["n2_tot"] = (c.n2 + c.O_n2).astype(np.float32); c["n5_tot"] = (c.n5 + c.O_n5).astype(np.float32)
    c["vol30_tot"] = (c.vol30 + c.O_vol30).astype(np.float32)
    c["age_min"] = np.fmin(c.age_last, c.OX_age_last).astype(np.float32)
    return c


AUG = MKT_PURE + ba.AUG
MKTX = AUG + ["OX_age_last", "OX_spread", "n1_l1", "n1_l2", "n1_l3", "On1_l1", "On1_l2", "On1_l3", "fl1_l1", "fl1_l2", "dask1", "dask2",
              "Odask1", "Odask2", "dbid1", "dbid2", "n2_tot", "n5_tot", "vol30_tot", "age_min"]
NEED = sorted(set(MKT_PURE) | set(OTH) | set(EXTRA_O) | {"wi", "is_up", "rel", "start_ts", "cid", "y", "yGF", "yXM", "yDS", "ask_o", "bid_o", "n1", "flow1", "m_last"})

if __name__ == "__main__":
    t0 = time.time(); rng = np.random.default_rng(0)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "ts"])
    bs = block_seconds(fl[fl.ts < V0])
    parts = []; info = {"days": [], "rows": 0}
    for d0 in BUILD_DAYS:
        c = pd.read_parquet(f"{C}/cells/{d0}.parquet", columns=[k for k in NEED if k != "cid"] + ["cid"])
        c = mktx(c)
        t = (c.start_ts.to_numpy() + c.rel.to_numpy()).astype(np.int64)
        k = keep_mask(t, bs)
        sel = k & ((c.y.to_numpy() == 1) | (rng.random(len(c)) < 0.3))
        sub = c.loc[sel, sorted(set(MKTX)) + ["y"]].copy(); sub["w"] = np.where(sub.y == 1, 1.0, 1 / 0.3)
        parts.append(sub); info["days"].append({"d0": d0, "cells": int(len(c)), "kept": float(k.mean()), "sampled": int(sel.sum())})
        del c, sub; print("build", d0, round(time.time() - t0), flush=True)
    B = pd.concat(parts, ignore_index=True); del parts
    info["rows"] = int(len(B)); info["positives"] = int(B.y.sum())
    for nm, cols in (("PURE", MKT_PURE), ("AUG", AUG), ("MKTX", MKTX)):
        m = lgb.train(t3.PARAMS, lgb.Dataset(B[cols], B.y, weight=B.w), num_boost_round=200)
        m.save_model(f"{OUT}/own_{nm}.txt")
        imp = pd.Series(m.feature_importance("gain"), index=cols).sort_values(ascending=False)
        info[f"{nm}_top"] = {k: round(float(v / imp.sum()), 4) for k, v in imp.head(8).items()}
        print(nm, "trained", round(time.time() - t0), flush=True)
    info["params"] = t3.PARAMS; info["rounds"] = 200; info["features"] = {"PURE": MKT_PURE, "AUG": AUG, "MKTX": MKTX}
    json.dump(info, open(f"{OUT}/own_baseline_info.json", "w"), indent=1, default=str)
    print("done", round(time.time() - t0))
