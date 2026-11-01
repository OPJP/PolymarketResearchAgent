"""Iteration 6: update state.json (catalog X70-X86, hypotheses H61-H68, components, iteration entry, notes)."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
P = ROOT / "research/reverse_engineering/tommy-cs2-maker/state.json"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
shutil.copy(P, ROOT / ".cache/re/tommy-cs2-maker/state_backup_iter5.json")
s = json.loads(P.read_text(encoding="utf-8"))
cat = s["catalog"]


def load(name):
    p = RES / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


fg = load("funding_graph.json")
fr = load("final_rule_v3_validate_iter6.json")
fund_ev = ("funding_graph.json (Polygon eth_getLogs, USDC.e + USDC Transfers, blocks 95,371,932-96,005,476 = 10-12..H): the wallet"
           " moves $1.01M in / out only with Polymarket contracts (CTF, the V2 collateral wrapper 0xc011a7e1, exchanges, adapters)"
           " plus one external counterparty 0x4cd00e38 (2 outgoing, $2,220); 0x51dbdd2b $173k / $175k with Polymarket contracts plus"
           " one external sender 0x3a3bd7bb (73 small incoming, $2,104); owner EOA 0x8af810f0: $2,000 in from 0xf70da978, $2,000 out to"
           " 0x116342d6 (then address-poisoning dust); 0x51dbdd2b signer 0xdecd4b4c: none. No overlap, no direct transfer: Y5 (one"
           " operator) not supported in this window (POL funding and earlier history not scanned).")

new = {
    "X70": {"status": "open", "source": "information panel P1 (iter 5): the maker leg on the live book: dense quote occupancy and an executable replay",
            "evidence": "Steps 1-2 run on BUILD-live (live_occupancy.json; 10-31 14:50-18:00, 627,712 level-samples every 1 s per book side,"
                        " levels others' best +2c .. -8c, own levels by fingerprint with its actual sizes; first half fit, second half"
                        " scored): gap only AUC 0.635; all fast public features 0.688 (logit) / 0.767 (LightGBM); the delay-window"
                        " features (non-own cancels in the last 200 / 1,000 ms, best changes in 500 ms) carry ~0 importance (6 / 38 / 44"
                        " vs 1,435-2,410 for price level, others' size at / ahead of the level, gap). Occupancy is partly a function of slow"
                        " book shape, not of sub-second waves; below the 0.85 signature. Steps 3-4 (rule distillation, executable replay"
                        " on the recorded books, wiring into evaluate) and the VALIDATE-live blocks (from 11-01 18:00) remain."},
    "X71": {"status": "open", "source": "information panel P2 (iter 5): key-free organiser-side live sources (CSTV / GOTV+ relays, match-server panels), league by league",
            "evidence": "First pass (web search as a normal visitor): DraculaN = Digital Crusade, Bucharest (offline series with online"
                        " stages); 1win Private Club #2 offline (Serbia, 19-22 Oct); Stake Ranked = StarLadder LAN circuit; Stake Pulse ="
                        " Black Molly Entertainment studio; Circuit X Curitiba offline LAN (Brazil); NODWIN Clutch Series online; PGL"
                        " Bucharest qualifier online. A LAN-only rule fails (online NODWIN 6/23 and PGL qualifier 9/13 traded). rdy.gg"
                        " (tournament hub listing live standings and map results) answers HTTP 403 to a plain fetch (bot protection, not"
                        " bypassed). No public CSTV / GOTV+ relay or live match panel found yet; second pass (Liquipedia server / platform"
                        " fields, organiser match pages) open."},
    "X72": {"status": "tried", "source": "information panel P3 (iter 5): the per-match coverage state (what switches its input on and off)",
            "evidence": "coverage_state.json: persistence diff (P(present | previous burst within 120 s present) - P(.. absent)) 0.126 /"
                        " 0.124 (BUILD / VALIDATE); within-market permutation null 0.035 / 0.040 (p 0.0025 / 0.0035); stratified by market"
                        " x price bin x reversal x game time 0.090 / 0.063 (p 0.089 / 0.009); composition-only 0.021 / 0.017. Most of the"
                        " persistence is the reversal / price / game-time composition; a residual remains on VALIDATE. Present 29-35% after"
                        " a burst on the OTHER team within 120 s, 5.6-8.0% after one on the same team, 19-20% with none. Public-covariate"
                        " model of which informed bursts it leads: VALIDATE AUC 0.747 (+0.009 with the lagged own label). The HMM and the"
                        " chat / stream alignment (steps 2-3) need dev-block chat data (11-01 06-12 on)."},
    "X73": {"status": "open", "source": "information panel P4 (iter 5): SX Bet on-chain in-play fills as a second venue's clock",
            "evidence": "Iteration 6 probe: api.sx.bet/trades and /trades/consolidated answer 404 (Not Found); /sports and /leagues/active"
                        " answer 200 (listing only), so SX trade history is not available key-free through the API. The chain half (SX"
                        " Network RPC + exchange fill events from docs.sx.bet) remains to verify."},
    "X74": {"status": "tried" if fg else "open", "source": "information panel P5 (iter 5): funding graph of the wallet and 0x51dbdd2b (one operator or two subscribers)",
            "evidence": fund_ev or "funding_graph.py started (Polygon eth_getLogs, USDC.e and USDC Transfers from / to the wallet, its owner"
                                  " 0x8af810f0, 0x51dbdd2b and its signer 0xdecd4b4c, 10-12 .. H); not finished this iteration."},
    "X75": {"status": "open", "source": "mechanics panel P1 (iter 5): price deep states with own inventory, the pair cap against its own opposite top, book age",
            "evidence": "Partial (joint_quote.json, BUILD-live): its own pair sum after a burst p10 / p50 / p90 0.92 / 0.97 / 0.99 (cap at"
                        " ~0.99); min(join, K - trigger top) adds ~2-3 points over join on the untouched token (0.67 / 0.73 vs 0.63 / 0.70)."
                        " The deep-state branches (after takes, after pulls / cooldowns, long side) and the book-age sweep remain; they need"
                        " the 11-01 blocks for a held-out test."},
    "X76": {"status": "tried", "source": "mechanics panel P2 (iter 5): outcome = copy of the maker leg + a public residual control chosen on BUILD",
            "evidence": "hedge_ceiling.json (DIAGNOSTIC, the wallet's real maker fills as the oracle maker leg; hedge H(X): when |inventory| > X"
                        " buy the short outcome at the first public taker BUY print >= 2 s later + 1c, within 120 s): BUILD maker-only 0.39 /"
                        " 0.50, every hedge lowers BUILD (H400 0.12 / 0.26, H800 0.23 / 0.40), so the BUILD choice is no hedge, which scores"
                        " VALIDATE 0.38 / 0.34; hedges help only VALIDATE (H600 0.62 / 0.50) and lose money (H100 -$4.6k / -$6.3k). With"
                        " X82: maker leg alone 0.38 / 0.34, activity baseline 0.51 / 0.37, both legs' locked margin 0.82 / 0.75: the outcome"
                        " item needs the private taker leg. Step 2 (executable live version) is bounded by this ceiling."},
    "X77": {"status": "open", "source": "mechanics panel P3 (iter 5): cross-market series fair value as the maker anchor and a historical price anchor",
            "evidence": "Not run this iteration (needs outcome / team alignment between match and map markets and the map-score state)."},
    "X78": {"status": "tried", "source": "mechanics panel P4 (iter 5): at pack-only events, are its pulls locked to the public wave or to the event",
            "evidence": "wave_lock.json (BUILD-live, server clock): at its own takes u - p 14 / 15 / 17 ms (p25 / p50 / p75), slope on w - p"
                        " -0.05, before the first public cancel in 69% (event-locked). At 54 pack takes without a wallet take: pulls in 48%,"
                        " u - w +8 / +15 / +62 ms, u - p 29 / 37 / 985 ms, slope +1.40 (corr 0.81, permutation p 0.008, 14 events with both"
                        " after p), before the wave in 14%: WAVE-LOCKED (a ~15-ms book reaction), reading A. Wallet maker hit in the pack's"
                        " tx: 39% with pull + wave, 42% wave without pull, 22% neither: the pull protects little. Retail busy-phase control:"
                        " u - w median +124 ms, corr 0.37."},
    "X79": {"status": "tried", "source": "mechanics panel P5 (iter 5): a 1.5-s cancel -> re-post cooldown timer as a ladder state element and software fingerprint",
            "evidence": "cooldown.json (BUILD-live): own cancel -> next own add on the same side: 225 intervals in [1,500, 1,520) ms vs 4-12"
                        " per 20-ms bin around (29 / 21 in the adjacent bins): a hard 1.5-s re-post timer. Level age at the cancel not"
                        " constant (p10 / p50 / p90 121 ms / 3.3 s / 49 s): not a refresh timer; the re-post lands at the cancelled price in"
                        " 50.8% (other cancels 14.9%); a non-own change in the prior 100 ms in 50% (others 67%). Step 4 (cooldown_siblings.json,"
                        " every dev-start CS2 book of tommy_cs2_near): same-size same-price re-adds 1,490-1,530 ms after a trade-free decrease"
                        " vs the same pairing at 1,290-1,330 / 1,690-1,730 ms: traded markets size 100 221 vs 105 (two control windows);"
                        " UNTRADED markets size 100 656 vs 392, size 30 324 vs 55, odd sizes 23.25 / 88.52 / 99.98 33 / 32 / 29 vs 0-2; size"
                        " 10 no excess. The 1.5-s timer is a shared bot behaviour (other ladders of 30 and odd sizes), not a unique sibling"
                        " fingerprint; mapping the untraded 100-share pairs to wallets needs calldata of those markets."},
    "X80": {"status": "tried", "source": "assumptions panel P1 (iter 5): sub-second public cancel-wave follower as the maker's protection",
            "evidence": "Step 2 (wave_lock.json): at pack-only events 57% of its pulls come 0-30 ms after the first non-own cancel, 7% 30-200 ms"
                        " after, 14% before it; but it pulls at only 48% of those events and the pull barely changes its hit rate (39% vs"
                        " 42%). Step 1 (live_occupancy.json): delay-window cancel features add ~0 to resting-level occupancy (LightGBM"
                        " importance 6-44 vs 1,435-2,410), so the 'signature if false' holds for presence (< 0.03 gain from the fast"
                        " features); fast public features overall reach 0.767 (slow book shape), not 0.80+. Step 3 (latency sweep of a"
                        " follower on the engine) not run; its value is bounded by the weak protection the wallet itself gets."},
    "X81": {"status": "tried", "source": "assumptions panel P2 (iter 5): price as one two-token quote at the bot's view time",
            "evidence": "joint_quote.json (BUILD-live, 5,622 bursts with own levels on both tokens): own pair sum IQR 4c (p10 / p50 / p90"
                        " 0.92 / 0.97 / 0.99), every burst adds on ONE side only: not a (mid, spread) quote ('signature if false'); a soft"
                        " cap at ~0.99. On the untouched token: join 0.63 / 0.70, K - trigger 0.63 / 0.59 (K 0.98), min(join, K - trigger)"
                        " 0.67 / 0.73 within one tick (first / second half). View-lag and fingerprint-precision steps (3-4) remain under"
                        " X75."},
    "X82": {"status": "tried", "source": "assumptions panel P3 (iter 5): outcome activity baseline and single-leg ceilings",
            "evidence": "outcome_baseline.json: print-count pseudo-PnL vs the wallet's per-market PnL BUILD +0.41 [0.11, 0.65] / +0.18"
                        " [0.00, 0.35], VALIDATE +0.51 [0.32, 0.67] / +0.37 [0.19, 0.53]; its maker fills alone 0.39 / 0.50 and 0.38 / 0.34;"
                        " taker fills alone 0.15 / -0.05 and 0.10 / 0.13; locked margin 0.85 / 0.66 and 0.82 / 0.75 (partials given log"
                        " prints 0.79 / 0.71 on VALIDATE). evaluate() now reports pnl_baseline_prints_* and the rule's partial correlation"
                        " given log prints."},
    "X83": {"status": "ruled_out", "source": "assumptions panel P4 (iter 5): the take as an edge-threshold decision on events it sees",
            "evidence": "Its premise (it sees most of the pack's events and declines them) is contradicted by X78: at pack-only events its"
                        " pulls come a median 15 ms AFTER the first public cancel and precede it in only 14% (at its own takes: 69% before),"
                        " and none of the 11 pre-pack pulls of iteration 5 carries the zero-fill FAK signature (pack_prepull_signature.json)."
                        " The seen-not-taken class is therefore a public-wave reaction, not an event it saw; its takes are a different"
                        " event set (reversals; X72)."},
    "X84": {"status": "tried", "source": "assumptions panel P5 (iter 5): freeze the selection rule for exam league turnover",
            "evidence": "exam_league_mix.json (listing projection only, fetched without the shared cache, nothing raw stored): h1 100"
                        " non-GRID events, 26% in 2 leagues absent from the v3 exam table; h2 95, 25% in 3 unseen leagues; non-GRID tier"
                        " mix h1 5:62 / 2:18 / 4:16 / 3:4, h2 5:60 / 4:16 / 2:13 / 3:6. Below the 30% switch threshold: v3 stays frozen"
                        " (pre-registered in NOTES iteration 6), X31 pack-lag variant kept as the documented fallback."},
    "X85": {"status": "tried", "source": "self-proposed (iteration 6, Y4): bookmaker-run leagues and an odds-feed input",
            "evidence": "burst_by_owner.json: led / near share of the informed bursts in sportsbook-branded leagues (1win, Stake) 0.160"
                        " [0.135, 0.185] (28 events) vs other leagues 0.168 [0.143, 0.195] (49 events): no organiser-bookmaker effect on"
                        " its take rate; Y4 gets no support from this measure (odds-feed probes themselves remain under X48)."},
    "X86": {"status": "open", "source": "self-proposed (iteration 6, Y7): low-latency stream platform (Kick vs Twitch) as the input's edge",
            "evidence": "burst_by_owner.json: led / near share Kick 0.176 [0.152, 0.202] (53 events) vs Twitch 0.141 [0.117, 0.165] (23"
                        " events): a weak platform difference; the X38 chat clock (pre-registered) and per-platform latency on the dev"
                        " blocks are the test."},
}
for k, v in new.items():
    cat[k] = v
for k in ("X38", "X47", "X54"):
    cat[k]["evidence"] += " | Iteration 6: no development live block during the iteration (10-31 18-24 sealed); still pending for 11-01 06-12."
cat["C1"]["evidence"] = cat["C1"].get("evidence", "") + " | Iteration 6: funding graph (X74), see there."

s["hypotheses"] += [
    {"id": "H61", "family": "information (Y1)", "description": "It sees nearly every in-round event (round wins too) and declines the takes that do not clear its hurdle, protecting the ladder instead.",
     "validate_metrics": {"pull_before_public_wave_pack_only": 0.14, "pull_before_public_wave_own_takes": 0.69, "u_minus_w_ms_p50_pack_only": 15},
     "verdict": "rejected for the pack's events (BUILD-live, 54 events): its pulls there are wave-locked"},
    {"id": "H62", "family": "maker protection (Y2)", "description": "At informed events outside its feed it follows the first public cancel on the exposed side within ~15 ms (a co-located book reaction).",
     "validate_metrics": {"share_events_with_pull": 0.48, "slope": 1.40, "corr": 0.81, "perm_p": 0.008, "hit_rate_with_vs_without_pull": [0.39, 0.42]},
     "verdict": "supported (BUILD-live, 14 events with both); weak protection; VALIDATE-live pending"},
    {"id": "H63", "family": "information (Y3)", "description": "An intermittent per-match input (stream / relay session, scout) switches its takes on and off.",
     "validate_metrics": {"persistence_diff": [0.126, 0.124], "p_within_market": [0.0025, 0.0035], "p_stratified": [0.089, 0.009]},
     "verdict": "mostly composition (reversal / price / game time); a residual persistence on VALIDATE (p 0.009)"},
    {"id": "H64", "family": "taker selection among informed bursts", "description": "Which informed bursts it leads is predictable from public burst covariates (reversal vs same-team, price level, market type, game time, size).",
     "validate_metrics": {"auc": 0.747, "auc_with_lagged_own_label": 0.756, "present_after_reversal": [0.353, 0.287], "present_after_same_team": [0.056, 0.08]},
     "verdict": "supported as a descriptive model (needs the event itself, which is private)"},
    {"id": "H65", "family": "outcome", "description": "The wallet's per-market PnL is driven by activity plus the cross-leg locked margin; no single leg reaches item 5.",
     "validate_metrics": {"prints_baseline": [0.513, 0.369], "maker_leg_only": [0.38, 0.336], "taker_leg_only": [0.095, 0.13], "locked_margin": [0.824, 0.751]},
     "verdict": "supported: item 5 needs both legs (the taker input); the activity baseline is ~0.5 Pearson"},
    {"id": "H66", "family": "price", "description": "The maker sets one two-token quote (mid, spread).",
     "validate_metrics": {"own_pair_sum_iqr_c": 4.0, "own_pair_sum_p90": 0.99, "single_sided_bursts": 1.0},
     "verdict": "rejected (BUILD-live): sides re-quoted one at a time under a ~0.99 pair cap"},
    {"id": "H67", "family": "maker presence", "description": "Its resting ladder is a fast public function of the live book (sub-second cancel waves).",
     "validate_metrics": {"gap_only_auc": 0.635, "fast_public_lgbm_auc": 0.767, "delay_window_importance": "6-44 of ~9,000"},
     "verdict": "rejected for the fast part (BUILD-live halves); slow book shape carries 0.77"},
    {"id": "H69", "family": "maker state machine", "description": "A client timer re-posts a cancelled level exactly 1.5 s later, at the same price in half the cases.",
     "validate_metrics": {"spike_1500_1520ms": 225, "neighbour_bins": "4-12 (29 / 21 adjacent)", "same_price_repost": 0.508, "shared_by_other_bots": "untraded markets size 30: 324 vs 55 control"},
     "verdict": "supported (BUILD-live); deterministic ladder holes; the timer is shared with other bots, so not a unique fingerprint"},
    {"id": "H70", "family": "taker trigger (event class)", "description": "Its takes are the first in-round turn against the team that just gained: after a pack-only burst on team X it leads the next informed burst far more often when it is on the other team; an economy-surprise reading (upset wins, breaks) explains it.",
     "validate_metrics": {"lead_after_pack_burst_5_120s_other_vs_same": "23-36% vs 7-14%", "glm_dU_p": 0.745, "glm_dBR_p": 0.922, "glm_dBP": [1.03, 0.059]},
     "verdict": "sequence effect supported (both splits); the economy-count reading not supported; plants remain the only per-map lead"},
    {"id": "H71", "family": "price (live, frozen)", "description": "Frozen live price rule in evaluate(): others' best bid at sign - 100 ms with own levels removed, capped at 0.99 - own top on the other token.",
     "validate_metrics": {"BUILD_live_filled_orders": 172, "within_tick": 0.424, "exact": 0.198, "last_trade_same_rows": 0.187},
     "verdict": "frozen for VALIDATE-live (11-01 06-12 on) and the future-block exam; below 0.8"},
    {"id": "H68", "family": "information (Y4 / Y7)", "description": "Its input is an organiser-bookmaker odds feed (Y4) or a low-latency stream platform (Y7).",
     "validate_metrics": {"led_share_bookmaker_vs_other": [0.16, 0.168], "led_share_kick_vs_twitch": [0.176, 0.141]},
     "verdict": "Y4 not supported by take shares; Y7 weakly consistent, open (X86)"},
]

comp = s["components"]
comp["timing"]["description"] = (
    "Taker: at in-round events of an unobserved feed, upstream of every public trace on the events it acts on (pulls its"
    " complement at +11-19 ms, before the first public cancel in 69%; 0x51dbdd2b acts inside that window in some takes);"
    " it acts on ~16-20% of the informed 3c+ bursts in its markets, mostly the first informed move AGAINST the previous"
    " burst (present 29-35% after a burst on the other team, 6-8% after one on the same team; public-covariate AUC 0.75)."
    " At the pack's other events it does not see the event: it pulls in ~half of them a median 15 ms AFTER the first"
    " public cancel (wave-locked, slope 1.4, p 0.008; BUILD-live) and is hit about as often as without a pull. Maker:"
    " re-quotes continuously, one side per burst; re-posts the complement ~1.04 s after its takes.")
comp["timing"]["confidence"] = 0.55
comp["price"]["description"] = (
    "Maker: whole-cent BUYs, one side per burst, joining the other makers' best bid (live, own levels removed: within one"
    " tick of others' best at 67% of re-quote bursts, 45.6% of filled orders), with the two-token pair sum capped near 0.99"
    " (p90 0.99; the cap adds ~2-3 points); historical anchors 25-35% (last print 0.305 on VALIDATE, the rule metric);"
    " after its takes the complement top is K - L (K 0.94) for ~1 s. Resting occupancy: 0.77 AUC from slow live book"
    " shape, nothing from sub-second waves. Taker: limit = stale ask + a premium scaling with the event.")
comp["side"]["description"] = (
    "Maker: both outcomes in every market (VALIDATE-only). Taker: the team that gained in-round, typically the first"
    " informed move against the previous burst (reversal); per-map shares follow bomb plants beyond wins (p 0.03-0.06),"
    " T side 54-57% (n.s.). Side is not scored (two-sided at market level).")
comp["selection"]["description"] += (" Exam lots (listing projection): 25-26% of non-GRID events in leagues unseen by v3 (below the"
                                     " 30% switch threshold; v3 kept, pre-registered); tier-3 non-GRID events are rare there (4 / 6).")

s["target_metrics_notes"]["pnl_baseline"] = ("Iteration 6 (X82): the 'c x in-play public prints' pseudo-PnL correlates with the wallet's per-market PnL"
                                             " at VALIDATE +0.513 / +0.369 (BUILD +0.413 / +0.181); maker leg alone +0.38 / +0.34;"
                                             " taker leg alone +0.10 / +0.13; locked margin +0.82 / +0.75. evaluate() reports"
                                             " pnl_baseline_prints_* and pnl_corr_partial_given_prints.")
if fr:
    s["target_metrics_notes"]["frozen_rule_rerun_iter6"] = {k: fr.get(k) for k in (
        "selection_auc", "selection_baseline", "presence_auc", "presence_baseline", "price_within_tick", "pnl_corr_pearson",
        "pnl_corr_spearman", "pnl_baseline_prints_pearson", "pnl_baseline_prints_spearman",
        "pnl_baseline_prints_traded_pearson", "pnl_baseline_prints_traded_spearman", "pnl_corr_partial_given_prints")}
s["strategy_statement"] = (
    "CS2 (and some Dota 2) in-play bot; from 10-16 a buy-only two-sided maker plus an informed taker, before that a"
    " round-trip taker in GRID tier-1/2 events that traded late. [VALIDATE-only] Selection: whole events (match + all"
    " maps) of non-GRID tier-3/4 leagues, never an event with a GRID series id (0/122), favouring popular events and those"
    " the informed pack also trades; event rule AUC 0.954 vs activity 0.892; part of the skips are bot downtime."
    " [VALIDATE-only] Maker: whole-cent BUY ladders (100 shares, or an event-wide size ramping from ~50 to 100) near the"
    " other makers' best bid on both outcome tokens, re-quoted one side at a time with the pair sum capped near 0.99, never"
    " sells, merges pairs (97% paired, pair cost 0.978). [hypothesis, BUILD-live] Protection: at its own takes it pulls the"
    " complement at +11-19 ms (before any public cancel) and re-posts it ~1.04 s later at K - L; at the informed pack's"
    " other events it does NOT see the event and, in about half of them, follows the first public cancel by ~15 ms, which"
    " barely protects it (hit 39-42%). [hypothesis] Taker: FAK BUYs of the team that gained in-round from a private feed,"
    " mostly the first informed move against the previous burst (plant / retake type), at the stale ask plus a premium that"
    " scales with the event; ~16-20% of the informed bursts in its markets. [VALIDATE-only] Economics: the per-market PnL is"
    " the locked margin of pairs formed ACROSS the two legs (0.82 / 0.75); the maker leg alone reaches 0.38 / 0.34 and an"
    " activity-only pseudo-PnL 0.51 / 0.37, so the outcome item needs the taker input.")
s["iterations"].append({"n": 6, "minutes": int(sys.argv[2]) if len(sys.argv) > 2 else 95, "best_validate_score": 0.8721,
                        "paradigm": "event-level decision unit (take / wave-follow / hit at every informed event) with mechanism tests of the dodge, sequence-composition nulls, outcome co-occurrence baseline",
                        "families": ["wave-locked vs event-locked pulls (X78 / X80)", "per-match coverage state with stratified nulls (X72)",
                                     "outcome activity baseline and single-leg ceilings (X82)", "joint two-token quote (X81)",
                                     "dense live occupancy with sub-second features (X70 / X80)", "exam league mix from the listing projection (X84)",
                                     "led share by league owner and stream platform (X85 / X86)", "funding graph (X74)",
                                     "edge-threshold take reading ruled out by measurement (X83)"]})
s["next_steps"] = [
    "11-01 06-12 development block (BUILD-live) and 11-01 18-24 (VALIDATE-live): X38 chat clock under the pre-registered rule; X47b round-market books;"
    " X54 synchronous pulls; re-run wave_lock.py (H62) and live_occupancy.py (H67) out of sample; X75 deep-state price branches; X79 cooldown timer.",
    "X71 organiser-side live sources (Liquipedia / organiser pages, CSTV relays) and X73 SX chain fills: the remaining key-free source classes for the taker input.",
    "X77 series fair value as a historical price anchor (the only route to a better h1 / h2 price number).",
    "Ask the user: Twitch VOD chat access route (X53, VODs of 10-21/22 expire ~11-04/05), PandaScore token (X55), HLTV page checks (X64), demo downloads (X37), Kick VOD segments (X4 / X22).",
]
s["live_split"] = {"note": "re-registered 2026-10-31 ~21:40 UTC (iteration 6), before any 11-01 record exists: the iteration-2 VALIDATE-live (from 11-01 18:00) falls after the projected end of the budget (~11-01 10:00-12:00 UTC)",
                   "BUILD": "development block 10-31 12-18 UTC", "VALIDATE": "development block 11-01 06-12 UTC and every later development block",
                   "frozen_live_rules": ["final_rule._live_price (LIVE_VIEW_MS 100, PAIR_CAP 0.99)", "H62 wave follower (own-size pull 0-30 ms after the first non-own cancel at pack-only events)",
                                         "H69 1.5-s same-price re-post timer", "live_occupancy.py recipe (refit only on BUILD-live)"],
                   "previous": {"BUILD": "development blocks before 2026-11-01 12:00 UTC", "VALIDATE": "development blocks from 2026-11-01 18:00 UTC on"}}
s["target_metrics_notes"]["price_live"] = ("Iteration 6: frozen live join rule in evaluate() (live_price): BUILD-live 10-31 block, 172 filled maker orders,"
                                           " within one tick 0.424 (exact 0.198) vs last trade 0.187 on the same rows; historical side-adjusted last print"
                                           " 0.313 vs 0.305 on VALIDATE (not adopted).")
s["data_sources"] = list(s.get("data_sources", [])) + [
    "Polygon eth_getLogs (publicnode): USDC.e / USDC Transfer events of the wallet, its owner, 0x51dbdd2b and its signer, 10-12..H (funding_graph.json)",
    "Gamma events listing projection for h1 / h2 (series 10310), fetched with httpx without the shared cache, projected in memory to lot / league / tier / GRID flag (exam_league_mix.json, aggregates only)",
    "api.sx.bet probes: /trades and /trades/consolidated 404, /sports and /leagues/active 200 (listing only)",
    "web search (normal visitor) for organiser / platform of the traded leagues; rdy.gg match page HTTP 403 (not bypassed)",
]
P.write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
print("catalog", len(cat), "open", sorted(k for k, v in cat.items() if v.get("status") == "open"))
