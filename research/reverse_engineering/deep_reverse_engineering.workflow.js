export const meta = {
  name: 'deep-reverse-engineering',
  description: 'One expert reverse-engineering agent per strategy, iterating until high accuracy or a wall; independent holdout examiner; skeptics try to refute every pass; progress committed to GitHub',
  phases: [
    { title: 'Reverse engineer', detail: 'iterations of ~60 min per strategy, checkpointed in a lab notebook' },
    { title: 'Examine', detail: 'independent leakage audit, frozen evaluation on the holdout, deploy-now judgment' },
    { title: 'Refute', detail: 'three skeptics (leakage, statistics, deployability) per criterion the examiner passed' },
    { title: 'Commit', detail: 'serialized snapshots: rebuild the dashboard, commit, push the research branch' },
  ],
}

// args (research/reverse_engineering/strategies.json):
// { strategies: [{ key, title, dossier, wallets, resume, prior_iters, prior_minutes }], order?, concurrency?,
//   max_iters?, max_minutes?, branch? }
// resume: true continues from an existing workspace (NOTES.md, state.json) instead of starting fresh.
// prior_iters / prior_minutes: work already done in an earlier run; they count toward the budget.
const MAX_ITERS = (args && args.max_iters) || 5
const MAX_MINUTES = (args && args.max_minutes) || 300
const CONCURRENCY = (args && args.concurrency) || 2
const BRANCH = (args && args.branch) || 'deep-re-local'
const ORDER = (args && args.order) || args.strategies.map((s) => s.key)
const STRATS = ORDER.map((k) => args.strategies.find((s) => s.key === k)).filter(Boolean)
for (const s of args.strategies) if (!ORDER.includes(s.key)) STRATS.push(s)

const ITER = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['continue', 'target_reached', 'wall'] },
    wall_reason: { type: 'string' },
    primary_metric: { type: 'string', description: 'pre-registered primary metric name, fixed across iterations' },
    best_validate_score: { type: 'number', description: 'best VALIDATE value of the primary metric so far (higher is better)' },
    best_validate_metrics: { type: 'object', additionalProperties: true },
    co_occurrence_baseline: { type: 'number', description: 'the same metric for the market-activity-only baseline' },
    best_rule_summary: { type: 'string' },
    families_tried_this_iteration: { type: 'array', items: { type: 'string' } },
    data_added_this_iteration: { type: 'array', items: { type: 'string' } },
    key_findings: { type: 'array', items: { type: 'string' } },
    minutes_worked: { type: 'number' },
    polyrea_bugs: { type: 'array', items: { type: 'string' } },
  },
  required: ['status', 'primary_metric', 'best_validate_score', 'best_rule_summary', 'families_tried_this_iteration', 'key_findings', 'minutes_worked'],
}

const VERDICT = { type: 'string', enum: ['pass', 'partial', 'fail'] }
const EXAM = {
  type: 'object',
  properties: {
    holdout_sample: { type: 'string' },
    rule_summary: { type: 'string' },
    leakage_check: { type: 'object', properties: { passed: { type: 'boolean' }, details: { type: 'string' } }, required: ['passed', 'details'] },
    metrics: { type: 'object', additionalProperties: true, description: 'selection_auc, selection_p, recall, lift, presence_auc, co_occurrence_baseline, side_accuracy, side_baseline, price_within_tick, pnl_correlation, rule_return_strict, rule_return_p, wallet_return, and any others' },
    target_met: { type: 'boolean' },
    criteria: {
      type: 'object',
      properties: { match: VERDICT, backtest: VERDICT, replicable: VERDICT, persists: VERDICT },
      required: ['match', 'backtest', 'replicable', 'persists'],
    },
    criteria_details: { type: 'object', additionalProperties: { type: 'string' }, description: 'one or two sentences of evidence per criterion' },
    why_it_works: { type: 'string', description: 'the economic mechanism: who loses to it and what it is paid for' },
    deploy_now: {
      type: 'object',
      properties: { supported: { type: 'boolean' }, evidence: { type: 'string' } },
      required: ['supported', 'evidence'],
      description: 'is "this strategy is statistically significant to continue working if I deployed it now" supported for a normal user?',
    },
    explanation: { type: 'string' },
    mechanical_fixes_made: { type: 'string' },
    evidence_files: { type: 'array', items: { type: 'string' } },
  },
  required: ['holdout_sample', 'rule_summary', 'leakage_check', 'metrics', 'target_met', 'criteria', 'why_it_works', 'deploy_now', 'explanation', 'evidence_files'],
}

