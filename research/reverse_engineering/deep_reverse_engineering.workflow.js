export const meta = {
  name: 'deep-reverse-engineering',
  description: 'One expert reverse-engineering agent per approved strategy, iterating until high accuracy or a wall, then an independent holdout examiner',
  phases: [
    { title: 'Reverse engineer', detail: 'iterations of ~60 min per strategy, checkpointed in a lab notebook' },
    { title: 'Examine', detail: 'independent leakage audit and frozen evaluation on the holdout' },
  ],
}

// args: { strategies: [{ key, title, dossier, resume? }], max_iters?, max_minutes? }
// resume: true continues from an existing workspace (NOTES.md, state.json) instead of starting fresh.
const MAX_ITERS = (args && args.max_iters) || 5
const MAX_MINUTES = (args && args.max_minutes) || 300
const STRATS = args.strategies

const ITER = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['continue', 'target_reached', 'wall'] },
    wall_reason: { type: 'string' },
    primary_metric: { type: 'string', description: 'pre-registered primary metric name, fixed across iterations' },
    best_validate_score: { type: 'number', description: 'best VALIDATE value of the primary metric so far (higher is better)' },
    best_validate_metrics: { type: 'object', additionalProperties: true },
    best_rule_summary: { type: 'string' },
    families_tried_this_iteration: { type: 'array', items: { type: 'string' } },
    data_added_this_iteration: { type: 'array', items: { type: 'string' } },
    key_findings: { type: 'array', items: { type: 'string' } },
    minutes_worked: { type: 'number' },
    polyrea_bugs: { type: 'array', items: { type: 'string' } },
  },
  required: ['status', 'primary_metric', 'best_validate_score', 'best_rule_summary', 'families_tried_this_iteration', 'key_findings', 'minutes_worked'],
}

const EXAM = {
  type: 'object',
  properties: {
    holdout_sample: { type: 'string' },
    rule_summary: { type: 'string' },
    leakage_check: { type: 'object', properties: { passed: { type: 'boolean' }, details: { type: 'string' } }, required: ['passed', 'details'] },
    metrics: { type: 'object', additionalProperties: true, description: 'selection_auc, selection_p, recall, lift, presence_auc, side_accuracy, side_baseline, price_within_tick, pnl_correlation, rule_return_strict, rule_return_p, wallet_return, and any others' },
    target_met: { type: 'boolean' },
    criteria: { type: 'object', properties: { match: { type: 'string', enum: ['pass', 'partial', 'fail'] }, backtest: { type: 'string', enum: ['pass', 'fail'] }, replicable: { type: 'string', enum: ['pass', 'fail'] } }, required: ['match', 'backtest', 'replicable'] },
    explanation: { type: 'string' },
    mechanical_fixes_made: { type: 'string' },
    evidence_files: { type: 'array', items: { type: 'string' } },
  },
  required: ['holdout_sample', 'rule_summary', 'leakage_check', 'metrics', 'target_met', 'criteria', 'explanation', 'evidence_files'],
}

function iterPrompt(s, i, history) {
  const start = i === 1 && !s.resume
    ? 'This is iteration 1: create your workspace, set up NOTES.md and state.json, pre-register your primary metric (higher is better, comparable across iterations) and your BUILD/VALIDATE split, and begin by expanding the data well beyond what the earlier studies used.'
    : `Continue your predecessor's work: read NOTES.md and state.json in your workspace before anything else (earlier iterations, including any from a previous run, are recorded there). Iterations in this run so far: ${JSON.stringify(history)}. Do not repeat hypotheses already rejected; push into directions not yet tried, and deepen the ones that are working.`
  return `You are the deep reverse-engineering agent for strategy "${s.key}" (${s.title}). Iteration ${i} of at most ${MAX_ITERS} in this run.

Read research/reverse_engineering/BRIEF.md first and follow it exactly (holdout discipline, no future data, data sources, metrics, high-accuracy target, wall, engineering rules, files to maintain). Workspace: research/reverse_engineering/${s.key}/ and .cache/re/${s.key}/. Repo root: your current working directory (run every command from it).

Dossier:
${s.dossier}

${start}

Reason deeply and think like an expert reverse engineer: form explicit hypotheses about the mechanism, design measurements that discriminate between them, and let the data overturn your assumptions. Work for about 60 minutes of wall-clock time: run \`date -u +%s\` now and check it regularly; at about 55-60 minutes stop starting new analyses, update NOTES.md, state.json, FINAL_RULE.md and code/final_rule.py (the best frozen rule so far, with evaluate(start_ts, end_ts)), and return.

Return status "target_reached" only if the brief's high-accuracy target holds on VALIDATE; "wall" only with the evidence the brief asks for (information wall) or if you are certain no further direction is worth trying; otherwise "continue".`
}

