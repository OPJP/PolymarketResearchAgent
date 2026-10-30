# Polymarket Research Agent

Reverse engineering the strategies of Polymarket's most profitable wallets from
public data, and testing whether each strategy is real, reproducible,
replicable on ordinary hardware, and still working.

The toolkit, **polyrea**, adapts the investigation flow of
[REA (Reverse Engineer Anything)](https://github.com/morluto/rea) from binaries
to trading wallets: an agent asks about one wallet, polyrea inspects and traces
it through analysis adapters, every result comes back as an Evidence envelope
(observed / derived / inferred facts, sources, coverage, limitations,
unknowns), and the agent uses that evidence to form and test hypotheses through
the same tools.

- Dashboard: [`dashboard/index.html`](dashboard/index.html) (open locally or via GitHub Pages)
- Research ledger (one record per wallet): [`research/ledger.json`](research/ledger.json)
- Per-wallet dossiers: `research/wallets/<wallet>/REPORT.md`
- Methodology and pre-registered thresholds: [`docs/methodology.md`](docs/methodology.md)

## Results (data as of 2026-10-30)

**No wallet in the top 500 passed every criterion.** Full detail in
[`research/README.md`](research/README.md) and the dashboard.

| Step | Wallets |
| --- | --- |
| Screened (top 500 by monthly PnL) | 500 |
| Profit significant outside the ranking window, above $50k/month, constant returns | 11 |
| At least 10% per month on peak capital at risk | 10 |
| Fills verified on Polygon | 10 |
| Reverse-engineered rule matches the wallet on held-out data | 0 |

What the 11 survivors actually do:

- **BTC 5-minute Up/Down bots** (GoodFallen, x-MoneyForWhiskas,
  dangerously-skip-permissions): one operator across three wallets that also
  trade against each other. No public-data rule matches them; the market price
  already beats a 1-second public spot model, so their edge is sub-second.
  About half their profit is the 50% Obsidian fee rebate.
- **Directional crypto makers** (bosona, almach, likely one operator): real,
  persistent, rebate-independent profit, but every public-data maker version
  loses 14-26% in the same windows, even with optimistic fills. Their edge is
  queue priority and fast cancels.
- **Rebate farmer** (0xb55f...): trading loses $49k a month; the whole profit
  is the fee rebate. A newcomer at the 0% tier would lose ~$40k a month.
- **In-play sports and esports makers** (RN1, TommyLeePeeca): they cancel
  quotes within seconds of game events; a public-data maker in the same
  markets loses 8-19%.
- **In-play sports takers** (justaluckydude, 0xdbdd...): justaluckydude buys the
  scoring side within 0-10 s of a play (95% direction agreement), but the
  public-data rule is not significantly profitable, a 5-second delay removes the
  edge, and its PnL has a significant downward trend.
- **High-probability carry** (elmcap2): 3.7% per month on $6.5M of capital.

## Install

```bash
python3 -m venv .venv
```

```bash
. .venv/bin/activate
```

```bash
pip install -e '.[test]'
```

## Use it from an agent (MCP)

`.mcp.json` registers the server for Claude Code and other MCP clients:

```json
{"mcpServers": {"polyrea": {"command": "python", "args": ["-m", "polyrea.server"]}}}
```

Tools (REA tool shapes):

| Shape | Tools |
| --- | --- |
| list | `list_leaderboard`, `list_external_sources` |
| inspect | `inspect_wallet_pnl`, `inspect_market`, `inspect_research_ledger` |
| trace | `trace_wallet_fills` (API fills joined to decoded on-chain `OrderFilled` events, with maker/taker role) |
| compare | `updown_study` (hypothesis vs. the wallet's actual decisions on crypto Up/Down markets) |
| workflow | `screen_leaderboard`, `investigate_wallet`, `assess_persistence` |
| external data | `register_external_source`, `fetch_external_series`, `spot_seconds` |
| ledger | `record_verdict` |

Additional study workflows (Python API, used by the research run):
`polyrea.workflows.updown_study.run_updown_maker_study` (directional maker) and
`polyrea.workflows.sports_study.run_sports_study` (in-play reaction to ESPN
play-by-play).

## Use it from a terminal

```bash
polyrea --list
```

```bash
polyrea inspect_wallet_pnl --wallet 0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6
```

```bash
polyrea register_external_source --name fred.dgs10 --url-template 'https://example.org/api?start={start_iso}&end={end_iso}' --records-path observations --time-field date --value-field value --time-unit iso --availability-lag-seconds 86400
```

## No future data

Strategies only read data through a point-in-time view: each record carries
the time it describes and the time it became public, and a decision at `t`
can only see records public by `t` (`LookAheadError` otherwise). Market
resolution and other post-hoc fields are reserved for settlement. Fast
vectorized code is audited on every run against the guarded view and against
data physically truncated at the decision time, and tests corrupt all future
data and require identical decisions. See `docs/methodology.md`.

## Tests

```bash
pytest
```

The suite covers statistical calibration (HAC t-test size under
autocorrelation, bootstrap and deflated-Sharpe null behaviour, Holm/BH), the
point-in-time layer (availability lags, masked fields, leak detection),
cursor pagination merges, on-chain receipt decoding for both exchange versions,
ledger accounting, the Up/Down fair-value audit, match-test power and
specificity on synthetic informed and random wallets, trade-through fill rules,
MCP tool contracts, and an end-to-end MCP stdio session. Tests that hit live
endpoints are marked `live` and excluded by default.

## Layout

```
polyrea/
  evidence.py        Evidence envelope (REA result contract)
  pit.py             point-in-time store/view, look-ahead audit, external source registry
  adapters/          data-api, gamma, clob, Polygon receipts, Kraken spot, ESPN
  stats/             significance (HAC, bootstrap, PSR/DSR, Holm, BH), persistence
  analysis/          PnL frames, ledger, profile, Up/Down fair value + match test + backtests
  workflows/         screen (A1), investigate (A2/B), updown_study, sports_study (C)
  tools.py server.py cli.py   shared tool layer, MCP server, CLI
  report.py          ledger, dossiers, dashboard
research/            stage A snapshot and results, per-wallet evidence, verdicts, ledger
dashboard/           generated dashboard
docs/                methodology
```
