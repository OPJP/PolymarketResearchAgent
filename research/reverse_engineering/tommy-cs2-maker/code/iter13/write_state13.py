"""Iteration 13 state.json update: panel proposals X172-X183 and self-proposed X184-X188 into the catalog with this
iteration's evidence; corrections of C1 / C4 / X65 / X95 / X110 / X96 closures; components, strategy statement,
hypotheses, data sources, iteration entry, next steps (target metrics unchanged: v5)."""
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
WS = ROOT / "research/reverse_engineering/tommy-cs2-maker"
RES = WS / "results"
MINUTES = int(os.environ.get("IT13_MINUTES", "0"))


def rj(n):
    p = RES / n
    return json.load(open(p, encoding="utf-8")) if p.exists() else None


S = json.load(open(WS / "state.json", encoding="utf-8"))
cat = S["catalog"]
ha, spc, sh, sp, sl, ssep = rj("hawk_align.json"), rj("same_process_census.json"), rj("sibling_history.json"), rj("sibling_price.json"), rj("sibling_feed_lag.json"), rj("sibling_sep.json")
evc, sfh, fc, lvt, luh, tr = rj("event_value_coupling.json"), rj("slow_filter_hist.json"), rj("follower_census.json"), rj("lead_vs_trades.json"), rj("ladder_union_hist.json"), rj("tick_rule.json")
wt, sm, ssel, dmsg, ird = rj("withdrawal_triggers.json"), rj("salt_merged.json"), rj("sibling_selection.json"), rj("declined_messages.json"), rj("inround_drift.json")
ild = rj("inround_lead.json")

bb = ha["summary"]
x172 = ("Step 0: hawk.live series pages fetched once each as a normal visitor through the shared cached client (code/iter13/hawk_fetch.py; Inertia data-page JSON; head-to-head list with sealed series dropped unread): 10-22 ty-gl, 10-22 ts8-legion1 (team-spirit-vs-legion), 10-31 ty-gl (pari-universe-playoffs); 10-22 liquid-1win HTTP 404 'No query results for model [App\\Models\\Series]' under three slugs. "
        f"Step 1 (hawk_align.json, code/iter13/hawk_align.py): 6 maps, BetBoom / SpinBetter / Parimatch, proportional de-margin; clock-free monotone alignment of its 686 Dota burst tops: wallet RMS vs print RMS (median over maps) betboom {bb['betboom_free']['wallet_rms_c_median']:.2f}c vs {bb['betboom_free']['print_rms_c_median']:.2f}c, spin-better {bb['spin-better_free']['wallet_rms_c_median']:.2f}c vs {bb['spin-better_free']['print_rms_c_median']:.2f}c, parimatch {bb['parimatch_free']['wallet_rms_c_median']:.2f}c vs {bb['parimatch_free']['print_rms_c_median']:.2f}c; wallet below print on 1 of 6 maps for each provider; within 1c pooled 0.54-0.63 vs print 0.60-0.70; reversed 2.2-3.5c, other maps 1.9-2.9c (power). "
        "Verdict: its Dota value is not a de-margined line of these three providers (it tracks them exactly as closely as the market). Step 2 (live poller with timestamps) not run: no wallet Dota trade in the VALIDATE-live block (dota2-synaps-hn skipped), later development blocks fall after the budget.")
