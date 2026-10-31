"""Iteration 4 state.json update (replaces entries by id, never appends duplicates)."""
import json
from pathlib import Path

RES = Path(__file__).resolve().parents[2]
P = RES / "state.json"
s = json.load(open(P))

cat = s["catalog"]
cat["X8"] = {"status": "tried", "source": "information panel P5 (iter 1)",
             "evidence": "Clock-free use of the bo3 per-round team stats (iter 4, X50, event_type_counts.json): 91 matched maps; per-map share of the wallet's take events on a team vs the team differences in round wins, opening kills, clutches, bomb plants, kills: opening kills carry no weight (alone p 0.71; beyond round wins coef -0.17, p 0.44), round wins weak (p 0.09-0.12), bomb plants the strongest (corr 0.38; p 0.059 beyond W, FK, CL). Per-round labels with a clock remain part of X37 (demo ticks)."}
new = {
    "X37": ("open", "information panel P1 (iter 3): demo-tick event clock from bo3-hosted CS2 demos",
            "bo3.gg /api/v1/games/<id> (game 190260): demo_url is a relative path (demos/manually_uploaded/...-m3-mirage.dem), demo_data null, game_rounds without kill times, duration includes pauses; download host unverified (bo3.gg/<path> serves the SPA, files.bo3.gg 404 per the panel). Needs the user's consent to download 50-300 MB demos and to install a demo parser from PyPI; free disk fell to 2.9 GB at 17:53 UTC 10-31. Not run."),
    "X38": ("open", "information panel P2 (iter 3): live chat clock (Twitch / Kick)",
            "Recorder started 18:16 UTC 10-31 (code/iter4/chat_recorder.py, feed tommy_chat, worker pid 28984): anonymous Twitch IRC (justinfan + the public anonymous placeholder pass, login verified: 001 Welcome), channels = Gamma resolutionSource of non-GRID CS2 events in play that started in development blocks; stores only channel, tmi-sent-ts, receive time, message length and emote count (no text, no user names); idles in sealed blocks; hard stop 11-03 00:00 UTC, 50 MB. Kick not attempted (its chat socket needs a client key read from Kick's web page; the panel asked to confirm with the user). Analysis waits for the 11-01 06-12 development block."),
    "X39": ("tried", "information panel P3 (iter 3): official data-rights map as the selection boundary",
            "Falsifier checked first: PGL holds an exclusive official data partnership with Oddin.gg for its CS2 / Dota 2 events (2024-2026, >= 11 tier-1 CS2 tournaments; europeangaming.eu 2024-04-23, sbcamericas.com 2024-04-29), yet the wallet traded 9 of 13 PGL events (PGL Bucharest Closed Qualifier, tier 4, community co-streams). An organiser-level holder flag predicts a skip: the organiser-level form is falsified; an event-level coverage flag is not public. Not adopted."),
    "X40": ("tried", "information panel P4 (iter 3): slow UI takers as a historical broadcast clock",
            "ui_clock.json (16-22 Oct, 1,630 wallet takes, retail <= 20 orders per address): retail net flow on its team is contra in 0-12 s (-95) and turns positive only at 68 s (mid-size 36 s); takes followed by a >= 4c public jump within 10 s: contra -65 in 0-12 s, turn at 72 s; takes whose next jump is > 40 s away: no contra, turn at 40 s. The retail response depends on the public repricing (it trades against the jump), not on a fixed delay after its event: no broadcast-delay signature; not usable as a clock."),
    "X41": ("open", "information panel P5 (iter 3): Azuro / SX on-chain fills",
            "Azuro data endpoints fail: thegraph.azuro.org and thegraph-1.onchainfeed.org -> DNS failure (getaddrinfo), api.onchainfeed.org/api/v1/public/market-manager/sports -> 404; the LiveCore contract address was not found in one web search (Azuro-protocol GitHub subgraphs repo to check next). SX: odds endpoints need a key (iter 3, X23). Low priority (sparse fills, ~2-s blocks, venue bet delays)."),
    "X42": ("open", "information panel P6 (iter 3): Dota 2 natural experiment at 3-5 s resolution",
            "The 30-s OpenDota recorder (tommy_dota_live) runs; it has no overlap yet with a wallet Dota take in a development block (its dev-unit Dota trades were 12:59-13:44 UTC, the recorder started 16:43). 3-5-s polling over days exceeds OpenDota's free tier (60 calls/min, ~50k per month); a 10-s variant restricted to dev blocks with its Dota events in play is the feasible form."),
    "X43": ("tried", "mechanics panel P1 (iter 3): maker quote = pair-sum-capped join of others' best bids, on others' book",
            "quote_others_book.json (own recorder, server clock, 10-31 14:51-18:00, 171 filled CS2 maker orders, own levels subtracted by size fingerprint 100/68/58/54): within one tick (0.01) of the full-book best bid 5 ms before signing 52.6% (exact 21.6%), of others' best bid 45.6% (18.7%), pair-cap rules min(obb, K - obb_other) 24-46% for K 0.96-0.98, last trade 19.3%. 41.5% of its filled orders sit ABOVE others' best bid (+1c 20.5%): fill selection on censored orders. The pair-sum-cap rule is not supported on filled orders (the panel's 59% was on resting-ladder states); no 80% price rule."),
    "X44": ("tried", "mechanics panel P2 (iter 3): queue-aware replay of a public quote on the matched-order record",
            "queue_replay.json: join others' last observed best bids (observations only from txs without any wallet order, LAT 2 s), pair cap K, strict price-time-priority fills, the wallet's takes removed: BUILD -5.2% / VALIDATE -4.4% (pair cost median 1.005 vs the wallet's 0.978), per-market PnL corr Pearson/Spearman BUILD -0.32/-0.13, VALIDATE -0.04/-0.04, while paired volume tracks the wallet (Spearman 0.79 / 0.91). Inserting its pulls (oracle) changes corr by <= 0.03; K 0.96/0.98, 3 levels, IMAX 200, LAT 1 s all similar. The margin is not reproducible from tape + calldata: outcome needs a live-book replay (future blocks)."),
    "X45": ("tried", "mechanics panel P3 (iter 3): FAK limit premium as the bot's private post-event value",
            "premium_value.json: Spearman(premium, bought team's move) 0.26 at 10 s (event-bootstrap CI [0.16, 0.35] BUILD, [0.17, 0.35] VALIDATE), 0.13-0.17 at 60 s; other takers 0.04-0.05 at 10 s and ~0 at 60 s; VALIDATE 60-s move by premium 0/1/2/3/4/5+c: +2.2/+2.0/+2.1/+5.5/+5.0/+9.6c. No levelling at the limit: the price sits a median +2 to +5c above its limit at 60-120 s. Fan-out (56 pairs): match/map premium ratio 0.58 (map 1) and 0.50 (map 2) = the series sensitivity at q = 0.5 (0.5). Supported: a private valuation with a margin, propagated from map to match."),
    "X46": ("tried", "mechanics panel P4 (iter 3): zero-fill FAK attempts by the FAK-return re-post fingerprint",
            "pull_attrib.json (own-size pulls 100/68/58/54, >= 2 levels within 5 ms): with an on-chain take 33 pulls, strict signature (no own re-add in [60, 1000) ms, >= 1 in [1000, 1150) ms) 63.6%, team up >= 1c at 10 s 87.9%; without a take 829 pulls, signature 3.5% vs 2.7% at random times; the 29 signature pulls without a take go up 62.1% / down 17.2% (random 25.8% / 28.5%). Hidden attempts about 7-11 against 33 visible (20-35% more attempts than fills); the signature alone is not specific."),
    "X47": ("open", "assumptions panel P1 (iter 3): round markets of the same map as the first public trace",
            "(a) historical, VALIDATE (round_takers_hist.json; 39 events, 665 round markets, 529 decoded round-market taker txs): a round-market taker signed in the 1 s before its takes in 0.93% (controls 0.21-0.72%), in the 200 ms before in 0.10% (0-0.10%), in the 500 ms after in 6.7% (controls 0.2-0.8%; the 3-wallet cluster among them): round-market takers follow it, none leads. (b) live books: recorder tommy_cs2_rounds started 17:36 UTC (code/iter4/round_recorder.py, worker pid 29380, 38-41 markets); the wallet made no take between 17:36 and 18:00, so the book test waits for the 11-01 06-12 development block."),
    "X48": ("open", "assumptions panel P2 (iter 3): the input is a live odds / win-probability feed",
            "(a) premium test done (X45): premium scaling is wallet-specific and the price does not level off at its limit (+2-5c above at 60-120 s), so 'buy up to the new fair price' is not supported; a model value with a margin fits. (b) probes of in-play odds sources (1win, Stake, Thunderpick, GG.bet, Pinnacle frontends; odds-api.io needs a key from the user) not run: terms to be checked first."),
    "X49": ("tried", "assumptions panel P3 (iter 3): order-level attribution of the earliest cancels",
            "pull_attrib.json (39 takes, 10-31 14:50-18:00, server clock): its own pull (equal-size multi-level or 100-share cancels) follows 89.7% of its takes at +11 / +14 / +19 ms (p10 / p50 / p90), sizes 100 (19), 68 (8), 54 (7), 58 (1). A non-own cancel precedes its first own cancel in 28.6% of takes; one lies in the 50 ms before signing in 10.3% (about the base rate); so about 18% of takes see an unattributed cancel between its signing and its pull (a ~14-ms window, about 6x the ~3% base rate). Others' first cancel after its own pull: p10 -35, p25 -6, p50 +8, p75 +88 ms. Not every fast cancel is a reaction to its pull: some makers act on the same event within ~10-15 ms (caveat: remainders of its own partly filled levels can carry odd sizes)."),
    "X50": ("tried", "assumptions panel P4 (iter 3): pulls as the unit of the taker decision; clock-free event-type test",
            "Pulls as units: X46. Clock-free test (event_type_counts.json, 82 maps, 541 take events): binomial GLM with map fixed effects of its take-event share per team: dW alone 0.28 (p 0.12), dFK alone 0.06 (p 0.71), dFK beyond dW -0.17 (p 0.44), dBP beyond dW/dFK/dCL +0.60 (p 0.059; corr 0.38, the highest). P4e: dW p 8e-8, dFK beyond dW p 0.59, dBP beyond -0.67 (p 0.0008). The opening-kill reading is not supported; bomb plants are the leading candidate (weak power)."),
    "X51": ("tried", "assumptions panel P5 (iter 3): the GRID taker regime as a natural experiment on the input's latency class",
            "grid_latency.json (decision proxy = block time - 2 s for every group): bet-on team vs its price 60 s before the decision: taker regime GRID (1,435 trades, 70 markets) +1.41c at -10 s, +2.86c at 0, +6.78c at +60 s; taker regime non-GRID (208, 15 markets) +0.97 / +2.04 / +5.62c; maker regime takes (1,629) -0.85 / -0.98 / +3.06c. In the taker regime, GRID and non-GRID alike, about 30-40% of the move came before its decision (late, momentum-like); in the maker regime the path is flat or falling before and the move comes after. The switch on 10-16 changed the input's speed (and the client: pre-signed orders before, immediate signing after), not only the universe."),
    "X52": ("tried", "assumptions panel P6 (iter 3): one operator across wallets via the signer EOA",
            "signer_check.json (51 txs decoded): the 3-wallet cluster 0x72aaaaf9 / 0xfe8a28be / 0x2529c68d are POLY_PROXY (sigType 1) with three different signers (0xf15f4f45, 0x21ac60ff, 0x799204d1); P93 signer 0xbac5c53a, Pf1 0x5dfc48b5, 0x893575c7 0xdb889f28; the wallet, P4e and the fast late makers are deposit wallets (sigType 3, signer = the wallet; owners differ, iter 2). No signer shared by two makers. Funding links not checked."),
}
for k, (st, src, ev) in new.items():
    cat[k] = {"status": st, "source": src, "evidence": ev}

