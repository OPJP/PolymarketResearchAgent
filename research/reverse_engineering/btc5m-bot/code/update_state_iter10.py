"""Iteration 10: update state.json (catalog X73-X86 from the iteration-9 panel, components, strategy statement, hypotheses,
data_sources, live_lab, iterations, target_metrics notes; the frozen historical rule and its metrics are unchanged).
Usage: python update_state_iter10.py MINUTES"""
import os, json, shutil, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
P = _ROOT + "/research/reverse_engineering/btc5m-bot/state.json"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
shutil.copy(P, _ROOT + "/.cache/re/btc5m-bot/state_backup_iter9.json")
s = json.load(open(P, encoding="utf-8"))
MIN = float(sys.argv[1]) if len(sys.argv) > 1 else None


def J(name):
    p = f"{R}/{name}"
    return json.load(open(p)) if os.path.exists(p) else None


crowd = J("crowd10.json")
cat = s["catalog"]
I9 = "panel iteration 9"
cat["X73"] = {"status": "tried", "source": f"{I9}, information P1 (Polymarket's 150-ms crypto taker delay in the decision record: arrival-time decisions, PIT-clean windows, busy state, full label, queue model)",
              "evidence": "delay10.py / ctl10.py (results/delay10.json, ctl10.json): fresh-signed taker orders of other wallets in cluster txs reach the match >= 186.5-189.8 ms after signing "
                          "(q1 per hour 13:00-17:00 of 10-31; q5 192.7-203.5 ms; ten fast wallets' minima 186-199 ms); control markets (shared recorder clob_wallets, 500 sampled txs): 35-73 ms floor "
                          "for markets without a delay and ~1,033-1,046 ms on sports in-play markets. D ~ 150 ms + ~35 ms signing / posting. Per-wallet gap between consecutive taker matches: DS q1 254 "
                          "ms (6 of 1,017 gaps < 240 ms), GF q1 196 ms, XM q1 152 ms. PIT-clean vote [m - 650, m - 180) 83.3% on 67.6% voted (placebo 50.2%) vs frozen [m - 600, m - 100) 83.2% on "
                          "65.8%; price at m - 180 90.7% within a tick vs 92.3% at m - 50: pre-registered (side_live_decision_pit, price_live_book_pit, hazard pit_label). Busy state (flag10b): "
                          "P(new decision | flagged) by busy wallets 0 / 1 / 2 = 18.1 / 27.9 / 36.2% (A), 12.9 / 27.8 / 22.2% (C): no suppression. Full label: see X77 / X86. Step 5 "
                          "(queue10.py): P(won) with 0 / 1 / 2+ crowd orders ahead in the delay buffer 67.4 / 63.3 / 45.8% (DS 80.1% vs 68.7%, GF 72.2% vs 61.4%): partly a FIFO "
                          "queue; a third of races with nobody ahead are lost (maker requotes during the hold)."}
cat["X74"] = {"status": "tried", "source": f"{I9}, information P2 (the crowd's signing timestamps as a ms-exact decision record of the shared trigger)",
              "evidence": "fetchcrowd10.py / crowd10.py (results/crowd10.json, crowd10_fast.json): calldata of 45,045 recorded BTC 5m match txs of 10-31 14:55-17:55; 28,293 fresh-signed "
                          "non-operator BUYs (180-2,000 ms sign-to-match; 1,896 wallets) and 7,903 fast ones (180-260 ms; 763 wallets). 100-ms decision-clock grid, fit A, scored C: crowd label "
                          "from venue inputs AUC 0.599 (fast 0.540) vs Polymarket-activity baseline 0.632 (0.656): the crowd follows Polymarket, not the venues. Cluster label (m - 180): frozen "
                          "crowd model 0.606 / 0.572, cluster venue model 0.655, PM activity 0.657. P(cluster | crowd decision in the same 100 ms) 2.1% vs 0.81% (fast 3.2% vs 0.89%). Among "
                          "the top 3% of the crowd model, cluster taken vs skipped AUC 0.702 (fast 0.666). Signature (crowd AUC >= 0.75 from a venue input) not met; the crowd record does not "
                          "reveal the selection input."}
