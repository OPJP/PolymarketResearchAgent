"""Iteration 12 state.json update: panel proposals X158-X171 into the catalog with this iteration's evidence, components,
strategy statement, hypotheses, live lab, data sources, iteration entry, next steps (target metrics unchanged: v5)."""
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
WS = ROOT / "research/reverse_engineering/tommy-cs2-maker"
RES = WS / "results"
MINUTES = int(os.environ.get("IT12_MINUTES", "0"))


def rj(n):
    p = RES / n
    return json.load(open(p, encoding="utf-8")) if p.exists() else None


S = json.load(open(WS / "state.json", encoding="utf-8"))
cat = S["catalog"]
rm, lm, sr, pb, tg = rj("round_markov_fit.json"), rj("ladder_machine.json"), rj("stale_remainder_absent.json"), rj("pit_partial_book.json"), rj("take_gap.json")
la, wd, ln, di, re_ = rj("loop_attribution_all.json"), rj("withdrawals.json"), rj("lineage.json"), rj("dota_inverse_fit.json"), rj("round_econ.json")

A = rm["all"]
x171 = (f"round_markov_fit.json (code/iter12/round_markov_fit.py; pre-registered in NOTES iteration 12): clock-free hidden-Markov fit (Viterbi over the round index, MR12 / MR3 table at a constant round-win probability, per-token offsets, 2 Viterbi-EM passes) of its filled maker bursts on {rm['maps']} CS2 map markets of 16-22 Oct ({rm.get('maps_skipped_team_names', 0)} dropped for unmatched bo3 team names), true bo3 winner sequence vs {rm['n_perm']} permutations with the same final score, the last public print as control. "
        f"Median over maps: rank of the true sequence {A['rank_v_median']:.3f} (V) vs {A['rank_p_median']:.3f} (print); residual SD {A['sig_v_median']*100:.2f}c vs {A['sig_p_median']*100:.2f}c (V smaller on {A['share_maps_sig_v_lt_sig_p']:.0%} of maps); first burst after inferred round ends {A['freeze_sd_v_median']*100:.2f}c vs {A['freeze_sd_p_median']*100:.2f}c. "
        f"BUILD {rm['build']['sig_v_median']*100:.2f}c vs {rm['build']['sig_p_median']*100:.2f}c, VALIDATE {rm['validate']['sig_v_median']*100:.2f}c vs {rm['validate']['sig_p_median']*100:.2f}c. Pre-registered verdict: {rm['verdict']}. Its levels sit no closer to a round-score Markov valuation than the print does (E1a in constant-p form fails).")
lmv = lm["V_after"]
x163 = (f"ladder_machine.json (code/iter12/ladder_machine.py, frozen constants: burst 20 ms, depth 5 slots, band [0.05, 0.95]; BUILD-live V-relative rows of the mechanics panel, {lm['adds']} validated adds in {lm['bursts']} bursts): with V = its own top after the burst (oracle) the machine 'n adds take the n highest free whole-cent slots under V, top-first' scores set unit {lmv['set_unit']}, per order without rank {lmv['per_order_no_rank']}, whole burst {lmv['per_burst']}; by class "
        + ", ".join(f"{k} {v[0]} (n {v[1]})" for k, v in lmv["set_unit_by_class"].items())
        + f"; V error -2/-1/+1/+2c: {lm['V_error_curve']['-2c']} / {lm['V_error_curve']['-1c']} / {lm['V_error_curve']['+1c']} / {lm['V_error_curve']['+2c']}; a 1.5-s cooldown on vacated slots lowers it ({lm['V_after_cooldown']['set_unit']}); public proxies through the machine: others' best {lm['proxy_J']['set_unit']} (per order {lm['proxy_J']['per_order_no_rank']}), J + 1c {lm['proxy_J_plus_1c']['set_unit']}, own top before {lm['proxy_own_top_before']['set_unit']}. "
        f"Same-V residual adds spread over slots 0..-5 ({lm['same_V_class']['slot_dist']}), {lm['same_V_class']['share_at_recently_vacated_price']:.1%} at a recently vacated price. Corrects iteration-11 finding 3: the price item fails because V is private, not because of the ladder. VALIDATE-live scoring and the set-unit question to the user remain.")