top = spc["top"][:3]
x176 = ("same_process_census.json, sibling_accounts.json, sibling_history.json, sibling_price.json, sibling_feed_lag.json, sibling_sep.json, ladder_union_hist.json, sibling_selection.json (code/iter13/). "
        "Census over every maker with >= 100 orders in the wallet's 16-22 Oct markets: orders signed 0-5 ms after a same-token wallet order vs the [5, 50) ms rate: "
        + "; ".join(f"{t['maker'][:10]} {t['lag0_5']} vs {t['per5ms_5_50']} per 5 ms ({t['ratio']}x, {t['lag0_5_same_price']} same price, sizes {t['sizes_top']})" for t in top)
        + "; every other maker <= 4.5x. Owners in the immutable proxy args (same factory 0xd729a0cb as the wallet): 0x7d67f01d -> 0x80a19b87, 0x52661b8e -> 0xe6f64514, 0x67119033 -> 0x116342d6 (the EOA that received the wallet owner's only outgoing $2,000); 0x80a19b87 / 0xe6f64514 / the wallet's owner are EIP-7702 accounts delegated to 0x63c0c19a. Profile names: 0x52661b8e 'TommyLeePeeecan', 0x7d67f01d 'BACKTESTEOCARAIO1'. "
        "0x7d67f01d: BUY-only + MERGE maker since September (Sep 8,909 BUY / 0 SELL, Oct 35,877 / 68; 100-share CS2 / Dota, LoL 100 then 10), all-non-GRID CS2 in 10-01..10-15 (19,310 trades, 133 events) while the wallet was a GRID taker (7,506 of 7,717 CS2 trades GRID); winds down from 10-16 as the wallet takes the role over. "
        f"Its 10-08..10-15 maker orders (sample 3,253 txs): within one tick of the last print {sp['sibling_7d67']['price']['within_tick_last_print']} (wallet BUILD {sp['wallet_BUILD']['price']['within_tick_last_print']} / VALIDATE {sp['wallet_VALIDATE']['price']['within_tick_last_print']}), offset -1c, whole cents, band, ramp sizes; its takes (1000 / 2000 caps) sign a median {sl['P4e']['median_lag_ms_within_500']} ms after P4e on the same token (63.5% in [20, 100) ms). "
        f"September: maker within tick {ssep['price']['within_tick_last_print']} at offset {ssep['price']['median_offset_c']}c, takes {ssep['lag_vs_p4e']['median_lag_ms_within_500']} ms after P4e. "
        f"Historical uncensoring: the 5-share co-signed orders sit in the wallet's five slots (union within V - 4c in {luh['union_within_V_minus_4c']} of {luh['co_bursts']} bursts; slot profile {luh['sibling_slot_hist_cents_below_V']}). "
        f"Selection replication: the frozen league / GRID component scores 0x7d67f01d's 10-01..10-15 event choice at AUC {ssel['sibling_7d67']['auc_s_lg']} ({ssel['sibling_7d67'].get('auc_s_lg_nongrid_only')} within non-GRID). "
        "One operator, at least four accounts, one signing process; the 10-16 switch is an account migration (corrects C1 / X14 / X65 / X95 / X110).")
x173 = (f"Historical form (event_value_coupling.json, code/iter13/event_value_coupling.py): {evc['pairs_both_nonzero']} same-tick (+-5 ms) map / match burst pairs with both changes nonzero in {evc['events']} CS2 Bo3 events of 16-22 Oct: team-direction agreement {evc['direction_agreement']}; |dV_match / dV_map| median by s tercile "
        + ", ".join(f"{k} {v['abs_ratio_median']} (s {v['s_median']}, n {v['n']})" for k, v in evc["ratio_by_s_tercile"].items())
        + f"; Spearman(s, |ratio|) {evc['spearman_s_vs_abs_ratio'][0]} (p {evc['spearman_s_vs_abs_ratio'][1]:.2f}); public prints over the same intervals ratio {evc['public_prints_same_intervals']['abs_ratio_median']} (n {evc['public_prints_same_intervals']['n']}). "
        "One private event-level update written to both books by about the same cents (not scaled by s; not public co-motion). Live form (decider maps, public-change term) waits for VALIDATE-live.")
v = sfh["by_h"]
x174 = ("Historical form (slow_filter_hist.json, code/iter13/slow_filter_hist.py): EMA of the same market's public prints (wallet transactions excluded) at half-lives 0 / 2 / 5 / 15 / 60 / 180 s, rounded after a BUILD offset, within one tick of 12,099 VALIDATE maker orders: "
        + " / ".join(str(v[h]["VALIDATE"]["within_tick_with_offset"]) for h in ("0", "2", "5", "15", "60", "180"))
        + ": every memory is worse than the last print. Live form (on-tick hazard on the event composite with round books) waits for VALIDATE-live records of the wallet.")
