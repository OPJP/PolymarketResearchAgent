"""Contract tests: every tool is registered with a schema, CLI parsing mirrors signatures."""

import asyncio
import inspect

from polyrea import tools
from polyrea.cli import _parser_for, main


def test_every_tool_registered_with_schema():
    from polyrea.server import mcp

    listed = asyncio.run(mcp.list_tools())
    names = {t.name for t in listed}
    assert names == set(tools.TOOLS)
    for t in listed:
        assert t.description and len(t.description) > 10
        schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema")
        assert schema["type"] == "object"
        fn = tools.TOOLS[t.name]
        required = {p for p, v in inspect.signature(fn).parameters.items() if v.default is inspect.Parameter.empty}
        assert set(schema.get("required", [])) == required


def test_cli_parsers_build_for_all_tools():
    for name, fn in tools.TOOLS.items():
        p = _parser_for(name, fn)
        assert p.prog.endswith(name)


def test_cli_list(capsys):
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "investigate_wallet" in out and "updown_study" in out


def test_record_verdict_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "RESEARCH_DIR", tmp_path)
    tools.record_verdict("0xABC", "reject", "A1", ["reason"], summary="s")
    tools.record_verdict("0xabc", "pass", "C", ["ok"])
    led = tools.inspect_research_ledger()
    assert len(led["wallets"]) == 1 and led["wallets"][0]["verdict"] == "pass"
    import pytest

    with pytest.raises(ValueError):
        tools.record_verdict("0xabc", "maybe", "C", [])


def test_register_external_source(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "RESEARCH_DIR", tmp_path)
    tools.register_external_source("fred.dgs10", "https://example.org/x?s={start}", "obs", "date", "value", time_unit="iso", availability_lag_seconds=86400)
    names = {s["name"] for s in tools.list_external_sources()["sources"]}
    assert "fred.dgs10" in names and "coinbase.btcusd.1m" in names
