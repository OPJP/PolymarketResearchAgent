"""Shared helpers for the independent stage-A1 re-check.

* The repository cache (.cache/http.sqlite) is opened strictly read-only
  (sqlite URI mode=ro); nothing inside the repository is written.
* New network fetches go to a scratch cache under this directory.
* All statistics below are re-implemented here (numpy/scipy/statsmodels), not
  imported from polyrea.stats or polyrea.workflows.screen.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
import zlib
from pathlib import Path

import numpy as np
from scipy import stats

REPO = Path("/home/user/PolymarketResearchAgent")
HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
AS_OF = 1793318400  # frozen as_of recorded in stage_a1.json evidence.subject.as_of
DATA_API = "https://data-api.polymarket.com"


# --------------------------------------------------------------------------- cache access
class RepoCacheRO:
    def __init__(self):
        p = REPO / ".cache" / "http.sqlite"
        try:
            self.db = sqlite3.connect(f"file:{p}?mode=ro", uri=True, check_same_thread=False, timeout=60)
            self.db.execute("select count(*) from responses where 0").fetchall()
        except sqlite3.OperationalError:
            self.db = sqlite3.connect(f"file:{p}?mode=ro&immutable=1", uri=True, check_same_thread=False)

    def get_raw(self, url: str, method: str = "GET", payload: str = ""):
        key = hashlib.sha256(f"{method} {url} {payload}".encode()).hexdigest()
        row = self.db.execute("select fetched_at, body from responses where key=?", (key,)).fetchone()
        if row is None:
            return None
        return row[0], zlib.decompress(row[1])


class LayeredCache:
    """get: scratch cache first, then the repo cache (read-only). put: scratch only."""

    def __init__(self, scratch_dir: Path):
        from polyrea.adapters.http import ResponseCache

        self.scratch = ResponseCache(scratch_dir / "http.sqlite")
        self.repo = RepoCacheRO()

    def get(self, key, max_age):
        hit = self.scratch.get(key, max_age)
        if hit is not None:
            return hit
        row = self.repo.db.execute("select fetched_at, body from responses where key=?", (key,)).fetchone()
        if row is None:
            return None
        if max_age is not None and time.time() - row[0] > max_age:
            return None
        return row[0], zlib.decompress(row[1])

    def put(self, key, url, status, body):
        self.scratch.put(key, url, status, body)


def make_pm(fresh_only: bool = False):
    """PolymarketData whose HTTP client never writes into the repository."""
    from polyrea.adapters.http import HttpClient
    from polyrea.adapters.polymarket import PolymarketData

    sd = HERE / ("cache_fresh" if fresh_only else "cache")
    sd.mkdir(exist_ok=True)
    http = HttpClient(cache_dir=sd)
    if not fresh_only:
        http.cache = LayeredCache(sd)
    return PolymarketData(http)


def user_pnl_url(w: str) -> str:
    return f"{DATA_API}/v2/user-pnl?user={w.lower()}&interval=all&fidelity=1d"


# --------------------------------------------------------------------------- daily series (own construction)
def daily_pnl(points: list[dict], as_of: int = AS_OF, field: str = "economic_pnl"):
    """Daily PnL from the cumulative series.

    Own construction: keep complete-day (00:00 UTC) points stamped <= as_of, map
    each to the day it closes (stamp - 1 day), carry the last level over days
    without a point, and difference. The first level is the starting point, so
    the first difference is taken from day 2 on. Returns (days[], values[]).
    """
    lv: dict[int, float] = {}
    for p in points:
        ts = int(p["timestamp"])
        if ts > as_of or ts % 86400:
            continue
        v = p.get(field)
        if v is None:
            continue
        lv[ts // 86400] = float(v)  # later duplicates overwrite
    if not lv:
        return np.array([], dtype=int), np.array([])
    d0, d1 = min(lv), max(lv)
    levels = []
    last = 0.0
    for d in range(d0, d1 + 1):
        if d in lv:
            last = lv[d]
        levels.append(last)
    levels = np.asarray(levels)
    days = np.arange(d0 + 1, d1 + 1)  # stamp day label (same labelling as the project)
    return days, np.diff(levels)


def nonmidnight_count(points, as_of=AS_OF):
    return sum(1 for p in points if int(p["timestamp"]) <= as_of and int(p["timestamp"]) % 86400)


# --------------------------------------------------------------------------- statistics (own)
def nw_lags(n: int) -> int:
    return max(1, int(math.floor(4 * (n / 100.0) ** (2.0 / 9.0))))


def hac_t(x: np.ndarray, lags: int | None = None):
    """One-sided Newey-West t-test of mean>0 via statsmodels OLS on a constant (no small-sample correction)."""
    import statsmodels.api as sm

    x = np.asarray(x, float)
    n = len(x)
    if n < 5:
        return float("nan"), 1.0
    L = nw_lags(n) if lags is None else lags
    if np.all(x == x[0]):
        return (float("inf") if x[0] > 0 else float("nan")), (0.0 if x[0] > 0 else 1.0)
    res = sm.OLS(x, np.ones((n, 1))).fit(cov_type="HAC", cov_kwds={"maxlags": L, "use_correction": False})
    t = float(res.tvalues[0])
    return t, float(stats.t.sf(t, df=n - 1))


def hac_t_manual(x: np.ndarray, lags: int | None = None):
    """Second, numpy-only implementation (autocovariances via np.correlate) as a cross-check."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 5:
        return float("nan"), 1.0
    L = nw_lags(n) if lags is None else lags
    e = x - x.mean()
    ac = np.correlate(e, e, mode="full")[n - 1 :] / n
    w = 1 - np.arange(1, L + 1) / (L + 1)
    s = ac[0] + 2 * np.sum(w * ac[1 : L + 1])
    se = math.sqrt(max(s, 1e-300) / n)
    t = x.mean() / se
    return float(t), float(stats.t.sf(t, df=n - 1))


