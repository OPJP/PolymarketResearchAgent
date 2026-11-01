"""Indicators, event detectors and hidden-dimension tests (BRIEF.md "Hidden dimensions and indicators").

A strategy that runs on a dimension your data lacks cannot be replicated from the data you have. This
module helps find such dimensions: turn any series into causal indicators and events, then test whether
the wallet's decisions line up with those events beyond what chance and shared timing explain.

Everything is causal. Indicators live on a regular grid (`grid` + `asof`), and a value at grid time t uses
only samples stamped at or before t. Thresholds use volatility estimated from strictly earlier steps.
Stamp each input series with its publication time (BRIEF.md "No future data"), not its event time.

    t = grid(a, b, 0.1)                                    # 100-ms grid
    mid = asof(t, book_ts, book_mid)                       # last value at or before each step
    ev_ts, ev_sign = jumps(t, mid, horizon=5, k=3.0)       # 0.5-s moves beyond 3 sigma
    res = event_study(sign_ts, ev_ts, units, max_lag_s=30, bin_s=0.25,
                      decision_sign=side, event_sign=ev_sign)
    res["shape_peak_lag_s"], res["p_link"], res["signed"]["p_link"]

Specific events: `jumps`, `crossings`, `cusum`, `divergence`, `burst`, `first_occurrence`, conditioned on
state with `gate` and combined with `compound`; `event_features` turns events into causal per-cell inputs.

Tests:
- `event_study`: decision rate (and side concordance) around events, per lag. The null keeps each unit's
  time-in-unit structure and activity level (see its docstring), and a link must show both a level
  excess and a localized timing peak (`p_link`): a flat lift over all lags is shared activity.
- `screen`: many indicators at once, with BH q-values over one joint family.
- `incremental_auc`: does a feature add to a base score (the current rule, the co-occurrence baseline)?
  Group folds, and a Bayesian block bootstrap of the gain.
- `residual_clustering`: do unexplained decisions in different markets coincide at second scale more
  than a null that keeps each market's own timing allows (pass period_s for scheduled markets)? That
  points to a common driver: a feed, news, the bot's own loop.

Memory: `event_study` peaks at about 60 bytes per unit per FFT bin; it refuses jobs above `max_cells`.
`python research/reverse_engineering/tools/indicators.py selftest` runs a small synthetic check.
"""
from __future__ import annotations

import math
import sys

import numpy as np

# ---------------------------------------------------------------------------------------------- grids


def grid(start: float, end: float, step: float) -> np.ndarray:
    """Regular grid [start, end) with the given step in seconds."""
    return start + step * np.arange(int(math.ceil((end - start) / step)))


