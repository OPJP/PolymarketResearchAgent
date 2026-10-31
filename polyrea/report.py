"""Build the research ledger, per-wallet reports and the dashboard.

Inputs
  research/stage_a/stage_a1.json      every screened wallet (stage A1 metrics + reasons)
  research/verdicts/<wallet>.json     deep-dive verdicts (criteria checklist, mechanism, evidence)
Outputs
  research/ledger.json                one record per wallet (the dashboard's data)
  research/wallets/<wallet>/REPORT.md human-readable dossier for deep-dived wallets
  dashboard/index.html                standalone dashboard (data embedded)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from polyrea.evidence import to_jsonable

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"

CRITERIA = [
    ("significance", "Profit significant, not luck", "Pre-selection HAC t-test Holm-adjusted over 500 wallets < 0.05, block bootstrap p < 0.01, deflated Sharpe > 0.95"),
    ("monthly_50k", "Net profit above $50k/month", "Last 30 days and median of recent 30-day blocks both above $50k"),
    ("consistency", "Constant returns (low std)", "Annualized daily Sharpe >= 3, >= 75% positive weeks, >= 80% positive months"),
    ("roc", "High % profit", ">= 10% per month on peak capital at risk (reconstructed from fills)"),
    ("onchain", "Trades verified on-chain", "Random sample of API fills matched to Polygon OrderFilled events"),
    ("match", "Reverse-engineered rule matches the wallet", "Held-out decisions: stratified AUC beats a within-block rotation null (p < 0.01) and the fitted rule flags >= 20% of the wallet's decisions at >= 2x the base rate; a significant but smaller association is a partial match"),
    ("backtest", "Rule profitable in held-out PIT backtest", "Walk-forward, no future data, fees included; p < 0.05"),
    ("replicable", "Replicable on a normal computer and connection", "No sub-second race, no private data feed, no self-trading or rebate tier the replicator lacks"),
    ("persistence", "Conditions still hold now", "Last 30 days significant, no significant decline (vs. earlier days or inside the last 30), no negative trend, one-off bonuses removed, policy unchanged"),
]


def load_json(p: Path) -> Any:
    return json.loads(p.read_text()) if p.exists() else None


def a1_criteria(m: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Stage A criteria entries derived from the screen metrics (identical wording for every wallet)."""
    return {
        "significance": {
            "status": "pass",
            "detail": f"pre-selection {m.get('pre_selection_days')}d: HAC t={m.get('hac_t_pre', 0):.1f}, Holm p={m.get('p_holm_pre', 1):.1e}, bootstrap p={m.get('p_boot_pre', 1):.1e}; deflated Sharpe {m.get('deflated_sharpe', 0):.3f}",
        },
        "monthly_50k": {"status": "pass", "detail": f"last 30d ${m.get('last_30d_pnl', 0):,.0f}; median month ${m.get('median_month_pnl', 0):,.0f}"},
        "consistency": {
            "status": "pass",
            "detail": f"annualized Sharpe {m.get('annual_sharpe', 0):.1f}; positive weeks {m.get('share_positive_weeks', 0):.0%}; positive months {m.get('share_positive_months', 0):.0%}",
        },
    }


def build_ledger() -> dict[str, Any]:
    a1 = load_json(RESEARCH / "stage_a" / "stage_a1.json") or {"wallets": [], "evidence": {}}
    verdicts = {p.stem.lower(): json.loads(p.read_text()) for p in sorted((RESEARCH / "verdicts").glob("*.json"))}
    rows = []
    for r in a1["wallets"]:
        m = r["metrics"]
        w = r["wallet"]
        base = {
            "wallet": w,
            "name": r.get("name"),
            "rank": r.get("rank"),
            "lb_pnl_month": r.get("lb_pnl"),
            "lb_volume_month": r.get("lb_volume"),
            "pnl_30d": m.get("last_30d_pnl"),
            "median_month_pnl": m.get("median_month_pnl"),
            "annual_sharpe": m.get("annual_sharpe"),
            "share_positive_weeks": m.get("share_positive_weeks"),
            "history_days": m.get("history_days"),
            "p_holm_pre": m.get("p_holm_pre"),
            "deflated_sharpe": m.get("deflated_sharpe"),
            "incentive_share": m.get("incentive_share"),
            "lb_series_inconsistent": m.get("lb_series_inconsistent"),
            "cumulative_weekly": m.get("cumulative_weekly"),
            "a1_pass": bool(r["stage_a1_pass"]),
        }
        if w in verdicts:
            v = verdicts[w]
            v["criteria"] = {**a1_criteria(m), **(v.get("criteria") or {})}
            base.update(
                {
                    "stage": v.get("stage", "C"),
                    "verdict": v["verdict"],
                    "reasons": v.get("reasons", []),
                    "archetype": v.get("archetype"),
                    "deep_dive": v,
                }
            )
        else:
            base.update(
                {
                    "stage": "A1",
                    "verdict": "in_progress" if r["stage_a1_pass"] else "reject",
                    "reasons": r["stage_a1_reasons"] or ["passed stage A1; reverse engineering in progress"],
                }
            )
        rows.append(base)
    ev = a1.get("evidence") or {}
    ledger = {
        "generated_at": int(time.time()),
        "as_of": (ev.get("subject") or {}).get("as_of"),
        "criteria": [{"key": k, "label": l, "rule": d} for k, l, d in CRITERIA],
        "screen_criteria": (ev.get("derived") or {}).get("criteria"),
        "funnel": _funnel(rows),
        "wallets": rows,
    }
    (RESEARCH / "ledger.json").write_text(json.dumps(to_jsonable(ledger), indent=1))
    return ledger


