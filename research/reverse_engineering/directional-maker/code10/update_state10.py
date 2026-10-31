"""Iteration 10: bring state.json up to date (catalog X87-X100 and status changes, components, hypotheses, iteration
entry, strategy statement, live_lab, data sources). R6 stays the frozen rule; target_metrics keep R6's VALIDATE values."""
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent / "state.json"
R = HERE.parent / "results"
s = json.loads(P.read_text())
cat = s["catalog"]


def j(name):
    try:
        return json.loads((R / name).read_text())
    except Exception:  # noqa: BLE001
        return {}


lot = j("iter10_a1_lot.json")
liv = j("iter10_a1_live.json")
d06 = j("iter10_a1_dev1031_0006.json")
m1 = j("iter10_m1_pair_lot.json")
m2 = j("iter10_m2_phase.json")
i95 = j("iter10_i95_twap.json")
r7 = j("iter10_r7_side.json")
sw = j("iter10_i93_switch_noise.json")


def g(d, *ks, default=None):
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def f3(x):
    return "n/a" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


stD = g(lot, "study", "SCHEDULE_ONLY_D_mid_a", default={})
vaD = g(lot, "validate", "SCHEDULE_ONLY_D_mid_a", default={})
stDall = g(lot, "study", "D_mid_a", default={})
vaDall = g(lot, "validate", "D_mid_a", default={})
a1_text = (f"STUDY region D (all fills) {f3(stDall.get('acc_D_bought_cl_favourite'))} (n {stDall.get('n_D')}), schedule rungs only "
           f"{f3(stD.get('acc_D_bought_cl_favourite'))} (n {stD.get('n_D')}); VALIDATE aggregate {f3(vaDall.get('acc_D_bought_cl_favourite'))} "
           f"(n {vaDall.get('n_D')}), schedule only {f3(vaD.get('acc_D_bought_cl_favourite'))} (n {vaD.get('n_D')}); "
           f"region D share {f3(stDall.get('share_D'))} / {f3(vaDall.get('share_D'))} vs live 0.19-0.20; "
           f"frozen posture with S = Chainlink {f3(g(lot, 'study', 'posture_frozen_cl_mid_a', 'acc'))} / {f3(g(lot, 'validate', 'posture_frozen_cl_mid_a', 'acc'))} "
           f"(Binance S: 0.543 / 0.645); 10-31 00-06 development block (block clock): region D {f3(d06.get('acc_D_bought_cl_favourite'))} (n {d06.get('n_D')}, "
           f"share {f3(d06.get('share_D'))}).")

