"""Iteration 14: catalog X189-X203, components, statement, hypotheses and the iteration entry -> results/iter14_extra.json
(read by write_state14.py)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
WS = ROOT / "research/reverse_engineering/tommy-cs2-maker"
RES = WS / "results"
S = json.load(open(WS / "state.json"))
MIN = float(sys.argv[1]) if len(sys.argv) > 1 else 95.0


def rj(n):
    p = RES / n
    return json.load(open(p)) if p.exists() else {}


lag, trs, trb, pg, mp, e3, st = (rj("lag_tolerance.json"), rj("event_transport_sign.json"), rj("event_transport_block.json"),
                                 rj("phase_gated_ladder.json"), rj("message_profile.json"), rj("e3_screen.json"), rj("sports_twin.json"))
P13 = "panel iteration 13"
cat = {}


def put(k, status, source, ev):
    cat[k] = {"status": status, "source": source, "evidence": ev}


put("X189", "open", P13 + " information P1: round-END clock on the feed's time, then V as a side / economy-aware score table",
    "First pass, step 1 on the feed's own clock (code/iter14/message_profile.py, results/message_profile.json): 2,111 informed take clusters (>= 2 group-P / G takers within 300 ms, wallet-free txs). "
    f"Its value steps at the message: BUILD 57% / VALIDATE 42% of its 60-s signed move in (-1, +3] s, 3.5% / 25% before (the print shows the same pre-trend on VALIDATE); V - P +1.72 / +0.79c at +2 s, ~0 by +60 s; the print reacts at +3..+5 s. "
    "Steps 2-5 (bo3 alignment of the clusters, union-top uncensoring, table fit on the clock, opener / plant regressions on clock rounds) not run.")
put("X190", "open", P13 + " information P2: point-in-time round-end signal from public prints as the price rule's score clock",
    "E3-1 screen (results/e3_screen.json): public print events (I3 >= 2c clean-print jumps, I4 3-sigma jumps, I5 other-book jumps, I6 first print after silence) follow its re-pricing decisions "
    "(shape peaks at -2.5..-5 s, decisions BEFORE the public event; no link at +-2 s for I3 / I4 / I5), while its decisions follow the informed takers' signatures by +0.4-0.6 s. With X201 (a value lagged by 0.25 s keeps 0.355 of the set unit, 0.215 on V-change bursts) "
    "a public round-end signal that arrives 2-5 s after the feed cannot carry the price item; iteration 9's LightGBM with group-P / G take features scored 0.285 vs the print's 0.298. Signature (>= 0.40 on burst tops) not reachable; the score-table step (V_hat = table(score_pub)) not built.")
put("X191", "open", P13 + " information P3: LoL natural experiment without the lolesports key (Leaguepedia RiotGameId + Riot livestats)", "Not run in iteration 14.")
put("X192", "tried", P13 + " information P4: feed-state synchrony across concurrent events (E7) as a presence input",
    "E7 on out-of-fold BUILD presence misses (results/e2_residuals.json): ratio 0.63 / 0.70 / 0.99 at 0.5 / 2 / 10 s (p 0.87 / 0.99 / 0.54), all signings 0.81 at 2 s (p 1.00): no cross-event synchrony, so the step-3 feed-state feature is not built (the proposal's 'if false' branch: presence is per-market).")
put("X193", "open", P13 + " information P5: pure-Python CS2 demo game-event extractor so the demo test needs one consent", "Not written in iteration 14; the download still needs the user's consent (X37 / X122).")
if st:
    pv = st.get("price_vs_last_print", {})
    ml = rj("mlb_twin.json")
    put("X194", "tried", P13 + " mechanics P1: the operator's in-play sports quoting as a public-input twin of V",
        f"First pass, steps 1-2 and a first step-4 check (code/iter14/sports_twin.py, results/sports_twin.json): 0x52661b8e's September sport trades {st.get('sport_trades')} in {st.get('events')} events, {st.get('decoded_txs')} txs decoded; "
        f"orders maker {st.get('orders', {}).get('maker')} / taker {st.get('orders', {}).get('taker')}; maker fingerprint {json.dumps(st.get('maker_fingerprint', {}))[:300]}; bursts {json.dumps(st.get('maker_bursts', {}))[:250]}; "
        f"price vs last print on {pv.get('markets')} markets: within one tick {pv.get('within_tick')}, median offset {pv.get('median_offset_c')}c, by group {json.dumps(pv.get('by_group', {}))[:300]}. MLB (code/iter14/mlb_twin.py, results/mlb_twin.json): {ml.get('games_with_takes')} games / {ml.get('takes')} takes against statsapi play ends: p_link +-10 s {ml.get('plays_pm10s', {}).get('p_link')}, +-60 s {ml.get('plays_pm60s', {}).get('p_link')}; scoring plays +-60 s {ml.get('scoring_pm60s', {}).get('p_link')}, +-600 s {ml.get('scoring_pm600s', {}).get('p_link')} (shape peak {ml.get('scoring_pm600s', {}).get('shape_peak_lag_s')} s: it buys the team that scores about 2 min before the run); on-base plays (1,793) +-10 s {ml.get('onbase_pm10s', {}).get('p_link')}, +-60 s {ml.get('onbase_pm60s', {}).get('p_link')}. "
            "No fixed-lag play reaction: the sports account is a slower state-based BUY taker, not the push-feed ladder maker (the panel's if-false branch: the feed is an esports product). Football (ESPN key events), the public in-play model fit and co-receivers not run.")
else:
    put("X194", "open", P13 + " mechanics P1: the operator's in-play sports quoting as a public-input twin of V", "Calldata of 1,326 September sport txs decoded (sib5266_sport); analysis not finished in iteration 14.")
put("X195", "open", P13 + " mechanics P2: a wallet-independent true round clock, then the kill-state vs early-result test",
    "First pass with the feed's own messages as the clock (X189 step 1, results/message_profile.json): no pre-message ramp of V beyond the print's own (K reading unsupported in this unit); its move is a step at the message. "
    "Clock first pass (code/iter14/round_clock.py, results/round_clock_clusters_*.json): bo3 durations snapped to winner-direction informed clusters in [-15, +30] s: 286 snaps vs 206 with the winner sequence reversed (1.39x; weak clock); on 61 rounds with both ends snapped its winner-signed change mid-round -0.47c, at the message +2.84c (mid-round AUC 0.537 vs print 0.569); single-take anchors (results/round_clock_takes_*.json): 515 vs 383 snaps (1.34x), 141 rounds, mid-round +2.11c (VALIDATE +3.02c), at the message +2.14c, mid AUC 0.638 vs 0.605: the R-vs-K split depends on the anchor set, and no public anchor set is a reliable clock (1.3-1.45x over the reversed sequence). Print-anchored variant (results/round_clock_print_15_30.json): 875 vs 673 snaps (1.30x), 412 rounds; its value moves +2.85c mid-round and +1.55c late before the print jump (mid AUC 0.675 vs 0.606): the 10-45 s lead. Survivor gradient and a better anchor set (co-receiver maker clusters, all books) not run.")
jt = rj("july_twosided.json")
put("X196", "tried", P13 + " mechanics P3: the operator's July-September versions, two-sided quotes as an uncensored V",
    f"First pass (code/iter14/july_twosided.py, results/july_twosided.json): 0x52661b8e July CS2 / August Dota, {jt.get('txs_sampled')} txs decoded, {jt.get('maker_orders')} maker orders (BUY {jt.get('maker_buy_share')}): within one tick of the last print "
    f"{jt.get('maker_vs_last_print', {}).get('within_tick')} with offsets BUY {jt.get('maker_vs_last_print', {}).get('median_offset_buy_c')}c / SELL {jt.get('maker_vs_last_print', {}).get('median_offset_sell_c')}c: a print-pegged two-sided quote. "
    "Activity by day: two-sided without merges through 09-02, silent 09-03..09-16, BUY-only + MERGE from 09-17 (0x7d67f01d from 09-21): the private-value design arrives as a step after a two-week pause (change point 09-03..09-17). "
    "Same-token bid / ask pairs within 2 s: 1 (the uncensored-mid test needs a longer pairing window); the weekly in-round AUC and co-signing-lag dating (steps 3-5) not run.")
put("X197", "open", P13 + " mechanics P4: uncensor V with price-time priority (every public trade bounds its quote)", "Steps 1 + 4 simplified (code/iter14/pt_bounds.py, results/pt_bounds.json): 75,236 upper bounds from wallet-free sweeps of bids in 220 markets vs 24,180 exact own levels (3.1x); with a next own level within 60 s the bound is 0-1c above it in 26.0% (exact 15.1%; the panel bar of >= 30% narrowly fails), below it in 27%; previous own level > 1c above the swept level in 16.2% (order gone). Steps 2 (censored fit of V) and 3 (in-round timing at bound resolution) not run.")
if trs:
    v = trs["VALIDATE"]
    put("X198", "tried", P13 + " mechanics P5: examinable historical price rule, one event value through the series map, the complement and the slots",
        f"code/iter14/event_transport.py, results/event_transport_{{sign,block}}.json: K 0.97, BETA (map -> match) {trs['BETA_build']} on BUILD. VALIDATE within one tick, own knowledge at signing: per-token persistence {v['P_tok']['within_tick_all']}, complement transport {v['T_book0']['within_tick_all']}, "
        f"map <-> match transport {v['T_event0']['within_tick_all']}, -1c slot shift {v['T_book1']['within_tick_all']}; public at block time (fills on chain before signing): {trb['VALIDATE']['P_tok']['within_tick_all']} / {trb['VALIDATE']['T_book0']['within_tick_all']} (last print 0.305-0.322). "
        "Signature >= 0.60 fails: its value moves between its own fills on all books at once; own-state ceiling ~0.44.")
put("X199", "open", P13 + " assumptions P1: V as a kill-state model on a latent per-round kill-order lattice", "Not run in iteration 14 (finding 5: V steps at the feed's messages with no private pre-message ramp, which a lattice fit on print-inferred rounds cannot resolve).")
put("X200", "ruled_out", P13 + " assumptions P2: V as a per-book delta integrator with re-anchoring",
    "Measured: the match book moves 0.57 x the map move for map moves >= 3c (mechanics panel iter-13, 32 pairs; slope 1.05 on s x dV_map) and BETA (consecutive co-repricings) 0.46 on BUILD (X198): a series map of one map value, not equal cents per message (the integrator signature 'ratio ~1 at every horizon' fails at the same-tick horizon once the 1-cent tick is removed).")
if lag:
    put("X201", "tried", P13 + " assumptions P3: lag tolerance of the price item before relying on any delayed public source",
        "code/iter14/lag_tolerance.py, results/lag_tolerance.json (BUILD-live, frozen X163 machine): set unit at L = 0+ / 0.25 / 1 / 4 s = "
        f"{lag['L_0.001s']['all']['set_unit']} / {lag['L_0.25s']['all']['set_unit']} / {lag['L_1s']['all']['set_unit']} / {lag['L_4s']['all']['set_unit']} (oracle {lag['oracle_L0_V_after']['all']['set_unit']}, others' best bid now {lag['public_J']['all']['set_unit']}); "
        f"V-change bursts ({lag['class_share_orders'].get('V_change')} of orders, {lag['class_share_filled'].get('V_change')} of filled orders) {lag['L_0.001s']['V_change']['set_unit']} at 0+; refills {lag['L_0.001s']['refill_same_V']['set_unit']} -> {lag['L_4s']['refill_same_V']['set_unit']} at 4 s. "
        "'If true' signature holds: delayed public sources cannot carry the price item. Dota leg not covered (no Dota adds in BUILD-live).")
if pg:
    vc = pg["VALIDATE_chosen"]
    put("X202", "tried", P13 + " assumptions P4: a round-phase-gated public ladder for the outcome item",
        f"code/iter14/phase_gated_ladder.py, results/phase_gated_ladder.json (validated X57 engine): BUILD-chosen {pg['chosen_on_BUILD']}; VALIDATE per-market Pearson / Spearman {vc['pnl_vs_wallet'][0]} / {vc['pnl_vs_wallet'][1]} (return {vc['return']}, {vc['pnl_vs_wallet'][2]} markets); halves {pg['VALIDATE_chosen_halves']}; "
        "every gated variant <= 0.35 / 0.12 with returns -5.5%..+2.0%; the continuous five-slot ladder 0.315 / 0.238. Fails (< 0.5): the outcome item stays gated by its value.")
put("X203", "tried", P13 + " assumptions P5: find the operator's other processes by key fingerprint (7702 delegate 0x63c0c19a), funding and names",
    "Steps 1 and 4 (code/iter14/owner_census.py, owner_census_cosign.py; results/owner_census*.json; chain state at latest, read-only): all 499 sigType-3 addresses with >= 50 orders in the decoded calldata are factory proxies (125- or 146-byte); owners 472 EOAs, 19 delegate to 0x63c0c19a (the four known operator owners included, 0x116342d6 too), 8 to other delegates. "
    "Behaviour: 0x10d79cc7 (890 CS2 orders 09-24..10-16, BUY-only whole-cent 20-share maker) 7 orders within 0-5 ms of an operator order vs 5 in 5-50 ms (12.6x per ms); 0xd2bb9459 (372 CS2 orders 10-12..10-16, BUY-only maker, 100-200 shares) 16 vs 16 (9.0x); the other 13 show no excess; no taker-only account at feed speed (0xaadb0195 +1.76 s behind P4e). "
    "So >= 6 operator accounts, all CS2 here (no LoL / GRID window). Steps 2 (USDC funding links) and 3 (profile names) not run.")

e3s = ""
if e3:
    sv = e3.get("survivors", [])
    conf = [r for r in e3.get("validate", []) if r.get("confirmed_alpha_0.01")]
    e3s = (f"BUILD survivors {len(sv)} of {len(e3['build']['rows'])} rows; VALIDATE confirmed {len(conf)}: "
           + "; ".join(f"{r['name']} {r['range']} peak {r.get('shape_peak_lag_s')} s p_link {r['p_link']:.2g} signed {r.get('signed_p_link')}" for r in conf)[:900])

e6 = rj("e6_latent.json")
put("E4", "tried", "BRIEF 11-01", "Discrepancy / composite indicators: legacy bookmaker line minus print (X172 Dota: no closer than the print), MR12 / side-aware tables minus print (X171, X181 step 4: no closer), Dota game-state fair value (X123); iteration 14: other-book (map <-> match) jumps as a divergence event (E3-1 I5: follows its decisions by 3.5-5 s) and the map -> match series map of its own value (slope 0.46, X198). No discrepancy indicator leads its decisions.")
put("E6", "tried", "BRIEF 11-01", f"First form (code/iter14/e6_latent.py, results/e6_latent.json): latent = push-feed message intensity proxied point in time by group-P wallet-free takes on the event; VALIDATE incremental_auc over co-occurrence +{e6.get('over_cooccurrence_B0', {}).get('gain', 0):.4f} (CI {e6.get('over_cooccurrence_B0', {}).get('gain_ci95')}), over co-occurrence + self-excitation +{e6.get('over_B0_plus_self_excitation', {}).get('gain', 0):.4f}: nothing beyond its own past. Event study of the proxy against its decisions: E3-1 (I1 / I2 lead its re-pricings by 0.4-1.5 s; public series follow them). Legacy latent fits: X171, X181.")
comp = S["components"]
comp["price"]["description"] += (" Iteration 14: the price item tolerates no input lag (X201: a value lagged 0.25 s keeps 0.355 of the set unit, 4 s 0.293; 90% of filled orders are V-change bursts, 0.20-0.23 at any lag); "
                                 "own state transported over the complement and the series map reaches 0.44 (X198; 0.26-0.27 when only on-chain-public own fills are used); on the feed's own clock its value steps at the informed messages (57% / 42% of the 60-s move in (-1, +3] s) with no private pre-message ramp, and the clean print reacts 2-5 s later (X189 first pass). V = map value written into the match book through a series map (slope 0.46).")
comp["timing"]["description"] += (" Iteration 14 (E3-1, pre-registered, BH on BUILD, VALIDATE confirmation): its maker re-pricing decisions follow the informed takers' signatures (peak +0.4-0.6 s, sign-concordant) and precede public print events by 2.5-5 s; no cross-event synchrony of the unexplained decisions (E7).")
comp["exit"]["description"] += (" Iteration 14 (X202): a round-phase-gated public ladder does not earn the wallet's per-market PnL profile (VALIDATE 0.25 / 0.05).")
comp["timing"]["confidence"] = 0.68
comp["price"]["confidence"] = 0.58
stmt = S["strategy_statement"]
stmt += (" [hypothesis, iteration 14] The private part of V is the push feed's message stream priced at the message: on the feed's clock (informed take clusters) its value steps within 0-3 s and is flat before, the market follows 2-5 s later on those messages "
         "(10-45 s on average); a value lagged by even 0.25 s loses the price item (X201), so only the feed itself, not a delayed public source, can carry it.")
hyp = [
    {"id": "H146", "family": "price", "description": "A delayed public in-play state (stream, Valve 4-s, HLTV) can carry the price item.", "validate_metrics": {"set_unit_L0.25": lag.get("L_0.25s", {}).get("all", {}).get("set_unit"), "set_unit_L4": lag.get("L_4s", {}).get("all", {}).get("set_unit")}, "verdict": "rejected (BUILD-live, X201)"},
    {"id": "H147", "family": "price", "description": "Own state transported across the complement and the series map gives the next order (>= 0.60).", "validate_metrics": {"T_book_sign": trs.get("VALIDATE", {}).get("T_book0", {}).get("within_tick_all"), "P_tok_sign": trs.get("VALIDATE", {}).get("P_tok", {}).get("within_tick_all")}, "verdict": "rejected (0.44)"},
    {"id": "H148", "family": "outcome", "description": "A round-phase-gated public ladder reproduces the wallet's per-market PnL (>= 0.5).", "validate_metrics": {"pearson_spearman": pg.get("VALIDATE_chosen", {}).get("pnl_vs_wallet")}, "verdict": "rejected"},
    {"id": "H149", "family": "presence", "description": "A common cross-event driver (E7) explains presence misses.", "validate_metrics": {"ratio_2s": 0.70, "p": 0.99}, "verdict": "rejected (BUILD)"},
    {"id": "H150", "family": "price", "description": "V builds a private in-round state before the feed's messages (K).", "validate_metrics": {"V_share_before_msg_build": mp.get("BUILD", {}).get("V_share_before_-1s"), "V_share_before_msg_val": mp.get("VALIDATE", {}).get("V_share_before_-1s")}, "verdict": "open: no pre-message ramp in the message-locked profile, but mid-round moves appear on a single-take clock (VALIDATE); no reliable public round clock"},
    {"id": "H151", "family": "timing", "description": "Its re-pricings follow the push feed's messages and precede the public print (E3-1).", "validate_metrics": {"e3": e3s[:300]}, "verdict": "supported (BUILD screen; VALIDATE confirmation in e3_screen.json)"},
]
nxt = ["X194 steps 3-5: the operator's football / MLB quoting against ESPN key events and MLB statsapi playEvents (event study, public in-play model, co-receivers).",
       "X189 steps 2-5 / X195: align the informed-cluster clock to bo3 rounds (winner direction, durations); regress V's steps at clock round ends on opener / plant / alive_time; union-top uncensoring.",
       "X203 owner census by the 7702 delegate; X196 July-September versions; X197 price-time bounds; X191 LoL; X199 kill lattice.",
       "E4 composite event indicators, E5 news / social for selection, E6 latent fit with incremental_auc over co-occurrence + self-excitation baselines.",
       "VALIDATE-live: no wallet record in 11-01 06-12 (bca-pha still untraded at 11:56 UTC); the next development blocks fall after the budget."]
it = {"n": 14, "minutes": MIN, "best_validate_score": 0.8834, "status": "continue",
      "paradigm": "brief-11-01 hidden-dimension pass (E1 inventory, E2 out-of-fold residual shape, E7 synchrony, E3 pre-registered event-state screen) plus the feed's own clock as the unit (message-locked value paths), the lag tolerance of the price item, own-state transport, a phase-gated public ladder, and the operator's sports quoting as a new data source",
      "families": ["E1 dimension inventory (37 dimensions)", "E2 out-of-fold BUILD residuals (GroupKFold 2-h blocks)", "E7 residual_clustering across events", "E3-1 event-state screen with BH (informed takes, clusters, print jumps, other-book jumps, silence)",
                   "message-locked value / print profiles on informed clusters (X189 / X195 first pass)", "lag tolerance of the ladder machine (X201)", "feed-message and print-anchored round clocks from bo3 durations (X195 first pass)", "price-time priority bounds of its quote (X197 steps 1 + 4)", "E7 power statement", "E6 latent with incremental_auc over co-occurrence + self-excitation", "two-sided July-August quotes and the 09-17 change point (X196)", "7702-delegate owner census with co-signing confirmation (X203)", "MLB statsapi event study of the sports account (X194)", "own-state transport across complement and series map (X198)",
                   "round-phase-gated public ladder in the X57 engine (X202)", "operator's September sports quoting: calldata, fingerprint, price vs print (X194 first pass)", "delta integrator ruled out by measurement (X200)", "legacy indicator ledger (31 rows)"]}
out = {"catalog": cat, "components": comp, "strategy_statement": stmt, "hypotheses": hyp, "next_steps": nxt, "iteration": it, "e3_summary": e3s}
(RES / "iter14_extra.json").write_text(json.dumps(out, indent=1))
print("ok", len(cat), e3s[:400])
