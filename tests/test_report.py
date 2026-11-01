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
    (research / "stage_a" / "stage_a1.json").write_text(json.dumps({"evidence": {"subject": {"as_of": 1_790_000_000}}, "wallets": wallets}), encoding="utf-8")
    ok = {k: {"status": "pass", "detail": "x"} for k in ("roc", "onchain", "match", "backtest", "replicable", "persistence")}
    (research / "verdicts" / "0xa.json").write_text(json.dumps({"wallet": "0xa", "verdict": "pass", "stage": "C", "criteria": ok}), encoding="utf-8")
    bad = dict(ok, match={"status": "fail", "detail": "no"})
    (research / "verdicts" / "0xb.json").write_text(json.dumps({"wallet": "0xb", "verdict": "reject", "stage": "C", "criteria": bad}), encoding="utf-8")
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


def test_deep_re_progress_from_workspaces(tmp_path, monkeypatch):
    research = _setup(tmp_path, monkeypatch)
    re_dir = research / "reverse_engineering"
    for key in ("s1", "s2", "s3"):
        (re_dir / key / "results").mkdir(parents=True)
    (re_dir / "strategies.json").write_text(json.dumps({"strategies": [
        {"key": "s1", "title": "one", "wallets": ["0xa"]}, {"key": "s2", "title": "two"}, {"key": "s3", "title": "three"}, {"key": "s4"}]}), encoding="utf-8")
    (re_dir / "s1" / "state.json").write_text(json.dumps({"primary_metric": "auc", "best": {"rule_id": "R1"},
        "iterations": [{"n": 1, "minutes": 50, "best_validate_score": 0.7}, {"n": 2, "minutes": 55, "best_validate_score": 0.81}]}), encoding="utf-8")
    (re_dir / "s1" / "results" / "exam.json").write_text(json.dumps({"target_met": False, "leakage_check": {"passed": True, "details": ""},
        "criteria": {"match": "partial", "backtest": "fail", "replicable": "fail", "persists": "fail"}}), encoding="utf-8")
    (re_dir / "s2" / "state.json").write_text(json.dumps({"status": "wall", "wall_reason": "information wall", "iterations": [{"n": 1, "minutes": 60}]}), encoding="utf-8")
    (re_dir / "s3" / "state.json").write_text(json.dumps({"iterations": [{"n": 1, "minutes": 60, "best_validate_score": 0.6}]}), encoding="utf-8")
    (re_dir / "s3" / "results" / "exam.json").write_text(json.dumps({"target_met": True, "criteria": {"match": "pass", "backtest": "pass"}}), encoding="utf-8")
    (re_dir / "s3" / "results" / "adjudication.json").write_text(json.dumps({"criteria": {"backtest": "fail"}}), encoding="utf-8")
    led = report.build_ledger()
    by = {s["key"]: s for s in led["deep_re"]}
    assert by["s1"]["status"] == "examined" and by["s1"]["iterations"] == 2 and by["s1"]["minutes"] == 105
    assert by["s1"]["best_validate_score"] == 0.81 and by["s1"]["exam"]["criteria"]["match"] == "partial"
    assert by["s2"]["status"] == "wall" and by["s2"]["best_validate_score"] is None
    assert by["s3"]["status"] == "adjudicated" and by["s3"]["adjudication"]["criteria"]["backtest"] == "fail"
    assert by["s3"]["exam_rounds"] == 1 and by["s3"]["wall_audits"] == 0
    assert by["s4"]["status"] == "not_started"
    report.write_summary_md(led)
    md = (research / "README.md").read_text(encoding="utf-8")
    assert "| [s3](reverse_engineering/s3/NOTES.md) | adjudicated | 1 (60 min) | 0.600 | 1 | 0 (0) | yes | pass | fail |" in md
    html = report.render_dashboard(led, fragment=True)
    assert '"deep_re"' in html and 're-rows' in html

    # An agent that keeps working after a failed exam is in progress again; the workflow's progress file sets the stage.
    s1 = json.loads((re_dir / "s1" / "state.json").read_text(encoding="utf-8"))
    (re_dir / "s1" / "state.json").write_text(json.dumps({**s1, "status": "continue", "strategy_statement": "quotes at fair minus 1c"}), encoding="utf-8")
    (re_dir / "s3" / "results" / "progress.json").write_text(json.dumps({"stage": "decoded", "exam_rounds": 2, "panels": 4,
        "wall_audits": [{"n": 1, "accepted": False}, {"n": 2, "accepted": False}]}), encoding="utf-8")
    by = {s["key"]: s for s in report.build_ledger()["deep_re"]}
    assert by["s1"]["status"] == "in_progress" and by["s1"]["strategy_statement"] == "quotes at fair minus 1c"
    assert by["s3"]["status"] == "decoded" and by["s3"]["exam_rounds"] == 2
    assert by["s3"]["wall_audits"] == 2 and by["s3"]["walls_rejected"] == 2 and by["s3"]["panels"] == 4
