"""Behavioral profile of a wallet: what it trades, when, at what prices, and
where its money comes from.

The per-market decomposition is the core reverse-engineering fact for
buy-only wallets. For a binary market where the wallet bought ``q_up`` shares of
one outcome at average ``a_up`` and ``q_dn`` of the other at ``a_dn``:

* ``pairs = min(q_up, q_dn)`` complete sets are worth exactly $1 at resolution
  regardless of outcome -> locked PnL ``pairs * (1 - a_up - a_dn)``;
* the residual ``|q_up - q_dn|`` shares are a directional bet worth 1 or 0.

A wallet whose profit is mostly locked pair spread is a two-sided liquidity
provider; one whose profit is mostly directional residual is a predictor.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

import numpy as np
import pandas as pd


def market_family(slug: str | None, market: dict[str, Any] | None = None) -> str:
    """Coarse family used to group a wallet's markets (no outcome information)."""
    cfg = (market or {}).get("cryptoMarketConfig") or {}
    if cfg.get("asset") and cfg.get("duration"):
        return f"crypto-updown:{cfg['asset']}:{cfg['duration']}"
    s = slug or ""
    m = re.match(r"^(btc|eth|sol|xrp|bnb|doge|hype)-updown-(\d+[mhd])", s)
    if m:
        return f"crypto-updown:{m.group(1)}:{m.group(2)}"
    if re.search(r"(bitcoin|ethereum|solana|xrp|bnb)-up-or-down", s):
        return "crypto-updown:hourly-or-daily"
    if re.search(r"-(above|below|price|reach|hit)-", s) and re.search(r"(bitcoin|btc|eth|ethereum|solana)", s):
        return "crypto-price-level"
    head = s.split("-")[0]
    sports = {"nba", "nfl", "mlb", "nhl", "cfb", "cbb", "wnba", "epl", "ucl", "lal", "sea", "bun", "fl1", "uel", "mls", "atp", "wta", "itf", "ufc", "spl", "ukr1", "ukr2"}
    esports = {"cs2", "cs", "dota2", "dota", "lol", "val", "codmw"}
    if head in esports or re.match(r"^(cs\d|dota\d|lol|val)", s):
        return f"esports:{re.sub(r'\d', '', head)}"
    if head in sports or re.match(r"^(fl\d|ukr\d|spl|itf|atp|wta)", s):
        return f"sports:{re.sub(r'\d', '', head)}"
    if re.search(r"(election|governor|senate|president|republicans|democrats|win-the|nominee|out-before|primary)", s):
        return "politics"
    return "other"


