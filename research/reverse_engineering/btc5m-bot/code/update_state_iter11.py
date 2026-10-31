"""Iteration 11: update state.json (catalog X87-X99 from the iteration-10 panel, corrections of X9 / X27 / X85, components,
strategy statement, hypotheses, data_sources, live_lab, iterations, target_metrics notes; the frozen historical rule and its
VALIDATE metrics are unchanged).
Usage: python update_state_iter11.py MINUTES"""
import os, json, shutil, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
P = _ROOT + "/research/reverse_engineering/btc5m-bot/state.json"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
shutil.copy(P, _ROOT + "/.cache/re/btc5m-bot/state_backup_iter10.json")
s = json.load(open(P, encoding="utf-8"))
MIN = float(sys.argv[1]) if len(sys.argv) > 1 else None


def J(name):
    p = f"{R}/{name}"
    return json.load(open(p)) if os.path.exists(p) else None


cat = s["catalog"]
I10 = "panel iteration 10"
on, rg, sz, lam, rc, rf, v11, lg = J("onset11.json"), J("regime11.json"), J("size11.json"), J("lam11.json"), J("race11.json"), J("refill11.json"), J("version11.json"), J("large11.json")
cat["X87"] = {"status": "open", "source": f"{I10}, information P1 (London-arrival clock: time every feed where the bot is; European venues never analysed: Deribit, Coinbase L1, Bitstamp, Kraken)",
              "evidence": "Step 0 tried (crowd11.py, results/crowd11_fresh.json / crowd11_all.json): every crowd taker re-timed on the server clock (m - 180, like the cluster): crowd-label "
                          "venue model 0.582 (fresh) / 0.587 (all 40,224 taker BUYs) vs Polymarket-activity baseline 0.657 / 0.653 (sign_ms clock 0.599 vs 0.632): the client clock was not the "
                          "artefact. P(cluster | crowd decision in the same 100 ms) 3.2% vs 0.68% (4.7x), P(crowd | cluster) 35.5-43%. Bot location evidence (X98 step 2): the bot reads "
                          "Polymarket's book ~30 ms old and Binance ~100+ ms old (near the engine, far from Tokyo). Steps 1-4 (venue transit calibration, London-arrival kernels, parity "
                          "gate) need the European venues: recorder rec_eu11 (Coinbase level2_50 + ticker, Bitstamp, Kraken v2, from 11-01 05:59 UTC; Deribit already in btc5m_xfam). "
                          "Open until scored on 11-01 06-12 / 18-24."}
cat["X88"] = {"status": "open", "source": f"{I10}, information P2 (alt-perp basket SOL / XRP / DOGE / BNB at ms for the no-vote third and the onset selection)",
              "evidence": "Recorder rec_eu11 (feed btc5m_xeu: Binance USD-M bookTicker, Bybit orderbook.1, OKX bbo-tbt for SOL / XRP / DOGE / BNB, 30 ms) from 11-01 05:59 UTC; subscriptions "
                          "acknowledged (probe 22:55 UTC, acks only). Live kernels / weak-vote agreement / pre-registered extended vote need the next development block; historical step 6 "
                          "(Bybit orderbook.200 alts into the VALIDATE side model) not run (cache at the 1.5 GB cap). Historical H29 at 1 s: 54.5-55.5% where neither BTC nor ETH moved."}
cat["X89"] = {"status": "open", "source": f"{I10}, information P3 (historical match clock from complete blocks: anchors from every Polymarket market)",
              "evidence": "Not tested in iteration 11 (the live selection / size tests came first). Note for the test: on 10-31 the race outcome is ~deterministic given the arrival "
                          "(race11), so a sub-second historical clock matters for the side and the PIT live components on h1 / h2, not for the PnL condition under the >= 2 s convention."}
cat["X90"] = {"status": "open", "source": f"{I10}, information P4 (who holds the ask: maker last-look speed as a fill-aware selector)",
              "evidence": "Not tested (needs the insertion-to-maker-order link of ins9 for skipped onsets). Related iteration-11 facts: lost races are decisions priced on an ask that "
                          "moved 30-180 ms before the arrival (lam11: lost races peak at Lambda = 180 ms vs 30 ms for won races); an earlier arrival by 50 / 100 / 150 ms would have won "
                          "21 / 40 / 51% of the lost races (race11)."}
