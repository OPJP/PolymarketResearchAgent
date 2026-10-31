"""Iteration 3 state.json update (replaces, never appends duplicates)."""
import json
from pathlib import Path

RES = Path(__file__).resolve().parents[2]
P = RES / "state.json"
s = json.load(open(P))

# ---- hypotheses: dedupe by id (keep last), then add / update iteration-3 entries
hyp = {}
for h in s["hypotheses"]:
    hyp[h["id"]] = h
hyp["H14"] = {"id": "H14", "family": "trigger-book-collapse",
              "description": "v2: the taker fires 0.3-1.0 s after a public near-touch depth collapse (other makers cancel).",
              "validate_metrics": {"server_clock_pre_sign_collapse": 0.141, "random": 0.023, "post_sign_collapse": 0.672,
                                   "receive_clock_pre_sign_collapse": 0.703},
              "verdict": "RETRACTED (iteration 3): receive-clock artefact; on the CLOB server clock the wave starts a median 51 ms after its signing"}
new = [
    ("H17", "taker-upstream-feed", "U1: the taker decisions run on a private in-round game feed upstream of all Polymarket data; FAK BUYs of the team that gained, matched 1.04 s later against makers that did not cancel.",
     {"wave_onset_after_sign_ms_p25_p50_p75": [14, 51, 168], "flat_book_before_sign_median": 1.0, "match_minus_sign_ms_p50": 1040},
     "supported (dev block, 64 orders): nothing public precedes its signing; input not obtained"),
    ("H18", "taker-unit-event", "Assumptions P3: one internal signal per game event fires legs in map and match markets.",
     {"hist_pairs_within_50ms": 60, "gap_ms_p50_p90": [1, 4], "dev_fanout_share": 0.11}, "supported"),
    ("H19", "taker-censoring", "Assumptions P1: its skipped collapses are FAK attempts lost in a fill race.",
     {"events": 1212, "acted": 25, "P_acted_given_depth_left_ge_30pct": 0.009, "n": 873}, "rejected: skipped collapses had fillable depth"),
    ("H20", "selection-bo3", "Information P1: bo3.gg stars / tier as a coverage proxy beyond activity.",
     {"auc_G_plus_stars": 0.929, "auc_G": 0.930, "auc_A": 0.897, "nonGRID_A": 0.899, "nonGRID_G_plus_stars": 0.882},
     "rejected: popularity proxy, no gain beyond pre-game activity + GRID"),
    ("H21", "selection-grid-only", "Assumptions P2: activity + GRID flag without the league rate.",
     {"auc": 0.930, "gain": 0.033, "gain_ci95": [0.008, 0.065], "p": 0.0025}, "weaker than v2 (0.954); v2 kept"),
    ("H22", "price-inplay-tick", "Assumptions P4: score price at the in-play tick (0.01).",
     {"within_tick_last_print": 0.305, "within_tick_rebuilt_touch": 0.396, "live_server_clock_at_bid": 0.293, "live_within_1c": 0.554},
     "metric corrected; price still far below 0.8"),
    ("H23", "size-by-game", "Assumptions P6: 10-share maker orders are a Dota 2 rule, not a version change.",
     {"dota_10share_share": 1.0, "cs2_100share_validate": 0.894, "cs2_100share_dev": 0.784}, "supported (size rule v3)"),
    ("H24", "round-score-model", "U5 / X2: quotes or takes from a public round-score model.",
     {"sports_socket_round_part_constant_for_its_events": True}, "rejected for its events: no public round data exists for them"),
]
for i, f, d, m, v in new:
    hyp[i] = {"id": i, "family": f, "description": d, "validate_metrics": m, "verdict": v}
s["hypotheses"] = list(hyp.values())

# ---- data sources: dedupe
ds = list(dict.fromkeys(s["data_sources"]))
for x in ["CLOB /time and HTTP Date clock probes (code/iter3/clock_probe.py)",
          "dev-unit market list from own recorder sub records + data-api /trades?user&market per dev market (no sealed-unit activity requested)",
          "calldata of every taker tx of the wallet's 9 dev-unit markets (4,234 txs, calldata_dev.parquet)",
          "bo3.gg finished lists 2026-10-15..10-22 (460 matches) matched to 295 of 384 events",
          "OpenDota /api/live probe (200, 143 KB per poll, 100 games, field 'delay')"]:
    if x not in ds:
        ds.append(x)