pr = sr["panel_signature_rows"]
x169 = (f"stale_remainder_absent.json (code/iter12/stale_remainder_absent.py; the iteration-5 census, {sr['bursts']} informed bursts, {sr['label_n']}): later BUY takers matched in (m, m + 4 s] after the leader's match m = sign + 1,040 ms, maker legs at an effective price <= the leader's limit. Wallet-absent bursts: share with any such non-wallet consumption per 1-s bin "
        + " / ".join(str(sr["all"]["wallet-absent"][f"later_m+{i}-{i+1}s_share_any_nonwallet"]) for i in range(4))
        + ", mean shares " + " / ".join(str(sr["all"]["wallet-absent"][f"later_m+{i}-{i+1}s_mean_nonwallet_shares"]) for i in range(4))
        + "; matched by move10, wallet-absent at m+2-3 s vs the wallet's own take at <= L in present bursts: "
        + "; ".join(f"{r['move10']}: {r['absent_later_m+2-3s_mean']} vs {r['present_wallet_take_le_L_mean']}" for r in pr)
        + " shares. The T_hi signature (>= 50% survives) fails: the stale remainder is gone by the match even without the wallet; the outcome latency bound (T_lo world) stands on a natural experiment.")
V12 = pb["VALIDATE"]
x165 = (f"pit_partial_book.json (code/iter12/pit_partial_book.py): point-in-time partial-fill book (other makers' BUY orders partly filled at or before t - 2 s, below size, age cutoff since the last fill). VALIDATE coverage / within one tick on covered rows: "
        + "; ".join(f"{a} s {V12[f'age{a}']['coverage']} / {V12[f'age{a}']['bid_within_tick_covered']}" for a in (10, 30, 60, 120, 300))
        + f"; with the last print as fallback {pb['chosen_on_BUILD']['VALIDATE_bid_fallback']} vs last print {pb['chosen_on_BUILD']['VALIDATE_last_print']} (age chosen on BUILD {pb['chosen_on_BUILD']['bid_age']} s; gain {pb['VALIDATE_gain_bid_fallback']['gain']} {pb['VALIDATE_gain_bid_fallback']['ci95']}); not frozen (bar +0.05). Steps 2-3 (followers, queue-inversion latency) not run.")
x170 = (f"take_gap.json (code/iter12/take_gap.py; BUILD-live raw book, {tg['takes']} takes, {tg['untriggered']} untriggered own bursts): gap = own top on the bought token 1.5 s after minus others' best ask before: AUC {tg['gap']['auc_raw']} (n {tg['gap']['n']}, takes {tg['gap']['takes']}, permutation p {tg['gap']['perm_p']}; takes median {tg['gap']['by_class']['1']['50%']}c, untriggered {tg['gap']['by_class']['0']['50%']}c); "
        f"leave-one-event-out logistic with |dV| and ask depth {tg.get('logit_loeo', {}).get('auc')}; complement form AUC {tg['gap_comp']['auc_raw']} (inflated by the K - limit repair); premium vs gap Spearman {tg.get('premium_vs_gap_spearman')}. Partly supported: takes happen when its revealed value reaches the stale ask, but no sharp threshold (< 0.85 on the non-circular form).")
