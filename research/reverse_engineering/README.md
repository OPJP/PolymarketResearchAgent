# Deep reverse engineering: run it locally

One expert reverse-engineering agent per approved strategy (the 12 wallets
that passed stage A1, grouped into 8 strategies where one operator runs
several wallets). Each agent works in iterations of about 60 minutes,
keeping a lab notebook so the next iteration continues where it stopped,
until it reaches the high-accuracy target, a wall, or 5 iterations. An
independent examiner then audits the frozen rule for look-ahead, scores it on
the holdout (2026-10-23 onward, which the agent never sees) and judges
criteria (6) match, (7) backtest, (8) replicable and (9) persists ("this
strategy is statistically significant to continue working if I deployed it
now"). Three skeptics (leakage, statistics, deployability lenses) then try to
refute every criterion the examiner passed; a pass survives only if most of
them cannot refute it. After every iteration and examination the workflow
rebuilds the dashboard and commits the workspace to the research branch, so
GitHub carries the progress.

- `BRIEF.md`: the rules every agent follows (holdout, no future data, data
  sources, metrics, accuracy target, stopping rule, files to keep).
- `deep_reverse_engineering.workflow.js`: the Claude Code workflow script.
- `strategies.json`: its arguments (the 8 strategies and their dossiers).
- `<strategy>/`: each agent's workspace (`NOTES.md`, `state.json`,
  `FINAL_RULE.md`, `code/`, results; `EXAM.md`, `results/exam.json`,
  `results/refute_*.json` and `results/adjudication.json` once examined).
- `tools/resources.py`: memory and disk gate the agents run before heavy jobs.

## Status when the cloud run was stopped (2026-10-31)

Iteration 1 finished for four strategies; the other four had just started
(their notebooks hold setup notes only). No holdout examination has run yet.
Scores are on each agent's VALIDATE period, before the holdout:

| Strategy | Primary metric (VALIDATE) | Best rule so far |
| --- | --- | --- |
| btc5m-bot | presence AUC 0.892 | LightGBM behaviour clone on spot + tape features |
| elmcap2-carry | presence AUC 0.896 | LightGBM behaviour clone on CLOB price, time to end |
| directional-maker | presence AUC 0.772 | LightGBM presence model per 10-s bin |
| dbdd-inplay-taker | selection AUC 0.731 | LightGBM score over in-play taker prints |
| jld-inplay-taker, rebate-farmer, rn1-inplay-maker, tommy-cs2-maker | not yet scored | iteration 1 had just started |

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
entries. Options in the args: `concurrency` (strategies worked on at once,
default 2), `order` (priority), `max_iters` (default 5), `max_minutes`
(default 300 per strategy), `branch` (where progress is pushed), and per
strategy `resume` (true continues from the notebook in its workspace; set it
to false and delete the workspace to start over) and `prior_iters` /
`prior_minutes` / `prior_scores` (work from an earlier run that counts toward
the budget and the diminishing-returns wall).

The local run (from 2026-10-31) is on a laptop with 12.9 GB of RAM shared
with the desktop, so `concurrency` is 2 and every agent keeps its Python
jobs under about 1 GB and waits for free memory before heavy jobs (see
"Local run" in `BRIEF.md`). With more memory, raise `concurrency`.

## After a run

Each examined strategy has `EXAM.md` and `results/exam.json` with the
holdout metrics and the examiner's judgment on criteria (6)-(9), and
`results/adjudication.json` with the criteria after the skeptics. The
dashboard's "Deep reverse engineering" table shows both. Update
`research/verdicts/<wallet>.json` with them and rebuild the ledger, reports
and dashboard:

```bash
.venv/Scripts/python.exe -m polyrea.report
```
