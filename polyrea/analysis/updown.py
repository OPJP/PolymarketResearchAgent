"""Crypto Up/Down markets: fair-value model, decision match test, PIT backtest.

Market mechanics (Gamma metadata, 2026): each market covers a window
[eventStartTime, endDate] of 5m / 15m / 1h. It resolves Up iff the Chainlink
TWAP over the last ``twapLookbackSeconds`` (60 s) of the window is >= the
strike ``priceToBeat``, which is the same TWAP over the 60 s before the window
starts (the previous window's final price; 555/555 consecutive pairs agree).
Takers pay ``rate * p * (1 - p)`` per share (feeSchedule, exponent 1); a share
of fees is rebated to makers. The price tick is 0.01 between 0.04 and 0.96 and
0.001 outside (``quote_price``).

Hypothesis family LA(theta, latency): *buy the side whose spot-implied fair
value exceeds its ask by more than theta*, using spot information that is
``latency`` seconds old. The fair value uses only data available at the
decision time:

* strike S0 = mean spot over [start - 60 s, start) available at the decision
  (decisions before the window starts get fair value 0.5);
* S_t = latest spot available at t - latency;
* sigma = realized 1-second volatility over the preceding 30 minutes;
* inside the TWAP period the already-observed part of the average is used.

Evaluation is vectorized for speed; :func:`audit_vectorized_fair_value`
re-computes a sample through the guarded :class:`~polyrea.pit.PITView` and
requires identical numbers, so the fast path cannot see the future either.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from polyrea.pit import PITStore, TimeSeries
from polyrea.stats.significance import hac_t_test, permutation_pvalue, sharpe, stationary_bootstrap_pvalue

VOL_LOOKBACK = 1800
TWAP_SECONDS = 60
FEE_RATE_DEFAULT = 0.07
# criterion (6) effect-size floor: the fitted rule must flag at least this share
# of the wallet's TEST decisions, at this multiple of the base rate
MATCH_MIN_RECALL = 0.2
MATCH_MIN_LIFT = 2.0


@dataclass(frozen=True)
class Window:
    condition_id: str
    asset: str
    duration: str
    start_ts: int
    end_ts: int
    up_token: str
    down_token: str
    twap_seconds: int = TWAP_SECONDS
    fee_rate: float = FEE_RATE_DEFAULT
    # settlement only (post-hoc): payout of the Up token, None if unresolved
    up_payout: float | None = field(default=None, compare=False)


def windows_from_markets(markets: dict[str, dict[str, Any]]) -> list[Window]:
    out = []
    for cid, m in markets.items():
        cfg = m.get("cryptoMarketConfig") or {}
        if not cfg.get("asset"):
            continue
        try:
            tokens = json.loads(m.get("clobTokenIds") or "[]")
            outcomes = json.loads(m.get("outcomes") or "[]")
            prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
        except (TypeError, ValueError):
            continue
        if len(tokens) != 2 or outcomes[:2] != ["Up", "Down"]:
            continue
        start = pd.Timestamp(m.get("eventStartTime")).timestamp() if m.get("eventStartTime") else None
        end = pd.Timestamp(m.get("endDate")).timestamp() if m.get("endDate") else None
        if start is None or end is None:
            continue
        resolved = m.get("umaResolutionStatus") == "resolved" and prices and max(prices) >= 0.999
        fs = m.get("feeSchedule") or {}
        out.append(
            Window(
                condition_id=cid,
                asset=cfg["asset"],
                duration=cfg.get("duration", ""),
                start_ts=int(start),
                end_ts=int(end),
                up_token=str(tokens[0]),
                down_token=str(tokens[1]),
                twap_seconds=int(cfg.get("twapLookbackSeconds") or TWAP_SECONDS),
                fee_rate=float(fs.get("rate", FEE_RATE_DEFAULT)) if m.get("feesEnabled", True) else 0.0,
                up_payout=prices[0] if resolved else None,
            )
        )
    return sorted(out, key=lambda w: w.start_ts)


def taker_fee_per_share(price: np.ndarray | float, rate: float) -> np.ndarray | float:
    return rate * np.asarray(price) * (1 - np.asarray(price))


def snap_price(p: float) -> float:
    """Remove data-api float noise: market-order rows carry usdc/size, e.g. 0.5099999753.

    A price within 1e-5 of the 0.001 grid is put on it; genuine sweep averages
    stay as they are.
    """
    r = round(p, 3)
    return r if abs(p - r) < 1e-5 else p


# ----------------------------------------------------------------------------- spot index
class SpotIndex:
    """Vectorized point-in-time access to a per-second spot TimeSeries."""

    def __init__(self, series: TimeSeries):
        self.s = series
        self.av = series.available_ts
        self.ev = series.event_ts
        self.px = series.values.astype(float)
        lr = np.diff(np.log(self.px), prepend=np.log(self.px[0])) if len(self.px) else np.array([])
        self.cum_r2 = np.cumsum(lr**2)
        # centred before summing: a raw cumsum of ~1e10 loses ~1e-7 per mean, which matters near a window's end
        self.px_ref = float(self.px[0]) if len(self.px) else 0.0
        self.cum_px = np.cumsum(self.px - self.px_ref)

    def _idx_available(self, t: np.ndarray) -> np.ndarray:
        """Index of the last record available at or before each t (-1 if none)."""
        return np.searchsorted(self.av, t, side="right") - 1

    def price_at(self, t: np.ndarray) -> np.ndarray:
        i = self._idx_available(np.asarray(t))
        out = np.where(i >= 0, self.px[np.clip(i, 0, None)], np.nan)
        return out

    def sigma_at(self, t: np.ndarray, lookback: int = VOL_LOOKBACK) -> np.ndarray:
        """Realized per-second log-return std over records available in (t-lookback, t]."""
        t = np.asarray(t)
        hi = self._idx_available(t)
        lo = self._idx_available(t - lookback)
        n = hi - lo
        s_hi = np.where(hi >= 0, self.cum_r2[np.clip(hi, 0, None)], 0.0)
        s_lo = np.where(lo >= 0, self.cum_r2[np.clip(lo, 0, None)], 0.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            var = (s_hi - s_lo) / np.maximum(n, 1)
        return np.where(n >= 60, np.sqrt(np.maximum(var, 1e-14)), np.nan)

    def mean_between(self, a: np.ndarray, b: np.ndarray, t_avail: np.ndarray) -> np.ndarray:
        """Mean of per-second prices with event_ts in [a, b), restricted to records available by t_avail."""
        a, b, t_avail = np.asarray(a), np.asarray(b), np.asarray(t_avail)
        hi_av = self._idx_available(t_avail)
        lo = np.searchsorted(self.ev, a, side="left") - 1
        hi = np.minimum(np.searchsorted(self.ev, b, side="left") - 1, hi_av)
        n = hi - lo
        s_hi = np.where(hi >= 0, self.cum_px[np.clip(hi, 0, None)], 0.0)
        s_lo = np.where(lo >= 0, self.cum_px[np.clip(lo, 0, None)], 0.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(n > 0, (s_hi - s_lo) / n + self.px_ref, np.nan)


def fair_up_vectorized(spot: SpotIndex, start: np.ndarray, end: np.ndarray, t_dec: np.ndarray, twap: int = TWAP_SECONDS) -> np.ndarray:
    """P(Up) at decision times ``t_dec`` using spot available at ``t_dec``."""
    start, end, t_dec = (np.asarray(x, dtype=np.int64) for x in (start, end, t_dec))
    s0 = spot.mean_between(start - twap, start, t_dec)  # strike: TWAP before the window
    s0 = np.where(np.isnan(s0), spot.price_at(start), s0)
    st = spot.price_at(t_dec)
    sig = spot.sigma_at(t_dec)
    twap_start = end - twap
    before = t_dec < twap_start
    # before TWAP period: avg ~ S_t, var = sigma^2 S^2 [(twap_start - t) + twap/3]
    var_before = (twap_start - t_dec).clip(min=0) + twap / 3.0
    # inside TWAP period: known part A over [twap_start, t), remaining r seconds
    r = (end - t_dec).clip(min=0).astype(float)
    a_known = spot.mean_between(twap_start, np.minimum(t_dec, end), t_dec)  # the closing TWAP stops at the window end
    a_known = np.where(np.isnan(a_known), st, a_known)
    mean_in = ((twap - r) * a_known + r * st) / twap
    sd_in = (r / twap) * np.sqrt(np.maximum(r, 1e-9) / 3.0)
    mean = np.where(before, st, mean_in)
    sd_units = np.where(before, np.sqrt(var_before), sd_in)  # in sqrt(seconds)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (mean - s0) / (st * sig * sd_units)
    p = stats.norm.cdf(z)
    p = np.where(t_dec < start, 0.5, p)  # strike unknown before the window opens
    p = np.where(t_dec >= end, np.where(mean >= s0, 1.0, 0.0), p)
    return p


def fair_up_pit(store: PITStore, spot_name: str, w: Window, t: int, latency: int, availability_lag: int = 1) -> float | None:
    """Reference (slow) implementation that reads spot only through the guarded PITView.

    Mirrors :func:`fair_up_vectorized` exactly: volatility over records
    available in (t_dec - VOL_LOOKBACK, t_dec], each record's log return taken
    against the record before it.
    """
    view = store.view(t)
    t_dec = t - latency
    if t_dec < w.start_ts:
        return 0.5
    s0 = view.latest(spot_name, at=w.start_ts)
    st = view.latest(spot_name, at=t_dec)
    if s0 is None or st is None:
        return None
    ev_k, v_k = view.history(spot_name, lookback=max(0, t - (w.start_ts - w.twap_seconds)) + 2)
    k_sel = (ev_k >= w.start_ts - w.twap_seconds) & (ev_k < w.start_ts) & (ev_k + availability_lag <= t_dec)
    strike = float(np.mean(v_k[k_sel].astype(float))) if k_sel.any() else float(s0[1])
    ev, vals = view.history(spot_name, lookback=VOL_LOOKBACK + latency + 5)
    av = ev + availability_lag
    vals = vals.astype(float)
    idx = np.nonzero((av > t_dec - VOL_LOOKBACK) & (av <= t_dec))[0]
    if len(idx) < 60:
        return None
    prev = np.clip(idx - 1, 0, None)
    lr = np.where(idx - 1 >= 0, np.log(vals[idx]) - np.log(vals[prev]), 0.0)
    if idx[0] == 0 and store.series[spot_name].event_ts[0] != ev[0]:
        # the record before the window exists in the store but fell outside the
        # history read; fetch it through the view to keep the math identical
        e2, v2 = view.history(spot_name, lookback=VOL_LOOKBACK + latency + 3600)
        j = int(np.searchsorted(e2, ev[0])) - 1
        if j >= 0:
            lr[0] = math.log(vals[0]) - math.log(float(v2[j]))
    sig = math.sqrt(max(float(np.mean(lr**2)), 1e-14))
    S0, St = strike, float(st[1])
    twap_start = w.end_ts - w.twap_seconds
    if t_dec < twap_start:
        mean, sd_units = St, math.sqrt((twap_start - t_dec) + w.twap_seconds / 3.0)
    else:
        r = max(w.end_ts - t_dec, 0)
        sel = (ev >= twap_start) & (ev < min(t_dec, w.end_ts)) & (av <= t_dec)
        a_known = float(np.mean(vals[sel])) if sel.any() else St
        mean = ((w.twap_seconds - r) * a_known + r * St) / w.twap_seconds
        sd_units = (r / w.twap_seconds) * math.sqrt(max(r, 1e-9) / 3.0)
    if t_dec >= w.end_ts:
        return 1.0 if mean >= S0 else 0.0
    z = (mean - S0) / (St * sig * sd_units)
    return float(stats.norm.cdf(z))


def audit_vectorized_fair_value(store: PITStore, spot_name: str, windows: list[Window], probes: list[tuple[Window, int]], latency: int) -> dict[str, Any]:
    """Compare vectorized fair values with the PITView reference on sample probes.

    Also re-evaluates the reference on a store truncated at the decision time;
    a mismatch would mean future data influenced the value.
    """
    spot = SpotIndex(store.series[spot_name])
    errs, trunc_errs, n = [], [], 0
    for w, t in probes:
        ref = fair_up_pit(store, spot_name, w, t, latency)
        vec = float(fair_up_vectorized(spot, np.array([w.start_ts]), np.array([w.end_ts]), np.array([t - latency]), w.twap_seconds)[0])
        if ref is None or not np.isfinite(vec):
            continue
        cut = fair_up_pit(store.truncated(t), spot_name, w, t, latency)
        n += 1
        errs.append(abs(ref - vec))
        trunc_errs.append(abs(ref - (cut if cut is not None else np.nan)))
    return {
        "probes": n,
        "max_abs_diff_vectorized_vs_pit": float(np.max(errs)) if errs else None,
        "max_abs_diff_full_vs_truncated_store": float(np.nanmax(trunc_errs)) if trunc_errs else None,
        "passed": bool(n > 0 and max(errs) < 1e-6 and np.nanmax(trunc_errs) < 1e-9),
    }


# ----------------------------------------------------------------------------- prints
def taker_buy_prints(tapes: dict[str, list[dict[str, Any]]], windows: list[Window]) -> pd.DataFrame:
    """Every aggressive BUY on either outcome: the liquidity a taker could have hit."""
    by_cid = {w.condition_id: w for w in windows}
    rows = []
    for cid, tape in tapes.items():
        w = by_cid.get(cid)
        if w is None:
            continue
        for r in tape:
            if r.get("side") != "BUY":
                continue
            asset = str(r.get("asset"))
            if asset == w.up_token:
                is_up = True
            elif asset == w.down_token:
                is_up = False
            else:
                continue
            rows.append(
                {
                    "condition_id": cid,
                    "ts": int(r["timestamp"]),
                    "wallet": (r.get("proxyWallet") or "").lower(),
                    "is_up": is_up,
                    "price": snap_price(float(r["price"])),
                    "size": float(r["size"]),
                    "start_ts": w.start_ts,
                    "end_ts": w.end_ts,
                    "twap": w.twap_seconds,
                    "fee_rate": w.fee_rate,
                    "up_payout": w.up_payout,
                }
            )
    return pd.DataFrame(rows)


def score_prints(prints: pd.DataFrame, spot: SpotIndex, latency: int, shift: int = 0) -> np.ndarray:
    """Model edge (fair value of the bought side minus price) for each print.

    ``shift`` moves the spot clock (used by the permutation null); with
    ``shift=0`` the decision for a print at ts uses spot available at ts - latency.
    """
    t_dec = prints["ts"].to_numpy() - latency
    fu = fair_up_vectorized(
        spot,
        prints["start_ts"].to_numpy() + shift,
        prints["end_ts"].to_numpy() + shift,
        t_dec + shift,
        int(prints["twap"].iloc[0]) if len(prints) else TWAP_SECONDS,
    )
    fair_side = np.where(prints["is_up"].to_numpy(), fu, 1 - fu)
    return fair_side - prints["price"].to_numpy()


def score_spot_return(prints: pd.DataFrame, spot: SpotIndex, latency: int, shift: int | np.ndarray = 0, horizon: int = 2) -> np.ndarray:
    """Signed spot log return over ``horizon`` s toward the bought side (hypothesis SR).

    Uses spot available ``latency`` s before the print: a maker whose bids are
    filled right after spot moved toward that side is quoting on spot.
    """
    t = prints["ts"].to_numpy() - latency + shift
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.log(spot.price_at(t) / spot.price_at(t - horizon))
    return np.where(prints["is_up"].to_numpy(), r, -r)


def auc(score: np.ndarray, y: np.ndarray) -> float:
    ok = np.isfinite(score)
    s, yy = score[ok], y[ok]
    n1 = int(yy.sum())
    n0 = len(yy) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    ranks = stats.rankdata(s)
    return float((ranks[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def decision_metrics(score: np.ndarray, y: np.ndarray, theta: float) -> dict[str, float]:
    ok = np.isfinite(score)
    pred = (score[ok] > theta).astype(int)
    yy = y[ok].astype(int)
    tp = int(((pred == 1) & (yy == 1)).sum())
    fp = int(((pred == 1) & (yy == 0)).sum())
    fn = int(((pred == 0) & (yy == 1)).sum())
    tn = int(((pred == 0) & (yy == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = (tp * tn - fp * fn) / denom if denom else float("nan")
    base = (tp + fn) / max(1, tp + fp + fn + tn)
    return {"theta": theta, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec, "mcc": mcc, "base_rate": base, "lift": prec / base if base else float("nan")}


def fit_theta(score: np.ndarray, y: np.ndarray, grid: np.ndarray | None = None) -> float:
    """Threshold with the best MCC; the default grid is quantiles of the score."""
    if grid is None:
        fin = score[np.isfinite(score)]
        grid = np.unique(np.quantile(fin, np.linspace(0.5, 0.995, 60))) if len(fin) else np.array([0.0])
    best, best_mcc = 0.0, -2.0
    for th in grid:
        m = decision_metrics(score, y, float(th))["mcc"]
        if np.isfinite(m) and m > best_mcc:
            best, best_mcc = float(th), m
    return best


def window_positions(prints: pd.DataFrame, blocks: list[tuple[int, int]], duration_s: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Block id, window index inside the block and windows per block for each print's window."""
    st = prints["start_ts"].to_numpy().astype(np.int64)
    bid = np.full(len(st), -1)
    widx = np.zeros(len(st), dtype=np.int64)
    nwin = np.zeros(len(st), dtype=np.int64)
    for b, (a, e) in enumerate(blocks):
        m = (st >= a) & (st < e)
        bid[m] = b
        widx[m] = (st[m] - a) // duration_s
        nwin[m] = (e - a) // duration_s
    return bid, widx, nwin


