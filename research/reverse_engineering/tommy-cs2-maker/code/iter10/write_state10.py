"""Iteration 10 state update: catalog X132-X143 (iteration-9 panel), component descriptions, ledger, iteration entry."""
import json, shutil, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
WS = ROOT / 'research/reverse_engineering/tommy-cs2-maker'
P = WS / 'state.json'
shutil.copy(P, ROOT / '.cache/re/tommy-cs2-maker/state_backup_iter9_end.json')
s = json.load(open(P, encoding='utf-8'))
cat = s['catalog']

new = {
 'X132': ('information panel P1 (iter 9): uncensored Dota ladder on the recorded books, on the OpenDota game clock', 'open',
          'Deferred with a measurement: the 10-31 development Dota maps have no wallet-independent clock (P4e anchors 0 and 4 on ty-gl maps 1 / 2, D-scan p 0.85; log_dota_feed_align_1031.txt), and fitting D on the wallet\'s own adds / cancels would make the kill-locking test circular. Folded into X118 on VALIDATE-live: the Valve receive-time clock (tommy_dota_rt) replaces the OpenDota D, with the panel\'s classification of re-pricing bursts (own-team kill, other-team kill, fight, objective, none) and the offset-in-fight test.'),
 'X133': ('information panel P2 (iter 9): Thunderpick in-play odds relayed key-free by bo3.gg as the private value', 'open',
          'Endpoint verified (bo3.gg live index, 200, keys total / results / links; bet_updates per live CS2 match: team coefficients, active flags, max_coeff, markets_count, additional handicap markets). Recorder code/iter10/tp_odds_recorder.py, feed tommy_tp_odds, ONE index request every 3 s (< 0.4 req/s), unit-rule filing, worker pid 31860, started 1793505571, hard stop 1793599200, 150 MB cap. Tests (a)-(f) and verdicts pre-registered in NOTES iteration 10 before any development record exists; first development block 11-01 06-12. Direct bookmaker probes (step 3) stay with X48 (b), consent needed.'),
 'X134': ('information panel P3 (iter 9): the offset driver on the feed\'s own clock (message phase / intensity), then its public echo', 'tried',
          'offset_phase.json (historical ceiling, 22,792 filled maker orders, wallet-independent message clock at the TRUE signing times): offset from the last print on class, time since message / own take, messages in 5 / 30 s, price level: R^2 0.071 BUILD / 0.043 VALIDATE (LightGBM 0.037), within one tick 0.281 vs last print 0.306; offset SD 6.0c, residual 5.9c. Ceiling below the panel\'s 0.4 / +0.10, so the point-in-time echo step (x records, pending-tx check) was not run: message phase does not set the offset.'),
 'X135': ('information panel P4 (iter 9): subscriber makers and joiners as the control for finding 14', 'tried',
          'subscriber_makers.json (BUILD-live, moves from +100 ms): wallet Spearman 0.31 / 0.24 / 0.18 at 2 / 10 / 30 s (quiet books 0.47 / 0.36 / 0.29, n 328) vs 5-share (trio-like) 0.14 / 0.10 / 0.07 (quiet 0.03 / 0.02 / 0.01), 10-share (group-G-like) 0.11 / 0.08 / 0.03, 20-share (0x2e3c40fa-like) 0.14 / 0.13 / 0.09, other sizes 0.14 / 0.10 / 0.05; fill-selected linked others 0.34 at 10 s (wallet linked 0.64). Signature C (unique value) holds; the edge is not merely the fan-out position. Bid / ask split and a joiner-free rebuilt mid not run (the quiet-book and post-100-ms versions already exclude the concurrent joiner window).'),
 'X136': ('mechanics panel P1 (iter 9): co-receiver maker cascade; event-locked vs leader-locked re-pricing', 'tried',
          'cascade_lock.json (16-22 Oct on chain, 3,674 P4e messages): of 446 messages with a wallet maker re-pricing within 150 ms, any of six fast co-receiver makers signed >= 20 ms before it on 6.1%; vs 0xed446954 (n 21; +18 vs +51 ms) the wallet signs first on 14%, < 20 ms after on 33%, lag corr -0.48 (slope -0.43); its takes vs 0xed446954 first 22%, < 20 ms 41%, corr -0.04; vs 0x2005d16a first 26%, < 20 ms 63%; its lag is the same with (51 ms) and without (53 ms) any leader order. Event-locked (signature if false). R-anchor step not pursued (the latest other-maker add scores 0.47-0.51 vs 0.46 for the mid, iteration-9 information panel); R as the placebo: X135 and the cascade member 0x51dbdd2b (0.49 fill-selected vs the wallet 0.64).'),
 'X137': ('mechanics panel P2 (iter 9): the maker message ledger (V update per message, price gap by order class)', 'tried',
          'message_ledger.json / own_persistence.json (24,180 filled maker orders, 6,628 wallet-independent messages): VALIDATE quiet 70.6% of orders (last print 0.375 / own previous level 0.543 / K - complement 0.315), follow 21.5% (0.166 / 0.404 / 0.186), msg 3.7% (0.167 / 0.451 / 0.104), repair 3.7% (0.077 / 0.321 / 0.114); all 0.305 / 0.500 / 0.271. dV at messages: hurt token median -3c (p10 -10, p90 0; n 588), siblings -3c (349), helped -1c (107), dV = 0 in 4-6%. Own persistence by gap since the previous own order 0-2 s 0.72, 2-10 s 0.59, 10-60 s 0.52, > 60 s 0.23; oracle union of own and last print 0.60. Signature if false: the gap is not localized in the message class and V is not a fixed-step updater.'),
 'X138': ('mechanics panel P3 (iter 9): taker-side knockout and an outcome feasibility bound', 'tried',
          'outcome_bound*.json: VALIDATE (BUILD) Pearson / Spearman vs the wallet per market: real maker + taker legs 0.98 / 0.97; E = engine replay of its maker orders + real taker leg 0.87 / 0.80 (0.89 / 0.68); F = same maker + taker delayed to its block + 1 s 0.43 / 0.39 (0.36 / 0.47), at its own block 0.60 / 0.40 (0.44 / 0.45), + 2c tolerance 0.60 / 0.44 (0.46 / 0.50); G = public ladder D + real taker 0.33 / 0.29; H = D + delayed taker (executable) <= 0.33 / 0.21 (BUILD <= 0.08 / 0.13). Legs correlate -0.87. Signature if false: the outcome item needs the +50-ms take timing (a quantified wall item).'),
 'X139': ('mechanics panel P4 (iter 9): one quote function across all receivers (event feed vs price feed)', 'tried',
          'receiver_icc.json: 501 P4e messages with >= 2 receivers\' FAK BUYs on the same token (1,370 limits; P4e, wallet, 0x2005d16a, trio, 11 group-G members): ICC(1) of premiums over the last print raw 0.15-0.17, after receiver fixed effects 0.43 BUILD / 0.28 VALIDATE / 0.35 pooled (raw limits 0.75-0.77, the shared level); within-message spread median 3c (p90 11-21c), all within 1c on 21-28%. Event feed (<= 0.43 vs >= 0.8 for a price feed): each receiver prices the raw events with its own model.'),
 'X140': ('assumptions panel P1 (iter 9): GRID x tier confound; Feed P coverage of non-GRID tier-1/2 events before h1', 'tried',
          'tier12_listing.json / listing_proj_iter10.parquet (listing projection only): development has no non-GRID tier-1/2 CS2 event; h1 18 and h2 21 non-GRID tier-2 events, all PGL Masters (10-24..10-31; first event on an h2 day, so every h1 event has an earlier PGL Masters event within 72 h); forward IEM (11-02, 4 in the development block 00-06) and BLAST Rivals (11-11), GRID key not yet attached. Analogues: league PGL (tier 4) 9 of 13 traded; non-GRID traded rate falls with tier number (0.91 / 0.51 / 0.06); Dota PARI Universe 3 of 4. Pre-registered treatment B: keep v5 (gp72 decides the stratum by group-P coverage of earlier PGL Masters events, which the examiner counts; v5 ~0.40 at gp72 0, ~0.57 at 1, ~0.66 at 2, thr 0.472). Risk if the wallet trades the stratum without group-P prints: h1 recall ~0.45.'),
 'X141': ('assumptions panel P2 (iter 9): exit band [0.05, 0.95] and the endgame residual as a stop rule; replays on it', 'tried',
          'endgame_stop.json / knockout_band.json: 0 of 24,180 maker orders and 0 of 1,698 taker limits outside [0.05, 0.95] vs 10.0% of public maker BUYs in the same markets (a client constant). Endgame (VALIDATE): last loser fill 0.05 / 0.11 / 0.31, min loser price <= 0.06 in 24% of markets, 4.3% of loser shares at <= 0.10, fills after the loser\'s first public 0.10 in 57% of markets (no early stop). Residual vs PnL 0.44 / 0.42. Band applied to the engine\'s public sets: D 0.245 / 0.087 (0.245 / 0.089 without), B 0.244 / 0.052; returns unchanged. Signature if true fails; the band is kept as a decoded exit component.'),
 'X142': ('assumptions panel P3 (iter 9): item 2 by arithmetic (lift ceilings), resting-order presence, labelled skips', 'tried',
          'lift_ceiling.json: h1 base rate 0.145-0.222 (PGL Masters skipped / traded), lift ceiling 4.5-6.9, precision needed for lift 3 0.43-0.67; h2 0.150-0.247; forward 0.13-0.23: not ceiling-bound, the 20th-percentile threshold kept. Labelled skips: no development-period pause known; the 10-29 one-hour pause cannot remove whole events, so no exclusion. Resting-order presence (step 2) not run: item 2 is carried by selection (VALIDATE 0.970, recall 0.744, lift 3.155); it stays a possible future-block presence label.'),
 'X143': ('assumptions panel P4 (iter 9): point-in-time lead budget of game-state inputs after the publication delay', 'not_applicable',
          'No frozen or candidate rule has a game-state input: X123 (Dota V anchor) failed at the true clock (0.411 vs the last print 0.431), X119 kill locking 13% vs 10%, X125 no CS2 round clock, so there is no rule to re-score at +5 s. The live lead budget (Valve snapshot receive time vs the wallet\'s re-pricing and take) is X118\'s pre-registered test (b) on VALIDATE-live.'),
}
for k, (src, st, ev) in new.items():
    cat[k] = {'status': st, 'source': src, 'evidence': ev}
