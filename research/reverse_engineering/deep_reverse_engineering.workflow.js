export const meta = {
  name: 'deep-reverse-engineering',
  description: 'One expert reverse engineer per strategy that keeps going until the strategy is decoded: fresh-eyes panels after every iteration, walls only after an independent audit, repeated exams on pre-registered sealed lots with skeptics, progress committed to GitHub',
  phases: [
    { title: 'Reverse engineer', detail: 'iterations of about 100 minutes per strategy, checkpointed in a lab notebook' },
    { title: 'Panel', detail: 'three fresh-eyes experts propose untried directions after every iteration' },
    { title: 'Wall audit', detail: 'three auditors try to name untried directions before a wall stands' },
    { title: 'Examine', detail: 'leakage audit and frozen evaluation on the next sealed lot; a failed exam feeds its diagnosis back' },
    { title: 'Refute', detail: 'three skeptics per criterion the examiner passed' },
    { title: 'Commit', detail: 'serialized snapshots: progress file, dashboard rebuild, commit, push' },
  ],
}

// args (research/reverse_engineering/strategies.json):
// { strategies: [{ key, title, dossier, wallets, sealed_min_hours, prior_iters, prior_minutes, prior_scores,
//     released?, future_examined_until?, prior_exams?: [{ round, lot, criteria }], prior_diagnosis?, interrupted? }],
//   order?, concurrency?, max_minutes?, min_wall_minutes?, iter_minutes?, max_exams?, branch? }
// The sealed calendar mirrors research/reverse_engineering/tools/sealed.py: lots h1 and h2 (alternating days of
// [H, T0)), then 6-hour blocks from T0 where block j of day d is sealed iff d + j is odd.
const H = 1792713600
const T0 = 1793404800
const DAY = 86400
const BLOCK = 6 * 3600
const LOT_DAYS = { h1: [0, 2, 4, 6], h2: [1, 3, 5, 7] }
const MAX_MINUTES = args.max_minutes || 1200
const MIN_WALL_MINUTES = args.min_wall_minutes || 600
const ITER_MINUTES = args.iter_minutes || 100
const MAX_EXAMS = args.max_exams || 4
const MAX_DEFERRALS = 2
const MAX_FAILURES = 4
const CONCURRENCY = args.concurrency || 3
const BRANCH = args.branch || 'deep-re-local'
// The runtime stops a workflow at 1000 agents. Panels stop first, then new iterations, so exams and commits still
// run; each strategy also has its own quota so one cannot starve the strategies queued after it.
const PANEL_CAP = 860
const ITER_CAP = 900
const STRAT_QUOTA = 125
const ORDER = args.order || args.strategies.map((s) => s.key)
const STRATS = ORDER.map((k) => args.strategies.find((s) => s.key === k)).filter(Boolean)
for (const s of args.strategies) if (!ORDER.includes(s.key)) STRATS.push(s)
const CRITERIA = ['match', 'backtest', 'replicable', 'persists']
const COMPONENTS = ['selection', 'timing', 'side', 'price', 'size', 'exit']

let spawned = 0
const spawnedBy = {}
function run(key, prompt, opts) {
  spawned += 1
  spawnedBy[key] = (spawnedBy[key] || 0) + 1
  return agent(prompt, opts)
}
const utc = (ts) => new Date(ts * 1000).toISOString().replace('.000Z', 'Z')
const clip = (t, n) => (typeof t === 'string' && t.length > n ? `${t.slice(0, n)}...` : t)
const clone = (x) => JSON.parse(JSON.stringify(x))

function futureSealed(ts) {
  const k = Math.floor((ts - T0) / BLOCK)
  return (Math.floor(k / 4) + (k % 4)) % 2 === 1
}
// The data the next exam would use, given what is released and the current time.
function nextLot(st, now) {
  for (const lot of ['h1', 'h2']) {
    if (!st.released.includes(lot)) return { lot, intervals: LOT_DAYS[lot].map((d) => [H + d * DAY, H + (d + 1) * DAY]), hours: 96 }
  }
  const iv = []
  let t = T0 + Math.floor((Math.max(st.futureUntil, T0) - T0) / BLOCK) * BLOCK
  while (now && t + BLOCK <= now) {
    if (futureSealed(t)) iv.push([t, t + BLOCK])
    t += BLOCK
  }
  return { lot: `f${st.futureRound + 1}`, intervals: iv, hours: iv.length * 6, until: iv.length ? iv[iv.length - 1][1] : null }
}
const fmtLot = (l) => `${l.lot}: ${l.intervals.map(([a, b]) => `[${utc(a)}, ${utc(b)})`).join(', ') || 'no sealed blocks yet'}`

// Target conditions the reverse engineer's own VALIDATE numbers must meet before sealed data is spent on an exam.
function targetGaps(m) {
  if (!m) return ['no target_metrics reported']
  const n = (k) => (typeof m[k] === 'number' ? m[k] : null)
  const gaps = []
  const pres = n('presence_auc')
  const sel = n('selection_auc')
  const presOk = pres != null && pres >= 0.85 && n('presence_baseline') != null && pres - n('presence_baseline') >= 0.05
  const selOk = sel != null && sel >= 0.8 && (n('selection_recall') || 0) >= 0.5 && (n('selection_lift') || 0) >= 3 && n('selection_baseline') != null && sel - n('selection_baseline') >= 0.05
  if (!presOk && !selOk) gaps.push(`presence AUC >= 0.85 or selection AUC >= 0.80 (recall >= 50%, lift >= 3), each at least 0.05 above its activity-only baseline (reported: presence ${pres} vs ${n('presence_baseline')}, selection ${sel} vs ${n('selection_baseline')})`)
  if (n('side_accuracy') != null && n('side_accuracy') < 0.8) gaps.push(`side accuracy >= 0.80 (reported ${n('side_accuracy')})`)
  if (n('price_within_tick') != null && n('price_within_tick') < 0.8) gaps.push(`price within one tick >= 0.80 (reported ${n('price_within_tick')})`)
  if (!(n('pnl_corr_pearson') >= 0.5 && n('pnl_corr_spearman') >= 0.5)) gaps.push(`per-market PnL correlation >= 0.5, Pearson and Spearman (reported ${n('pnl_corr_pearson')} / ${n('pnl_corr_spearman')})`)
  if (!(n('coverage_fills') >= 0.8 && n('coverage_abs_pnl') >= 0.8)) gaps.push(`coverage >= 80% of fills and of absolute PnL (reported ${n('coverage_fills')} / ${n('coverage_abs_pnl')})`)
  return gaps
}
// Progress toward the target in [0, 1], used only to decide when to force a pivot.
function progressScore(m) {
  if (!m) return null
  const c = (x) => Math.max(0, Math.min(1, x))
  const n = (k) => (typeof m[k] === 'number' ? m[k] : null)
  const terms = []
  const paths = []
  if (n('presence_auc') != null) paths.push(0.5 * c(n('presence_auc') / 0.85) + 0.5 * c((n('presence_auc') - (n('presence_baseline') ?? n('presence_auc'))) / 0.05))
  if (n('selection_auc') != null) paths.push(0.5 * c(n('selection_auc') / 0.8) + 0.5 * c((n('selection_auc') - (n('selection_baseline') ?? n('selection_auc'))) / 0.05))
  if (paths.length) terms.push(Math.max(...paths))
  if (n('side_accuracy') != null) terms.push(c(n('side_accuracy') / 0.8))
  if (n('price_within_tick') != null) terms.push(c(n('price_within_tick') / 0.8))
  if (n('pnl_corr_pearson') != null || n('pnl_corr_spearman') != null) terms.push(c(Math.min(n('pnl_corr_pearson') ?? 0, n('pnl_corr_spearman') ?? 0) / 0.5))
  if (n('coverage_fills') != null || n('coverage_abs_pnl') != null) terms.push(c(Math.min(n('coverage_fills') ?? 0, n('coverage_abs_pnl') ?? 0) / 0.8))
  return terms.length ? terms.reduce((a, b) => a + b, 0) / terms.length : null
}