x175 = (f"withdrawal_triggers.json (code/iter13/withdrawal_triggers.py; BUILD-live): latest non-own change on the event's books within 40 ms before: withdrawal starts {wt['withdrawal_starts']['share_with_change_40ms']} (mean {wt['withdrawal_starts']['mean_changes_40ms']} changes; kinds {wt['withdrawal_starts']['kind']}; sizes {wt['withdrawal_starts']['size_class']}), other triggered pulls {wt['other_triggered_pulls']['share_with_change_40ms']} ({wt['other_triggered_pulls']['mean_changes_40ms']}; {wt['other_triggered_pulls']['kind']}), shifted {wt['shifted_starts']['share_with_change_40ms']} ({wt['shifted_starts']['mean_changes_40ms']}). "
        "No class precedes >= 60% of starts against <= 20% of other pulls (signature a fails); no trade precedes any start; a withdrawal starts on the same co-mover cluster as its other pulls. Suspension overlap (b) and the round-book clock (c) wait for VALIDATE-live.")
x177 = (f"First pass (tick_rule.json, code/iter13/tick_rule.py; BUILD-live {tr['bursts']} add bursts / {tr['adds']} adds through the frozen X163 machine, no fitting): set unit / per order: R0 J {tr['R0']['all']['set_unit']} / {tr['R0']['all']['per_order_no_rank']}, R1 own top before {tr['R1']['all']['set_unit']} / {tr['R1']['all']['per_order_no_rank']}, R2 own top + 1c x sign(last-second others'-mid move) {tr['R2']['all']['set_unit']} / {tr['R2']['all']['per_order_no_rank']}, R3 J + signed step {tr['R3']['all']['set_unit']} / {tr['R3']['all']['per_order_no_rank']}, R4 hybrid {tr['R4']['all']['set_unit']} / {tr['R4']['all']['per_order_no_rank']}. "
        "The signed public delta adds <= 2.5 points to its own top and loses 5 points on J: not 'previous level plus public delta'. The full ledger (holds, queue state, pulls on both tokens) waits for VALIDATE-live.")
x178 = ("Ruled out for its precursor-price premise by measurement (the assumptions panel's Check A re-run unchanged, NOTES iteration 13 finding 7): of 156 calldata-linked own adds, 89-97 have a same-book non-own change within 40 ms before their book time and 65-81% of those were signed before that change reached the book; co-movers are other operators' makers (9 linked pairs within 20 ms: 0x893575c7, 0x51dbdd2b, ...), none of the operator's accounts; withdrawal starts are preceded by the same cluster as other pulls (X175). Precursors are co-receptions, not inputs, so no precursor-class response rule exists to freeze.")
x179 = (f"salt_merged.json (code/iter13/salt_merged.py): {sm['co_bursts']} co-signed bursts (wallet + 5-share sibling orders 0-10 ms after, merged in signing order), GF(2) V8 xorshift128+ test of code/iter7/v8salt_lib.py, both mantissa conventions, DT 0 / 3 ms, strides 1-6 forward and reverse: "
        + "; ".join(f"{k} {v_['hits']} of {v_['tried']} (controls {v_['control_hits']} of {v_['control_tried']})" for k, v_ in sm.items() if isinstance(v_, dict))
        + ". Not one recoverable V8 stream across accounts either; strides beyond 9 would need a solver install (the user's consent).")
x180 = ("Step 1 partly: Check A replicated (65-81% of 'triggered' linked adds signed before their trigger reached the book; NOTES iteration 13 finding 7); only 9 linked non-own adds sign within 20 ms of an own linked add on BUILD-live (1.3% vs 0.1% shifted), too few for per-maker lag fits; the co-movers are other operators (0x893575c7, 0x51dbdd2b, 0x4f87cf20, 0x758dac51). Step 2 on chain: the panel's Check G (other makers' filled-order clusters follow 13.1% of P4e's messages within 300 ms vs 0.8%). "
        "Withdrawal starts sit on co-mover clusters like the other pulls (X175). Steps 3-4 (re-label on the cluster clock, the post-onset price rule) wait for VALIDATE-live.")