def stationary_bootstrap_p(x: np.ndarray, n_boot: int = 20000, mean_block: float | None = None, seed: int = 12345):
    """Politis-Romano stationary bootstrap, null imposed by centering; p=(1+#{mean*>=obs})/(B+1).

    Implemented by drawing geometric block lengths and wrapping blocks (not the
    project's per-step coin flip), so it is an independent implementation.
    """
    x = np.asarray(x, float)
    n = len(x)
    if n < 5:
        return 1.0
    b = mean_block or max(2.0, n ** (1 / 3))
    rng = np.random.default_rng(seed)
    c = x - x.mean()
    obs = x.mean()
    cc = np.concatenate([c, c])  # wrap-around
    cs = np.concatenate([[0.0], np.cumsum(cc)])
    sums = np.zeros(n_boot)
    filled = np.zeros(n_boot, dtype=int)
    while True:
        need = filled < n
        if not need.any():
            break
        k = int(need.sum())
        start = rng.integers(0, n, k)
        ln = rng.geometric(1.0 / b, k)
        ln = np.minimum(ln, n - filled[need])
        sums[need] += cs[start + ln] - cs[start]
        filled[need] += ln
    means = sums / n
    return float((1 + np.sum(means >= obs)) / (n_boot + 1))


def ann_sharpe(x):
    x = np.asarray(x, float)
    if len(x) < 2:
        return float("nan")
    sd = x.std(ddof=1)
    if sd == 0:
        return float("inf") if x.mean() > 0 else float("nan")
    return float(x.mean() / sd * math.sqrt(365))


def deflated_sharpe(x, n_trials: int = 500):
    """Bailey & Lopez de Prado DSR: PSR against E[max of N null SRs], null SR std 1/sqrt(T-1)."""
    x = np.asarray(x, float)
    T = len(x)
    if T < 5 or x.std(ddof=1) == 0:
        return float("nan")
    sr = x.mean() / x.std(ddof=1)
    g = 0.5772156649015329
    sd0 = 1 / math.sqrt(T - 1)
    sr0 = sd0 * ((1 - g) * stats.norm.ppf(1 - 1 / n_trials) + g * stats.norm.ppf(1 - 1 / (n_trials * math.e)))
    skew = stats.skew(x)
    kurt = stats.kurtosis(x, fisher=False)
    den = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr**2))
    return float(stats.norm.cdf((sr - sr0) * math.sqrt(T - 1) / den)), float(sr0)


