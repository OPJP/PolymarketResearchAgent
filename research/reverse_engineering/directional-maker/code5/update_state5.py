"""Iteration 5: bring state.json up to date (catalog incl. X10-X25, components, statement, target_metrics, ledger)."""
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent / "state.json"
R = HERE.parent / "results"
s = json.loads(P.read_text(encoding="utf-8"))
live = json.loads((R / "iter5_live_final.json").read_text(encoding="utf-8")) if (R / "iter5_live_final.json").exists() else {}

cat = s["catalog"]


def setc(k, status, ev):
    cat[k] = {"status": status, "evidence": ev}


setc("A1", "tried", "Gamma resolutionSource Chainlink TWAP-60; priceToBeat(W) = finalPrice(W-1) (iteration 1). Live (iteration 5, own RTDS "
     "recorder dm_rtds, staggered 25-s reconnects, ~99% second coverage vs 52% in the shared feed): crypto_prices_twap_sixty stamped at the "
     "window end equals Gamma finalPrice to 4+ decimals in 3/3 BTC 5m windows (14:10-14:25 UTC). Quote-level race on the live block: near-touch "
     "500/100 quotes vs a TWAP-60 digital fair from Chainlink 1-s (strike = TWAP at start) MAD 0.105 / corr 0.90 vs Binance futures MAD 0.037-0.039 "
     "/ corr 0.97 (results/iter5_live_h_*.json). Settlement-disagreement windows (I5): cluster's late net side follows the real outcome 60% "
     "(63/105, BUILD+STUDY+VALIDATE agg.) vs the market's last print 73-85%; near-strike 51% vs 80-85% (results/iter5_disagree.json). Not settlement-informed.")
setc("A2", "tried", "Iteration 5 live block (server stamps, ms): requote direction of near-touch 500/100 quotes vs each venue's move over the previous "
     "50-250 ms: Binance USD-M futures bookTicker 96-97% (n 67-75), Bybit perp 60-80%, OKX swap 62-70%, Coinbase 41-56%, Binance spot 51-54%, "
     "Hyperliquid 43-62%; quote levels fit all perps similarly (MAD 0.028-0.039). Kraken 1-s worse than Binance (iteration 3). Reference = Binance futures.")
setc("A3", "tried", "Futures aggTrades 10-08..30 (iteration 4): futures fair explains limit prices better than spot (0.846 vs 0.838), presence +0.0007. "
     "Iteration 5 live: the futures bookTicker mid is the requote trigger when it moves (96-100% direction agreement within 250 ms); the futures "
     "microprice is not (55-62%). Spot fair fits quote levels worse (MAD 0.044-0.074 vs 0.031). Options/DVOL not tried (X13).")
setc("A7", "tried", "Tape last trade / flow features (R2-R3); constant fee and reward fields (iteration 3); live raw book (iteration 5): the cluster's "
     "near-touch requotes follow its own token's best bid moves of the previous 250 ms in 89% (n 396); resting fingerprint 500 at the hit level "
     "raises P(cluster in the trade) from 0.9% to 13.6%.")
setc("B2", "tried", "Iteration 5 raw book: 500-share orders live median 0.69 s (p10 0.09, p90 2.8 s), 100-share 0.37 s; cancel-to-re-add median 16 ms; "
     "52-87% of removals are followed within 100 ms by an equal-size add on the same side (re-sign); 71% of re-signs keep the price "
     "(loses time priority). Earlier: fills consume orders within 0-2 s (iterations 2-3).")
setc("X2", "tried", "source: exam round 1 (live lab: book at decision times). Iteration 5: own unaggregated recorder dm_clob_raw (every price_change, "
     "server ms) since 14:04 UTC 10-31; 99% of the cluster's 138 filled maker orders (calldata original size) have an add of exactly that size "
     "at their level before the match (results/iter5_live_*.json).")
setc("X3", "tried", "source: exam round 1 (settlement feed). See A1: RTDS TWAP-60 recorded at ~99% coverage; it reproduces finalPrice; the quotes "
     "follow Binance futures, not Chainlink.")