function examPrompt(s, hist) {
  return `You are the independent examiner for strategy "${s.key}" (${s.title}). The reverse engineer finished after ${hist.length} iteration(s) with final status "${hist.length ? hist[hist.length - 1].status : 'none'}". Do not trust their numbers; reproduce everything yourself.

Read research/reverse_engineering/BRIEF.md (rules, holdout, metrics, target) and the workspace research/reverse_engineering/${s.key}/ (NOTES.md, state.json, FINAL_RULE.md, code/). Repo root: your current working directory (run every command from it).

1. Leakage audit: read the code. Confirm every parameter of the final rule is a constant fixed before the holdout, that development code never read data at or after H=1792713600 (2026-10-23 00:00 UTC), and that decision features are point-in-time (no outcomes, no post-hoc metadata, block-time slack for maker fills, ESPN delay >= 5 s). Run a truncation test on a sample: remove or corrupt all data after each decision time and confirm identical decisions.
2. Run code/final_rule.py evaluate(H, latest available) on the holdout (or a fixed, stated sample of holdout blocks, games or events large enough for the metrics). If it fails for mechanical reasons (paths, imports) fix only those and report what you changed; never change rule parameters.
3. Independently recompute the key metrics with your own code where feasible: selection AUC against the appropriate null with recall and lift, behaviour-cloning presence AUC without own-state features, side accuracy against the best market-only baseline, price within one tick, per-market PnL correlation with the wallet, the rule's return under strict fills with latency >= 2 s (and match_slack=2 for makers) with its p-value, and the wallet's own return on the same markets.
4. Judge: is the brief's high-accuracy target met on the holdout? Criterion (6) match: pass / partial / fail (docs/methodology.md rules plus the brief's target). Criterion (7) backtest: is the rule significantly profitable on the holdout (p < 0.05) under strict fills at >= 2 s? Criterion (8) replicable: could a normal user on a normal connection run it profitably (no private feed, latency >= 2 s, capacity toward $50k/month)?

Write EXAM.md and results/exam.json in the workspace. Follow the brief's engineering rules (memory, no git, write only in the workspace and .cache/re/${s.key}/).`
}

const results = await pipeline(
  STRATS,
  async (s) => {
    const history = []
    let minutes = 0
    for (let i = 1; i <= MAX_ITERS; i++) {
      const r = await agent(iterPrompt(s, i, history), { label: `re:${s.key}:${i}`, phase: 'Reverse engineer', schema: ITER, effort: 'max' })
      if (!r) { history.push({ n: i, status: 'agent_failed' }); break }
      minutes += r.minutes_worked || 60
      history.push({ n: i, status: r.status, primary_metric: r.primary_metric, best_validate_score: r.best_validate_score, families: r.families_tried_this_iteration, rule: r.best_rule_summary, findings: r.key_findings, minutes: r.minutes_worked })
      log(`${s.key} iteration ${i}: ${r.status}, best ${r.primary_metric}=${r.best_validate_score}`)
      if (r.status !== 'continue') break
      if (minutes >= MAX_MINUTES) { history[history.length - 1].status = 'wall'; history[history.length - 1].wall_reason = 'time budget'; break }
      if (i >= 3) {
        const prev = history[i - 3].best_validate_score
        if (typeof prev === 'number' && r.best_validate_score - prev < 0.01) {
          history[history.length - 1].status = 'wall'
          history[history.length - 1].wall_reason = 'diminishing returns: < 0.01 improvement over two iterations'
          break
        }
      }
    }
    return { key: s.key, history, minutes }
  },
  async (st, s) => {
    const exam = await agent(examPrompt(s, st.history), { label: `exam:${s.key}`, phase: 'Examine', schema: EXAM, effort: 'xhigh' })
    return { ...st, exam }
  },
)
return results