def blocks_back(x, size):
    x = np.asarray(x, float)
    k = len(x) // size
    if k == 0:
        return np.array([])
    return x[len(x) - k * size :].reshape(k, size).sum(axis=1)[::-1]  # most recent first


def holm(p):
    p = np.asarray(p, float)
    m = len(p)
    o = np.argsort(p, kind="mergesort")
    adj = np.minimum(1.0, np.maximum.accumulate((m - np.arange(m)) * p[o]))
    out = np.empty(m)
    out[o] = adj
    return out


def screen_metrics(x: np.ndarray, sel: int = 30, boot: bool = True, n_boot: int = 20000):
    """All stage-A1 metrics from a daily PnL vector (oldest first)."""
    x = np.asarray(x, float)
    n = len(x)
    pre = x[: max(0, n - sel)]
    months = blocks_back(x, 30)
    weeks = blocks_back(x, 7)
    t_pre, p_pre = hac_t(pre)
    t_pre_m, p_pre_m = hac_t_manual(pre)
    dsr = deflated_sharpe(x)
    out = {
        "n": n,
        "pre_days": len(pre),
        "t_pre": t_pre,
        "p_pre": p_pre,
        "p_pre_manual": p_pre_m,
        "p_boot_pre": stationary_bootstrap_p(pre, n_boot=n_boot) if (boot and len(pre) >= 5) else None,
        "dsr": dsr[0] if isinstance(dsr, tuple) else dsr,
        "dsr_sr0_daily": dsr[1] if isinstance(dsr, tuple) else None,
        "sr_daily": float(x.mean() / x.std(ddof=1)) if n > 2 and x.std(ddof=1) > 0 else None,
        "last30": float(x[-30:].sum()) if n else 0.0,
        "months": months.tolist(),
        "median6": float(np.median(months[:6])) if len(months) else None,
        "pos_months": float(np.mean(months > 0)) if len(months) else None,
        "sharpe": ann_sharpe(x),
        "pos_weeks": float(np.mean(weeks > 0)) if len(weeks) else None,
        "total": float(x.sum()),
        "zero_days": int(np.sum(x == 0)),
    }
    t_full, p_full = hac_t(x)
    out["t_full"], out["p_full"] = t_full, p_full
    return out


def reasons(m: dict, p_holm: float | None) -> list[str]:
    """Same pre-registered thresholds as the project, applied to my metrics."""
    r = []
    if m["n"] == 0:
        return ["no history"]
    if m["pre_days"] < 60:
        r.append("pre<60d")
    else:
        if p_holm is None or p_holm > 0.05:
            r.append("holm")
        if m["p_boot_pre"] is None or m["p_boot_pre"] > 0.01:
            r.append("boot")
    if m["dsr"] is None or not np.isfinite(m["dsr"]) or m["dsr"] < 0.95:
        r.append("dsr")
    if m["last30"] < 50_000:
        r.append("last30")
    if m["median6"] is None or m["median6"] < 50_000:
        r.append("median6")
    if m["pos_months"] is None or m["pos_months"] < 0.8:
        r.append("pos_months")
    if m["sharpe"] is None or not np.isfinite(m["sharpe"]) or m["sharpe"] < 3:
        r.append("sharpe")
    if m["pos_weeks"] is None or m["pos_weeks"] < 0.75:
        r.append("pos_weeks")
    return r


def load_a1():
    return json.loads((REPO / "research/stage_a/stage_a1.json").read_text())


def reason_codes(rs: list[str]) -> list[str]:
    out = []
    for r in rs:
        if r.startswith("insufficient pre-selection"):
            out.append("pre<60d")
        elif r.startswith("pre-selection profit not significant"):
            out.append("holm")
        elif r.startswith("pre-selection block-bootstrap"):
            out.append("boot")
        elif r.startswith("deflated Sharpe"):
            out.append("dsr")
        elif r.startswith("last-30d"):
            out.append("last30")
        elif r.startswith("median monthly"):
            out.append("median6")
        elif r.startswith("positive months"):
            out.append("pos_months")
        elif r.startswith("annualized Sharpe"):
            out.append("sharpe")
        elif r.startswith("positive weeks"):
            out.append("pos_weeks")
        elif r.startswith("no PnL history"):
            out.append("no history")
        else:
            out.append("?" + r)
    return out