new = {
    "X10": ("tried", "source: panel iter4 information I1 (reference feed by server-clock lead-lag of quote changes). Binance USD-M futures bookTicker: "
            "near-touch requote direction agrees 96-97% with its mid move 50-250 ms earlier (0-500 ms 91%, 1-3 s 67%); other venues 41-80%. "
            "But 93-98% of requotes happen with no futures mid move in the previous 0.5 s: the engine re-signs on a ~0.5-s cycle and follows the "
            "Polymarket touch (89%) between futures moves. Latency bound: <= 50-250 ms after a futures move."),
    "X11": ("open", "source: panel iter4 information I2 (match clock instead of block clock for features). Raw x records with server ms now recorded; "
            "historical rebuild on all-match calldata not done."),
    "X12": ("tried", "source: panel iter4 information I3 (use the Chainlink recording; race Chainlink vs futures). Own staggered RTDS recorder ~99% "
            "coverage; TWAP-60 at end = finalPrice (3/3); quote level vs Chainlink fair MAD 0.105 vs futures 0.037: futures wins. Opening-side test "
            "in disagreement windows and last-60-s test not run on live data yet (too few windows)."),
    "X13": ("open", "source: panel iter4 information I4 (DVOL implied vol). Not fetched yet; live quote residual is flatter than the realised-vol "
            "fair (quotes above fair near 0.5, below it above 0.8), consistent with a higher vol input."),
    "X14": ("tried", "source: panel iter4 information I5 (settlement-disagreement windows). Cluster's late net side follows the real outcome in "
            "60% of proxy-disagreement windows (STUDY 7/10, VALIDATE 18/30, BUILD 38/65) vs the market's last print 73-85%; near-strike decile "
            "51% vs 80-85%. Not settlement-informed (results/iter5_disagree.json)."),
    "X15": ("tried", "source: panel iter4 mechanics P1 (unaggregated book events + size fingerprint). dm_clob_raw: 99% of 138 cluster maker orders "
            "found as an exact-size add at their level before the match (incl. re-signed remainders such as 492.44); 63% were added at the touch; "
            "age at match median 1.2 s (p25 0.2 s, p75 4.5 s). Exact-500 events 7.1 adds/s and exact-100 ~14/s in BTC 5m current+next and 15m "
            "current (neighbours 499/501 near zero)."),
    "X16": ("tried", "source: panel iter4 mechanics P2 (back-of-queue level depletion). Tape (STUDY, 938k bid hits): P(cluster | hit clears the "
            "level) 0.63% vs 0.85% when the level holds (stratified rate ratio 0.63): strong form rejected. Live: with a fingerprint 500 resting "
            "at the hit level only 13.6% of trades reach it (behind the queue); it rises with volume already absorbed at the level (0.75% -> 1.27%)."),
    "X17": ("tried", "source: panel iter4 mechanics P3 (salt counter as requote counter). Live salt slopes 16.7-17.2 orders/s per wallet (51/s "
            "for three) vs 24.6/s exact-500/100 adds in the three recorded BTC markets alone: signed ~ posted; each quote is re-signed every "
            "~0.5-0.7 s, 71% at an unchanged price. STUDY densification not needed for the rate question."),
    "X18": ("tried", "source: panel iter4 mechanics P4 (exit by buying the complement). 72% (STUDY) / 83% (VALIDATE agg.) of its BTC 5m taker buys "
            "are on the under-held side; size = imbalance exactly in 42-46% (median ratio 0.80-1.0; p25 0.2 = one-fifth level); pair cost median "
            "1.12 / 1.06; median 176 / 115 s into the window; merge follows in 17% / 51%. Taker-fill PnL +$215 / +$422 (4% / 2% of the period PnL); "
            "maker-maker pairs are ~90% of paired shares (results/iter5_flatten.json). Hazard model not fitted (low PnL weight)."),
    "X19": ("open", "source: panel iter4 mechanics P5 (censored inverse fit of the quote from every match). Superseded in part by direct live quote "
            "observation (quote = futures TWAP-60 fair - 0.02..0.05, MAD 0.03); historical censored fit not run."),
    "X20": ("open", "source: panel iter4 mechanics P6 (side is the taker's choice; decode the skew). Live: Up and Down quotes are re-signed "
            "independently (0.4% within 50 ms of each other); skew vs inventory not measured yet."),
    "X21": ("open", "source: panel iter4 assumptions Q1 (one universe for one engine). Coverage measured (results/iter5_coverage.json): VALIDATE "
            "BTC 5m 78.3% of fills / 68.6% of abs PnL, + BTC 15m 86.8% / 89.1%; STUDY BTC 5m 53.6% / 55.5%, six families needed for 80/80 "
            "(82.7% / 92.4%). BTC 15m tapes 10-09..30 fetched (.cache/re/directional-maker/t15/); the R3 pipeline on 15m not run yet; live: the "
            "same 500/100 quote stream runs in BTC 15m (half of near-touch adds)."),
    "X22": ("tried", "source: panel iter4 assumptions Q2 (size in the outcome metric). VALIDATE (agg.): per-share rule 0.329/0.325; x public clock size "
            "0.321/0.283; x own previous-30-min largest fill 0.341/0.288; ceiling (its own fills at one share) 0.688/0.780. Size is not the binding "
            "constraint on VALIDATE; the clock schedule is also contradicted live (500/100 orders on Saturday 14:00 UTC)."),
    "X23": ("tried", "source: panel iter4 assumptions Q3 (signed is not posted). Live: posted/signed ~0.5 within BTC 5m+15m alone (24.6 adds/s of its "
            "size class vs 51 signed/s for all markets): signatures are posted quotes, not mostly rejected post-only attempts; orders are not "
            "post-only either (a 500 BUY at 0.66 matched first as taker, then its remainder as maker, same salt)."),
    "X24": ("open", "source: panel iter4 assumptions Q4 (fast makers' state from historical maker rows). Not done."),
    "X25": ("open", "source: panel iter4 assumptions Q5 (risk controller on markouts). Not done."),
}
for k, (st, ev) in new.items():
    setc(k, st, ev)