cat['X48']['evidence'] = cat['X48']['evidence'] + ' | Iteration 10: the key-free relay of Thunderpick\'s in-play odds through bo3.gg\'s live index is recorded as X133 (tommy_tp_odds); the direct bookmaker probes (1win, Stake, Thunderpick pages) still need the user\'s consent.'
cat['X118']['evidence'] = cat['X118']['evidence'] + ' | Iteration 10: X132 (uncensored Dota ladder) folded in: classify the wallet\'s 10-share Dota re-pricing bursts by the preceding Valve snapshot change (own-team kill, other-team kill, fight, objective, none) at receive time, with shifted-clock nulls.'

C = s['components']
C['selection']['description'] = C['selection']['description'] + ' Iteration 10 (X140): the exam lots\' only non-GRID tier-1/2 stratum is PGL Masters (h1 18, h2 21 events; never in development); pre-registered treatment = v5 unchanged, i.e. gp72 decides it by group-P coverage of earlier PGL Masters events (examiner counts them); h1 is not lift-ceiling-bound (base rate 0.145-0.222).'
C['timing']['description'] = C['timing']['description'] + ' Iteration 10 (X136): the maker re-pricing on P4e-alone messages is EVENT-locked (signs before or < 20 ms after the fastest co-receiver maker 0xed446954 on 33% of shared messages, lag corr -0.48; same lag with and without any leader), so it is not a book reaction to a faster maker.'
C['price']['confidence'] = 0.45
C['price']['description'] = C['price']['description'] + ' Iteration 10: the price gap is not localized in message orders (X137: quiet orders, 71% of fills, 0.375 vs the last print / 0.543 vs its own previous level); message phase explains 4% of the offset (X134); receivers share no value beyond the stale print (X139 ICC 0.28-0.43: an event feed); its level is more informative than every subscriber-like maker class (X135: 0.24 vs <= 0.13 at 10 s). Own-state persistence is the best historical anchor (0.500; 0.72 within 2 s of its previous order). All its orders lie in [0.05, 0.95].'
C['exit']['description'] = C['exit']['description'] + ' Iteration 10 (X141): hard client band [0.05, 0.95] (0 of 25,878 orders outside; 10% of public makers\' are); it bids the eventual loser down to the band with no early stop (last loser fill p50 0.11; min <= 0.06 in 24% of markets). The outcome item needs its +50-ms take timing (X138: real taker leg + its maker orders 0.87 / 0.80; taker at its earliest public trace with the oracle maker leg at best 0.60 / 0.44; executable public sets <= 0.33 / 0.21).'