X = {
    "X87": ("open", "source: panel iter9 information I9-1 (pmxt archive of the unaggregated CLOB stream, 07-16..08-10). Iteration 10 step 1 "
            "(code10/pmxt_pilot.py, results/iter10_pmxt_pilot_2026-07-22T13.json): host verified (HEAD 07-20T13 200, 527.5 MB; 08-09T13 200; "
            "10-20T13 404); 07-22 13-14 UTC, 11 BTC 5m windows, 67 MB of range reads, 4.2 M events; calldata of 150 cluster txs: timestamp 0 "
            "and metadata 0 in 100%, per-wallet salt monotone 92-100% at 25-32 orders/s, sizes 500/300/50 + pairing-class sizes; filled "
            "orders: add found 62%, age median 1,044 ms, at the touch 49%, posted 69 ms after the previous trade, 26% in 20-ms same-size "
            "bursts. Same engine family, different configuration. Steps 2-6 (24-day reduction, pre-registered fit 07-16..31 / score "
            "08-01..09, replay, module schedule) not done; no Chainlink history exists for July."),
    "X88": ("tried", "source: panel iter9 information I9-2 (make the quote unit examinable). Iteration 10 (code10/i92_label.py, "
            "code10/i92_dx.py): the shared recorder's clob_crypto files hold ~0.09 top-of-book snapshots per token-second for BTC 5m: "
            "the '+500 at the touch' label has recall 0.010-0.022 vs the raw label (unusable); the own exam recorder dx_clob (BTC 5m "
            "current+next, 15m current, to 11-03 00:00 UTC) gives recall 1.00, precision 0.44 (definitional: it also marks adds that left "
            "the touch within the second) on the 15:53-16:30 overlap. Step 3 done: code10/famrec.py (feed dw_clob: ETH, SOL, XRP, BNB, DOGE, "
            "HYPE 5m current+next and 15m current, examrec's reduction) started 10-31 22:59:41 UTC, hard stop 11-03 00:00 UTC. Step 2 "
            "(pmxt throttle simulation) not needed after step 1. Hourly/daily/4h books are not in any own recorder."),
    "X89": ("open", "source: panel iter9 information I9-3 (module state from public triggers and the operator's clock on the full "
            "history). Iteration 10: step 3 pre-registered (code10/i93_switch_stamps.py: six 30-s Chainlink runs in the 2 h before each of "
            "6 switch-offs and in two Mon-Thu controls each; 3,240 stamps queued in the detached fetch). The full-history activity "
            "(June-October) is not fetched; the EU (10-25) and US (11-01) DST changes both fall at the end of the history, so the "
            "zone test needs the post-11-01 development blocks (see X99). Step 3 result (code10/i93_switch_noise.py): " + json.dumps(g(sw, "pooled", default={}))
            + " (median per 30-s run: sd of 1-s Chainlink changes, lag-1 autocorrelation, sd of Chainlink - Binance within the run)."),
    "X90": ("open", "source: panel iter9 information I9-4 (save the settlement stream for BUILD and the lot before the 30-day horizon; redo "
            "the historical posture with the real reference). Iteration 10: detached polite fetch code10/fetch_cl_hist.py (crypto-price "
            "endpoint, ~1.4-1.6 requests/s, one request = the values at tau and tau + 300) of 51,879 queued stamps (lot BTC 5m fills on the "
            "pre-registered match clock, BUILD BTC 5m fill seconds b - 4, switch-noise runs, BTC 15m), hard stop 11-01 10:00 UTC; "
            "chunks in .cache/re/directional-maker/cl/cl_hist10_*. The historical posture with S = Chainlink is X97."),
    "X91": ("open", "source: panel iter9 information I9-5 (mo-money's third input). Iteration 10 (code10/i95_twap.py): candidate (b) the "
            "RTDS TWAP-60 topic at the add: mo-money's 500s " + f3(g(i95, "momoney|500", "add_tw")) + " vs Chainlink "
            + f3(g(i95, "momoney|500", "add_cl")) + "; almach " + f3(g(i95, "almach|500", "add_tw")) + " vs " + f3(g(i95, "almach|500", "add_cl"))
            + ", bosona " + f3(g(i95, "bosona|500", "add_tw")) + " vs " + f3(g(i95, "bosona|500", "add_cl")) + ": rejected (lowers every wallet). "
            "Candidates (a) the RTDS Binance relay (dz_rtdsbn, only from 19:12 UTC, sealed so far), (c) the 15m mid, (d) the complement's "
            "best ask: not tested; (a) needs 11-01 06-12."),
    "X92": ("tried", "source: panel iter9 mechanics M1 (two order types: the imbalance pairing bid). Iteration 10 (code10/m1_pair_lot.py): "
            "class replicated on the lot (pairing 11.2% STUDY / 14.1% VALIDATE aggregate of BTC 5m maker BUY fills, on the under-held outcome "
            "1.000 / 1.000; schedule rungs 0.298 / 0.316); price NOT anchored to own cost (pair cost median 0.91 / 0.81, q10-q90 0.50-1.42 / "
            "0.44-1.24; within a tick of 1 - held VWAP - m 1.4-4.7%, of 1 - last held price - m 1.7-4.8%; signature >= 60% fails); pairing "
            "fills held to resolution +1.1% / -0.3%, other fills +1.5% / +4.7%. The side by order type (panel: 0.842 / 0.906 live, 0.721 "
            "VALIDATE) is own state. Strict replay with both order types: X64."),
    "X93": ("tried", "source: panel iter9 mechanics M2 (time-left phase machine). Iteration 10 (code10/m2_phase.py): per-phase choice among "
            "frozen / slow v3600 / TWAP lock-in fairs on 12-15, scored on 15-18: " + f3(g(m2, "test_15_18", "phase_rule")) + " vs frozen "
            + f3(g(m2, "test_15_18", "frozen")) + " (n " + str(g(m2, "test_15_18", "n")) + "); per wallet mo-money "
            + f3(g(m2, "test_15_18", "per_wallet_phase_rule", "momoney")) + ", almach " + f3(g(m2, "test_15_18", "per_wallet_phase_rule", "almach"))
            + ", bosona " + f3(g(m2, "test_15_18", "per_wallet_phase_rule", "bosona")) + "; the 60-120 s phase 0.782 (frozen 0.756). Signature "
            "(60-120 s >= 0.82 with one pre-registered fair, every wallet >= 0.80) not met; the gain is mostly the slow sigma, which failed "
            "its historical replications. Pre-registered as a secondary for 11-01 06-12."),
    "X94": ("open", "source: panel iter9 mechanics M3 (mo-money's deficit as a ladder parameter: per-wallet skew and half-spread from "
            "wallet-attributed limit prices, survival of off-posture rungs). Not done: filled orders alone are selected at the touch; the "
            "survival test needs per-wallet attribution of unfilled adds (the 11-01 full-depth book)."),
    "X95": ("open", "source: panel iter9 mechanics M4 (account for every signature; unrecorded families; collateral). Iteration 10: the "
            "family recorder dw_clob (X88) now records XRP / BNB / DOGE / HYPE / ETH / SOL 5m-15m books from 10-31 22:59 UTC; the salt-rate "
            "regression and the hourly/daily books are for the next development block. Collateral: the assumptions panel F2 measured no "
            "deposits, weekly Monday sweeps at the 01:00 restart and a minimum cash of $19.7-21.8k (capital never binds; development data)."),
    "X96": ("tried", "source: panel iter9 mechanics M5 (off-posture fills as lost cancel races). Iteration 10 (code10/a1_score.py live, "
            "m5_cancel_race; 647 fills with taker sign_ms): the posture with the report in force at sign_ms + b - lambda (b {0, 190}, lambda "
            "{0, 100, 150} ms) scores 0.698-0.718 vs 0.739-0.740 at the match; where they differ (5-8%) the match posture is right 0.70-0.75, "
            "the arrival posture 0.25-0.30. Rejected: the filled rungs had already re-priced for the publish between signing and match."),
    "X97": ("tried", "source: panel iter9 assumptions A1 (is the posture a stable rule? sigma-free test on a historical match clock from "
            "taker signing ms). Iteration 10 (code10/a1_delay.py, a1_stamps.py, a1_score.py, a1_0006.py): calibration on 10-31 14:06-16:30 "
            "(737 fills): region D truth 0.965, pre-registered proxies (T_hat = clip(sign_ms + 620, b - 3.0 s, b - 1.5 s), Chainlink "
            "report at T_hat - 1.432 s, last clean print at b - 3) 0.953, block clock (report b - 4) 0.952: the proxies reproduce the truth. "
            "History with the real Chainlink value (crypto-price endpoint, random subsample of the lot fills): " + a1_text +
            " By rung class (code10/r7_side.py): VALIDATE 500-class rungs follow Chainlink in region D 0.973 (73 fills, 26 windows, "
            "window mean 0.974), 62s 0.458, 250s 0.484; STUDY 500s 0.759 (58 fills, 11 windows), 62s 0.532; fresh development block 10-31 00-06 "
            "(code10/a1_0006_class.py, calldata of all 1,178 cluster orders, prediction written before the run): 500s 1.000 (41 fills, 10 windows), "
            "62s 0.448 (58 fills; hour 00 UTC 0.103, n 29, which is the whole hour-00 anomaly). Verdict: the posture is the "
            "side rule of the US-session 500 ladder and replicates on the historical VALIDATE at the live level in the sigma-free region; "
            "the all-fill failure is a composition effect of the off-session 62/250 ladder (00-12 UTC), whose side follows no public "
            "candidate (0.48-0.51 on STUDY). The pre-registered class-conditional R7-side failed on VALIDATE (0.660 vs 0.710, gain -0.049 "
            "[-0.085, -0.017]) because the STUDY-chosen rules for the 250 / 100 rungs did not transfer."),
    "X98": ("ruled_out", "source: panel iter9 assumptions A2 (mo-money: queue-order selection or a per-account reference weight). "
            "Measurements: (a) queue selection: the mechanics panel's sibling-copy classes (iter9_mechanics finding 3: where mo-money's "
            "order was filled first its posture is 0.80 vs almach 0.99; it is lower in every class) contradict the prediction that the "
            "deficit halves at equal rank; (b) a per-account Binance weight: the information panel's blend a x fair_CL + (1 - a) x fair_BN "
            "peaks for mo-money at a = 0.9 with 0.770 vs 0.762 at a = 1 (+0.008 < the +0.04 signature); iteration 10 adds the TWAP-60 "
            "reference (X91), which lowers every wallet. Mo-money's input remains unnamed (X91 / X94 open)."),
    "X99": ("open", "source: panel iter9 assumptions A3 (freeze clock conventions before the post-DST exam blocks). Iteration 10: "
            "pre-registration written in NOTES (23:13 UTC 10-31): UTC and ET variants of hour, US-session flag, size session, calendar "
            "gate and restart; observations 11-02 00-06 (restart and sweep timestamps only), 11-02 12-18 (first 500 of the session), 11-01 "
            "18-24 (any switch). Not observable yet."),
    "X100": ("tried", "source: panel iter9 assumptions A4 (locate the profit decision: locked pairs vs residual vs rebates). Iteration 10 "
             "(code10/m1_pair_lot.py window split, per wallet x window, BTC 5m): STUDY locked " + f3(g(m1, "STUDY", "window_split", "locked_sum"))
             + " USD, residual " + f3(g(m1, "STUDY", "window_split", "resid_sum")) + "; VALIDATE aggregate locked "
             + f3(g(m1, "VALIDATE_aggregate", "window_split", "locked_sum")) + ", residual " + f3(g(m1, "VALIDATE_aggregate", "window_split", "resid_sum"))
             + "; var(residual)/var(total) " + f3(g(m1, "STUDY", "window_split", "var_resid_over_var_total")) + " / "
             + f3(g(m1, "VALIDATE_aggregate", "window_split", "var_resid_over_var_total")) + ". Neither part is positive in every split (A4's "
             "and E2's signatures both fail); the residual carries most of the cross-window variance. Rebates: the assumptions panel F3 "
             "puts maker+taker rebates and rewards at $23.0k of $111.7k net (10-08..30), BUILD maker rebates $14.5k vs BTC 5m PnL $35k."),
}
for k, (st_, ev) in X.items():
    cat[k] = {"status": st_, "evidence": ev}

