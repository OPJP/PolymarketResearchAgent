"""Daily PnL frames from Polymarket's v2 user-pnl series.

``economic_pnl`` (cumulative) = position PnL (realized + unrealized market PnL)
+ wallet income (maker/taker rebates, liquidity rewards, yield, referrals).
``trade_pnl`` excludes wallet income. Both are kept: a wallet whose profit is
mostly incentives depends on Polymarket keeping those programs.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

FIELDS = ("economic_pnl", "trade_pnl", "wallet_income", "maker_rebate", "reward_income", "fees_paid", "volume_usdc", "trade_count")


def daily_frame(points: list[dict[str, Any]], as_of: int | None = None) -> pd.DataFrame:
    """One row per complete UTC day with daily (differenced) values.

    The final point of the API series is a partial day stamped "now"; it is
    dropped so every row covers a full day. Cumulative fields are forward
    filled across days without points before differencing. ``volume_usdc`` and
    ``trade_count`` are cumulative in the source too.
    """
    if not points:
        return pd.DataFrame(columns=[f"d_{f}" for f in FIELDS])
    df = pd.DataFrame(points)
    df["ts"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    if as_of is not None:
        df = df[df["timestamp"] <= as_of]
    is_midnight = (df["timestamp"] % 86400) == 0
    df = df[is_midnight].copy()
    if df.empty:
        return pd.DataFrame(columns=[f"d_{f}" for f in FIELDS])
    df = df.set_index(df["ts"].dt.floor("D"))
    df = df[~df.index.duplicated(keep="last")]
    full = pd.date_range(df.index.min(), df.index.max(), freq="D", tz="UTC")
    out = pd.DataFrame(index=full)
    for f in FIELDS:
        if f in df:
            cum = pd.to_numeric(df[f], errors="coerce").reindex(full).ffill().fillna(0.0)
            out[f] = cum
            # value stamped at day D midnight is cumulative through end of D-1
            out[f"d_{f}"] = cum.diff().fillna(cum.iloc[0])
    # first row's diff equals its cumulative level (history start); treat start at 0
    out.index.name = "day_end"
    return out


def monthly_blocks(daily: pd.Series, block_days: int = 30) -> list[float]:
    """Sums over consecutive 30-day blocks counted back from the latest day."""
    vals = daily.to_numpy(dtype=float)
    blocks = []
    end = len(vals)
    while end - block_days >= 0:
        blocks.append(float(vals[end - block_days : end].sum()))
        end -= block_days
    return blocks  # most recent first


def weekly_sums(daily: pd.Series) -> np.ndarray:
    vals = daily.to_numpy(dtype=float)
    k = len(vals) // 7
    if k == 0:
        return np.array([])
    trimmed = vals[len(vals) - 7 * k :]
    return trimmed.reshape(k, 7).sum(axis=1)