s['strategy_statement'] = s['strategy_statement'] + ' [VALIDATE-only, iteration 10] Exit band: it never bids below 0.05 or above 0.95 (a client constant) and keeps bidding a collapsing team down to that floor. [hypothesis, iteration 10] Its message re-pricing is event-locked on its own feed (not a reaction to faster co-receiver makers), the receivers of the feed share no value beyond the stale print (an event feed priced by each receiver\'s own model), and its add level is more informative than every subscriber-like maker class: the price input is its own valuation. [VALIDATE-only, iteration 10] The per-market outcome needs its +50-ms take timing: with the real taker leg its own maker orders replayed correlate 0.87 / 0.80 with its PnL, with the taker moved to its first public trace at most 0.60 / 0.44.'

s['hypotheses'] += [
 {'id': 'H112', 'family': 'maker timing', 'description': 'The maker re-pricing is leader-locked to a faster co-receiver maker (book reaction) rather than event-locked (X136).',
  'validate_metrics': {'shared_msgs_ed446954': 21, 'wallet_first_share': 0.143, 'lt_20ms_after_leader_share': 0.333, 'lag_corr': -0.479, 'any_leader_20ms_before_share': 0.061},
  'verdict': 'rejected (event-locked; filled-order censoring)'},
 {'id': 'H113', 'family': 'outcome', 'description': 'The outcome item is reachable with the taker leg delayed to its first public trace (X138).',
  'validate_metrics': {'E_real_taker': [0.866, 0.804], 'F_block_plus1s': [0.429, 0.391], 'F_lag0_tol2': [0.596, 0.438], 'H_executable_best': [0.327, 0.206]},
  'verdict': 'rejected: the outcome item needs the +50-ms take timing'},
 {'id': 'H114', 'family': 'price', 'description': 'The price gap is localized in message orders; the ladder between messages is mechanical (fixed-step V updater, X137).',
  'validate_metrics': {'quiet_share': 0.706, 'quiet_last_print': 0.375, 'quiet_own_prev': 0.543, 'msg_last_print': 0.167, 'all_own_prev': 0.5, 'dv_zero_share': [0.039, 0.056]},
  'verdict': 'rejected'},
 {'id': 'H115', 'family': 'price', 'description': 'Message phase / intensity on the feed clock sets the price offset (X134 ceiling).',
  'validate_metrics': {'r2_validate_linear': 0.0433, 'r2_validate_lgbm': 0.0373, 'within_tick': 0.281, 'last_print': 0.306},
  'verdict': 'rejected at the true clock'},
 {'id': 'H116', 'family': 'information', 'description': 'The feed is a fair-price product shared by its receivers (X139).',
  'validate_metrics': {'icc_premium_fe_validate': 0.279, 'icc_premium_fe_build': 0.43, 'icc_raw_limits': 0.745, 'all_within_1c_share': 0.213},
  'verdict': 'rejected (event feed)'},
 {'id': 'H117', 'family': 'price', 'description': 'The wallet\'s level informativeness is only its fan-out position (subscriber makers as informative, X135).',
  'validate_metrics': {'wallet_s10': 0.244, 'wallet_s10_quiet': 0.363, 'size5_s10': 0.101, 'size10_s10': 0.077, 'size20_s10': 0.133},
  'verdict': 'rejected (unique value; BUILD-live)'},
 {'id': 'H118', 'family': 'exit', 'description': 'A hard [0.05, 0.95] band plus an endgame stop drives the per-market residual; band replays track the wallet (X141).',
  'validate_metrics': {'orders_outside_band': 0, 'public_outside_band_share': 0.0999, 'D_band': [0.245, 0.087], 'D_noband': [0.245, 0.089], 'last_loser_fill_p50': 0.11},
  'verdict': 'band decoded; replays not repaired'},
 {'id': 'H119', 'family': 'selection', 'description': 'Non-GRID tier-1/2 events (PGL Masters in h1 / h2) are decided by group-P coverage through v5\'s gp72 (X140).',
  'validate_metrics': {'h1_events': 18, 'h2_events': 21, 'h1_gp72_zero_by_construction': 0, 'v5_at_gp72_0_1_2': [0.40, 0.57, 0.66], 'thr': 0.472},
  'verdict': 'pre-registered (no rule change); untestable on development data'},
 {'id': 'H120', 'family': 'information', 'description': 'An external in-play bookmaker price (Thunderpick via bo3.gg) is the private value (X133).',
  'validate_metrics': {}, 'verdict': 'open: recorder running, tests pre-registered for VALIDATE-live'},
]
s['iterations'].append({'n': 10, 'minutes': 100, 'best_validate_score': 0.8834,
  'paradigm': 'message x token unit on the full on-chain order record (message ledger, cascade lock, receiver ICC) plus taker-side knockouts as an outcome feasibility bound, and a new external in-play price source (Thunderpick odds via bo3.gg) recorded from this iteration',
  'families': ['co-receiver cascade lock test on chain (X136)', 'taker-side knockout / outcome feasibility bound in the validated engine (X138)',
               'maker message ledger by order class, dV per message, own-state persistence (X137)', 'offset vs message phase ceiling (X134)',
               'cross-receiver ICC of take premiums: event vs price feed (X139)', 'subscriber-class maker informativeness on BUILD-live (X135)',
               'listing projection of the GRID x tier stratum; PGL Masters treatment pre-registered (X140)', 'exit band and endgame, band-constrained engine replays (X141)',
               'per-lot lift ceilings (X142)', 'Thunderpick in-play odds recorder via bo3.gg live index (X133)']})