for k in ("X52", "X68"):
    cat[k]["status"] = "tried"
    cat[k]["evidence"] = str(cat[k].get("evidence", "")) + (" | iteration 10: done in its strong form as X97 (A1): a historical match clock "
                                                            "T_hat from the taker signing ms (lot calldata, 97%) + a calibrated delay; on 10-31 it reproduces the "
                                                            "match-clock region-D truth (0.953 vs 0.965), and on the lot region D stays near two thirds.")
cat["X76"]["evidence"] = str(cat["X76"].get("evidence", "")) + (" | iteration 10: historical per-wallet region D (STUDY, real Chainlink): "
                                                                + json.dumps(g(lot, "study", "per_wallet_D_mid_a", default={}))
                                                                + "; TWAP-60 at the add lowers mo-money's 500s too (X91); 500 ladder on the historical VALIDATE (aggregate): region D almach 1.000 "
                                                                "(n 14), bosona 1.000 (16), mo-money 0.953 (43), posture over 500s 0.754 / 0.688 / 0.781: mo-money's live 500 "
                                                                "deficit is not a fixed per-account property. Still open.")
cat["X74"]["evidence"] = str(cat["X74"].get("evidence", "")) + (" | iteration 10 (H-VOL-500, pre-registered; code10/hvol500.py): on the 500 "
                                                                "ladder with the real Chainlink value on the calibrated match clock, VALIDATE (aggregate) frozen 0.742 vs v3600 "
                                                                "0.617 (gain -0.125 [-0.230, -0.034]); STUDY 0.613 vs 0.633: the frozen (fast) sigma stays.")