hyp = {h["id"]: h for h in s["hypotheses"]}
for i, f, d, m, v in [
    ("H35", "outcome-queue-replay", "V5: a public quote rule (join others' observed bids, pair cap) with queue-priority fills reproduces the per-market PnL ranking.",
     {"BUILD_ret": -0.0516, "VALIDATE_ret": -0.0438, "corr_P_S_BUILD": [-0.323, -0.129], "corr_P_S_VALIDATE": [-0.038, -0.035], "paired_volume_spearman": [0.792, 0.908], "pair_cost_median": 1.0053},
     "rejected on tape + calldata: volume allocation reproduced, margin and PnL ranking not; oracle pulls do not help"),
    ("H36", "taker-premium-valuation", "The FAK premium encodes a private estimate of the event's price impact.",
     {"spearman_10s_BUILD": 0.257, "ci": [0.16, 0.353], "spearman_10s_VALIDATE": 0.258, "ci_V": [0.173, 0.346], "other_takers_10s": [0.051, 0.04], "fanout_ratio_map1_map2": [0.58, 0.5]},
     "supported (VALIDATE): wallet-specific dose-response; map-to-match propagation at the series sensitivity; limit kept below the post-event price"),
    ("H37", "input-odds-feed", "V4: an in-play odds feed; the limit is the new fair price.", {"median_gap_price_minus_limit_60s_c": "+2..+5"},
     "not supported in the 'limit = fair price' form (price ends above the limit); odds-source probes pending"),
    ("H38", "round-market-lead", "V3: round-market participants act before the wallet.", {"prior_1s": 0.0093, "controls": [0.0021, 0.0072, 0.0041], "next_500ms": 0.0671},
     "rejected for takers (historical); book part pending (live)"),
    ("H39", "zero-fill-attempts", "Mechanics P4: zero-fill FAK attempts are as many as visible takes.", {"sig_with_take": 0.636, "sig_no_take": 0.035, "sig_random": 0.027, "dir_up_sig_no_take": 0.621, "random_up": 0.258},
     "partly: about 7-11 hidden attempts vs 33 visible (20-35%)"),
    ("H40", "only-fast-leader", "Assumptions P3: all cancels in the first ~40 ms are the wallet's own.", {"own_pull_share": 0.897, "other_before_own": 0.286, "other_pre_sign_50ms": 0.103},
     "rejected in the strong form: ~18% of takes see unattributed cancels between its signing and its pull"),
    ("H41", "event-type", "Which in-round event the taker follows (clock-free per-map counts).", {"dFK_p_beyond_dW": 0.44, "dBP_p": 0.059, "corr_BP": 0.38},
     "opening kills not supported; bomb plants leading candidate (weak)"),
    ("H42", "switch-latency", "Assumptions P5: the 10-16 switch changed the input's latency class.", {"GRID_pre_move_c": 2.86, "nonGRID_taker_regime_pre_move_c": 2.04, "maker_regime_pre_move_c": -0.98},
     "supported: taker-regime trades were late in GRID and non-GRID alike; maker-regime takes are first movers"),
    ("H43", "maker-quote-others-book", "Mechanics P1: the maker quote is a pair-sum-capped join of others' best bids.", {"join_others_within_tick": 0.456, "full_book_bid": 0.526, "cap_097": 0.316, "above_others_bid": 0.415},
     "not supported on filled orders (live BUILD, 171 orders)"),
    ("H44", "data-rights-boundary", "Information P3: selection = events without an official data holder.", {"PGL_traded": "9/13", "PGL_holder": "Oddin.gg"},
     "organiser-level form falsified by PGL"),
]:
    hyp[i] = {"id": i, "family": f, "description": d, "validate_metrics": m, "verdict": v}