cat["X75"] = {"status": "tried", "source": f"{I9}, information P3 (the delay regimes 250 / 50 / 150 ms and other dated rule changes as natural experiments)",
              "evidence": "delayreg10.py / vol10.py / version10.py / version10b.py (results/delayreg10.json, vol10.json, version10*.json; operator OrderFilled logs, hour 16-17 UTC, Mon-Thu; "
                          "drpc's free plan now caps eth_getLogs at ~100 blocks per call, HTTP 400 above): cluster maker share 45.1% (D 250, 08-10..13) -> 25.8% right after 08-17 (D 50; "
                          "-19.2 points, day-bootstrap CI [-28.0, -6.4]) -> 57.8% at 08-31..09-03 (still D 50) -> 47.4% after 09-04 (D 150; -10.4 [-19.6, -2.8], opposite to the "
                          "prediction). Not volatility (corr with log 1-s vol -0.15; regime effects unchanged with vol in the OLS). Confounded by BOT VERSIONS: 08-12 orders signed fresh "
                          "(5.6% in the ladder bursts, size 100), 08-19 30% in bursts (size 30, taker share 75%), 09-01 and 09-08 100% pre-signed ladders (menu 20 / 60 / 80 / 200). The "
                          "delay regimes do not isolate D; the version history (C4) is the next step (switch date in version10b)."}
cat["X76"] = {"status": "open", "source": f"{I9}, information P4 (record PolyBolt's public price.polymarket next to the CLOB market channel)",
              "evidence": "Contract read (https://ws-live-v2.polymarket.com/asyncapi.json, HTTP 200, 63 KB, 10-31 21:35 UTC): price.polymarket is public (no auth), filter {asset_id}, envelope "
                          "{v, channel, seq, ts producer ms, snapshot, dropped, payload {best_bid, best_ask, timestamp}}. Recorder code/rec_pb10.py launched 21:36 UTC (pid 15792), sleeps until "
                          "11-01 06:00 UTC (development block), records feed btc5m_pb through the Writer until 11-02 12:00 UTC, cap 150 MB. Not verifiable before 11-01 06:00 (sealed block now); "
                          "the comparison with btc5m_clob_raw2 is the next iteration's."}
cat["X77"] = {"status": "tried", "source": f"{I9}, mechanics P1 (complete the decision record: ghost lost races by a mechanical fingerprint)",
              "evidence": "ghost10.py / ghost10b.py / flag10.py (results/ghost10*.json, flag10.json; 208,198 old-ask insertions 14:55-17:55): the crowd places 41.7k 30-share bids at the old ask "
                          "(median life 48 ms) plus 20 / 24 / 50 / 64 / 88-share bot classes, so DS / GF ghosts are not attributable by size or life; every class is 4-8x over-represented 0-300 ms "
                          "after a visible cluster event (co-racing). XM's 60-share legs: crowd classes follow DS : GF : XM events 2.7 : 1 : 1, unknown 60s 287 : 112 : 23 -> >= 313 XM ghost legs "
                          "(median life 527 ms) vs 363 filled 60-share orders (ALL maker-first): XM >= 1.86 decisions per filled 60-share order (<= 4.4). Skipped flagged instants (top 1% / 3%) carry "
                          "0.24x / 0.17x the taken instants' rate of unknown 60-share insertions and 0.46x / 0.31x of 100-share ones vs 0.53x / 0.43x for crowd sizes: at most ~12% of skips hide a "
                          "decision. The selectivity is real; the ghost legs sit inside visible events."}
cat["X78"] = {"status": "tried", "source": f"{I9}, mechanics P2 (trigger unit = a perp bookTicker event, scored per event)",
              "evidence": "evt10.py (results/evt10.json; Binance USD-M BTC L1 events merged within 50 ms, clean events, label = decision on o in [tau + 150, tau + 700)): A / C 28,070 / 30,812 events, "
                          "base 6.2% / 4.7%; price-level changes 30.0% / 28.7% (0.05-0.2 bp 40.5% / 34.1%), size-only depletion 5.8% / 4.7% and refill 6.1% / 4.4% (= base); o's ask moved by "
                          "tau + 150: 41.9% / 40.5% (price events); OKX / Bybit agreeing 0 / 1 / 2: 4.4 / 6.6 / 12.5% (A), 3.4 / 5.4 / 10.6% (C). Logistic fit A -> C AUC 0.681 vs Polymarket-activity "
                          "baseline 0.574; precision at matched volume 15.1%. The queue-depletion trigger is not supported; no class reaches the 40% signature."}