cat["X91"] = {"status": "tried", "source": f"{I10}, information P5 (Polymarket's other crypto books BTC 15m / 4h, ETH / SOL 5m / 15m / 4h as the market-wide confirmation)",
              "evidence": "xmkt11.py (results/xmkt11.json; evt10 clean events, fit A scored C): a same-direction cross-market trade in [tau - 300, tau) raises P(take) (A 10.7% vs 5.4%, C "
                          "6.2% vs 4.4%) but an opposite-direction one about as much (A: BTC-long 9.0%, ETH 10.0%): activity, not confirmation; on price-level events of C 23.5% with vs "
                          "29.9% without (univariate 0.44-0.50); FULL 0.681 -> FULL + cross-market 0.674. Rejected as a selector."}
cat["X92"] = {"status": "tried", "source": f"{I10}, mechanics P1 (the trigger's normalizer: vol-adaptive z-score threshold or a rate controller instead of a bp threshold)",
              "evidence": "onset11.py / elast11.py (results/onset11.json, elast11.json): event unit, fit A scored C: FULL 0.681, normalizer terms without bp 0.657, FULL + normalizer 0.697 "
                          "(+0.015, CI [-0.002, +0.032]); univariate |bp| 0.588 vs z_rv_h 0.51-0.57 (h = 5-300 s), tick counts 0.49-0.53, within-window percentile 0.584; event-level window "
                          "chi2/df 14.8 -> 11.7. Complete live record per window-minute (110): elasticity of decisions to log(1 + Binance price-level events) 0.08 (se 0.18) with vol "
                          "controls, 0.18 (0.09) alone, within-window 0.30 (0.21); var/mean 13.4 (over-dispersed); P(take) RISES with the operator's own recent decisions (rec30 0 / 1-2 / "
                          "3-5 / 6+: 1.5 / 4.7 / 4.8 / 7.5% A, 1.4 / 3.6 / 4.4 / 6.2% C; own state). Critique 3 (no rate response) confirmed; (a) z* and (b) pacing both rejected."}
cat["X93"] = {"status": "open", "source": f"{I10}, mechanics P2 (resolve the race on the recorded book: deterministic execution instead of X82's independent lottery)",
              "evidence": "First step (race11.py, results/race11.json; 2,155 decisions): lost races would have been won by an EARLIER arrival of 10 / 25 / 50 / 100 / 150 ms in 3 / 11 / 21 / "
                          "40 / 51% of cases, by a later one in <= 1%; won races keep ask <= L for arrivals 25-150 ms earlier in 87-97% (the last ~25 ms before the match are unreliable in the "
                          "30-ms-coalesced recording); operator near-ties (another operator arrival within 5 ms) win 37.2% vs 63.0%. The race is close to deterministic given the arrival "
                          "(flip rate 4-7% at 25-50 ms timing error on lost races), so X82's independent-lottery ceiling does not apply to replays on recorded books (future blocks); it "
                          "still applies at the block clock. The full simulator (crowd queue, maker refills, per-window PnL) is not built."}
cat["X94"] = {"status": "tried", "source": f"{I10}, mechanics P3 (the cancel timer is armed at submission: per-wallet TTL from the POST, tested on the delay regimes)",
              "evidence": "Live (rem10): cancelled never-filled remainders, life from the insertion DS median 328 ms (q10 45, q90 4,485; n 100), GF 240 (36, 867; 38), XM 124 (48, 747; 12); "
                          "Weibull shape 0.63-0.77 (decreasing hazard, no sharp timer); minimum 14-26 ms (cancels sent during the hold); within one regime life from the POST = life from the "
                          "insertion + 150 ms (constant hold), so dispersion cannot discriminate there. Historical (refill11.py, results/refill11.json; per order hash, 16 operator hours): "
                          "P(taker-first order later refilled as maker) 8.3% -> 6.4% at 08-17 (D 250 -> 50; -1.9 points [-6.2, +2.6]; predicted UP) and 22.4% -> 17.5% at 09-04 (D 50 -> 150; "
                          "-4.9 [-8.8, -0.9]; predicted DOWN). Maker-first share of filled orders 25.7% -> 14.7% and 31.2% -> 23.2%. Partly supported (09-04 step only); levels follow the "
                          "versions (6-8% mid-August vs 17-22% September)."}
