"""Stage A2 + B: per-wallet investigation (capital, on-chain verification, profile).

Everything is frozen at ``as_of`` (UTC midnight by default) so a re-run reads
the same window from cache.
"""

from __future__ import annotations

import json
import math
import random
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from polyrea.adapters.chain import PolygonChain, decode_fills
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.ledger import build_ledger, capital_and_roc
from polyrea.analysis.pnl import daily_frame
from polyrea.analysis.profile import (
    per_market_decomposition,
    price_bucket_calibration,
    resolution_info,
    summarize_profile,
    timing_features,
)
from polyrea.evidence import Coverage, Evidence, Source, to_jsonable

DAY = 86400


def default_as_of() -> int:
    return int(time.time()) // DAY * DAY


def load_window(
    wallet: str,
    days: int = 30,
    as_of: int | None = None,
    warmup_days: int = 7,
    pm: PolymarketData | None = None,
) -> dict[str, Any]:
    pm = pm or PolymarketData()
    as_of = as_of or default_as_of()
    start = as_of - days * DAY
    activity, act_sources, act_cov = pm.activity(wallet, start=start - warmup_days * DAY, end=as_of)
    cids = sorted({r["conditionId"] for r in activity if r.get("conditionId")})
    markets, mk_sources = pm.markets_by_condition(cids)
    res_ts = {}
    for cid, m in markets.items():
        r = resolution_info(m)
        if r["resolved"] and r["closed_ts"]:
            res_ts[cid] = r["closed_ts"]
    ledger = build_ledger(wallet, activity, res_ts)
    trades = pd.DataFrame(ledger.trades)
    if not trades.empty:
        trades = trades[(trades["ts"] >= start) & (trades["ts"] < as_of)].reset_index(drop=True)
    return {
        "wallet": wallet.lower(),
        "as_of": as_of,
        "start": start,
        "days": days,
        "activity": activity,
        "activity_coverage": act_cov,
        "markets": markets,
        "ledger": ledger,
        "trades": trades,
        "sources": act_sources + mk_sources,
        "missing_markets": [c for c in cids if c not in markets],
    }