s["hypotheses"] = list(hyp.values())

ll = [x for x in s["live_lab"] if "tommy_cs2_rounds" not in x.get("what", "") and "tommy_chat" not in x.get("what", "")]
ll.append({"what": "own recorder, feed tommy_cs2_rounds (code/iter4/round_recorder.py): CLOB books of the round / map-handicap / total markets of NON-GRID CS2 events whose game start is in a development block; near-touch format of tommy_cs2_near; idles in sealed blocks; detached (launcher pid 33544, worker pid 29380), hard stop 2026-11-03 00:00 UTC, 200 MB cap", "start": 1793468189, "end": 1793664000})
ll.append({"what": "own recorder, feed tommy_chat (code/iter4/chat_recorder.py): anonymous Twitch chat timing (channel, tmi-sent-ts, receive time, message length, emote count; no text or names) of the stream channels of non-GRID CS2 events that started in development blocks; idles in sealed blocks; detached (launcher pid 27360, worker pid 28984), hard stop 2026-11-03 00:00 UTC, 50 MB cap", "start": 1793470574, "end": 1793664000})
s["live_lab"] = ll

s["components"] = {
    "selection": {"confidence": 0.7, "tag": "VALIDATE-only",
                  "description": "Whole events of non-GRID CS2 leagues (never a GRID event: 0/122), a subset of the events the informed pack covers; event logistic (league rate with GRID zeroing + pre-game popularity) AUC 0.954 vs activity 0.892 (gain +0.062, p 0.002), recall 0.72 at lift 3.3. An organiser-level official-data-holder flag is falsified (PGL: Oddin.gg holder, 9/13 traded)."},
    "timing": {"confidence": 0.45, "tag": "hypothesis",
               "description": "Taker: at in-round events of an unobserved feed; on the server clock it signs before every public trace (CS2 match / map books; round-market takers only follow it: 0.9% before vs 6.7% after). It pulls its own complement ladder in 90% of takes at +11/+14/+19 ms; ~18% of takes see other cancels between its signing and its pull (shared event, not only reactions); ~20-35% more attempts than fills (zero-fill FAKs). Before 10-16 its trades were late (+2.9c pre-move in GRID), from 10-16 it moves first. Maker: quotes from game start; re-posts the complement ~1.04 s after its takes (VALIDATE-only)."},
    "side": {"confidence": 0.5, "tag": "hypothesis",
             "description": "Maker: both outcomes (VALIDATE-only). Taker: the team that gained in-round; per-map take shares follow round wins and bomb plants (corr 0.38, p 0.06), not opening kills (p 0.44 beyond wins)."},
    "price": {"confidence": 0.4, "tag": "VALIDATE-only",
              "description": "Maker: whole-cent BUYs near the bid (filled orders vs the live full-book bid 52.6% within tick, vs others' bid 45.6%; 41.5% above others' bid by fill selection; last-print anchor 0.305 on VALIDATE). Taker: limit = stale ask + a premium that grows with the event (wallet-specific Spearman 0.26 with the 10-s move), kept 2-5c below the 60-120 s price; match-leg premium = map-leg premium x series sensitivity (~0.5)."},
    "size": {"confidence": 0.65, "tag": "VALIDATE-only",
             "description": "Maker 100 shares in CS2 (inventory-scaled 54/58/68 seen in its pulls), 10 in Dota 2. Taker: about 0.3x of the pre-event depth up to its limit; fills ~98% of what the wave leaves; 1000/2000 caps fading."},
    "exit": {"confidence": 0.75, "tag": "VALIDATE-only",
             "description": "Never sells; pulls the complement ladder at its takes and re-posts it ~1.04 s later (slower informed takers fill it); merges pairs (pair cost 0.978) and holds the residual. A public tape-based ladder with queue priority gets the same volume but a pair cost of 1.005 (loses 4-5%): the margin needs the live book."},
}