cat["X95"] = {"status": "tried", "source": f"{I10}, mechanics P4 (rebuild the version history from the signing schedule; correct finding 17)",
              "evidence": "version11.py (results/version11.json; 60 sampled operator txs on 08-05, 08-12, 08-15 16:00-16:20 UTC, calldata decoded in memory): operator orders signed 3-121 s "
                          "before their block (08-05 DS taker median 48 s, XM taker 61 s; 08-12 DS taker 111 s, XM taker 92 s; within 5 s of the block 1.7-3.3%) vs 2.8-3.5 s for other "
                          "wallets' taker orders in the same txs; two signing bursts per window (08-05: 0-30 s and 150-180 s mod 300; 08-12: 30-90 s and 180-240 s); one size per day. "
                          "August was pre-signed on other schedules; iteration 10's finding 17 ('fresh-signed until 08-18') is retracted; the 08-17 delay cut falls inside one schedule. "
                          "No fresh-signed segment exists in August; July (XM from 06-20) and the full daily segmentation stay under X9 / X26."}
cat["X96"] = {"status": "tried", "source": f"{I10}, assumptions P1 (conflated or confirmed venue input: skipped onsets are ticks that did not survive to the bot's snapshot)",
              "evidence": "onset11.py (results/onset11.json): within |bp| terciles P(take | move still >= 50% in place at +D) - P(take | reverted) = 0.4-2.5 points for D = 50-200 ms "
                          "(top tercile at +100: C 7.2% vs 5.4%, A 9.4% vs 6.5%); price-level events survive 180 / 181 and are taken 29% either way; as a non-PIT diagnostic survival + "
                          "OKX / Bybit confirmation +0.031 [0.021, 0.042] (0.712), i.e. later ticks and venue confirmation (both moved by +150 ms: 9.7% vs 2.5% with neither on C); (a - "
                          "tau) kernel of taken clean events flat over 0-550 ms. Phase lock on the venue clock already excluded by the panel (Rayleigh Z <= 3.0). Rejected. Snapshot "
                          "streams (Binance depth5@100ms, OKX books5, Bybit orderbook.50) recorded from 11-01 05:59 (rec_eu11) for the stream-lag test."}
cat["X97"] = {"status": "tried", "source": f"{I10}, assumptions P2 (test the size-feedback channel causally before calling condition 5 'at the edge of attainability')",
              "evidence": "size11.py (results/size11.json; 2,155 live decisions, 111 large): P(next same-outcome decision large within 30 s) after a large WON 19.1% (47) vs LOST 27.1% (48), "
                          "after a small won 3.9% (1,175) vs lost 3.6% (694); exogenous losses (crowd ahead) 27.8% (36). AUC of large by operator net on o: realized 0.668, SENT 0.680; "
                          "realized and sent-minus-realized similar weights (0.10, 0.09); P(large) 17.6% when sent long but realized short (n 34). No realized-fill feedback detected: the "
                          "size reads intentions or a slow regime, so lean10's 0.47-0.58 is not supported and the fixed-size ceiling 0.70-0.77 applies (under-powered: 111 large on a "
                          "Saturday; the panel's block-clock check -0.01 +- 0.20 agrees). Public predictors of large: see large11."}
cat["X98"] = {"status": "open", "source": f"{I10}, assumptions P3 (align on the bot's clock: triangulate its location, re-express features in bot time)",
              "evidence": "Step 2 tried (lam11.py, results/lam11.json): among 1,252 decisions whose o-ask changed in [a - 400, a], P(limit == ask(a - Lambda)) peaks at Lambda = 30 ms "
                          "(0.481; 0.455 at 0, 0.391 at 150, 0.274 at 300; placebo inside the hold 0.44 at -30); DS 50, GF 10, XM 30 ms; won races 30 ms (0.647), lost races 180 ms "
                          "(0.378). The bot reads Polymarket ~30 ms old and Binance ~100+ ms old: near Polymarket's engine. Steps 1 (per-venue leading edges) and 3 (the (Lambda, tau) "
                          "AUC profile) not done."}