s["data_sources"] = ds
tb = list(dict.fromkeys(s.get("tool_bugs", [])))
tb.append("Laptop clock: the shared recorder's receive time t runs 0.9-1.4 s behind the CLOB server and drifts by about -130 ms per hour (10-31 13:00-15:45 UTC); every live timing must use the record's server field s (sports feed: correct t with a rolling offset from CLOB x records).")
tb.append("tools/live.py status: 'written' stays 0 for sports and rtds although their hour files grow (counter only).")
s["tool_bugs"] = list(dict.fromkeys(tb))

# ---- catalog updates
c = s["catalog"]
c["A5"]["evidence"] += " Iter 3: for its dev-block events the socket's round part stays 000-000 (map scores only) while GRID events carry per-round scores; its taker signing precedes every public trace on the server clock."
c["A7"] = {"status": "tried", "evidence": "Recorded books on the CLOB SERVER clock (iter 3, server_clock.json): the consumed-side depth is flat until its signing and the cancel wave starts a median 51 ms after it (p25 14 ms); the iter-2 'collapse precedes 87%' was a receive-clock artefact (laptop 0.9-1.4 s slow). The book is downstream of its decision. Maker price vs server-clock bid 50 ms before signing: at bid 29.3%, within 1c 55.4%."}
c["B2"]["evidence"] += " Iter 3: the 43% join-the-bid figure was measured on a book from after its own order (receive clock); server clock: 29.3% at the bid, 14.7% 1c above."
c["B3"]["evidence"] += " Iter 3, in-play tick (0.01 for 89.7% of VALIDATE maker orders): within one tick of the last print 0.305 (frozen rule), rebuilt touch 0.396."
c["C2"]["evidence"] += " Iter 3 server clock: the pack signs 0.2-0.5 s after the cancel wave, the wallet ~50 ms before it; nobody public signs before the wallet."
c["X2"] = {"status": "ruled_out", "evidence": "Round-boundary requoting rejected (iter 1: 14.1% of maker signings within 15 s after a round-end proxy vs 8.1%); a public round-score Markov model has no input for its events: the sports socket carries only map scores for them (round part constant 000-000 on the dev block) and its taker signing precedes every public trace (server_clock.json)."}
c["X7"]["evidence"] += " Iter 3: RETRACTED as a trigger: on the server clock the collapse follows its signing (wave onset p50 +51 ms)."
c["X13"]["evidence"] += " Iter 3: measured on the receive clock (book from ~1 s after signing), so 'depth at signing' was post-wave depth; to be redone on the server clock."
add = {
    "X19": ("tried", "information panel P1 (iter 2): bo3.gg stars / tier_rank / bookmaker line as selection coverage proxy. Non-GRID traded rate 0* 4%, 1* 45%, 2* 87%, 3* 100%, but VALIDATE AUC activity+GRID 0.930 vs +stars 0.929; inside non-GRID 0.899 vs 0.882: a popularity proxy, no gain (selection_bo3.json). PIT check moot."),
    "X20": ("tried", "information panel P2 (iter 2): book reader with a confirmation rule vs slower feed. Resolved by the server clock: neither; the wallet signs before the collapse (wave onset +51 ms median), so it reads neither the book nor a slower copy of the cancellers' feed (server_clock.json)."),
    "X21": ("open", "information panel P3 (iter 2): event-wide cancel clock and canceller identity (attribute level decrements to calldata maker orders; owners / funders of the first cancellers). Not run: needs level attribution on the own recorder."),
    "X22": ("open", "information panel P4 (iter 2): event-locked Kick VOD stream clock with ~50 MB of 160p segments. Needs the user's explicit consent to download video (not given); asked in the return."),
    "X23": ("open", "information panel P5 (iter 2): SX Bet in-play prices (v2 order endpoints 400 / 404, newer API not found) and PandaScore live.supported (403 'Token is missing'; needs a token from the user, no account may be created here). Asked in the return."),
    "X24": ("open", "information panel P6 (iter 2): Dota 2 natural experiment with OpenDota /api/live (verified 200, no key, 143 KB per poll, 100 games, a 'delay' field). Recorder not started: the wallet traded one Dota 2 event in dev blocks so far; start it for dev blocks with Dota 2 events in its leagues."),
    "X25": ("tried", "mechanics panel P1 (iter 2): server-clock forensics. Laptop offset -0.90 s (13:00) to -1.40 s (15:45); wallet match - sign 1,034 / 1,040 / 1,052 ms (p5/p50/p90); consumed-side depth 1.00 up to signing, 0.66 at +0.1 s, 0.13 at +1.0 s, refill at +1.04 s; collapse pre-sign 14.1% vs random 2.3% (receive clock 70.3%); v2 trigger retracted; final_rule.py v3 reports the server-clock diagnostic only (server_clock.json)."),
    "X26": ("open", "mechanics panel P2 (iter 2): maker leg as a feed-blind state machine (hazard of maker signings by trigger type; does it cancel within 150 ms of a wave; price = f(best other bid, own complement bid, inventory)). Not run this iteration."),
    "X27": ("tried", "mechanics panel P3 (iter 2): per-signer calibration on the dev block: wallet 1,040 ms, pack Pfe 1,064 / Pf1 1,082, fast others 1,038-1,060, slow 2.0-2.2 s; the wallet signs ~50 ms before the wave and the pack 0.2-0.5 s after it, so it ranks first on most events. Act / no-act vs rank and leftover not modelled yet (server_clock.json per_signer)."),
    "X28": ("open", "mechanics panel P4 (iter 2): delay-window requoters (19% of its taker USD from orders signed after its FAK; 0xed446954 27% of that) as the reason for the limit premium and size cap. Not run this iteration."),
    "X29": ("open", "mechanics panel P5 (iter 2): historical match-clock tape (taker sign_ms + calibrated delay) for h1/h2 price anchors. Calibration now exists (wallet 1,040 ms, fast signers 1,038-1,082 ms); rebuild not run."),
    "X30": ("tried", "assumptions panel P1 (iter 2): attempt censoring. 1,212 server-clock collapses in its markets, 25 acted; 873 kept >= 30% of the reference depth 1 s later (a FAK would have filled) and it acted on 0.9% of them: skipped collapses are not lost races (burst_fanout.json)."),
    "X31": ("tried", "assumptions panel P2 (iter 2): activity + GRID flag without the league rate: VALIDATE AUC 0.930 (gain +0.033 [0.008, 0.065], p 0.0025) vs frozen v2 0.954; listing-time candidates inside non-GRID events: bo3 stars no gain (X19), stream channel +0.005 (X6). The quote-in-untraded-events detector (step 4) not run."),
    "X32": ("tried", "assumptions panel P3 (iter 2): fan-out legs: 60 map + match pairs signed a median 1 ms apart (p90 4 ms) in 16-22 Oct; 11% of dev-block taker orders; no book precedes either leg on the server clock: one signal per game event (burst_fanout.json)."),
    "X33": ("tried", "assumptions panel P4 (iter 2): in-play tick 0.01 (first sub-cent resting order median price 0.999; 89.7% of VALIDATE maker orders before it). price_within_tick at the tick in force: last print 0.305 (frozen rule), rebuilt touch 0.396; live server clock at the bid 29.3%, within 1c 55.4% (versions_price.json). Ladder-from-unfilled-levels not run."),
    "X34": ("open", "assumptions panel P5 (iter 2): the cancels belong to identifiable makers (size matching of level decrements to calldata orders). Not run this iteration; with the server clock the cancellers are the wallet's fastest peers (+14-51 ms)."),
    "X35": ("tried", "assumptions panel P6 (iter 2): versions. All 10-share maker orders are Dota 2 (10-22 and dev block), so the 10-22 'version' was the game mix; CS2 maker 100 shares 89.4% (16-22 Oct) vs 78.4% (dev); taker caps 1000/2000 14.4% vs 0%, size median 470 vs 183, fill frac 0.155 vs 0.242: taker sizing drifts, maker rule stable (versions_price.json)."),
}
for k, (st, ev) in add.items():
    c[k] = {"status": st, "evidence": ev}
