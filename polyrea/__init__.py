"""polyrea: reverse engineer Polymarket wallet strategies from public data.

The package follows the investigation flow of REA (https://github.com/morluto/rea):

1. Ask      - an agent asks a question about one wallet (the "local target").
2. Inspect  - polyrea tools inspect and trace that wallet through analysis
              adapters (Polymarket data API, Gamma, CLOB, Polygon RPC, exchanges).
3. Evidence - every tool returns an Evidence envelope that keeps observed,
              derived and inferred facts apart, with sources, coverage,
              limitations and unknowns.
4. Use      - the agent explains / implements / tests a strategy hypothesis and
              asks follow-up questions through the same tools.
"""

__version__ = "0.1.0"