cat["X99"] = {"status": "open", "source": f"{I10}, assumptions P4 (recover the bot's Math.random state from the order salts: Bun / JSC xorshift128+, V8 variants)",
              "evidence": "Not tested in iteration 11 (the panel's V8 single-call test was negative; the JSC and multi-call variants need a z3 search over copy offsets)."}
# corrections of older items
cat["X27"]["status"] = "tried"
cat["X27"]["evidence"] += (" | Iteration 11 (measurement by the iteration-10 assumptions panel, polyrea collateral_at at six pre-H blocks 10-21 12:00 .. 10-22 23:00 UTC): pUSD GF $12.5-18.8k, "
                           "XM $70.5-72.6k, DS $62.4-64.8k, W4 $11.4-14.6k, USDC.e 0; a window's spend ~$0.4-0.7k, so free collateral is 15-100x a window's spend and unrelated to activity "
                           "(XM holds the most and trades the least): collateral does not gate decisions.")
cat["X85"]["status"] = "tried"
cat["X85"]["evidence"] += (" | Iteration 11: collateral ruled out (X27); the minute-level decision count is over-dispersed (var/mean 13.4, elast11) and barely elastic to activity "
                           "(0.08-0.30); P(take) rises with the operator's own recent decisions beyond public crowd activity (regime11: FULL 0.681, + crowd 0.685, + own rec30 0.715 on C; "
                           "within crowd terciles rec30 still raises P), so the window-level rate is a self-exciting internal state whose cause stays under X72.")
cat["X9"]["evidence"] += (" | Iteration 11 (version11, X95): the 'fresh-signed until 08-18' reading is retracted: on 08-05 and 08-12 operator orders were signed 3-121 s before their "
                          "block (other wallets 2.8-3.5 s) in two bursts per window at other phases; one size per day.")
cat["X75"]["evidence"] += (" | Iteration 11 (refill11, X94): refill probability per taker-first order 8.3% -> 6.4% (08-17) and 22.4% -> 17.5% (09-04); with finding 17 retracted the "
                           "08-17 maker-share drop falls inside one pre-signed schedule.")
cat["X72"]["evidence"] += (" | Iteration 11: no normalizer (X92), no survival / confirmation gate (X96), no cross-market confirmation (X91), crowd server clock (X87 step 0); among "
                           "Binance price-level events (taken 29-30%) no public feature reaches AUC 0.58 in both halves (price11: |bp| 0.46 / 0.51, z_rv_5 0.56 / 0.59, agreement 0.58 / "
                           "0.53, o's ask 0.52 / 0.64); own recent decisions 0.58 / 0.64; bursts are directional (30-s bins |share Up - 0.5| 0.224 vs null 0.130). Still open.")

pm1, pm2, kn = J("pmxt11.json"), J("pmxt11_0806.json"), J("kern11.json")
ev60 = " | Iteration 11 (pmxt11.py / kern11.py): the archive is read through HTTP range requests on the market-sorted row groups (no key; ~100 MB per hour, nothing stored but derived subsets): "
if pm1:
    ev60 += f"08-01 12-13 UTC: {pm1.get('btc5m_markets')} BTC 5m markets, {pm1.get('archive_trades_btc5m')} trades, cluster taker txs with server ms {pm1.get('cluster_txs_with_ms')} (a quiet hour: XM only, min gap {((pm1.get('taker_gap_ms') or {}).get('XM') or {}).get('min')} ms). "
if pm2:
    ev60 += f"08-06 16-17 UTC: taker gaps {json.dumps(pm2.get('taker_gap_ms'))}. "