cat["X83"]["evidence"] = str(cat["X83"].get("evidence", "")) + (" | iteration 10: the family recorder dw_clob (X88) adds the books of every "
                                                                "5m/15m crypto family from 10-31 22:59 UTC for a family-general universe; per-family presence models not built.")

comp = s["components"]
comp["side"]["description"] = (
    "two side rules by ladder: the US-session 500 x 2^k rungs (74% of VALIDATE fills in 12-18 UTC, 78% of the 10-31 block) buy the "
    "outcome whose Chainlink edge over the Polymarket mid is positive (digital of the report stamped T - 1.432 s, Gamma strike, 1.4 x "
    "300-s vol): live 10-31 0.786 per fill, 0.965 where Chainlink and the market disagree on the favourite; historical VALIDATE "
    "(calibrated match clock, real Chainlink) 500s 0.742 per fill and 0.973 in that region (26 windows), STUDY 0.613 / 0.759, the "
    "fresh 10-31 00-06 block 1.000 in that region (10 windows). The "
    "off-session 62/250 rungs (00-12 UTC) follow no public candidate (region D 0.46-0.53; cheaper / favourite / Binance / Chainlink "
    "0.48-0.51 on STUDY); where they coexist with 500s in a window they sit on the other outcome (71% of 163 VALIDATE pairs), i.e. "
    "the far-side rungs of the same ladder; in pure off-session windows their side is undecoded (hypothesis: an unskewed two-sided "
    "ladder whose fill side the takers choose). Imbalance pairing bids sit on "
    "the under-held outcome 100% (own state). Mo-money's 500s are off the posture at the add (0.646; not TWAP-60). Off-posture fills "
    "are not lost cancel races. A class-conditional public rule failed its pre-registered VALIDATE test (0.660 vs 0.710).")
