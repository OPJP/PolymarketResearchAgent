import json

from polyrea import report


def _setup(tmp_path, monkeypatch):
    research = tmp_path / "research"
    (research / "stage_a").mkdir(parents=True)
    (research / "verdicts").mkdir()
    m = {"last_30d_pnl": 60000, "median_month_pnl": 70000, "annual_sharpe": 5.0, "share_positive_weeks": 0.9, "share_positive_months": 1.0,
         "pre_selection_days": 90, "hac_t_pre": 5.0, "p_holm_pre": 1e-5, "p_boot_pre": 1e-4, "deflated_sharpe": 0.99, "history_days": 120}
    wallets = [
        {"wallet": "0xa", "name": "A", "rank": 1, "lb_pnl": 1, "lb_volume": 1, "stage_a1_pass": True, "stage_a1_reasons": [], "metrics": m},
        {"wallet": "0xb", "name": "B", "rank": 2, "lb_pnl": 1, "lb_volume": 1, "stage_a1_pass": True, "stage_a1_reasons": [], "metrics": m},
        {"wallet": "0xc", "name": "C", "rank": 3, "lb_pnl": 1, "lb_volume": 1, "stage_a1_pass": False, "stage_a1_reasons": ["deflated Sharpe 0.1 < 0.95"], "metrics": {"history_days": 10}},
    ]
    (research / "stage_a" / "stage_a1.json").write_text(json.dumps({"evidence": {"subject": {"as_of": 1_790_000_000}}, "wallets": wallets}))
    ok = {k: {"status": "pass", "detail": "x"} for k in ("roc", "onchain", "match", "backtest", "replicable", "persistence")}
    (research / "verdicts" / "0xa.json").write_text(json.dumps({"wallet": "0xa", "verdict": "pass", "stage": "C", "criteria": ok}))
    bad = dict(ok, match={"status": "fail", "detail": "no"})
    (research / "verdicts" / "0xb.json").write_text(json.dumps({"wallet": "0xb", "verdict": "reject", "stage": "C", "criteria": bad}))
    monkeypatch.setattr(report, "RESEARCH", research)
    return research


def test_ledger_merges_verdicts_and_funnel(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    led = report.build_ledger()
    by = {w["wallet"]: w for w in led["wallets"]}
    assert by["0xa"]["verdict"] == "pass" and by["0xc"]["verdict"] == "reject"
    assert by["0xa"]["deep_dive"]["criteria"]["significance"]["status"] == "pass"  # filled from metrics
    counts = [f["count"] for f in led["funnel"]]
    assert counts[:2] == [3, 2]
    labels = [f["label"] for f in led["funnel"]]
    assert counts[labels.index("Strategy match")] == 1  # 0xb drops at the match step
    assert counts[-1] == 1


def test_dashboard_embeds_data_safely(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    led = report.build_ledger()
    led["wallets"][0]["name"] = "</script><b>x"
    html = report.render_dashboard(led, fragment=True)
    assert "</script><b>x" not in html  # closing tag escaped inside the JSON block
    assert html.startswith("<title>")
    full = report.render_dashboard(led)
    assert full.startswith("<!doctype html>")