const REFUTE = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    severity: { type: 'string', enum: ['fatal', 'material', 'minor', 'none'] },
    reasoning: { type: 'string' },
    reproduced_numbers: { type: 'object', additionalProperties: true },
    evidence_files: { type: 'array', items: { type: 'string' } },
  },
  required: ['refuted', 'severity', 'reasoning'],
}

const LENSES = {
  leakage: 'LEAKAGE AND LOOK-AHEAD: any feature, parameter, threshold, universe filter or label that uses information from at or after the decision time or from the holdout; the wallet\'s own prints leaking into features; block-time slack ignored for maker fills; post-hoc market metadata; a co-occurrence baseline that explains the result.',
  statistics: 'STATISTICS: is the effect real and large enough? Recompute the key number yourself; check sample size, dependence between observations (windows, games, blocks), the right null, multiplicity over hypotheses and families tried, selection of the reported metric or sample, sensitivity to the threshold and to dropping the best days or markets.',
  deployability: 'DEPLOYABILITY FOR A NORMAL USER: latency at least 1-2 s for decision plus order, queue position as a newcomer, fees and the 0% rebate tier a newcomer holds, capacity toward $50k/month, capital needed, private or faster data feeds, and whether the conditions (Polymarket policy, market listings, competition, the wallet\'s own recent PnL trend) still hold in the latest data.',
}
const CRIT_LENSES = {
  match: ['leakage', 'statistics', 'deployability'],
  backtest: ['leakage', 'statistics', 'deployability'],
  replicable: ['deployability', 'statistics', 'leakage'],
  persists: ['deployability', 'statistics', 'leakage'],
}

function iterPrompt(s, i, history) {
  const fresh = i === 1 && !s.resume
  const start = fresh
    ? 'This is iteration 1: create your workspace, set up NOTES.md and state.json, pre-register your primary metric (higher is better, comparable across iterations) and your BUILD/VALIDATE split, and begin by expanding the data well beyond what the earlier studies used.'
    : `Continue your predecessor's work: read NOTES.md and state.json in your workspace before anything else (earlier iterations, including the ones from the earlier cloud run, are recorded there). Iterations in this run so far: ${JSON.stringify(history)}. Do not repeat hypotheses already rejected; push into directions not yet tried, and deepen the ones that are working.`
  const local = (history.filter((h) => h.local).length === 0)
    ? '\n\nThis is the first iteration on the local machine (see "Local run" in the brief): the earlier intermediates in .cache/re/ are gone. Check resources first (tools/resources.py), re-fetch only what your next analyses need, and fix any Linux paths in code you reuse.'
    : ''
  return `You are the deep reverse-engineering agent for strategy "${s.key}" (${s.title}). Iteration ${i} of at most ${MAX_ITERS} (counting the earlier run's).

Read research/reverse_engineering/BRIEF.md first and follow it exactly (holdout discipline, no future data, data sources, metrics, co-occurrence baseline, high-accuracy target, wall, engineering rules for this shared laptop, files to maintain). Workspace: research/reverse_engineering/${s.key}/ and .cache/re/${s.key}/. Repo root: your current working directory (run every command from it).

Dossier:
${s.dossier}

${start}${local}

Reason deeply and think like an expert reverse engineer: form explicit hypotheses about the mechanism, design measurements that discriminate between them, and let the data overturn your assumptions. If the data you have is not enough to tell hypotheses apart, get more (longer history, every market rather than a sample, on-chain order reconstruction, other reference feeds). Work for about 60 minutes of wall-clock time: run \`date -u +%s\` now and check it regularly; at about 55-60 minutes stop starting new analyses, update NOTES.md, state.json (with status and this iteration's entry), FINAL_RULE.md (including "Why it works" and "Can a normal user deploy it now") and code/final_rule.py (the best frozen rule so far, with evaluate(start_ts, end_ts)), and return.

Return status "target_reached" only if the brief's high-accuracy target holds on VALIDATE; "wall" only with the evidence the brief asks for (information wall) or if you are certain no further direction is worth trying; otherwise "continue".`
}