att = la["attribution"]
x158 = (f"loop_attribution_all.json / loop_attribution.json (code/iter12/loop_attribution.py; BUILD-live server clock, P = 504 ms, +-15 ms, uniform {la['uniform_rate']}): on-tick rates "
        + ", ".join(f"{k} {v[0]} (n {v[1]})" for k, v in la["on_tick_rate"].items())
        + f", takes {la['takes_on_tick'][0]} (n {la['takes_on_tick'][1]}). Attribution over all own bursts: off-tick bursts follow a same-book non-own change within 40 ms in {att['off_tick_own']['same_lag_le_40ms']} (control ticks {att['off_tick_control']['same_lag_le_40ms']}, median lag {att['off_tick_own']['same_lag_median_ms']} ms): event-driven; on-tick bursts {att['on_tick_own']['same_lag_le_40ms']} vs {att['on_tick_control']['same_lag_le_40ms']} within 40 ms, any same-book change in the previous tick {att['on_tick_own']['same_any_in_tick']} vs {att['on_tick_control']['same_any_in_tick']}, sibling books {att['on_tick_own']['sib_any_in_tick']} vs {att['on_tick_control']['sib_any_in_tick']}; the excess sits 250-504 ms before the tick. "
        "The quiet class is sampled on the loop; at most ~14 points of on-tick re-pricings follow public book changes: branch (a) fails. Steps 3-5 (sign runs, step sizes, off-tick message counts vs bo3 kills, tick-sampled follower) not run; replicate on VALIDATE-live.")
x159 = (f"Steps 1-2 on BUILD-live (withdrawals.json, code/iter12/withdrawals.py; {wd['events']} events, occupancy over its traded books of each event): {wd['episodes_ge_2ticks']} event-wide withdrawals of >= 2 ticks, duration quantiles (s) {wd['dur_quantiles_s']}; exactly three ticks {wd['share_3ticks_pm60ms']}, >= 3 s {wd['share_ge_3s']}, >= 10 s {wd['share_ge_10s']}; within 2 s after its own take {wd['share_start_within_2s_after_own_take']}. "
        "Across episodes the match market's print moves a median 1.0c (control 0.0c; 22% >= 3c), prints 3-20x denser than control: variable-length, event-locked withdrawals (E4-like or a round-boundary own policy), not the 3-tick repair. Step 3 (coincidence with Thunderpick suspensions) and step 4 need development records of matched in-play matches (none yet).")
x166 = (f"lineage.json (code/iter12/lineage.py): deposit wallet deployed at block {ln['deploy_block']} (ts {ln['deploy_ts']} = 06-16 13:00 UTC, 5.5 h before its first trade) by relayer {ln['deploy_txs'][0]['from'] if ln.get('deploy_txs') else '?'} through factory 0x00000000000fb5c9adea0298d729a0cb3823cc07 (selector 0x77835641); ERC-1967 proxy with immutable args (factory, owner). Owner 0x8af810f0: EIP-7702 account delegated to 0x63c0c19a282a1b52b07dd5a65b58948a07dae32b, nonce {ln['owner_nonce']}; its Polymarket Safe {ln['owner_safe']} never deployed; no Polymarket activity for the owner or that Safe: no predecessor under the owner key. "
        "First June funding infeasible key-free: drpc 'ranges over 10000 blocks are not supported on free plan' (archive-depth logs), publicnode 'Archive requests require a personal token', 1rpc.io '50 blocks range' / 'Too Many Requests', polygon.blockscout.com HTTP 403. October logs readable (verified).")
dt = di["clock_true"]
x167 = (f"Step 1 (historical) dota_inverse_fit.json (code/iter12/dota_inverse_fit.py; {di['orders']} filled maker orders on {di['maps']} Dota maps, clock from P4e's takes, state at tau - 5 s): inverse fit on oriented gold / xp / kill leads, minute and the pre-game prior, leave one map out: within one tick {dt['logistic_ls']['within_tick']} (logistic LS, MAE {dt['logistic_ls']['mae_c']}c) / {dt['lgbm']['within_tick']} (LightGBM, MAE {dt['lgbm']['mae_c']}c) at the true clock vs {di['clock_m300']['logistic_ls']['within_tick']} / {di['clock_p300']['logistic_ls']['within_tick']} at -/+300 s and the last print {di['last_print']['within_tick']} (MAE {di['last_print']['mae_c']}c); last print + model change {dt['lp_plus_dmodel']['within_tick']} (placebos {di['clock_m300']['lp_plus_dmodel']['within_tick']} / {di['clock_p300']['lp_plus_dmodel']['within_tick']}). "
        "Public per-minute state carries the coarse level only. Step 2 (Valve live state at receive time, tommy_dota_rt) waits for development blocks with Dota in play.")