irdm = ird
x181 = (f"Steps 1-3 (inround_drift.json, code/iter13/inround_drift.py; {irdm['maps']} CS2 maps, {irdm['rounds']} rounds; round boundaries from the print's X171 fit): AUC of its within-round level change for the bo3 round winner {irdm['auc_dW']} vs the print's {irdm['auc_dP']} (difference {irdm['auc_diff_W_minus_P']} {irdm['auc_diff_ci95']}, map bootstrap p {irdm['auc_diff_p_le0']}); residualised on the print {irdm['auc_dW_resid_on_dP']}; print flat {irdm['auc_dW_when_print_flat']}; "
        + "; ".join(f"guard {g}s {irdm[f'guard_{g}s']['auc_dW']} vs {irdm[f'guard_{g}s']['auc_dP']}" for g in (10, 20, 30, 45))
        + "; early windows " + "; ".join(f"first {e}s {irdm[f'early_{e}s']['auc_dW']} vs {irdm[f'early_{e}s']['auc_dP']}" for e in (30, 60) if f'early_{e}s' in irdm)
        + (f"; inround_lead.json: a >= 2c move toward the winner inside the round only by its value {ild['D2c']['only_wallet']}, only by the print {ild['D2c']['only_print']}, both {ild['D2c']['both']}" if ild else "")
        + (f"; before the print's first >= 2c move in the round {irdm['pre_print_move']['auc_dW']} vs {irdm['pre_print_move']['auc_dP']} ({irdm['pre_print_move']['rounds']} rounds; {irdm['pre_print_move']['rounds_where_print_later_moved']['auc_dW']} where the print moves later)" if 'pre_print_move' in irdm else "")
        + (f"; by split BUILD {irdm['by_split']['BUILD']['auc_dW']} vs {irdm['by_split']['BUILD']['auc_dP']}, VALIDATE {irdm['by_split']['VALIDATE']['auc_dW']} vs {irdm['by_split']['VALIDATE']['auc_dP']}" if 'by_split' in irdm else "")
        + ". Signature met: its value is an in-round win-probability state that builds up its lead during the round. Step 4 (side-aware table at freeze time) not run.")
x182 = (f"Step 1 (follower_census.json, lead_vs_trades.json; BUILD-live): non-own adds at its new top within 2 s: untriggered {fc['untriggered']['mean_followers_at_top']} vs {fc['untriggered']['shifted_mean_at_top']} shifted ({fc['untriggered']['ratio']}x), triggered {fc['triggered']['mean_followers_at_top']} vs {fc['triggered']['shifted_mean_at_top']} ({fc['triggered']['ratio']}x): joiners exist. "
        f"Lead on executed prices: Spearman(offset to mid, non-wallet trade VWAP in (t+5, t+60] s minus mid) {lvt['own_spearman']} for {lvt['own_adds']} own adds vs {lvt['other_spearman']} for other makers (null {lvt['null_mean']}, p95 {lvt['null_p95']}, p {lvt['p_own_vs_null']}): the lead is not only followers'. Step 2 (joiner-free mid, per-tick controller with an absorbing gap) not run.")
x183 = ("Historical form (declined_messages.json, code/iter13/declined_messages.py; 16-22 Oct pack take clusters): a filled wallet maker order signed within +-30 ms of the cluster onset on any book of the event: "
        + "; ".join(f"{k} {v_['member_rate']} vs {v_['shifted_rate']} shifted ({v_['ratio']}x, n {v_['clusters']})" for k, v_ in dmsg.items())
        + ". Its maker leg re-prices at the messages it does not take: the round-win kind is received and declined (withdraws iteration-7 finding 20). The BUILD-live direction test (V toward the pack's team) not run.")