def _ts(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return int(pd.Timestamp(iso).timestamp())
    except (ValueError, TypeError):
        return None


def resolution_info(market: dict[str, Any]) -> dict[str, Any]:
    """Post-hoc facts (settlement only - never used by decision code)."""
    try:
        prices = [float(x) for x in json.loads(market.get("outcomePrices") or "[]")]
        tokens = json.loads(market.get("clobTokenIds") or "[]")
    except (TypeError, ValueError):
        prices, tokens = [], []
    resolved = market.get("umaResolutionStatus") == "resolved" or (market.get("closed") and prices and max(prices) >= 0.999)
    payout = {str(t): p for t, p in zip(tokens, prices)} if resolved else {}
    closed_ts = _ts((market.get("closedTime") or "").replace(" ", "T").replace("+00", "+00:00") if market.get("closedTime") else None)
    return {"resolved": bool(resolved and payout), "payout": payout, "closed_ts": closed_ts}


def per_market_decomposition(trades: pd.DataFrame, markets: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """One row per (condition) with pair / residual decomposition and settled PnL."""
    rows = []
    for cid, g in trades.groupby("condition_id"):
        m = markets.get(cid) or {}
        res = resolution_info(m)
        by_out = g.groupby("outcome_index").agg(shares=("size", "sum"), cost=("usdc", "sum"))
        q = {int(k): float(v) for k, v in by_out["shares"].items()}
        c = {int(k): float(v) for k, v in by_out["cost"].items()}
        q0, q1 = q.get(0, 0.0), q.get(1, 0.0)
        a0 = c.get(0, 0.0) / q0 if q0 else np.nan
        a1 = c.get(1, 0.0) / q1 if q1 else np.nan
        pairs = min(q0, q1)
        tokens = json.loads(m.get("clobTokenIds") or "[]") if m else []
        pay = res["payout"]
        payout_total = None
        if res["resolved"] and len(tokens) == 2:
            payout_total = q0 * pay.get(str(tokens[0]), 0.0) + q1 * pay.get(str(tokens[1]), 0.0)
        cost_total = float(g["usdc"].sum())
        locked = pairs * (1.0 - a0 - a1) if pairs > 0 else 0.0
        resid_side = 0 if q0 > q1 else 1
        resid_q = abs(q0 - q1)
        resid_cost = resid_q * (a0 if resid_side == 0 else a1) if resid_q > 0 else 0.0
        resid_pay = None
        if payout_total is not None and len(tokens) == 2:
            resid_pay = resid_q * pay.get(str(tokens[resid_side]), 0.0)
        rows.append(
            {
                "condition_id": cid,
                "family": market_family(g["slug"].iloc[0], m),
                "slug": g["slug"].iloc[0],
                "n_fills": len(g),
                "first_ts": int(g["ts"].min()),
                "last_ts": int(g["ts"].max()),
                "q0": q0,
                "q1": q1,
                "avg0": a0,
                "avg1": a1,
                "pairs": pairs,
                "pair_cost": (a0 + a1) if pairs > 0 else np.nan,
                "two_sided": q0 > 0 and q1 > 0,
                "balance": pairs / max(q0, q1) if max(q0, q1) > 0 else np.nan,
                "cost": cost_total,
                "resolved": payout_total is not None,
                "payout": payout_total,
                "pnl": (payout_total - cost_total) if payout_total is not None else np.nan,
                "locked_pnl": locked,
                "residual_pnl": (resid_pay - resid_cost) if resid_pay is not None else np.nan,
                "residual_won": (resid_pay > 0) if resid_pay is not None and resid_q > 0 else None,
                "residual_shares": resid_q,
            }
        )
    return pd.DataFrame(rows)


def timing_features(trades: pd.DataFrame, markets: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Per-fill timing relative to the market's window / game start (static fields only)."""
    out = trades.copy()
    starts, ends, gstarts = {}, {}, {}
    for cid, m in markets.items():
        starts[cid] = _ts(m.get("eventStartTime"))
        ends[cid] = _ts(m.get("endDate"))
        gstarts[cid] = _ts(m.get("gameStartTime"))
    out["window_start"] = out["condition_id"].map(starts)
    out["window_end"] = out["condition_id"].map(ends)
    out["game_start"] = out["condition_id"].map(gstarts)
    span = out["window_end"] - out["window_start"]
    out["window_frac"] = np.where(span > 0, (out["ts"] - out["window_start"]) / span, np.nan)
    out["secs_to_end"] = out["window_end"] - out["ts"]
    out["secs_from_game_start"] = out["ts"] - out["game_start"]
    return out


def summarize_profile(trades: pd.DataFrame, per_market: pd.DataFrame, timing: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {"fills": 0}
    fam_usd = trades.assign(fam=trades["condition_id"].map(per_market.set_index("condition_id")["family"])).groupby("fam")["usdc"].sum()
    resolved = per_market[per_market["resolved"]]
    pnl = float(resolved["pnl"].sum()) if len(resolved) else 0.0
    locked = float(resolved["locked_pnl"].sum()) if len(resolved) else 0.0
    resid = float(resolved["residual_pnl"].sum()) if len(resolved) else 0.0
    wf = timing["window_frac"].dropna()
    gs = timing["secs_from_game_start"].dropna()
    return {
        "fills": int(len(trades)),
        "buy_share": float((trades["side"] == "BUY").mean()),
        "usd_volume": float(trades["usdc"].sum()),
        "median_fill_usd": float(trades["usdc"].median()),
        "families_by_usd": {k: float(v) for k, v in fam_usd.sort_values(ascending=False).head(10).items()},
        "markets": int(len(per_market)),
        "markets_resolved": int(len(resolved)),
        "share_two_sided_markets": float(per_market["two_sided"].mean()),
        "median_pair_cost": float(per_market["pair_cost"].median()) if per_market["pair_cost"].notna().any() else None,
        "median_balance": float(per_market["balance"].median()) if per_market["balance"].notna().any() else None,
        "settled_pnl": pnl,
        "settled_locked_pnl": locked,
        "settled_residual_pnl": resid,
        "residual_win_rate": float(np.mean([x for x in resolved["residual_won"] if x is not None])) if len(resolved) and resolved["residual_won"].notna().any() else None,
        "market_win_rate": float((resolved["pnl"] > 0).mean()) if len(resolved) else None,
        "price_quantiles": [float(x) for x in np.percentile(trades["price"], [5, 25, 50, 75, 95])],
        "window_frac_quantiles": [float(x) for x in np.percentile(wf, [5, 25, 50, 75, 95])] if len(wf) else None,
        "share_fills_after_game_start": float((gs > 0).mean()) if len(gs) else None,
        "hour_of_day_usd": {int(h): float(v) for h, v in trades.groupby(pd.to_datetime(trades["ts"], unit="s").dt.hour)["usdc"].sum().items()},
    }


def price_bucket_calibration(trades: pd.DataFrame, markets: dict[str, dict[str, Any]], bins: int = 10) -> list[dict[str, Any]]:
    """Win rate of bought shares vs. price paid (edge = win_rate - price)."""
    payouts = {}
    for cid, m in markets.items():
        r = resolution_info(m)
        if r["resolved"]:
            payouts.update(r["payout"])
    t = trades[trades["asset"].isin(payouts.keys())].copy()
    if t.empty:
        return []
    t["won"] = t["asset"].map(payouts)
    t["bucket"] = np.clip((t["price"] * bins).astype(int), 0, bins - 1)
    out = []
    for b, g in t.groupby("bucket"):
        w = g["size"]
        out.append(
            {
                "price_lo": b / bins,
                "price_hi": (b + 1) / bins,
                "fills": int(len(g)),
                "shares": float(w.sum()),
                "avg_price": float((g["price"] * w).sum() / w.sum()),
                "win_rate": float((g["won"] * w).sum() / w.sum()),
            }
        )
    return out
