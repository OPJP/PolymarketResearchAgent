# Deep reverse engineering: run it locally

One expert reverse-engineering agent per approved strategy. These are the 12
wallets that passed stage A1, grouped into 8 strategies where one operator
runs several wallets.

**The premise (since 2026-10-31).** Every wallet passed a strict
significance screen, so a real strategy exists, and not finding it counts as
a failed investigation, not as a result. The first local run let agents
declare a "diminishing returns" wall after about 3 hours. The user rejected
that, so the run now works like this:

- **Iterations.** Each agent works in iterations of about 100 minutes, for
  up to about 20 hours per strategy. It keeps a lab notebook, and at the start
  of each iteration it writes five or more competing explanations.
- **Decoding.** The agent decodes the strategy component by component
  (selection, timing, side, price, size, exit) and works through a mandatory
  direction catalog:
  - settlement feeds, other venues and derivatives, faster event feeds,
    Polymarket's own data;
  - calldata order reconstruction, quote inverse-fitting, complements and
    merges, rebates and rewards;
  - sibling wallets, copy trading, counterparties, bot versions;
  - other targets and model classes, replay, PnL decomposition.
- **On-chain decision times.** V2 `matchOrders` calldata carries every
  filled order's millisecond signing time, so each order's decision time can
  be lined up against every feed.
- **Live lab.** One shared recorder (`tools/live.py`, started 2026-10-31 for
  120 hours) records:
  - the CLOB order books of the BTC/ETH/SOL 5m, 15m and 4h Up/Down windows;
  - the books of the markets the sports and event wallets are trading;
  - Polymarket's Chainlink price and 60-second TWAP (the BTC Up/Down
    settlement source);
  - Polymarket's sports websocket.
  It files every record into a development or a sealed folder by the
  calendar.
- **Panel.** After every iteration, three fresh-eyes experts (information
  source, mechanics and on-chain forensics, assumption breaker) read the
  notebook and propose untried directions. The next iteration must test them
  or rule them out with a measurement.
- **No diminishing-returns stop.** Two iterations without progress force a
  pivot to a different paradigm.
- **Walls.** A wall can be claimed only after 10+ hours, with every catalog
  item closed by evidence and a quantitative account of what is unexplained.
  It stands only if three independent auditors all fail to name an untried
  direction. A rejected wall turns the auditors' directions into the next
  to-do list.
- **Sealed calendar** (pre-registered, `tools/sealed.py`):
  - the holdout days 2026-10-23..30 form two exam lots by alternating day
    (`h1`, `h2`);
  - from 2026-10-31, 6-hour blocks alternate between development and sealed,
    rotating so each time of day is in both;
  - units (windows, games, events) are assigned by their start or
    resolution.
- **Target claims.** A target claim is checked against the agent's own
  VALIDATE numbers for every target condition before any sealed data is
  spent.
- **Exams.** An independent examiner audits the frozen rule for look-ahead,
  scores it on the next lot (`h1`, then `h2`, then future sealed blocks),
  and judges criteria (6) match, (7) backtest, (8) replicable and
  (9) persists ("this strategy is statistically significant to continue
  working if I deployed it now"). Match passes only if the whole
  pre-registered target holds:
  - at least 80% coverage of fills and PnL;
  - presence or selection at least 0.05 AUC above the stronger of two
    activity-only baselines;
  - side, price and PnL-correlation thresholds;
  - alpha 0.0025 across up to 4 rounds;
  - replication on both halves of the lot.
- **Skeptics.** Three skeptics try to refute every criterion the examiner
  passed; for match the lenses are leakage, statistics and match validity. A
  pass survives only if all three return, none finds it fatally wrong, and
  at most one finds a material flaw.
- **Failed exams.** If the match is not a pass, the lot is released to that
  strategy as development data, the examiner's diagnosis (from the lot's
  first half) and the skeptics' objections go back to the agent, and it
  continues on the next lot, for up to 4 exams.
- **GitHub.** After every iteration, wall audit and exam, the workflow writes
  `results/progress.json`, rebuilds the dashboard, and commits the workspace
  to the research branch, so GitHub carries the progress.

- `BRIEF.md`: the rules every agent follows (premise, sealed data and live
  lab, no future data, decoding by component, the direction catalog, data
  sources, metrics, accuracy target, the wall, files to keep).
- `deep_reverse_engineering.workflow.js`: the Claude Code workflow script.
- `strategies.json`: its arguments (the 8 strategies and their dossiers).
- `<strategy>/`: each agent's workspace (`NOTES.md`, `state.json`,
  `FINAL_RULE.md`, `code/`, results; `panels/iter<n>_<lens>.md`;
  `results/wall_audit_<n>_<lens>.json`; per exam round `EXAM_r<k>.md`,
  `results/exam_r<k>.json`, `results/refute_r<k>_*.json` and
  `results/adjudication_r<k>.json`, with the latest round also copied to
  `EXAM.md`, `results/exam.json` and `results/adjudication.json`;
  `results/progress.json`).