s["catalog"] = c

# ---- components, statement, metrics
s["components"] = {
    "selection": {"confidence": 0.7, "tag": "VALIDATE-only", "description": "Whole events of non-GRID CS2 leagues (never a GRID event: 0/122); event logistic (league rate with GRID zeroing + pre-game popularity) AUC 0.954 vs activity 0.892 (gain +0.062, p 0.002), recall 0.72 at lift 3.3; bo3 stars add nothing beyond popularity."},
    "timing": {"confidence": 0.4, "tag": "hypothesis", "description": "Maker: continuous from game start (VALIDATE-only). Taker: at in-round game events seen on an unobserved private feed; on the server clock it signs before every public trace (cancel wave +51 ms median after it); fan-out legs in map + match within 1-4 ms."},
    "side": {"confidence": 0.5, "tag": "hypothesis", "description": "Maker: both outcomes (VALIDATE-only). Taker: the team that just gained in-round (the team whose asks other makers pull right after it signs; +2.6-2.9c in 10 s)."},
    "price": {"confidence": 0.35, "tag": "VALIDATE-only", "description": "Maker: whole-cent BUYs near the best bid (server clock: 29% at the bid, 55% within 1c; in-play tick 0.01; last-print anchor 0.305). Taker: FAK at best ask + 0-2c."},
    "size": {"confidence": 0.65, "tag": "VALIDATE-only", "description": "Maker 100 shares in CS2 markets, 10 in Dota 2 (all 10-share orders are Dota 2); taker variable and drifting (caps 1000/2000 fading)."},
    "exit": {"confidence": 0.75, "tag": "VALIDATE-only", "description": "Never sells; merges complete pairs; holds the unpaired residual to resolution."},
}
s["strategy_statement"] = (
    "CS2 (and some Dota 2) in-play bot; from 10-16 a buy-only two-sided maker plus an informed taker, before that a round-trip taker in GRID tier-1/2 events. "
    "[VALIDATE-only] Selection: whole events (match + all maps) of non-GRID tier-3 leagues (1win, Stake, PGL, Circuit X, DraculaN, NODWIN, ...; since 10-31 also CyberClash and FiReSPORTS), never an event with a GRID official-data series id (0/122), favouring popular events; event rule AUC 0.954 vs activity 0.892. "
    "These are exactly the events in which Polymarket's own sports feed carries no round scores. "
    "[VALIDATE-only] Maker: from game start it keeps whole-cent BUY orders near the best bid on BOTH outcome tokens (100 shares in CS2, 10 in Dota 2), never sells, merges complete pairs (97% paired, pair cost 0.978) and holds the residual; its stale complement bids are what the slower informed takers hit. "
    "[hypothesis, live dev block] Taker: on in-round game events it sends FAK BUYs of the team that gained (in map and match markets within 1-4 ms) at the best ask + 0-2c; on the CLOB server clock it signs before every public trace: the fastest other makers cancel that team's asks a median 51 ms after its signing, the informed pack signs 0.2-0.5 s later, and its order matches 1.04 s after signing (the in-play delay) against makers who did not cancel. Its input is a private in-round feed that none of the obtained public data contains; the iteration-2 'book-collapse trigger' was a receive-clock artefact and is retracted. "
    "[VALIDATE-only] Economics: locked pair margins and rebates plus the informed taker legs; a generic public-data ladder in the same markets loses 5-10%.")