s['live_lab'].append({'what': 'own recorder, feed tommy_tp_odds (code/iter10/tp_odds_recorder.py): bo3.gg live index of current CS2 matches every 3 s (one request covers all live matches; bet_updates = Thunderpick odds, maps score, live_updates), a record per state change, matched to open Polymarket CS2 events by team names, unit-rule filing via code/iter5/unit_writer.py; detached (launcher 21048, worker 31860), hard stop 2026-11-02 06:00 UTC, 150 MB cap',
                      'start': 1793505571, 'end': 1793599200})
s['data_sources'] += ['bo3.gg live index api/v1/matches?filter[matches.status][in]=current&filter[matches.discipline_id][eq]=1 (verified 2026-11-01 03:57 UTC; Thunderpick bet_updates per live CS2 match) -> feed tommy_tp_odds',
                      'Gamma listing projection of CS2 events 10-10..11-04 (slug, scheduled start, lot, league, tier, GRID flag only; fetched without the shared cache) -> .cache/re/tommy-cs2-maker/listing_proj_iter10.parquet']
s['next_steps'] = ['VALIDATE-live (11-01 06-12 and later development blocks): X133 tests (a)-(f) on tommy_tp_odds with the pre-registered verdicts (the new external data class; required pivot).',
                   'X118 Valve tests on tommy_dota_rt with X132 folded in (uncensored Dota ladder classified by the preceding snapshot change, receive-time clock).',
                   'Iteration-8/9 runbooks on VALIDATE-live: finding 14 / 16 repeats with the X135 classes, X121, X98 pool (v4 / v5 / v5b), live price rule.',
                   'If p_TP passes: a receive-time p_TP price rule for the future-block exams and the X138 bound with p_TP as the maker anchor.',
                   'Ask the user: demos (X122 / X37), Dota replays (X129 step 2), PandaScore token (X55), HLTV page checks (X64), stream / chat routes (X4 / X22 / X53), direct bookmaker probes (X48 b), z3 for X96.']
s.setdefault('target_metrics_notes', {})['iteration10'] = ('Rule unchanged (v5): target_metrics are the iteration-9 VALIDATE values. Outcome feasibility (X138): with the real taker leg its own maker orders replayed reach 0.87 / 0.80; '
    'with the taker at its first public trace at most 0.60 / 0.44 (oracle maker leg); executable public sets <= 0.33 / 0.21. Price: best historical own-state anchor 0.500 (previous own level), public 0.305.')
s['status'] = 'continue'
s['wall_reason'] = None
s['updated'] = int(time.time())
json.dump(s, open(P, 'w', encoding='utf-8'), indent=1)
op = sorted([k for k, v in s['catalog'].items() if v.get('status') == 'open'], key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0))
print('catalog', len(s['catalog']), 'open', len(op), op)