cat["X79"] = {"status": "tried", "source": f"{I9}, mechanics P3 (decode the cancel rule at server ms; maker-echo fill model in the replica)",
              "evidence": "rmv10.py (results/rmv10.json; 196 never-filled remainders with a located removal; life q10 / 50 / 90 = 44 / 264 / 2,793 ms): at the removal vs a control instant "
                          "inside the same life, o's ask >= L + 1 c 100% vs 99.5% (>= 2 c 57% vs 51%), outbid 47% vs 37%, a venue tick toward o 3.1% vs 4.6%, against o 1.5% vs 0%. Timer-like "
                          "(a drawn TTL of ~0.1-1 s with a long tail); an adverse-tick cancel is rejected; 'leave when the ask moves k c above L' does not discriminate (the ask is above L for "
                          "the whole life). Not done: the maker-echo replica (steps 3-4)."}
cat["X80"] = {"status": "tried", "source": f"{I9}, mechanics P4 (chase episodes as a censored readout of the reservation price)",
              "evidence": "chase10.py (results/chase10.json; 2,155 decisions, 1,174 episodes, 499 with >= 2 decisions): limit steps up 532 / flat 255 / down 194; reach = max limit - "
                          "ask 500 ms before the start q10 / 50 / 90 = -1 / 0 / +3 c (0 / 1 / 1 / 3 c for 1 / 2 / 3 / 4+ decisions); at the stop the next ask is above the max limit in 68%; "
                          "reach vs 100 Delta dS: Spearman 0.20, OLS 0.61 c + 1.00 x. A reservation price R = mid0 + 1.0 Delta dS + 0.6 c is consistent but loose. Interval regression "
                          "(fit A, score C) not done."}
cat["X81"] = {"status": "ruled_out", "source": f"{I9}, mechanics P5 (live state-machine replica for condition 5: large on the first strong event with a flat book, then the own-net overlay)",
              "evidence": "Bounded by X82 (lean10.py): even the wallet's OWN decisions replayed with independent race outcomes and the own-net size feedback correlate with themselves at r = 0.47-0.58 "
                          "pooled (q 0.61-0.70; per wallet 0.41-0.62); a replica that reproduces only part of the decisions (live overlap 8-15%, overlap8 / evt10) and fills its own races correlates "
                          "with the wallet at most at that level times its decision overlap, below 0.5. Condition 5 cannot be reached by a state-machine replica of this kind; the bound is the "
                          "measurement."}
cat["X82"] = {"status": "tried", "source": f"{I9}, assumptions P1 (re-target condition 5 on the large-order lean; PnL ceiling with the own-state size feedback re-simulated)",
              "evidence": "lean10.py (results/lean10.json, lean10_v3.json; VALIDATE 1,904 windows): corr(window PnL, large-only PnL) 0.77 pooled (DS 0.53, GF 0.90, XM 0.81; halves 0.77 / 0.78), "
                          "small-only 0.06; corr(PnL, netLarge x outcome) 0.75; sign(netLarge) = outcome 48.8%. Replay test-retest r (rho) pooled at q = 0.61 / 0.70: sizes fixed 0.70 (0.70) / 0.77 "
                          "(0.77); coupled monotone own-net rule 0.50 (0.52) / 0.58 (0.59); state-consistent 0.47 (0.49) / 0.55 (0.57); full re-draw 0.50 (0.46) / 0.57 (0.53); per wallet 0.41-0.62. "
                          "The feedback brings even a perfect decode to the 0.5 bar: condition 5 is a quantified wall-level bound (race lottery amplified by pyramiding)."}
cat["X83"] = {"status": "tried", "source": f"{I9}, assumptions P2 (selection on episodes: evidence accumulation vs a constant-hazard null)",
              "evidence": "flag10.py / flag10b.py: episodes of top-3% points (gap <= 1 s) A 252 / C 173, take rate 41.7% / 35.3% (points 27.1% / 20.4%); constant hazard p = 0.094 reproduces C by run "
                          "length (9.7 / 29.6 / 38.8 / 61.3% vs 9.4 / 22.0 / 44.0 / 78.5%) but the first-decision hazard by step is 26.2% / 23.1% at the onset point and 2.4-8.4% afterwards; "
                          "onset take rate by onset-tick tercile C 17 / 28 / 50% (A 23 / 29 / 29%); per-step AUC on C: steps 0.723, + instantaneous 0.735, + accumulated evidence 0.728. Neither a "
                          "memoryless thinning nor accumulation: a reaction to the onset event with probability ~1/4-1/2 rising with its strength. Window chi2 / df 2.01 (A), 1.97 (C)."}