tm = s["target_metrics"]
tm["price_within_tick"] = 0.305
s["target_metrics"] = tm
s["target_metrics_notes"] = {
    "selection": "event level, frozen rule (v2 selection constants, BUILD) on VALIDATE: gain +0.062 [0.019, 0.115], p 0.002",
    "presence": "fill per (market, 30-s bin), event score x in-play: below the activity baseline (co-occurrence by construction)",
    "live_taker": "RETRACTED (receive clock). Server-clock diagnostic on the 10-31 dev block (61 taker orders): collapse in 2 s before signing 14.8% vs random 2.1%, after signing 72.1%; match - sign p50 1,040 ms",
    "price": "in-play tick (0.01): last-print anchor 0.305 (exact 0.001 match 0.115); rebuilt touch 0.396; live server-clock bid 0.293 (within 1c 0.554)",
    "pnl": "generic tape ladder (executable, strict fills); negative",
}
s["best"] = {"rule_id": "tommy-v3-grid-league-upstream", "validate_metrics": {
    "events": 128, "events_traded": 36, "selection_auc": 0.9538, "selection_baseline": 0.8916, "selection_gain": 0.0622,
    "selection_gain_ci95": [0.0188, 0.1148], "selection_gain_p_le0": 0.002, "selection_recall": 0.722, "selection_lift": 3.302,
    "presence_auc": 0.8721, "presence_baseline": 0.899, "price_within_tick": 0.305, "price_exact_last_print": 0.115,
    "size_100_accuracy": 0.883, "pnl_corr_pearson": -0.121, "pnl_corr_spearman": -0.061}}
s["status"] = "continue"
s["wall_reason"] = None
it = [x for x in s["iterations"] if x.get("n") != 3]
it.append({"n": 3, "minutes": 100, "best_validate_score": 0.8721, "families": [
    "server-clock forensics and laptop clock calibration (retraction of the v2 book trigger)",
    "per-signer calibration through the in-play delay", "fan-out legs / event unit", "attempt-censoring test on server-clock collapses",
    "bo3.gg pre-match fields for selection", "activity + GRID selection without league rate", "price at the in-play tick and server-clock touch",
    "version fingerprints (size by game)", "sports socket round coverage by event"]})
s["iterations"] = it
json.dump(s, open(P, "w"), indent=1)
print("hypotheses", len(s["hypotheses"]), "catalog", len(c), "open", [k for k, v in c.items() if v["status"] == "open"])