const NUM = { type: ['number', 'null'] }
const TARGET_KEYS = ['presence_auc', 'selection_auc', 'selection_recall', 'selection_lift', 'presence_baseline', 'selection_baseline', 'side_accuracy', 'side_baseline', 'price_within_tick', 'pnl_corr_pearson', 'pnl_corr_spearman', 'coverage_fills', 'coverage_abs_pnl']
const COMPONENT = {
  type: 'object',
  properties: { confidence: { type: 'number', description: '0-1' }, description: { type: 'string' }, tag: { type: 'string', enum: ['exam-verified', 'VALIDATE-only', 'hypothesis'] } },
  required: ['confidence', 'description'],
}
const ITER = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['continue', 'target_reached', 'wall'] },
    wall_reason: { type: 'string' },
    now_ts: { type: 'number', description: 'output of `date -u +%s` just before returning' },
    paradigm: { type: 'string', description: 'a short name for the approach this iteration developed' },
    primary_metric: { type: 'string' },
    best_validate_score: { type: 'number', description: 'VALIDATE value of the primary metric for the current best rule' },
    target_metrics: {
      type: 'object',
      properties: Object.fromEntries(TARGET_KEYS.map((k) => [k, NUM])),
      required: TARGET_KEYS,
      description: 'the current best rule on VALIDATE, named as in the brief (null where not applicable)',
    },
    best_validate_metrics: { type: 'object', additionalProperties: true },
    strategy_statement: { type: 'string', description: 'plain-language description of what the bot does, with each component tagged' },
    components: { type: 'object', properties: Object.fromEntries(COMPONENTS.map((k) => [k, COMPONENT])), required: COMPONENTS },
    best_rule_summary: { type: 'string' },
    families_tried_this_iteration: { type: 'array', items: { type: 'string' } },
    proposals_tested: { type: 'array', items: { type: 'string' }, description: 'panel or audit proposals (X items) tested this iteration, each with its verdict' },
    data_added_this_iteration: { type: 'array', items: { type: 'string' } },
    catalog_open: { type: 'array', items: { type: 'string' }, description: 'catalog ids still open, including X items' },
    live_lab: {
      type: 'array',
      items: { type: 'object', properties: { start: { type: 'number' }, end: { type: 'number' }, what: { type: 'string' } }, required: ['start', 'end'] },
      description: 'your own extra recorders, if any (the shared recorder is not listed here)',
    },
    key_findings: { type: 'array', items: { type: 'string' } },
    next_steps: { type: 'array', items: { type: 'string' } },
    minutes_worked: { type: 'number', description: 'wall-clock minutes of THIS iteration only' },
    polyrea_bugs: { type: 'array', items: { type: 'string' } },
  },
  required: ['status', 'now_ts', 'paradigm', 'primary_metric', 'best_validate_score', 'target_metrics', 'strategy_statement', 'components', 'best_rule_summary', 'families_tried_this_iteration', 'catalog_open', 'key_findings', 'next_steps', 'minutes_worked'],
}

const PANEL = {
  type: 'object',
  properties: {
    critique: { type: 'string', description: 'what the investigation is missing or getting wrong, in a few sentences' },
    proposals: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          hypothesis: { type: 'string' },
          why_it_fits: { type: 'string', description: 'what in the evidence points to it' },
          test: { type: 'string', description: 'a concrete discriminating test runnable on this laptop' },
          data_needed: { type: 'string' },
          signature_if_true: { type: 'string' },
          catalog_id: { type: 'string' },
          priority: { type: 'number', description: '1 = most likely to close the gap' },
        },
        required: ['title', 'hypothesis', 'test', 'priority'],
      },
    },
  },
  required: ['critique', 'proposals'],
}

const AUDIT = {
  type: 'object',
  properties: {
    accept: { type: 'boolean' },
    reasoning: { type: 'string' },
    catalog_gaps: { type: 'array', items: { type: 'string' }, description: 'catalog ids not genuinely closed' },
    untried_directions: {
      type: 'array',
      items: {
        type: 'object',
        properties: { title: { type: 'string' }, why_promising: { type: 'string' }, test: { type: 'string' }, data_needed: { type: 'string' }, catalog_id: { type: 'string' } },
        required: ['title', 'why_promising', 'test'],
      },
    },
  },
  required: ['accept', 'reasoning', 'untried_directions'],
}