if kn:
    ev60 += (f"kern11 on 08-06 16-17: crowd sign-to-match {json.dumps(kn.get('crowd_sign_to_match_ms'))}; cluster kernel peak L = {kn.get('kernel_peak_L_ms')} ms before the match "
             f"(excess - placebo {kn.get('kernel_peak_excess_minus_placebo')}), by wallet {json.dumps({w: v.get('peak_L') for w, v in (kn.get('kernel_by_wallet') or {}).items()})}.")
pm3, kn3 = J("pmxt11_0805.json"), J("kern11_0805.json")
if pm3:
    ev60 += f" Replication 08-05 16-17 UTC: taker gaps {json.dumps(pm3.get('taker_gap_ms'))}."
if kn3:
    ev60 += (f" kern11 08-05: crowd sign-to-match {json.dumps(kn3.get('crowd_sign_to_match_ms'))}; kernel peak L = {kn3.get('kernel_peak_L_ms')} ms "
             f"(excess - placebo {kn3.get('kernel_peak_excess_minus_placebo')}), by wallet {json.dumps({w: v.get('peak_L') for w, v in (kn3.get('kernel_by_wallet') or {}).items()})}.")
kb = J("kern11b.json")
if kb:
    ev60 += f" Same kernel on 10-31 (D = 150 ms, bookTicker mid; kern11b): peak L = {kb.get('kernel_peak_L_ms')} ms (by wallet {json.dumps({w: v.get('peak_L') for w, v in (kb.get('kernel_by_wallet') or {}).items()})})."
sd11, lb = J("side11.json"), J("lam11b.json")
if sd11:
    ev60 += " Side in the 250-ms regime (side11, Binance trades only): hold-shifted PIT window agrees " + ", ".join(
        f"{k}: {v['pit_D250 [m-850, m-280)']['agree_on_voted']} on {v['pit_D250 [m-850, m-280)']['voted']} voted (placebo {v['pit_D250 [m-850, m-280)']['placebo_agree']})" for k, v in sd11.items()) + "."
if lb:
    ev60 += f" View lag in August (lam11b, 08-06): peak Lambda = {(lb.get('changed') or {}).get('peak_lambda_ms')} ms (eq {(lb.get('changed') or {}).get('peak_eq')}, n {(lb.get('changed') or {}).get('n')}) vs 30 ms on 10-31."
    cat["X98"]["evidence"] += f" | August (lam11b, pmxt 08-06 16-17, D = 250): peak Lambda = {(lb.get('changed') or {}).get('peak_lambda_ms')} ms on {(lb.get('changed') or {}).get('n')} decisions with an ask change."
cat["X60"]["evidence"] += ev60
if kn and kn.get("kernel_peak_L_ms") is not None:
    cat["X60"]["status"] = "tried"
open_ids = sorted([k for k, v in cat.items() if v.get("status") == "open"], key=lambda k: (k[0], int(k[1:]) if k[1:].isdigit() else 0))
s["catalog_open_after_iteration11"] = open_ids

comp = s["components"]
comp["timing"]["description"] = ("Decision = submission of a pre-signed ladder order about 100-150 ms after a Binance USD-M / OKX / Bybit microprice tick toward the outcome; under Polymarket's "
                                  "150-ms taker delay the order ARRIVES ~150 ms before its match. The bot reads Polymarket's book ~30 ms old and Binance ~100+ ms old (limits match o's ask at "
                                  "a - 30 ms best): it runs near Polymarket's engine. Selective: it reacts mostly at the onset of a flagged episode (23-26%), price-level Binance ticks with other "
                                  "venues agreeing are taken 29-41%; the decision rate is barely elastic to the minute's tick count (0.08-0.30) and over-dispersed (var/mean 13); no self-kept vol "
                                  "scale, survival / confirmation gate, cross-market confirmation or crowd timing selects the onsets; among price-level ticks the take is indistinguishable from a "
                                  "coin given every public input (AUC <= 0.58 in both halves) and rises with the bot's own recent decisions (a self-exciting internal state, own state). "
                                  "Historically presence on block seconds 0.875 vs 0.821 (+0.054).")