cat["X84"] = {"status": "open", "source": f"{I9}, assumptions P3 (large and small as two decision streams; the large stream as a window-level state machine)",
              "evidence": "Partial (lean10): P(large | operator net state on o) short 9.6%, flat 13.5%, long 17.9% on VALIDATE; large orders on the long leg 56.8%, short 33.3%, flat 9.9%; BUILD "
                          "table by wallet DS 4.5 / 6.5 / 9.7%, GF 6.6 / 14.9 / 19.9%, XM 2.4 / 6.0 / 8.6% (short / flat / long). Live quick check (results/large10.json, 2,155 sized "
                          "decisions of 10-31 14:55-17:55, 5.2% large): P(large) 4.7% at episode onsets vs 5.7% later, 5.9 / 4.9 / 5.2% by window rank: no initiation structure on "
                          "this Saturday. Initiation from public features while flat needs the weekday development blocks."}
cat["X85"] = {"status": "open", "source": f"{I9}, assumptions P4 (a window-level take rate: collateral, set state, schedule)",
              "evidence": "Overdispersion replicated (flag10: chi2 / df 2.01 on A, 1.97 on C against the constant-hazard null). Collateral path from USDC Transfer logs not built."}
cat["X86"] = {"status": "tried", "source": f"{I9}, assumptions P5 (does every decision leave a book trace? never-filled remainders)",
              "evidence": "ghost10.py (results/ghost10.json): 271 T-first orders with an unfilled remainder and no maker fill: insertion found at (o, L) 17-33 ms before the trade message for 88.2% "
                          "(filled-later remainders 97.4%); DS 88%, GF 88%, XM 89%; 30-share 87.5%, 100-share 95.7%. Decisions leave a trace; no hidden FAK / rejected class at scale."}
cat["X72"]["evidence"] += (" | Iteration 10: the skips are genuine non-decisions (X77: unknown 60 / 100-share insertions at skipped instants 0.17-0.46x the taken rate vs 0.43-0.53x for crowd "
                           "sizes); the take probability is front-loaded at the episode onset (23-26%, then 2-8% per 100 ms) and rises with the onset tick on C (17 / 28 / 50%), not with accumulated "
                           "evidence (X83); per-event Binance price-level ticks 29-30% (X78); busy wallets do not suppress (X73). Still open: what decides ~1 in 3 onsets.")
cat["X27"]["evidence"] += " | Iteration 10: folded into X85 (window-level rate); not run."
v10b = J("version10b.json")
cat["X9"]["evidence"] += (" | Iteration 10 (version10.py / version10b.py, V2 calldata of sampled cluster txs, hour 16-17 UTC): bot VERSIONS in August-September: 08-01..18 orders signed "
                          "FRESH (2-16% inside the ladder burst phases; one size per day, changing almost daily: 90, 60, 50, 100, 20, 80, 30), 08-19..21 28-36%, from 08-22 100% "
                          "pre-signed two-size ladders (30 / 90, 25 / 75; switch between 08-21 and 08-22 16:00 UTC, five days after the 250 -> 50 ms delay cut), 09-01 / 09-08 a "
                          "20 / 60 / 80 / 200 menu; 10-09..22 60/100, 30/50, 30/100. Per-day August series in results/version10b.json"
                          + (f" ({len(v10b)} days)" if v10b else "") + ". Full change-point search not done.")
open_ids = sorted([k for k, v in cat.items() if v.get("status") == "open"], key=lambda k: (k[0], int(k[1:]) if k[1:].isdigit() else 0))
s["catalog_open_after_iteration10"] = open_ids