s["strategy_statement"] = (
    "CS2 (and some Dota 2) in-play bot; from 10-16 a buy-only two-sided maker plus an informed taker, before that a "
    "round-trip taker in GRID tier-1/2 events that traded late (into moves already under way). [VALIDATE-only] "
    "Selection: whole events (match + all maps) of non-GRID tier-3/4 leagues, never an event with a GRID series id "
    "(0/122), favouring popular events and those the informed pack also trades; event rule AUC 0.954 vs activity 0.892. "
    "[VALIDATE-only] Maker: whole-cent 100-share BUY ladders near the best bid on both outcome tokens from game start, "
    "never sells, merges pairs (97% paired, pair cost 0.978), holds the residual; at its own takes it pulls its "
    "complement ladder within 11-19 ms (90% of takes) and re-posts it ~1.04 s later, when its FAK returns, so slower "
    "informed takers fill it. A public tape-based copy of this ladder with queue priority gets the same volume but loses "
    "4-5%: the margin needs the live book. [hypothesis, live dev block] Taker: on in-round game events of a private "
    "feed it sends FAK BUYs of the team that gained (map and match legs within 1-4 ms) at the stale ask plus a premium "
    "that scales with the event's price impact (wallet-specific) and is propagated to the match leg at the series "
    "sensitivity; on the CLOB server clock nothing public precedes it (books of the match / map markets; round-market "
    "takers only follow), some fast makers cancel within ~10-15 ms of it on the same event, the pack signs 0.2-0.5 s "
    "later, and its order matches 1.04 s after signing. Per map, its take shares follow round wins and bomb plants, not "
    "opening kills. [VALIDATE-only] Economics: locked pair margins and rebates plus the informed taker legs; a generic "
    "public-data ladder in the same markets loses 5-10%.")