comp["price"]["description"] = ("Limit = o's ask the bot saw ~30 ms before arriving (peak of P(limit == ask(a - Lambda)) at Lambda = 30 ms; DS 50, GF 10, XM 30); o's ask at m - 180 within a tick "
                                 "90.7% live, 95.1% on VALIDATE calldata (trivial touch anchor, stated as such); lost races are the decisions priced on an ask that moved 30-180 ms before the "
                                 "arrival (their Lambda peak is 180 ms); 16% of taker orders 1+ c above the touch.")
comp["size"]["description"] = ("Fixed (small, large) menu per day; large orders pyramid the leg the operator holds. Iteration 11: the size reads the operator's INTENDED (sent) position or a slow "
                                "regime, not realized fills (after a won vs lost large race the next same-outcome decision is large 19% vs 27%; sent net AUC 0.680 vs realized 0.668), so the "
                                "fixed-size replay ceiling 0.70-0.77 applies rather than lean10's 0.47-0.58 (tentative: 111 large decisions). The per-window PnL is the large-order lean (corr "
                                "0.77), a coin with respect to the outcome. Under the latency >= 2 s strict-fill convention even the wallet's own decisions with true sizes reach only 0.40.")
comp["exit"]["description"] = ("Remainders and lost races rest as GTC bids at the old ask; cancelled never-filled remainders live DS median 328 ms, GF 240, XM 124 (Weibull shape 0.63-0.77, no sharp "
                                "timer; some cancels are sent during the hold); refills fall when the hold rises (09-04: 22.4% -> 17.5%), not when it falls (08-17); every position is held to "
                                "resolution; 87% of shares end paired at 0.979; REDEEM per window; TAKER_REBATE = 0.5 x the previous day's taker fees; one order in flight per wallet, decisions "
                                "fan out across wallets.")
for k in ("timing", "side", "price", "size", "exit", "selection"):
    comp[k]["tag"] = "VALIDATE-only"
comp["size"]["confidence"] = 0.7
comp["timing"]["confidence"] = 0.75
s["strategy_statement"] = (
    "One operator runs a TypeScript clob-client bot on three (plus a fourth) wallets in every BTC 5-minute Up/Down window, and only there [VALIDATE-only]. It pre-signs BUY orders on both "
    "outcomes at every cent in bursts each window (three bursts at -89.5 / +42 / +173 s since 08-22; other two-burst schedules in early August, never fresh-signed at decision time) "
    "[VALIDATE-only]. It submits one about 100-150 ms after a microprice tick of the Binance USD-M / OKX / Bybit BTC and ETH perps toward an outcome, at the ask it saw ~30 ms before "
    "arriving (1+ c higher in 16% of orders) [VALIDATE-only]; it runs near Polymarket's engine and sees Binance ~100 ms late [VALIDATE-only, location hypothesis]. Polymarket holds every "
    "marketable order 150 ms, so the bot races the crowd in that delay queue; given the arrival time the race outcome is nearly deterministic on the recorded book [VALIDATE-only]. It "
    "takes about one in three flagged episodes, mostly at their onset; which ones is not decoded: no public input recorded separates taken from skipped price-level ticks, and the "
    "take rate rises with the bot's own recent activity, a self-exciting internal state [VALIDATE-only; open]. The side is the tick direction (83% per decision, point-in-time clean) "
    "[VALIDATE-only]. Lost races rest at the old ask for ~0.1-1 s and fill as maker about half the time [VALIDATE-only]. The size is small unless the operator's intended position is "
    "flat or long the outcome, so large orders pyramid the leg it holds; realized fills do not feed back [VALIDATE-only, own state, tentative]. Positions are held to resolution; 87% "
    "of shares end in complete sets bought at 0.979 [VALIDATE-only]. Income = locked sets (~2.1 c per pair) and the 50% taker-fee rebate; the large-size lean is a coin with respect "
    "to the outcome and carries the per-window PnL variance [VALIDATE-only]. Nothing is exam-verified.")