comp = s["components"]
comp["timing"]["description"] = ("Decision = submission of a pre-signed ladder order about 100-150 ms after a Binance USD-M / OKX / Bybit microprice tick toward the outcome; under Polymarket's "
                                  "150-ms crypto taker delay the order ARRIVES ~150 ms before its match and the bot's last input is ~m - 180 ms (measured: fresh-signed floor 186-190 ms vs 35-73 ms on "
                                  "no-delay markets). Selective and real: ~1.45-1.7 decisions per filled order for DS / GF (XM's 60-share legs >= 1.86); skipped flagged instants are not hidden lost races; "
                                  "the take probability is front-loaded at the onset of a flagged episode (23-26%, rising with the onset tick), then 2-8% per 100 ms; Binance price-level ticks with "
                                  "other venues agreeing are the strongest event class (29-41%). What decides which onsets it takes is open. Decision-level hazard frozen on the exam feeds: AUC 0.656 "
                                  "vs 0.598 out of sample (0.728 on decisions, lab feeds); historically presence on block seconds 0.875 vs 0.821 (+0.054, CI [0.051, 0.056]).")
comp["timing"]["confidence"] = 0.75
comp["side"]["description"] = ("Per decision (live): the microprice vote of the fast venues before the decision; PIT-clean window [m - 650, m - 180) (= [a - 500, a - delta)) 83.3% on 67.6% "
                                "voted vs the frozen [m - 600, m - 100) 83.2% on 65.8% (16:04-17:55, exam feeds; pre-registered for 11-01 06-12); the same for won and lost races (80.6 / 80.5%); "
                                "full-coverage fallbacks ~75%; at the block clock 72.7% per order (76.7% side model). No wallet is one-sided beyond its order-count null, so the side condition "
                                "does not bind in substance. The side does not reference the operator's book, an exact-strike FV or a stale-quote edge; the underdog tilt is consistent with an "
                                "implied-vol FV (hypothesis).")
comp["price"]["description"] = ("Limit = o's ask it saw before arriving: o's ask at m - 180 ms (a - delta, PIT-clean) is within a tick for 90.7% (exact 72.1%), at m - 50 92.3% (78.2%); 95.1% within a "
                                 "tick on VALIDATE calldata (trivial touch anchor, stated as such); maker-first orders are the same limits after a lost race; 16% of taker orders deliberately 1+ c above "
                                 "the touch (not the depth-cover level), which under the delay covers an earlier queued order lifting the touch during the hold.")
comp["size"]["description"] = ("Fixed (small, large) menu per day; the large size follows the OPERATOR's own net on the outcome (own state): P(large) short 9.6% / flat 13.5% / long 17.9% on VALIDATE "
                                "(large orders on the long leg 57%: pyramiding); within-wallet AUC GF 0.75-0.77, XM 0.67-0.70, DS 0.58-0.59 with W4 in the net vs market controls 0.35-0.55. The "
                                "per-window PnL IS the large-order lean (corr 0.77 with large-only PnL; sign(netLarge) = outcome 48.8%, a coin), and the feedback makes the lean a race-seeded "
                                "lottery: the wallet's own decisions replayed with independent races and the own-net size rule correlate with themselves at 0.47-0.58 (sizes fixed 0.70-0.77). "
                                "Live (50 large orders; hypothesis): large is more likely on strong ticks (pre-registered test 11-01 06-12).")
comp["exit"]["description"] = ("Taker remainders (38% of taker-first orders on 10-31) and lost races rest as GTC bids at the old ask for ~0.1-1 s (never-filled remainders: median life 240 ms, "
                                "p75 0.8 s, p90 3 s; 88% leave a book trace); 46% of remainders get a maker fill (10-31); every position is held to resolution (no sells, merges, splits); 87% of "
                                "shares end paired at 0.979; REDEEM per window; TAKER_REBATE = 0.5 x the previous day's taker fees; a wallet has one order in flight (the delay hold plus a round "
                                "trip: DS q1 gap 254 ms), so decisions fan out across wallets and XM, the last leg, loses all its 60-share races on 10-31.")
for k in ("timing", "side", "price", "size", "exit"):
    comp[k]["tag"] = "VALIDATE-only"