x160 = ""
if re_:
    ov = re_.get("offset_vs_print", {}); oc = re_.get("offset_vs_print_ctrl_prev_rounds", {})
    x160 = (f"Clock-free form of steps 4-5 (round_econ.json, code/iter12/round_econ.py; first burst after each round end inferred by the X171 fit, bo3 round economy of the new round): residual vs table ~ equipment difference Spearman {re_['res_v']['spearman_eq']} {re_['res_v']['ci95']} (V) vs {re_['res_p']['spearman_eq']} {re_['res_p']['ci95']} (print); its level minus the last print ~ equipment difference: Spearman {ov.get('spearman_eq_tokdemeaned')}, OLS {ov.get('ols_eq_coef_c_per_1k')}c per $1k (t {ov.get('ols_eq_t')}); "
            f"controlling the previous rounds' winners and the score: {oc.get('eq_coef_c_per_1k')}c per $1k (t {oc.get('eq_t')}), previous-round winner {oc.get('prevA_coef_c')}c (t {oc.get('prevA_t')}); "
            + "; ".join(f"{k}: {re_[k]['eq_coef_c_per_1k']}c per $1k (t {re_[k]['eq_t']})" for k in ("offset_vs_print_prev_A_won", "offset_vs_print_prev_A_lost") if k in re_)
            + ". Steps 1-3 (pause-aware DP clock on public jumps, causal round starts) and step 6 (anchor rule) not run.")

new_items = {
    "X158": ("information panel P1 (iter 11): the 504-ms loop as the decision clock; tick-level attribution of what moves V", "tried", x158),
    "X159": ("information panel P2 (iter 11): suspension fingerprint for E4 independent of Thunderpick's level", "open", x159),
    "X160": ("information panel P3 (iter 11): historical in-round clock and economy from bo3 with a pause-aware DP", "open", x160),
    "X161": ("information panel P4 (iter 11): Azuro on chain as a historical in-play line", "open",
             "Not run in iteration 12. Feasibility checked: October Polygon logs are readable key-free (publicnode, drpc, verified); the obstacle is mapping Azuro conditions to CS2 games without its API / subgraph (X41: DNS / 404), i.e. ConditionCreated -> gameId -> LP NewGame ipfsHash -> IPFS team names. Planned with the contract addresses read as text from Azuro's toolkit package."),
    "X162": ("information panel P5 (iter 11): Kick stream clock from IVS playlist PROGRAM-DATE-TIME and a dose-response test", "open",
             "Recorder started (code/iter12/kick_pdt_recorder.py, feed tommy_kick_pdt, launcher 8260 / worker 16248, 11-01 07:51 UTC, hard stop 11-03 00:00 UTC, 50 MB): Kick channel API key-free (verified 200, IVS playback URL present offline), IVS playlists as text, no segments. Dose-response analysis waits for >= 15 recorded development events (first non-GRID Kick event of a development block: cs2-bca-pha 11-01 11:00 UTC)."),
    "X163": ("mechanics panel P1 (iter 11): V-plus-ladder-machine price decode, the unchanged-V class, the burst-set unit", "tried", x163),
    "X164": ("mechanics panel P2 (iter 11): point-in-time round-score clock from the same map's totals / handicap books", "open",
             "Not run in iteration 12: BUILD-live holds 24 minutes of tommy_cs2_rounds records; the development matches of 11-01 06-12 start at 09:00 UTC, after this iteration. Planned on VALIDATE-live blocks (detector, bo3 validation, V_markov; note X171: V is not a constant-p round table, so step 4 tests the clock only)."),
    "X165": ("mechanics panel P3 (iter 11): the operator's queue as a book-free record (point-in-time partial-fill book, followers, arrival latency)", "tried", x165),
    "X166": ("mechanics panel P4 (iter 11): lineage of the deposit wallet (creation, first funding, predecessor)", "tried", x166),
    "X167": ("assumptions panel P1 (iter 11): Dota V as a learnable map of Valve's public spectator state (inverse fit of its own levels)", "open", x167),
    "X168": ("assumptions panel P2 (iter 11): Thunderpick strong form (suspensions as the event clock, uncensored levels, map lines)", "open",
             "Steps on the wallet side done under X159 (variable-length, event-locked withdrawals on BUILD-live). The Thunderpick side (suspension starts, re-open coefficients, timing vs its markers against 2,000 circular shifts, levels at re-open) needs tommy_tp_odds2 P records of matched in-play development matches: none yet (status: matched 1, P polls 0 at 07:37 UTC); first candidates 11-01 09:00-12:00 UTC."),
    "X169": ("assumptions panel P3 (iter 11): counterfactual stale remainder on wallet-absent informed bursts; outcome conventions", "tried", x169),
    "X170": ("assumptions panel P4 (iter 11): the take as a threshold on its own revealed V against the stale ask", "tried", x170),
    "X171": ("assumptions panel P5 (iter 11): clock-free fit of CS2 V to a round-state Markov valuation", "tried", x171),
}
for k, (src, stt, ev) in new_items.items():
    cat[k] = {"status": stt, "source": src, "evidence": ev}