s["components"] = {
    "selection": {"confidence": 0.3, "tag": "hypothesis",
                  "description": "one engine over crypto Up/Down; BTC 5m = 78% of VALIDATE fills / 69% of abs PnL, BTC 5m+15m 87% / 89% (STUDY 54% / 56% "
                                 "and 63% / 75%); the same 500/100 quote stream runs in BTC 15m live; BTC 5m on/off is a runtime switch with no public correlate yet."},
    "timing": {"confidence": 0.65, "tag": "VALIDATE-only",
               "description": "continuous re-signing: each (market, side) quote is cancelled and re-added about every 0.5-0.7 s (re-add 16 ms after the "
                              "cancel; 71% at an unchanged price), ~17 signed orders/s per wallet; requote direction follows Binance USD-M futures mid moves "
                              "within 50-250 ms (96-97%) and the Polymarket touch between them (89%) [live development block 10-31]; exposed to moves of the "
                              "last ~0.25-1.5 s (STUDY ms clocks)."},
    "side": {"confidence": 0.45, "tag": "exam-verified",
             "description": "Up and Down quoted independently; it is filled on the side where its futures-fair quote reaches the touch: VALIDATE 0.663 vs "
                            "0.613 activity baseline; exam round 1 0.655 vs 0.600."},
    "price": {"confidence": 0.55, "tag": "exam-verified",
              "description": "rule: last clean print - 0.01 (within one tick 0.709 VALIDATE, exam 0.688). Decoded quote (live, hypothesis): near-touch quote "
                             "= TWAP-60 digital fair of the Binance futures mid - 0.02..0.05 (corr 0.97-0.99, MAD 0.03), flatter than the realised-vol "
                             "fair; filled orders were at the touch when posted (63%)."},
    "size": {"confidence": 0.6, "tag": "VALIDATE-only",
             "description": "runtime size class with a one-fifth second level (500/100 on Saturday 10-31 14:00 UTC; 62/12 or 250/50 on other days); "
                            "partially filled orders are re-signed with the remainder (492.44, 76.38, ...); size does not depend on the edge."},
    "exit": {"confidence": 0.55, "tag": "VALIDATE-only",
             "description": "holds to resolution; taker-buys the under-held complement (72-83% of its taker buys) sized to the imbalance or one fifth, "
                            "pair cost 1.06-1.12, then merges in 17-51% of those windows; small PnL weight (2-4%); maker-maker pairs are 90% of paired shares."},
}
s["strategy_statement"] = (
    "One engine signs every order of the three wallets (per-wallet sequential salt counter, timestamp/metadata/builder 0, daily 01:00 UTC restart) "
    "[VALIDATE-only]. It keeps BUY quotes on both outcomes of BTC 5m and 15m Up/Down windows (and other crypto Up/Down markets), each side on its own, "
    "and cancels and re-posts every quote about every 0.5-0.7 s, mostly at an unchanged price, so its orders are always young and behind the queue "
    "at their level [hypothesis: live development block 10-31, raw book with its size fingerprint, 99% of its filled orders found]. The quote is a "
    "TWAP-60 digital fair value of the Binance USD-M futures mid minus about 0.02-0.05 (corr 0.97-0.99 with its near-touch quotes); when the futures "
    "best bid/ask moves, the next re-post moves the same way within 50-250 ms (96-97%), and between futures moves it follows the Polymarket touch "
    "(89%); Bybit, OKX, Coinbase, Binance spot, Hyperliquid and Chainlink explain its quotes less [hypothesis: live]. It is filled when its quote "
    "reaches the best bid of a token (the side the futures fair says the market underprices) and takers use up the orders ahead of it "
    "[exam-verified partially: side 0.655, price 0.688]. Order size is a runtime class with a one-fifth second level (500/100, 250/50 or 62/12), "
    "partial fills are re-posted as remainders [VALIDATE-only]. It holds to resolution and occasionally taker-buys the under-held complement to "
    "the exact imbalance and merges (2-4% of PnL) [VALIDATE-only]. It is not settlement-informed (its late inventory follows the true outcome in "
    "60% of proxy-disagreement windows vs 73-85% for the market) and earns almost nothing from rewards ($0.81) and 8% from rebates. Profit: the spread "
    "from dispersed takers on a futures-anchored quote that is refreshed faster than the average maker's; in busy periods most of it comes from "
    "buying both outcomes cheaply at different moments (+11% on paired dollars). Not decoded: which BTC 5m windows are switched on, and the exact "
    "quote offset (MAD 0.03 = 3 ticks) that decides whether it is at the touch.")
