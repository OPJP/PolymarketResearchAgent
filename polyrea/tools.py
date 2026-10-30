"""Tool implementations shared by the MCP server and the CLI.

Tool shapes follow REA's catalog conventions:

* list / search  - ``list_leaderboard``, ``list_external_sources``
* inspect        - ``inspect_wallet_pnl``, ``inspect_market``, ``inspect_research_ledger``
* trace          - ``trace_wallet_fills`` (API fills joined to on-chain OrderFilled events)
* compare        - ``updown_study`` (hypothesis vs. the wallet's actual decisions)
* workflow       - ``screen_leaderboard``, ``investigate_wallet``, ``assess_persistence``
* registry       - ``register_external_source``, ``fetch_external_series``, ``record_verdict``

Every tool returns a JSON-serializable dict; workflows return an Evidence
envelope (observed / derived / inferred, sources, coverage, limitations).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from polyrea.evidence import Coverage, Evidence, to_jsonable

RESEARCH_DIR = Path(os.environ.get("POLYREA_RESEARCH_DIR", Path(__file__).resolve().parent.parent / "research"))


def _pm():
    from polyrea.adapters.polymarket import PolymarketData

    return PolymarketData()


# ------------------------------------------------------------------ list
def list_leaderboard(time_period: str = "month", limit: int = 50, order_by: str = "PNL") -> dict[str, Any]:
    """List Polymarket leaderboard rows (time_period: day|week|month|all; order_by: PNL|VOL)."""
    rows, sources = _pm().leaderboard(time_period=time_period, order_by=order_by, limit=limit)
    return Evidence(
        tool="list_leaderboard",
        subject={"kind": "leaderboard", "time_period": time_period, "order_by": order_by},
        observed={"rows": rows},
        sources=sources,
        coverage=Coverage("complete" if len(rows) >= limit else "partial", f"{len(rows)} rows"),
        limitations=["Leaderboard PnL can disagree with the wallet's mark-to-market PnL series; see inspect_wallet_pnl."],
    ).to_dict()


# ------------------------------------------------------------------ inspect
def inspect_wallet_pnl(wallet: str) -> dict[str, Any]:
    """Daily-PnL statistics of one wallet: significance (HAC, bootstrap), Sharpe, monthly blocks, income split, persistence."""
    from polyrea.analysis.pnl import daily_frame
    from polyrea.stats.persistence import persistence_report
    from polyrea.workflows.investigate import default_as_of
    from polyrea.workflows.screen import wallet_pnl_metrics

    pm = _pm()
    body, src = pm.user_pnl(wallet)
    as_of = default_as_of()
    pts = body.get("points") or []
    m = wallet_pnl_metrics(pts, as_of)
    df = daily_frame(pts, as_of=as_of)
    income = {}
    if not df.empty:
        for f in ("trade_pnl", "maker_rebate", "reward_income", "fees_paid", "wallet_income"):
            if f"d_{f}" in df:
                income[f] = float(df[f"d_{f}"].iloc[-30:].sum())
    pers = persistence_report(df["d_economic_pnl"].iloc[1:].to_numpy()) if len(df) > 40 else None
    return Evidence(
        tool="inspect_wallet_pnl",
        subject={"kind": "wallet", "wallet": wallet.lower(), "as_of": as_of},
        observed={"income_last_30d": income},
        derived={"metrics": m, "persistence": asdict(pers) if pers else None},
        sources=[src],
        coverage=Coverage("complete" if pts else "empty", f"{len(pts)} PnL points"),
        limitations=["Daily PnL is mark-to-market from Polymarket's v2 user-pnl index."],
    ).to_dict()


def inspect_market(condition_id: str | None = None, slug: str | None = None, include_post_hoc: bool = False) -> dict[str, Any]:
    """Static (listing-time) market fields; post-hoc fields only on request and labelled."""
    from polyrea.adapters.http import shared_client
    from polyrea.adapters.polymarket import GAMMA_API
    from polyrea.pit import STATIC_MARKET_FIELDS

    if not condition_id and not slug:
        raise ValueError("condition_id or slug required")
    if condition_id:
        markets, sources = _pm().markets_by_condition([condition_id])
        m = markets.get(condition_id)
    else:
        data, src = shared_client().get_json(f"{GAMMA_API}/markets", [("slug", slug), ("closed", "true")], adapter="gamma.markets")
        if not data:
            data, src = shared_client().get_json(f"{GAMMA_API}/markets", [("slug", slug)], adapter="gamma.markets")
        m, sources = (data[0] if data else None), [src]
    if m is None:
        return Evidence(tool="inspect_market", subject={"condition_id": condition_id, "slug": slug}, coverage=Coverage("empty", "not found")).to_dict()
    static = {k: m[k] for k in STATIC_MARKET_FIELDS if k in m}
    post = {k: v for k, v in m.items() if k not in STATIC_MARKET_FIELDS and k not in ("description", "image", "icon", "events")}
    return Evidence(
        tool="inspect_market",
        subject={"kind": "market", "condition_id": m.get("conditionId"), "slug": m.get("slug")},
        observed={"static": static, **({"post_hoc_DO_NOT_USE_IN_DECISIONS": post} if include_post_hoc else {})},
        sources=sources,
        coverage=Coverage("complete"),
        limitations=["Post-hoc fields (prices, resolution, volume, closed time) describe the present and leak the future if used for past decisions."],
    ).to_dict()


def inspect_research_ledger() -> dict[str, Any]:
    """Return research/ledger.json: every researched wallet with its verdict, stage and reasons."""
    p = RESEARCH_DIR / "ledger.json"
    return json.loads(p.read_text()) if p.exists() else {"wallets": []}


# ------------------------------------------------------------------ trace
def trace_wallet_fills(wallet: str, start: int, end: int, verify_onchain: bool = True, limit: int = 300) -> dict[str, Any]:
    """Wallet fills in [start, end) joined to decoded on-chain OrderFilled events."""
    from polyrea.adapters.chain import PolygonChain, decode_fills

    rows, sources, cov = _pm().activity(wallet, start=start, end=end, types=("TRADE",))
    rows = rows[-limit:]
    w = wallet.lower()
    receipts = {}
    if verify_onchain and rows:
        receipts, rsrc = PolygonChain().receipts([r["transactionHash"] for r in rows])
        sources = sources + rsrc[:3]
    fills = []
    for r in rows:
        item = {k: r.get(k) for k in ("timestamp", "transactionHash", "conditionId", "slug", "outcome", "side", "price", "size", "usdcSize", "asset")}
        rec = receipts.get(r["transactionHash"])
        if rec:
            mine = [f for f in decode_fills(rec) if f.maker == w and f.token_id == str(r["asset"])]
            item["onchain"] = {
                "events": len(mine),
                "shares": sum(f.shares for f in mine),
                "roles": sorted({f.role_of(w) for f in mine}),
                "fee": sum(f.fee for f in mine),
                "exchange_version": sorted({f.version for f in mine}),
            }
        fills.append(item)
    return Evidence(
        tool="trace_wallet_fills",
        subject={"kind": "wallet", "wallet": w, "start": start, "end": end},
        observed={"fills": fills},
        sources=sources,
        coverage=Coverage(cov.status if len(rows) < limit else "partial", f"{len(fills)} fills (limit {limit})"),
    ).to_dict()


# ------------------------------------------------------------------ external data
def _registry():
    from polyrea.pit import ExternalRegistry

    return ExternalRegistry(RESEARCH_DIR / "external_sources.json")


def list_external_sources() -> dict[str, Any]:
    """List registered external public time-series sources (built-in and user-registered) with their availability lags."""
    reg = _registry()
    return {"sources": [asdict(s) for s in reg.sources.values()], "cursor_sources": ["kraken.<asset>usd.trades (per-second, via spot_seconds)"]}


def register_external_source(
    name: str,
    url_template: str,
    records_path: str,
    time_field: str,
    value_field: str,
    time_unit: str = "s",
    availability_lag_seconds: int = 0,
    chunk_seconds: int = 86400,
    description: str = "",
) -> dict[str, Any]:
    """Register any public JSON time series; fields may be keys or integer indices."""
    from polyrea.pit import ExternalSourceSpec

    def _key(x: str) -> str | int:
        return int(x) if isinstance(x, str) and x.lstrip("-").isdigit() else x

    spec = ExternalSourceSpec(name, url_template, records_path, _key(time_field), _key(value_field), time_unit, availability_lag_seconds, chunk_seconds, description)
    _registry().register(spec)
    return {"registered": asdict(spec)}


def fetch_external_series(name: str, start: int, end: int, max_points: int = 500) -> dict[str, Any]:
    """Fetch a registered external series for [start, end) with event and availability timestamps."""
    ts, sources = _registry().fetch(name, start, end)
    n = len(ts)
    step = max(1, n // max_points)
    return Evidence(
        tool="fetch_external_series",
        subject={"kind": "external_series", "name": name, "start": start, "end": end},
        observed={
            "points": [[int(e), int(a), float(v)] for e, a, v in zip(ts.event_ts[::step], ts.available_ts[::step], ts.values[::step])],
            "columns": ["event_ts", "available_ts", "value"],
        },
        derived={"count": n, "downsample_step": step},
        sources=sources,
        coverage=Coverage("complete" if n else "empty", f"{n} records"),
        limitations=["Decisions at time t may only use records with available_ts <= t."],
    ).to_dict()


def spot_seconds(asset: str, start: int, end: int, max_points: int = 600) -> dict[str, Any]:
    """Per-second spot prices (Kraken trades) for btc|eth|sol|xrp|doge in [start, end); each second is available 1 s later."""
    from polyrea.adapters.spot import kraken_trades, per_second_series

    trades, sources = kraken_trades(asset, start, end)
    ts = per_second_series(f"spot.kraken.{asset}", trades, start, end)
    step = max(1, len(ts) // max_points)
    return Evidence(
        tool="spot_seconds",
        subject={"kind": "spot", "asset": asset, "start": start, "end": end},
        observed={"trades": len(trades), "points": [[int(e), float(v)] for e, v in zip(ts.event_ts[::step], ts.values[::step])]},
        derived={"availability_lag_seconds": 1},
        sources=sources[:5],
        coverage=Coverage("complete" if trades else "empty"),
    ).to_dict()


# ------------------------------------------------------------------ workflows
def screen_leaderboard(limit: int = 500, time_period: str = "month") -> dict[str, Any]:
    """Stage A1: screen the top leaderboard wallets on selection-bias-aware significance, $50k/month, and consistency."""
    from polyrea.workflows.screen import run_screen

    res = run_screen(RESEARCH_DIR / "stage_a", limit=limit, time_period=time_period)
    ev = res["evidence"].to_dict()
    ev["derived"]["wallets_summary"] = [
        {"wallet": r["wallet"], "name": r["name"], "rank": r["rank"], "pass": r["stage_a1_pass"], "reasons": r["stage_a1_reasons"][:3]} for r in res["wallets"]
    ]
    return ev


def investigate_wallet(wallet: str, days: int = 30, onchain_sample: int = 200) -> dict[str, Any]:
    """Stage A2/B: capital at risk and ROC, on-chain fill verification with maker/taker roles, per-market decomposition and profile."""
    from polyrea.workflows.investigate import investigate_wallet as _inv

    return _inv(wallet, days=days, onchain_sample=onchain_sample, out_dir=RESEARCH_DIR / "wallets").to_dict()


def updown_study(wallet: str, asset: str = "btc", duration: str = "5m", blocks_per_period: int = 12, n_perm: int = 200) -> dict[str, Any]:
    """Walk-forward test of the spot-latency hypothesis on crypto Up/Down windows: decision match vs. permutation null, PIT backtest, latency decay."""
    from polyrea.workflows.updown_study import run_updown_study

    return run_updown_study(wallet, asset=asset, duration=duration, blocks_per_period=blocks_per_period, n_perm=n_perm, out_dir=RESEARCH_DIR / "wallets").to_dict()


def assess_persistence(wallet: str, recent_days: int = 30) -> dict[str, Any]:
    """Is the edge still alive? Recent-window significance, decline vs. earlier, trend and CUSUM break tests on daily PnL."""
    from polyrea.analysis.pnl import daily_frame
    from polyrea.stats.persistence import persistence_report
    from polyrea.workflows.investigate import default_as_of

    body, src = _pm().user_pnl(wallet)
    df = daily_frame(body.get("points") or [], as_of=default_as_of())
    out: dict[str, Any] = {}
    for col in ("d_economic_pnl", "d_trade_pnl", "d_position_pnl"):
        if col in df and len(df) > recent_days + 10:
            out[col] = asdict(persistence_report(df[col].iloc[1:].to_numpy(), recent_days=recent_days))
    return Evidence(
        tool="assess_persistence",
        subject={"kind": "wallet", "wallet": wallet.lower(), "recent_days": recent_days},
        derived=out,
        sources=[src],
        coverage=Coverage("complete" if out else "empty"),
        limitations=["Persistence of the wallet's own PnL; strategy-level persistence comes from the walk-forward backtest."],
    ).to_dict()


def record_verdict(wallet: str, verdict: str, stage: str, reasons: list[str], evidence_paths: list[str] | None = None, summary: str = "") -> dict[str, Any]:
    """Append/replace a wallet's verdict in research/ledger.json (the dashboard's data)."""
    if verdict not in ("pass", "reject", "inconclusive", "in_progress"):
        raise ValueError("verdict must be pass | reject | inconclusive | in_progress")
    p = RESEARCH_DIR / "ledger.json"
    ledger = json.loads(p.read_text()) if p.exists() else {"wallets": []}
    entries = {e["wallet"]: e for e in ledger["wallets"]}
    e = entries.get(wallet.lower(), {"wallet": wallet.lower()})
    e.update({"verdict": verdict, "stage": stage, "reasons": reasons, "evidence_paths": evidence_paths or [], "summary": summary, "updated_at": int(time.time())})
    entries[wallet.lower()] = e
    ledger["wallets"] = sorted(entries.values(), key=lambda x: x.get("rank") or 10**9)
    p.write_text(json.dumps(to_jsonable(ledger), indent=1))
    return {"recorded": e}


TOOLS = {
    "list_leaderboard": list_leaderboard,
    "inspect_wallet_pnl": inspect_wallet_pnl,
    "inspect_market": inspect_market,
    "inspect_research_ledger": inspect_research_ledger,
    "trace_wallet_fills": trace_wallet_fills,
    "list_external_sources": list_external_sources,
    "register_external_source": register_external_source,
    "fetch_external_series": fetch_external_series,
    "spot_seconds": spot_seconds,
    "screen_leaderboard": screen_leaderboard,
    "investigate_wallet": investigate_wallet,
    "updown_study": updown_study,
    "assess_persistence": assess_persistence,
    "record_verdict": record_verdict,
}