cat["X150"]["evidence"] = str(cat["X150"].get("evidence", "")) + " | Iteration 12 correction (X163): with V-relative ladder state the oracle ceiling is 0.73-0.79 per order and 0.875 on the burst-set unit; the 0.71-0.75 cap came from features relative to the old top."
cat["X155"]["evidence"] = str(cat["X155"].get("evidence", "")) + " | Iteration 12 (X169): the T_lo world is confirmed on wallet-absent informed bursts (later takers obtain 3-7% of the wallet's take at <= the leader's limit after its match)."
S["catalog"] = cat

comp = S["components"]
comp["price"]["description"] = (
    "Maker: one private value V per burst plus a mechanical ladder: a burst of n adds takes the n highest free whole-cent slots V .. V - 4c inside [0.05, 0.95], top-first (X163, BUILD-live oracle: set unit 0.875, per order 0.73, up / fresh / down bursts 0.87-0.94; V must be exact to the cent: +-1c gives 0.70 / 0.81, +-2c 0.22 / 0.08). "
    "V is not a round-score Markov table (X171: residual 3.22c vs the print's 3.21c), not the others' fresh levels (X153), not SX Bet (X145), not a public per-minute Dota state map (X167 step 1: 0.17 vs the last print 0.42); its quiet re-pricings are sampled on its 504-ms loop with little public trace (X158). "
    "Examinable historical anchor: the last print 0.305-0.322 within one tick (VALIDATE); a point-in-time partial-fill book does not beat it (X165, 0.274 vs 0.275). Live: touch 0.42 (fills) / 0.45 (adds). Pre-game 1-2c under Polymarket's print.")
comp["price"]["tag"] = "VALIDATE-only"
comp["timing"]["description"] = (str(comp["timing"]["description"]).split(" Iteration 12:")[0] +
    " Iteration 12: two clocks. Event path (off-tick): takes (0 of 22 on the loop) and triggered actions within a median 17 ms of a book change. Loop path: a free-running ~504-ms loop carries the quiet re-pricings (72.8% of untriggered adds within 15 ms of the predicted tick vs 6% uniform; X158), whose inputs leave a public trace in at most ~14 points of cases. "
    "It withdraws whole events for variable lengths (median 12.5 s, 3% at the 3-tick repair) at moments of public action (X159 steps 1-2). The take is consistent with its revealed value reaching the stale ask (X170, AUC 0.81).")
comp["exit"]["description"] = (str(comp["exit"]["description"]).split(" Iteration 12:")[0] +
    " Iteration 12 (X169): on 3,028 wallet-absent informed bursts later takers obtain only 3-7% of the wallet's typical take at <= the leader's limit after its match: the stale remainder is gone by the match, so the T_lo world (outcome <= 0.50 / 0.41 at any public lag of the take) is real, not a replay convention.")
S["components"] = comp