def rotation_shifts(bid: np.ndarray, widx: np.ndarray, nwin: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """One draw of the rotation null: each block's windows take the spot path of
    the window k_b places later (cyclically) in the same block, k_b != 0 drawn
    independently per block. Price, timing and side of every print are kept;
    only the link between the print and its own spot path is broken, and every
    shifted decision still lands on loaded spot data."""
    shift = np.zeros(len(bid), dtype=np.int64)
    for b in np.unique(bid[bid >= 0]):
        m = bid == b
        n = int(nwin[m][0])
        if n < 2:
            continue
        k = int(rng.integers(1, n))
        shift[m] = ((widx[m] + k) % n - widx[m])
    return shift


def match_strata(prints: pd.DataFrame, n_price_bins: int = 50) -> np.ndarray:
    """Strata of comparable decisions: price quantile x time in window x side.

    A wallet may prefer some prices, times or sides for reasons unrelated to
    the hypothesis; comparing it with other traders only inside a stratum
    removes those static preferences from the match statistic.
    """
    price = prints["price"].to_numpy()
    edges = np.unique(np.quantile(price, np.linspace(0, 1, n_price_bins + 1)[1:-1])) if len(price) else np.array([])
    pbin = np.searchsorted(edges, price, side="right")
    span = (prints["end_ts"] - prints["start_ts"]).to_numpy()
    frac = (prints["ts"] - prints["start_ts"]).to_numpy() / np.maximum(span, 1)
    tbin = np.digitize(frac, [0.0, 0.25, 0.5, 0.75, 1.0])
    return (pbin * 10 + tbin) * 2 + prints["is_up"].to_numpy().astype(int)


def stratified_auc(score: np.ndarray, y: np.ndarray, strata: np.ndarray) -> float:
    """Pooled within-stratum AUC (Mann-Whitney U summed over strata / sum n1*n0)."""
    ok = np.isfinite(score)
    if not ok.any():
        return float("nan")
    df = pd.DataFrame({"s": score[ok], "y": y[ok].astype(int), "g": strata[ok]})
    df["r"] = df.groupby("g")["s"].rank()
    df["ry"] = df["r"] * df["y"]
    agg = df.groupby("g").agg(n=("y", "size"), n1=("y", "sum"), rs=("ry", "sum"))
    n0 = agg["n"] - agg["n1"]
    u = agg["rs"] - agg["n1"] * (agg["n1"] + 1) / 2
    den = agg["n1"] * n0
    valid = den > 0
    return float(u[valid].sum() / den[valid].sum()) if valid.any() else float("nan")


def match_test(
    fit_prints: pd.DataFrame,
    test_prints: pd.DataFrame,
    wallet: str,
    spot: SpotIndex,
    test_blocks: list[tuple[int, int]],
    duration_s: int,
    score_fns: dict[str, Any] | None = None,
    lags: list[int] | None = None,
    n_perm: int = 200,
    seed: int = 0,
    n_price_bins: int = 50,
) -> dict[str, Any]:
    """Walk-forward decision-level match test of a spot hypothesis vs. the wallet.

    FIT chooses the score (one of ``score_fns``) and its latency by
    stratified AUC, and the decision threshold theta by MCC. TEST (later,
    untouched) measures the stratified AUC of the fitted score for which
    prints are the wallet's, against a rotation null (:func:`rotation_shifts`):
    every print keeps its price, time in window and side and is scored on
    another real spot path of the same block. Under "the wallet ignores spot
    beyond those static features" the observed and rotated statistics are
    exchangeable. Effect size is the rule's recall and lift at theta.
    """
    score_fns = score_fns or {"fair_minus_price": score_prints}
    lags = lags if lags is not None else [-10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 20]
    w = wallet.lower()
    y_fit = (fit_prints["wallet"] == w).to_numpy().astype(int)
    g_fit = match_strata(fit_prints, n_price_bins)
    lag_scan: dict[str, float] = {}
    for name, fn in score_fns.items():
        for L in lags:
            lag_scan[f"{name}@{L}"] = stratified_auc(fn(fit_prints, spot, L), y_fit, g_fit)
    eligible = [k for k in lag_scan if int(k.rsplit("@", 1)[1]) >= 0 and np.isfinite(lag_scan[k])]
    best = max(eligible, key=lambda k: lag_scan[k]) if eligible else f"{next(iter(score_fns))}@0"
    best_name, best_lag = best.rsplit("@", 1)[0], int(best.rsplit("@", 1)[1])
    fn = score_fns[best_name]
    s_fit = fn(fit_prints, spot, best_lag)
    theta = fit_theta(s_fit, y_fit)
    y_te = (test_prints["wallet"] == w).to_numpy().astype(int)
    g_te = match_strata(test_prints, n_price_bins)
    s_te = fn(test_prints, spot, best_lag)
    auc_te = stratified_auc(s_te, y_te, g_te)
    dm = decision_metrics(s_te, y_te, theta)
    bid, widx, nwin = window_positions(test_prints, test_blocks, duration_s)
    rng = np.random.default_rng(seed)
    null_auc, null_finite = [], []
    for _ in range(n_perm):
        sh = rotation_shifts(bid, widx, nwin, rng) * duration_s
        sp = fn(test_prints, spot, best_lag, shift=sh)
        null_finite.append(float(np.isfinite(sp).mean()) if len(sp) else float("nan"))
        null_auc.append(stratified_auc(sp, y_te, g_te))
    null_auc = np.array([x for x in null_auc if np.isfinite(x)])
    w_scores = s_te[(y_te == 1) & np.isfinite(s_te)]
    o_scores = s_te[(y_te == 0) & np.isfinite(s_te)]
    p = permutation_pvalue(auc_te, null_auc) if len(null_auc) else None
    recall_ok = bool(np.isfinite(dm["recall"]) and dm["recall"] >= MATCH_MIN_RECALL)
    lift_ok = bool(np.isfinite(dm["lift"]) and dm["lift"] >= MATCH_MIN_LIFT)
    return {
        "lag_scan_auc_fit": lag_scan,
        "chosen_score": best_name,
        "chosen_latency_s": int(best_lag),
        "theta": theta,
        "fit": {"prints": int(len(fit_prints)), "wallet_prints": int(y_fit.sum()), "auc": lag_scan[best]},
        "test": {
            "prints": int(len(test_prints)),
            "wallet_prints": int(y_te.sum()),
            "auc": auc_te,
            "auc_unstratified": auc(s_te, y_te),
            "auc_null_mean": float(null_auc.mean()) if len(null_auc) else None,
            "auc_null_p95": float(np.percentile(null_auc, 95)) if len(null_auc) else None,
            "auc_null_max": float(null_auc.max()) if len(null_auc) else None,
            "auc_null_sd": float(null_auc.std(ddof=1)) if len(null_auc) > 1 else None,
            "auc_z_vs_null": float((auc_te - null_auc.mean()) / null_auc.std(ddof=1)) if len(null_auc) > 1 and null_auc.std(ddof=1) > 0 else None,
            "auc_perm_p": p,
            "score_finite_share": float(np.isfinite(s_te).mean()) if len(s_te) else None,
            "null_finite_share_min": float(np.nanmin(null_finite)) if null_finite else None,
            "decision": dm,
            "wallet_mean_score": float(w_scores.mean()) if len(w_scores) else None,
            "others_mean_score": float(o_scores.mean()) if len(o_scores) else None,
        },
        "criterion_6": {
            "perm_p_below_0.01": bool(p is not None and p < 0.01),
            f"recall_ge_{MATCH_MIN_RECALL}": recall_ok,
            f"lift_ge_{MATCH_MIN_LIFT}": lift_ok,
            "pass": bool(p is not None and p < 0.01 and recall_ok and lift_ok),
        },
        "null": "within-block window rotation, stratified by price x time-in-window x side",
        "n_perm": n_perm,
    }


# ----------------------------------------------------------------------------- backtest
def backtest(
    prints: pd.DataFrame,
    spot: SpotIndex,
    theta: float,
    latency: int,
    size_cap_usd: float = 25.0,
    capture: float = 1.0,
    exclude_wallet: str | None = None,
) -> dict[str, Any]:
    """PIT backtest of LA(theta, latency) on observed taker liquidity.

    For each taker BUY print (liquidity that traded at ``price``) the rule
    decides with spot available at ts - latency. Selected prints are bought at
    the print price for min(size, cap) USD, scaled by ``capture`` (share of
    contested liquidity we would win), paying the taker fee. Settlement uses
    the resolved payout, which the decision never sees.
    """
    p = prints[prints["up_payout"].notna()].copy()
    if exclude_wallet:
        p = p[p["wallet"] != exclude_wallet.lower()]
    p["edge"] = score_prints(p, spot, latency)
    sel = p[np.isfinite(p["edge"]) & (p["edge"] > theta)].copy()
    if sel.empty:
        return {"trades": 0}
    usd = np.minimum(sel["size"] * sel["price"], size_cap_usd) * capture
    shares = usd / sel["price"]
    payout = np.where(sel["is_up"], sel["up_payout"], 1 - sel["up_payout"])
    fee = taker_fee_per_share(sel["price"].to_numpy(), 1.0) * sel["fee_rate"].to_numpy() * shares
    pnl = shares * payout - usd - fee
    sel["pnl"] = pnl
    sel["usd"] = usd
    sel["day"] = pd.to_datetime(sel["end_ts"], unit="s", utc=True).dt.floor("D")
    daily = sel.groupby("day")["pnl"].sum()
    per_window = sel.groupby("condition_id")["pnl"].sum()
    t = hac_t_test(per_window.to_numpy())
    boot = stationary_bootstrap_pvalue(per_window.to_numpy(), n_boot=3000)
    return {
        "trades": int(len(sel)),
        "windows": int(sel["condition_id"].nunique()),
        "usd_traded": float(usd.sum()),
        "pnl": float(pnl.sum()),
        "fees": float(fee.sum()),
        "return_on_traded": float(pnl.sum() / usd.sum()),
        "win_rate": float((payout > 0.5).mean()),
        "per_window_mean": float(per_window.mean()),
        "per_window_hac_t": t.statistic,
        "per_window_p": t.p_value,
        "per_window_bootstrap_p": boot.p_value,
        "daily_pnl": {str(k.date()): float(v) for k, v in daily.items()},
        "daily_sharpe_annual": sharpe(daily.to_numpy()) if len(daily) > 2 else None,
    }


def wallet_replay(prints: pd.DataFrame, wallet: str) -> dict[str, Any]:
    """Actual outcome of the wallet's own taker buys on the same prints (original strategy)."""
    p = prints[(prints["wallet"] == wallet.lower()) & prints["up_payout"].notna()].copy()
    if p.empty:
        return {"trades": 0}
    payout = np.where(p["is_up"], p["up_payout"], 1 - p["up_payout"])
    usd = p["size"] * p["price"]
    fee = taker_fee_per_share(p["price"].to_numpy(), 1.0) * p["fee_rate"].to_numpy() * p["size"]
    pnl = p["size"] * payout - usd - fee
    per_window = pd.Series(pnl.to_numpy(), index=p["condition_id"]).groupby(level=0).sum()
    t = hac_t_test(per_window.to_numpy())
    return {
        "trades": int(len(p)),
        "usd_traded": float(usd.sum()),
        "pnl": float(pnl.sum()),
        "return_on_traded": float(pnl.sum() / usd.sum()),
        "per_window_hac_t": t.statistic,
        "per_window_p": t.p_value,
    }


# ----------------------------------------------------------------------------- maker (passive) hypotheses
def maker_buy_prints(full_tapes: dict[str, list[dict[str, Any]]], taker_tapes: dict[str, list[dict[str, Any]]], windows: list[Window]) -> pd.DataFrame:
    """Passive BUY fills (any wallet): full-tape rows that are not taker rows.

    These are resting bids that a taker hit; the population a directional maker
    competes in.
    """
    by_cid = {w.condition_id: w for w in windows}
    rows = []
    for cid, tape in full_tapes.items():
        w = by_cid.get(cid)
        if w is None:
            continue
        taker_keys: dict[tuple, int] = {}
        for r in taker_tapes.get(cid, []):
            k = (r.get("transactionHash"), (r.get("proxyWallet") or "").lower(), str(r.get("asset")), r.get("side"))
            taker_keys[k] = taker_keys.get(k, 0) + 1
        for r in tape:
            k = (r.get("transactionHash"), (r.get("proxyWallet") or "").lower(), str(r.get("asset")), r.get("side"))
            if taker_keys.get(k, 0) > 0:
                taker_keys[k] -= 1
                continue
            if r.get("side") != "BUY":
                continue
            asset = str(r.get("asset"))
            if asset not in (w.up_token, w.down_token):
                continue
            rows.append(
                {
                    "condition_id": cid,
                    "ts": int(r["timestamp"]),
                    "wallet": (r.get("proxyWallet") or "").lower(),
                    "is_up": asset == w.up_token,
                    "price": snap_price(float(r["price"])),
                    "size": float(r["size"]),
                    "start_ts": w.start_ts,
                    "end_ts": w.end_ts,
                    "twap": w.twap_seconds,
                    "fee_rate": w.fee_rate,
                    "up_payout": w.up_payout,
                }
            )
    return pd.DataFrame(rows)


def taker_flow(taker_tapes: dict[str, list[dict[str, Any]]], windows: list[Window]) -> pd.DataFrame:
    """Every taker print (BUY and SELL) used by the trade-through fill model."""
    by_cid = {w.condition_id: w for w in windows}
    rows = []
    for cid, tape in taker_tapes.items():
        w = by_cid.get(cid)
        if w is None:
            continue
        for r in tape:
            asset = str(r.get("asset"))
            if asset not in (w.up_token, w.down_token):
                continue
            rows.append({"condition_id": cid, "ts": int(r["timestamp"]), "is_up": asset == w.up_token, "side": r.get("side"), "price": snap_price(float(r["price"])), "size": float(r["size"])})
    return pd.DataFrame(rows)


def quote_price(x: np.ndarray | float, tick: float | None = None) -> np.ndarray:
    """Highest valid bid at or below ``x``.

    ``tick=None`` applies the exchange's dynamic tick: 0.01 between 0.04 and
    0.96, 0.001 outside (mid-range tape prices sit on the cent grid 96% of the
    time; Gamma's ``orderPriceMinTickSize`` is read after resolution, at an
    extreme price, so it reports 0.001).
    """
    x = np.asarray(x, dtype=float)
    if tick is not None:
        return np.floor(x / tick + 1e-9) * tick
    q01 = np.floor(x / 0.01 + 1e-9) * 0.01
    q001 = np.floor(x / 0.001 + 1e-9) * 0.001
    return np.where((q001 < 0.04) | (q001 > 0.96), q001, q01)


def _valid_quote(q: np.ndarray, tick: float | None) -> np.ndarray:
    lo = 0.001 if tick is None else tick
    return (q >= lo - 1e-12) & (q <= 1 - lo + 1e-12)


def maker_backtest(
    flow: pd.DataFrame,
    windows: list[Window],
    spot: SpotIndex,
    delta: float,
    latency: int,
    requote_s: int = 5,
    size_shares: float = 20.0,
    tick: float | None = None,
    min_secs_to_end: int = 0,
    queue_share: float = 1.0,
    rebate_share_of_fee_equiv: float = 0.0,
    at_touch: bool = False,
) -> dict[str, Any]:
    """PIT backtest of a slow directional maker (vectorized).

    ``at_touch=True`` is the optimistic bound: prints *at* the bid also fill it
    (as if our order were first in the queue).

    Every ``requote_s`` seconds (from window start until ``min_secs_to_end``
    before the end) the strategy computes fair values with spot that is
    ``latency`` seconds old and rests BUY bids at floor((fair - delta)/tick)*tick
    on each side, ``size_shares`` each, until the next requote. A bid at q on
    side s fills only on a later taker print in (t0, t0 + requote_s] that
    trades *through* it: a taker SELL of s below q, or a taker BUY of the other
    side above 1 - q (complementary mint). Fill = min(size, print size *
    queue_share). No taker fee; maker rebates excluded unless
    ``rebate_share_of_fee_equiv`` > 0. Equivalent to
    :func:`_maker_backtest_reference` (tested).
    """
    by_cid = {w.condition_id: w for w in windows}
    if flow.empty:
        return {"fills": 0}
    out = []
    for cid, g in flow.groupby("condition_id"):
        w = by_cid[cid]
        if w.up_payout is None:
            continue
        ticks = np.arange(w.start_ts, w.end_ts - min_secs_to_end, requote_s)
        if len(ticks) == 0:
            continue
        fu = fair_up_vectorized(spot, np.full(len(ticks), w.start_ts), np.full(len(ticks), w.end_ts), ticks - latency, w.twap_seconds)
        ts = g["ts"].to_numpy().astype(np.int64)
        j = (ts - w.start_ts - 1) // requote_s  # print in (t0, t0 + R] belongs to tick j
        ok = (ts > w.start_ts) & (j >= 0) & (j < len(ticks))
        if not ok.any():
            continue
        j, is_up = j[ok], g["is_up"].to_numpy()[ok]
        sell = (g["side"].to_numpy()[ok] == "SELL")
        buy = (g["side"].to_numpy()[ok] == "BUY")
        price, size = g["price"].to_numpy()[ok], g["size"].to_numpy()[ok]
        for side_up in (True, False):
            fair = fu if side_up else 1 - fu
            q = quote_price(fair - delta, tick)
            valid = np.isfinite(fu) & _valid_quote(q, tick)
            qj = q[j]
            eps = -1e-9 if at_touch else 1e-9
            through = ((is_up == side_up) & sell & (price < qj - eps)) | ((is_up != side_up) & buy & (price > 1 - qj + eps))
            avail = np.bincount(j[through], weights=size[through], minlength=len(ticks)) * queue_share
            filled = np.where(valid, np.minimum(size_shares, avail), 0.0)
            idx = np.nonzero(filled > 0)[0]
            if len(idx) == 0:
                continue
            payout = w.up_payout if side_up else 1 - w.up_payout
            rebate = rebate_share_of_fee_equiv * w.fee_rate * q[idx] * (1 - q[idx]) * filled[idx]
            for k, t0 in enumerate(ticks[idx]):
                i = idx[k]
                out.append({"condition_id": cid, "ts": int(t0), "is_up": side_up, "price": float(q[i]), "shares": float(filled[i]), "pnl": float(filled[i] * (payout - q[i]) + rebate[k]), "fair": float(fair[i]), "end_ts": w.end_ts})
    return _maker_summary(out)


def spot_reactive_maker_backtest(
    flow: pd.DataFrame,
    windows: list[Window],
    spot: SpotIndex,
    theta: float,
    delta: float,
    latency: int,
    horizon: int = 2,
    requote_s: int = 1,
    size_shares: float = 20.0,
    tick: float | None = None,
    min_secs_to_end: int = 0,
    queue_share: float = 1.0,
    at_touch: bool = False,
    match_slack: int = 0,
) -> dict[str, Any]:
    """PIT backtest of hypothesis SR as a strategy: quote only after spot moves.

    Every ``requote_s`` seconds, with information ``latency`` seconds old, the
    strategy reads the spot log return over the last ``horizon`` seconds. It
    rests a bid on Up only if that return exceeds ``theta`` (on Down only if it
    is below ``-theta``), at the side's last public tape price minus ``delta``
    (implied from taker prints known by then). Fills follow the same
    trade-through rule as :func:`maker_backtest` (``at_touch`` is the
    first-in-queue bound). Windows without fills count as zero PnL.

    ``match_slack``: tape timestamps are block times, so a print stamped T was
    matched somewhere in [T - slack, T]. With ``match_slack=2`` each print is
    attributed to the order that was live at its earliest possible match
    time, so an order can never be filled by a trade that may have happened
    before it was placed (the conservative, correct choice for Polygon's ~2 s
    blocks).
    """
    by_cid = {w.condition_id: w for w in windows}
    out = []
    windows_seen = []
    for cid, g in flow.groupby("condition_id"):
        w = by_cid[cid]
        if w.up_payout is None:
            continue
        windows_seen.append(cid)
        g = g.sort_values("ts", kind="stable")
        ticks = np.arange(w.start_ts, w.end_ts - min_secs_to_end, requote_s)
        if len(ticks) == 0:
            continue
        ts = g["ts"].to_numpy().astype(np.int64)
        is_up = g["is_up"].to_numpy()
        price, size = g["price"].to_numpy(), g["size"].to_numpy()
        side_s = g["side"].to_numpy()
        implied_up = np.where(is_up, price, 1 - price)
        k = np.searchsorted(ts, ticks - latency, side="right") - 1
        anchor_up = np.where(k >= 0, implied_up[np.clip(k, 0, None)], np.nan)
        t_dec = ticks - latency
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.log(spot.price_at(t_dec) / spot.price_at(t_dec - horizon))
        tm = ts - match_slack
        j = (tm - w.start_ts - 1) // requote_s
        ok = (tm > w.start_ts) & (j >= 0) & (j < len(ticks))
        if not ok.any():
            continue
        j, iu, sell, buy = j[ok], is_up[ok], side_s[ok] == "SELL", side_s[ok] == "BUY"
        pr, sz = price[ok], size[ok]
        eps = -1e-9 if at_touch else 1e-9
        for side_up in (True, False):
            gate = (r > theta) if side_up else (r < -theta)
            anchor = anchor_up if side_up else 1 - anchor_up
            q = quote_price(anchor - delta, tick)
            valid = gate & np.isfinite(r) & np.isfinite(anchor) & _valid_quote(q, tick)
            qj = q[j]
            through = ((iu == side_up) & sell & (pr < qj - eps)) | ((iu != side_up) & buy & (pr > 1 - qj + eps))
            avail = np.bincount(j[through], weights=sz[through], minlength=len(ticks)) * queue_share
            filled = np.where(valid, np.minimum(size_shares, avail), 0.0)
            payout = w.up_payout if side_up else 1 - w.up_payout
            for i in np.nonzero(filled > 0)[0]:
                out.append({"condition_id": cid, "ts": int(ticks[i]), "is_up": side_up, "price": float(q[i]), "shares": float(filled[i]), "pnl": float(filled[i] * (payout - q[i])), "fair": float("nan"), "end_ts": w.end_ts})
    res = _maker_summary(out)
    if res.get("fills"):
        f = pd.DataFrame(out)
        per_window = f.groupby("condition_id")["pnl"].sum().reindex(windows_seen, fill_value=0.0)
        t = hac_t_test(per_window.to_numpy())
        res.update({"windows_total": len(windows_seen), "per_window_t_incl_zero": t.statistic, "per_window_p_incl_zero": t.p_value,
                    "per_window_bootstrap_p_incl_zero": stationary_bootstrap_pvalue(per_window.to_numpy(), n_boot=2000).p_value})
    return res


def fixed_price_ladder_backtest(flow: pd.DataFrame, windows: list[Window], price: float, side_up: bool, requote_s: int = 5, size_shares: float = 20.0) -> dict[str, Any]:
    """A resting bid at a fixed ``price`` on one side for the whole window (no data at all).

    Tests the hypothesis "the wallet simply leaves deep bids for panic sellers";
    same trade-through fills as :func:`maker_backtest`, one ``size_shares`` bid
    per ``requote_s`` interval.
    """
    by_cid = {w.condition_id: w for w in windows}
    out = []
    for cid, g in flow.groupby("condition_id"):
        w = by_cid.get(cid)
        if w is None or w.up_payout is None:
            continue
        ts = g["ts"].to_numpy().astype(np.int64)
        j = (ts - w.start_ts - 1) // requote_s
        n_ticks = int(np.ceil((w.end_ts - w.start_ts) / requote_s))
        ok = (ts > w.start_ts) & (j >= 0) & (j < n_ticks)
        iu, sd, pr, sz = g["is_up"].to_numpy()[ok], g["side"].to_numpy()[ok], g["price"].to_numpy()[ok], g["size"].to_numpy()[ok]
        through = ((iu == side_up) & (sd == "SELL") & (pr < price - 1e-9)) | ((iu != side_up) & (sd == "BUY") & (pr > 1 - price + 1e-9))
        avail = np.bincount(j[ok][through], weights=sz[through], minlength=n_ticks)
        filled = np.minimum(size_shares, avail)
        payout = w.up_payout if side_up else 1 - w.up_payout
        for i in np.nonzero(filled > 0)[0]:
            out.append({"condition_id": cid, "ts": int(w.start_ts + i * requote_s), "is_up": side_up, "price": price, "shares": float(filled[i]), "pnl": float(filled[i] * (payout - price)), "fair": float("nan"), "end_ts": w.end_ts})
    return _maker_summary(out)


def _maker_summary(out: list[dict[str, Any]]) -> dict[str, Any]:
    if not out:
        return {"fills": 0}
    f = pd.DataFrame(out)
    per_window = f.groupby("condition_id")["pnl"].sum()
    day = pd.to_datetime(f["end_ts"], unit="s", utc=True).dt.floor("D")
    daily = f.groupby(day)["pnl"].sum()
    t = hac_t_test(per_window.to_numpy())
    usd = float((f["price"] * f["shares"]).sum())
    return {
        "fills": int(len(f)),
        "windows": int(per_window.size),
        "usd_bought": usd,
        "pnl": float(f["pnl"].sum()),
        "return_on_bought": float(f["pnl"].sum() / usd) if usd else None,
        "per_window_mean": float(per_window.mean()),
        "per_window_t": t.statistic,
        "per_window_p": t.p_value,
        "per_window_bootstrap_p": stationary_bootstrap_pvalue(per_window.to_numpy(), n_boot=2000).p_value if per_window.size >= 5 else None,
        "daily_pnl": {str(k.date()): float(v) for k, v in daily.items()},
        "fill_win_rate": float((f["pnl"] > 0).mean()),
    }


def _maker_backtest_reference(
    flow: pd.DataFrame,
    windows: list[Window],
    spot: SpotIndex,
    delta: float,
    latency: int,
    requote_s: int = 5,
    size_shares: float = 20.0,
    tick: float | None = None,
    min_secs_to_end: int = 0,
    queue_share: float = 1.0,
    rebate_share_of_fee_equiv: float = 0.0,
) -> dict[str, Any]:
    """PIT backtest of a slow directional maker.

    Every ``requote_s`` seconds (from window start until ``min_secs_to_end``
    before the end) the strategy computes fair values with spot that is
    ``latency`` seconds old and rests BUY bids at floor((fair - delta)/tick)*tick
    on each side, ``size_shares`` each, until the next requote. A bid at q on
    side s fills only on a later taker print that trades *through* it: a taker
    SELL of s at price < q, or a taker BUY of the other side at price > 1 - q
    (complementary mint). Fill size = min(remaining, print size * queue_share).
    No taker fee; maker rebates excluded unless ``rebate_share_of_fee_equiv`` > 0.
    """
    by_cid = {w.condition_id: w for w in windows}
    if flow.empty:
        return {"fills": 0}
    out = []
    for cid, g in flow.groupby("condition_id"):
        w = by_cid[cid]
        if w.up_payout is None:
            continue
        g = g.sort_values("ts")
        ticks = np.arange(w.start_ts, w.end_ts - min_secs_to_end, requote_s)
        if len(ticks) == 0:
            continue
        fu = fair_up_vectorized(spot, np.full(len(ticks), w.start_ts), np.full(len(ticks), w.end_ts), ticks - latency, w.twap_seconds)
        ts_arr = g["ts"].to_numpy()
        for i, t0 in enumerate(ticks):
            if not np.isfinite(fu[i]):
                continue
            t1 = t0 + requote_s
            lo, hi = np.searchsorted(ts_arr, t0, side="right"), np.searchsorted(ts_arr, t1, side="right")
            if hi <= lo:
                continue
            seg = g.iloc[lo:hi]
            for is_up, fair in ((True, fu[i]), (False, 1 - fu[i])):
                q = float(quote_price(fair - delta, tick))
                if not bool(_valid_quote(np.array([q]), tick)[0]):
                    continue
                through_sell = seg[(seg["is_up"] == is_up) & (seg["side"] == "SELL") & (seg["price"] < q - 1e-9)]
                through_mint = seg[(seg["is_up"] != is_up) & (seg["side"] == "BUY") & (seg["price"] > 1 - q + 1e-9)]
                avail = float(through_sell["size"].sum() + through_mint["size"].sum()) * queue_share
                filled = min(size_shares, avail)
                if filled <= 0:
                    continue
                payout = w.up_payout if is_up else 1 - w.up_payout
                rebate = rebate_share_of_fee_equiv * w.fee_rate * q * (1 - q) * filled
                out.append({"condition_id": cid, "ts": int(t0), "is_up": is_up, "price": q, "shares": filled, "pnl": filled * (payout - q) + rebate, "fair": fair, "end_ts": w.end_ts})
    if not out:
        return {"fills": 0}
    f = pd.DataFrame(out)
    per_window = f.groupby("condition_id")["pnl"].sum()
    day = pd.to_datetime(f["end_ts"], unit="s", utc=True).dt.floor("D")
    daily = f.groupby(day)["pnl"].sum()
    t = hac_t_test(per_window.to_numpy())
    usd = float((f["price"] * f["shares"]).sum())
    return {
        "fills": int(len(f)),
        "windows": int(per_window.size),
        "usd_bought": usd,
        "pnl": float(f["pnl"].sum()),
        "return_on_bought": float(f["pnl"].sum() / usd) if usd else None,
        "per_window_mean": float(per_window.mean()),
        "per_window_t": t.statistic,
        "per_window_p": t.p_value,
        "per_window_bootstrap_p": stationary_bootstrap_pvalue(per_window.to_numpy(), n_boot=2000).p_value if per_window.size >= 5 else None,
        "daily_pnl": {str(k.date()): float(v) for k, v in daily.items()},
        "fill_win_rate": float((f["pnl"] > 0).mean()),
    }