tm = s["target_metrics"]
tm["coverage_fills"] = 0.7835
tm["coverage_abs_pnl"] = 0.6859
tm["_notes"] = ("rule R3 on VALIDATE 2026-10-27..30 (code/final_rule.py, results/iter4_r3_validate_*.json); unchanged in iteration 5. coverage_fills / "
                "coverage_abs_pnl: share of the cluster's TRADE rows and of per-market absolute cash-flow PnL in BTC 5m windows on VALIDATE "
                "(results/iter5_coverage.json; BTC 5m + 15m would give 0.868 / 0.891; STUDY BTC 5m 0.536 / 0.555). side_baseline = market-activity-only "
                "model; own-inventory side baseline 0.70 (BUILD4 refit).")
s["live_lab"] = [{"what": "code5/rawrec.py: dm_clob_raw (unaggregated CLOB events, BTC 5m current+next, 15m current), dm_bnf/dm_bnfa (Binance "
                          "futures bookTicker + aggTrade), dm_bns, dm_cb, dm_okx, dm_byb, dm_hl, dm_rtds (staggered RTDS); hard stop 18:00 UTC; "
                          "disk cap 280 MB", "start": 1793455457, "end": 1793469600}]
s["live_lab_note"] = ("Shared recorder (pid 27184) running. Own raw recorder code5/rawrec.py (Writer, dev/sealed by block) from 2026-10-31 14:04 UTC "
                      "(restarted 14:06 and 14:22 to add the futures aggTrade path and full futures bookTicker), hard stop 18:00 UTC; read with "
                      "code5/rawread.py (handles gzip members cut by restarts). The shared rtds feed's 'written' counter stays 0 although records exist.")
