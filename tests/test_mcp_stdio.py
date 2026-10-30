"""End-to-end MCP over stdio: spawn the server, handshake, list tools, call one."""

import asyncio
import json
import os
import sys

import pytest


def test_stdio_handshake_and_call(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = {**os.environ, "POLYREA_RESEARCH_DIR": str(tmp_path), "POLYREA_OFFLINE": "1"}
    params = StdioServerParameters(command=sys.executable, args=["-m", "polyrea.server"], env=env)

    async def run():
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                listed = await s.list_tools()
                names = {t.name for t in listed.tools}
                res = await s.call_tool("record_verdict", {"wallet": "0xabc", "verdict": "reject", "stage": "A1", "reasons": ["test"]})
                return names, res

    names, res = asyncio.run(run())
    assert {"investigate_wallet", "updown_study", "screen_leaderboard", "register_external_source"} <= names
    text = res.content[0].text
    assert json.loads(text)["recorded"]["verdict"] == "reject"
    assert json.loads((tmp_path / "ledger.json").read_text())["wallets"][0]["wallet"] == "0xabc"
