"""Iteration 7: update state.json (catalog X28-X43, components, strategy statement, hypotheses, live_lab, iterations)."""
import os, json, shutil
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
P = _ROOT + "/research/reverse_engineering/btc5m-bot/state.json"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
shutil.copy(P, _ROOT + "/.cache/re/btc5m-bot/state_backup_iter6.json")
s = json.load(open(P))
pnl = json.load(open(f"{R}/pnl7.json")); st7 = json.load(open(f"{R}/strict7.json")); sz = json.load(open(f"{R}/size7.json"))
rem = json.load(open(f"{R}/remainder7.json")); tl = json.load(open(f"{R}/tilt7.json"))
lag_a = json.load(open(f"{R}/lag7_1793458200.json")); lag_b = json.load(open(f"{R}/lag7_1793456040.json"))

cat = s["catalog"]
cat["X28"] = {"status": "tried", "source": "panel iteration 6, assumptions P1 (PnL target as an order-overlap problem)",
              "evidence": "pnl7.py / strict7.py (results/pnl7.json, strict7.json): split-half per-window PnL DS -0.03, GF 0.14, XM -0.03, pool 0.16; PnL vs net x outcome 0.88-0.93; "
                          "big orders vs total GF 0.85, XM 0.73, DS 0.35; oracle at 30 shares pool 0.41/0.49, at the size class 0.88/0.87; strict-fill oracle (own decisions through the "
                          "frozen fill model) at latency >= 2 s and true size pool 0.40/0.39 (DS 0.50, GF 0.48, XM 0.49), at 30 shares 0.14/0.21; same-block window true size 0.68/0.66, "
                          "30 shares 0.26/0.31. The frozen replica's 0.18 is the ceiling of its own design. Convention for the correlation pre-registered (NOTES iteration 7). "
                          "Not done: an executable size-aware replica at the decoded latency (iteration 8)."}
cat["X29"] = {"status": "tried", "source": "panel iteration 6, assumptions P2 (large size is an event-level decision)",
              "evidence": "size7.py (results/size7.json): both-large co-occurrence across wallets 1.68 x independence vs within-(wallet, hour) permutation null 0.75 (97.5% 0.84, "
                          "p = 0.0005); P(partner large | large) 0.379 vs 0.182; P(large | PIT block-clock features) within-wallet AUC 0.44-0.59 (all features 0.70, wallet alone 0.66). "
                          "Event-level component confirmed, not predictable from BTC 1-s moves / price / time; live test of depth and microprice strength pending (too few large orders on the Saturday block)."}
cat["X30"] = {"status": "open", "source": "panel iteration 6, assumptions P3 (bot FV differs from the market's; underdog-tilt surface)",
              "evidence": "Steps 1-2 done (tilt7.py, results/tilt7.json): underdog share at |p - 0.5| 0.3-0.4: cluster small 58.3%, big 68.7%, other takers 34.8%; at static prices "
                          "(< 2 c over 30 s) cluster 57.0% vs others 36.5%; after moves 58.5%: a vol/shape difference or ladder artefact, not a lag. Step 3 (revealed-preference FV fit) and step 4 open."}
cat["X31"] = {"status": "tried", "source": "panel iteration 6, assumptions P4 (microprice tick: trigger or correlate)",
              "evidence": "lag7.py (results/lag7_*.json): lag profile of the vote in 100-ms bins peaks at [m-400, m-200) (75%) and falls to ~50% after m+100 ms (placebo ~50%); "
                          "hazard on a 100-ms grid steps up with the signed tick toward o (2.3% -> 5.1% -> 5.6% -> 8.7%; first interval 1.0% -> 9.4%), flat for moves against o; "
                          "signed-move AUC 0.64/0.73 vs activity 0.69/0.61, combined +0.02/+0.08. Verdict: trigger (necessary, low base hazard), not a correlate."}
cat["X32"] = {"status": "open", "source": "panel iteration 6, assumptions P5 (ladder lifecycle around the +172.7 s burst)", "evidence": "Not tested in iteration 7."}
cat["X33"] = {"status": "open", "source": "panel iteration 6, assumptions P6 (tier bonuses / why four wallets)", "evidence": "Not tested in iteration 7."}
cat["X34"] = {"status": "tried", "source": "panel iteration 6, information P1 / mechanics critique 1 (record the exam inputs through the sealed blocks)",
              "evidence": "rec_exam7.py (pid 32576) started 10-31 16:03:48 UTC, hard stop 11-02 06:00 UTC, cap 300 MB: feeds btc5m_xclob + btc5m_xven written in every block via the Writer "
                          "(sealed folder never read); _live_vote in final_rule.py reads them (16:04-16:25 dev: 273 matches, cover 61.5%, agree 80.4%, identical to the v2 lab feed). "
                          "Not done: the archive-only vote (OKX tbt, Bybit ob200) comparison of the panel's step 3."}
