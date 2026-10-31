"""Tape-only two-sided maker: can a slow market maker with public data earn the spread?

For any binary market, fair value of outcome 0 at decision time t is the last
taker print known at t - latency (a print of outcome 1 at price p implies
1 - p for outcome 0). Every ``requote_s`` seconds the maker rests BUY bids on
both outcomes at fair - delta. A bid fills only on later taker prints that trade
through it (taker SELL of that outcome below the bid, or taker BUY of the
other outcome above 1 - bid). Positions settle at resolution; no fees are paid
by makers and rebates are excluded. Uses only public tape data.
``at_touch=True`` is the optimistic first-in-queue bound (a print at the bid
also fills it). The tick follows the exchange's dynamic rule unless given.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from polyrea.analysis.updown import quote_price
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue


def tape_maker_backtest(
    flow: pd.DataFrame,
    payouts: dict[str, float],
    delta: float,
    latency: int,
    requote_s: int = 10,
    size_shares: float = 20.0,
    tick: float | None = None,
    active: dict[str, tuple[int, int]] | None = None,
    queue_share: float = 1.0,
    at_touch: bool = False,
) -> dict[str, Any]:
    """``flow`` columns: condition_id, ts, outcome (0/1), side (BUY/SELL), price, size.

    ``payouts`` maps condition_id -> payout of outcome 0 (settlement only).
    ``active`` optionally limits quoting to [start, end) per market.
    """
    out = []
    eps = -1e-9 if at_touch else 1e-9
    lo_q = 0.001 if tick is None else tick
    for cid, g in flow.groupby("condition_id"):
        if cid not in payouts:
            continue
        g = g.sort_values("ts")
        ts = g["ts"].to_numpy()
        p0 = np.where(g["outcome"].to_numpy() == 0, g["price"].to_numpy(), 1 - g["price"].to_numpy())
        start, end = active.get(cid, (int(ts[0]), int(ts[-1]))) if active else (int(ts[0]), int(ts[-1]))
        for t0 in range(int(start), int(end), requote_s):
            k = np.searchsorted(ts, t0 - latency, side="right") - 1
            if k < 0:
                continue
            fair0 = float(p0[k])
            lo, hi = np.searchsorted(ts, t0, side="right"), np.searchsorted(ts, t0 + requote_s, side="right")
            if hi <= lo:
                continue
            seg = g.iloc[lo:hi]
            for outcome, fair in ((0, fair0), (1, 1 - fair0)):
                q = float(quote_price(fair - delta, tick))
                if q < lo_q - 1e-12 or q > 1 - lo_q + 1e-12:
                    continue
                sell_through = seg[(seg["outcome"] == outcome) & (seg["side"] == "SELL") & (seg["price"] < q - eps)]
                mint_through = seg[(seg["outcome"] != outcome) & (seg["side"] == "BUY") & (seg["price"] > 1 - q + eps)]
                filled = min(size_shares, float(sell_through["size"].sum() + mint_through["size"].sum()) * queue_share)
                if filled <= 0:
                    continue
                pay = payouts[cid] if outcome == 0 else 1 - payouts[cid]
                out.append({"condition_id": cid, "ts": t0, "outcome": outcome, "price": q, "shares": filled, "pnl": filled * (pay - q)})
    if not out:
        return {"fills": 0}
    f = pd.DataFrame(out)
    per_m = f.groupby("condition_id")["pnl"].sum()
    usd = float((f["price"] * f["shares"]).sum())
    t = hac_t_test(per_m.to_numpy())
    # pairs vs residual per market
    q = f.groupby(["condition_id", "outcome"])["shares"].sum().unstack(fill_value=0.0)
    pairs = float(np.minimum(q.get(0, 0), q.get(1, 0)).sum()) if len(q.columns) == 2 else 0.0
    return {
        "fills": int(len(f)),
        "markets": int(per_m.size),
        "usd_bought": usd,
        "pnl": float(f["pnl"].sum()),
        "return_on_bought": float(f["pnl"].sum() / usd) if usd else None,
        "per_market_mean": float(per_m.mean()),
        "per_market_t": t.statistic,
        "per_market_p": t.p_value,
        "per_market_bootstrap_p": stationary_bootstrap_pvalue(per_m.to_numpy(), n_boot=2000).p_value if per_m.size >= 5 else None,
        "matched_pairs_shares": pairs,
        "share_markets_positive": float((per_m > 0).mean()),
    }