comp["side"]["confidence"] = 0.6
comp["side"]["tag"] = "VALIDATE-only (500 ladder: live 10-31 and historical VALIDATE region D); hypothesis (off-session 62/250 ladder)"
comp["size"]["description"] = ("October: schedule rungs 500 x 2^k with a one-fifth level (100 / 12 only at 30-120 s left), 62/250 outside the "
                               "weekday session; imbalance pairing bids of exactly |Up - Down| own shares on the under-held outcome (not "
                               "remainders); July (pmxt, same engine family): 500 / 300 / 50 + pairing sizes; June: 50/100/300.")
comp["exit"]["description"] = ("holds to resolution; completes pairs with maker pairing bids (11-14% of lot fills, priced at the market, "
                               "not off its own cost: pair cost median 0.81-0.91, < 1 in 61-72%) and small complement taker buys; merges "
                               "~65 s before the end. Window PnL split: locked pairs -$0.9k / +$33.3k vs residual +$5.7k / -$10.3k (STUDY / "
                               "VALIDATE aggregate): neither part is reliably the profit.")
comp["exit"]["confidence"] = 0.6
comp["timing"]["description"] = comp["timing"]["description"] + (" Iteration 10: the filled rungs agree with the report at the match, not "
                                                                   "at the taker's signing (M5); July engine: posts a median 69 ms after the "
                                                                   "previous trade, filled orders 1.0 s old.")