hyp = s["hypotheses"]
nid = len(hyp) + 1
for fam, desc, vm, verdict in [
    ("Q1 coverage by family", "fills and abs cash-flow PnL by market family", {"validate_btc5m": [0.7835, 0.6859], "validate_btc5m_15m": [0.8684, 0.8911],
                                                                                "study_btc5m": [0.5356, 0.5555]}, "BTC 5m-only rule cannot reach 80/80 on STUDY-like periods; BTC 5m+15m does on VALIDATE"),
    ("P2a level clearing (tape)", "P(cluster | bid hit clears the level) vs held, STUDY", {"p_cleared": 0.0063, "p_held": 0.0085, "mh_ratio": 0.634}, "strong back-of-queue form rejected"),
    ("I5 settlement disagreement", "late net side in proxy-disagreement windows", {"cluster_follows_real": 0.60, "market_follows_real": [0.73, 0.85], "near_strike": 0.51}, "not settlement-informed"),
    ("P4 flatten", "taker buys of the under-held side", {"share_under_held": [0.72, 0.83], "pair_cost_median": [1.12, 1.06], "taker_pnl_share": [0.04, 0.02]}, "real but small"),
    ("Q2 size in PnL", "rule PnL x size_hat vs wallet dollar PnL (VALIDATE)", {"per_share": [0.329, 0.325], "x_clock": [0.321, 0.283], "x_own": [0.341, 0.288],
                                                                              "ceiling_one_share": [0.688, 0.780]}, "size not the binding constraint"),
    ("live raw-book fingerprint", "exact-size adds before the cluster's matches", {"orders": 138, "found": 0.993, "added_at_touch": 0.628}, "the cluster's quotes are observable"),
    ("live reference feed", "requote direction vs venue moves 50-250 ms earlier", {"binance_futures": 0.97, "bybit": [0.60, 0.80], "okx": [0.62, 0.70], "coinbase": [0.41, 0.56],
                                                                                    "spot": [0.51, 0.54], "hyperliquid": [0.43, 0.62]}, "Binance USD-M futures is the reference"),
    ("live quote level", "near-touch quote vs TWAP-60 digital fair", {"futures_mad": 0.031, "futures_corr": 0.977, "median_offset": -0.02, "chainlink_mad": 0.105}, "quote = futures fair - h; h and vol not yet tick-precise"),
]:
    hyp.append({"id": f"H{nid}", "family": fam, "description": desc, "validate_metrics": vm, "verdict": verdict})
    nid += 1
s["data_sources"].append("iteration 5: own raw recorder (code5/rawrec.py) feeds dm_* in .cache/live/dev/ from 2026-10-31 14:04 UTC; calldata of the "
                         "cluster's live-block txs and of all 797 trades of 14:10-14:13 UTC; BTC 15m windows + taker tapes 2026-10-09..30 "
                         "(.cache/re/directional-maker/t15/, 148 MB)")
s["iterations"].append({"n": 5, "minutes": None, "best_validate_score": 0.716, "validate_definition": "2026-10-27..30 (lot second half)",
                        "paradigm": "observe the quote: unaggregated raw book + size fingerprint + ms reference feeds (live lab)",
                        "families": ["X15 raw-book fingerprint", "X10 reference feed lead-lag", "X12/A1 RTDS settlement + Chainlink race", "X17/X23 signed vs posted",
                                     "X16 level clearing", "X14 settlement disagreement", "X18 flatten rule", "X21 coverage by family", "X22 size in PnL",
                                     "live quote level vs fair", "live requote cadence and lifetimes", "BTC 15m tape fetch"]})
s["status"] = "continue"
s["wall_reason"] = None
P.write_text(json.dumps(s, indent=1), encoding="utf-8")
print("catalog open:", [k for k, v in cat.items() if v["status"] == "open"])
