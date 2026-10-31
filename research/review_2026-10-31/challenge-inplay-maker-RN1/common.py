"""Shared helpers: load sampled tapes, FIT/TEST split (identical rule to maker_study:
split at the median of RN1's first-fill time per market), PIT tape features."""
import json
from pathlib import Path
import numpy as np, pandas as pd

S = Path(__file__).resolve().parent
W = "0x2005d16a84ceefa912d4e380cd32e7ff827875ea"


def load():
    tk = pd.read_pickle(S / "sample_taker.pkl")
    mk = pd.read_pickle(S / "sample_maker.pkl")
    meta = json.load(open(S / "sample_meta.json"))
    cids = meta["cids"]
    active = {c: tuple(v) for c, v in meta["active"].items()}
    split = int(np.median([active[c][0] for c in cids]))
    fit = sorted(c for c in cids if active[c][0] < split)
    test = sorted(c for c in cids if active[c][0] >= split)
    meta["split"] = split
    meta["fit"], meta["test"] = fit, test
    return tk, mk, meta


def implied_p0(df):
    """Implied price of outcome 0 of each print."""
    return np.where(df["outcome"].to_numpy() == 0, df["price"].to_numpy(), 1 - df["price"].to_numpy())


def tape_state(tk_m: pd.DataFrame, query_ts: np.ndarray, latency: int, jump: float, look: int):
    """PIT state of one market at each query time t, using only taker prints with ts <= t - latency - 1
    (prints in the same second as t are treated as not yet seen).

    Returns: last implied p0, seconds since last jump (jump = |p0_k - p0 at <= ts_k - look| >= jump),
    realised range of p0 over the trailing `look` seconds.
    """
    g = tk_m.sort_values("ts")
    ts = g["ts"].to_numpy().astype(np.int64)
    p0 = implied_p0(g)
    # reference price `look` seconds before each print
    j = np.searchsorted(ts, ts - look, side="right") - 1
    ref = np.where(j >= 0, p0[np.clip(j, 0, None)], np.nan)
    isjump = np.abs(p0 - ref) >= jump - 1e-9
    jump_ts = ts[isjump]
    cut = query_ts.astype(np.int64) - latency - 1
    k = np.searchsorted(ts, cut, side="right") - 1
    last = np.where(k >= 0, p0[np.clip(k, 0, None)], np.nan) if len(ts) else np.full(len(cut), np.nan)
    kj = np.searchsorted(jump_ts, cut, side="right") - 1
    since_jump = np.where(kj >= 0, cut - jump_ts[np.clip(kj, 0, None)], 1e9) if len(jump_ts) else np.full(len(cut), 1e9)
    # trailing range over look seconds
    lo = np.searchsorted(ts, cut - look, side="right")
    rng = np.full(len(cut), np.nan)
    for i in range(len(cut)):
        if k[i] >= lo[i] and k[i] >= 0:
            seg = p0[lo[i]:k[i] + 1]
            rng[i] = seg.max() - seg.min()
        elif k[i] >= 0:
            rng[i] = 0.0
    return last, since_jump, rng