s["strategy_statement"] = (
    "One operator runs a TypeScript clob-client bot on three (plus a fourth) wallets in every BTC 5-minute Up/Down window, and only there [VALIDATE-only]. It pre-signs a ladder of BUY "
    "orders on both outcomes at every cent three times per window [VALIDATE-only] and submits one about 100-150 ms after a microprice tick of the Binance USD-M / OKX / Bybit BTC and "
    "ETH perps toward an outcome, at the ask it saw just before (deliberately 1+ c higher in 16% of orders) [VALIDATE-only]. Polymarket holds every marketable order 150 ms on these "
    "markets (measured floor 186-190 ms from signing vs 35-73 ms elsewhere), so the bot races the crowd in that delay queue [VALIDATE-only]. It is selective: it takes about one in "
    "three flagged episodes, mostly right at their onset and more often for stronger ticks; the skipped instants are genuine non-decisions, not hidden lost races [VALIDATE-only; "
    "what selects the onsets it takes is open]. The side is the tick direction (83% per decision, point-in-time clean; 95%+ on strong ticks) [VALIDATE-only]. A lost race rests at "
    "the old ask for ~0.1-1 s and fills as maker about half the time [VALIDATE-only]. The size is small unless the operator's own book is flat or long the outcome, so large orders "
    "pyramid the leg it already holds [VALIDATE-only, own state]. Positions are held to resolution; 87% of shares end in complete sets bought at 0.979 [VALIDATE-only]. Income = "
    "locked sets (~2.1 c per pair) and the 50% taker-fee rebate; the large-size lean is a coin with respect to the outcome and carries the per-window PnL variance [VALIDATE-only]. "
    "Because race outcomes seed the lean and the size rule amplifies it, even the true rule replayed correlates with the wallet's per-window PnL at only ~0.5 [VALIDATE-only]. "
    "The pre-signed ladder is the current version: until 08-18 the bot signed its orders fresh with one size per day, and it switched to pre-signed two-size ladders on 08-22, five days after Polymarket cut the taker delay from 250 to 50 ms [VALIDATE-only]. "
    "Nothing is exam-verified.")
s["status"] = "continue"
s["environment_notes"] = s.get("environment_notes", []) + ["10-31 21:50 UTC: drpc free plan refuses eth_getLogs above ~100-199 blocks (HTTP 400, misleading message 'ranges over 10000 blocks'); publicnode refuses archive ranges without a token. final_rule.cluster_fills falls back to 100-block chunks."]
hy = s["hypotheses"]
nxt = max(int(h["id"][1:]) for h in hy) + 1
new = [
    ("taker delay (X73)", "D from the fresh-signed sign-to-match floor; PIT-clean vote and price", {"floor_q1_ms": "186.5-189.8", "control_floor_ms": "35-73 (no delay), ~1,035 (sports in-play)",
     "vote_pit_650_180": "83.3% on 67.6%", "vote_frozen": "83.2% on 65.8%", "price_m-180_within_tick": 0.9074, "price_m-50": 0.9233}, "D = 150 ms confirmed; PIT-clean versions pre-registered"),
    ("decision record completeness (X86)", "never-filled remainders found in the book", {"found_never_filled": 0.8819, "found_filled_later": 0.974, "cancel_life_median_ms": 240},
     "every decision leaves a trace (88-97%)"),
    ("ghost lost races (X77)", "fan-out fingerprint attribution and skipped-instant test", {"XM_ghost_legs_lb": 313, "XM_filled_60": 363, "skipped_over_taken_60_top1": 0.24,
     "skipped_over_taken_crowd_top1": 0.525}, "skips are not hidden decisions (F1 rejected)"),
    ("episode hazard (X83)", "first-decision hazard by step since onset; accumulation", {"onset_hazard_A_C": [0.2619, 0.2312], "later_steps": "0.024-0.084", "auc_C_steps": 0.7232,
     "auc_C_inst": 0.7346, "auc_C_accum": 0.7283}, "front-loaded at onset; not memoryless, not accumulation"),
    ("busy state (X73 step 3)", "P(decision | flagged) by busy wallets", {"A": [0.1808, 0.2787, 0.3617], "C": [0.1287, 0.2784, 0.2222]}, "no suppression (F7 rejected)"),
    ("large-order lean and feedback ceiling (X82)", "decomposition and replays with own-net size feedback", {"corr_pnl_large": 0.7732, "sign_netL_outcome": 0.4875,
     "r_tt_fixed_q61_q70": [0.6979, 0.774], "r_tt_coupled_q61_q70": [0.4973, 0.5775], "r_tt_state_q61_q70": [0.4716, 0.5483]}, "condition 5 bounded near 0.5 even for the true rule"),
    ("bot versions around the delay changes (X75 / X9)", "signing mode and size menu per period from calldata", {"in_bursts_0812_0819_0901_0908": [0.0556, 0.2988, 1.0, 1.0],
     "taker_order_share": [0.4365, 0.753, 0.4023, 0.4822], "cluster_maker_share_by_period": [0.4506, 0.2582, 0.5777, 0.4741]}, "the maker share follows the version (fresh-signed vs pre-signed ladders) as much as D"),
    ("delay-queue race model (X73 step 5)", "P(won) by crowd orders ahead in the 150-ms buffer", {"P(won|0,1,2+ ahead)": [0.6735, 0.633, 0.4583], "DS": [0.8011, 0.6871], "GF": [0.7215, 0.614]},
     "partly FIFO; maker requotes during the hold decide a third of the races"),
    ("event-level trigger (X78)", "Binance bookTicker events by class", {"price_level_P_A_C": [0.3003, 0.2873], "deplete_P_A_C": [0.0582, 0.0468], "auc_C": 0.681, "auc_C_base": 0.5737},
     "price-level ticks with venue agreement strongest; depletion not a trigger"),
]
if crowd:
    new.append(("crowd decision record (X74)", "crowd fresh-signed decisions as the shared trigger", {k: v for k, v in crowd.items() if not k.startswith("_")}, crowd.get("_verdict", "see NOTES")))