NEW = {
    "X172": ("information panel P1 (iter 12): hawk.live archived and live multi-bookmaker Dota lines as the wallet's Dota value (E4 for the Dota half)", "tried", x172),
    "X173": ("information panel P2 (iter 12): one game value per event: map-match same-tick coupling against the series sensitivity", "tried", x173),
    "X174": ("information panel P3 (iter 12): rounded slow filter of the event's public composite (strong form of E16)", "tried", x174),
    "X175": ("information panel P4 (iter 12): name what starts and ends each event-wide withdrawal", "tried", x175),
    "X176": ("mechanics panel P1 (iter 12): map every account the wallet's bot signs for and use them as natural experiments on V", "tried", x176),
    "X177": ("mechanics panel P2 (iter 12): a signed per-tick ledger of the 504-ms loop with pulls, queue state and public deltas", "tried", x177),
    "X178": ("mechanics panel P3 (iter 12): the event path's response function (precursor class -> response price)", "ruled_out", x178),
    "X179": ("mechanics panel P4 (iter 12): the salt stream when one process signs for several accounts", "tried", x179),
    "X180": ("assumptions panel P1 (iter 12): the event path is a common-cause cluster; co-mover message clock", "tried", x180),
    "X181": ("assumptions panel P2 (iter 12): V is an in-round win-probability state; round-level drift and a side-aware table at freeze time", "tried", x181),
    "X182": ("assumptions panel P3 (iter 12): the lead of V may be its followers'; per-tick book-state controller", "tried", x182),
    "X183": ("assumptions panel P4 (iter 12): is the round-win kind missing from its input, or received and declined?", "tried", x183),
    "X184": ("self-proposed (iteration 13): LoL natural experiment: the operator's earlier account quoted LoL with the same maker design (Sep 100 shares, Oct 10 shares, BUY-only, whole cents, band); Riot publishes live game state key-free (feed.lolesports.com livestats windows), so the value model can be fitted where its input is public", "open",
             "Not run: mapping Polymarket LoL events to Riot game ids needs the lolesports esports API, whose key is embedded in the public website for anonymous clients; using it needs the user's decision (as for hawk.live's socket key). The livestats feed itself is key-free. Sibling LoL design measured (NOTES iteration 13 finding 15)."),
    "X185": ("self-proposed (iteration 13): the operator's bot-version history on its earlier account (June-July two-sided 5-7-share design; September -3c offset; October -1c)", "tried",
             "sibling_jun.json (code/iter13/sibling_jun.py; all 2,133 June CS2 transactions decoded): 786 maker orders (whole cents, band, 7-12 shares, BUY 737 / SELL 49) within one tick of the last print 0.455 at offset 0c (0.537 when the print is > 60 s old); late September 0.218 at -3c, 10-08..10-15 0.298 at -1c, the wallet 0.305-0.309 at -1c (sibling_sep.json, sibling_price.json; feed lag +65 -> +34 ms). The June maker pegged to the stale print; the private value appears by late September, in the feed era. July (LoL only) not decoded."),
    "X186": ("self-proposed (iteration 13): the lead of its level on a joiner-free mid (X182 step 2)", "open", "Joiners measured (follower_census.json) and the lead on executed trades (lead_vs_trades.json, 0.316 vs 0.153); the joiner-free mid needs a rebuild of others_mid_dev without levels added at its top +-1c within 2 s."),
    "X187": ("self-proposed (iteration 13): the selection rule on the operator's earlier account out of sample (10-01..10-15)", "tried",
             f"sibling_selection.json (code/iter13/sibling_selection.py): 718 CS2 events (337 GRID), 0x7d67f01d traded 115 (all non-GRID); frozen league / GRID component AUC {ssel['sibling_7d67']['auc_s_lg']}, non-GRID only {ssel['sibling_7d67'].get('auc_s_lg_nongrid_only')}, non-GRID seen leagues {ssel['sibling_7d67'].get('auc_s_lg_nongrid_seen_leagues')}; the wallet's own GRID-taker events of the window {ssel['wallet']['auc_s_lg']}. The selection rule is the maker strategy's and replicates out of sample on another account (VALIDATE-only)."),
    "X188": ("self-proposed (iteration 13): the operator's other accounts in GRID CS2 events (0x67119033 27 GRID events, 0x52661b8e 13 in October) as a window on the same process where round scores are public", "open",
             "First pass (grid_inround.json, code/iter13/grid_inround.py): their October GRID CS2 quoting has the maker design (0x67119033 27 events, BUY 0.995, whole cents 0.984, band 1.0, 20 shares; 0x52661b8e 13 events, BUY 1.00, 5 shares); 2,078 GRID-event transactions decoded; only 11 maps / 71 rounds usable: within-round AUC 0.660 for their level vs 0.357 for the print (unreliable with so few rounds). Open: needs their full GRID record and the sports socket's GRID round clock on development blocks."),
}
for k, (src, st, ev) in NEW.items():
    cat[k] = {"status": st, "source": src, "evidence": ev}