base = S["strategy_statement"].split(" [VALIDATE-only, iteration 12]")[0]
S["strategy_statement"] = (base +
    " [VALIDATE-only, iteration 12] Its maker price is one private value per burst plus a mechanical ladder (n adds fill the n highest free whole-cent slots under the value; 0.875 on the burst-set unit with the value known), so the price item is gated only by the value; that value is not a round-score Markov table (no closer to it than the print), not a map of public per-minute Dota state, and its quiet changes are sampled on a ~504-ms loop with little public trace. "
    "[hypothesis, BUILD-live] It withdraws whole events for seconds to minutes at moments of public action (median 12.5 s), and it takes when its revealed value reaches the stale ask. [VALIDATE-only, iteration 12] Without the wallet the stale remainder at an informed limit is also gone by the leader's match, so the outcome bound at public latency is a property of the market, not of the replay.")

S["live_lab"].append({"what": "own recorder, feed tommy_kick_pdt (code/iter12/kick_pdt_recorder.py; X162): Kick channel API (key-free) and the IVS HLS playlists as text (newest PROGRAM-DATE-TIME per media sequence; no segments, no chat, no video) of the Kick channels of non-GRID CS2 / Dota events in play; unit-rule filing via code/iter5/unit_writer.py; detached (launcher 8260, worker 16248), hard stop 2026-11-03 00:00 UTC, 50 MB cap, < 2 requests/s", "start": 1793519469, "end": 1793664000})
S["data_sources"].extend([
    "Kick channel API kick.com/api/v2/channels/<slug> (key-free, verified 2026-11-01) and Amazon IVS HLS playlists (text only) -> feed tommy_kick_pdt",
    "Polygon archive state via drpc eth_getCode (key-free for getCode; archive-depth getLogs refused on the free plan) for the deposit wallet's deployment block",
    "bo3.gg per-round team economy (equipment_value, economy_level, side) from the cached /games/<id>/rounds records",
])
S["hypotheses"].extend([
    {"id": "H128", "family": "price", "description": "Between in-round events its CS2 value sits on an MR12 round-score Markov table (clock-free HMM fit).", "validate_metrics": {"sig_v_c": round(A['sig_v_median'] * 100, 2), "sig_print_c": round(A['sig_p_median'] * 100, 2), "rank_v": A['rank_v_median'], "rank_p": A['rank_p_median']}, "verdict": "rejected (pre-registered: not a score table)"},
    {"id": "H129", "family": "price", "description": "Given V, the ladder is mechanical (n highest free whole-cent slots under V, top-first).", "validate_metrics": {"set_unit": lmv['set_unit'], "per_order": lmv['per_order_no_rank'], "per_burst": lmv['per_burst']}, "verdict": "supported on BUILD-live (oracle V); VALIDATE-live scoring pending"},
    {"id": "H130", "family": "outcome", "description": "Without the wallet's take the stale remainder at an informed limit survives the leader's match (T_hi world).", "validate_metrics": {"absent_later_share_per_bin": [sr['all']['wallet-absent'][f'later_m+{i}-{i+1}s_share_any_nonwallet'] for i in range(4)]}, "verdict": "rejected (T_lo world on a natural experiment)"},
    {"id": "H131", "family": "price", "description": "A point-in-time partial-fill book anchors its quotes better than the last print (historical, examinable).", "validate_metrics": {"fallback_score": pb['chosen_on_BUILD']['VALIDATE_bid_fallback'], "last_print": pb['chosen_on_BUILD']['VALIDATE_last_print']}, "verdict": "rejected"},
    {"id": "H132", "family": "timing", "description": "The take is a threshold on its own revealed value against the stale ask.", "validate_metrics": {"auc_gap": tg['gap']['auc_raw'], "auc_loeo": tg.get('logit_loeo', {}).get('auc')}, "verdict": "partly supported (AUC 0.81, no sharp threshold)"},
    {"id": "H133", "family": "timing", "description": "Its quiet re-pricings are samples of public book changes taken at its 504-ms loop tick.", "validate_metrics": {"untriggered_adds_on_tick": la['on_tick_rate'].get('untriggered_add'), "on_tick_any_same_book_change": [att['on_tick_own']['same_any_in_tick'], att['on_tick_control']['same_any_in_tick']]}, "verdict": "loop confirmed; public-sampling branch rejected (excess <= 14 points)"},
    {"id": "H134", "family": "price", "description": "Its Dota value is a learnable map of public per-minute game state (inverse fit).", "validate_metrics": {"within_tick": dt['logistic_ls']['within_tick'], "last_print": di['last_print']['within_tick']}, "verdict": "rejected for per-minute OpenDota state (live Valve state pending)"},
    {"id": "H135", "family": "timing", "description": "Its event-wide withdrawals are the fixed 3-tick repair after its own pulls (own-model holes only).", "validate_metrics": {"share_3ticks": wd['share_3ticks_pm60ms'], "median_s": wd['dur_quantiles_s']['0.5']}, "verdict": "rejected: variable-length, event-locked withdrawals (BUILD-live)"},
])
S["iterations"].append({"n": 12, "minutes": MINUTES, "best_validate_score": 0.8834,
    "paradigm": "the wallet's value V as the target: clock-free hidden-Markov valuation fits (CS2 round-score Markov table, Dota public-state inverse fit, round economy), the V-plus-mechanical-ladder decomposition of the price item, the 504-ms loop tick as the decision unit, and natural experiments on the outcome convention (wallet-absent bursts) and on withdrawals",
    "families": ["clock-free HMM fit of V to an MR12 round-score Markov table vs permutations and the print (X171)", "round economy at inferred round starts (X160 clock-free form)", "V-plus-ladder machine with frozen constants (X163)", "wallet-absent natural experiment for the stale remainder (X169)", "point-in-time partial-fill book (X165)", "take vs own revealed value against the stale ask (X170)", "504-ms loop phase labels and tick-interval attribution (X158)", "event-wide withdrawal fingerprint (X159 / X168 steps 1-2)", "deposit-wallet lineage on chain (X166)", "Dota inverse fit on public per-minute state (X167 step 1)", "Kick IVS stream-clock recorder (X162)"]})
