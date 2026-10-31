"""How much of a wallet's profit depends on Polymarket's taker-rebate tier.

Taker Rebate Program (docs.polymarket.com/programs/taker-rebates, 2026): a
wallet's tier is set by its 30-day weighted taker volume; the rebate is a
share of the taker fees it paid, paid daily. The first time a wallet reaches a
tier it also gets a one-time level-up bonus. A replicator starting today pays
the same fees but begins at the bottom tier, and collects each bonus once, so
neither the incumbent's tier nor its bonuses are part of a replicable monthly
profit.

``position_pnl`` in the user-pnl series is market PnL after fees; maker
rebates, liquidity rewards and holding yield are open to anyone quoting the
same way and are kept.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from polyrea.analysis.pnl import daily_frame

# (name, 30-day weighted volume needed, rebate share of taker fees, one-time level-up bonus USD)
TAKER_TIERS: list[tuple[str, float, float, float]] = [
    ("None", 0.0, 0.00, 0.0),
    ("Bronze", 2_000.0, 0.03, 10.0),
    ("Silver", 20_000.0, 0.08, 50.0),
    ("Gold", 200_000.0, 0.18, 250.0),
    ("Platinum", 1_000_000.0, 0.32, 1_500.0),
    ("Diamond", 4_000_000.0, 0.44, 7_500.0),
    ("Obsidian", 10_000_000.0, 0.50, 25_000.0),
]


def _cum_daily(points: list[dict[str, Any]], field: str, as_of: int) -> np.ndarray:
    pts = [{"timestamp": p["timestamp"], "economic_pnl": float(p.get(field) or 0.0)} for p in points]
    df = daily_frame(pts, as_of=as_of)
    return df["d_economic_pnl"].iloc[1:].to_numpy() if len(df) > 1 else np.array([])


def rebate_dependence(points: list[dict[str, Any]], as_of: int, days: int = 30) -> dict[str, Any]:
    """Window PnL split into components, the observed tier, one-off bonuses, and PnL at every tier."""
    fields = ("economic_pnl", "position_pnl", "fees_paid", "taker_rebate", "maker_rebate", "reward_income", "yield_income", "referral_income")
    daily = {f: _cum_daily(points, f, as_of) for f in fields}
    n = min(len(v) for v in daily.values()) if daily else 0
    if n < 3:
        return {"days": 0}
    daily = {f: v[-n:] for f, v in daily.items()}
    win = {f: float(v[-days:].sum()) for f, v in daily.items()}
    fees = -daily["fees_paid"]  # positive USD paid
    reb = daily["taker_rebate"]
    # rebates are paid at midnight for the previous day's fees
    prev_fees = np.r_[np.nan, fees[:-1]]
    in_window = np.arange(n) >= n - days
    ok = (prev_fees > 50) & np.isfinite(prev_fees)
    recent_ok = ok & in_window
    recent = reb[recent_ok] / prev_fees[recent_ok] if recent_ok.any() else np.array([])
    rate = float(np.median(recent)) if len(recent) else 0.0
    tier = min(TAKER_TIERS, key=lambda t: abs(t[2] - rate))
    # one-off payments: rebate far above the steady rate that matches a level-up bonus
    bonuses = []
    for i in np.nonzero(in_window & np.isfinite(prev_fees))[0]:
        excess = reb[i] - rate * max(prev_fees[i], 0.0)
        if excess > max(500.0, 0.5 * rate * max(prev_fees[i], 0.0)):
            match = min(TAKER_TIERS[1:], key=lambda t: abs(t[3] - excess))
            bonuses.append({"day_index_from_end": int(n - 1 - i), "rebate": float(reb[i]), "excess": float(excess),
                            "nearest_level_up_bonus": {"tier": match[0], "usd": match[3]}, "matches_bonus": bool(abs(match[3] - excess) <= 0.1 * match[3])})
    bonus_total = float(sum(b["excess"] for b in bonuses if b["matches_bonus"]))
    base = win["position_pnl"] + win["maker_rebate"] + win["reward_income"] + win["yield_income"] + win["referral_income"]
    fees_win = -win["fees_paid"]
    at_tier = {f"{name} {int(r * 100)}%": base + r * fees_win for name, _, r, _ in TAKER_TIERS}
    return {
        "days": days,
        "window": win,
        "taker_fees_paid": fees_win,
        "observed_taker_rebate_rate_median": rate,
        "observed_tier": tier[0],
        "one_off_payments": bonuses,
        "level_up_bonus_total": bonus_total,
        "economic_pnl_recurring": win["economic_pnl"] - bonus_total,
        "pnl_at_tier": at_tier,
        "note": "pnl_at_tier = position PnL after fees + maker rebates + rewards + yield + tier rate x taker fees; level-up bonuses excluded.",
    }