# corrections of earlier closures
corr = (" | Iteration 13 correction (X176): one operator signs for at least four accounts with one process (0x52661b8e 'TommyLeePeeecan', 0x67119033 owned by 0x116342d6, the wallet owner's $2,000 recipient, and 0x7d67f01d 'BACKTESTEOCARAIO1', the maker strategy's account before 10-16); see X176.")
for k in ("C1", "X14", "X95", "X110", "X65"):
    if k in cat and corr not in cat[k].get("evidence", ""):
        cat[k]["evidence"] = cat[k].get("evidence", "") + corr
if "C4" in cat:
    cat["C4"]["evidence"] = cat["C4"].get("evidence", "") + " | Iteration 13: the 10-16 'switch' is an account migration of a running strategy (0x7d67f01d made the non-GRID markets with the same design, prices, feed position and selection from at least 09-21); version change on that account: maker offset -3c (late September) -> -1c (October), feed lag +65 -> +34 ms."
for k in ("C4b",):
    if k in cat:
        cat[k]["evidence"] = cat[k].get("evidence", "") + " | Iteration 13: answered by X176: no Polymarket change is needed; the operator moved its maker from 0x7d67f01d to the main account on 10-16."
if "X96" in cat:
    cat["X96"]["status"] = "tried"
    cat["X96"]["evidence"] = cat["X96"].get("evidence", "") + " | Iteration 13 (X179): merged wallet + sibling sequences also give 0 consistent systems at strides 1-6 (controls 0); closed as 'not a recoverable small-stride V8 stream'; larger strides need a solver install (user's consent)."
for k in ("X48",):
    if k in cat:
        cat[k]["evidence"] = cat[k].get("evidence", "") + " | Iteration 13 (X172): three CIS bookmakers' archived in-play Dota lines (BetBoom, SpinBetter, Parimatch via hawk.live) are not its Dota value (no closer than the print)."

S["components"]["selection"]["description"] += (" Iteration 13 (X187, VALIDATE-only): the frozen league / GRID component replicates out of sample on the operator's earlier maker account (0x7d67f01d, 10-01..10-15, 718 events): AUC 0.942 (non-GRID only 0.868); the selection belongs to the maker strategy and moved with it on 10-16.")
S["components"]["selection"]["confidence"] = 0.78
S["components"]["timing"]["description"] += (" Iteration 13: the event path is co-reception of a dense hidden stream shared with other operators' makers (65-81% of 'triggered' adds signed before their trigger reached the book; withdrawals start on the same co-mover cluster as other pulls); its maker leg re-prices at the pack's messages it does not take (5.3x shifted), so the take's kind filter sits at the take decision (value threshold), not at its input.")
S["components"]["price"]["description"] += (" Iteration 13: V is an in-round win-probability state (its within-round drift predicts the round winner at AUC 0.90 vs the print's 0.68; 0.79 vs 0.62 even 45 s before the print-inferred round end); one value per event written to the map and match books by the same cents (96% direction agreement); not a de-margined BetBoom / SpinBetter / Parimatch Dota line (no closer than the print), not an EMA of prints (<= 0.30), not its own top plus the public delta (<= 0.46 through the machine); the five-slot ladder is confirmed historically through the operator's 5-share accounts (98% of co-bursts inside V - 4c).")
S["components"]["price"]["confidence"] = 0.55
S["components"]["exit"]["description"] += " Iteration 13: the same BUY-only + MERGE design ran on the operator's earlier account (0x7d67f01d) in September-October."
S["components"]["size"]["description"] += " Iteration 13: the earlier account used the same 100-share CS2 size with the 50-79 ramp sizes, and 1000 / 2000 taker caps before 10-16."