def verify_onchain(wallet: str, trades: pd.DataFrame, sample: int = 200, seed: int = 0, chain: PolygonChain | None = None) -> dict[str, Any]:
    """Check a random sample of API trades against Polygon receipts.

    Groups API rows by (tx, asset); a group is confirmed when the wallet's
    decoded OrderFilled shares for that token in that tx match the API size
    within 0.5%. Role (maker / taker) and fees come from the same events.
    """
    chain = chain or PolygonChain()
    if trades.empty:
        return {"sampled": 0}
    groups = trades.groupby(["tx", "asset"]).agg(size=("size", "sum"), usdc=("usdc", "sum"), side=("side", "first")).reset_index()
    rng = random.Random(seed)
    idx = list(range(len(groups)))
    rng.shuffle(idx)
    pick = groups.iloc[idx[:sample]]
    receipts, sources = chain.receipts(pick["tx"].tolist())
    w = wallet.lower()
    confirmed = 0
    missing_receipt = 0
    roles = defaultdict(float)
    role_counts = defaultdict(int)
    fee_usdc = 0.0
    taker_usdc = 0.0
    mismatches = []
    for _, g in pick.iterrows():
        rec = receipts.get(g["tx"])
        if not rec:
            missing_receipt += 1
            continue
        mine = [f for f in decode_fills(rec) if f.maker == w and f.token_id == str(g["asset"])]
        shares = sum(f.shares for f in mine)
        if mine and abs(shares - g["size"]) <= max(0.005 * g["size"], 0.011):
            confirmed += 1
        else:
            mismatches.append({"tx": g["tx"], "api_size": g["size"], "chain_shares": shares, "events": len(mine)})
        for f in mine:
            role = f.role_of(w)
            roles[role] += f.usdc
            role_counts[role] += 1
            if role == "taker":
                fee_usdc += f.fee
                taker_usdc += f.usdc
    checked = len(pick) - missing_receipt
    n_role = sum(role_counts.values())
    maker_share = role_counts["maker"] / n_role if n_role else float("nan")
    ci = _wilson(role_counts["maker"], n_role)
    return {
        "sampled": int(len(pick)),
        "receipts_found": int(checked),
        "confirmed": int(confirmed),
        "confirmed_rate": confirmed / checked if checked else None,
        "confirmed_rate_ci95": list(_wilson(confirmed, checked)),
        "maker_fill_share": maker_share,
        "maker_fill_share_ci95": list(ci),
        "maker_usdc_share": roles["maker"] / (roles["maker"] + roles["taker"]) if (roles["maker"] + roles["taker"]) else None,
        "taker_fee_rate_observed": fee_usdc / taker_usdc if taker_usdc else None,
        "mismatches": mismatches[:10],
        "sources": [asdict(s) for s in sources[:3]] + ([{"more": len(sources) - 3}] if len(sources) > 3 else []),
    }


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def investigate_wallet(
    wallet: str,
    days: int = 30,
    as_of: int | None = None,
    onchain_sample: int = 200,
    out_dir: Path | None = None,
    pm: PolymarketData | None = None,
) -> Evidence:
    pm = pm or PolymarketData()
    win = load_window(wallet, days=days, as_of=as_of, pm=pm)
    trades, markets, ledger = win["trades"], win["markets"], win["ledger"]
    body, pnl_src = pm.user_pnl(wallet)
    df = daily_frame(body.get("points") or [], as_of=win["as_of"])
    daily = df["d_economic_pnl"].iloc[1:] if not df.empty else pd.Series(dtype=float)
    roc = capital_and_roc(ledger, daily, window_days=days)
    per_market = per_market_decomposition(trades, markets) if not trades.empty else pd.DataFrame()
    timing = timing_features(trades, markets) if not trades.empty else pd.DataFrame()
    summary = summarize_profile(trades, per_market, timing) if not trades.empty else {"fills": 0}
    calib = price_bucket_calibration(trades, markets) if not trades.empty else []
    chain = verify_onchain(wallet, trades, sample=onchain_sample)
    income = {k: float(df[f"d_{k}"].iloc[-days:].sum()) for k in ("wallet_income", "maker_rebate", "reward_income", "fees_paid") if f"d_{k}" in df}
    ev = Evidence(
        tool="investigate_wallet",
        subject={"kind": "wallet", "wallet": wallet.lower(), "window_start": win["start"], "as_of": win["as_of"], "days": days},
        observed={
            "activity_rows": len(win["activity"]),
            "fills_in_window": summary.get("fills", 0),
            "markets_in_window": summary.get("markets", 0),
            "income_window": income,
            "pnl_series_window": float(daily.iloc[-days:].sum()) if len(daily) else None,
        },
        derived={
            "capital": roc,
            "profile": summary,
            "price_calibration": calib,
            "onchain_verification": chain,
            "ledger_anomalies": ledger.anomalies[:20],
            "ledger_anomaly_count": len(ledger.anomalies),
        },
        sources=[pnl_src] + win["sources"][:5],
        coverage=Coverage(
            win["activity_coverage"].status if not win["missing_markets"] else "partial",
            f"{win['activity_coverage'].detail}; {len(win['missing_markets'])} markets without Gamma metadata",
        ),
        limitations=[
            "Capital at risk is the cost basis of open positions; collateral for resting (unfilled) orders is not visible on-chain and is not counted.",
            "Positions opened before the warm-up period are invisible to the ledger; sells/redeems of them are logged as anomalies.",
            "On-chain verification is a random sample; rates carry Wilson 95% intervals.",
        ],
    )
    if out_dir is not None:
        d = out_dir / wallet.lower()
        d.mkdir(parents=True, exist_ok=True)
        (d / "profile.json").write_text(json.dumps(ev.to_dict(), indent=1))
        if not per_market.empty:
            per_market.to_csv(d / "per_market.csv.gz", index=False)
    return ev
