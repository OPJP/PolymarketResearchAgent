"""Iteration 5: update state.json (catalog X53-X69, hypotheses H46-H57, components, live_lab, iteration entry)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
P = ROOT / "research/reverse_engineering/tommy-cs2-maker/state.json"
shutil.copy(P, ROOT / ".cache/re/tommy-cs2-maker/state_backup_iter4.json")
s = json.loads(P.read_text(encoding="utf-8"))
cat = s["catalog"]

cat["X38"]["evidence"] += (" | Iteration 5: v2 recorder (code/iter5/chat_recorder_v2.py, worker pid 536) records in EVERY block (channels from"
                           " listing-time fields; records of sealed-start units filed sealed by unit_writer.UnitWriter), so the future-block"
                           " examiner gets the chat clock. Pre-registered rule (NOTES iteration 5): chat peak in [60, 300] s after its takes ->"
                           " V1 (upstream of the broadcast), in [0, 20] s -> V2 (stream-derived); +-600-s shift null, p < 0.0025. First data in"
                           " the 11-01 06-12 development block.")
cat["X47"]["evidence"] += (" | Iteration 5: v2 round recorder (code/iter5/round_recorder_v2.py, worker pid 8668) records in every block, all"
                           " non-GRID CS2 round / handicap / total markets chosen from listing-time fields; live test still pending (11-01 06-12).")

new = {
    "X53": {"status": "open", "source": "information panel P1 (iter 4): Twitch VOD chat replay as a historical broadcast clock for 16-22 Oct",
            "evidence": "Pre-registration written (NOTES iteration 5, X38 rule: peak [60, 300] s -> V1, [0, 20] s -> V2). The only route to"
                        " VOD metadata and chat replay without an account is gql.twitch.tv with the web player's public client id, an"
                        " undocumented endpoint; the panel asked to clear this access route with the user first (as for Kick's client key),"
                        " so nothing was fetched. Affiliate VODs of 10-21/22 expire about 11-04/05: needs the user's decision soon."},
    "X54": {"status": "open", "source": "information panel P2 (iter 4): cross-market synchronous own pulls as a dense label of the feed's event stream",
            "evidence": "Only the panel's own check exists (10-31 14:50-18:00: 47 synchronous pulls on 2 events, 12x the time-shift"
                        " control, 4 at takes). The per-map granularity regression and the refractory test need maps whose map and match"
                        " markets were recorded from game start, and bo3 per-map counts: the 10-31 block has 2 such events (no power)."
                        " Planned for the 11-01 06-12 block and later (round markets now recorded in every block)."},
    "X55": {"status": "infeasible", "source": "information panel P3 (iter 4): exact PandaScore join via eventMetadata.pandascoreMatchId",
            "evidence": "PandaScore REST answers 403 {\"error\": \"Token is missing\"} without a token (iteration 3, X23); the agent must not"
                        " create accounts. Used instead: GRID flag, league rate, pack-coverage lag, bo3 stars (X6 / X15 / X32). Becomes"
                        " feasible if the user supplies a token (join is exact: pandascoreMatchId on 100% of 1,324 events)."},
    "X56": {"status": "tried", "source": "mechanics panel P2 (iter 4): sweep probes, an uncensored on-chain label of the resting ladder",
            "evidence": "sweep_probes.json: 13,400 BUILD / 15,941 VALIDATE probes (fully consumed levels of other takers' in-play"
                        " multi-level sweeps; y = wallet order resting there), base rate 0.25 / 0.30. VALIDATE AUC: activity 0.663 (logit)"
                        " / 0.632 (GBM); + quote state (level vs others' 2-s-stale touch, pair sum) 0.669 / 0.664, gain +0.032 [0.015,"
                        " 0.047]; + own inventory 0.695 / 0.715. Band rule P(y | level - stale touch) flat 0.18-0.30 (VALIDATE AUC 0.596)."
                        " The resting ladder is not a function of the public 2-s-stale state. Live validation of probes vs own levels"
                        " (step 2) not run (needs more dev blocks)."},
    "X57": {"status": "tried", "source": "mechanics panel P1 (iter 4): validate the fill engine on the wallet's own orders; maker-only margin replay",
            "evidence": "engine_check.json: the X44 engine replaying the wallet's own maker orders assigns 88.3% / 88.8% of its real maker"
                        " shares to the same tx (phantom 6.4% / 6.5%), maker-only pair cost 0.975 vs real 0.978: the engine is valid."
                        " Attribution: touch 60-62% of shares, 1c behind 22%, 2c+ 15-18% (60-s markouts rise with depth); in-delay 15-16%"
                        " (+2.8-3.7c/share at settlement vs non-pack takers); pack 16-18% (-1.5 / -4.5c). margin_replay.json: a public"
                        " ladder 4c below others' 2-s-stale bid, 5 levels, reaches pair cost 0.972 / 0.978 and a locked margin of +$3.8k /"
                        " +$3.4k, but its residual loses $13.4k per split; per-market corr with the wallet VALIDATE +0.02 / -0.02 (BUILD"
                        " +0.19 / +0.19). Oracle re-post bounds (step 4) and the live-book variant (step 5) not run."},
    "X58": {"status": "tried", "source": "assumptions panel P1 (iter 4): survivorship-free census of informed bursts",
            "evidence": "census.json (rebuilt pack orders incl. the 5,752 in wallet txs that pack_orders.parquet lacked): 1,845 BUILD /"
                        " 1,941 VALIDATE informed BUY bursts with >= 3c move at +10 s; wallet-absent 80.2% / 79.8% (78% when the wallet"
                        " signed an order in the market within 60 s; 63-64% for multi-order bursts); in absent bursts its complement is hit"
                        " in 19-22% (24k / 30k stale + 11k / 12k in-delay shares; markouts -1.0..-3.2c). census_event_types.json: absent"
                        " bursts follow round wins (dW +0.79, p 3e-9), wallet-led bursts follow bomb plants beyond wins (dBP +1.21, p 0.03)."
                        " pack_event_pulls.json (live): at 54 pack-only takes it pulls the exposed side before the pack signs in 20.4% (null"
                        " 0.9%), within 150 ms after in 25.9%, and is hit in 37% of those txs."},
    "X59": {"status": "tried", "source": "mechanics panel P3 (iter 4): event size schedule; selection as a size rule censored at its floor",
            "evidence": "size_schedule.json: one (a, b) on own pairs / public in-play USD / elapsed time fits 0-4% of non-100 sizes within"
                        " one share (collapses to always-100: 92.1% / 88.3%). 28 events (36%) start below 100 (median 54) and ramp"
                        " monotonically; 'previous size in the event' (own state) within one share 99.0% / 99.5%. Start size vs pre-game USD"
                        " Spearman 0.55. Censored-selection step not run: no public start-size rule exists to censor."},
    "X60": {"status": "tried", "source": "assumptions panel P2 (iter 4): avoidance census, operator tests and the delay-queue leak control",
            "evidence": "avoid_census.json: 24 makers with >= 1% presence; r < 0.3: 0xe40ecff6 0.05, 0x2005d16a (rn1-inplay-maker) 0.10,"
                        " 0x51dbdd2b 0.16, 0xed446954 0.27 (median 0.80); a low r only needs a < 1 s reaction. leak_control.json: non-own"
                        " cancels in the arrival window of retail orders 8.5% vs 5.0% null, no spike vs the rest of the delay; elevated only"
                        " for informed orders (pack 4.8x, wallet 7.3x): no leak. Step 2 (same-process delta on the live book, funding logs)"
                        " not run: 2 co-subscriber cancels so far; funding needs millions of blocks of Transfer logs."},
    "X61": {"status": "tried", "source": "assumptions panel P4 (iter 4): session-clean selection labels and downtime risk",
            "evidence": "session_labels.json: operating windows 10-16..10-22 listed; 64 of 256 BUILD skips out of session; session-clean"
                        " refit: VALIDATE AUC 0.9586 vs 0.8964, gain +0.062 [0.019, 0.113], p 0.002, recall 0.778, lift 3.32 (uncleaned"
                        " recipe 0.9574 / 0.750 / 3.31); per day +0.034 / +0.094; a 3-h session day drops AUC to 0.89. Not adopted (noise);"
                        " C5 session starts on 10-31 / 11-01 not measurable yet (06-12 10-31 was sealed)."},
    "X62": {"status": "tried", "source": "assumptions panel P5 (iter 4): split the taker leg by size class",
            "evidence": "taker_size_class.json: caps (1000 / 2000) fill 5-6%, premium-move Spearman 0.04 / 0.13, 60-s markout +1.9 /"
                        " +0.3c, settlement +3.5% / +2.6%; odd sizes fill 11-15%, Spearman 0.15 / 0.09, +3.4 / +2.2c, +15.5% / +10.6%."
                        " Daily cap share 6%, 52-64% (10-17/18), 31-32%, 13-20% (10-21/22), 0% on 10-31: caps are a weak early sub-policy."},
    "X63": {"status": "open", "source": "mechanics panel P4 (iter 4): requote trigger as a hysteresis band on others' book",
            "evidence": "First pass (requote_trigger.json, 5,373 own add bursts, 10-31 block): within 50 ms before a burst its own cancel"
                        " 37.9% (null 1.6%), others' near-touch change 44.5% (10.1%), trade 2.6%, none 37.1% (89%); but non-own changes"
                        " before vs after its bursts 66.8% vs 69.1% (null 18.8%): symmetric co-occurrence, no clean trigger; no period in"
                        " inter-burst intervals. The band hazard with own-level tracking and the post-requote top fit are not done yet."},
    "X64": {"status": "open", "source": "information panel P4 (iter 4): HLTV scorebot as the named V1 source, checked by the user",
            "evidence": "Needs the user: opening ~20 HLTV match pages (traded vs skipped non-GRID matches of 16-22 Oct) as a normal visitor,"
                        " and, only with explicit consent, one HAR export of a live scorebot during a development block. HLTV blocks"
                        " automated access (Cloudflare 403, X36); the agent does not bypass it."},
    "X65": {"status": "open", "source": "information panel P5 (iter 4): date the feed by the co-subscribers' histories",
            "evidence": "Partial: 0x51dbdd2b traded Stake Pulse 17 / PGL 10 / NODWIN 4 CS2 events on 10-12..10-15 (assumptions panel"
                        " iter 4) and P4e was in 48% of the maker-regime leagues' non-GRID events 09-26..10-15 (iteration 2): both"
                        " predate the wallet there, so the source predates the switch. The latency change point needs calldata of their"
                        " maker orders before 10-16 (~30k pre-switch txs) and was not run; X69 covers the X51 rerun."},
    "X66": {"status": "tried", "source": "mechanics panel P5 (iter 4): sibling wallets by software fingerprint",
            "evidence": "Calldata scan of 114 makers with >= 200 orders in its markets: 16 are buy-only, whole-cent, sigType 3, but with"
                        " dominant sizes 5 / 20 / 25 / 300 and no 100-share ladder with event ramps: no sibling client in its markets. The"
                        " merge-timer scan over other makers' MERGE activity (data-api) was not run; 0x51dbdd2b's merge job differs"
                        " (mechanics panel iter 4)."},
    "X67": {"status": "tried", "source": "assumptions panel P3 (iter 4): one valuation, two legs (maker top = model value minus half-spread)",
            "evidence": "own_cost_anchor.json: K - L (limit of its last take on the other token, K 0.94) within one tick 53.0% / 56.7% of"
                        " maker orders signed 0-1.04 s after the take (last print 3.7% / 4.3%), 24-28% at 1.04-5 s, ~14% at 5-120 s, 6%"
                        " later (~2% of orders overall). Own-cost anchors (K - avg / last / LIFO cost of the other token) 6-22% vs last print"
                        " 34%. Step 2 (live implied mid m_W leading others' mid) not run (needs own-level tracking, X63)."},
    "X68": {"status": "tried", "source": "information panel critique 1 (iter 4): record the new clocks in every block for the exam",
            "evidence": "Done: round_recorder_v2 / chat_recorder_v2 (code/iter5) record in every block via unit_writer.UnitWriter"
                        " (sealed-start units always filed sealed); started 19:28 UTC 10-31, hard stop 11-03 00:00 UTC."},
    "X69": {"status": "ruled_out", "source": "information panel critique 6 (iter 4): rerun X51 on the taker-regime sign_ms",
            "evidence": "Taker-regime signing is not the decision time: 40 sampled txs with real block times had sign-to-block p5 3.0 s,"
                        " median 34 s, p95 291 s, each a FAK filled in one tx (iteration 2), i.e. pre-signed orders fired later. X51's"
                        " block time - 2 s is the right proxy there."},
}
cat.update(new)

H = [
    ("H46", "engine validity", "The X44 strict price-time engine reproduces the wallet's own maker fills.",
     {"same_tx_share": [0.883, 0.888], "phantom": [0.064, 0.065], "pair_cost_real": [0.9779, 0.9781], "pair_cost_engine": [0.9752, 0.9745]},
     "supported: the 1.005 of the X44 replay is the quote rule, not the engine"),
    ("H47", "public deep ladder", "A public ladder 4c below others' 2-s-stale bid (5 levels) copies the wallet's margin and PnL ranking.",
     {"pair_cost": [0.972, 0.978], "margin_usd": [3786, 3442], "residual_usd": [-13391, -13432], "pnl_corr_validate": [0.024, -0.019]},
     "rejected for outcome: same pair cost, but the residual breaks the ranking"),
    ("H48", "quote probes", "Its resting presence at fully consumed sweep levels is predictable from public point-in-time state.",
     {"val_auc_activity": 0.663, "val_auc_quote": 0.669, "gain": 0.032, "gain_ci95": [0.015, 0.047], "val_auc_with_own": 0.715},
     "rejected: AUC 0.67, presence follows fast or private state"),
    ("H49", "census", "The wallet's input is a superset of the pack's (it leads every informed burst).",
     {"absent_share": [0.802, 0.798], "absent_share_wallet_active60": [0.782, 0.778], "absent_hit_share": [0.193, 0.218],
      "absent_markout120_c": [-3.16, -1.58], "glm_absent_dW": 0.793, "glm_led_dBP_beyond_dW": 1.206, "glm_led_dBP_p": 0.032},
     "rejected: it misses ~80% of the pack's 3c+ bursts (round-win type) and leads plant-type events"),
    ("H50", "delay-queue leak", "Pending delayed taker orders leak to fast makers.",
     {"retail_arrival_rate": 0.085, "retail_null": 0.05, "retail_ratio_rest_of_delay": "1.1-1.8x"}, "not supported"),
    ("H51", "pair completion", "Its complement bid = K minus its own unpaired cost.",
     {"within_tick_avg_cost": 0.058, "within_tick_last_fill": 0.216, "within_tick_lifo": 0.138, "last_print_same_rows": 0.338,
      "K_minus_L_0_1.04s": 0.567}, "rejected generally; K - L holds for ~1 s after its takes"),
    ("H52", "size schedule", "One global (a, b) maps a cumulative quantity to its maker size.",
     {"non100_within1": [0.0, 0.04], "prev_size_rule_within1": [0.990, 0.995], "start_size_spearman_pre_usd": 0.549},
     "rejected: ramps are event-specific"),
    ("H53", "taker sub-policies", "The 1000 / 2000-share caps are a weaker sub-policy than odd sizes.",
     {"settle_caps": [0.035, 0.026], "settle_odd": [0.155, 0.106], "spearman_caps": [0.04, 0.127], "spearman_odd": [0.154, 0.085]},
     "supported"),
    ("H54", "session labels", "Cleaning out-of-session skips improves the frozen selection recipe.",
     {"val_auc": 0.9586, "baseline": 0.8964, "gain": 0.0622, "recall": 0.778, "lift": 3.319, "per_day_gain": [0.034, 0.094]},
     "small improvement within noise; not adopted"),
    ("H55", "requote band", "Its maker re-quotes follow others' touch changes (a band trigger).",
     {"others_change_50ms_before": 0.668, "after": 0.691, "null": 0.188}, "not confirmed: symmetric co-occurrence"),
    ("H56", "pack-event visibility", "At pack-only events the wallet does not react at all (blind).",
     {"own_pull_before_pack_sign": 0.204, "null": 0.009, "own_pull_0_150ms_after": 0.259, "hit_in_pack_tx": 0.37},
     "rejected: it pulls before the pack in ~20% (sees some events first), stays exposed in the rest"),
    ("H57", "avoiders", "Makers that avoid its FAKs (low presence ratio) are co-subscribers of its feed.",
     {"low_r": {"0xe40ecff6": 0.049, "0x2005d16a": 0.103, "0x51dbdd2b": 0.161, "0xed446954": 0.267}},
     "inconclusive: a < 1 s reaction to the public wave suffices for a low ratio"),
]
for hid, fam, desc, vm, verdict in H:
    s["hypotheses"].append({"id": hid, "family": fam, "description": desc, "validate_metrics": vm, "verdict": verdict})

comp = s["components"]
comp["selection"]["description"] = (
    "Whole events of non-GRID CS2 leagues (never a GRID event: 0/122), a subset of the events the informed pack covers;"
    " event logistic (league rate with GRID zeroing + pre-game popularity) AUC 0.954 vs activity 0.892 (gain +0.062, p 0.002),"
    " recall 0.72 at lift 3.3. Part of the skips are downtime (64 of 256 BUILD skips with no order anywhere in [gs, gs+1h]);"
    " session-clean refit 0.959 / recall 0.78 (not adopted). The main exam risk is a short session day (AUC 0.89 if one day ran 3 h).")
comp["timing"]["description"] = (
    "Taker: at in-round events of an unobserved feed, upstream of every public trace on the events it acts on (pulls its"
    " complement in 90-95% of takes at +11-19 ms; 0x51dbdd2b acts inside that window in some takes). But it acts on only ~20%"
    " of the informed 3c+ bursts in its markets: the pack's round-win-type bursts are mostly wallet-absent (80%), while its own"
    " follow bomb plants beyond round wins (p 0.03). At pack-only events it pulls before the pack signs in 20% (null 0.9%) and is"
    " hit in 37%. No delay-queue leak. Maker: re-quotes continuously in busy phases (co-occurring symmetrically with others'"
    " changes, no period); re-posts the complement ~1.04 s after its takes.")
comp["side"]["description"] = (
    "Maker: both outcomes (VALIDATE-only). Taker: the team that gained in-round on plant-type events (per-map shares follow bomb"
    " plants beyond wins, p 0.03-0.06), T side only 54% (p 0.13); the pack's round-win events are not its trigger.")
comp["price"]["description"] = (
    "Maker: whole-cent BUYs near the bid; last-print anchor 0.305 on VALIDATE (rule metric), live full-book bid 0.526; after"
    " its takes the complement top is K - L (K 0.94) for ~1 s (56.7% within tick, n 247) and decays; own-cost anchors fail"
    " (6-22%); its resting presence at swept levels is not predictable from the public 2-s-stale state (probe AUC 0.67)."
    " Taker: limit = stale ask + a premium scaling with the event (wallet-specific), kept 2-5c below the 60-120 s price; caps"
    " (1000 / 2000 shares) carry little of it.")
comp["size"]["description"] = (
    "Maker: 100 shares in CS2 (88-92% of orders); in 36% of events an event-wide size starts at 50-96 (median 54, lower when"
    " pre-game USD is low, Spearman 0.55) and steps up monotonically to 100 (no global schedule found; 'previous size' persists"
    " 99%); 10 shares in Dota 2. Taker: odd sizes ~0.3x of the pre-event depth; 1000 / 2000 caps were an early weak sub-policy.")
comp["size"]["confidence"] = 0.6
comp["exit"]["description"] = (
    "Never sells; pulls the complement at its own takes and re-posts it ~1.04 s later (K - L); merges pairs (pair cost 0.978,"
    " reproduced exactly by the validated engine on its own orders); stays exposed at the pack's events it does not detect"
    " (hit in ~20% of them at -1.5..-3c markouts). A public ladder 4c below the stale touch reaches the same pair cost but"
    " carries a residual loss of $13-14k per split.")
comp["timing"]["confidence"] = 0.5

s["live_lab"] = [x for x in s["live_lab"]]
for x in s["live_lab"]:
    if "tommy_cs2_rounds" in x.get("what", "") and "v2" not in x.get("what", ""):
        x["end"] = 1793474880
        x["what"] += " (v1 stopped 19:28 UTC 10-31: replaced by v2)"
    if "tommy_chat" in x.get("what", "") and "v2" not in x.get("what", ""):
        x["end"] = 1793474880
        x["what"] += " (v1 stopped 19:28 UTC 10-31: replaced by v2)"
s["live_lab"].append({"what": "own recorder v2, feed tommy_cs2_rounds (code/iter5/round_recorder_v2.py): books of every non-GRID CS2 round /"
                              " handicap / total market in play, chosen from listing-time fields, in EVERY block; records of sealed-start units"
                              " always filed sealed (code/iter5/unit_writer.py); detached (launcher 15676, worker 8668), hard stop 2026-11-03"
                              " 00:00 UTC, 200 MB cap", "start": 1793474901, "end": 1793664000})
s["live_lab"].append({"what": "own recorder v2, feed tommy_chat (code/iter5/chat_recorder_v2.py): anonymous Twitch chat timing (no text, no"
                              " names) of the resolutionSource channels of non-GRID CS2 events in play, in EVERY block; a record is filed sealed"
                              " if its channel's current unit started in a sealed block; detached (launcher 17648, worker 536), hard stop"
                              " 2026-11-03 00:00 UTC, 50 MB cap", "start": 1793474901, "end": 1793664000})

s["target_metrics_notes"]["presence_probe"] = ("iteration-5 pivot (not the pre-registered primary): sweep-probe resting presence, VALIDATE AUC"
                                               " 0.669 (quote state) vs 0.663 (activity), gain +0.032 [0.015, 0.047]; with own inventory 0.715")
s["target_metrics_notes"]["pnl"] += (" | Iteration 5: the engine is validated on the wallet's own orders (88-89% same-tx, pair cost 0.975 vs"
                                     " 0.978); best public ladder (4c below the stale bid, 5 levels) pair cost 0.978 but residual -$13.4k:"
                                     " VALIDATE +0.024 / -0.019 (BUILD +0.19 / +0.19).")
s["data_bugs"] = s.get("data_bugs", []) + [
    "pack_orders.parquet (iteration 2) was built from calldata_pub only, which excludes every tx with a wallet order: 5,752 pack taker"
    " orders that hit the wallet's ladder were missing from pack-based analyses (clusters, pack-vs-rounds, P4e side shares)."
    " code/iter5/census.py rebuilds from both records."]
s["status"] = "continue"
s["wall_reason"] = None
s["strategy_statement"] = (
    "CS2 (and some Dota 2) in-play bot; from 10-16 a buy-only two-sided maker plus an informed taker, before that a round-trip"
    " taker in GRID tier-1/2 events that traded late. [VALIDATE-only] Selection: whole events (match + all maps) of non-GRID"
    " tier-3/4 leagues, never an event with a GRID series id (0/122), favouring popular events and those the informed pack also"
    " trades; event rule AUC 0.954 vs activity 0.892; part of the skips are bot downtime. [VALIDATE-only] Maker: whole-cent"
    " BUY ladders (100 shares, or an event-wide size ramping from ~50 to 100) near the best bid on both outcome tokens from"
    " game start, re-quoted continuously, never sells, merges pairs (97% paired, pair cost 0.978; the validated fill engine"
    " reproduces this on its own orders); 38-40% of its fill shares sit behind the transaction's best level and 15% come from"
    " orders posted inside the takers' 1-s delay. At its own takes it pulls its complement within 11-19 ms and re-posts it"
    " ~1.04 s later at K - L. [hypothesis, live dev block] Taker: on plant-type in-round events of a private feed it sends FAK"
    " BUYs of the team that gained (map and match legs within 1-4 ms) at the stale ask plus a premium that scales with the"
    " event; on the CLOB server clock nothing public precedes it on those events, but it acts on only ~20% of the informed 3c+"
    " bursts in its markets: the pack's round-win events are mostly wallet-absent, and its ladder is picked off there (-1.5..-3c"
    " markouts). [VALIDATE-only] Economics: locked pair margins and rebates plus the informed taker legs; a public ladder in the"
    " same markets can match the pair cost (4c below the stale touch) but loses $13-14k per split on its residual.")
s["next_steps"] = [
    "11-01 06-12 development block: X38 chat clock under the pre-registered rule; X47b round-market books before its signings;"
    " X54 synchronous pulls; X63 band hazard with own-level tracking; census step 4 on more pack-only events; zero-fill FAK share.",
    "Outcome: add a wallet-like exit (re-pair after large repricings, merge timer, pull-based residual cap) to the public ladder on"
    " the validated engine; score margin and residual separately; settle with the examiner whether item 5 needs latency >= 2 s.",
    "Ask the user: Twitch VOD chat access route (X53, VODs of 10-21/22 expire ~11-04/05), PandaScore token (X55), HLTV page checks"
    " (X64), demo downloads (X37), Kick VOD segments (X4 / X22).",
    "X65 latency change point from pre-switch calldata of 0x51dbdd2b / P4e; X66 merge timers of the four fast avoiders; X60 step 2"
    " (same-process delta, funding) when more co-subscriber cancels exist.",
]
s["iterations"].append({"n": 5, "minutes": 88, "best_validate_score": 0.8721, "families": [
    "recorders in every block with unit-based sealed filing (X68)",
    "fill-engine validation on the wallet's own orders (X57)",
    "maker-fill attribution by depth / in-delay / taker class (X57)",
    "public deep-ladder replay on the validated engine (X57)",
    "sweep probes: uncensored resting-ladder presence (X56)",
    "survivorship-free census of informed bursts + event types + live pack-event pulls (X58)",
    "delay-queue leak control (X60)",
    "avoidance census of informed makers (X60)",
    "own-cost and K - L price anchors (X67)",
    "event size schedule (X59)",
    "taker size-class split (X62)",
    "session-clean selection labels (X61)",
    "live requote trigger co-occurrence (X63)",
    "sibling fingerprint scan (X66)"]})
s["data_sources"] = s.get("data_sources", []) + [
    ".cache/re/tommy-cs2-maker/probes.parquet (29,341 sweep probes, 16-22 Oct)",
    ".cache/re/tommy-cs2-maker/census_bursts.parquet (3,786 informed bursts with >= 3c moves, 16-22 Oct)",
    ".cache/re/tommy-cs2-maker/engine_check_rows.parquet / engine_attr_rows.parquet (engine validation and fill attribution)",
    ".cache/re/tommy-cs2-maker/own_cost_anchor.parquet (maker orders with own inventory state)"]
P.write_text(json.dumps(s, indent=1), encoding="utf-8")
print("open:", [k for k, v in s["catalog"].items() if v.get("status") == "open"])
print("catalog size", len(s["catalog"]))