cat["X35"] = {"status": "tried", "source": "panel iteration 6, mechanics P1 (remainder lifecycle: cancel / TTL / fill-and-kill)",
              "evidence": "remainder7.py (results/remainder7.json): 59.4% of taker-first orders leave a remainder; 19% of remainders refill, within 0 s median (p90 3 s); removal upper "
                          "bound median 5 s (42% <= 3 s, 69% <= 10 s). GTC remainder cancelled within seconds (TTL ~2-5 s), not resting, not FAK."}
cat["X36"] = {"status": "open", "source": "panel iteration 6, information P2 (decision-level replay replica on the recorded pre-match book)",
              "evidence": "Partly answered on tapes by X28's strict-fill oracle; the live-book replay is not done."}
cat["X37"] = {"status": "open", "source": "panel iteration 6, information P3 (Tardis 2026-11-01 free sample, all venues tick by tick)", "evidence": "The 11-01 files do not exist yet (10-31)."}
cat["X38"] = {"status": "open", "source": "panel iteration 6, information P4 (block-clock limit as the formal h1/h2 account, per wallet)",
              "evidence": "Pooled (iteration 6): vote 84.8% at match ms vs 76.8% at the block clock; per-wallet version not done."}
cat["X39"] = {"status": "open", "source": "panel iteration 6, information P5 (exchange clock calibration and reaction-latency fingerprint)", "evidence": "Not tested."}
cat["X40"] = {"status": "open", "source": "panel iteration 6, mechanics P2 (per-block match clock from tx order and co-racers' signing ms)",
              "evidence": "Iteration 6 (X22): tx_index fit leaves |error| < 200 ms for 27.5% vs 26.5% constant; co-racers' signing ms worse than a constant (information panel)."}
cat["X41"] = {"status": "open", "source": "panel iteration 6, mechanics P3 (live reaction kernel per series and fixed latency)",
              "evidence": "Vote-level kernel measured in X31 (peak 200-500 ms before the match); per-series 10-ms kernels not done."}
cat["X42"] = {"status": "open", "source": "panel iteration 6, mechanics P4 (ladder level chosen; reservation price from pay-up / not chasing)", "evidence": "Not tested."}
cat["X43"] = {"status": "open", "source": "panel iteration 6, mechanics P5 (authenticated GitHub code search for the bot's source)",
              "evidence": "No GitHub token / connector authorized in this session (the GitHub MCP server needs authentication); merged with X10 for the next attempt."}
cat["D2"]["evidence"] = (cat["D2"].get("evidence", "") + " | Iteration 7: decision-level hazard on a 100-ms grid at matching-engine ms (lag7.py): P(match on o in [t+100, t+600)) "
                         "2.3% -> 8.7% with the signed microprice move toward o; AUC move 0.64/0.73, activity 0.69/0.61, combined 0.72/0.68.").strip(" |")
cat["D2"]["status"] = "tried"
cat["B2"]["evidence"] = (cat["B2"].get("evidence", "") + " | Iteration 7 (X35): remainders cancelled within seconds (refills <= 3 s, removal bound median 5 s).").strip(" |")

