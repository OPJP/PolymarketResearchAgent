"""E6 first form: the push feed's message intensity as a latent dimension, proxied point in time by its visible
subscribers (group P, fixed on BUILD in iteration 9) - does it add to presence over the co-occurrence baseline AND a
self-excitation baseline?

Bins: VALIDATE presence bins (bins_1792540800_1792713600.parquet: market x 30-s bin, y = wallet fill in the bin).
Base scores (fitted on BUILD bins, scored on VALIDATE):
  B0   co-occurrence: LightGBM on market activity (prints / volume / moves of the market and event; contains the
       subscribers' own prints);
  B0S  B0 + self-excitation: the wallet's own fills in the previous 30 / 120 / 600 s on the market and the event
       (a baseline only; never a rule feature).
Latent features (point in time; a take is usable from its block time): group-P takes on the event in transactions
without the wallet in the previous 30 / 120 / 600 s, and the seconds since the last one (capped at 3600).
Test: indicators.incremental_auc (GroupKFold over 2-h blocks, Bayesian block bootstrap) of the latent over B0 and
over B0S. Output: results/e6_latent.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter4"))
import indicators as ind  # noqa: E402
from queue_replay import load_record  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
B0 = ["m_n30", "m_v30", "m_n120", "m_v120", "m_n600", "m_v600", "m_cum", "m_tsl", "m_p", "m_dev", "m_dp60", "m_dp300",
      "m_nw600", "e_n30", "e_v30", "e_n120", "e_v120", "e_n600", "e_v600", "e_cum", "e_tsl", "e_pre", "elapsed",
      "is_match", "map_no"]
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, max_bin=63, verbose=-1, seed=7)


def counts_before(times_sorted, t, w):
    return np.searchsorted(times_sorted, t, side="left") - np.searchsorted(times_sorted, t - w, side="left")


def add_feats(b, own_by_cid, own_by_ev, gp_by_ev):
    for w in (30, 120, 600):
        b[f"s_m{w}"] = 0.0
        b[f"s_e{w}"] = 0.0
        b[f"g_e{w}"] = 0.0
    b["g_tsl"] = 3600.0
    for cid, idx in b.groupby("cid").groups.items():
        t = b.loc[idx, "start"].to_numpy(float)
        ev = b.loc[idx, "event"].iloc[0]
        om = own_by_cid.get(cid, np.array([]))
        oe = own_by_ev.get(ev, np.array([]))
        ge = gp_by_ev.get(ev, np.array([]))
        for w in (30, 120, 600):
            b.loc[idx, f"s_m{w}"] = counts_before(om, t, w)
            b.loc[idx, f"s_e{w}"] = counts_before(oe, t, w)
            b.loc[idx, f"g_e{w}"] = counts_before(ge, t, w)
        j = np.searchsorted(ge, t, side="left") - 1
        b.loc[idx, "g_tsl"] = np.where(j >= 0, np.minimum(t - ge[np.maximum(j, 0)], 3600), 3600) if len(ge) else 3600.0
    return b


def main():
    GP = set(json.load(open(RES / "selection_groupP.json"))["members"])
    bb = pd.read_parquet(OUT / "bins_1792108800_1792540800.parquet")
    bv = pd.read_parquet(OUT / "bins_1792540800_1792713600.parquet")
    f = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "event", "first_fill_ts"])
    own_by_cid = {k: np.sort(g.first_fill_ts.to_numpy(float)) for k, g in f.groupby("cid")}
    own_by_ev = {k: np.sort(g.first_fill_ts.to_numpy(float)) for k, g in f.groupby("event")}
    wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx"]).tx)
    cd, _ = load_record()
    tk = cd[(cd.idx == -1) & ~cd.tx.isin(wtx)].drop_duplicates("tx")
    tk = tk[tk.maker.str.lower().isin(GP)]
    ev_of = pd.read_parquet(OUT / "universe.parquet", columns=["cid", "event_slug"]).drop_duplicates("cid")
    ev_of = dict(zip(ev_of.cid, ev_of.event_slug))
    tk = tk.assign(event=tk.cid.map(ev_of))
    gp_by_ev = {k: np.sort(g.bts.to_numpy(float)) for k, g in tk.groupby("event")}
    bb = add_feats(bb, own_by_cid, own_by_ev, gp_by_ev)
    bv = add_feats(bv, own_by_cid, own_by_ev, gp_by_ev)
    S = [f"s_m{w}" for w in (30, 120, 600)] + [f"s_e{w}" for w in (30, 120, 600)]
    G = [f"g_e{w}" for w in (30, 120, 600)] + ["g_tsl"]
    rng = np.random.default_rng(0)
    keep = (bb.y == 1) | (rng.random(len(bb)) < 0.25)
    wts = np.where(bb.y[keep] == 1, 1.0, 4.0)
    m0 = lgb.train(PARAMS, lgb.Dataset(bb.loc[keep, B0], bb.loc[keep, "y"], weight=wts), 250)
    m1 = lgb.train(PARAMS, lgb.Dataset(bb.loc[keep, B0 + S], bb.loc[keep, "y"], weight=wts), 250)
    bv["b0"] = m0.predict(bv[B0])
    bv["b0s"] = m1.predict(bv[B0 + S])
    bv["blk"] = (bv.start // 7200).astype(int)
    out = {"validate_bins": int(len(bv)), "positives": int(bv.y.sum()), "gp_takes_events": len(gp_by_ev)}
    y = bv.y.to_numpy()
    for name, base in (("over_cooccurrence_B0", "b0"), ("over_B0_plus_self_excitation", "b0s")):
        r = ind.incremental_auc(y, bv[base].to_numpy(), bv[G].to_numpy(), bv.blk.to_numpy(), n_splits=5, n_boot=500)
        out[name] = {k: r[k] for k in r if not isinstance(r[k], (list, np.ndarray)) or len(r[k]) <= 3}
        print(name, json.dumps(out[name], default=float), flush=True)
    (RES / "e6_latent.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
