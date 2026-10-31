"""Iteration 2: per-day cell grids (window, outcome, second) with PIT spot + tape features, own-state inventory
features (reported separately, never in the primary score) and labels. Saved as float32 parquet to
.cache/re/btc5m-bot/cells/<day0>.parquet. Only windows whose tape file exists (tape features need it).
Usage: python build_cells_day.py DAY0 [DAY0 ...]   (day0 = UTC midnight epoch; all days < H)"""
import os, sys, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from spot import Spot
from cells import build_cells, FEATS
from tape_feats import add_tape_feats, TAPE_FEATS
H = 1792713600
C = _ROOT + "/.cache/re/btc5m-bot"
OWN = ["inv_o", "inv_other", "inv_net", "avg_o", "avg_other", "pair_if_buy"]
EXTRA = ["dm5", "dm10", "dm30", "dgap5", "dgap10"]


def add_inv(cells, f, nW):
    """Cluster inventory per window strictly before second s (fills with block ts <= s-1). Own state only."""
    g = f[(f.rel >= 0) & (f.rel < 300)]
    sh = np.zeros((2, nW, 300)); usd = np.zeros((2, nW, 300))
    wmap = dict(zip(cells.cid.to_numpy()[::300][:nW], range(nW)))  # first outcome block: wi order
    wi = g.cid.map(wmap)
    ok = wi.notna().to_numpy()
    o = np.where(g.is_up.to_numpy()[ok], 0, 1); w = wi.to_numpy()[ok].astype(int); r = g.rel.to_numpy()[ok].astype(int)
    np.add.at(sh, (o, w, r), g.shares.to_numpy()[ok]); np.add.at(usd, (o, w, r), g.usdc.to_numpy()[ok])
    csh = np.cumsum(sh, axis=2) - sh; cusd = np.cumsum(usd, axis=2) - usd  # strictly before s
    o_c = np.where(cells.is_up.to_numpy(), 0, 1); w_c = cells.wi.to_numpy(); r_c = cells.rel.to_numpy().astype(int)
    cells["inv_o"] = csh[o_c, w_c, r_c].astype(np.float32); cells["inv_other"] = csh[1 - o_c, w_c, r_c].astype(np.float32)
    cells["inv_net"] = cells.inv_o - cells.inv_other
    with np.errstate(invalid="ignore", divide="ignore"):
        cells["avg_o"] = (cusd[o_c, w_c, r_c] / csh[o_c, w_c, r_c]).astype(np.float32)
        cells["avg_other"] = (cusd[1 - o_c, w_c, r_c] / csh[1 - o_c, w_c, r_c]).astype(np.float32)
    cells["pair_if_buy"] = (cells.ask_o + cells.avg_other).astype(np.float32)
    return cells


def add_extra(cells):
    """Changes of the outcome's last traded price and of the FV-minus-price gap over 5/10/30 s (PIT: shifts of PIT columns)."""
    key = cells.is_up.astype(np.int64).to_numpy() * 10**7 + cells.wi.to_numpy().astype(np.int64)
    for h in (5, 10, 30):
        prev = cells.groupby(key, sort=False).m_last.shift(h)
        cells[f"dm{h}"] = (cells.m_last - prev).astype(np.float32)
    for h in (5, 10):
        prev = cells.groupby(key, sort=False).gap_m.shift(h)
        cells[f"dgap{h}"] = (cells.gap_m - prev).astype(np.float32)
    return cells


def build_day(day0, sp, f, win):
    w = win[(win.start_ts >= day0) & (win.start_ts < day0 + 86400) & (win.end_ts <= H)]
    w = w[[os.path.exists(f"{C}/tapes/{c}.parquet") for c in w.cid]].sort_values("start_ts").reset_index(drop=True)
    if len(w) == 0:
        return None
    c = build_cells(w, f, sp)
    c = add_tape_feats(c, f, sp)
    c = add_inv(c, f, len(w))
    c = add_extra(c)
    for k in c.columns:
        if c[k].dtype == np.float64:
            c[k] = c[k].astype(np.float32)
    return c


if __name__ == "__main__":
    os.makedirs(f"{C}/cells", exist_ok=True)
    sp = Spot(); f = pd.read_parquet(f"{C}/fills.parquet"); win = pd.read_parquet(f"{C}/windows.parquet")
    for d in sys.argv[1:]:
        t0 = time.time(); d = int(d)
        c = build_day(d, sp, f, win)
        if c is None:
            print("no windows", d); continue
        c.to_parquet(f"{C}/cells/{d}.parquet", index=False)
        print(d, "windows", c.wi.max() + 1, "cells", len(c), "y", round(float(c.y.mean()), 4), round(time.time() - t0), "s", flush=True)