S["strategy_statement"] = (
    "CS2 and Dota 2 in-play bot of one operator who signs for at least four accounts with one process (the wallet 'TommyLeePeeca'; 0x52661b8e 'TommyLeePeeecan'; 0x67119033, owned by the wallet owner's $2,000 recipient; 0x7d67f01d 'BACKTESTEOCARAIO1'). "
    "The maker strategy ran on 0x7d67f01d (non-GRID CS2, Dota and LoL, from at least 09-21) and moved to the main account on 10-16, when the main account stopped its GRID taker; it has the same maker prices, feed position and selection on both accounts; in June the same design quoted at the stale public print (0.455 within one tick), and the private value appeared by late September, in the feed era [VALIDATE-only]. "
    "[VALIDATE-only] Selection: whole events of non-GRID CS2 / Dota 2 leagues covered by its push-feed product; frozen v5 pooled AUC 0.970 vs activity 0.886, recall 0.74 at lift 3.16, coverage 1.0; its league / GRID component also scores the operator's earlier account's event choice at AUC 0.94 out of sample. "
    "[VALIDATE-only] Maker: whole-cent BUY ladders on both outcome tokens (100 shares in CS2, 10 in Dota 2), never sells, merges pairs in a 300-s loop (pair cost 0.978); a burst of n adds takes the n highest free slots V, V - 1c, ..., V - 4c inside [0.05, 0.95] (oracle 0.875 live; confirmed historically through the 5-share accounts). "
    "[hypothesis, historical outcome-validated] V is its own in-round win-probability state fed by a private esports push feed: within a round its value drifts toward the eventual round winner (AUC 0.90 vs the print's 0.68), one value per event is written to the map and match books, and the value leads other traders' executed prices (Spearman 0.32 vs 0.15 for other makers). No public source obtained reproduces V to the cent (bookmaker lines, round tables, public game state, filters of prints or book deltas all score at or below the last print). "
    "[hypothesis] Taker: FAK buys of the team that gained on messages of the shared push feed (>= 19 subscribers at fixed lags; the operator sat at +30-65 ms behind P4e since late September), taken when its revealed value reaches the stale ask; its maker leg also re-prices at the messages it does not take. Exit: never sells; pulls and re-pairs the complement around its takes; merges complete pairs; holds the residual. "
    "Not decoded to the exam bar: the price item needs V to the cent and the outcome item needs the +50-ms take; both stand on a private feed (measured bounds in FINAL_RULE.md).")

