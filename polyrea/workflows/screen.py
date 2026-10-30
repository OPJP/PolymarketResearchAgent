"""Stage A: screen leaderboard wallets on their own on-chain PnL record.

No reverse engineering is needed here: the wallet's daily PnL stream alone
decides whether its profits are statistically distinguishable from luck and
whether they meet the size / consistency requirements. Criteria are fixed in
:data:`CRITERIA` before any wallet is examined.

Selection bias: the leaderboard ranks wallets on their last ~30 days, which
guarantees that window looks good. Significance is therefore tested on the
*pre-selection* history (all days before the ranking window) and adjusted for
testing 500 wallets at once (Holm). The deflated Sharpe ratio additionally
accounts for picking the best of many.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.pnl import daily_frame, monthly_blocks, weekly_sums
from polyrea.evidence import Coverage, Evidence, to_jsonable
from polyrea.stats import significance as S


@dataclass(frozen=True)
class Criteria:
    selection_window_days: int = 30
    min_pre_selection_days: int = 60
    max_holm_p: float = 0.05  # pre-selection HAC t-test, Holm-adjusted over all wallets
    max_bootstrap_p: float = 0.01  # pre-selection stationary bootstrap (raw)
    min_deflated_sharpe: float = 0.95  # full history, deflated for n wallets
    min_last_month_pnl: float = 50_000.0
    min_median_month_pnl: float = 50_000.0
    months_for_median: int = 6
    min_share_positive_months: float = 0.8
    min_annual_sharpe: float = 3.0
    min_share_positive_weeks: float = 0.75
    min_monthly_roc: float = 0.10  # PnL / peak capital at risk, evaluated in stage A2


CRITERIA = Criteria()


def wallet_pnl_metrics(points: list[dict[str, Any]], as_of: int, crit: Criteria = CRITERIA) -> dict[str, Any]:
    df = daily_frame(points, as_of=as_of)
    if df.empty or "d_economic_pnl" not in df:
        return {"history_days": 0}
    d = df["d_economic_pnl"].iloc[1:]  # first row is the starting level, not a day of PnL
    trade = df["d_trade_pnl"].iloc[1:] if "d_trade_pnl" in df else d * np.nan
    n = len(d)
    pre = d.iloc[: max(0, n - crit.selection_window_days)]
    months = monthly_blocks(d)
    recent_months = months[: crit.months_for_median]
    weeks = weekly_sums(d)
    cum = d.cumsum().to_numpy()
    income = float(df["d_wallet_income"].iloc[1:].sum()) if "d_wallet_income" in df else float("nan")
    total = float(d.sum())
    t_full = S.hac_t_test(d.to_numpy())
    t_pre = S.hac_t_test(pre.to_numpy())
    boot_pre = S.stationary_bootstrap_pvalue(pre.to_numpy(), n_boot=4000) if len(pre) >= 5 else None
    return {
        "history_days": n,
        "first_day": str(d.index.min().date()) if n else None,
        "last_day": str(d.index.max().date()) if n else None,
        "total_pnl": total,
        "total_trade_pnl": float(trade.sum()),
        "incentive_share": income / total if total > 0 else None,
        "last_30d_pnl": float(d.iloc[-30:].sum()) if n else 0.0,
        "monthly_pnl_recent_first": recent_months,
        "median_month_pnl": float(np.median(recent_months)) if recent_months else None,
        "share_positive_months": float(np.mean([m > 0 for m in months])) if months else None,
        "annual_sharpe": S.sharpe(d.to_numpy()),
        "annual_sharpe_pre": S.sharpe(pre.to_numpy()),
        "per_day_sharpe": float(d.mean() / d.std(ddof=1)) if n > 2 and d.std(ddof=1) > 0 else None,
        "share_positive_days": float((d > 0).mean()) if n else None,
        "share_positive_weeks": float((weeks > 0).mean()) if len(weeks) else None,
        "daily_mean": float(d.mean()) if n else None,
        "daily_std": float(d.std(ddof=1)) if n > 1 else None,
        "max_drawdown": S.max_drawdown(cum),
        "hac_t_full": t_full.statistic,
        "p_full": t_full.p_value,
        "pre_selection_days": len(pre),
        "hac_t_pre": t_pre.statistic,
        "p_pre": t_pre.p_value,
        "p_boot_pre": boot_pre.p_value if boot_pre else None,
        "volume_30d": float(df["d_volume_usdc"].iloc[-30:].sum()) if "d_volume_usdc" in df else None,
        "trades_30d": float(df["d_trade_count"].iloc[-30:].sum()) if "d_trade_count" in df else None,
        "cumulative_weekly": [float(x) for x in cum[::7]] + ([float(cum[-1])] if n else []),
    }


def apply_criteria(m: dict[str, Any], crit: Criteria = CRITERIA) -> list[str]:
    """Reasons a wallet fails stage A1 (empty list = passes)."""
    r: list[str] = []
    if m.get("history_days", 0) == 0:
        return ["no PnL history returned"]
    if m["pre_selection_days"] < crit.min_pre_selection_days:
        r.append(f"insufficient pre-selection history ({m['pre_selection_days']}d < {crit.min_pre_selection_days}d): significance outside the ranking window cannot be established")
    else:
        if m.get("p_holm_pre") is None or m["p_holm_pre"] > crit.max_holm_p:
            r.append(f"pre-selection profit not significant after Holm correction (p_holm={_fmt(m.get('p_holm_pre'))})")
        if m.get("p_boot_pre") is None or m["p_boot_pre"] > crit.max_bootstrap_p:
            r.append(f"pre-selection block-bootstrap p={_fmt(m.get('p_boot_pre'))} > {crit.max_bootstrap_p}")
    if m.get("deflated_sharpe") is None or m["deflated_sharpe"] < crit.min_deflated_sharpe:
        r.append(f"deflated Sharpe {_fmt(m.get('deflated_sharpe'))} < {crit.min_deflated_sharpe}")
    if m["last_30d_pnl"] < crit.min_last_month_pnl:
        r.append(f"last-30d PnL ${m['last_30d_pnl']:,.0f} < $50k")
    if m.get("median_month_pnl") is None or m["median_month_pnl"] < crit.min_median_month_pnl:
        r.append(f"median monthly PnL ${_fmt(m.get('median_month_pnl'), money=True)} < $50k")
    if m.get("share_positive_months") is None or m["share_positive_months"] < crit.min_share_positive_months:
        r.append(f"positive months {_fmt(m.get('share_positive_months'))} < {crit.min_share_positive_months}")
    if m.get("annual_sharpe") is None or not np.isfinite(m["annual_sharpe"]) or m["annual_sharpe"] < crit.min_annual_sharpe:
        r.append(f"annualized Sharpe {_fmt(m.get('annual_sharpe'))} < {crit.min_annual_sharpe} (returns not constant enough)")
    if m.get("share_positive_weeks") is None or m["share_positive_weeks"] < crit.min_share_positive_weeks:
        r.append(f"positive weeks {_fmt(m.get('share_positive_weeks'))} < {crit.min_share_positive_weeks}")
    return r


def _fmt(x: Any, money: bool = False) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{x:,.0f}" if money else f"{x:.3g}"


def run_screen(
    out_dir: Path,
    limit: int = 500,
    time_period: str = "month",
    workers: int = 6,
    pm: PolymarketData | None = None,
    crit: Criteria = CRITERIA,
) -> dict[str, Any]:
    pm = pm or PolymarketData()
    as_of = int(time.time()) // 86400 * 86400  # complete days only
    board, lb_sources = pm.leaderboard(time_period=time_period, limit=limit)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "leaderboard_snapshot.json").write_text(
        json.dumps({"fetched_at": int(time.time()), "time_period": time_period, "order_by": "PNL", "rows": board}, indent=1)
    )
    results: dict[str, dict[str, Any]] = {}

    def work(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        w = row["user_id"].lower()
        body, src = pm.user_pnl(w)
        m = wallet_pnl_metrics(body.get("points") or [], as_of, crit)
        m["source"] = asdict(src)
        return w, m

    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(work, row): row for row in board}
        for i, f in enumerate(as_completed(futs)):
            row = futs[f]
            try:
                w, m = f.result()
            except Exception as exc:  # recorded, never silently dropped
                w, m = row["user_id"].lower(), {"history_days": 0, "error": repr(exc)}
            results[w] = m
            if (i + 1) % 50 == 0:
                print(f"[screen] {i + 1}/{len(board)}", flush=True)

    # multiple-testing adjustment over every wallet tested (failed fetches count as p=1)
    wallets = [r["user_id"].lower() for r in board]
    p_pre = [results[w].get("p_pre", 1.0) if results[w].get("pre_selection_days", 0) >= crit.min_pre_selection_days else 1.0 for w in wallets]
    holm = S.holm_bonferroni(p_pre)
    bh = S.benjamini_hochberg(p_pre)
    srs = [results[w].get("per_day_sharpe") for w in wallets]
    sr_std = float(np.nanstd([s for s in srs if s is not None and np.isfinite(s)]))
    for w, ph, pb in zip(wallets, holm, bh):
        results[w]["p_holm_pre"] = ph
        results[w]["p_bh_pre"] = pb

    rows_out = []
    for rank_row in board:
        w = rank_row["user_id"].lower()
        m = results[w]
        if m.get("history_days", 0) > 0:
            body, _ = pm.user_pnl(w)  # cached
            df = daily_frame(body.get("points") or [], as_of=as_of)
            d = df["d_economic_pnl"].iloc[1:].to_numpy()
            m["deflated_sharpe"] = S.deflated_sharpe_ratio(d, n_trials=len(board))
        lb = float(rank_row.get("pnl") or 0.0)
        if m.get("history_days", 0) > 0:
            m["lb_vs_series_gap"] = lb - m["last_30d_pnl"]
            m["lb_series_inconsistent"] = abs(lb - m["last_30d_pnl"]) > max(25_000.0, 0.25 * abs(lb))
        reasons = apply_criteria(m, crit) if "error" not in m else [f"fetch error: {m['error']}"]
        rows_out.append(
            {
                "wallet": w,
                "name": rank_row.get("user_name"),
                "rank": rank_row.get("rank"),
                "lb_pnl": rank_row.get("pnl"),
                "lb_volume": rank_row.get("volume"),
                "stage_a1_pass": not reasons,
                "stage_a1_reasons": reasons,
                "metrics": m,
            }
        )
    ev = Evidence(
        tool="screen_leaderboard",
        subject={"kind": "leaderboard", "time_period": time_period, "limit": limit, "as_of": as_of},
        observed={"wallets": len(board)},
        derived={
            "criteria": asdict(crit),
            "a1_pass": [r["wallet"] for r in rows_out if r["stage_a1_pass"]],
            "cross_sectional_per_day_sharpe_std": sr_std,
        },
        sources=lb_sources,
        coverage=Coverage("complete" if all("error" not in results[w] for w in wallets) else "partial", f"{len(wallets)} wallets"),
        limitations=[
            "Daily PnL comes from Polymarket's v2 user-pnl index (mark-to-market incl. unrealized); trades are separately verified on-chain for wallets that pass.",
            "Leaderboard membership is itself a selection on recent PnL; significance is tested on the pre-selection history and corrected for 500 tests.",
            "Return on capital is not available from the PnL series; it is evaluated in stage A2 from reconstructed exposure.",
        ],
    )
    (out_dir / "stage_a1.json").write_text(json.dumps(to_jsonable({"evidence": ev.to_dict(), "wallets": rows_out}), indent=1))
    return {"evidence": ev, "wallets": rows_out}