def asof(t: np.ndarray, ts: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Last value of x stamped at or before each grid time (NaN before the first sample). ts must be sorted."""
    ts, x = np.asarray(ts, float), np.asarray(x, float)
    i = np.searchsorted(ts, t, side="right") - 1
    out = np.full(len(t), np.nan)
    ok = i >= 0
    out[ok] = x[i[ok]]
    return out


def counts(t: np.ndarray, ts: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
    """Number (or weighted sum) of items stamped in (t_{k-1}, t_k], so the value at t_k is known at t_k.
    The first step counts items in (t_0 - step, t_0]. Feeds burst indicators."""
    ts = np.asarray(ts, float)
    o = np.argsort(ts, kind="mergesort")
    w = np.ones(len(ts)) if weights is None else np.asarray(weights, float)[o]
    cum = np.r_[0.0, np.cumsum(w)]
    step = t[1] - t[0] if len(t) > 1 else 1.0
    edges = np.r_[t[0] - step, t]
    c = cum[np.searchsorted(ts[o], edges, side="right")]
    return np.diff(c)


# ------------------------------------------------------------------------------- causal transforms


def _ffill(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, float)
    idx = np.where(np.isnan(x), 0, np.arange(len(x)))
    np.maximum.accumulate(idx, out=idx)
    out = x[idx]
    out[: np.argmax(~np.isnan(x)) if (~np.isnan(x)).any() else len(x)] = np.nan
    return out


def ewm(x: np.ndarray, halflife: float) -> np.ndarray:
    """Exponentially weighted mean over grid steps (halflife in steps). Causal; NaN gaps hold the last value."""
    from scipy.signal import lfilter

    x = _ffill(x)
    first = int(np.argmax(~np.isnan(x))) if (~np.isnan(x)).any() else len(x)
    out = np.full(len(x), np.nan)
    if first < len(x):
        a = 1.0 - 0.5 ** (1.0 / halflife)
        y = x[first:]
        out[first:] = lfilter([a], [1.0, a - 1.0], y, zi=[(1.0 - a) * y[0]])[0]
    return out


def lag(x: np.ndarray, h: int = 1) -> np.ndarray:
    """x shifted h steps later (x[t - h]); NaN for the first h steps."""
    out = np.full(len(x), np.nan)
    if h < len(x):
        out[h:] = np.asarray(x, float)[: len(x) - h]
    return out


def diff(x: np.ndarray, h: int = 1) -> np.ndarray:
    """x[t] - x[t - h]."""
    return np.asarray(x, float) - lag(x, h)


def ew_sigma(dx: np.ndarray, halflife: float) -> np.ndarray:
    """EW root mean square of dx from strictly earlier steps (so a threshold never sees the move it tests)."""
    return np.sqrt(lag(ewm(np.square(dx), halflife), 1))


def zscore(x: np.ndarray, halflife: float) -> np.ndarray:
    """(x - its EW mean) / EW sigma of that deviation, both from strictly earlier steps."""
    m = lag(ewm(x, halflife), 1)
    return (np.asarray(x, float) - m) / ew_sigma(np.asarray(x, float) - m, halflife)


def jump_z(x: np.ndarray, horizon: int, halflife: float | None = None) -> np.ndarray:
    """Move over `horizon` steps in units of the recent sigma of such moves."""
    d = diff(x, horizon)
    return d / ew_sigma(d, halflife or 50.0 * horizon)


# ------------------------------------------------------------------------------------ event detectors


def _refractory(idx: np.ndarray, t: np.ndarray, refractory_s: float) -> np.ndarray:
    if refractory_s <= 0 or len(idx) < 2:
        return idx
    keep, last = [], -np.inf
    for i in idx:
        if t[i] - last >= refractory_s:
            keep.append(i)
            last = t[i]
    return np.asarray(keep, dtype=int)


def threshold_events(t: np.ndarray, s: np.ndarray, level: float, refractory_s: float = 0.0):
    """Rising edges of |s| >= level on grid t. Returns (event_ts, sign of s). NaN never fires."""
    s = np.asarray(s, float)
    on = np.abs(np.nan_to_num(s, nan=0.0)) >= level
    idx = np.flatnonzero(on & ~np.r_[False, on[:-1]])
    idx = _refractory(idx, t, refractory_s)
    return t[idx], np.sign(s[idx])


def jumps(t, x, horizon: int, k: float = 3.0, halflife: float | None = None, refractory_s: float = 0.0):
    """Moves over `horizon` steps larger than k recent sigmas. Returns (event_ts, sign)."""
    return threshold_events(t, jump_z(x, horizon, halflife), k, refractory_s)


def crossings(t, x, level: float = 0.0, refractory_s: float = 0.0):
    """Times x crosses `level`; sign +1 upward, -1 downward."""
    d = np.sign(np.nan_to_num(np.asarray(x, float) - level, nan=0.0))
    d = _ffill(np.where(d == 0, np.nan, d))
    idx = np.flatnonzero((d != lag(d, 1)) & ~np.isnan(d) & ~np.isnan(lag(d, 1)))
    idx = _refractory(idx, t, refractory_s)
    return t[idx], d[idx]


def cusum(t, x, k: float = 0.5, h: float = 5.0, halflife: float = 600.0):
    """Two-sided CUSUM on standardized one-step increments: regime-change alarms. Returns (event_ts, sign)."""
    z = np.nan_to_num(diff(x, 1) / ew_sigma(diff(x, 1), halflife), nan=0.0, posinf=0.0, neginf=0.0)
    out_t, out_s, sp, sn = [], [], 0.0, 0.0
    for i, zi in enumerate(z):
        sp, sn = max(0.0, sp + zi - k), min(0.0, sn + zi + k)
        if sp > h or sn < -h:
            out_t.append(t[i])
            out_s.append(1.0 if sp > h else -1.0)
            sp = sn = 0.0
    return np.asarray(out_t, float), np.asarray(out_s, float)


def divergence(t, a, b, horizon: int, k: float = 3.0, halflife: float | None = None, refractory_s: float = 0.0):
    """One dimension moved and the other has not: |jump_z(a) - jump_z(b)| >= k (e.g. a venue moved, the
    Polymarket book did not yet: a stale quote). Sign is that of a's excess move."""
    return threshold_events(t, jump_z(a, horizon, halflife) - jump_z(b, horizon, halflife), k, refractory_s)


def burst(t, ts, window_steps: int, k: float = 3.0, halflife: float | None = None, refractory_s: float = 0.0):
    """Count of items (posts, headlines, comments, other traders' prints) over a window beyond k recent sigmas
    of that count. Never the wallet's own fills or orders (BRIEF.md "No future data")."""
    c = np.convolve(counts(t, ts), np.ones(window_steps), mode="full")[: len(t)]
    return threshold_events(t, zscore(c, halflife or 50.0 * window_steps), k, refractory_s)


def first_occurrence(t, cond, resets):
    """First grid time `cond` holds after each reset (a window open, a map start, a listing) and before the
    next one. Returns event timestamps."""
    t, cond, resets = np.asarray(t, float), np.asarray(cond, bool), np.sort(np.asarray(resets, float))
    hits = t[cond]
    out = []
    for i, r in enumerate(resets):
        end = resets[i + 1] if i + 1 < len(resets) else np.inf
        j = np.searchsorted(hits, r, side="left")
        if j < len(hits) and hits[j] < end:
            out.append(hits[j])
    return np.asarray(out, float)


def gate(ev_ts, ev_sign, t, state, lo: float = -np.inf, hi: float = np.inf):
    """Keep only events that fire while a state series on grid t (moneyness |S-K|/(sigma sqrt(tau)), time to
    expiry, a regime, a map score) is in [lo, hi]. The state is read as of the event time. Pre-register gates."""
    ev_ts = np.asarray(ev_ts, float)
    s = asof(ev_ts, t, state)
    keep = (s >= lo) & (s <= hi)
    return ev_ts[keep], (None if ev_sign is None else np.asarray(ev_sign, float)[keep])


def compound(a_ts, a_sign, b_ts, within_s: float, absent: bool = True):
    """Compound events. absent=True: A fired and no B followed within `within_s` (fires at a + within_s,
    when that is known, e.g. a venue moved and the Polymarket book has not). absent=False: the first B
    within `within_s` after an A (fires at that B). Sign is A's."""
    a_ts, b_ts = np.asarray(a_ts, float), np.sort(np.asarray(b_ts, float))
    sg = np.ones(len(a_ts)) if a_sign is None else np.asarray(a_sign, float)
    j = np.searchsorted(b_ts, a_ts, side="right")
    nxt = np.where(j < len(b_ts), b_ts[np.minimum(j, max(len(b_ts) - 1, 0))] if len(b_ts) else np.inf, np.inf)
    hit = nxt <= a_ts + within_s
    if absent:
        return a_ts[~hit] + within_s, sg[~hit]
    return nxt[hit], sg[hit]


def event_features(cell_ts, ev_ts, ev_sign=None, horizons=(1.0, 10.0, 60.0)) -> dict:
    """Causal per-cell features from an event series, for incremental_auc or a rule: seconds since the last
    event at or before each cell time, its sign, and event counts in each trailing (cell - h, cell]."""
    cell_ts, ev_ts = np.asarray(cell_ts, float), np.asarray(ev_ts, float)
    o = np.argsort(ev_ts, kind="mergesort")
    ev_ts = ev_ts[o]
    j = np.searchsorted(ev_ts, cell_ts, side="right")
    has = j > 0
    out = {"since_last": np.where(has, cell_ts - ev_ts[np.maximum(j - 1, 0)] if len(ev_ts) else np.inf, np.inf)}
    if ev_sign is not None:
        sg = np.asarray(ev_sign, float)[o]
        out["last_sign"] = np.where(has, sg[np.maximum(j - 1, 0)] if len(sg) else 0.0, 0.0)
    for h in horizons:
        out[f"count_{h:g}s"] = (j - np.searchsorted(ev_ts, cell_ts - h, side="right")).astype(float)
    return out


# ----------------------------------------------------------------------------------- multiple testing


def bh(p) -> np.ndarray:
    """Benjamini-Hochberg q-values. NaN p-values stay NaN and do not count toward the family."""
    p = np.asarray(p, float)
    out = np.full(len(p), np.nan)
    ok = np.flatnonzero(~np.isnan(p))
    n = len(ok)
    if n:
        o = ok[np.argsort(p[ok])]
        q = np.minimum.accumulate((p[o] * n / np.arange(1, n + 1))[::-1])[::-1]
        out[o] = np.minimum(q, 1.0)
    return out


def holm(p) -> np.ndarray:
    """Holm family-wise adjusted p-values. NaN p-values stay NaN and do not count toward the family."""
    p = np.asarray(p, float)
    out = np.full(len(p), np.nan)
    ok = np.flatnonzero(~np.isnan(p))
    n = len(ok)
    if n:
        o = ok[np.argsort(p[ok])]
        out[o] = np.minimum(np.maximum.accumulate(p[o] * (n - np.arange(n))), 1.0)
    return out


def gumbel_tail(x: float, null_max) -> float:
    """Tail p of an observed maximum from a Gumbel fitted by moments to the null maxima. A permutation p is
    floored at 1/(n_null + 1); this one is not, so BH over a large family stays possible."""
    m = np.asarray(null_max, float)
    m = m[np.isfinite(m)]
    if len(m) < 20 or m.std() == 0:
        return float("nan")
    beta = m.std(ddof=1) * math.sqrt(6.0) / math.pi
    mu = m.mean() - 0.5772156649 * beta
    return float(-np.expm1(-np.exp(-(x - mu) / beta)))


# ----------------------------------------------------------------------------------------- event study


def _bin_to_units(ts, units, bin_s, nbins, weights=None):
    """Matrix (units x nbins) of counts (or summed weights) of timestamps inside each unit."""
    starts, ends = units[:, 0], units[:, 1]
    ts = np.asarray(ts, float)
    u = np.searchsorted(starts, ts, side="right") - 1
    ok = (u >= 0) & (ts < ends[np.clip(u, 0, None)])
    b = np.floor((ts[ok] - starts[u[ok]]) / bin_s).astype(np.int64)
    w = np.ones(ok.sum()) if weights is None else np.asarray(weights, float)[ok]
    m = np.zeros((len(units), nbins), np.float32)
    np.add.at(m, (u[ok], b), w)
    return m, int(ok.sum())


def _classes(x, k):
    """Quantile class of each value (k classes; ties share a class)."""
    x = np.asarray(x, float)
    if k <= 1 or np.unique(x).size <= 1:
        return np.zeros(len(x), int)
    edges = np.unique(np.quantile(x, np.linspace(0, 1, k + 1)[1:-1]))
    return np.searchsorted(edges, x, side="right")


def _xcorr(pairs, null, groups, lengths, jit, L, nfft, n_null, rng, chunk):
    """Observed and null cross-correlations (sums over units) at lags -L..L bins, for each (E, C) pair in
    `pairs`, with the same null draw applied to every pair (so ratios between pairs are matched)."""
    lag_idx = np.r_[np.arange(nfft - L, nfft), np.arange(0, L + 1)]
    U, nb = pairs[0][0].shape
    Cfs = [np.fft.rfft(C, nfft, axis=1).astype(np.complex64) for _, C in pairs]
    obs = np.empty((len(pairs), 2 * L + 1))
    out = np.empty((len(pairs), n_null, 2 * L + 1))

    def acc(Ef_rows, Cf, perm=None):
        s = np.zeros(Cf.shape[1], np.complex128)
        for a in range(0, U, chunk):
            e = Ef_rows[a : a + chunk] if perm is None else Ef_rows[perm[a : a + chunk]]
            s += np.einsum("uf,uf->f", np.conj(e), Cf[a : a + chunk])
        return np.fft.irfft(s, nfft)[lag_idx]

    if null == "swap":
        Efs = [np.fft.rfft(E, nfft, axis=1).astype(np.complex64) for E, _ in pairs]
        for i in range(len(pairs)):
            obs[i] = acc(Efs[i], Cfs[i])
        for d in range(n_null):
            perm = np.arange(U)
            for g in groups:
                perm[g] = rng.permutation(g)
            for i in range(len(pairs)):
                out[i, d] = acc(Efs[i], Cfs[i], perm)
        return obs, out
    for i, (E, _) in enumerate(pairs):
        obs[i] = acc(np.fft.rfft(E, nfft, axis=1).astype(np.complex64), Cfs[i])
    cols = np.arange(nb)
    chunk = max(1, min(chunk, int(2e6 // nb)))  # the index and shifted matrices are chunk x nb
    for d in range(n_null):
        shift = rng.integers(jit[0], jit[1] + 1, U) * rng.choice([-1, 1], U)
        sums = [np.zeros(Cfs[0].shape[1], np.complex128) for _ in pairs]
        for a in range(0, U, chunk):
            ln = lengths[a : a + chunk, None]
            idx = cols[None, :] - shift[a : a + chunk, None]  # shift without wrap; events leaving the unit drop
            valid = (idx >= 0) & (idx < ln) & (cols[None, :] < ln)
            idx = np.clip(idx, 0, nb - 1)
            for i, (E, _) in enumerate(pairs):
                e = np.take_along_axis(E[a : a + chunk], idx, 1) * valid
                ef = np.fft.rfft(e, nfft, axis=1).astype(np.complex64)
                sums[i] += np.einsum("uf,uf->f", np.conj(ef), Cfs[i][a : a + chunk])
        for i in range(len(pairs)):
            out[i, d] = np.fft.irfft(sums[i], nfft)[lag_idx]
    return obs, out


def _p(stat_obs, stat_null_max):
    """Permutation p of an observed maximum; its Gumbel tail p; and the one to use (tail at the floor)."""
    p_perm = (1 + (stat_null_max >= stat_obs).sum()) / (1 + len(stat_null_max))
    p_tail = gumbel_tail(stat_obs, stat_null_max)
    use = p_tail if (stat_null_max >= stat_obs).sum() == 0 and not math.isnan(p_tail) else p_perm
    return float(p_perm), p_tail, float(use)


def _boxsum(a, w):
    """Moving sums of width w along the last axis (one per start position)."""
    c = np.cumsum(np.concatenate([np.zeros(a.shape[:-1] + (1,)), a], axis=-1), axis=-1)
    return c[..., w:] - c[..., :-w]


def _maxstat(stack, two_sided):
    """Rows: obs first, then null draws; columns: statistics. Standardize with the pooled mean and sd (obs
    included, so obs and draws are exchangeable) and return each row's maximum and obs's argmax."""
    mean, sd = stack.mean(0), stack.std(0, ddof=1)
    z = (stack - mean) / np.where(sd > 0, sd, np.inf)
    s = np.abs(z) if two_sided else z
    return s.max(1), int(np.argmax(s[0])), z[0]


def _summarize(obs, null, lags_s, flank_s, widths, two_sided, ref=None):
    """Level and shape statistics over (lag, width) windows. `ref`, for the signed test, is the matched
    unsigned (obs, null): the shape is then the signed pairs in a core window minus what the flank's net
    concordance (signed / unsigned pairs) predicts from the unsigned pairs in that window."""
    stack = np.vstack([obs[None], null])
    core, flank = np.abs(lags_s) < flank_s, np.abs(lags_s) >= flank_s
    n_core = int(core.sum())
    ws = [w for w in widths if w <= n_core]
    # Level: windowed excess pairs, family-wise over (lag, width).
    lev, lev_at = [], []
    for w in ws:
        lev.append(_boxsum(stack, w))
        lev_at += [(i, w) for i in range(stack.shape[1] - w + 1)]
    lmax, lk, lz = _maxstat(np.concatenate(lev, axis=1), two_sided)
    p_perm, p_tail, p_level = _p(lmax[0], lmax[1:])
    li, lw = lev_at[lk]
    mean = stack.mean(0)
    # Shape: a localized excess. Unsigned: lift (pairs / pooled mean per lag) in a core window minus the
    # flank mean lift, so a shared activity level, which multiplies every lag, cancels. Signed: concordance
    # in a core window beyond what the flank's concordance predicts, so a shared trend cancels.
    with np.errstate(divide="ignore", invalid="ignore"):
        if ref is None:
            lift = np.where(mean > 0, stack / np.where(mean > 0, mean, 1.0), 0.0)
            fl = lift[:, flank].mean(1, keepdims=True)
            sh = [_boxsum(lift[:, core], w) / w - fl for w in ws]
        else:
            rstack = np.vstack([ref[0][None], ref[1]])
            fl = stack[:, flank].sum(1, keepdims=True) / np.maximum(rstack[:, flank].sum(1, keepdims=True), 1e-12)
            sh = [_boxsum(stack[:, core], w) - fl * _boxsum(rstack[:, core], w) for w in ws]
    sh_at = [(i, w) for w in ws for i in range(n_core - w + 1)]
    smax, sk, sz = _maxstat(np.nan_to_num(np.concatenate(sh, axis=1)), two_sided)
    ps_perm, ps_tail, p_shape = _p(smax[0], smax[1:])
    si, sw = sh_at[sk]
    core_lags = lags_s[core]
    step = float(lags_s[1] - lags_s[0])
    with np.errstate(divide="ignore", invalid="ignore"):
        lift_lag = np.where(mean != 0, obs / mean, np.nan)
        win_lift = float(obs[li : li + lw].sum() / mean[li : li + lw].sum()) if mean[li : li + lw].sum() else float("nan")
        flank_rate = obs[flank].mean()
        shape_lift = float(obs[core][si : si + sw].mean() / flank_rate) if flank_rate else float("nan")
    level_lag = float(lags_s[li : li + lw].mean())
    return {
        "lags_s": lags_s.tolist(), "obs": obs.tolist(), "null_mean": mean.tolist(), "lift": lift_lag.tolist(),
        "peak_lag_s": level_lag, "peak_width_s": lw * step, "peak_lift": win_lift, "peak_z": float(lz[lk]),
        "level_peak_in_flank": bool(abs(level_lag) >= flank_s),
        "p_level": p_level, "p_level_perm": p_perm, "p_level_tail": p_tail,
        "shape_peak_lag_s": float(core_lags[si : si + sw].mean()), "shape_width_s": sw * step,
        "shape_lift": shape_lift, "shape_z": float(sz[sk]),
        "p_shape": p_shape, "p_shape_perm": ps_perm, "p_shape_tail": ps_tail,
        "median_lift": float(np.nanmedian(lift_lag)) if np.isfinite(lift_lag).any() else float("nan"),
        # A link needs both a level excess and a localized timing peak (intersection-union test).
        "p_link": max(p_level, p_shape),
    }


def event_study(decisions, events, units, max_lag_s: float = 60.0, bin_s: float = 1.0, n_null: int = 1000,
                strata=None, null: str = "auto", flank_s: float | None = None, jitter_s=None,
                activity_classes: int | None = None, length_classes: int = 4, widths=(1, 2, 4, 8, 16),
                decision_sign=None, event_sign=None, seed: int = 0, chunk: int = 1024,
                max_cells: float = 4e7) -> dict:
    """Decision rate (and side concordance) around events, per lag, against a null that keeps each unit's
    activity level and its time-in-unit structure.

    decisions: the wallet's decision times (B1 signing times; for makers also its posts, re-prices and
    cancels from the live lab), never fill times. events: indicator event times (publication times).
    units: non-overlapping [start, end) development units (windows, games, hours). Only points inside a
    unit count, and lags stay inside the unit.

    Nulls:
    - "swap": each unit's event track moves to another unit of the same stratum, at the same offsets from
      the unit start. The default stratum is unit-length class x class of the unit's event count x class of
      its decision count (activity_classes defaults to 3-10, growing with the number of units). The signed
      test stratifies by length class x the signs of the unit's net event sign and net side instead. Pass `strata` (one label per unit) for
      the confounders you know: realized-volatility class, hour of day, tournament tier.
    - "jitter": each unit's event track shifts by +-[jitter_s] (default [max_lag_s, 3 max_lag_s]) without
      wrapping; events leaving the unit drop. It keeps time-in-unit structure only on scales well above the
      shift, so prefer swap.
    - "auto" (default): swap when at least 80% of units have a stratum partner; otherwise swap within
      length classes (and `strata`) only (activity_classes is then reported as 0); otherwise jitter. Units
      without a partner keep their own events in every draw (see units_in_null).

    Statistics over windows of `widths` lag bins (so broad responses are found, not only sharp ones):
    - level: windowed excess pairs; p_level is family-wise over all (lag, width) windows.
    - shape: the lift in a window at |lag| < flank_s (default max_lag_s / 2) minus the flank mean lift
      (|lag| >= flank_s). A shared activity level multiplies every lag and cancels; a timing link is
      localized and survives. So max_lag_s must be at least twice the longest lag of interest; a level
      peak in the flank is flagged (level_peak_in_flank) and needs a wider max_lag_s.
    - p_link = max(p_level, p_shape): a link needs both. Each p is a permutation p from pooled
      standardization (obs and draws exchangeable), or its Gumbel tail when no draw reaches the observed
      value, so BH over large families stays possible. One-sided for decision excess; the signed test
      (does the side follow the event's sign?) is two-sided, and its shape is the net concordance.

    lag > 0: the decision follows the event. A localized peak at negative lags means the wallet acts before
    the event: the event is downstream of (or shares a source with) the wallet's real input. Look upstream.

    Memory: about 60 bytes per unit per FFT bin at the peak (nfft = next power of two >= unit bins + lag
    bins), about three times the work with signs. It refuses jobs above `max_cells`.
    """
    units = np.asarray(units, float).reshape(-1, 2)
    order = np.argsort(units[:, 0])
    units = units[order]
    if np.any(units[1:, 0] < units[:-1, 1]):
        raise ValueError("units overlap")
    lengths = np.ceil((units[:, 1] - units[:, 0]) / bin_s).astype(int)
    nbins, L = int(lengths.max()), int(math.ceil(max_lag_s / bin_s))
    if L < 4:
        raise ValueError("max_lag_s must span at least 4 bins")
    flank_s = max_lag_s / 2 if flank_s is None else flank_s
    lags_s = np.arange(-L, L + 1) * bin_s
    if not ((np.abs(lags_s) < flank_s).any() and (np.abs(lags_s) >= flank_s).sum() >= 2):
        raise ValueError("flank_s leaves no core or no flank lags")
    nfft = 1 << int(math.ceil(math.log2(nbins + L + 1)))
    cells = len(units) * (nfft // 2 + 1) * 4
    if cells > max_cells:
        raise MemoryError(f"{cells:.3g} cells > max_cells; use a larger bin_s, shorter units or fewer units")
    k_act = activity_classes or max(3, min(10, int(math.sqrt(len(units) / 8))))

    C, n_dec = _bin_to_units(decisions, units, bin_s, nbins)
    E, n_ev = _bin_to_units(events, units, bin_s, nbins)
    base = [_classes(lengths, length_classes), _classes(E.sum(1), k_act), _classes(C.sum(1), k_act)]
    if strata is not None:
        base.append(np.unique(np.asarray(strata)[order], return_inverse=True)[1])

    def make_groups(cols):
        lab = np.unique(np.stack(cols, 1), axis=0, return_inverse=True)[1].ravel()
        gs = [np.flatnonzero(lab == s) for s in np.unique(lab)]
        return [g for g in gs if len(g) > 1]

    groups = make_groups(base)
    swappable = int(sum(len(g) for g in groups))
    coarse = False
    if null == "auto" and swappable < 0.8 * len(units):
        # Too fragmented: swap within length classes (and your strata) only. The shape test still
        # cancels a shared activity level; the jitter null is the last resort.
        g2 = make_groups([base[0]] + base[3:])
        if sum(len(g) for g in g2) >= 0.8 * len(units):
            groups, swappable, coarse = g2, int(sum(len(g) for g in g2)), True
    kind = null if null != "auto" else ("swap" if swappable >= 0.8 * len(units) else "jitter")
    jit_s = jitter_s or (max_lag_s, 3 * max_lag_s)
    jit = (max(1, int(round(jit_s[0] / bin_s))), max(1, int(round(jit_s[1] / bin_s))))

    (obs,), (nul,) = _xcorr([(E, C)], kind, groups, lengths, jit, L, nfft, n_null, np.random.default_rng(seed),
                            chunk)
    out = _summarize(obs, nul, lags_s, flank_s, widths, two_sided=False)
    out.update(n_decisions=n_dec, n_events=n_ev, n_units=len(units), null=kind, units_in_null=swappable,
               activity_classes=0 if coarse else k_act, bin_s=bin_s, flank_s=flank_s)
    if kind == "swap" and swappable < 0.8 * len(units):
        out["warning"] = f"only {swappable} of {len(units)} units have a stratum partner; consider null='jitter'"
    if decision_sign is not None and event_sign is not None:
        Cs, _ = _bin_to_units(decisions, units, bin_s, nbins, decision_sign)
        Es, _ = _bin_to_units(events, units, bin_s, nbins, event_sign)
        # Sides: length class (and your strata) x signs of the unit's net event sign and net side.
        sgroups = make_groups([base[0]] + base[3:] + [np.sign(Es.sum(1)).astype(int), np.sign(Cs.sum(1)).astype(int)])
        skind = kind if kind == "jitter" or sum(len(g) for g in sgroups) >= 0.8 * len(units) else "jitter"
        (obs_s, obs_u), (nul_s, nul_u) = _xcorr([(Es, Cs), (E, C)], skind, sgroups, lengths, jit, L, nfft, n_null,
                                                np.random.default_rng(seed + 1), chunk)
        out["signed"] = _summarize(obs_s, nul_s, lags_s, flank_s, widths, two_sided=True, ref=(obs_u, nul_u))
        out["signed"]["null"] = skind
    return out


def screen(decisions, indicators: dict, units, **kw) -> list[dict]:
    """Event study for each indicator {name: (event_ts, event_sign or None)}, with BH q-values over one
    joint family: every indicator's p_link, plus the signed p_link of those with signs.

    Pre-register the family (one dimension family: indicators, event definitions, gates, compounds, lag
    ranges) in NOTES.md before running, screen on BUILD, and confirm only the survivors once on VALIDATE.
    Run each family at two or more lag ranges (e.g. +-2 s, +-60 s, +-600 s), since the shape test looks
    only inside |lag| < max_lag_s / 2. Log every row in state.json indicators.
    """
    dsign = kw.pop("decision_sign", None)
    rows = []
    for name, (ev, es) in indicators.items():
        r = event_study(decisions, ev, units, decision_sign=dsign if es is not None else None, event_sign=es, **kw)
        s = r.get("signed", {})
        rows.append({"name": name, "n_events": r["n_events"], "null": r["null"], "units_in_null": r["units_in_null"],
                     "n_units": r["n_units"], "peak_lag_s": r["peak_lag_s"], "peak_lift": r["peak_lift"],
                     "level_peak_in_flank": r["level_peak_in_flank"], "median_lift": r["median_lift"],
                     "shape_peak_lag_s": r["shape_peak_lag_s"], "shape_width_s": r["shape_width_s"],
                     "shape_lift": r["shape_lift"], "p_level": r["p_level"], "p_shape": r["p_shape"],
                     "p_link": r["p_link"], "signed_shape_peak_lag_s": s.get("shape_peak_lag_s"),
                     "signed_shape_z": s.get("shape_z"), "signed_p_link": s.get("p_link"),
                     "warning": r.get("warning")})
    ps = [r["p_link"] for r in rows] + [r["signed_p_link"] for r in rows if r["signed_p_link"] is not None]
    qs = bh(ps)
    for r, q in zip(rows, qs[: len(rows)]):
        r["q_bh"] = float(q)
    for r, q in zip([r for r in rows if r["signed_p_link"] is not None], qs[len(rows):]):
        r["signed_q_bh"] = float(q)
    return sorted(rows, key=lambda r: min(r["q_bh"], r.get("signed_q_bh", 1.0)))


# ------------------------------------------------------------------------------------ incremental value


def _tie_starts(s_sorted):
    return np.flatnonzero(np.r_[True, s_sorted[1:] != s_sorted[:-1]])


def _auc_w(y, w, starts):
    pos, neg = np.add.reduceat(w * y, starts), np.add.reduceat(w * (1 - y), starts)
    below = np.cumsum(neg) - neg
    den = pos.sum() * neg.sum()
    return float((pos * (below + 0.5 * neg)).sum() / den) if den > 0 else float("nan")


def weighted_auc(y, score, w=None) -> float:
    """ROC AUC with observation weights (ties count one half)."""
    y, score = np.asarray(y, float), np.asarray(score, float)
    o = np.argsort(score, kind="mergesort")
    w = np.ones(len(y)) if w is None else np.asarray(w, float)
    return _auc_w(y[o], w[o], _tie_starts(score[o]))


def incremental_auc(y, base_score, X, groups, n_splits: int = 5, n_boot: int = 1000, nonlinear: bool = True,
                    seed: int = 0) -> dict:
    """Out-of-fold AUC gain from adding features X to a base score (the current rule or the co-occurrence
    baseline), with a Bayesian bootstrap over groups (2-hour blocks or games).

    Both models are logistic regressions fitted with GroupKFold on f([base]) and f([base, X]), where f is a
    spline basis when nonlinear (applied to both, so the gain is not a recalibration of the base). Returns auc_base, auc_full, gain, a 95% interval and p (one-sided, gain <= 0).
    A feature that only predicts what the activity baseline predicts adds nothing here.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import SplineTransformer, StandardScaler

    y = np.asarray(y, int)
    b = np.asarray(base_score, float).reshape(-1, 1)
    if b.min() >= 0 and b.max() <= 1:
        b = np.log(np.clip(b, 1e-6, 1 - 1e-6) / (1 - np.clip(b, 1e-6, 1 - 1e-6)))
    X = np.nan_to_num(np.asarray(X, float).reshape(len(y), -1))
    groups = np.asarray(groups)

    def model(nl):
        steps = [SplineTransformer(n_knots=6, degree=3)] if nl else []
        return make_pipeline(*steps, StandardScaler(), LogisticRegression(max_iter=500))

    oof0, oof1 = np.zeros(len(y)), np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=n_splits).split(b, y, groups):
        oof0[te] = model(nonlinear).fit(b[tr], y[tr]).decision_function(b[te])  # same flexibility in base
        full_tr, full_te = np.hstack([b[tr], X[tr]]), np.hstack([b[te], X[te]])
        oof1[te] = model(nonlinear).fit(full_tr, y[tr]).decision_function(full_te)

    o0, o1 = np.argsort(oof0, kind="mergesort"), np.argsort(oof1, kind="mergesort")
    s0, s1 = _tie_starts(oof0[o0]), _tie_starts(oof1[o1])
    _, gidx = np.unique(groups, return_inverse=True)
    rng = np.random.default_rng(seed)
    a0, a1 = _auc_w(y[o0], np.ones(len(y))[o0], s0), _auc_w(y[o1], np.ones(len(y))[o1], s1)
    gains = np.empty(n_boot)
    for i in range(n_boot):
        w = rng.exponential(1.0, gidx.max() + 1)[gidx]
        gains[i] = _auc_w(y[o1], w[o1], s1) - _auc_w(y[o0], w[o0], s0)
    return {"auc_base": a0, "auc_full": a1, "gain": a1 - a0,
            "gain_ci95": [float(np.quantile(gains, 0.025)), float(np.quantile(gains, 0.975))],
            "p_gain_le_0": float((1 + (gains <= 0).sum()) / (1 + n_boot)), "n": int(len(y)),
            "n_groups": int(gidx.max() + 1)}


# --------------------------------------------------------------------------------- residual synchrony


def _pairs_within(ts_sorted, delta):
    return int((np.searchsorted(ts_sorted, ts_sorted + delta, side="right") - np.arange(len(ts_sorted)) - 1).sum())


def residual_clustering(ts, market, delta_s: float = 2.0, band_s: float | None = None, n_null: int = 1000,
                        jitter_s=None, period_s=None, seed: int = 0, top: int = 20) -> dict:
    """Do decisions the current rule fails to explain (out of fold) coincide across different markets within
    delta_s more often than their co-activity a little further apart predicts?

    Statistic: cross-market pairs at |dt| <= delta_s minus the pairs at delta_s < |dt| <= band_s (default
    3 delta_s) scaled by width. Co-activity on scales well above band_s (shared busy minutes or hours) is
    nearly flat over [0, band_s] and cancels; shared bursts of length B still leave a ratio of about
    1 + 2 delta_s / B, so read p together with the ratio. ratio = near pairs / pairs expected from the band.

    Null: each market's track shifts rigidly, so its internal timing is kept and only the alignment across
    markets is broken.
    - Default: by +-U[2 delta_s, 10 delta_s].
    - period_s: by a random nonzero multiple of the period (up to 12), wrapped within the data span rounded
      out to whole periods. Use it whenever markets run on a regular schedule (crypto windows: the least
      common multiple of the window lengths in the set, e.g. 900 s for 5m + 15m), or sharp bunching at the
      open shows up as synchrony.
    - Markets that start at irregular times (games after their kick-off) are not covered by either null:
      independent bunching after each start reads as synchrony. Express their misses relative to each
      market's start, or use only misses well after the start.

    Excess synchrony means a common driver outside the per-market data: a shared feed, news, a cross-market
    signal, an operational event, or the bot's own processing loop. Look the top clusters up in news,
    social and status logs. Returns near and band pairs, ratio, p (one-sided), the top clusters (time,
    number of distinct markets) and, with period_s, each cluster's offset within the period.
    """
    ts, market = np.asarray(ts, float), np.asarray(market)
    if len(ts) < 2:
        raise ValueError("residual_clustering needs at least two decisions")
    band_s = band_s or 3.0 * delta_s
    if band_s <= delta_s:
        raise ValueError("band_s must exceed delta_s")
    scale = delta_s / (band_s - delta_s)
    _, mk = np.unique(market, return_inverse=True)
    m = int(mk.max()) + 1
    same_near = same_band = 0
    for g in range(m):  # within-market pairs do not change under rigid per-market shifts
        tg = np.sort(ts[mk == g])
        n_d, n_b = _pairs_within(tg, delta_s), _pairs_within(tg, band_s)
        same_near, same_band = same_near + n_d, same_band + n_b - n_d

    def stat(x):
        xs = np.sort(x)
        near_all, band_all = _pairs_within(xs, delta_s), _pairs_within(xs, band_s)
        near, band = near_all - same_near, band_all - near_all - same_band
        return near, band, near - scale * band

    near, band, obs = stat(ts)
    rng = np.random.default_rng(seed)
    lo, hi = jitter_s or (2.0 * delta_s, 10.0 * delta_s)
    if period_s:
        span_lo = math.floor(ts.min() / period_s) * period_s
        span = max(period_s, math.ceil((ts.max() + 1e-9) / period_s) * period_s - span_lo)
    null = np.empty(n_null)
    for d in range(n_null):
        sgn = rng.choice([-1.0, 1.0], m)
        if period_s:
            x = span_lo + np.mod(ts + (sgn * period_s * rng.integers(1, 13, m))[mk] - span_lo, span)
        else:
            x = ts + (sgn * rng.uniform(lo, hi, m))[mk]
        null[d] = stat(x)[2]
    o = np.argsort(ts, kind="mergesort")
    st, sm = ts[o], mk[o]
    ends = np.searchsorted(st, st + delta_s, side="right")
    n_mk = np.array([len(np.unique(sm[i:j])) for i, j in enumerate(ends)])
    clusters = []
    for i in np.argsort(-n_mk, kind="mergesort"):
        if n_mk[i] < 2 or len(clusters) >= top:
            break
        if all(abs(st[i] - c[0]) > delta_s for c in clusters):
            clusters.append((float(st[i]), int(n_mk[i])))
    expected = scale * band
    out = {"near_pairs": near, "band_pairs": band, "expected_near": expected,
           "ratio": near / expected if expected > 0 else (float("nan") if near == 0 else float("inf")),
           "excess": obs, "null_mean_excess": float(null.mean()),
           "p": float((1 + (null >= obs).sum()) / (1 + n_null)), "top_clusters": clusters,
           "n": int(len(ts)), "n_markets": m,
           "null": f"period {period_s} s, wrapped" if period_s else f"shift +-[{lo}, {hi}] s"}
    if period_s:
        out["cluster_offsets_s"] = [round(c[0] % period_s, 3) for c in clusters]
    return out


def ledger_row(name: str, dimension: str, definition: str, event: str, result: dict, period: str,
               verdict: str) -> dict:
    """One row for state.json `indicators` (every indicator tried, including the failed ones).
    period: BUILD, VALIDATE or legacy (a study from before 2026-11-01, entered as it was, whole)."""
    keep = ("null", "units_in_null", "n_units", "n_events", "peak_lag_s", "peak_width_s", "peak_lift",
            "level_peak_in_flank", "median_lift", "shape_peak_lag_s", "shape_width_s", "shape_lift", "p_level",
            "p_shape", "p_link", "q_bh", "signed_p_link", "signed_q_bh", "gain", "gain_ci95", "p_gain_le_0",
            "min_detectable_share", "warning")
    if period == "legacy":
        res = {k: v for k, v in result.items() if not isinstance(v, (list, np.ndarray)) or len(v) <= 20}
    else:
        res = {k: result[k] for k in keep if k in result and result[k] is not None}
    return {"name": name, "dimension": dimension, "definition": definition, "event": event, "period": period,
            "result": res, "verdict": verdict}


# ------------------------------------------------------------------------------------------- self-test


def selftest() -> None:
    """Plant a 0.5-s lag in synthetic data and check that it is found; that time-in-window, activity-level
    and schedule confounds are not credited; and that detectors are causal."""
    rng = np.random.default_rng(1)
    units = np.array([(i * 300.0, i * 300.0 + 300.0) for i in range(200)])
    ev = np.sort(rng.uniform(0, 60000, 800))
    es = rng.choice([-1.0, 1.0], len(ev))
    keep = rng.random(len(ev)) < 0.4
    dec = np.r_[ev[keep] + 0.5 + rng.normal(0, 0.05, keep.sum()), rng.uniform(0, 60000, 1500)]
    dsg = np.r_[es[keep], rng.choice([-1.0, 1.0], len(dec) - keep.sum())]
    r = event_study(dec, ev, units, max_lag_s=10, bin_s=0.25, n_null=300, decision_sign=dsg, event_sign=es)
    assert abs(r["shape_peak_lag_s"] - 0.5) <= 0.25 and r["p_link"] < 0.01, r
    assert r["signed"]["p_link"] < 0.01 and r["signed"]["shape_z"] > 0
    print(f"planted: peak {r['shape_peak_lag_s']} s, lift {r['shape_lift']:.1f}, p_link {r['p_link']:.2g}")

    at_open = lambda n: units[rng.integers(0, len(units), n), 0] + np.minimum(rng.exponential(20, n), 299)
    r = event_study(at_open(1500), at_open(800), units, max_lag_s=10, bin_s=0.25, n_null=300)
    assert r["p_link"] > 0.01, r["p_link"]
    print(f"both busiest at the open, independent: p_link {r['p_link']:.2f}")

    vol = rng.lognormal(0, 1, len(units))
    inside = lambda k: np.concatenate([rng.uniform(a, b, rng.poisson(k * v)) for (a, b), v in zip(units, vol)])
    r = event_study(inside(8), inside(3), units, max_lag_s=10, bin_s=0.25, n_null=300)
    assert r["p_link"] > 0.01, r["p_link"]
    print(f"shared activity level, independent: p_link {r['p_link']:.2f} (median lift {r['median_lift']:.2f})")

    t = grid(0, 1000, 0.1)
    x = np.cumsum(rng.normal(0, 1, len(t)))
    x2 = x.copy()
    x2[5000:] += 50.0
    e1, e2 = jumps(t, x, 5, k=3)[0], jumps(t, x2, 5, k=3)[0]
    assert np.array_equal(e1[e1 < t[5000]], e2[e2 < t[5000]]), "detector looked ahead"
    print("detectors causal")

    y = (rng.random(4000) < 0.2).astype(int)
    base = rng.normal(0, 1, 4000) + y
    g = np.repeat(np.arange(40), 100)
    inc = incremental_auc(y, base, rng.normal(0, 1, 4000) + 0.8 * y, g, n_boot=300)
    nul = incremental_auc(y, base, rng.normal(0, 1, 4000), g, n_boot=300)
    assert inc["gain"] > 0.03 and inc["p_gain_le_0"] < 0.01 and nul["p_gain_le_0"] > 0.01
    print(f"incremental: gain {inc['gain']:.3f} (useful), {nul['gain']:.4f} (noise, p {nul['p_gain_le_0']:.2f})")

    shared = rng.uniform(0, 20000, 60)
    ts = np.r_[np.repeat(shared, 3) + rng.normal(0, 0.3, 180), rng.uniform(0, 20000, 600)]
    mk = np.r_[np.tile([0, 1, 2], 60), rng.integers(0, 6, 600)]
    rc = residual_clustering(ts, mk, n_null=200)
    opens = lambda: np.concatenate([w + rng.exponential(4, rng.poisson(1)) for w in units[:, 0]])
    rs = [opens() for _ in range(3)]
    sched = residual_clustering(np.concatenate(rs), np.repeat([0, 1, 2], [len(v) for v in rs]), n_null=200,
                                period_s=300.0)
    assert rc["p"] < 0.01 and sched["p"] > 0.01, (rc["p"], sched["p"])
    print(f"synchrony: ratio {rc['ratio']:.1f} (shared driver); scheduled opens with period null p {sched['p']:.2f}")
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        selftest()
    else:
        print(__doc__)