s["components"] = {
    "selection": {"confidence": 0.85, "tag": "VALIDATE-only", "description": "Every BTC 5m Up/Down window (94-99% traded, all wallets in the same windows), nothing else; inside a window only prices in the ladder range ~0.12-0.88; whole-cluster outages of 40 min-5 h are bot-side."},
    "timing": {"confidence": 0.8, "tag": "VALIDATE-only", "description": "Decision = submission of a pre-signed ladder order 200-500 ms after a tick-level MICROPRICE move of the BTC/ETH perps and spot (Binance, OKX, Bybit) toward the outcome: live lag profile peaks at [m-400, m-200) and vanishes 100 ms after the match; the hazard of a match rises 2.3% -> 8.7% with the signed tick (trigger, not correlate; necessary, low base hazard). Historically presence on block seconds 0.875 vs pure baseline 0.819."},
    "side": {"confidence": 0.6, "tag": "VALIDATE-only", "description": "Per decision: the direction of the perp microprice move over [m-600, m-100) ms (ten-series vote 86% / 83% / 75% in three live intervals; six-series exam-feed vote 80% on 62% of decisions); per block second 76.7% historically; buys both outcomes in 99.8% of windows pooled; buys the underdog more as |p-0.5| grows (58% small / 69% big at 0.3-0.4 vs others 35%), also at static prices."},
    "price": {"confidence": 0.9, "tag": "VALIDATE-only", "description": "Limit = the touch of the chosen outcome at the decision (trivial touch anchor, stated as such): VALIDATE calldata 95.1% within a tick; live 93% against the recorded ask 50 ms before the match; 11% of orders 1+ c above the touch (more for large)."},
    "size": {"confidence": 0.65, "tag": "VALIDATE-only", "description": "Fixed (small, large) menu per day signed at every price; large share is a per-wallet setting (DS 8%, GF 33%, XM 13%) PLUS an event-level component (both-large across wallets 1.68x independence vs null 0.75, p=0.0005) that block-clock features do not predict (within-wallet AUC 0.44-0.59). The size class carries the replicable PnL (oracle 30-share 0.41 vs size-class 0.88 pooled)."},
    "exit": {"confidence": 0.9, "tag": "VALIDATE-only", "description": "Taker remainders (59% of orders) rest as GTC for at most a few seconds (refills <= 3 s, removal bound median 5 s) and are cancelled; holds to resolution; no sells, merges, splits or conversions; one REDEEM per window; daily TAKER_REBATE = 0.5 x prior-day taker fees (~85% of income) and MAKER_REBATE; no liquidity or holding rewards."},
}
s["strategy_statement"] = (
    "One operator runs a TypeScript clob-client bot on four wallets [VALIDATE-only]. For every BTC 5-minute Up/Down window it pre-signs a ladder of BUY limit orders on both "
    "outcomes at every cent, in bursts 90 s before the open and at +42 s and +173 s, signing the wallets one after another [VALIDATE-only, calldata]. It submits a pre-signed order "
    "at the current touch of the outcome toward which the BTC/ETH perpetuals' microprice just ticked: live, the side information peaks 200-500 ms before the match and vanishes "
    "right after it, and the hazard of a match rises about fourfold with the size of the tick toward the outcome (a trigger, not a correlate) [VALIDATE-only: live development "
    "block]; the ten-series vote gives the side of 75-86% of taker decisions in three successive live intervals [VALIDATE-only]. The limit is the touch (95% within a tick from "
    "calldata) [VALIDATE-only]; an unfilled remainder rests for at most a few seconds and is cancelled [VALIDATE-only]. Sizes come from a fixed daily menu (30/60/100); the large "
    "size is partly chosen per event across wallets, but nothing measured at the block clock predicts it [VALIDATE-only]. It buys both outcomes in almost every window, tilts "
    "toward the underdog as prices leave 0.5, and holds to resolution [VALIDATE-only]. About 85% of its income is the 50% taker-fee rebate on its volume; trading after fees is near "
    "break-even [VALIDATE-only]. Per-window PnL is a sum of order-level bets (split-half ~0), so replicating it requires the same orders and sizes: with a fixed 30-share size and "
    ">= 2 s latency even the wallet's own decisions reach only 0.14-0.40 [VALIDATE-only]. Nothing is exam-verified.")