S["next_steps"] = [
    "VALIDATE-live (11-01 06-12 from 09:00 UTC, 11-01 18-24, 11-02 00-06): Thunderpick tests (X144 frozen; X159 step 3 / X168 suspension coincidence with its event-wide withdrawals), X158 replication and steps 3-5, X163 machine scoring with V proxies, X164 rounds-book clock, X167 step 2 / X118 on tommy_dota_rt, X162 dose-response once >= 15 Kick events exist.",
    "X160 with a public clock: pause-aware DP on signed public jumps, then test the economy term of its offset beyond the previous round results.",
    "X161 Azuro: contract addresses from the toolkit text, ConditionCreated -> game mapping, in-play bet density on its events.",
    "Re-fit the taker-size and merge-law constants on BUILD-live before a future-block exam (X156).",
    "Ask the user: may the examiner score the burst-set unit for price (X163)? is item 5 judged at 2-s latency (X169 says T_lo holds either way)? demos / PandaScore token / HLTV / stream routes (unchanged).",
]
S["target_metrics_notes"]["iteration_12"] = ("No rule change; target_metrics unchanged (v5). New measured bounds: the price item with V known is 0.73 per order / 0.875 on the burst-set unit (X163), so it is gated only by V; "
    "the PIT partial-fill book does not beat the last print (X165); the T_lo outcome world is confirmed on wallet-absent bursts (X169).")
pg = S.get("progress_gauges", {})
if "g1_live_price_adds" in pg:
    pg["g1_live_price_adds"]["bound"] = "oracle with V known: 0.73 per order without rank, 0.875 on the burst-set unit (X163, ladder_machine.json)"
if "g3_outcome_bound" in pg:
    pg["g3_outcome_bound"]["value"] = str(pg["g3_outcome_bound"].get("value", "")) + "; T_lo confirmed on 3,028 wallet-absent bursts (X169)"
S["progress_gauges"] = pg
S["status"] = "continue"
S["wall_reason"] = None
S["updated"] = int(time.time())
json.dump(S, open(WS / "state.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("state written; open:", [k for k, x in S["catalog"].items() if x.get("status") == "open"])