def _funnel(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deep = [r for r in rows if r.get("deep_dive")]

    def passed(r, key):
        return (r["deep_dive"].get("criteria", {}).get(key) or {}).get("status") == "pass"

    stages = [("Screened (top 500 monthly PnL)", len(rows))]
    stages.append(("Passed significance, $50k/month, consistency", sum(1 for r in rows if r.get("a1_pass"))))
    keys = ["roc", "onchain", "match", "backtest", "replicable", "persistence"]
    labels = ["High % profit (ROC)", "Verified on-chain", "Strategy match", "Held-out backtest", "Replicable", "Conditions persist"]
    alive = deep
    for k, l in zip(keys, labels):
        alive = [r for r in alive if passed(r, k)]
        stages.append((l, len(alive)))
    return [{"label": l, "count": c} for l, c in stages]


def wallet_report_md(row: dict[str, Any]) -> str:
    v = row["deep_dive"]
    lines = [
        f"# {row['name']} (`{row['wallet']}`)",
        "",
        f"Leaderboard rank {row['rank']} (monthly PnL). Verdict: **{v['verdict'].upper()}**. Archetype: {v.get('archetype', 'n/a')}.",
        "",
        f"Profile: https://polymarket.com/profile/{row['wallet']}",
        "",
        "## Mechanism",
        "",
        v.get("mechanism", ""),
        "",
        "## Criteria",
        "",
        "| Criterion | Status | Evidence |",
        "| --- | --- | --- |",
    ]
    for key, label, _ in CRITERIA:
        c = v.get("criteria", {}).get(key) or {"status": "untested", "detail": ""}
        lines.append(f"| {label} | {c['status']} | {c.get('detail', '').replace('|', '/')} |")
    if v.get("key_numbers"):
        lines += ["", "## Key numbers", ""]
        lines += [f"- {k}: {val}" for k, val in v["key_numbers"].items()]
    if v.get("reasons"):
        lines += ["", "## Why this verdict", ""] + [f"- {r}" for r in v["reasons"]]
    if v.get("corrections"):
        lines += ["", "## Corrections after the adversarial review (2026-10-31)", ""] + [f"- {c}" for c in v["corrections"]]
    if v.get("evidence"):
        lines += ["", "## Evidence files", ""] + [f"- `{p}`" for p in v["evidence"]]
    return "\n".join(lines) + "\n"


def write_reports(ledger: dict[str, Any]) -> None:
    for r in ledger["wallets"]:
        if r.get("deep_dive"):
            d = RESEARCH / "wallets" / r["wallet"]
            d.mkdir(parents=True, exist_ok=True)
            (d / "REPORT.md").write_text(wallet_report_md(r))


def render_dashboard(ledger: dict[str, Any], fragment: bool = False) -> str:
    tpl = (Path(__file__).parent / "dashboard_template.html").read_text()
    slim = dict(ledger)
    slim["wallets"] = [{k: v for k, v in r.items()} for r in ledger["wallets"]]
    data = json.dumps(to_jsonable(slim)).replace("</", "<\\/")
    body = tpl.replace("__DATA__", data)
    if fragment:
        return body
    return "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n</head>\n<body>\n" + body + "\n</body>\n</html>\n"


def write_summary_md(ledger: dict[str, Any]) -> None:
    import collections
    import re

    rows = ledger["wallets"]
    deep = sorted([r for r in rows if r.get("deep_dive")], key=lambda r: r.get("rank") or 0)
    lines = [
        "# Research results",
        "",
        f"Data as of {time.strftime('%Y-%m-%d', time.gmtime(ledger['as_of'])) if ledger.get('as_of') else 'n/a'} (UTC). Generated by `python -m polyrea.report`.",
        "",
        "## Funnel",
        "",
        "| Step | Wallets |",
        "| --- | --- |",
    ]
    lines += [f"| {f['label']} | {f['count']} |" for f in ledger["funnel"]]
    lines += ["", "## Deep-dived wallets", "", "| Rank | Wallet | Archetype | Verdict | Failed criteria | Partial |", "| --- | --- | --- | --- | --- | --- |"]
    labels = {k: l for k, l, _ in CRITERIA}
    for r in deep:
        crit = r["deep_dive"].get("criteria", {})
        failed = [labels[k] for k, _, _ in CRITERIA if (crit.get(k) or {}).get("status") == "fail"]
        partial = [labels[k] for k, _, _ in CRITERIA if (crit.get(k) or {}).get("status") == "partial"]
        lines.append(f"| {r['rank']} | [{r['name']}](wallets/{r['wallet']}/REPORT.md) | {r.get('archetype') or ''} | {r['verdict']} | {'; '.join(failed) or '-'} | {'; '.join(partial) or '-'} |")
    lines += ["", "## Criteria across deep-dived wallets", "", "Not sequential: every criterion was assessed for every wallet where possible.", "",
              "| Criterion | Pass | Partial | Fail | Not assessed |", "| --- | --- | --- | --- | --- |"]
    for k, label, _ in CRITERIA:
        st = [((r["deep_dive"].get("criteria", {}).get(k)) or {}).get("status", "untested") for r in deep]
        lines.append(f"| {label} | {st.count('pass')} | {st.count('partial')} | {st.count('fail')} | {len(st) - st.count('pass') - st.count('partial') - st.count('fail')} |")
    a1 = [r for r in rows if not r.get("deep_dive") and r["verdict"] == "reject"]
    categories = [
        ("no PnL history", "No PnL history returned"),
        ("insufficient pre-selection history", "Under 60 days of history before the ranking window"),
        ("not significant after Holm", "Pre-selection profit not significant (Holm, 500 tests)"),
        ("block-bootstrap", "Pre-selection block bootstrap p > 0.01"),
        ("deflated Sharpe", "Deflated Sharpe <= 0.95 (could be the luckiest of 500)"),
        ("last-30d PnL", "Last 30 days below $50k"),
        ("median monthly PnL", "Median 30-day block below $50k"),
        ("annualized Sharpe", "Annualized Sharpe below 3"),
        ("positive weeks", "Under 75% positive weeks"),
        ("positive months", "Under 80% positive months"),
        ("fetch error", "Data fetch error"),
    ]
    counter: collections.Counter = collections.Counter()
    for r in a1:
        for reason in r.get("reasons", []):
            label = next((lab for key, lab in categories if key in reason), "Other")
            counter[label] += 1
    lines += ["", f"## Stage A1 rejections ({len(a1)} wallets)", "", "A wallet can fail several criteria.", "", "| Reason | Wallets |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in counter.most_common(12)]
    lines += ["", "Full per-wallet detail: `ledger.json` and the dashboard (`../dashboard/index.html`).",
              "", "The adversarial review of the first round (code audit, a challenge of every verdict, an independent re-check of stage A1, and a completeness critique) "
              "is recorded in `review_2026-10-31/` with every reviewer's scripts and outputs; the defects it confirmed and how they were fixed are listed in `../docs/methodology.md`."]
    (RESEARCH / "README.md").write_text("\n".join(lines) + "\n")


def build_all(artifact_path: Path | None = None) -> dict[str, Any]:
    ledger = build_ledger()
    write_reports(ledger)
    write_summary_md(ledger)
    (ROOT / "dashboard").mkdir(exist_ok=True)
    (ROOT / "dashboard" / "index.html").write_text(render_dashboard(ledger))
    if artifact_path is not None:
        artifact_path.write_text(render_dashboard(ledger, fragment=True))
    return ledger


if __name__ == "__main__":
    import sys

    out = build_all(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    print(json.dumps(out["funnel"], indent=1))