function examPrompt(s, hist) {
  const last = hist.length ? hist[hist.length - 1] : null
  return `You are the independent examiner for strategy "${s.key}" (${s.title}); wallets ${JSON.stringify(s.wallets || [])}. The reverse engineer finished after ${hist.length} iteration(s) in this run (plus ${s.prior_iters || 0} earlier) with final status "${last ? last.status : 'none'}"${last && last.wall_reason ? ` (${last.wall_reason})` : ''}. Do not trust their numbers; reproduce everything yourself.

Read research/reverse_engineering/BRIEF.md (rules, holdout, metrics, co-occurrence baseline, target, engineering rules for this shared laptop) and the workspace research/reverse_engineering/${s.key}/ (NOTES.md, state.json, FINAL_RULE.md, code/). Repo root: your current working directory (run every command from it). Also read docs/methodology.md (criteria) and research/verdicts/<wallet>.json for the wallets.

1. Leakage audit: read the code. Confirm every parameter of the final rule is a constant fixed before the holdout, that development code never read data at or after H=1792713600 (2026-10-23 00:00 UTC), and that decision features are point-in-time (no outcomes, no post-hoc metadata, the wallet's own prints excluded from features, block-time slack for maker fills, ESPN delay >= 5 s). Run a truncation test on a sample: remove or corrupt all data after each decision time and confirm identical decisions.
2. Run code/final_rule.py evaluate(H, latest available) on the holdout (or a fixed, stated sample of holdout blocks, games or events large enough for the metrics). If it fails for mechanical reasons (paths, imports, Windows) fix only those and report what you changed; never change rule parameters.
3. Independently recompute the key metrics with your own code where feasible: selection AUC against the appropriate null with recall and lift, behaviour-cloning presence AUC without own-state features AND the co-occurrence (market-activity-only) baseline, side accuracy against the best market-only baseline, price within one tick, per-market PnL correlation with the wallet, the rule's return under strict fills with latency >= 2 s (and match_slack=2 for makers) with its p-value, and the wallet's own return on the same markets.
4. Judge each criterion:
   - (6) match: pass / partial / fail (docs/methodology.md rules plus the brief's high-accuracy target; a presence AUC that the co-occurrence baseline explains is not a decoded rule).
   - (7) backtest: is the rule significantly profitable on the holdout (p < 0.05) under strict fills at >= 2 s, without rebates a newcomer would not get?
   - (8) replicable: could a normal user on a normal connection and computer run it profitably (no private or faster feed, latency >= 2 s, newcomer queue position and 0% rebate tier, capacity toward $50k/month)?
   - (9) persists: is "this strategy is statistically significant to continue working if I deployed it now" supported? Use the holdout's forward days (data after 2026-10-30 that did not exist when the study was designed), the rule's holdout PnL, the wallet's own recent PnL (polyrea.tools.assess_persistence(wallet, as_of=<latest full day>) with one-off bonuses removed), and whether the conditions the mechanism relies on (policy, fees and rebates, listings, competition) still hold. Pass only with statistical evidence, not plausibility.
5. Explain why the strategy works (the economic mechanism: who loses to it, what it is paid for) and state whether the deploy-now statement is supported, with the evidence.

Write EXAM.md and results/exam.json in the workspace. Follow the brief's engineering rules (memory and disk gates, no git, write only in the workspace and .cache/re/${s.key}/).`
}