const VERDICT = { type: 'string', enum: ['pass', 'partial', 'fail'] }
const COMP_VERDICT = { type: 'string', enum: ['pass', 'partial', 'fail', 'not_applicable'] }
const EXAM = {
  type: 'object',
  properties: {
    fresh_data_sufficient: { type: 'boolean' },
    holdout_sample: { type: 'string', description: 'the lot, its units and what was left out' },
    now_ts: { type: 'number' },
    rule_summary: { type: 'string' },
    leakage_check: { type: 'object', properties: { passed: { type: 'boolean' }, details: { type: 'string' } }, required: ['passed', 'details'] },
    metrics: { type: 'object', additionalProperties: true, description: 'every target metric with its baseline, interval and p-value, plus backtest numbers' },
    per_wallet: { type: 'object', additionalProperties: true },
    target_conditions: { type: 'object', additionalProperties: { type: 'string' }, description: 'scope, presence_or_selection, side, price, outcome, significance, replication: met / not met / not applicable, with the numbers' },
    components: { type: 'object', properties: Object.fromEntries(COMPONENTS.map((k) => [k, COMP_VERDICT])), required: COMPONENTS, additionalProperties: false },
    target_met: { type: 'boolean' },
    criteria: { type: 'object', properties: Object.fromEntries(CRITERIA.map((k) => [k, VERDICT])), required: CRITERIA, additionalProperties: false },
    criteria_details: { type: 'object', additionalProperties: { type: 'string' } },
    why_it_works: { type: 'string', description: 'the economic mechanism: who loses to it and what it is paid for' },
    deploy_now: {
      type: 'object',
      properties: { supported: { type: 'boolean' }, evidence: { type: 'string' } },
      required: ['supported', 'evidence'],
      description: 'is "this strategy is statistically significant to continue working if I deployed it now" supported for a normal user?',
    },
    diagnosis: { type: 'string', description: 'for the reverse engineer, from the first half of the lot only' },
    explanation: { type: 'string' },
    mechanical_fixes_made: { type: 'string' },
    evidence_files: { type: 'array', items: { type: 'string' } },
  },
  required: ['fresh_data_sufficient', 'holdout_sample', 'now_ts', 'rule_summary', 'leakage_check', 'metrics', 'target_conditions', 'components', 'target_met', 'criteria', 'why_it_works', 'deploy_now', 'diagnosis', 'explanation', 'evidence_files'],
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

const PANEL_LENSES = {
  information: 'INFORMATION SOURCE AND DATA: what does the wallet see, earlier or better, that the investigation has not obtained? Settlement feeds, other venues and derivatives, faster sports or esports feeds, Polymarket\'s own books and real-time feeds (the shared recordings), cross-market prices, news. Which data would most sharply separate the leading explanations, and how can it be fetched on this laptop?',
  mechanics: 'MECHANICS AND ON-CHAIN FORENSICS: how the orders are actually built: V2 calldata order reconstruction (signing timestamps, original size, limit price), resting-order lifetimes and ladders, requote and cancel cadence, the inverse-fitted quote function, complement pairs, splits and merges, inventory and risk limits, rebates, liquidity and holding rewards, fingerprints of the bot software.',
  assumptions: 'ASSUMPTION BREAKER: what is the investigation taking for granted that may be false? The target variable or the unit of decision, pooling several bot versions or several strategies, the wallets being one operator, the wallet copying another wallet, counterparty flow being the edge, a mis-specified metric or baseline, human or scheduled behaviour, operational events, where exactly the PnL comes from.',
}
const AUDIT_LENSES = {
  untried: 'UNTRIED MECHANISMS: explanations of the wallet\'s decisions that the ledger never tested, or tested only in a weak form (say what the strong form is).',
  data: 'DATA ADEQUACY: is the conclusion limited by the data rather than by the mechanism? Missing feeds, too little history, sampled instead of complete markets, the shared recordings unused, no calldata order reconstruction, no sibling wallets.',
  method: 'METHOD AND TARGET: could the wall be an artefact of how the problem was posed? The wrong target (fills instead of orders), the wrong unit, pooled bot versions, a weak model class, a mis-specified baseline, or an information-wall test that does not show what it claims.',
}
const LENSES = {
  leakage: 'LEAKAGE AND LOOK-AHEAD: any feature, parameter, threshold, universe filter or label that uses information from at or after the decision time or from sealed units; reads of other strategies\' files, the shared HTTP cache file or .cache/live/sealed/ during development; raw Gamma records of sealed markets; the wallet\'s own prints leaking into features; block-time slack ignored for maker fills; post-hoc market metadata.',
  statistics: 'STATISTICS: is the effect real and large enough? Recompute the key number yourself; check sample size, dependence (2-hour blocks, games), the right null with enough draws, alpha = 0.0025, the replication halves, multiplicity over hypotheses and families tried, selection of the reported metric or sample, sensitivity to the threshold and to dropping the best days or markets.',
  match_validity: 'MATCH VALIDITY: does the match come from co-occurrence with other traders (is the examiner\'s own activity-only baseline strong enough?), from own-state features, an oracle, a narrowed universe (coverage of fills and absolute PnL below 80%), a subset of wallets or bot versions, or trivial anchors presented as decoded components?',
  deployability: 'DEPLOYABILITY FOR A NORMAL USER: latency at least 1-2 s for decision plus order, queue position as a newcomer, fees and the 0% rebate tier a newcomer holds, capacity toward $50k/month, capital needed, private or faster data feeds, and whether the conditions (Polymarket policy, market listings, competition, the wallet\'s own recent PnL trend) still hold in the latest data.',
}
const CRIT_LENSES = {
  match: ['leakage', 'statistics', 'match_validity'],
  backtest: ['leakage', 'statistics', 'deployability'],
  replicable: ['deployability', 'statistics', 'leakage'],
  persists: ['deployability', 'statistics', 'leakage'],
}

const PREMISE = 'The premise (the user\'s standard): these wallets passed a strict significance screen, so their profit is not luck. A systematic decision process produced their trades, and it runs on inputs that exist somewhere. Finding that process is the job; "no public-data rule matched" is a failed investigation, not a finding. Found means a frozen rule that passes the sealed exam: a match that is leaked, overfit, driven by co-occurrence or narrowed in scope is a worse failure than an honest "not decoded" with a quantitative account of what is unexplained.'
const EXAMINER_STANCE = 'The premise in the brief drives the reverse engineer, not you. Your verdict must not depend on it: "fail" is a normal outcome, and a generous reading of a partial result is a defect.'

function sealedLine(s, st) {
  return `Sealed data for you (pre-registered calendar, research/reverse_engineering/tools/sealed.py; run it with your key to see your periods): released lots ${JSON.stringify(st.released)}, future sealed blocks examined up to ${utc(st.futureUntil)}. Everything else at or after H = ${utc(H)} that the calendar marks sealed is off limits, including .cache/live/sealed/.`
}

function iterPrompt(s, st) {
  const i = st.iter + 1
  const out = []
  out.push(`You are the deep reverse-engineering agent for strategy "${s.key}" (${s.title}); wallets ${JSON.stringify(s.wallets || [])}. Iteration ${i}. ${Math.round(st.minutes)} of the ${MAX_MINUTES}-minute budget are used. A wall may be claimed only after ${MIN_WALL_MINUTES} minutes, with no catalog item (including X items) open, and it stands only if an independent audit cannot name an untried direction.`)
  out.push(PREMISE)
  out.push(`Read research/reverse_engineering/BRIEF.md first and follow it exactly. It changed on 2026-10-31: finding the strategy is the job; there is no diminishing-returns stop; walls need proof and an audit; there is a direction catalog to work through (track it in state.json, with every panel and audit proposal as an X item); a pre-registered calendar decides what is sealed; a shared live recorder (tools/live.py) is running; V2 calldata gives every filled order's millisecond signing time (catalog B1); the high-accuracy target is pre-registered in detail; a failed exam feeds its diagnosis back to you. Workspace: research/reverse_engineering/${s.key}/ and .cache/re/${s.key}/. Repo root: your current working directory (run every command from it).`)
  out.push(sealedLine(s, st))
  out.push(`Dossier:\n${s.dossier}`)
  out.push('If your workspace has no NOTES.md yet, create it, state.json (with the catalog and target_metrics) and code/, pre-register your primary metric and your BUILD/VALIDATE split, and begin by expanding the data well beyond what the earlier studies used. Otherwise continue your predecessors\' work: read NOTES.md, state.json, FINAL_RULE.md, panels/, any EXAM*.md and results/wall_audit_*.json before anything else. Bring state.json up to the brief\'s current format (catalog with the new items, target_metrics, component tags) if it is older. Do not repeat hypotheses already rejected in the same form; deepen what works and open what was never tried.')
  if (s.interrupted && st.history.length === 0) out.push(`Interrupted work from the previous run: ${s.interrupted}`)
  if (st.retryNote) out.push(st.retryNote)
  if (st.history.length) out.push(`Iterations in this run so far: ${JSON.stringify(st.history.slice(-6))}`)
  if (st.failedRound) {
    const f = st.failedRound
    out.push(`EXAM ROUND ${f.round} (lot ${f.lot}) DID NOT PASS. Lot ${f.lot} is now released to you: its first half carries the diagnosis and is yours to study case by case; use its second half as VALIDATE (aggregate metrics only). The examiner's diagnosis: ${f.diagnosis || '(none given)'}${f.refutations ? `\nThe skeptics downgraded the examiner's pass: ${f.refutations}` : ''}\nRead EXAM_r${f.round}.md, results/exam_r${f.round}.json, results/adjudication_r${f.round}.json and results/refute_r${f.round}_*.json. The cases where your rule disagrees with the wallet are the most informative data you have.`)
  }
  if (st.auditDirections) out.push(`THE LAST WALL AUDIT (number ${st.auditDirections.n}) REJECTED THE WALL. Add each of these to the catalog as an X item and test it or rule it out with a measurement before any new wall claim (full text in results/wall_audit_${st.auditDirections.n}_*.json): ${JSON.stringify(st.auditDirections.items)}`)
  if (st.wallRefusal) out.push(`Your last wall claim was refused: ${st.wallRefusal}. Continue.`)
  if (st.claimRefusal) out.push(`Your last target claim was refused before any exam: ${st.claimRefusal}. Keep working on those conditions.`)
  if (st.examNote) out.push(st.examNote)
  if (st.panel) out.push(`PANEL after iteration ${st.iter}: three independent experts read your notebook. Their critiques and top proposals (full text in panels/iter${st.iter}_*.md): ${JSON.stringify(st.panel)}\nAdd each proposal to the catalog as an X item. Test the highest-priority ones this iteration, or record (with the measurement) why one is already ruled out. List what you tested in proposals_tested.`)
  if (st.pivot) out.push(`PIVOT REQUIRED: progress toward the target moved less than 0.02 over the last two iterations (progress ${JSON.stringify(st.progress.slice(-3))}, from target_metrics). Spend this iteration on a fundamentally different paradigm: a different target, data source, unit of decision or model class, from the catalog or the panel. Tuning the current model is not a pivot. Name it in "paradigm".`)
  out.push(`How to work: think like the best reverse engineer alive. Start by writing at least five competing explanations of how this wallet makes its money (including unlikely ones) and what observation tells them apart, then design measurements that discriminate between them, and let the data overturn your assumptions. Decode the decision process component by component (selection, timing, side, price, size, exit), not a fill predictor. If the data cannot separate the hypotheses, get more (catalog: V2 calldata signing times, the settlement TWAP, the recorded books, sibling wallets, copy-trading lead-lag, bot versions, rewards and rebates, ...). Work for about ${ITER_MINUTES} minutes of wall-clock time: run \`date -u +%s\` now and check it regularly. At about ${ITER_MINUTES - 8} minutes stop starting new analyses; update NOTES.md, state.json (status, strategy_statement, components with tags, catalog, target_metrics, this iteration's entry), FINAL_RULE.md and code/final_rule.py (the best frozen rule so far, with evaluate(start_ts, end_ts, intervals=None) reporting per wallet and pooled); run \`date -u +%s\` once more for now_ts; and return.`)
  out.push('Return "target_reached" only if every target condition holds on VALIDATE in target_metrics (the workflow checks them before spending sealed data). Return "wall" only if every wall condition in the brief holds; an early or unproven claim is refused and costs only time. Otherwise return "continue". catalog_open lists every catalog id still open, X items included.')
  return out.join('\n\n')
}

function panelPrompt(s, st, lens, r) {
  const latest = { statement: clip(r.strategy_statement, 1500), components: r.components, target_metrics: r.target_metrics, paradigm: r.paradigm, rule: clip(r.best_rule_summary, 800), findings: (r.key_findings || []).slice(0, 10), next_steps: r.next_steps, catalog_open: r.catalog_open }
  return `You are a fresh-eyes expert on a review panel for the Polymarket strategy "${s.key}" (${s.title}); wallets ${JSON.stringify(s.wallets || [])}. The reverse engineer has worked ${Math.round(st.minutes)} minutes over ${st.iter} iterations and has not yet decoded the strategy.

${PREMISE} The panel's job is to find what the investigation is missing.

Your lens: ${PANEL_LENSES[lens]}

Read research/reverse_engineering/BRIEF.md (especially the premise and the direction catalog), then the workspace research/reverse_engineering/${s.key}/: NOTES.md, state.json (hypothesis ledger, catalog, components), FINAL_RULE.md, earlier files in panels/, and any EXAM*.md and results/wall_audit_*.json. Repo root: your current working directory.

Latest iteration: ${JSON.stringify(latest)}

Propose 3 to 6 directions through your lens that are NOT already in the hypothesis ledger or the catalog, or that were tested only in a weak form (then say what the strong form is). Each needs: the hypothesis; what in the evidence points to it; a concrete discriminating test runnable on this laptop with public data or the shared recordings; the data it needs; the signature you would see if it is true. Rank them by the chance they close the gap. You may run small checks to sharpen a proposal (first run .venv/Scripts/python.exe research/reverse_engineering/tools/resources.py --wait-mem 600; keep each process under 300 MB; at most about 20 minutes), but do not do the reverse engineer's work. ${sealedLine(s, st)}

Write your critique and proposals to research/reverse_engineering/${s.key}/panels/iter${st.iter}_${lens}.md (create the folder if needed) and nowhere else. No git.`
}

function auditPrompt(s, st, r, lens, n) {
  return `You are an independent wall auditor for the Polymarket strategy "${s.key}" (${s.title}); wallets ${JSON.stringify(s.wallets || [])}. After ${Math.round(st.minutes)} minutes over ${st.iter} iterations, the reverse engineer claims a wall: "${clip(r.wall_reason || '', 2500)}"

${PREMISE} A wall stands only if it is proven and nobody can name a promising untried direction. Default to rejecting it.

Your lens: ${AUDIT_LENSES[lens]}

Read research/reverse_engineering/BRIEF.md (premise, catalog, wall), then the workspace research/reverse_engineering/${s.key}/: NOTES.md, state.json (hypothesis ledger, catalog, components), FINAL_RULE.md, panels/, any EXAM*.md and earlier results/wall_audit_*.json. Repo root: your current working directory. Check that every catalog item (X items included) was genuinely tried or ruled out with a measurement (not an argument, not a weak version), that "infeasible" items record the failing request, that the earlier audits' directions were addressed, and that the information-wall evidence is quantitative and shows what it claims. You may run small checks (first run .venv/Scripts/python.exe research/reverse_engineering/tools/resources.py --wait-mem 800; keep each process under 500 MB; at most about 30 minutes). ${sealedLine(s, st)}

accept = true only if you cannot name any concrete, promising, untried direction runnable on this laptop with public data or the shared recordings. Otherwise list those directions (title, why promising, test, data needed, catalog id) and the catalog items that are not genuinely closed.

Write your audit to research/reverse_engineering/${s.key}/results/wall_audit_${n}_${lens}.json and nowhere else. No git.`
}

function examPrompt(s, st, round, lot, last, final) {
  const prior = st.exams.length ? ` Earlier exam rounds: ${JSON.stringify(st.exams)}; their lots are development data now.` : ''
  const defer = final || st.deferrals >= MAX_DEFERRALS
    ? 'This exam may not be deferred: proceed with the data there is and state the statistical power.'
    : 'If the lot has too few units for the metrics (at least 40 games or matches for sports and esports; for sparse events, state the power), return fresh_data_sufficient = false at once without reading fills, prices or outcomes. Then write only results/exam_deferral_' + (st.deferrals + 1) + '.json (the counts and why) and nothing else; fill the other fields with these placeholders: strings "n/a", numbers 0, booleans false, criteria "fail", components "not_applicable", objects {}.'
  return `You are the independent examiner for strategy "${s.key}" (${s.title}); wallets ${JSON.stringify(s.wallets || [])}. Exam round ${round}, lot ${lot.lot}. The reverse engineer has worked ${Math.round(st.minutes)} minutes over ${st.iter} iterations; its last status is "${last ? last.status : 'none'}"${last && last.wall_reason ? ` (${clip(last.wall_reason, 600)})` : ''}. Do not trust their numbers; reproduce everything yourself. ${EXAMINER_STANCE}

Read research/reverse_engineering/BRIEF.md (sealed data, metrics, the pre-registered high-accuracy target with its scope, baseline, significance and replication rules, engineering rules for this shared laptop) and the workspace research/reverse_engineering/${s.key}/ (NOTES.md, state.json, FINAL_RULE.md, code/). Repo root: your current working directory (run every command from it). Also read docs/methodology.md (criteria) and research/verdicts/<wallet>.json for the wallets.

The exam lot (fixed by the pre-registered calendar in research/reverse_engineering/tools/sealed.py): ${fmtLot(lot)}. Units (windows, games, matches) that start in these intervals, or events that resolve in them; every record of those units counts, whatever its timestamp. Shared live recordings for the lot are in .cache/live/sealed/ (tools/live.py iter_live(..., allow_sealed=True)).${prior}

Rules for you: run every fetch of sealed data with the environment variable POLYREA_CACHE_DIR=.cache/exam/${s.key} so the shared HTTP cache never holds it. Never edit code/final_rule.py or other files in code/: drive it from your own exam/ scripts (set its ALLOW_SEALED to True there), and if a mechanical fix is unavoidable (paths, imports, memory, Windows), copy the file into exam/, patch the copy and save the diff as results/exam_r${round}_patch.diff. Draw any sample from listing metadata with a stated seed before reading fills or outcomes.

0. Sufficiency, from listing metadata only. ${defer}
1. Leakage audit: read the code. Confirm every parameter of the final rule is a constant, that development code never read sealed units (by the calendar, for this strategy), other strategies' workspaces or caches, the shared HTTP cache file, or .cache/live/sealed/, and never stored raw Gamma records of sealed markets; that decision features are point-in-time (no outcomes, no post-hoc metadata, the wallet's own prints excluded, block-time slack for maker fills, ESPN delay >= 5 s; settlement values only once published). Run a truncation test on a sample: remove or corrupt all data after each decision time and confirm identical decisions.
2. Before reading fills, split the lot into an earlier and a later half from listing metadata. Run evaluate(start, end, intervals) on the lot.
3. Independently recompute the target metrics with your own code where feasible, pooled, per half and per wallet: scope (coverage of fills and absolute PnL); presence or selection AUC with recall and lift; the gain over the stronger of the reverse engineer's activity-only baseline and one you fit yourself with the same model class, tuning budget and BUILD data, with a 95% block-bootstrap interval; side accuracy against the market-only and own-inventory-only baselines (you decide whether side applies); price within one tick against the best trivial anchor; per-market correlation of the executable rule's realized PnL with the wallet's (Pearson and Spearman); rotation or permutation nulls with at least 2,000 draws, one-sided alpha = 0.0025. Also the rule's return under strict fills with latency >= 2 s (match_slack=2 for makers) with its p-value, and the wallet's own return on the same markets.
4. target_met is true only if every condition of the pre-registered target holds (scope, presence or selection with the baseline gain, side, price, outcome, significance, replication); report each in target_conditions. Then judge each component (pass / partial / fail / not_applicable) and each criterion:
   - (6) match: pass ONLY if target_met is true. A methodology-only match (e.g. rotation-null p < 0.01 with modest effect sizes) is partial.
   - (7) backtest: is the rule significantly profitable on the lot (p < 0.05) under strict fills at >= 2 s, without rebates a newcomer would not get?
   - (8) replicable: could a normal user on a normal connection and computer run it profitably (no private or faster feed, latency >= 2 s, newcomer queue position and 0% rebate tier, capacity toward $50k/month)?
   - (9) persists: is "this strategy is statistically significant to continue working if I deployed it now" supported? Use the newest days of the lot, the rule's PnL there, the wallet's own recent PnL (polyrea.tools.assess_persistence(wallet, as_of=<latest full day>) with one-off bonuses removed), and whether the conditions the mechanism relies on (policy, fees and rebates, listings, competition) still hold. Pass only with statistical evidence, not plausibility.
5. Explain why the strategy works (the economic mechanism: who loses to it, what it is paid for) and state whether the deploy-now statement is supported, with the evidence.
6. Diagnosis: if the match is not a pass, the lot is released to the reverse engineer and they continue. Write a precise diagnosis from the FIRST half of the lot only: where the rule disagrees with the wallet (components, markets, times, states), what the disagreements have in common, and what they suggest. Give only aggregate metrics for the second half. Do not fix the rule yourself.
7. After a real (not deferred) exam, release the lot: .venv/Scripts/python.exe research/reverse_engineering/tools/sealed.py ${s.key} --release ${lot.lot.startsWith('f') ? `f --until ${lot.until}` : lot.lot}

Write EXAM_r${round}.md and results/exam_r${round}.json in the workspace, and copy them to EXAM.md and results/exam.json. Follow the brief's engineering rules (memory and disk gates, no git, write only in the workspace, exam/, .cache/re/${s.key}/ and .cache/exam/${s.key}/).`
}

function refutePrompt(s, exam, round, crit, lens) {
  return `You are an adversarial skeptic for strategy "${s.key}" (${s.title}). In exam round ${round}, an independent examiner judged criterion "${crit}" as PASS. Your job is to REFUTE that pass if it does not hold. Default to refuted=true if, after checking, you are not convinced the pass is sound. ${EXAMINER_STANCE}

Your lens: ${LENSES[lens]}

Examiner's judgment: ${JSON.stringify({ criteria: exam.criteria, criteria_details: exam.criteria_details, target_conditions: exam.target_conditions, components: exam.components, metrics: exam.metrics, per_wallet: exam.per_wallet, target_met: exam.target_met, holdout_sample: exam.holdout_sample, rule_summary: exam.rule_summary, deploy_now: exam.deploy_now })}

Read research/reverse_engineering/BRIEF.md, docs/methodology.md and the workspace research/reverse_engineering/${s.key}/ (FINAL_RULE.md, EXAM_r${round}.md, results/exam_r${round}.json, any results/exam_r${round}_patch.diff, state.json, code/, exam/). Repo root: your current working directory. Check the claim through your lens with your own code where feasible (recompute rather than trust; fetch sealed data only with POLYREA_CACHE_DIR=.cache/exam/${s.key}; keep jobs small: run research/reverse_engineering/tools/resources.py --wait-mem 1200 before anything heavy). Write your finding to research/reverse_engineering/${s.key}/results/refute_r${round}_${crit}_${lens}.json and nowhere else (no git). Severity: fatal = the pass is wrong; material = the pass rests on a flawed number but might survive a fix; minor = cosmetic.`
}

function commitPrompt(s, msg, files, copies) {
  const ws = `research/reverse_engineering/${s.key}`
  const entries = Object.entries(files || {})
  const cps = (copies || []).map(([a, b]) => `cp ${ws}/${a} ${ws}/${b}`)
  const step1 = entries.length
    ? `1. Use the Write tool to create each of these files with exactly the JSON shown (create folders if needed; overwrite existing files):\n${entries.map(([p, c]) => `${ws}/${p}:\n${JSON.stringify(c, null, 1)}`).join('\n\n')}\n${cps.length ? `Then run: ${cps.join(' && ')}\n` : ''}`
    : '1. (nothing to write)\n'
  return `You are a git committer for a research repository. Work from the repository root (your current working directory) in the Bash tool (Git Bash). Do not edit any file other than those in step 1.

${step1}2. Run: .venv/Scripts/python.exe -m polyrea.report   (rebuilds research/ledger.json, research/README.md, dashboard/index.html and research/wallets/*/REPORT.md). If it fails, report the error and continue without it.
3. Run: find ${ws} -type f -size +5M   — files listed there must NOT be committed.
4. Run: git add -- ${ws} research/reverse_engineering/BRIEF.md research/README.md research/ledger.json dashboard/index.html research/wallets   then for every file from step 3 run git reset -q -- <file>. Do not add anything else (never git add -A or git add .).
5. If git diff --cached --quiet reports changes, commit: git commit -m "${msg.replace(/"/g, "'")}" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
6. git push origin ${BRANCH}. If the push is rejected, run git pull --rebase --autostash origin ${BRANCH} and push once more; if that fails too, report it and stop (the next commit will push). Never force-push, never switch branches, never touch other branches.
Return one line: the commit hash (or "nothing to commit") and whether the push succeeded.`
}

// Commits run one at a time, in the order requested, so git never races itself. The prompt is built when the
// commit is requested, so it records the state at that moment.
let commitChain = Promise.resolve()
function commit(s, msg, files, copies) {
  const prompt = commitPrompt(s, msg, files, copies)
  commitChain = commitChain
    .then(() => run(s.key, prompt, { label: `commit:${s.key}`, phase: 'Commit', model: 'haiku', effort: 'low' }))
    .catch(() => null)
  return commitChain
}

function progress(st) {
  const sc = st.scores.filter((x) => typeof x === 'number')
  return clone({
    brief: 'find-the-strategy (2026-10-31, calendar lots)',
    stage: st.stage,
    iterations: st.iter,
    minutes: Math.round(st.minutes),
    budget_minutes: MAX_MINUTES,
    best_validate_score: sc.length ? Math.max(...sc) : null,
    progress: st.progress.slice(-1)[0] ?? null,
    released: st.released,
    future_examined_until: st.futureUntil,
    exam_rounds: st.exam_round,
    exams: st.exams,
    wall_audits: st.audits,
    wall_refusals: st.wallRefusals,
    claim_refusals: st.claimRefusals,
    panels: st.panels,
    note: st.note || null,
  })
}
const progressFile = (st) => ({ 'results/progress.json': progress(st) })

async function iterate(s, st) {
  const p = iterPrompt(s, st)
  const label = `re:${s.key}:${st.iter + 1}${st.failures ? `:try${st.failures + 1}` : ''}`
  const r = await run(s.key, p, { label, phase: 'Reverse engineer', schema: ITER, effort: 'max' })
  return r || run(s.key, p, { label: `${label}:retry`, phase: 'Reverse engineer', schema: ITER, effort: 'max' })
}

async function runPanel(s, st, r) {
  const lenses = Object.keys(PANEL_LENSES)
  const out = await parallel(lenses.map((lens) => () => run(s.key, panelPrompt(s, st, lens, r), { label: `panel:${s.key}:${st.iter}:${lens}`, phase: 'Panel', schema: PANEL, effort: 'xhigh' })))
  const panel = {}
  out.forEach((p, j) => {
    if (!p) return
    const top = (p.proposals || []).slice().sort((a, b) => (a.priority || 9) - (b.priority || 9)).slice(0, 5)
    panel[lenses[j]] = { critique: clip(p.critique, 1200), proposals: top.map((q) => ({ title: q.title, test: clip(q.test, 600), priority: q.priority })) }
  })
  st.panels += Object.keys(panel).length ? 1 : 0
  return Object.keys(panel).length ? panel : null
}

async function wallAudit(s, st, r) {
  const n = st.audits.length + 1
  const lenses = Object.keys(AUDIT_LENSES)
  const ask = (lens, tag) => run(s.key, auditPrompt(s, st, r, lens, n), { label: `audit:${s.key}:${n}:${lens}${tag}`, phase: 'Wall audit', schema: AUDIT, effort: 'xhigh' })
  const votes = await parallel(lenses.map((lens) => () => ask(lens, '').then((v) => v || ask(lens, ':retry'))))
  const vs = votes.map((v, j) => v && { ...v, lens: lenses[j] }).filter(Boolean)
  if (vs.length < lenses.length) return { incomplete: true }
  // The wall stands only if every auditor accepted it and none named an untried direction.
  const accepted = vs.every((v) => v.accept && !(v.untried_directions || []).length)
  const items = vs.flatMap((v) => (v.untried_directions || []).map((d) => ({ lens: v.lens, title: d.title, test: clip(d.test, 500), catalog_id: d.catalog_id })))
  const gaps = [...new Set(vs.flatMap((v) => v.catalog_gaps || []))]
  if (!accepted && !items.length) {
    vs.filter((v) => !v.accept).forEach((v) => items.push({ lens: v.lens, title: 'auditor objection', test: clip(v.reasoning, 600) }))
  }
  if (gaps.length) items.push({ lens: 'all', title: 'catalog items not genuinely closed', test: gaps.join(', ') })
  st.audits.push({ n, accepted, at_minutes: Math.round(st.minutes), rejected_by: vs.filter((v) => !v.accept || (v.untried_directions || []).length).map((v) => v.lens), directions: items.length, catalog_gaps: gaps })
  return { accepted, n, items }
}

async function examine(s, st, last, final) {
  const lot = nextLot(st, st.nowTs)
  const min = s.sealed_min_hours || 24
  if (lot.hours < min) return { waiting: true, lot, min }
  const round = st.exam_round + 1
  const exam = await run(s.key, examPrompt(s, st, round, lot, last, final), { label: `exam:${s.key}:r${round}:${lot.lot}`, phase: 'Examine', schema: EXAM, effort: 'xhigh' })
  if (!exam) return { failed: true }
  if (exam.fresh_data_sufficient === false && !final && st.deferrals < MAX_DEFERRALS) {
    st.deferrals += 1
    return { deferred: true, exam, lot }
  }
  st.exam_round = round
  st.deferrals = 0
  const refutations = {}
  const verdicts = Object.fromEntries(CRITERIA.map((k) => [k, (exam.criteria && exam.criteria[k]) || 'fail']))
  // A methodology-only match is not a pass.
  if (verdicts.match === 'pass' && exam.target_met !== true) verdicts.match = 'partial'
  const passed = CRITERIA.filter((k) => verdicts[k] === 'pass')
  log(`${s.key} exam r${round} (${lot.lot}): target ${exam.target_met ? 'met' : 'not met'}, criteria ${JSON.stringify(exam.criteria)}${passed.length ? `; refuting ${passed.join(', ')}` : ''}`)
  const downgraded = []
  // Skeptics run one at a time (each may run Python jobs on the shared laptop).
  for (const crit of passed) {
    const votes = []
    for (const lens of CRIT_LENSES[crit]) {
      const ask = (tag) => run(s.key, refutePrompt(s, exam, round, crit, lens), { label: `refute:${s.key}:r${round}:${crit}:${lens}${tag}`, phase: 'Refute', schema: REFUTE, effort: 'high' })
      votes.push((await ask('')) || (await ask(':retry')))
    }
    const vs = votes.map((v, j) => v && { ...v, lens: CRIT_LENSES[crit][j] }).filter(Boolean)
    refutations[crit] = vs.map((v) => ({ lens: v.lens, refuted: v.refuted, severity: v.severity, reasoning: clip(v.reasoning, 400) }))
    const fatal = vs.some((v) => v.refuted && v.severity === 'fatal')
    const material = vs.filter((v) => v.refuted && v.severity === 'material').length
    // The pass survives only if all three skeptics returned, none found it fatally wrong and at most one found a material flaw.
    if (vs.length < CRIT_LENSES[crit].length || fatal || material >= 2) {
      verdicts[crit] = crit === 'match' ? 'partial' : 'fail'
      downgraded.push(`${crit}: ${vs.filter((v) => v.refuted).map((v) => `${v.lens} (${v.severity}): ${clip(v.reasoning, 300)}`).join(' | ') || 'not every skeptic returned'}`)
    }
  }
  const adjudication = {
    round,
    lot: lot.lot,
    intervals: lot.intervals,
    examiner_criteria: exam.criteria,
    criteria: verdicts,
    components: exam.components,
    target_met: exam.target_met === true,
    target_conditions: exam.target_conditions,
    deploy_now_supported: !!(exam.deploy_now && exam.deploy_now.supported) && verdicts.persists === 'pass' && verdicts.backtest === 'pass' && verdicts.replicable === 'pass',
    refutations,
  }
  st.exams.push({ round, lot: lot.lot, criteria: verdicts, target_met: exam.target_met === true })
  // The examined lot becomes development data for this strategy.
  if (lot.lot.startsWith('f')) {
    st.futureUntil = lot.until
    st.futureRound += 1
  } else st.released.push(lot.lot)
  return { exam, verdicts, adjudication, round, lot, downgraded }
}

function commitExam(s, st, ex, prefix) {
  const sealedState = { released: st.released, future_examined_until: st.futureUntil }
  commit(s, `${s.key}: ${prefix} round ${ex.round}, lot ${ex.lot.lot} (${Object.entries(ex.verdicts).map(([k, v]) => `${k} ${v}`).join(', ')})`,
    { [`results/adjudication_r${ex.round}.json`]: ex.adjudication, 'results/sealed_state.json': sealedState, ...progressFile(st) },
    [[`results/adjudication_r${ex.round}.json`, 'results/adjudication.json']])
}

async function runStrategy(s) {
  const st = {
    stage: 'reverse_engineering',
    iter: s.prior_iters || 0,
    minutes: s.prior_minutes || 0,
    scores: (s.prior_scores || []).slice(),
    progress: [],
    released: (s.released || []).slice(),
    futureUntil: s.future_examined_until || T0,
    futureRound: (s.prior_exams || []).filter((e) => String(e.lot || '').startsWith('f')).length,
    exams: (s.prior_exams || []).slice(),
    exam_round: (s.prior_exams || []).length,
    failedRound: s.prior_diagnosis ? { round: (s.prior_exams || []).length, lot: ((s.prior_exams || []).slice(-1)[0] || {}).lot || 'h1+h2', diagnosis: s.prior_diagnosis } : null,
    audits: [],
    auditDirections: null,
    wallRefusal: null,
    wallRefusals: 0,
    claimRefusal: null,
    claimRefusals: 0,
    examNote: null,
    retryNote: null,
    panel: null,
    panels: 0,
    pivot: false,
    lastPivot: -99,
    deferrals: 0,
    failures: 0,
    nowTs: null,
    note: null,
    history: [],
  }
  let last = null
  let examinedLast = false
  while (true) {
    if (st.minutes >= MAX_MINUTES) { st.stage = 'budget_exhausted'; break }
    if (spawned >= ITER_CAP || spawnedBy[s.key] >= STRAT_QUOTA) { st.stage = 'agent_cap'; log(`${s.key}: stopping new iterations at the agent limit`); break }
    const r = await iterate(s, st)
    if (!r) {
      st.failures += 1
      st.retryNote = `The previous attempt at this iteration failed to return (${st.failures} in a row). Checkpoint early: write NOTES.md and state.json as you go, keep tool output short, and return well within the time.`
      if (st.failures >= MAX_FAILURES) { st.stage = 'agent_failed'; st.note = 'infrastructure: the reverse-engineering agent failed to return several times in a row'; break }
      continue
    }
    st.failures = 0
    st.retryNote = null
    last = r
    examinedLast = false
    st.iter += 1
    st.minutes += Math.min(Math.max(r.minutes_worked || ITER_MINUTES, 20), 2 * ITER_MINUTES)
    if (typeof r.now_ts === 'number' && r.now_ts > T0 && (!st.nowTs || r.now_ts >= st.nowTs)) st.nowTs = Math.floor(r.now_ts > 1e11 ? r.now_ts / 1000 : r.now_ts)
    st.scores.push(r.best_validate_score)
    st.progress.push(progressScore(r.target_metrics))
    st.history.push({
      n: st.iter, status: r.status, paradigm: r.paradigm, score: r.best_validate_score, progress: st.progress.slice(-1)[0],
      confidence: Object.fromEntries(Object.entries(r.components || {}).map(([k, v]) => [k, v && v.confidence])),
      families: r.families_tried_this_iteration, open_catalog: (r.catalog_open || []).length, minutes: r.minutes_worked,
    })
    // One-shot inputs are consumed by the iteration that just ran; audit directions stay until the next audit.
    st.failedRound = null
    st.wallRefusal = null
    st.claimRefusal = null
    st.examNote = null
    st.panel = null
    st.pivot = false
    log(`${s.key} iteration ${st.iter}: ${r.status} (${r.paradigm}), ${r.primary_metric}=${r.best_validate_score}, progress ${st.progress.slice(-1)[0]}, ${(r.catalog_open || []).length} catalog items open, ${Math.round(st.minutes)} min total`)
    commit(s, `${s.key}: deep reverse engineering iteration ${st.iter} (${r.status}, ${r.primary_metric} ${r.best_validate_score})`, progressFile(st))

    let done = false
    if (r.status === 'wall') {
      const open = r.catalog_open || []
      if (st.minutes < MIN_WALL_MINUTES) st.wallRefusal = `only ${Math.round(st.minutes)} of the required ${MIN_WALL_MINUTES} minutes have been worked`
      else if (open.length) st.wallRefusal = `catalog items still open: ${open.join(', ')}`
      if (st.wallRefusal) {
        st.wallRefusals += 1
        log(`${s.key}: wall refused (${st.wallRefusal})`)
      } else {
        st.stage = 'wall_audit'
        const a = await wallAudit(s, st, r)
        st.stage = 'reverse_engineering'
        if (a.incomplete) st.wallRefusal = 'the wall audit did not complete (an auditor failed to return); claim the wall again after this iteration if its conditions still hold'
        else if (a.accepted) { st.stage = 'wall_accepted'; done = true } else st.auditDirections = { n: a.n, items: a.items.slice(0, 20) }
        log(`${s.key} wall audit: ${a.incomplete ? 'incomplete' : a.accepted ? 'accepted' : `rejected with ${a.items.length} directions`}`)
        if (!a.incomplete) commit(s, `${s.key}: wall audit ${a.n} (${a.accepted ? 'accepted' : 'rejected'})`, progressFile(st))
      }
    } else if (r.status === 'target_reached') {
      const gaps = targetGaps(r.target_metrics)
      if (gaps.length) {
        st.claimRefusal = `these target conditions do not hold in your own VALIDATE target_metrics: ${gaps.join('; ')}`
        st.claimRefusals += 1
        log(`${s.key}: target claim refused (${gaps.length} conditions)`)
      } else {
        st.stage = 'examining'
        const ex = await examine(s, st, r, false)
        st.stage = 'reverse_engineering'
        if (ex.waiting) st.examNote = `THE EXAM IS WAITING FOR SEALED DATA: lot ${ex.lot.lot} has ${ex.lot.hours} of the ${ex.min} sealed hours it needs (${fmtLot(ex.lot)}). Keep improving and claim the target again later; sealed 6-hour blocks accrue on the calendar.`
        else if (ex.failed) st.examNote = 'The exam agent failed to return; the exam is retried when you next claim the target.'
        else if (ex.deferred) st.examNote = `EXAM DEFERRED by the examiner (too few units in lot ${ex.lot.lot}: ${clip(ex.exam.holdout_sample, 300)}). Keep improving; it is retried when you next claim the target.`
        else {
          examinedLast = true
          if (ex.verdicts.match === 'pass' && ex.adjudication.target_met) { st.stage = 'decoded'; done = true } else {
            st.failedRound = { round: ex.round, lot: ex.lot.lot, diagnosis: clip(ex.exam.diagnosis, 3000), refutations: ex.downgraded.length ? clip(ex.downgraded.join(' || '), 2000) : null }
            if (st.exam_round >= MAX_EXAMS) { st.stage = 'not_decoded_exams_exhausted'; done = true }
          }
          commitExam(s, st, ex, 'exam')
        }
      }
    }
    if (done) break
    const pr = st.progress.filter((x) => typeof x === 'number')
    if (pr.length >= 3 && st.iter - st.lastPivot >= 3 && pr[pr.length - 1] - pr[pr.length - 3] < 0.02) {
      st.pivot = true
      st.lastPivot = st.iter
    }
    if (st.minutes < MAX_MINUTES) {
      if (spawned < PANEL_CAP && spawnedBy[s.key] < STRAT_QUOTA - 15) st.panel = await runPanel(s, st, r)
      else log(`${s.key}: panel skipped near the agent limit`)
    }
  }

  // A strategy that stops without a passing exam on its latest rule is examined once more, so its conclusion is
  // recorded, if the next lot has enough sealed data.
  if (last && !examinedLast && st.stage !== 'decoded') {
    const stage = st.stage
    st.stage = 'examining'
    const ex = await examine(s, st, last, true)
    st.stage = stage
    if (ex.waiting) st.note = `${st.note ? `${st.note}; ` : ''}closing exam not run: lot ${ex.lot.lot} had ${ex.lot.hours} of ${ex.min} sealed hours`
    else if (ex.failed) st.note = `${st.note ? `${st.note}; ` : ''}closing exam agent failed to return`
    else if (ex.verdicts) {
      if (ex.verdicts.match === 'pass' && ex.adjudication.target_met) st.stage = 'decoded'
      commitExam(s, st, ex, 'closing exam')
    }
    if (st.note) log(`${s.key}: ${st.note}`)
  }
  commit(s, `${s.key}: deep reverse engineering finished (${st.stage})`, progressFile(st))
  log(`${s.key} finished: ${st.stage} after ${st.iter} iterations, ${Math.round(st.minutes)} min, ${st.exam_round} exam round(s), ${st.audits.length} wall audit(s)`)
  return { key: s.key, stage: st.stage, iterations: st.iter, minutes: st.minutes, exams: st.exams, audits: st.audits, history: st.history, note: st.note }
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
log(`${STRATS.length} strategies, ${CONCURRENCY} at a time, up to ${MAX_MINUTES} min each: ${STRATS.map((s) => s.key).join(', ')}`)
await Promise.all(Array.from({ length: Math.min(CONCURRENCY, STRATS.length) }, () => worker()))
await commitChain
return STRATS.map((s) => results[s.key])
