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

## Results (data as of 2026-10-30; reviewed 2026-10-31)

**No wallet in the top 500 passes every criterion.** Full detail in
[`research/README.md`](research/README.md), the per-wallet `REPORT.md` files
and the dashboard. The first round was audited by independent adversarial
reviewers; six code defects were confirmed and fixed and every study was
re-run (see "Changes after first run" in
[`docs/methodology.md`](docs/methodology.md); reviewer outputs are in
[`research/review_2026-10-31/`](research/review_2026-10-31/)).

| Step (each keeps only wallets that passed the steps above) | Wallets |
| --- | --- |
| Screened (top 500 by monthly PnL) | 500 |
| Profit significant outside the ranking window, above $50k/month, constant returns | 12 |
| At least 10% per month on capital at risk | 11 |
| Fills verified on Polygon | 11 |
| Reverse-engineered rule matches the wallet on held-out data | 0 (11 partial matches) |

Per criterion, across the 12 wallets: no held-out backtest passes, no
strategy is replicable from public data on a normal connection, and only
half still meet the persistence tests. A1 re-run one day later admits no new
wallet.

What the 12 survivors actually do:

- **BTC 5-minute Up/Down bots** (GoodFallen, x-MoneyForWhiskas,
  dangerously-skip-permissions; one operator): their passive bids get filled
  right after Binance spot moves toward that side, and a public rule built on
  that signature picks out their fills far better than chance (stratified
  AUC 0.60-0.63, z 9-14). Traded as a strategy, the rule loses 5-9% on 2,011
  unseen windows once fills are timed correctly; it only looks profitable if
  an order is credited with trades that may have matched before it existed.
  About half of their profit is the top taker-rebate tier.
- **Directional crypto makers** (bosona, almach, mo-money; one operator):
  real profit with little rebate dependence; no public-data maker built from
  the same data is significantly profitable in the same windows (results
  from -19% to +2%; fixed-price bids lose 45-81%). mo-money only entered after the dormant-weeks fix; its profit is
  shrinking.
- **Rebate farmer** (0xb55f...): trading loses $49k a month; the profit is a
  Diamond-tier rebate plus a one-off $25k level-up bonus. Recurring month
  $31k; a newcomer at the 0% tier loses about $40k.
- **In-play makers** (RN1, TommyLeePeeca): off the book before game events
  move the public price; a public-data maker loses 5-19% in the same
  markets, including RN1's most profitable families. TommyLeePeeca switched
  from taking to making on 16-17 October, so its profitable strategy has 13
  days of history.
- **In-play takers** (justaluckydude, 0xdbdd...): identifiable reactions to
  scoring plays and soccer goals, but no public rule is significantly
  profitable with a realistic information delay; justaluckydude's profit is
  decaying.
- **Event carry** (elmcap2): about 4% per month on $5.7M of capital, and its
  month is one FOMC meeting.

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
| workflow | `screen_leaderboard`, `investigate_wallet`, `assess_persistence`, `assess_rebate_dependence` |
| external data | `register_external_source`, `fetch_external_series`, `spot_seconds` |
| ledger | `record_verdict` |

Additional study workflows (Python API, used by the research run):

- `polyrea.workflows.updown_study.run_updown_maker_study`: directional (DM) and
  spot-reactive (SR) maker hypotheses on passive fills, with executable
  backtests under strict and at-touch fills.
- `polyrea.workflows.updown_study.run_frozen_rule_extension`: the FIT-chosen
  rules evaluated, frozen, on every unseen block of the TEST week and on days
  after `as_of`.
- `polyrea.workflows.sports_study.run_sports_study`: in-play reaction to ESPN
  play-by-play (information delay of at least 5 s).
- `polyrea.workflows.maker_study.run_maker_replicability_study`: tape-only
  two-sided maker in the wallet's own markets.

Spot data: Kraken trades (`spot_source="kraken"`) or the Binance 1-second
archive (`spot_source="binance"`, checksum-verified), both reduced to
per-second prices available one second after the second ends.

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
autocorrelation and at Holm-level alphas with the exact reference, bootstrap
and deflated-Sharpe null behaviour, Holm/BH), the point-in-time layer
(availability lags, masked fields, leak detection), cursor pagination
(including one-second offset walks on dense tapes), on-chain receipt decoding
for both exchange versions, ledger accounting (sells, complete sets, rebate
tiers and level-up bonuses), the Up/Down fair-value audit, match-test power on
synthetic informed wallets and specificity against random and spot-blind
wallets that prefer certain prices or times (the rotation null must not be
fooled), trade-through fill rules for every maker model, the sports
information-delay guard, MCP tool contracts, and an end-to-end MCP stdio
session. Tests that hit live endpoints are marked `live` and excluded by
default.

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