function refutePrompt(s, exam, crit, lens) {
  return `You are an adversarial skeptic for strategy "${s.key}" (${s.title}). An independent examiner judged criterion "${crit}" as PASS. Your job is to REFUTE that pass if it does not hold. Default to refuted=true if, after checking, you are not convinced the pass is sound.

Your lens: ${LENSES[lens]}

Examiner's judgment: ${JSON.stringify({ criteria: exam.criteria, criteria_details: exam.criteria_details, metrics: exam.metrics, target_met: exam.target_met, holdout_sample: exam.holdout_sample, rule_summary: exam.rule_summary, deploy_now: exam.deploy_now })}

Read research/reverse_engineering/BRIEF.md, docs/methodology.md and the workspace research/reverse_engineering/${s.key}/ (FINAL_RULE.md, EXAM.md, results/exam.json, code/). Repo root: your current working directory. Check the claim through your lens with your own code where feasible (recompute rather than trust; keep jobs small: run tools/resources.py --wait-mem 1200 before anything heavy). Write your finding to research/reverse_engineering/${s.key}/results/refute_${crit}_${lens}.json and nowhere else (no git). Severity: fatal = the pass is wrong; material = the pass rests on a flawed number but might survive a fix; minor = cosmetic.`
}

function commitPrompt(s, msg, adjudication) {
  const ws = `research/reverse_engineering/${s.key}`
  const step1 = adjudication
    ? `1. Use the Write tool to create ${ws}/results/adjudication.json with exactly this content (create the results folder if needed):\n${JSON.stringify(adjudication, null, 1)}\n`
    : '1. (nothing to write)\n'
  return `You are a git committer for a research repository. Work from the repository root (your current working directory) in the Bash tool (Git Bash). Do not edit any file other than the one in step 1.

${step1}2. Run: .venv/Scripts/python.exe -m polyrea.report   (rebuilds research/ledger.json, research/README.md, dashboard/index.html and research/wallets/*/REPORT.md). If it fails, report the error and continue without it.
3. Run: find ${ws} -type f -size +5M   — files listed there must NOT be committed.
4. Run: git add -- ${ws} research/reverse_engineering/BRIEF.md research/README.md research/ledger.json dashboard/index.html research/wallets   then for every file from step 3 run git reset -q -- <file>. Do not add anything else (never git add -A or git add .).
5. If git diff --cached --quiet reports changes, commit: git commit -m "${msg}" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
6. git push origin ${BRANCH}. If the push is rejected, run git pull --rebase origin ${BRANCH} and push once more. Never force-push, never switch branches, never touch other branches.
Return one line: the commit hash (or "nothing to commit") and whether the push succeeded.`
}

// Commits run one at a time, in the order requested, so git never races itself.
let commitChain = Promise.resolve()
function commit(s, msg, adjudication) {
  commitChain = commitChain
    .then(() => agent(commitPrompt(s, msg, adjudication), { label: `commit:${s.key}`, phase: 'Commit', model: 'haiku', effort: 'low' }))
    .catch(() => null)
  return commitChain
}

async function reverseEngineer(s) {
  const history = []
  let minutes = s.prior_minutes || 0
  const priorScores = s.prior_scores || []
  for (let i = (s.prior_iters || 0) + 1; i <= MAX_ITERS; i++) {
    if (minutes >= MAX_MINUTES) break
    let r = await agent(iterPrompt(s, i, history), { label: `re:${s.key}:${i}`, phase: 'Reverse engineer', schema: ITER, effort: 'max' })
    if (!r) r = await agent(iterPrompt(s, i, history), { label: `re:${s.key}:${i}:retry`, phase: 'Reverse engineer', schema: ITER, effort: 'max' })
    if (!r) { history.push({ n: i, local: true, status: 'agent_failed' }); break }
    minutes += r.minutes_worked || 60
    history.push({ n: i, local: true, status: r.status, wall_reason: r.wall_reason, primary_metric: r.primary_metric, best_validate_score: r.best_validate_score, co_occurrence_baseline: r.co_occurrence_baseline, families: r.families_tried_this_iteration, rule: r.best_rule_summary, findings: r.key_findings, minutes: r.minutes_worked, polyrea_bugs: r.polyrea_bugs })
    log(`${s.key} iteration ${i}: ${r.status}, best ${r.primary_metric}=${r.best_validate_score}${r.co_occurrence_baseline != null ? ` (baseline ${r.co_occurrence_baseline})` : ''}, ${Math.round(minutes)} min total`)
    commit(s, `${s.key}: deep reverse engineering iteration ${i} (${r.status}, best ${r.best_validate_score})`)
    if (r.status !== 'continue') break
    if (minutes >= MAX_MINUTES) { history[history.length - 1].status = 'wall'; history[history.length - 1].wall_reason = 'time budget'; break }
    if (i >= 3) {
      const scores = priorScores.concat(history.map((h) => h.best_validate_score))
      const prev = scores[scores.length - 3]
      // The brief's wall: < 0.01 gain over two iterations although each tried at least three new families
      // (iterations from the earlier run are taken as having done so).
      const tried = history.slice(-2).every((h) => (h.families || []).length >= 3)
      if (typeof prev === 'number' && r.best_validate_score - prev < 0.01 && tried) {
        history[history.length - 1].status = 'wall'
        history[history.length - 1].wall_reason = 'diminishing returns: < 0.01 improvement over two iterations'
        break
      }
    }
  }
  return { key: s.key, history, minutes }
}