s["strategy_statement"] = (
    "[engine: VALIDATE-only] One engine family (timestamp-0 orders, per-wallet sequential salt counters reset by the daily ~01:00 UTC "
    "restart; 25-32 orders/s per wallet in July, 11-18 in October) runs three separately treasured wallets (weekly Monday sweeps). "
    "[selection: hypothesis] It quotes nearly every crypto Up/Down window of the modules it runs; BTC 5m/15m are switched off for hours, "
    "mostly Fri-Sun US-Eastern evenings, sometimes ad hoc (10-31 16:53); only the all-crypto universe meets the scope bar in every 6-h "
    "block. [timing: VALIDATE-only] It re-prices on each Chainlink report within ~0-150 ms of the RTDS relay's publish and after Binance "
    "moves; filled orders are fresh posts at the touch; its filled rungs agree with the report at the match, not at the taker's signing. "
    "[side: VALIDATE-only for the 500 ladder, hypothesis off-session] Its US-session 500-share rungs buy the outcome whose Chainlink "
    "edge over the Polymarket mid is positive (live 10-31 0.79 per fill, 0.965 where Chainlink and the market disagree; historical "
    "VALIDATE with a calibrated match clock 0.74 per fill and 0.97 in that region); its off-session 62/250 rungs (00-12 UTC) follow no "
    "public side rule (0.48-0.53), as an unskewed two-sided ladder would. Imbalance pairing bids (exactly |Up - Down| own shares) "
    "always sit on the under-held outcome. [price: exam-verified (block "
    "clock) / VALIDATE-only (match clock)] Fill price = last clean print minus a tick; pairing bids are priced at the market, not off its "
    "own cost. [size: VALIDATE-only] 500 x 2^k schedule rungs (100/12 only at 30-120 s left) plus imbalance-sized pairing bids. [exit: "
    "VALIDATE-only] Holds to resolution, completes pairs, merges ~65 s before the end. [economics: VALIDATE-only] BTC 5m earns 2-4% on "
    "volume; rebates and rewards are about a fifth of net PnL; the split between locked pairs and the directional residual changes sign "
    "between STUDY and VALIDATE, and the residual carries most of the window-to-window variance.")