- `tools/resources.py`: memory and disk gate the agents run before heavy jobs.
- `tools/sealed.py`: the sealed calendar (`sealed.py <key>` prints a
  strategy's development and sealed periods; examiners release lots with it).
- `tools/live.py`: the shared live recorder (`live.py status`) and
  `iter_live`, the reader that returns development blocks only.

## Status at the restart under the new premise (2026-10-31, about 11:30 UTC)

Scores are each agent's VALIDATE period, before sealed data. The first local
run had examined only directional-maker:

| Strategy | Iterations so far | Best VALIDATE score | Note |
| --- | --- | --- | --- |
| directional-maker | 3 (152 min) | presence AUC 0.763 (0.772 earlier metric) | exam round 1 (all of h1 and h2) failed: match partial (0.700 vs 0.681 activity-only), rule -12.8%, wallets +3.95%. Its wall is reopened and its diagnosis goes back to the agent; its next exam uses future sealed blocks |
| btc5m-bot | 4 (192 min) | presence AUC 0.913 (activity-only 0.889) | iteration 5 was interrupted at the restart |
| tommy-cs2-maker | 0 | - | iteration 1 was interrupted after about 10 minutes |
| elmcap2-carry | 1 (48 min, cloud) | presence AUC 0.896 | |
| dbdd-inplay-taker | 1 (50 min, cloud) | selection AUC 0.731 | |
| rn1-inplay-maker, jld-inplay-taker, rebate-farmer | 0 | - | setup notes only |

## Setup

```bash
git clone https://github.com/OPJP/PolymarketResearchAgent.git
```

```bash
cd PolymarketResearchAgent
```

```bash
python -m venv .venv
```

On Windows the interpreter is `.venv/Scripts/python.exe`; on Linux and macOS
it is `.venv/bin/python`.

```bash
.venv/Scripts/python.exe -m pip install -e ".[test,research]"
```

```bash
.venv/Scripts/python.exe -m pytest -q
```

The HTTP cache (`.cache/http.sqlite`, about 1.2 GB) and the agents' large
intermediate data (`.cache/re/`) are not in git, so a first run downloads
again from the public sources it uses: Polymarket data-api and Gamma,
Polygon RPC (`polygon.drpc.org`), the Binance public archive
(`data.binance.vision`), Kraken, Coinbase/OKX candles and ESPN. Expect the
first iteration of each strategy to spend much of its time fetching. All
fetches are cached, so later iterations and reruns are fast.

## Run

Open Claude Code in the repository root and ask it to run the workflow, for
example:

> Use a workflow: run research/reverse_engineering/deep_reverse_engineering.workflow.js
> with the args in research/reverse_engineering/strategies.json.

To run only some strategies, pass a `strategies` list with just those
entries. Options in the args:

- `concurrency`: strategies worked on at once (3).
- `order`: priority.
- `max_minutes`: budget per strategy (1200).
- `min_wall_minutes`: no wall claim before this (600).
- `iter_minutes`: length of one iteration (100).
- `max_exams`: exam rounds per strategy (4).
- `branch`: where progress is pushed.
- Per strategy:
  - `prior_iters`, `prior_minutes`, `prior_scores`: work from earlier runs,
    counted toward the budget.
  - `sealed_min_hours`: the sealed time a future exam lot needs (12 for crypto
    windows, 24 for the others).
  - `released` and `future_examined_until`: calendar lots the strategy
    already has as development data.
  - `prior_exams` and `prior_diagnosis`: an exam that already ran.
  - `interrupted`: a note about files left by an interrupted iteration.

The local run is on a laptop with 12.9 GB of RAM shared with the desktop, so
every agent keeps its Python jobs under about 1 GB and waits for free memory
before heavy jobs (see "Local run" in `BRIEF.md`). Panels and auditors keep
theirs smaller. Worst case the run takes about 8 x 20 hours / 3, so roughly
two to three days. Stop it at any time; it can be resumed (the workflow tool
reuses finished agents' results), and every checkpoint is already on GitHub.

## After a run

Each examined strategy has `EXAM.md` and `results/exam.json` (latest round)
with the sealed-data metrics, the examiner's judgment on the components and on
criteria (6)-(9), and `results/adjudication.json` with the criteria after the
skeptics. `results/progress.json` says how the strategy ended: decoded, wall
accepted, budget exhausted or exams exhausted. The
dashboard's "Deep reverse engineering" table shows both. Update
`research/verdicts/<wallet>.json` with them and rebuild the ledger, reports
and dashboard:

```bash
.venv/Scripts/python.exe -m polyrea.report
```