S["hypotheses"] += [
    {"id": "H136", "family": "price", "description": "Its Dota value is a de-margined in-play line of BetBoom, SpinBetter or Parimatch (hawk.live archive).", "validate_metrics": {"wallet_rms_c_median_betboom": bb["betboom_free"]["wallet_rms_c_median"], "print_rms_c_median_betboom": bb["betboom_free"]["print_rms_c_median"]}, "verdict": "rejected: no closer to any provider than the print"},
    {"id": "H137", "family": "mechanics", "description": "The wallet's process signs for other accounts (same-process co-signing at 0-5 ms).", "validate_metrics": {"accounts": 3}, "verdict": "supported: 0x52661b8e, 0x67119033, 0x7d67f01d; owner funding link and names"},
    {"id": "H138", "family": "selection", "description": "The maker strategy and its selection pre-date the wallet's switch on another account.", "validate_metrics": {"auc_s_lg_sibling_1001_1015": ssel["sibling_7d67"]["auc_s_lg"]}, "verdict": "supported (account migration on 10-16)"},
    {"id": "H139", "family": "price", "description": "One value per event: same-tick map / match re-pricings agree in direction and size.", "validate_metrics": {"direction": evc["direction_agreement"], "n": evc["pairs_both_nonzero"]}, "verdict": "supported in direction; size not scaled by the series sensitivity"},
    {"id": "H140", "family": "price", "description": "Its level is a rounded EMA of public prints.", "validate_metrics": {"h0": v["0"]["VALIDATE"]["within_tick_with_offset"], "h5": v["5"]["VALIDATE"]["within_tick_with_offset"]}, "verdict": "rejected (historical form)"},
    {"id": "H141", "family": "price", "description": "Its value is an in-round win-probability state (within-round drift toward the round winner beyond the print).", "validate_metrics": {"auc_dW": ird["auc_dW"], "auc_dP": ird["auc_dP"], "guard45": ird["guard_45s"]}, "verdict": "supported (historical, outcome-validated)"},
    {"id": "H142", "family": "timing", "description": "The take's kind selectivity sits at its input (it does not receive the round-win kind).", "validate_metrics": {"member_ratio_no_take_P4e": dmsg["no_wallet_take_P4e"]["ratio"]}, "verdict": "rejected: its maker leg re-prices at the messages it does not take"},
    {"id": "H143", "family": "price", "description": "Its quiet value = own previous top plus the sign of the last-second public move.", "validate_metrics": {"R2_set_unit": tr["R2"]["all"]["set_unit"], "J_set_unit": tr["R0"]["all"]["set_unit"]}, "verdict": "rejected (BUILD-live, first pass)"},
]
S["data_sources"] += [
    "hawk.live series pages (Inertia data-page JSON): per-map in-play map-winner odds of BetBoom / SpinBetter / Parimatch with a site-wide update id (no timestamps), game states every ~20 s of game time, picks, streams; development series only (hawk/ in the cache)",
    "data-api activity and profile names of the operator's other accounts (0x7d67f01d, 0x52661b8e, 0x67119033) before H",
    "V2 calldata of 0x7d67f01d's sampled CS2 / Dota transactions (10-08..10-15: 3,253; 09-21..09-30: 3,000) and P4e's 1,718 September transactions on its markets",
    "chain state at latest (eth_getCode / nonce) of the operator's deposit wallets and owners (proxy immutable args, EIP-7702 designators)",
]
S["iterations"].append({"n": 13, "minutes": MINUTES, "best_validate_score": 0.8834,
                        "paradigm": "new data and units: a historical multi-bookmaker Dota line (hawk.live), the operator's other accounts as a second window on the same process (same-process census, owners, histories, pre-switch prices, feed lag and selection), one value per event (map-match coupling), and the value's in-round drift against bo3 round winners",
                        "families": ["hawk.live bookmaker lines vs its Dota value, clock-free alignment with controls (X172)", "same-process account census, owners, names, histories (X176)",
                                     "earlier-account maker prices, taker feed lag (October and September) (X176)", "historical ladder uncensoring through the 5-share accounts (X176 step 6)",
                                     "selection replication on the earlier account (X187)", "map-match same-tick coupling vs series sensitivity (X173)", "EMA filters of prints (X174)",
                                     "withdrawal trigger attribution (X175)", "signed public delta rules through the ladder machine (X177)", "triggered-add sign-time replication and co-mover identity (X180 / X178)",
                                     "in-round drift vs bo3 round winners with print-inferred rounds and guards (X181)", "follower census and the lead on executed trades (X182)",
                                     "declined-message membership of its maker leg (X183)", "merged-account V8 salt stream (X179)", "frozen v5 on the first VALIDATE-live block (6 events, 0 selected, 0 traded)",
                                     "in-round lead timing and early windows (X181 companion)", "the operator's GRID-event quoting, first pass (X188)", "the earlier account's June version (X185)"]})
S["next_steps"] = [
    "VALIDATE-live 11-01 06-12: if the wallet trades cs2-bca-pha (11:00), run the pre-registered live tests (X163, X158, X159 step 3 / X168, X144) and the live forms of X173 / X174 / X177.",
    "X181 step 4 (side-aware table at freeze time) and a winner-free round clock (on-chain co-mover clusters, X180 step 2) to make the in-round state measurable point in time.",
    "X188 / X184: the operator's other accounts in GRID CS2 (public round scores) and in LoL (Riot live stats; needs the user's decision on the lolesports web key) as windows on the same value process.",
    "X185 / X186: the earlier account's June-July versions; the lead on a joiner-free mid.",
    "Ask the user: demos, Kick VOD, HLTV pages, the lolesports web key, a solver install, and whether the examiner may score the burst-set unit.",
]
S["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
S["status"] = "continue"
S["wall_reason"] = None
json.dump(S, open(WS / "state.json", "w", encoding="utf-8"), indent=1)
op = [k for k, x in cat.items() if x.get("status") == "open"]
print("catalog", len(cat), "open", len(op), op)
