"""Iteration 14 state update: brief 11-01 items (E1-E7 catalog, `dimensions`, `indicators` with legacy rows), the
iteration-13 panel proposals X189-X203, this iteration's results, components, iteration entry. Reads results/*.json."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import indicators as ind  # noqa: E402

WS = ROOT / "research/reverse_engineering/tommy-cs2-maker"
RES = WS / "results"
S = json.load(open(WS / "state.json"))
cat = S["catalog"]


def rj(name):
    p = RES / name
    return json.load(open(p)) if p.exists() else None


e2, lag, trb, trs, pg, e3 = (rj("e2_residuals.json"), rj("lag_tolerance.json"), rj("event_transport_block.json"),
                             rj("event_transport_sign.json"), rj("phase_gated_ladder.json"), rj("e3_screen.json"))
ext = json.load(open(RES / "iter14_extra.json")) if (RES / "iter14_extra.json").exists() else {}
e7p = rj("e7_power.json") or {}

# ------------------------------------------------------------------ E1: dimension inventory


def D(family, status, source, resolution, latency, best, verdict, note="", mds=None):
    return {"family": family, "status": status, "source": source, "resolution": resolution, "publication_latency": latency,
            "best_indicator": best, "min_detectable_share": mds, "verdict": verdict, "note": note}


dims = {
    "pm_tape_prints": D("polymarket_internal", "have", "data-api /trades tapes (taker rows), wallet transactions excluded", "per trade",
                        "block time (~2 s after the match)", "activity n120 / n600 (presence baseline 0.8907 VALIDATE); last clean print (price 0.305-0.322)",
                        "drives", "co-occurrence: inside traded markets the OOF presence AUC of activity alone equals the rule's (0.9105 vs 0.910, E2); "
                        "the last clean print is the best historical price anchor but is late at informed moments (assumptions iter-13 check A)"),
    "pm_book_levels_queue_cancels": D("polymarket_internal", "have", "CLOB market websocket (shared recorder clob_wallets from 10-31; own recorder tommy_cs2_near)",
                                      "ms receive time", "real time", "others' best bid J at the burst (set unit 0.499 BUILD-live, X201); touch 0.452 per order",
                                      "drives", "co-reception: other makers re-price at the same ms (X180 / X154); live only (no pre-T0 history)"),
    "pm_other_wallets_feed_subscribers": D("polymarket_internal", "have", "V2 calldata signing ms of every filled order (79k public taker txs)",
                                           "ms (sign time)", "on chain at block time", "group-P coverage gp72 (selection v5); informed take clusters (E3-1)",
                                           "drives", "selection (v5 gain +0.084) and timing evidence of the push feed (>= 19 subscribers at fixed lags)"),
    "pm_listings_metadata": D("polymarket_internal", "have", "Gamma markets / events (listing-time fields)", "per market", "at listing",
                              "league / tier / GRID flag score (v4 / v5)", "drives", "selection AUC 0.970 VALIDATE; never a GRID event"),
    "pm_market_comments": D("polymarket_internal", "have", "Gamma /comments (parent_entity_type=Event, parent_entity_id) and events.commentCount, verified 11-01", "per comment", "post time",
                            "commentCount", "untested", "iteration 14: commentCount 0 in 40 of 40 sampled BUILD events (20 traded, 20 untraded); /comments empty: the dimension carries no content for these markets"),
    "pm_fees_rebates_rewards": D("polymarket_internal", "have", "Gamma feeSchedule, rewards params; activity MAKER_REBATE / REWARD rows", "per market / day",
                                 "listing / daily", "listing parameters 10-01..10-22 identical (C4b)", "untested",
                                 "the 10-16 switch is an account migration (iteration 13), not a policy change; rebate share of PnL not re-screened under the 11-01 rules"),
    "pm_operational_events": D("polymarket_internal", "proxy", "idle-gap scan (X106), status history not fetched", "minutes", "after the fact",
                               "group-P silence in idle gaps", "untested", "E7 found no cross-event synchrony of unexplained decisions (iteration 14; min_detectable_share 0.05)"),
    "pm_sports_websocket_scores": D("event_state", "have", "Polymarket sports websocket (shared recorder `sports`, from 10-31)", "per message", "real time",
                                    "", "untested", "live only; GRID CS2 round scores; no wallet record on VALIDATE-live blocks yet"),
    "pm_same_event_other_books": D("related_markets", "have", "tapes of map / match books; round handicap / totals listed (tapes not cached)",
                                   "per trade", "block time", "map -> match series slope 0.46 (BUILD, X198) / 0.49 (mechanics iter-13)",
                                   "drives", "the wallet writes one map value into the match book through a series map; the public match print moves 0.11 x"),
    "sportsbook_inplay_cs2_thunderpick": D("related_markets", "proxy", "Thunderpick odds via bo3.gg live index (own recorder tommy_tp_odds2, from 10-31)",
                                           "per update", "~seconds", "de-margined p (X144 frozen tests)", "untested", "no development match with both records yet"),
    "sportsbook_inplay_dota_hawk": D("related_markets", "have", "hawk.live archive (BetBoom, SpinBetter, Parimatch)", "per update", "archive",
                                     "de-margined line within 1c 0.54-0.63 vs print 0.60-0.70 (X172)", "untested",
                                     "E4 signature failed for three providers; other providers unarchived (family incomplete)"),
    "other_venue_sxbet": D("related_markets", "have", "SX Rollup fills decoded key-free (X145)", "per fill", "block time", "", "untested", "sparse esports coverage"),
    "other_venue_azuro": D("related_markets", "proxy", "Azuro on-chain bet events (X161 probe)", "per bet", "block time", "", "untested", "mapping not done"),
    "betting_exchange_apis": D("related_markets", "blocked", "Betfair / Pinnacle / sportsbook APIs (keys)", "", "", "", "untested", "keys needed (user)"),
    "push_feed_inround_events": D("event_state", "proxy", "co-subscribers' signing times (P4e, 0x2005d16a, the trio; group P / G)", "ms",
                                  "feed time (sign); public at block time", "informed take clusters (E3-1 I1 / I2)", "drives",
                                  "fan-out at fixed lags (wallet +50 ms behind P4e); maker re-pricings event-locked to messages (X136); its maker leg re-prices on messages it does not take (X183); vendor unknown"),
    "round_results_bo3": D("event_state", "have", "bo3.gg rounds (winners, end reasons, kills, plants, economy; no wall clock)", "per round", "after the fact (no timestamps)",
                           "in-round drift AUC 0.899 vs print 0.675 (X181)", "drives", "outcome-validated information in V; not point in time"),
    "feed_time_round_end_clock": D("event_state", "proxy", "informed take clusters, co-receiver signing clusters, print-inferred segments",
                                   "s", "feed time", "V ~ print(t + 20 s): 0.461 within one tick (information iter-13)", "inferred",
                                   "the price residual's main shape: failures pile up in the last 10-30 s of rounds (0.07-0.10 vs 0.33)"),
    "kill_level_inround_state": D("event_state", "missing", "demos (consent), HLTV scorebot (Cloudflare), stream OCR (consent)", "tick", "server time + delay",
                                  "", "untested", "information iter-13: V does not load on openers / plants; assumptions iter-13: V moves toward T in T eliminations without plant"),
    "dota_spectator_state_valve": D("event_state", "have", "Valve key-free realtime stats (own recorder tommy_dota_rt, from 10-31)", "4 s", "spectator delay",
                                    "", "untested", "X201: a 4-s-lagged value keeps 0.29 of the set unit; live only"),
    "dota_public_minute_state": D("event_state", "have", "OpenDota per-minute state (historical)", "60 s", "post-match", "inverse fit 0.17 within one tick (X167)",
                                  "untested", "family incomplete"),
    "stream_video_and_chat": D("event_state", "proxy", "Twitch / Kick chat (own recorders tommy_chat, tommy_kick_pdt); VOD needs consent", "s", "stream delay",
                               "", "untested", "X201: lagged inputs cannot carry the price item"),
    "lol_riot_livestats": D("event_state", "proxy", "feed.lolesports.com livestats (key-free), Leaguepedia game ids (rate-limited)", "10 s frames", "~live",
                            "", "untested", "X184 / X191: the operator's LoL quoting (earlier account) as a natural experiment"),
    "grid_official_data": D("event_state", "blocked", "GRID esports (signup)", "", "", "GRID flag (selection: never GRID)", "untested", "signup needs the user"),
    "settlement_oracle": D("event_state", "missing", "UMA / Polymarket resolution of match markets", "per market", "after the match", "", "untested",
                           "settlement-side only for in-play markets; not a plausible in-play input"),
    "news_rss_wires": D("information", "missing", "Google News RSS, GDELT (verified by the brief 11-01)", "per item", "first appearance", "", "untested",
                        "E5 selection screen (which matches it skips) not run"),
    "social_media": D("information", "proxy", "Reddit RSS, Telegram previews, Bluesky; X blocked", "per post", "post time", "", "untested", "E5"),
    "esports_schedules": D("information", "have", "Gamma schedule, bo3.gg match lists, liquipedia", "per match", "days ahead",
                           "league / tier score", "drives", "selection"),
    "own_resting_levels": D("own_state", "have", "own orders (B1) and the live book's own label", "ms", "own", "per-token persistence 0.417 VALIDATE (X198, own knowledge)",
                            "drives", "price ladder: the n highest free slots V..V-4 (X163)"),
    "own_inventory_pair_balance": D("own_state", "have", "own fills, merges", "per fill", "own", "merge law 300.22 + 7.28 x merges s", "drives",
                                    "exit: merges pairs on a ~300-s loop and holds the residual to resolution"),
    "own_pnl_drawdown_capital": D("own_state", "have", "activity (clamped to development periods)", "daily", "own", "", "untested",
                                  "every development day positive; no drawdown regime to test"),
    "operator_time_of_day": D("operator", "have", "listing times", "hour", "", "traded rate by start hour: 0 at 00-08 and 20-24 UTC, 0.11-0.27 at 08-20 (E2)",
                              "untested", "confounded with the schedule of the leagues it selects"),
    "operator_processing_loop_504ms": D("operator", "have", "live book (own label), historical signing times", "ms", "own", "504-ms loop phase (X158)", "drives",
                                        "timing of quiet re-pricings; period wanders 503-505 ms (sleep loop, mechanics iter-13)"),
    "operator_multi_account": D("operator", "have", "same-process census, owner keys, profile names (X176)", "per order", "on chain", "0-5 ms co-signing",
                                "drives", "one operator, four accounts; the 10-16 switch is an account migration"),
    "operator_human_reaction": D("operator", "have", "attention check vs concurrency (iteration 12 panel)", "", "", "elasticity -0.06", "untested",
                                 "E19 human desk closed by the attention check (no power statement)"),
    "infra_fanout_position_latency": D("infrastructure", "have", "signing-time lags behind P4e on the same token", "ms", "on chain", "+50 ms (wallet), +34 ms (Oct, earlier account)",
                                       "drives", "take race position; maker re-pricing at messages"),
    "infra_outages_restarts": D("infrastructure", "proxy", "idle gaps (X106), merge-loop phase breaks (X95)", "minutes", "after the fact", "", "untested",
                                "E7: no cross-event synchrony of unexplained decisions"),
    "feed_vendor_identity": D("event_state", "missing", "commercial esports data feeds (not identified; GRID excluded by selection)", "ms", "push",
                              "", "untested", "iteration 14: the operator's sports account shows no push-feed play reaction (MLB), so the feed is an esports product; the private-value design starts 09-17"),
    "infra_rate_limits": D("infrastructure", "missing", "", "", "", "", "untested", "not observable from the public record"),
}
S["dimensions"] = dims

# ------------------------------------------------------------------ indicators: legacy rows + this iteration
LEG = [
    ("A5", "sports_socket_vs_espn_vs_signing", "pm_sports_websocket_scores", "Polymarket sports websocket latency against ESPN / the wallet's signing", "score update"),
    ("X103", "provider_latency_socket_vs_market", "pm_sports_websocket_scores", "sports socket vs market reaction (provider latency)", "score update"),
    ("X65", "push_feed_cosigner_fanout", "push_feed_inround_events", "co-subscribers' signing lags on the same token", "informed take"),
    ("X111", "wallet_minus_P4e_lag_by_event_class", "push_feed_inround_events", "wallet - P4e lag by event class, MixedLM", "informed take"),
    ("X126", "fanout_delivery_structure", "push_feed_inround_events", "order consistency, common mode, queue load of the fan-out", "informed take"),
    ("X136", "cascade_lock_event_vs_leader", "push_feed_inround_events", "co-receiver cascade: event-locked vs leader-locked re-pricing", "P4e message"),
    ("X183", "declined_messages_maker_leg", "push_feed_inround_events", "wallet maker orders within +-30 ms of informed clusters it does not take", "informed cluster"),
    ("X180", "triggered_adds_coreception", "pm_book_levels_queue_cancels", "non-own same-book changes before its adds vs book arrival", "book change"),
    ("X175", "withdrawal_triggers", "pm_book_levels_queue_cancels", "latest non-own change on any book before an event-wide withdrawal", "book change"),
    ("X182", "lead_of_level_on_trades", "pm_tape_prints", "offset of uncensored adds vs later public VWAP", "own add"),
    ("X186", "joiner_free_lead", "pm_book_levels_queue_cancels", "lead of its level on a joiner-free mid", "own add"),
    ("X174", "slow_filter_prints", "pm_tape_prints", "EMA of clean prints (half-lives 0-180 s) as its level", "level"),
    ("X177", "signed_public_delta_rules", "pm_book_levels_queue_cancels", "own top + 1c x sign(last-second mid move)", "mid move >= 0.5c"),
    ("X181", "inround_drift_vs_bo3_winner", "round_results_bo3", "its level's within-round drift vs the round winner (print-inferred rounds)", "round"),
    ("X171", "mr12_hmm_clock_free", "round_results_bo3", "clock-free HMM of its levels against an MR12 / MR3 table vs 200 permutations", "round"),
    ("X160", "round_economy_at_starts", "round_results_bo3", "level minus print vs equipment difference at inferred round starts", "round start"),
    ("X125", "P4e_round_winner_alignment", "round_results_bo3", "P4e take sequence vs bo3 round winners", "round"),
    ("X50", "take_event_types", "round_results_bo3", "take-event share per team vs dW / dFK / dBP / dCL (binomial GLM)", "round"),
    ("X119", "dota_bursts_vs_kills", "dota_public_minute_state", "Dota maker bursts 0-6 s after kills on the feed clock", "kill"),
    ("X167", "dota_inverse_fit_public_state", "dota_public_minute_state", "Dota value vs public per-minute state with placebo clocks", "minute"),
    ("X123", "dota_game_state_fair_value", "dota_public_minute_state", "Dota fair value from 160 OpenDota pro matches as the maker anchor", "minute"),
    ("X172", "hawk_bookmaker_lines_dota", "sportsbook_inplay_dota_hawk", "de-margined bookmaker lines vs its Dota value (clock-free alignment)", "line update"),
    ("X145", "sxbet_second_venue", "other_venue_sxbet", "SX Bet fills vs its quotes", "fill"),
    ("X161", "azuro_probe", "other_venue_azuro", "Azuro bet events on Polygon / Gnosis", "bet"),
    ("X114", "multisport_fanout", "push_feed_inround_events", "co-signing in football / NBA / tennis", "informed take"),
    ("X120", "grid_natural_experiment", "grid_official_data", "GRID vs non-GRID events: decoded GRID-event txs", "event"),
    ("X106", "outages_idle_gaps", "infra_outages_restarts", "idle-but-up gaps vs group-P silence", "gap"),
    ("X158", "loop_504ms_phase", "operator_processing_loop_504ms", "504-ms loop phase and tick attribution", "loop tick"),
    ("X176", "same_process_accounts", "operator_multi_account", "0-5 ms co-signing census; owners; names", "own order"),
    ("X173", "map_match_coupling", "pm_same_event_other_books", "same-tick map / match re-pricings vs series sensitivity", "own burst"),
    ("X97", "thunderpick_or_chat_first", "sportsbook_inplay_cs2_thunderpick", "legacy esports odds / chat check", "update"),
]
rows = []
for cid_, name, dim, definition, event in LEG:
    c = cat.get(cid_)
    if not c:
        continue
    st = c.get("status")
    verdict = {"tried": "see evidence", "ruled_out": "no_effect (legacy; no power statement)", "infeasible": "infeasible"}.get(st, st)
    rows.append(ind.ledger_row(name, dim, definition, event, {"catalog_id": cid_, "status": st, "evidence": c.get("evidence"),
                                                             "source": c.get("source")}, "legacy", verdict))
if e2:
    e7 = e2["e7_residual_clustering"]
    for dl in ("0.5", "2.0", "10.0"):
        x = e7[f"delta_{dl}"]["unexplained"]
        rows.append(ind.ledger_row(f"e7_residual_clustering_delta_{dl}s", "infra_outages_restarts",
                                   "out-of-fold BUILD presence misses (signing bins below the median OOF p), signing times, market key = event, >= 10 min after start",
                                   f"cross-event coincidence within {dl} s", {"ratio": x.get("ratio"), "p": x.get("p"), "near": x.get("near"), "band": x.get("band"),
                                                                              "n_units": e7["events"], "n_events": e7["unexplained_orders"],
                                                                              "min_detectable_share": e7p.get("min_detectable_share")}, "BUILD",
                                   "no_effect" if (x.get("p") or 0) > 0.01 else "drives"))
if lag:
    rows.append(ind.ledger_row("lag_tolerance_price_item", "dota_spectator_state_valve / stream_video_and_chat (lagged public state)",
                               "frozen X163 machine with V = own value path at t - L (BUILD-live)", "burst",
                               {"set_unit_by_L": {k: lag[k]["all"]["set_unit"] for k in lag if k.startswith("L_")},
                                "V_change_by_L": {k: lag[k]["V_change"]["set_unit"] for k in lag if k.startswith("L_")},
                                "oracle": lag["oracle_L0_V_after"]["all"]["set_unit"], "public_J": lag["public_J"]["all"]["set_unit"]}, "legacy",
                               "lagged inputs cannot carry the price item"))
for r in (e3 or {}).get("build", {}).get("rows", []):
    rr = dict(r)
    rr["q_bh"] = rr.get("q_bh_family")
    rr["signed_q_bh"] = rr.get("signed_q_bh_family")
    rows.append(ind.ledger_row(f"E3-1_{r['name']}_{r['range']}", "push_feed_inround_events" if r["name"].startswith(("I1", "I2")) else "pm_tape_prints",
                               "E3-1 pre-registered (NOTES iteration 14)", r["name"], rr, "BUILD",
                               "survivor" if (rr.get("q_bh") or 1) <= 0.10 or (rr.get("signed_q_bh") or 1) <= 0.10 else "no_link_on_BUILD (no power statement)"))
for r in (e3 or {}).get("validate", []):
    rows.append(ind.ledger_row(f"E3-1_{r['name']}_{r['range']}", "push_feed_inround_events" if r["name"].startswith(("I1", "I2")) else "pm_tape_prints",
                               "E3-1 VALIDATE confirmation (one-sided alpha 0.01, Holm)", r["name"], r, "VALIDATE",
                               "confirmed" if r.get("confirmed_alpha_0.01") else "not_confirmed (stays untested without power)"))
S["indicators"] = rows

# ------------------------------------------------------------------ catalog: E1-E7, X189-X203
src13 = "panel iteration 13"


def put(k, status, source, evidence):
    cat[k] = {"status": status, "source": source, "evidence": evidence}


put("E1", "tried", "BRIEF 11-01", f"state.json dimensions: {len(dims)} entries over the seven families (iteration 14), each with status, source, resolution, latency, best indicator and verdict; missing / blocked ones carry their to-do.")
if e2:
    put("E2", "tried", "BRIEF 11-01", f"Out-of-fold BUILD residuals (code/iter14/e2_residuals.py, results/e2_residuals.json): GroupKFold(5) over 2-h blocks; rule = activity + listing meta with OOF league rate: OOF AUC {e2['oof_auc_rule']} vs activity {e2['oof_auc_activity_b0']}; inside traded markets {e2['oof_auc_rule_in_traded_markets']} vs {e2['oof_auc_b0_in_traded_markets']} (timing inside markets = co-occurrence); selection OOF league AUC {e2['selection_oof_auc_league_rate']}, 0 traded events missed, 6 false alarms (PGL 4, Stake Pulse 2); in-market residual largest in the first 60 min of play (AUC 0.75-0.78 vs 0.89-1.0 later). Price residual (68% of orders off the last print) piles up at round ends. NOTES 'Missing dimensions'.")
put("E3", "tried" if e3 else "open", "BRIEF 11-01", "E3-1 (event state: push-feed proxies and public tape events) pre-registered in NOTES iteration 14 and screened on BUILD with BH; survivors confirmed on VALIDATE (results/e3_screen.json). " + (ext.get("e3_summary", "") if ext else ""))
put("E4", "open", "BRIEF 11-01", "Legacy discrepancy tests: bookmaker lines minus print (X172 Dota; X144 Thunderpick waits), MR12 / side tables (X171, X181 step 4), Dota game-state fair value (X123). Composite event indicators (round-end detector on the event's books) not built.")
put("E5", "open", "BRIEF 11-01", "News / social / official sources against selection (which matches it skips) not screened; chat recorders exist (X38 / X87).")
put("E6", "open", "BRIEF 11-01", "Legacy latent fits (X171 clock-free HMM; X181 in-round drift) have no incremental_auc over co-occurrence + self-excitation baselines and no event study of the latent's changes yet.")
if e2:
    e7 = e2["e7_residual_clustering"]
    put("E7", "tried", "BRIEF 11-01", "residual_clustering of out-of-fold BUILD presence misses (signing times of maker orders whose signing bin is under-predicted, >= 10 min after start, market key = event, "
        f"{e7['unexplained_orders']} orders in {e7['events']} events): ratio {e7['delta_0.5']['unexplained']['ratio']:.2f} / {e7['delta_2.0']['unexplained']['ratio']:.2f} / {e7['delta_10.0']['unexplained']['ratio']:.2f} at 0.5 / 2 / 10 s, "
        f"p {e7['delta_0.5']['unexplained']['p']:.2f} / {e7['delta_2.0']['unexplained']['p']:.2f} / {e7['delta_10.0']['unexplained']['p']:.2f}; all signings {e7['delta_2.0']['all_signings']['ratio']:.2f} (p {e7['delta_2.0']['all_signings']['p']:.2f}) at 2 s: no cross-event synchrony (no common driver at second scale). Power (results/e7_power.json): min_detectable_share {e7p.get('min_detectable_share')} (planted 0.5-s cross-event coincidences, 3 of 3 runs).")
for k, v in ext.get("catalog", {}).items():
    cat[k] = v
S["catalog"] = cat
S["live_split_e3_note"] = "Live-only dimensions: the iteration-6 live split (BUILD-live 10-31 12-18, VALIDATE-live 11-01 06-12 and later development blocks) is kept (it predates the brief's default split)."
for k in ("strategy_statement", "components", "target_metrics_notes_iter14", "next_steps", "progress_gauges"):
    if k in ext:
        S[k] = ext[k]
if "iteration" in ext:
    S["iterations"] = [x for x in S["iterations"] if x.get("n") != 14] + [ext["iteration"]]
if "hypotheses" in ext:
    S["hypotheses"] += ext["hypotheses"]
S["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(S, open(WS / "state.json", "w"), indent=1)
print("dimensions", len(dims), "indicators", len(rows), "catalog", len(cat), "open", sum(1 for v in cat.values() if v.get("status") == "open"))
