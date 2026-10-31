"""Reconstruct a wallet's positions, cash flows and capital at risk from activity.

Activity rows (data-api ``/activity``) are replayed in timestamp order:

* ``TRADE`` BUY/SELL  - shares bought/sold at ``price`` for ``usdcSize``
* ``SPLIT``           - ``usdcSize`` USDC -> ``size`` shares of every outcome
* ``MERGE``           - ``size`` shares of every outcome -> ``usdcSize`` USDC
* ``REDEEM``          - resolved shares -> ``usdcSize`` USDC
* ``CONVERSION``      - neg-risk NO -> YES conversion (treated as neutral cash)
* ``REWARD`` / ``MAKER_REBATE`` / ``TAKER_REBATE`` / ``YIELD`` - wallet income

Positions use average cost. A position counts toward capital at risk from its
first buy until it is sold, merged, redeemed, or its market resolves (when the
resolution time is known), whichever is first. Capital at risk is the cost
basis of open positions - the cash a replicator must have committed.

Complete sets created by ``SPLIT`` pay exactly $1 per set whatever the outcome
and can be merged back to cash at any time, so they carry no outcome risk and
are tracked separately (``complete_set_events``); wallets park idle cash in
them to earn holding yield.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

INCOME_TYPES = {"REWARD", "MAKER_REBATE", "TAKER_REBATE", "YIELD", "REFERRAL"}


@dataclass
class Position:
    asset: str
    condition_id: str
    outcome_index: int | None
    shares: float = 0.0
    cost: float = 0.0
    opened_at: int | None = None
    realized: float = 0.0
    bought_shares: float = 0.0
    bought_usdc: float = 0.0
    sold_shares: float = 0.0
    sold_usdc: float = 0.0
    redeemed_usdc: float = 0.0
    closed_at: int | None = None
    close_kind: str | None = None

    @property
    def avg_cost(self) -> float:
        return self.cost / self.shares if self.shares > 1e-12 else 0.0


@dataclass
class Ledger:
    wallet: str
    positions: dict[str, Position] = field(default_factory=dict)
    exposure_events: list[tuple[int, float]] = field(default_factory=list)  # (ts, delta cost basis)
    complete_set_events: list[tuple[int, float]] = field(default_factory=list)  # (ts, delta USDC in complete sets)
    cash_events: list[tuple[int, float, str]] = field(default_factory=list)  # (ts, delta cash, kind)
    trades: list[dict[str, Any]] = field(default_factory=list)
    income: float = 0.0
    anomalies: list[str] = field(default_factory=list)

    def exposure_series(self, include_complete_sets: bool = False) -> pd.Series:
        """Capital at risk (open cost basis) after every event, indexed by time."""
        events = self.exposure_events + (self.complete_set_events if include_complete_sets else [])
        if not events:
            return pd.Series(dtype=float)
        ev = sorted(events)
        ts = np.array([e[0] for e in ev])
        level = np.cumsum([e[1] for e in ev])
        s = pd.Series(level, index=pd.to_datetime(ts, unit="s", utc=True))
        return s.groupby(level=0).last().clip(lower=0.0)

    def daily_peak_exposure(self, include_complete_sets: bool = False) -> pd.Series:
        s = self.exposure_series(include_complete_sets)
        if s.empty:
            return s
        return s.resample("D").max().ffill()


def build_ledger(
    wallet: str,
    activity: list[dict[str, Any]],
    resolution_ts: dict[str, int] | None = None,
) -> Ledger:
    """Replay activity (oldest first). ``resolution_ts`` maps conditionId -> resolved time."""
    led = Ledger(wallet=wallet.lower())
    resolution_ts = resolution_ts or {}
    by_condition_assets: dict[str, set[str]] = defaultdict(set)
    rows = sorted(activity, key=lambda r: (r.get("timestamp", 0), _type_order(r.get("type"))))
    pending_resolution: list[tuple[int, str]] = []

    def close_resolved(upto: int) -> None:
        # release capital of positions in markets that resolved before `upto`
        nonlocal pending_resolution
        keep = []
        for rts, cid in pending_resolution:
            if rts <= upto:
                for a in by_condition_assets.get(cid, ()):  # positions still open at resolution
                    p = led.positions.get(a)
                    if p and p.shares > 1e-9 and p.closed_at is None:
                        led.exposure_events.append((rts, -p.cost))
                        p.closed_at, p.close_kind = rts, "resolved"
            else:
                keep.append((rts, cid))
        pending_resolution = keep

    seen_conditions: set[str] = set()
    for r in rows:
        ts = int(r.get("timestamp", 0))
        close_resolved(ts)
        typ = r.get("type")
        cid = r.get("conditionId") or ""
        asset = str(r.get("asset") or "")
        size = float(r.get("size") or 0.0)
        usdc = float(r.get("usdcSize") or 0.0)
        if cid and cid not in seen_conditions and cid in resolution_ts:
            seen_conditions.add(cid)
            pending_resolution.append((int(resolution_ts[cid]), cid))
            pending_resolution.sort()
        if typ in INCOME_TYPES:
            led.income += usdc
            led.cash_events.append((ts, usdc, typ.lower()))
            continue
        if typ == "TRADE":
            side = r.get("side")
            price = float(r.get("price") or 0.0)
            pos = _pos(led, asset, cid, r.get("outcomeIndex"))
            by_condition_assets[cid].add(asset)
            if side == "BUY":
                was_flat = pos.shares <= 1e-9 or pos.closed_at is not None
                if pos.closed_at is not None:  # re-opened after a close
                    pos.closed_at, pos.close_kind = None, None
                pos.shares += size
                pos.cost += usdc
                pos.bought_shares += size
                pos.bought_usdc += usdc
                if was_flat:
                    pos.opened_at = ts
                led.exposure_events.append((ts, usdc))
                led.cash_events.append((ts, -usdc, "buy"))
            elif side == "SELL":
                sold = min(size, pos.shares) if pos.shares > 0 else 0.0
                if size - sold > 1e-6:
                    led.anomalies.append(f"sell of {size - sold:.4f} unseen shares of {asset[:10]}.. at {ts}")
                basis = pos.avg_cost * sold
                pos.realized += usdc - basis * (1 if sold else 0) if sold else usdc
                pos.shares -= sold
                pos.cost -= basis
                pos.sold_shares += size
                pos.sold_usdc += usdc
                if pos.closed_at is None:
                    led.exposure_events.append((ts, -basis))
                if pos.shares <= 1e-9 and pos.closed_at is None:
                    pos.closed_at, pos.close_kind = ts, "sold"
                led.cash_events.append((ts, usdc, "sell"))
            led.trades.append(
                {
                    "ts": ts,
                    "tx": r.get("transactionHash"),
                    "condition_id": cid,
                    "asset": asset,
                    "outcome_index": r.get("outcomeIndex"),
                    "outcome": r.get("outcome"),
                    "side": side,
                    "price": price,
                    "size": size,
                    "usdc": usdc,
                    "slug": r.get("slug"),
                    "event_slug": r.get("eventSlug"),
                    "title": r.get("title"),
                }
            )
        elif typ == "SPLIT":
            # one share of each outcome per USDC; split cost evenly across known outcomes
            led.cash_events.append((ts, -usdc, "split"))
            led.complete_set_events.append((ts, usdc))
            assets = sorted(by_condition_assets.get(cid, set()))
            key = f"split:{cid}"
            pos = _pos(led, key, cid, None)
            pos.shares += size
            pos.cost += usdc
            if pos.opened_at is None:
                pos.opened_at = ts
            del assets
        elif typ == "MERGE":
            led.cash_events.append((ts, usdc, "merge"))
            # release basis of one share of each outcome per merged pair
            released, released_sets = 0.0, 0.0
            for a in sorted(by_condition_assets.get(cid, set()) | {f"split:{cid}"}):
                p = led.positions.get(a)
                if not p or p.shares <= 1e-9:
                    continue
                q = min(size, p.shares)
                basis = p.avg_cost * q
                p.shares -= q
                p.cost -= basis
                if p.closed_at is None:
                    if a.startswith("split:"):
                        released_sets += basis
                    else:
                        released += basis
                if p.shares <= 1e-9 and p.closed_at is None:
                    p.closed_at, p.close_kind = ts, "merged"
            led.exposure_events.append((ts, -released))
            led.complete_set_events.append((ts, -released_sets))
        elif typ == "REDEEM":
            led.cash_events.append((ts, usdc, "redeem"))
            released, released_sets = 0.0, 0.0
            for a in sorted(by_condition_assets.get(cid, set()) | {f"split:{cid}"}):
                p = led.positions.get(a)
                if not p or p.shares <= 1e-9:
                    continue
                if p.closed_at is None:
                    if a.startswith("split:"):
                        released_sets += p.cost
                    else:
                        released += p.cost
                    p.closed_at, p.close_kind = ts, "redeemed"
                p.shares = 0.0
                p.cost = 0.0
            pos_any = led.positions.get(asset)
            if pos_any is not None:
                pos_any.redeemed_usdc += usdc
            led.exposure_events.append((ts, -released))
            led.complete_set_events.append((ts, -released_sets))
        elif typ == "CONVERSION":
            led.cash_events.append((ts, 0.0, "conversion"))
    close_resolved(2**62)
    return led


def _pos(led: Ledger, asset: str, cid: str, outcome_index: Any) -> Position:
    p = led.positions.get(asset)
    if p is None:
        p = Position(asset=asset, condition_id=cid, outcome_index=outcome_index)
        led.positions[asset] = p
    return p


def _type_order(t: str | None) -> int:
    # within one second apply buys/splits before sells/merges/redeems
    return {"SPLIT": 0, "TRADE": 1, "CONVERSION": 2, "MERGE": 3, "REDEEM": 4}.get(t or "", 5)


def capital_and_roc(led: Ledger, daily_pnl: pd.Series, window_days: int = 30) -> dict[str, Any]:
    """Peak capital at risk and return on it over the trailing window."""
    peak = led.daily_peak_exposure()
    if peak.empty or daily_pnl.empty:
        return {"peak_capital": None, "monthly_roc": None}
    end = daily_pnl.index.max()
    start = end - pd.Timedelta(days=window_days)
    in_win = (peak.index > start) & (peak.index <= end)
    win_peak = float(peak[in_win].max()) if in_win.any() else float("nan")
    pnl = float(daily_pnl[daily_pnl.index > start].sum())
    p95 = float(np.nanpercentile(peak[in_win], 95)) if in_win.any() else float("nan")
    with_sets = led.daily_peak_exposure(include_complete_sets=True)
    in_win2 = (with_sets.index > start) & (with_sets.index <= end)
    peak_sets = float(with_sets[in_win2].max()) if in_win2.any() else float("nan")
    return {
        "window_days": window_days,
        "peak_capital": win_peak,
        "p95_capital": p95,
        "peak_capital_incl_complete_sets": peak_sets,
        "window_pnl": pnl,
        "monthly_roc": pnl / win_peak * (30 / window_days) if win_peak and win_peak > 0 else None,
    }