tmn = s.get("target_metrics_notes", {})
tmn["pnl"] = "VALIDATE best executable: generic tape ladder (strict fills) -0.121 / -0.061; iteration-4 queue-aware replay of a join-others'-bid ladder: -0.04 / -0.04 (oracle pulls -0.01 / -0.02), paired volume Spearman 0.91 but pair cost 1.005: not reachable from tape + calldata"
tmn["price"] = "in-play tick (0.01): last-print anchor 0.305 on VALIDATE (rule metric); live BUILD filled orders: full-book bid 0.526, others' bid 0.456, pair-cap rules 0.24-0.46"
s["target_metrics_notes"] = tmn

ds = s["data_sources"]
for d in ["data-api taker tapes of 665 round / handicap / total markets of the wallet's VALIDATE events + 529 decoded round-market taker txs (publicnode)",
          "data-api taker tapes of 85 taker-regime markets 10-01..10-15 (70 GRID sampled, 15 non-GRID)",
          "V2 order signer EOAs re-decoded for 51 txs (wallet, pack, late makers)",
          "own recorder tommy_cs2_rounds (round-market books, dev blocks only, from 17:36 UTC 10-31)",
          "own recorder tommy_chat (anonymous Twitch chat timing, dev blocks only, from 18:16 UTC 10-31)",
          "bo3.gg per-round team stats (first_kills, kills, clutches, bomb_plants, trade_kills) for 91 maps of 16-22 Oct",
          "web: PGL / Oddin.gg official data partnership (2024-2026)"]:
    if d not in ds:
        ds.append(d)