s["status"] = "continue"
hy = s["hypotheses"]
nxt = max(int(h["id"][1:]) for h in hy) + 1
new = [
    ("trigger normalizer (X92)", "z-scored onset tick / tick counts / within-window percentile vs bp; decision-rate elasticity",
     {"auc_C_full": 0.681, "auc_C_full_norm": 0.6972, "gain_CI": [-0.0015, 0.0154, 0.0317], "uni_abs_bp": 0.5878, "uni_z_rv_300": 0.5722, "elasticity_npr_poisson": [0.0777, 0.1815],
      "var_over_mean_per_min": 13.41}, "rejected (G1, G2)"),
    ("conflated / confirmed venue input (X96)", "survival of the onset at +50..+200 ms, confirmation, kernel shape",
     {"surv_vs_rev_top_tercile_C_D100": [0.0715, 0.0539], "PRICE_survived_C": "180/181", "auc_C_full_surv(diag)": 0.7123}, "rejected (G3)"),
    ("crowd on the server clock (X87 step 0)", "crowd re-timed at m - 180", {"crowd_venue_auc": [0.582, 0.5874], "crowd_pm_auc": [0.6566, 0.6527], "P(cl|crowd same 100ms)": 0.0318,
     "P(cl|no crowd)": 0.0068}, "client-clock artefact rejected"),
    ("cross-market confirmation (X91)", "other crypto Up/Down books before the onset", {"auc_C_full": 0.681, "auc_C_full_x": 0.6739}, "rejected"),
    ("size feedback channel (X97)", "won vs lost large races; sent vs realized net", {"P(large next | large won, lost)": [0.1915, 0.2708], "auc_real_sent": [0.6675, 0.6801]},
     "no realized-fill feedback; intentions / regime (tentative)"),
    ("view lag of the Polymarket book (X98)", "limit == ask(a - Lambda) profile", {"peak_lambda_ms": 30, "peak_eq": 0.4808, "won_peak": 30, "lost_peak": 180}, "Lambda ~30 ms: near the engine"),
    ("race determinism on the recorded book (X93)", "flip rate by arrival-time error", {"lost_won_if_earlier_25_50_100": [0.1122, 0.2135, 0.4005], "operator_near_tie_P_won": [0.3719, 0.6298]},
     "nearly deterministic given the arrival"),
    ("public vs internal regime (X85)", "own recent decisions vs public crowd activity at onsets", {"auc_C": (rg or {}).get("auc_C")}, "self-exciting internal state beyond public activity"),
    ("remainder TTL and delay regimes (X94)", "per-wallet TTL; refills around 08-17 / 09-04", {"ttl_median_ms": {"DS": 328, "GF": 240, "XM": 124},
     "refill_0817": (rf or {}).get("change_0817 (D 250->50)"), "refill_0904": (rf or {}).get("change_0904 (D 50->150)")}, "partly supported (09-04 only)"),
    ("version history (X95)", "sign-to-block of August operator orders", {"0805_DS_T_median_s": 47.66, "0812_DS_T_median_s": 111.04, "others_T_median_s": [3.45, 3.81]},
     "August pre-signed; finding 17 retracted"),
]
if lg:
    new.append(("large size from public features (F6)", "public vs own-state predictors of the 100-share size", {k: lg.get(k) for k in ("univariate_auc_all", "fit_A_score_C_auc")}, "see NOTES"))

sm, xc, pm = J("sizems11.json"), J("xcorr11.json"), J("pmxt11.json")
if sm:
    new.append(("large size from millisecond ticks at the block clock (F6 historical)", "max 300-ms Binance USD-M move toward o in [bt - 3.0, bt - 0.2] vs large",
                {"by_split": sm.get("by_split"), "fit_BUILD_score_VALIDATE": sm.get("fit_BUILD_score_VALIDATE_auc")}, "no signal at the block clock (0.48-0.57)"))
if xc:
    new.append(("venue stamps lead-lag (X87 step 1)", "10-ms microprice cross-correlation on exchange stamps", {k: v.get("peak_lag_ms") for k, v in xc.items() if isinstance(v, dict) and "peak_lag_ms" in v},
                "OKX ~ Binance; Bybit and Deribit +60 ms"))
if pm:
    new.append(("250-ms regime gap floor (X60)", "per-wallet gap between consecutive taker matches on the pmxt archive", {"hour": pm.get("hour"), "taker_gap_ms": pm.get("taker_gap_ms")}, "see NOTES"))
