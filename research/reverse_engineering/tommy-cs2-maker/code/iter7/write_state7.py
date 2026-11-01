"""Iteration 7 state.json update (catalog X87-X100, live lab, live split, components, hypotheses, iteration entry)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
P = ROOT / "research/reverse_engineering/tommy-cs2-maker/state.json"
s = json.loads(P.read_text(encoding="utf-8"))
cat = s["catalog"]

cat["X87"] = {"status": "open", "source": "information panel P1 (iter 6): within-channel chat clock with two anchor classes and map-end calibration",
              "evidence": "Pre-registered in NOTES iteration 7 (anchor classes a-d, peak lags with anchor bootstrap, Delta = L_b - L_c pooled by inverse variance, decision table) before any 11-01 record exists. tommy_chat v2 has no development-block records yet (it started 10-31 18:16 UTC, inside a sealed block); runs on 11-01 06-12 and later development blocks."}
cat["X88"] = {"status": "open", "source": "information panel P2 (iter 6): Dota 2 spectator feed with Valve's known delay as the key-free in-game clock",
              "evidence": "Recorder widened (code/iter7/dota_live_recorder_v2.py, pid 4452, from 1793488489): every Polymarket Dota 2 event in play (v1: PARI Universe only), 15-s polls, records filed by unit through unit_writer (30-min fail-closed margin), hard stop 11-03 00:00 UTC. The lead statistic needs development blocks with Dota events in play. Side fact (coreceivers): none of P4e / 0x2005d16a / 0x51dbdd2b co-signs the wallet's 67 Dota takes of 16-22 Oct."}
cat["X89"] = {"status": "tried", "source": "information panel P3 (iter 6): Polymarket's slow flow as the broadcast's footprint, by anchor class",
              "evidence": "retail_anchor.json (16-22 Oct): retail (<= 20 orders) net flow on the bought team minus shifted controls is contra in 0-12 s after both pack-only (1,480 / 1,548 anchors) and isolated wallet-led bursts (90 / 133); the sustained turn comes at 76 vs 84 s (BUILD) and none within 120 s vs 36 s (VALIDATE); event-bootstrap differences [-48, +84] and [-36, +72] s. Retail trades against the repricing and turns late and unstably: it cannot place either source on the broadcast chain (ruled out as a clock by this measurement, as X40 for takes)."}
cat["X90"] = {"status": "open", "source": "information panel P4 (iter 6): name the source class from the games it serves",
              "evidence": "Partial (coreceivers): the shared push feed's subscribers P4e and 0x2005d16a are CS2-only in the wallet's markets (P4e 1 Dota take, 0x2005d16a none) and none co-signs the wallet's 67 Dota takes, so its Dota input is not that feed (or that feed's Dota product has other subscribers). Not run: 0x51dbdd2b's re-quote hazard in Valorant / LoL markets (needs the matched-order record of those markets) and the wallet's Dota take profile on the server clock (needs a development block with its Dota takes)."}
cat["X91"] = {"status": "open", "source": "information panel P5 (iter 6): Polymarket's own live channels beyond the 20-s sports socket",
              "evidence": "Not run: the blocks during iteration 7 (10-31 18-24, 11-01 00-06) are sealed, and the test needs a development-start event page in play; scheduled for 11-01 06-12."}
cat["X92"] = {"status": "tried", "source": "mechanics panel P1 (iter 6): validate the own-level label against calldata, re-run and re-freeze the live rules before 11-01 06-12",
              "evidence": "label_validate.json: 873 of 1,037 filled maker orders (all makers) linked to their book add; the iteration-6 size label F_mkt precision 0.765 (recall 1.0), single 100-share adds 0.506, multi-level bursts 0.930, odd sizes 0.980; validated label = F_mkt and (burst or odd size). Re-runs: live_price_relabel.json frozen join 0.424, validated join 0.419, touch 0.471 (172 orders) -> live price re-frozen to the touch (final_rule.LIVE_PRICE_PRIMARY); wave_lock_valid.json: pull share at pack-only events 16.7% (frozen 48%), busy-phase control 10%, 4 events with a pull after the signing -> H62 withdrawn; own-take pull kept (87%, 14-16 ms); timer_attrib.json: 1.5-s re-post on odd wallet sizes 11 vs 0.5 per control window, 100-share excess 227 vs 57 not attributable -> H69 kept for odd sizes. New VALIDATE-live pre-registrations in NOTES iteration 7 and live_split."}
cat["X93"] = {"status": "tried", "source": "mechanics panel P2 (iter 6): identify the client software from its fingerprints",
              "evidence": "warproxxx/poly-maker README (Python; merging via Safe / proxy not wired, exits by limit sells) and quenos/poly-maker trading.py (merge once per trade cycle when both sides >= MIN_MERGE_SIZE, 2-s loop, stop-loss / take-profit SELL orders, buys only in [0.1, 0.9)) fail the wallet's fingerprints (300-s merge timer, never sells). One web search found no public bot with a 300-s sequential merge loop. The merge law is shared by two other BUY-only whole-cent makers in its markets (0xf1f2b3c6, 0x52661b8e; merge_siblings.json), not phase-locked to it: a shared design, not a findable repo."}
cat["X94"] = {"status": "tried", "source": "mechanics panel P3 (iter 6): untriggered re-quotes as a dense label of the private feed",
              "evidence": "untriggered_othersmid.json (BUILD-live, validated label, others' mid, 2,000 within-book shifts): untriggered pulls (no public event on any book of the event in 300 ms, no timer, no take) n 213: -0.22 / -0.60 / -0.65c at 2 / 10 / 30 s (p < 0.0005 / < 0.0005 / 0.0005); triggered pulls -0.07 / -0.03 / +0.07; untriggered adds +0.18c at 2 s only; triggered adds +0.53 / +0.65 / +0.88c (public follow). Not failed takes (FAK-return re-post 3.8% vs triggered 4.9%, null 0.7%; untriggered_fak_signature.json); a threatening taker follows within 3 s in 7.5% (null 4.0%; untriggered_pulls2.json). 2.6x its takes in the window. Pre-registered for VALIDATE-live (10-s markout < 0 at p < 0.0025)."}
cat["X95"] = {"status": "tried", "source": "mechanics panel P4 (iter 6): the merge loop as the process clock (uptime, restarts, versions, siblings)",
              "evidence": "merge_loop.json: no merge in the taker regime; first merge 10-16 13:45:00 UTC; law 300.22 s + 7.28 s x merges (SD 1.33 s), 99.2% phase-continuous; 6 overnight breaks: daily runs starting 08:10-09:04 UTC (10-18 14:17), ending 16:40-23:30; first order 9-99 s after the first pass; 3 of 8 >= 30-min order gaps inside runs; non-GRID events inside runs traded 33.5% vs 14.3% outside; ramps not tied to restarts (2 of 7). merge_siblings.json: of 36 wallets (30 top makers + subscribers), 0xf1f2b3c6 (91.9%, min merge 20) and 0x52661b8e (95.9%, min merge 40) follow the law, neither phase-locked (8.9-9.1%); all others 0-31%."}
cat["X96"] = {"status": "open", "source": "mechanics panel P5 (iter 6): recover the client's PRNG state from the salts",
              "evidence": "Not run (needs z3 in a separate folder for the JSC / SpiderMonkey family; the panel's V8 weak form was negative). New context: round(U x Date.now() ms) is also the salt of P4e, 0x2005d16a, 0x51dbdd2b, P93 and 0xf1ee4842 (the TypeScript client default), so a recovered stream would identify processes, not the software."}
cat["X97"] = {"status": "tried", "source": "assumptions panel P1 (iter 6): the input is a shared push feed; co-receivers as instruments",
              "evidence": "coreceivers.json: P4e 203 co-signs on 44 events, -50 ms, event SD 9.1 ms, Kick - Twitch +2 ms [-7, +12]; 0x2005d16a 49 on 20 events, -20 ms, event SD 6.8 ms, +9 [-6, +23.5] -> pre-registered verdict: shared push feed. fanout_subscribers.json: lags to P4e equal on P4e-alone and co-signed events (0x2005d16a +25 / +44, 0xf1ee4842 +209 / +149, 0x8a80528d +203 / +220, 0xddb6e624 +203 / +217, P93 +404 / +385 ms; shift null 1-6 pairs). census_p4e_types.json: P4e-alone bursts load on round wins (dW +1.09, p 2e-4), not plants (dBP -0.54, p 0.08); wallet-without-P4e bursts on plants (dBP +1.29, p 0.045). Dota: no co-signs. Step 2 (live calibration) pending: P4e / 0x2005d16a absent from the 10-31 12-18 dev markets."}
cat["X98"] = {"status": "open", "source": "assumptions panel P2 (iter 6): score selection out of time on every development block after T0",
              "evidence": "exam_params.json (listing projection, aggregates): delay, clear-book, fee, rebate and reward parameters identical in 16-22 Oct, h1, h2 and the T0+ blocks. final_rule_v3_devblock_iter7.json: forward block 20 events, v3 AUC 0.797, recall 0.25 (1 of 4), lift 5.0; 'non-GRID and tier <= 4' 3 of 4 at lift 3.75; v3-tier logistic VALIDATE 0.926 / 0.556 / 3.23 (results/selection_variants.json). Pre-registered: pooled forward evaluation from 11-01 06:00, switching rule, schedule test via the first MERGE pass of 11-01. Open until the forward blocks are scored."}
cat["X99"] = {"status": "tried", "source": "assumptions panel P3 (iter 6): re-open Y1 on the taker module",
              "evidence": "coreceivers.json part B / coreceivers_nofollow.json: 1,883 census bursts with P4e, wallet presence 9.9%; raw presence rises with the edge P4e left (8.7% -> 30.6% at large edge) but with the wallet's followers excluded the edge effect is n.s. (log1p coef +0.065, p 0.17; large 23.3%), presence follows reversal (+0.61 / -0.52) and P4e's full fill (+1.02); large-edge same-team bursts 0 of 5. With equal subscriber lags on both kinds, the round-win absence is the wallet's selectivity (narrower subscription or kind filter), not an edge policy. Step 3 (live) pending."}
cat["X100"] = {"status": "tried", "source": "assumptions panel P4 (iter 6): price unit = a target ladder kept by hole-filling",
               "evidence": "hole_fill.json (BUILD-live; N fitted on the first half = 4): second half, all own adds within one tick 0.496 (frozen tracker) / 0.482 (validated) vs join 0.465 / 0.462 and own top 0.436 / 0.406; single adds 0.533 / 0.520 vs join 0.495 / 0.488; filled orders 0.35-0.36 vs join 0.465 and own top 0.57-0.60. A small gain on adds, none on fills; far below the 0.7 signature: the price ceiling stays below 0.8."}

s["live_lab"] = [x for x in s["live_lab"]]
for x in s["live_lab"]:
    if "tommy_dota_live" in x.get("what", "") and x.get("start") == 1793465020:
        x["end"] = 1793488460
        x["what"] += "; STOPPED 10-31 23:14 UTC (iteration 7), replaced by v2"
s["live_lab"].append({"what": "own recorder v2, feed tommy_dota_live (code/iter7/dota_live_recorder_v2.py): OpenDota /api/live league games every 15 s while ANY Polymarket Dota 2 event is in play (Gamma series 10309 checked every 10 min); records filed by unit through code/iter5/unit_writer.py (sealed if the game's activate_time or that time - 30 min is sealed) and by receive time; detached (pid 4452), hard stop 2026-11-03 00:00 UTC, 150 MB cap",
                      "start": 1793488489, "end": 1793664000})
ls = s["live_split"]
ls["frozen_live_rules"] = [
    "final_rule._live_price, re-frozen in iteration 7: primary = the touch (full-book best bid on the order's token at sign - 100 ms; BUILD-live 0.471), join with the iteration-6 label as secondary (0.424), LIVE_VIEW_MS 100, PAIR_CAP 0.99",
    "H69 1.5-s same-price re-post timer on odd wallet sizes: spike / control >= 3 (BUILD-live 11 vs 0.5)",
    "X94 untriggered validated pulls (code/iter7/untriggered_v2.py): 10-s others'-mid markout < 0 at p < 0.0025 (BUILD-live -0.60c, p < 0.0005)",
    "event-locked own-take pull (u - p 11-19 ms, BUILD-live 87% on the validated label)",
    "live_occupancy.py recipe (refit only on BUILD-live)"]
ls["withdrawn"] = ["H62 wave follower (iteration 7: not established on the calldata-validated label; 16.7% pull share at pack-only events vs 10% control, 4 usable events)"]
ls["note_iter7"] = "re-frozen 2026-10-31 ~23:20 UTC, before any 11-01 record exists"

comp = s["components"]
comp["selection"]["description"] = ("Whole events of non-GRID CS2 leagues (never a GRID event: 0/122); event logistic (league rate with GRID zeroing + pre-game popularity) VALIDATE AUC 0.954 vs activity 0.892 (gain +0.062, p 0.002), recall 0.72 at lift 3.3. "
    "The maker process runs in daily sessions (merge-loop runs, starting 08:10-09:04 UTC, ending 16:40-23:30): non-GRID events inside a run traded 33.5% vs 14.3% outside. "
    "Forward dev block 10-31 12-18: v3 recall 1 of 4 (3 traded events in FiReSPORTS, a league v3 never saw); tier rule 'non-GRID, tier <= 4' 3 of 4 at lift 3.75; a forward evaluation with a switching rule is pre-registered (X98). Exam-day listing parameters unchanged.")
comp["timing"]["description"] = ("Taker: messages of a shared CS2 push feed with >= 6 subscribers at fixed lags (P4e 0, 0x2005d16a +25, the wallet +50, three at ~+200, P93 ~+400 ms; event SD 7-9 ms, no platform effect): "
    "the wallet acts on the plant / turn kind (first informed move against the previous burst; per-map plants p 0.045) and skips the round-win kind that every other subscriber takes, with no edge-based decline (edge effect n.s. once its followers are removed). "
    "Maker: at its own takes it pulls the complement at +11-19 ms (event-locked, before any public cancel in 75%); between takes 15.5% of its validated pulls have no public trigger in the whole event and precede a -0.6c move of the others' mid in 10 s (p < 0.0005, BUILD-live): the private input reaches the ladder ~2.6x as often as it takes. The iteration-6 wave-follower reading is withdrawn (label artefact).")
comp["timing"]["confidence"] = 0.6
comp["price"]["description"] = ("Maker: whole-cent BUYs near the touch, one side per burst, pair sum capped near 0.99; historical last-print anchor 0.305 (VALIDATE, the rule metric). Live (BUILD-live, 172 filled orders): touch 0.471, join (others' best) 0.424 / 0.419 with the validated label; "
    "hole-filling of a 4-level target ladder 0.48-0.50 on adds (join 0.46) but 0.35 on fills (own top 0.54-0.60). No unit reaches 0.8 from public book state or own state. Taker: limit = stale ask + a premium scaling with the event.")
comp["exit"]["description"] = ("Never sells. Pulls the complement at its takes and re-posts ~1.04 s later; pulls bids on private adverse events between takes (untriggered pulls); merges complete pairs in a 300-s loop (300.22 s + 7.28 s per merge, minimum 100 shares; a shared design: two other makers follow it) and holds the residual. "
    "Pair cost 0.978. The iteration-6 public-wave-follower exit is withdrawn (label artefact).")
comp["exit"]["confidence"] = 0.75

hyp = s["hypotheses"]
hyp += [
 {"id": "H75", "family": "information source structure", "description": "Z1: the taker events are messages of a shared CS2 push feed (>= 6 subscribers at fixed lags); the wallet acts on its plant / turn kind only.",
  "validate_metrics": {"p4e_event_sd_ms": 9.14, "p4e_kick_minus_twitch_ms_ci95": [-7.0, 2.0, 12.0], "r2_event_sd_ms": 6.82, "subscriber_lags_alone_vs_cosigned_ms": {"0x2005d16a": [25, 44], "0xf1ee4842": [209, 149], "0x8a80528d": [203, 220], "0xddb6e624": [203, 217], "P93": [404, 385]}},
  "verdict": "supported (pre-registered fan-out verdict: shared push feed; the other subscribers take both kinds at their usual lags)"},
 {"id": "H76", "family": "taker policy", "description": "Z2 / Y1 on the taker module: it sees round wins and declines them by the edge left.",
  "validate_metrics": {"presence_large_edge_raw": 0.306, "presence_large_edge_no_followers": 0.233, "logit_log1p_edge_left": [0.065, 0.168], "large_edge_same_team_taken": "0 of 5"},
  "verdict": "not supported (edge effect is its followers; presence follows the event kind)"},
 {"id": "H77", "family": "maker information", "description": "Z4: the private input reaches the maker leg between takes (untriggered validated pulls precede adverse moves).",
  "validate_metrics": {"n": 213, "markout_others_mid_c": {"2s": -0.223, "10s": -0.601, "30s": -0.646}, "p_lower": {"2s": 0.0, "10s": 0.0, "30s": 0.0005}, "fak_return_share": 0.038, "threat_within_3s": 0.075},
  "verdict": "supported on BUILD-live; pre-registered for VALIDATE-live (11-01 06-12)"},
 {"id": "H78", "family": "label validity", "description": "The size fingerprint used for 'own levels' since iteration 3.",
  "validate_metrics": {"F_mkt_precision": 0.765, "single_100_precision": 0.506, "burst_precision": 0.93, "odd_size_precision": 0.98},
  "verdict": "contaminated; validated label = burst or odd size; H62 withdrawn, live price re-frozen to the touch"},
 {"id": "H79", "family": "process clock", "description": "Z5: the maker process runs in daily sessions (merge-loop runs), which shape part of the selection.",
  "validate_metrics": {"law_resid_sd_s": 1.33, "continuous_share": 0.992, "runs": 7, "traded_inside_vs_outside": [0.335, 0.143]},
  "verdict": "supported as a description (own activity; not an exam feature); clock-change test pre-registered"},
 {"id": "H80", "family": "bot software", "description": "Z7: the maker client is a public bot (poly-maker family).",
  "validate_metrics": {"poly_maker_merge": "per trade cycle, no timer", "poly_maker_sells": True, "wallet_sells": False},
  "verdict": "rejected for the poly-maker family; the 300-s merge law is shared by 0xf1f2b3c6 and 0x52661b8e (not phase-locked)"},
 {"id": "H81", "family": "price", "description": "X100: each add fills the highest hole of a target ladder {J..J-3c}.",
  "validate_metrics": {"adds_second_half": 0.496, "join": 0.465, "fills": 0.351, "own_top_fills": 0.573},
  "verdict": "rejected as a price rule (small gain on adds, loss on fills)"},
]

s["iterations"].append({"n": 7, "minutes": 100, "best_validate_score": 0.8721,
    "paradigm": "shared push feed decoded through its other subscribers' signing times (fan-out variance components, subscriber lags by event kind, edge-left policy test) plus the maker leg's actions on a calldata-validated own-level label (untriggered pulls as a label of the private input; merge loop as the process clock)",
    "families": ["own-level label validation against calldata (X92) and re-runs of live price / wave follower / timer", "fan-out variance components of co-signers (X97)", "subscriber lags on P4e-alone vs co-signed events", "event kinds of P4e-alone vs co-signed bursts (X97 / X99)", "edge-left taker policy test with follower exclusion (X99)", "untriggered pulls / adds markouts on the others' mid with FAK-return and threat checks (X94)", "merge-loop process clock and sibling law scan (X95)", "exam-day listing parameters (X98)", "forward-block selection and league-free variants (X98)", "retail flow by anchor class (X89)", "public bot code read (X93)", "target-ladder hole filling (X100)", "Dota recorder widened (X88)", "salt generators of the subscribers"]})
s["status"] = "continue"
s["wall_reason"] = None
s["strategy_statement"] = (
    "CS2 (and some Dota 2) in-play bot; from 10-16 a buy-only two-sided maker plus an informed taker, before that a round-trip taker in GRID tier-1/2 events that traded late. "
    "[VALIDATE-only] Selection: whole events (match + all maps) of non-GRID tier-3/4 leagues, never an event with a GRID series id (0/122), favouring popular events; event rule AUC 0.954 vs activity 0.892; the maker process runs in daily sessions (about 08:10-09:00 to 17:00-23:30 UTC) and skips events outside them. "
    "[VALIDATE-only] Maker: whole-cent BUY ladders (100 shares, or an event-wide size ramping from ~50 to 100) near the touch on both outcome tokens, re-quoted one side at a time with the pair sum capped near 0.99, never sells, merges pairs every 300 s (97% paired, pair cost 0.978). "
    "[hypothesis, BUILD-live] Protection: at its own takes it pulls the complement at +11-19 ms and re-posts it ~1.04 s later; between takes it pulls the bids of the team about to lose value on private events (untriggered pulls, -0.6c in 10 s, ~2.6x its take rate). "
    "[hypothesis] Taker: FAK BUYs on messages of a shared CS2 push feed that at least five other wallets receive at fixed lags (P4e 50 ms earlier); it takes the plant / turn kind (the first informed move against the previous burst) and skips the round-win kind the others take, at the stale ask plus a premium; ~16-20% of the informed bursts in its markets. "
    "[VALIDATE-only] Economics: the per-market PnL is the locked margin of pairs formed across the two legs (0.82 / 0.75); the maker leg alone reaches 0.38 / 0.34 and an activity-only baseline 0.51 / 0.37, so the outcome item needs the private taker leg.")
s["next_steps"] = [
    "11-01 06-12 (VALIDATE-live): score the iteration-7 pre-registered live rules unchanged (touch price, H69 odd sizes, X94 untriggered pulls, own-take pull), X87 chat clock, X91 Polymarket live channels (browser, dev unit), X97 step 2 (P4e / 0x2005d16a match - sign) and X99 step 3 if they trade; the schedule test (first MERGE pass).",
    "X98 forward selection pooled over the development blocks from 11-01 06:00 with the pre-registered switching rule (v3 vs v3-tier vs tier rule).",
    "X90 (0x51dbdd2b in Valorant / LoL), X96 (salt PRNG with z3 in a separate folder), the merge-law siblings 0xf1f2b3c6 / 0x52661b8e as same-software controls.",
    "Ask the user: live HLS playlist / chat route (X53), demos (X37), PandaScore token (X55), HLTV page checks (X64), odds probes (X48), Kick VOD segments (X4 / X22)."]
s.setdefault("data_bugs", [])
s["data_bugs"].append("iteration 7: exam_params.py first run also counted the state field acceptingOrders per lot (h1 / h2 / sealed T0 included); removed from results/exam_params.json and from the script; not used anywhere.")
tmn = s.get("target_metrics_notes", {})
tmn["price"] = (tmn.get("price", "") + " | Iteration 7: the own-level size label is 76.5% precise (calldata-validated); live filled orders: touch 0.471, join 0.424 (validated 0.419); live price re-frozen to the touch for VALIDATE-live; hole-filling 0.35 on fills.")
tmn["selection_forward"] = "Iteration 7: frozen v3 on the 10-31 12-18 development block (20 events): AUC 0.797, baseline 0.438, recall 0.25 (1 of 4), lift 5.0; pooled forward evaluation with a switching rule pre-registered (X98)."
s["target_metrics_notes"] = tmn
P.write_text(json.dumps(s, indent=1), encoding="utf-8")
op = [k for k, v in s["catalog"].items() if v.get("status") == "open"]
print("open", len(op), op)
