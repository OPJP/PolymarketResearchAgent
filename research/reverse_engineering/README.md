# Deep reverse engineering: run it locally

One expert reverse-engineering agent per approved strategy (the 12 wallets
that passed stage A1, grouped into 8 strategies where one operator runs
several wallets). Each agent works in iterations of about 60 minutes,
keeping a lab notebook so the next iteration continues where it stopped,
until it reaches the high-accuracy target, a wall, or 5 iterations. An
independent examiner then audits the frozen rule for look-ahead and scores
it on the holdout (2026-10-23 onward), which the agent never sees.

- `BRIEF.md`: the rules every agent follows (holdout, no future data, data
  sources, metrics, accuracy target, stopping rule, files to keep).
- `deep_reverse_engineering.workflow.js`: the Claude Code workflow script.
- `strategies.json`: its arguments (the 8 strategies and their dossiers).
- `<strategy>/`: each agent's workspace (`NOTES.md`, `state.json`,
  `FINAL_RULE.md`, `code/`, results; `EXAM.md` once examined).

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
python3 -m venv .venv
```

```bash
.venv/bin/pip install -e '.[test,research]'
```

```bash
.venv/bin/python -m pytest -q
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
entries. Options in the args: `max_iters` (default 5), `max_minutes` (default
300 per strategy), and per strategy `resume` (true continues from the notebook
in its workspace; set it to false and delete the workspace to start over).

Claude Code runs at most min(16, CPU cores - 2) agents of one workflow at a
time. Each agent's Python processes are asked to stay under about 3 GB, so
plan on roughly 3-4 GB of memory per concurrent agent.

## After a run

Each examined strategy has `EXAM.md` and `results/exam.json` with the
holdout metrics and the judgment on criteria (6) match, (7) backtest and (8)
replicable. Update `research/verdicts/<wallet>.json` with them and rebuild the
ledger, reports and dashboard:

```bash
.venv/bin/python -m polyrea.report
```