s["hypotheses"] += [
    {"id": "H61", "family": "PnL order overlap (X28)", "description": "per-window PnL is a sum of order-level bets; replicable only through the same orders and sizes",
     "validate_metrics": {"split_half_pool": pnl["by_wallet"]["pool"]["split_half"], "oracle_30_pool": pnl["by_wallet"]["pool"]["oracle_30_shares"], "oracle_size_class_pool": pnl["by_wallet"]["pool"]["oracle_size_class_30_100"]}, "verdict": "supported"},
    {"id": "H62", "family": "strict-fill oracle (X28)", "description": "the wallet's own taker decisions through the frozen strict-fill model",
     "validate_metrics": {k: st7[k] for k in ("[s+1,s+3]_true", "[s+1,s+3]_30", "[s-1,s+1]_true", "[s-1,s+1]_30")}, "verdict": "fill model at >= 2 s caps the pool at 0.40 (wall for convention a)"},
    {"id": "H63", "family": "event-level size (X29)", "description": "large size shared across wallets per event; P(large | PIT features)",
     "validate_metrics": {"cooccurrence": sz["cooccurrence"], "p_large_model": {k: v["auc_validate"] for k, v in sz["p_large_model"].items()}}, "verdict": "event-level confirmed; not predictable at the block clock"},
    {"id": "H64", "family": "trigger vs correlate (X31)", "description": "lag profile and decision-level hazard of the microprice tick",
     "validate_metrics": {"hazard_rep": lag_a["hazard"], "hazard_first": lag_b["hazard"]}, "verdict": "trigger"},
    {"id": "H65", "family": "remainder lifecycle (X35)", "description": "GTC remainder TTL",
     "validate_metrics": {k: rem[k] for k in ("taker_first_with_remainder_share", "remainder_ever_fills_again_share", "fill_span_s_when_refilled", "upper_bound_removal_s_after_last_fill")}, "verdict": "cancelled within seconds"},
    {"id": "H66", "family": "underdog tilt (X30 steps 1-2)", "description": "model-free surface of underdog share by |p-0.5|, rel, size, static vs moved",
     "validate_metrics": tl["summary_dist_0.3_0.4"], "verdict": "tilt persists at static prices (vol/shape or ladder artefact), not a lag"},
    {"id": "H67", "family": "live side, exam-input feeds", "description": "frozen six-series vote on btc5m_xven / ten-series on venues2, 16:04-16:25",
     "validate_metrics": {"six_series_exam_feed": {"n": 273, "cover": 0.6154, "agree": 0.8036, "placebo_agree": 0.5268}, "ten_series_v2": {"cover": 0.8462, "agree": 0.7532, "placebo_agree": 0.5}}, "verdict": "replicates at 75-80%, decaying"},
]
s["data_sources"] += ["Iteration 7: exam-input recorder rec_exam7.py (btc5m_xclob, btc5m_xven; every block through the Writer; sealed never read)",
                      "Iteration 7: all 2,016 VALIDATE taker tapes from the shared HTTP cache (session scratchpad, deleted)",
                      "Iteration 7: on-chain cluster fills 10-31 14:50-16:26 (development block)"]
s["live_lab"].append({"what": "rec_exam7.py EXAM-INPUT recorder (pid 32576): feeds btc5m_xclob (Polymarket BTC 5m touch changes, trades with server ms + tx hash, 10-level snapshots / 10 s) and btc5m_xven (Binance USD-M + spot bookTicker, OKX bbo-tbt, BTC/ETH, 30 ms); writes EVERY block through tools/live.py Writer (sealed blocks filed by the Writer, never read); cap 300 MB; status .cache/re/btc5m-bot/rec_exam7.status",
                      "start": 1793462628, "end": 1793599200})
s["sealed_from"]["development_after_H_used"] = [[1793404800, 1793426400], [1793448000, 1793463900]]
s["iterations"].append({"n": 7, "minutes": 95.0, "best_validate_score": 0.9132, "block_seconds_presence": 0.8747, "block_seconds_pure_baseline": 0.8193,
                        "pnl_corr": 0.1755, "pnl_oracle_ceilings_pool": {"strict_2s_true_size": st7["[s+1,s+3]_true"]["pool"], "strict_2s_30": st7["[s+1,s+3]_30"]["pool"],
                                                                        "same_block_true_size": st7["[s-1,s+1]_true"]["pool"], "size_class_no_fill_model": pnl["by_wallet"]["pool"]["oracle_size_class_30_100"]},
                        "families": ["exam-input recorder through sealed blocks (X34)", "PnL as order overlap + strict-fill oracle (X28)", "event-level size (X29)",
                                     "trigger vs correlate: lag profile + decision-level hazard at ms (X31, D2)", "remainder lifecycle (X35)", "underdog tilt surface (X30 steps 1-2)",
                                     "third out-of-sample live side interval on the exam feeds"]})
s["status"] = "continue"
s["wall_reason"] = None
s["frozen_rule"] = (s.get("frozen_rule") or "") if isinstance(s.get("frozen_rule"), str) else s.get("frozen_rule")
json.dump(s, open(P, "w"), indent=1)
op = [k for k, v in s["catalog"].items() if v.get("status") == "open"]
print("catalog", len(s["catalog"]), "open", len(op), op)