it = [x for x in s["iterations"] if x.get("n") != 4]
it.append({"n": 4, "minutes": 100, "best_validate_score": 0.8721,
           "families": ["queue-aware replay on the matched-order record (with and without oracle pulls)", "FAK premium as private valuation + fan-out ratio",
                        "maker quote on others' book (live, own levels subtracted)", "order-level cancel attribution", "zero-fill FAK attempts (re-post signature)",
                        "round-market takers before its takes (historical) + round-market book recorder", "slow UI takers as a broadcast clock",
                        "GRID taker regime price paths (latency class)", "clock-free event-type test (bo3 per-map counts)", "signer EOA decode",
                        "official data-rights falsifier (PGL)", "bo3 demo metadata", "Azuro endpoint probe", "anonymous Twitch chat recorder"],
           "primary_metric_note": "presence_auc unchanged (0.8721) for the second iteration: iteration 5 must pivot (e.g. a quote-presence target on the own recorder, or the event clock)"})
s["iterations"] = it
s["status"] = "continue"
s["wall_reason"] = None
s["next_steps"] = [
    "PIVOT (two iterations < 0.01 on presence_auc): a quote-presence target (its resting 100/68/58/54-share ladder per token and 10-s bin from tommy_cs2_near, own levels by fingerprint) vs an activity baseline on live dev blocks; or the event clock (X37 demo ticks with the user's consent)",
    "Ask the user: consent to download bo3 demos (name, host, size per file) and install a CS2 demo parser (X37); a PandaScore token (X23); an odds-api key or consent to probe bookmaker frontends (X48b)",
    "11-01 06-12 dev block: round-market books before its signings (X47b, tommy_cs2_rounds); chat clock lead-lag (X38, tommy_chat); more takes for X46 / X49",
    "Live-book replay of the maker ladder (outcome on future blocks): fills from the recorded book and the matched-order record, pulls at the public cancel wave",
    "Bomb-plant trigger (X50 lead): test per round with a clock once demos or chat are available; funding links of the 3-wallet cluster (X52)",
]
json.dump(s, open(P, "w"), indent=1)
print("catalog", len(cat), "open", sorted(k for k, v in cat.items() if isinstance(v, dict) and v.get("status") == "open"))