s.setdefault("hypotheses", []).extend([
    {"id": "H10-A1-STABLE", "family": "X97", "description": "the Chainlink-favourite posture is a stable rule (historical region D >= 0.80 with calibrated proxies)",
     "validate_metrics": {"live_truth_D": g(liv, "truth_matchclock_book_mid", "acc_D_bought_cl_favourite"), "live_proxy_D": g(liv, "T_hat_cl__mid_a", "acc_D_bought_cl_favourite"),
                          "study_D": stDall.get("acc_D_bought_cl_favourite"), "validate_D": vaDall.get("acc_D_bought_cl_favourite"), "dev1031_0006_D": d06.get("acc_D_bought_cl_favourite")},
     "verdict": "all fills: rejected (0.66-0.68); by class: the 500 ladder replicates (VALIDATE 0.973), the 62/250 ladder does not follow Chainlink"},
    {"id": "H10-M1-PAIRPRICE", "family": "X92", "description": "the pairing bid is priced off own held-side cost (1 - VWAP - m)",
     "validate_metrics": {"within_tick_best_study": 0.047, "within_tick_best_validate": 0.048}, "verdict": "rejected (priced at the market)"},
    {"id": "H10-A4-LOCKED", "family": "X100", "description": "the profit is locked pairs + rebates, the residual ~0 or negative in every split",
     "validate_metrics": {"study_locked": g(m1, "STUDY", "window_split", "locked_sum"), "study_resid": g(m1, "STUDY", "window_split", "resid_sum"),
                          "validate_locked": g(m1, "VALIDATE_aggregate", "window_split", "locked_sum"), "validate_resid": g(m1, "VALIDATE_aggregate", "window_split", "resid_sum")},
     "verdict": "rejected (the split changes sign between STUDY and VALIDATE)"},
    {"id": "H10-R7-SIDE", "family": "X97", "description": "class-conditional public side rule (500 -> Chainlink posture; 62/250/100 -> best STUDY candidate)",
     "validate_metrics": {"r7_public": g(r7, "validate", "r7_public"), "frozen_all": g(r7, "validate", "frozen_all"), "gain": g(r7, "validate", "gain_r7_public_vs_frozen"),
                          "ci": g(r7, "validate", "gain_ci_2h_blocks"), "region_D_500": g(r7, "validate", "region_D_by_class", "500"), "region_D_62": g(r7, "validate", "region_D_by_class", "62")},
     "verdict": "fails the pre-registered confirmation; the 500-class posture replicates (region D 0.97), the off-session classes have no decoded side"},
    {"id": "H10-HVOL-500", "family": "X74/X97", "description": "slow sigma v3600 vs frozen 1.4 x v300 on the 500 ladder, real Chainlink, calibrated clock (pre-registered)",
     "validate_metrics": json.loads((R / "iter10_hvol500.json").read_text()) if (R / "iter10_hvol500.json").exists() else {},
     "verdict": "fails (VALIDATE 0.617 vs 0.742, gain -0.125 [-0.230, -0.034]); the frozen sigma stays"},
    {"id": "H10-M5-RACE", "family": "X96", "description": "off-posture fills are lost cancel races (posture at taker arrival)",
     "validate_metrics": {"match": 0.740, "arrival_best": 0.718}, "verdict": "rejected"},
    {"id": "H10-M2-PHASE", "family": "X93", "description": "per-phase fair (frozen / slow / TWAP lock-in) chosen on 12-15",
     "validate_metrics": {"test_15_18": g(m2, "test_15_18", "phase_rule"), "frozen": g(m2, "test_15_18", "frozen")}, "verdict": "not adopted (mostly the slow sigma; signature not met)"},
    {"id": "H10-I95-TWAP", "family": "X91", "description": "mo-money's 500 pass reads the TWAP-60 topic", "validate_metrics": i95, "verdict": "rejected"},
])
s.setdefault("live_lab", []).append({"what": "code10/famrec.py: dw_clob, examrec's reduction (schedule-size deltas within 3 ticks with server ms, touch queue every 200 ms, trades with tx hash, books within 3 ticks every 5 s) for ETH, SOL, XRP, BNB, DOGE, HYPE 5m (current + next) and 15m (current); disk cap 280 MB, < 100 MB memory", "start": 1793487581, "end": 1793664000})
s.setdefault("data_sources", []).extend([
    "iteration 10: pmxt archive r2v2.pmxt.dev hourly parquet of the unaggregated CLOB market channel (verified 07-20T13 200, 08-09T13 200, 10-20T13 404; range reads; 07-22T13 pilot reduced to .cache/re/directional-maker/pmxt/)",
    "iteration 10: polymarket.com/api/crypto/crypto-price historical Chainlink seconds for the lot fills (pre-registered match clock), BUILD fill seconds, switch-noise runs (detached fetch to 11-01 10:00 UTC)",
    "iteration 10: own exam recorder dx_clob as the quote-unit label source for BTC 5m/15m (recall 1.00 vs the raw recorder)",
])
s["status"] = "continue"
s["wall_reason"] = None
s["iterations"].append({"n": 10, "minutes": 100, "best_validate_score": 0.716,
                        "validate_definition": "2026-10-27..30 (lot second half, aggregate); live 10-31 12-18 (seen by the panels: descriptive)",
                        "paradigm": "stability and composition of the decision: a calibrated historical match clock with the real settlement stream (is the posture a stable rule?), two order types (posture rungs vs imbalance pairing bids) with the PnL split, the examinability of the quote unit, and a public archive of the unaggregated book",
                        "families": ["X97 A1 historical match clock + real Chainlink (calibrated on 10-31; lot; 10-31 00-06)", "X92 M1 pairing bid class/price/PnL",
                                     "X100 A4 locked pairs vs residual", "X96 M5 cancel race", "X93 M2 phase rule", "X88 I9-2 label examinability + famrec recorder",
                                     "X87 I9-1 pmxt version check", "X91 I9-5 TWAP-60 per wallet", "X90 I9-4 Chainlink rescue fetch", "X99 A3 pre-registration", "X89 I9-3 switch-noise pre-registration"],
                        "ended_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime())})
s["target_metrics"]["_notes"] = str(s["target_metrics"].get("_notes", "")) + " Iteration 10: unchanged (R6 kept; no decision changed; the side component fails its historical replication in the sigma-free region, A1)."
P.write_text(json.dumps(s, indent=1))
print("open:", sorted(k for k, v in cat.items() if v["status"] == "open"))
