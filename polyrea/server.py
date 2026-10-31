"""polyrea MCP server (stdio). Register with: ``polyrea-mcp`` or ``python -m polyrea.server``."""

from __future__ import annotations

import inspect

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore[no-redef]

from polyrea import tools

INSTRUCTIONS = """polyrea reverse engineers Polymarket wallet strategies from public data.
Flow: list_leaderboard -> screen_leaderboard (significance without reverse
engineering) -> investigate_wallet (capital, on-chain maker/taker verification,
per-market decomposition) -> hypothesis tests (updown_study, ...) ->
assess_persistence -> record_verdict. Results are Evidence envelopes; keep
observed, derived and inferred facts apart and read limitations/unknowns.
No-future-data rule: decisions at time t may only use records with
available_ts <= t; post-hoc market fields (resolution, final volume) are for
settlement only. External public data: list_external_sources /
register_external_source / fetch_external_series."""

mcp = _Server("polyrea", instructions=INSTRUCTIONS)

for _name, _fn in tools.TOOLS.items():
    mcp.tool(name=_name, description=inspect.getdoc(_fn) or _name)(_fn)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