if sd11:
    new.append(("side vote in the 250-ms regime (X60)", "Binance trade-price vote over the hold-shifted PIT window, pmxt hours", {k: v.get("pit_D250 [m-850, m-280)") for k, v in sd11.items()}, "replicates qualitatively (72-76% vs 54-56% placebo)"))
if lb:
    new.append(("view lag in August (X98)", "limit == ask(a - Lambda) on pmxt price_change touches", {"changed": lb.get("changed"), "all": (lb.get("all") or {}).get("peak_lambda_ms")}, "see NOTES"))
for i, (fam, desc, vm, ver) in enumerate(new):
    hy.append({"id": f"H{nxt + i}", "family": fam, "description": desc, "validate_metrics": vm, "verdict": ver})
s["data_sources"] += ["Iteration 11: it11/onset_{A,C}.parquet (evt10 clean events with normalizer, survival, confirmation and own-state columns, 10-31 14:55-17:55)",
                      "Iteration 11: operator OrderFilled logs per order hash, hour 16-17 UTC on 16 days around 08-17 / 09-04 (counts only, results/refill11.json)",
                      "Iteration 11: V2 calldata of 60 sampled operator txs on 08-05 / 08-12 / 08-15 (decoded in memory, results/version11.json)",
                      "Iteration 11: recorder rec_eu11 (btc5m_xeu, btc5m_xsnap) from 11-01 05:59 UTC"]
s["live_lab"].append({"what": "rec_eu11.py (pid 14192): sleeps until 11-01 05:59 UTC, then records btc5m_xeu (Coinbase level2_50 top + ticker, Bitstamp order_book, Kraken v2 book, "
                              "SOL / XRP / DOGE / BNB perps on Binance USD-M, Bybit, OKX; sized L1 coalesced to 30 ms) and btc5m_xsnap (Binance USD-M depth5@100ms BTC / ETH, OKX books5, Bybit "
                              "orderbook.50 BTCUSDT; every message) through tools/live.py Writer (every block filed by the Writer, never read in sealed blocks); cap 280 MB; status "
                              ".cache/re/btc5m-bot/rec_eu11.status", "start": 1793512740, "end": 1793642400})
s["target_metrics_notes"]["iteration11"] = ("Historical rule unchanged (target_metrics as in iterations 9-10). Condition 5 account revised: no realized-fill size feedback detected (size11), so "
                                            "the replay ceiling with the decisions reproduced is the fixed-size 0.70-0.77 at the block clock, and on recorded books the race is nearly "
                                            "deterministic given the arrival (race11); under the latency >= 2 s convention the wallet's own decisions with true sizes reach 0.40 (strict7). "
                                            "The binding terms are decision overlap (the onset selection, not decoded) and the large-size regime.")
it = {"n": 11, "minutes": MIN, "best_validate_score": 0.9132, "block_seconds_presence": 0.8747, "block_seconds_stronger_baseline": 0.8211, "pnl_corr": 0.1755,
      "paradigm": "testing the panel's selection mechanisms on one onset table (normalizer, conflated input, cross-market confirmation, server-clock crowd), the size-feedback channel and "
                  "race determinism as the condition-5 account, the bot's view lag, and the version history",
      "families": ["trigger normalizer z_h / tick counts / percentile + decision-rate elasticity (X92)", "conflated / confirmed venue input: survival, confirmation, kernel (X96)",
                   "crowd on the server clock (X87 step 0)", "other crypto books as confirmation (X91)", "size feedback: won vs lost large races, sent vs realized net (X97)",
                   "view lag of the Polymarket book (X98 step 2)", "race determinism on the recorded book (X93 first step)", "public vs internal regime at onsets (X85)",
                   "remainder TTL per wallet and refills across delay regimes (X94)", "version history: sign-to-block in August (X95)", "price-level events: taken vs skipped scan",
                   "large size from public features (F6)", "recorder: European venues, alt perps, snapshot streams (X87 / X88 / X96)"]}
s["iterations"].append(it)
json.dump(s, open(P, "w", encoding="utf-8"), indent=1)
print("open", len(open_ids), open_ids)