async function examineAndRefute(s, st) {
  const exam = await agent(examPrompt(s, st.history), { label: `exam:${s.key}`, phase: 'Examine', schema: EXAM, effort: 'xhigh' })
  if (!exam) {
    commit(s, `${s.key}: examination failed to return`)
    return { ...st, exam: null }
  }
  const passed = Object.entries(exam.criteria || {}).filter(([, v]) => v === 'pass').map(([k]) => k)
  log(`${s.key} exam: target ${exam.target_met ? 'met' : 'not met'}, criteria ${JSON.stringify(exam.criteria)}${passed.length ? `; refuting ${passed.join(', ')}` : ''}`)
  const refutations = {}
  const final = { ...exam.criteria }
  // Skeptics run one at a time (each may run Python jobs on the shared laptop).
  for (const crit of passed) {
    const votes = []
    for (const lens of CRIT_LENSES[crit]) {
      votes.push(await agent(refutePrompt(s, exam, crit, lens), { label: `refute:${s.key}:${crit}:${lens}`, phase: 'Refute', schema: REFUTE, effort: 'high' }))
    }
    const vs = votes.map((v, j) => v && { ...v, lens: CRIT_LENSES[crit][j] }).filter(Boolean)
    const against = vs.filter((v) => v.refuted && v.severity !== 'minor').length
    refutations[crit] = vs.map((v) => ({ lens: v.lens, refuted: v.refuted, severity: v.severity, reasoning: v.reasoning }))
    // The pass survives only if a majority of the skeptics who returned could not refute it.
    if (vs.length === 0 || against * 2 >= vs.length) final[crit] = crit === 'match' ? 'partial' : 'fail'
  }
  const adjudication = {
    examiner_criteria: exam.criteria,
    criteria: final,
    target_met: exam.target_met,
    deploy_now_supported: !!(exam.deploy_now && exam.deploy_now.supported) && final.persists === 'pass' && final.backtest === 'pass' && final.replicable === 'pass',
    refutations,
  }
  commit(s, `${s.key}: holdout examination and adjudication (${Object.entries(final).map(([k, v]) => `${k} ${v}`).join(', ')})`, adjudication)
  return { ...st, exam, adjudication }
}

async function runStrategy(s) {
  const st = await reverseEngineer(s)
  return examineAndRefute(s, st)
}

// At most CONCURRENCY strategies are worked on at once (the machine is a shared laptop), in priority order.
const results = {}
let next = 0
async function worker() {
  while (next < STRATS.length) {
    const s = STRATS[next++]
    try {
      results[s.key] = await runStrategy(s)
    } catch (e) {
      results[s.key] = { key: s.key, error: String(e) }
      log(`${s.key} failed: ${String(e)}`)
    }
  }
}
log(`${STRATS.length} strategies, ${CONCURRENCY} at a time: ${STRATS.map((s) => s.key).join(', ')}`)
await Promise.all(Array.from({ length: Math.min(CONCURRENCY, STRATS.length) }, () => worker()))
await commitChain
return STRATS.map((s) => results[s.key])