for i, (fam, desc, vm, ver) in enumerate(new):
    hy.append({"id": f"H{nxt + i}", "family": fam, "description": desc, "validate_metrics": vm, "verdict": ver})
s["data_sources"] += ["Iteration 10: it10/ghost_cand.parquet (208,198 old-ask insertions with fates, 10-31 14:55-17:55)",
                      "Iteration 10: calldata of 500 sampled clob_wallets match txs (no-delay / sports-delay control, decoded in memory)",
                      "Iteration 10: it10/cdall10.parquet (calldata of every recorded BTC 5m match tx 10-31 14:55-17:55) and it10/txms10.parquet",
                      "Iteration 10: PolyBolt AsyncAPI contract (ws-live-v2.polymarket.com/asyncapi.json); recorder rec_pb10 from 11-01 06:00 UTC"]
s["live_lab"].append({"what": "rec_pb10.py launcher (pid 15792): sleeps until 11-01 06:00 UTC, then records PolyBolt public price.polymarket best bid / ask (producer ms, seq, dropped) "
                              "for the current and next BTC 5m tokens as feed btc5m_pb through tools/live.py Writer (every block filed by the Writer, never read in sealed blocks); cap 150 MB; "
                              "status .cache/re/btc5m-bot/rec_pb10.status", "start": 1793512800, "end": 1793620800})
s["target_metrics_notes"]["iteration10"] = ("Historical rule unchanged (target_metrics as in iteration 9). New pre-registered live keys (first clean test 11-01 06-12): side_accuracy_live_decision_pit "
                                            "(16:04-17:55 in sample: 83.3% on 67.6%), price_within_tick_live_pit (90.7%), presence_live_decision_auc_pit. Condition 5 account: the true rule's "
                                            "test-retest with the own-net size feedback is 0.47-0.58 pooled (lean10), so pnl_corr >= 0.5 is at the edge even for a perfect decode.")
it = {"n": 10, "minutes": MIN, "best_validate_score": 0.9132, "block_seconds_presence": 0.8747, "block_seconds_stronger_baseline": 0.8211, "pnl_corr": 0.1755,
      "paradigm": "the decision record under the 150-ms taker delay: ghost legs and the reality of the selectivity, episode-onset hazard, and the PnL ceiling with the own-state size feedback",
      "families": ["taker delay measured with a no-delay control; PIT-clean vote / price / hazard label pre-registered (X73)", "never-filled remainders in the book (X86)",
                   "ghost lost races by fan-out fingerprint; skipped-instant test (X77)", "episode-onset hazard vs constant hazard vs accumulation (X83)", "busy state from in-flight orders (X73)",
                   "large-order lean decomposition and feedback replays (X82)", "event-level bookTicker trigger (X78)", "state-machine replica bound (X81)",
                   "PolyBolt public channel recorder (X76)", "crowd signing-time decision record (X74)",
                   "delay-queue race model (X73 step 5)", "remainder cancel rule (X79)", "chase episodes / reservation price (X80)",
                   "delay regimes as natural experiments with volatility control (X75)", "bot versions August-October from calldata (X9 / C4)",
                   "exam-path robustness: chunked eth_getLogs in cluster_fills (drpc free-plan limit)"]}
s["iterations"].append(it)
json.dump(s, open(P, "w", encoding="utf-8"), indent=1)
print("open", len(open_ids), open_ids)
