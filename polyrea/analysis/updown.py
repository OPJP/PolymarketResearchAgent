"""Crypto Up/Down markets: fair-value model, decision match test, PIT backtest.

Market mechanics (Gamma metadata, 2026): each market covers a window
[eventStartTime, endDate] of 5m / 15m / 1h. It resolves Up iff the Chainlink
TWAP over the last ``twapLookbackSeconds`` (60 s) of the window is >= the price
at the window start. Takers pay ``rate * p * (1 - p)`` per share (feeSchedule,
exponent 1); a share of fees is rebated to makers.

Hypothesis family LA(theta, latency): *buy the side whose spot-implied fair
value exceeds its ask by more than theta*, using spot information that is
``latency`` seconds old. The fair value uses only data available at the
decision time:

* strike S0 = spot available at window start (decisions before the window
  starts get fair value 0.5);
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
        self.cum_px = np.cumsum(self.px)

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
            return np.where(n > 0, (s_hi - s_lo) / n, np.nan)


def fair_up_vectorized(spot: SpotIndex, start: np.ndarray, end: np.ndarray, t_dec: np.ndarray, twap: int = TWAP_SECONDS) -> np.ndarray:
    """P(Up) at decision times ``t_dec`` using spot available at ``t_dec``."""
    start, end, t_dec = (np.asarray(x, dtype=np.int64) for x in (start, end, t_dec))
    s0 = spot.price_at(start)
    st = spot.price_at(t_dec)
    sig = spot.sigma_at(t_dec)
    twap_start = end - twap
    before = t_dec < twap_start
    # before TWAP period: avg ~ S_t, var = sigma^2 S^2 [(twap_start - t) + twap/3]
    var_before = (twap_start - t_dec).clip(min=0) + twap / 3.0
    # inside TWAP period: known part A over [twap_start, t), remaining r seconds
    r = (end - t_dec).clip(min=0).astype(float)
    a_known = spot.mean_between(twap_start, t_dec, t_dec)
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
    S0, St = float(s0[1]), float(st[1])
    twap_start = w.end_ts - w.twap_seconds
    if t_dec < twap_start:
        mean, sd_units = St, math.sqrt((twap_start - t_dec) + w.twap_seconds / 3.0)
    else:
        r = max(w.end_ts - t_dec, 0)
        sel = (ev >= twap_start) & (ev < t_dec) & (av <= t_dec)
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
                    "price": float(r["price"]),
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
    grid = np.linspace(-0.05, 0.15, 41) if grid is None else grid
    best, best_mcc = 0.0, -2.0
    for th in grid:
        m = decision_metrics(score, y, float(th))["mcc"]
        if np.isfinite(m) and m > best_mcc:
            best, best_mcc = float(th), m
    return best


def match_test(
    fit_prints: pd.DataFrame,
    test_prints: pd.DataFrame,
    wallet: str,
    spot: SpotIndex,
    lags: list[int] | None = None,
    n_perm: int = 200,
    seed: int = 0,
) -> dict[str, Any]:
    """Walk-forward decision-level match test of hypothesis LA vs. the wallet.

    Fit period: choose the latency (lag scan by AUC) and theta (max MCC).
    Test period (later, untouched): AUC and MCC of the fitted rule predicting
    which taker prints the wallet took, with a permutation null that shifts the
    spot clock by >= 1 hour (destroys alignment, keeps autocorrelation).
    """
    lags = lags if lags is not None else [-10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 20]
    y_fit = (fit_prints["wallet"] == wallet.lower()).to_numpy().astype(int)
    lag_scan = {}
    for L in lags:
        lag_scan[L] = auc(score_prints(fit_prints, spot, L), y_fit)
    best_lag = max((L for L in lags if L >= 0 and np.isfinite(lag_scan[L])), key=lambda L: lag_scan[L], default=0)
    s_fit = score_prints(fit_prints, spot, best_lag)
    theta = fit_theta(s_fit, y_fit)
    y_te = (test_prints["wallet"] == wallet.lower()).to_numpy().astype(int)
    s_te = score_prints(test_prints, spot, best_lag)
    auc_te = auc(s_te, y_te)
    dm = decision_metrics(s_te, y_te, theta)
    rng = np.random.default_rng(seed)
    null_auc, null_mcc = [], []
    for _ in range(n_perm):
        sh = int(rng.integers(3600, 6 * 3600)) * int(rng.choice([-1, 1]))
        sp = score_prints(test_prints, spot, best_lag, shift=sh)
        null_auc.append(auc(sp, y_te))
        null_mcc.append(decision_metrics(sp, y_te, theta)["mcc"])
    null_auc = np.array([x for x in null_auc if np.isfinite(x)])
    null_mcc = np.array([x for x in null_mcc if np.isfinite(x)])
    w_scores = s_te[(y_te == 1) & np.isfinite(s_te)]
    o_scores = s_te[(y_te == 0) & np.isfinite(s_te)]
    mw = stats.mannwhitneyu(w_scores, o_scores, alternative="greater") if len(w_scores) and len(o_scores) else None
    return {
        "lag_scan_auc_fit": {int(k): v for k, v in lag_scan.items()},
        "chosen_latency_s": int(best_lag),
        "theta": theta,
        "fit": {"prints": int(len(fit_prints)), "wallet_prints": int(y_fit.sum()), "auc": lag_scan[best_lag]},
        "test": {
            "prints": int(len(test_prints)),
            "wallet_prints": int(y_te.sum()),
            "auc": auc_te,
            "auc_null_mean": float(null_auc.mean()) if len(null_auc) else None,
            "auc_null_p95": float(np.percentile(null_auc, 95)) if len(null_auc) else None,
            "auc_perm_p": permutation_pvalue(auc_te, null_auc) if len(null_auc) else None,
            "decision": dm,
            "mcc_null_p95": float(np.percentile(null_mcc, 95)) if len(null_mcc) else None,
            "mcc_perm_p": permutation_pvalue(dm["mcc"], null_mcc) if len(null_mcc) else None,
            "wallet_mean_edge": float(w_scores.mean()) if len(w_scores) else None,
            "others_mean_edge": float(o_scores.mean()) if len(o_scores) else None,
            "share_wallet_prints_with_positive_edge": float((w_scores > 0).mean()) if len(w_scores) else None,
            "mannwhitney_p": float(mw.pvalue) if mw is not None else None,
        },
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
