"""iteration 18: bring state.json up to date (catalog X215-X227 and E-items, dimensions, indicators ledger, hypotheses,
live_lab, components, strategy statement, iteration entry). Reads the iteration-18 result files."""
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = HERE.parent
R = W / "results"


def rj(name):
    p = R / name
    return json.loads(p.read_text()) if p.exists() else None


def main():
    s = json.loads((W / "state.json").read_text(encoding="utf-8"))
    sv = rj("iter18_sched_vol.json")
    dec = rj("iter18_sched_vol_decomp.json")
    idl = rj("iter18_ident_slope.json")
    kvp = rj("iter18_k_vs_profile.json")
    ev = rj("iter18_event_law.json")
    fn = rj("iter18_fn_by_type.json")
    eq = rj("iter18_equity_open.json")
    pnl = rj("iter18_pnl_by_ratio.json")
    cen = rj("iter18_center_sched.json")
    ne = rj("iter18_nonevent.json")
    off = rj("iter18_offrun_shocks.json")
    c = s["catalog"]
    src_m, src_a, src_i = "panel iter17 mechanics", "panel iter17 assumptions", "panel iter17 information"
    c["X215"] = {"status": "tried", "source": src_m + " P1", "title": "Scheduled forward-looking volatility in the fair; R8c as its symptom",
                 "evidence": (f"code18/sched_vol.py (T1, pre-registered 12:37 UTC): profile posture chosen on BUILD (utc_N28, sigma = 1.0 x max(v300, P)) "
                              f"BUILD {sv['chosen']['build_S1']} vs R8c {sv['build_R8c']}; lot STUDY S1 {sv['study']['S1']} / S2 {sv['study']['S2']} vs R8c {sv['study']['R8c']}; "
                              f"VALIDATE S1 {sv['validate']['S1']} / S2 {sv['validate']['S2']} vs R8c {sv['validate']['R8c']}: not adopted; open window S1 {sv['study']['open']['S1']} STUDY / {sv['validate']['open']['S1']} VALIDATE (signature fails). "
                              f"Decomposition: at fixed k the profile adds +0.016 (k1.4) on VALIDATE, the k change dominates; the open window needs >= 2 x max(v300, P). "
                              f"T6 code18/k_vs_profile.py: Spearman(best k, P/v300) over 18 days {kvp['spearman']} (p {round(kvp['p'], 3)}): the k-cycle is not the profile. "
                              f"T2 identification (code18/ident_slope.py): cluster slope {idl['same_windows']['cluster']['slope']} (p {round(idl['same_windows']['cluster']['p_one_sided_pos'], 4)}) vs other makers {idl['same_windows']['market_all_rows']['slope']} in the same windows: a cluster-only gradient.")}
    c["X216"] = {"status": "open", "source": src_m + " P2", "title": "A fill-free module state from the salt counter's rate",
                 "evidence": ("not run in iteration 18. Existing evidence (results/iter9_m4_salt.json): across the 10-31 16:53:54 BTC 5m switch-off bosona's counter slowed only from 12.1 to 11.0 orders/s "
                              "(8 / 28 orders), less than the 3-4 orders/s BTC 5m quantum the panel estimates; almach and mo-money were restarted 12-13 min later, so their post slopes are unusable. "
                              "A dense per-minute calldata calibration is still needed.")}
    c["X217"] = {"status": "open", "source": src_m + " P3", "title": "Name the consumed feed by its reaction-lag floor, venue by venue",
                 "evidence": "not run as specified; partial: T3 (code18/event_law.py) shows the post side follows Binance USD-M mid moves within 50-450 ms and the public Chainlink publish within (0, 150] ms (no earlier reaction); a per-venue lag histogram at 5 ms is still to do."}
    c["X218"] = {"status": "open", "source": src_m + " P4 (+ information I17-4 live part)", "title": "The 11-02 NYSE open live at full depth: which clock, anticipatory or reactive",
                 "evidence": "predictions (a)-(d) pre-registered in NOTES.md 12:37 UTC 11-01; recorder code18/open_rec.py (dm_* full depth through tools/live.py Writer) armed for 11-02 13:15-13:50 and 14:15-14:50 UTC (development block 12-18), own disk <= 60 MB; first launch (pid 10460) died on a status-path bug, relaunched 13:08 UTC as pid 27416 (status file confirms it is waiting). Result after 11-02 14:50 UTC."}
    c["X219"] = {"status": "tried", "source": src_a + " P1 (strong form of X215)", "title": "One estimator change on 10-01 identified by the contrast with May-September and a market control",
                 "evidence": (f"panel's history check (slope flip June-Aug <= 0, Oct +0.157); T2 market control on BUILD maker-row tapes: cluster {idl['same_windows']['cluster']['slope']} (s.e. {idl['same_windows']['cluster']['se']}) vs other makers "
                              f"{idl['same_windows']['market_all_rows']['slope']} -> reading met (the gradient is the cluster's); the rule form (T1) and the k link (T6) fail, so the estimator is identified as a gradient, not as a decoded sigma.")}
    c["X220"] = {"status": "tried", "source": src_i + " I17-1", "title": "Report innovation as an engine input at public-relay timing: event law E (and E2)",
                 "evidence": (f"code18/event_law.py: futures-only innovation frozen on 11-01 07-08; untouched 11-01 09:15-12:00: E {ev['confirm_1101_0915_1200']['all']['law_E'][0]}, E2 {ev['confirm_1101_0915_1200']['all']['law_E2'][0]} vs posture {ev['confirm_1101_0915_1200']['all']['posture'][0]} "
                              f"(n {ev['confirm_1101_0915_1200']['all']['posture'][1]}); 10-31 17:29-18:00: E {ev['confirm_1031_1729_1800']['all']['law_E'][0]}, E2 {ev['confirm_1031_1729_1800']['all']['law_E2'][0]} vs {ev['confirm_1031_1729_1800']['all']['posture'][0]}; "
                              f"(0,150] agreement {ev['confirm_1101_0915_1200']['event_study_u_ge_1']['(0,150]']['agree']} / {ev['confirm_1031_1729_1800']['event_study_u_ge_1']['(0,150]']['agree']} vs (-300,0] {ev['confirm_1101_0915_1200']['event_study_u_ge_1']['(-300,0]']['agree']} / {ev['confirm_1031_1729_1800']['event_study_u_ge_1']['(-300,0]']['agree']}: signature met on both held-out blocks (both are live-split BUILD days; live VALIDATE 11-02/03 pending, T12). "
                              "E2 added to evaluate() (quote_unit_side.law_E2, code14/qu_dx.py): 11-01 09:15-10:15 exam-path smoke 0.684 vs posture 0.536.")}
    dc = rj("iter18_display_crowd.json")
    c["X221"] = {"status": "open", "source": src_i + " I17-2", "title": "The display the paying takers see (strike crossings, results strip, countdown) as the counterparty's information",
                 "evidence": (f"light form (code18/display_crowd.py, BUILD 10-09..15, Binance stand-in display): {dc['crowd_buys']} non-HFT crowd buys; 0-10 s after a displayed crossing displayed-winner share "
                              f"{dc['0-10']['displayed_winner_share']} vs favourite {dc['0-10']['favourite_share']} (diff CI95 {dc['0-10']['diff_ci95']}): the crowd follows the price, not the display. "
                              "Open for the demand model and presence step with the real Chainlink display (lot endpoint seconds, live dy_rtds).")}
    offev = "not run (GDELT fetch unfinished)"
    if off:
        offev = (f"code18/offrun_shocks.py (T9, hourly; GDELT DOC returns hourly bins for 7-day ranges): {off['off_runs']} off-runs 08-02..10-22; burst share before starts vs placebo: "
                 f"bitcoin {off['bitcoin']['share_obs']} vs {off['bitcoin']['share_placebo']} (p {off['bitcoin']['binom_p']}), macro {off['macro']['share_obs']} vs {off['macro']['share_placebo']} (p {off['macro']['binom_p']}), "
                 f"vol jumps {off['vol']['share_obs']} vs {off['vol']['share_placebo']} (p {off['vol']['binom_p']}); readings met: {[k for k in ('bitcoin', 'macro', 'vol') if off[k]['reading_met']]}. "
                 "The conditional logit over 15-min slots was not run.")
    offev = ("not informative: GDELT throttled the fetch (HTTP 429; 618 of ~1,970 hours for 'bitcoin', 406 for the macro query); 7 off-runs by the pre-registered definition; "
             "vol jumps before starts 0.14 vs 0.21 placebo (p 0.82); bitcoin bursts 0 of 1 covered start. Needs the full GDELT series at a slower rate or the live RSS recording; the 15-min conditional logit was not run.")
    c["X222"] = {"status": "open", "source": src_i + " I17-3", "title": "Intraday information shocks against the module switches (selection)", "evidence": offev}
    c["X223"] = {"status": "tried", "source": src_i + " I17-4 (historical part)", "title": "What the open module reads at 09:30 New York: the equity open or BTC's move",
                 "evidence": (f"code18/yahoo_1m.py fetched 1-m bars of IBIT/QQQ/SPY/COIN/MSTR 10-02 13:30..10-30 (10-01 refused, HTTP 422, beyond the ~30-day window); code18/equity_open.py: 17 open windows (dev + STUDY): "
                              f"cheap share agree {eq['dev_study']['cheap_agree']} vs diverge {eq['dev_study']['cheap_diverge']} (MW p {round(eq['dev_study']['mannwhitney_p'], 3)}); Spearman |BTC move| {eq['dev_study']['spearman_absbtc_cheap'][0]}: a fixed fade, reading not met. Live part = X218.")}
    c["X224"] = {"status": "open", "source": src_i + " I17-5", "title": "Record the Perps index over its websocket at 200 ms",
                 "evidence": "wss://ws.perpetuals.polymarket.com/v1/ws answers but returns {status: err, error: invalid request} to three common subscribe formats (13:10 UTC 11-01); the subscription message is undocumented; the 1-Hz REST recorder (X214, dp_perps) keeps running to 11-03 00:00."}
    c["X225"] = {"status": "tried", "source": src_a + " P2", "title": "The PnL by forward/trailing volatility ratio before and after 10-01",
                 "evidence": (f"code18/pnl_by_ratio.py: exact outcomes from the cluster's REDEEM rows ({pnl['outcome_source_windows'].get('redeem')} windows; 100% agreement with Gamma on {pnl['redeem_vs_gamma']['windows']}); "
                              f"October return per $ by R quintile q0..q4 {[pnl['table']['10'][f'q{q}']['all']['ret'] for q in range(5)]}; cheap top - bottom CI90 {pnl['table']['10']['oct_cheap_top_minus_bottom_ci90']}: the signature fails with the opposite sign (the top-ratio quintile loses). The strict replay with the scheduled posture was not run (T1 already rejects the posture).")}
    c["X226"] = {"status": "tried", "source": src_a + " P4", "title": "Split the presence label by order type before attributing the misses to taker arrival",
                 "evidence": (f"code18/fn_by_type.py (VALIDATE aggregate): FN share all {fn['fn_share_all']}; cells with a fresh main-ladder fill {fn['by_cell_class']['has_main_fresh']['fn_share']} "
                              f"({fn['by_cell_class']['has_main_fresh']['share_of_all_fn']} of FN cells); own-state-only cells {fn['by_cell_class']['own_state_only']['fn_share']} ({fn['by_cell_class']['own_state_only']['share_of_all_fn']} of FN): signature not met; the taker-arrival account stands on the main ladder.")}
    c["X227"] = {"status": "tried", "source": src_a + " P3", "title": "The 11-01 regime as the scheduled-vol excess: centre re-fit with the scheduled fair",
                 "evidence": (f"code18/center_sched.py: with F_sched g {cen['1031_1729_1800']['F_sched']['g']} / {cen['1101_0700_0915']['F_sched']['g']}, w {cen['1031_1729_1800']['F_sched']['w']} / {cen['1101_0700_0915']['F_sched']['w']}, "
                              f"15-min w sd {cen['1101_0700_0915']['w_15min_sd']}: reading not met; the profile binds in only {cen['1101_0700_0915']['share_profile_binds']} of the 11-01 units.")}
    c["E3"]["evidence"] = c["E3"].get("evidence", "") + (" | Iteration 18: the report innovation (u = report change minus futures nowcast) as an event: (0,150] ms agreement 0.73 (freeze), 0.80 / 0.86 on two held-out live BUILD blocks, no pre-publish reaction; "
                                                         "event law E2 pre-registered for the live VALIDATE blocks (T12); the BH screen with the innovation event and its VALIDATE confirmation are pending.")
    c["E4"] = {**c.get("E4", {}), "status": "tried", "evidence": (c.get("E4", {}).get("evidence", "") + " | Iteration 18: discrepancy indicator 'Chainlink report minus the futures nowcast' (u) built and confirmed as a side input at public timing (X220); "
                                                                   "composite 'scheduled vol profile / trailing vol' (R) built: a cluster-only cheap-share gradient (T2) but no posture gain (T1) and the top-R quintile loses money (T8).")}
    c["E5"]["evidence"] = c["E5"].get("evidence", "") + (f" | Iteration 18: equity-open information (X223) no effect at n 17; intraday GDELT vs off-runs: {offev[:200]}. Live RSS recording not started: stays open.")
    c["E6"]["evidence"] = c["E6"].get("evidence", "") + " | Iteration 18: no latent fit (the k drift remains the candidate hidden state; T6 shows it is not the vol profile)."
    c["X214"]["evidence"] = c["X214"].get("evidence", "") + " | Iteration 18: still recording (status updated 12:34 UTC 11-01); the race needs the 11-01 18-24 and 11-02 blocks."
    # dimensions
    d = s["dimensions"]
    d["scheduled_vol_profile"] = {"family": "operator / related markets", "status": "have", "source": "Binance BTCUSDT 1-s klines archives (data.binance.vision, checksum), 05-15..10-30 reduced to per-slot rv (it18/slot_rv.parquet)",
                                  "resolution": "5-min UTC slot x day", "publication_latency": "point in time (previous 28 days)", "best_indicator": "utc_N28 profile / trailing 300-s vol (R)",
                                  "min_detectable_share": None, "verdict": "drives",
                                  "note": "cluster-only cheap-share gradient in October (slope +0.229, p 0.002; other makers -0.013); not a usable sigma for the posture (T1 VALIDATE -0.010); top-R quintile loses money (T8)."}
    d["pm_legacy_rtds"]["verdict"] = "drives"
    d["pm_legacy_rtds"]["note"] = (d["pm_legacy_rtds"].get("note", "") + " | Iteration 18: the report-specific innovation re-sides the at-touch posts within (0, 150] ms of the public publish "
                                   "(0.80 / 0.86 agreement on two held-out blocks, n 45 / 132; 0.40-0.53 before the publish).")
    d["chainlink_data_streams_low_latency"]["note"] = (d["chainlink_data_streams_low_latency"].get("note", "") + " | Iteration 18: no pre-publish reaction on a third block (11-01 09:15-12:00: (-300, 0] ms agreement 0.53, n 64; 10-31 17:29-18:00 0.40, n 45); "
                                                       "the trace a direct Data Streams subscriber would leave (agreement rising before P_i) is absent.")
    d["us_equity_market_open"]["note"] = (d["us_equity_market_open"].get("note", "") + " | Iteration 18: the open-window cheap lean does not depend on the equity first-minute return or its agreement with BTC (0.983 vs 0.988, n 17): a calendar fade, not equity information (X223).")
    d["news_wires_rss"]["note"] = (d["news_wires_rss"].get("note", "") + f" | Iteration 18 (GDELT hourly vs off-run starts, X222): {offev[:240]}")
    d["binance_usdm_futures"]["note"] = (d["binance_usdm_futures"].get("note", "") + " | Iteration 18: a mid move >= $2 over [t-500, t-50] ms sets the post side 0.86-0.90 on held-out blocks (law E2 branch 2); moves >= $1 over 1 s 0.70 (T11).")
    # indicators ledger
    I = s["indicators"]
    I += [
        {"name": "T1_profile_posture", "dimension": "scheduled_vol_profile", "definition": "sigma = k x max(v300, P_utc_N28(slot)) in the Chainlink / Binance posture; R8c branch removed (S1) / kept (S2)", "event": "level",
         "period": "VALIDATE", "result": {"build": sv["chosen"], "study": {k: sv["study"][k] for k in ("R8c", "S1", "S2")}, "validate": {k: sv["validate"][k] for k in ("R8c", "S1", "S2")}}, "verdict": "rejected (VALIDATE -0.010)"},
        {"name": "T2_profile_slope_market_control", "dimension": "scheduled_vol_profile", "definition": "window cheap share on log P (controls |r5|, trailing 1-h), weekday BTC 5m, cluster vs other makers", "event": "level (window)",
         "period": "BUILD", "result": idl["same_windows"], "verdict": "cluster-only gradient (reading met)"},
        {"name": "T6_kcycle_vs_profile", "dimension": "scheduled_vol_profile", "definition": "Spearman(best k per day, median P/v300)", "event": "level (day)", "period": "BUILD+STUDY", "result": {"rho": kvp["spearman"], "p": kvp["p"]}, "verdict": "no_effect"},
        {"name": "T3_report_innovation_publish", "dimension": "pm_legacy_rtds", "definition": "u = dCL - futures-only prediction (beta frozen 11-01 07-08); posts in (0,150] ms after a publish with |u| >= 1", "event": "publish (exact clock)",
         "period": "BUILD (held-out live blocks)", "result": {b: ev[b]["event_study_u_ge_1"] for b in ("confirm_1101_0915_1200", "confirm_1031_1729_1800")}, "verdict": "drives (held-out BUILD; live VALIDATE pending)"},
        {"name": "T3_event_law_E2", "dimension": "binance_usdm_futures + pm_legacy_rtds", "definition": "publish u within 150 ms -> sign(u); else futures move >= $2 over 0.5 s -> direction; else posture", "event": "compound",
         "period": "BUILD (held-out live blocks)", "result": {b: ev[b]["all"] for b in ("confirm_1101_0915_1200", "confirm_1031_1729_1800")}, "verdict": "drives (+0.09 to +0.12 over the posture)"},
        {"name": "T7_equity_open_agreement", "dimension": "us_equity_market_open", "definition": "sign(SPY+QQQ first-minute return) == sign(BTC first-minute move) at 13:30 UTC", "event": "first occurrence (open)",
         "period": "BUILD+STUDY", "result": eq["dev_study"], "verdict": "no_effect (n 17; only a >= 0.3 difference detectable)"},
        {"name": "T8_pnl_by_R", "dimension": "scheduled_vol_profile", "definition": "return per $ by month x R quintile x cheap/fav (exact REDEEM outcomes)", "event": "level (window)", "period": "BUILD+history (lot pooled)",
         "result": {"oct_by_q": [pnl["table"]["10"][f"q{q}"]["all"]["ret"] for q in range(5)], "oct_ci90_cheap_top_minus_bottom": pnl["table"]["10"]["oct_cheap_top_minus_bottom_ci90"]}, "verdict": "the top-R quintile loses (signature fails)"},
        {"name": "T10_center_sched", "dimension": "scheduled_vol_profile", "definition": "centre regression with F_sched", "event": "level", "period": "BUILD (live)", "result": {k: cen[k]["F_sched"] for k in ("1031_1729_1800", "1101_0700_0915")}, "verdict": "no_effect"},
        {"name": "T11_nonevent_posts", "dimension": "binance_usdm_futures", "definition": "candidates for the posts with no E2 event", "event": "various", "period": "BUILD (live, exploratory)",
         "result": {b: {k: ne[b][k] for k in ("posture", "opposite_last_hit", "fut_move_1000ms_ge1.0_else_posture", "last_publish_u_within_1s")} for b in ne}, "verdict": "exploratory; E3 pre-registered (T12)"},
    ]
    if off:
        I.append({"name": "T9_offrun_news_vol", "dimension": "news_wires_rss", "definition": "GDELT hourly burst (>= q95 of previous 168 h) / slot-rv jump in the hour before BTC 5m off-run starts vs hour-of-week placebos",
                  "event": "burst", "period": "BUILD (development 08-02..10-22)", "result": {k: off[k] for k in ("bitcoin", "macro", "vol")}, "verdict": "see reading_met per indicator"})
    s["hypotheses"] += [
        {"id": "H18-SCHED-VOL", "family": "side (scheduled volatility)", "description": "sigma = 1.0 x max(v300, P) (BUILD-chosen), no calendar branch", "validate_metrics": {"validate_S1": sv["validate"]["S1"], "validate_S2": sv["validate"]["S2"], "validate_r8c": sv["validate"]["R8c"]}, "verdict": "rejected"},
        {"id": "H18-EVENT-LAW-E2", "family": "side (quote unit, live)", "description": "publish innovation within 150 ms, else futures 0.5-s move >= $2, else posture", "validate_metrics": {"heldout_1101_0915_1200": ev["confirm_1101_0915_1200"]["all"], "heldout_1031_1729_1800": ev["confirm_1031_1729_1800"]["all"]}, "verdict": "confirmed on held-out BUILD blocks; reported in evaluate(); live VALIDATE pending"},
        {"id": "H18-FN-TYPES", "family": "presence (unit purity)", "description": "presence FN by order type", "validate_metrics": fn["reading"], "verdict": "taker arrival stands (own-state types 34% of FN)"},
        {"id": "H18-PNL-R", "family": "economics", "description": "money where scheduled and trailing vol disagree", "validate_metrics": {"oct_by_q": [pnl["table"]["10"][f"q{q}"]["all"]["ret"] for q in range(5)]}, "verdict": "rejected (top quintile loses)"},
    ]
    s["live_lab"].append({"what": "code18/open_rec.py (X218): code5/rawrec.py full-depth dm_* feeds (BTC 5m current+next, 15m current, reference venues) through tools/live.py Writer, 11-02 13:15-13:50 and 14:15-14:50 UTC only (development block 12-18), own disk <= 60 MB (dm_* cap 318.9 MB); pid 27416 (Start-Process hidden; the first launch pid 10460 died at start on a status-path bug)",
                          "start": 1793625300, "end": 1793631000})
    s["data_sources"] = s.get("data_sources", []) + ["Binance BTCUSDT 1s klines daily archives 05-15..10-07 (data.binance.vision, SHA-256 checked, reduced to it18/slot_rv.parquet)",
                                                     "Yahoo chart API 1-m bars IBIT/QQQ/SPY/COIN/MSTR 10-02..10-30 (it18/yahoo_1m*.parquet)",
                                                     "GDELT DOC 2.0 timelinevolraw hourly 08-02..10-22 ('bitcoin', '(crypto OR fed OR cpi)') (it18/gdelt_hourly.parquet)",
                                                     "cluster REDEEM rows as exact BTC 5m outcomes (100% agreement with Gamma on 4,387 windows)"]
    comp = s["components"]
    comp["timing"]["description"] = ("Iteration 18: two event inputs re-side the at-touch posts, the report-specific Chainlink innovation within (0, 150] ms of the public publish and a Binance futures mid move >= $2 over 0.5 s "
                                     "(law E2 0.642 vs posture 0.520 on the held-out 11-01 09:15-12:00 block; 0.804 vs 0.713 on 10-31 17:29-18:00); no reaction before the publish. | " + comp["timing"]["description"])
    comp["timing"]["tag"] = "VALIDATE-only"
    comp["side"]["description"] = ("Iteration 18: R8c unchanged; the October cheap lean is a cluster-only gradient over the time-of-day vol profile (not a usable sigma, not where the money is); the open window is a fixed fade. | "
                                   + comp["side"]["description"])
    comp["selection"]["description"] = ("Iteration 18: presence FN on VALIDATE are 65% fresh main-ladder cells (taker arrival) and 34% own-state order types; "
                                        + (f"off-runs vs GDELT / vol bursts: {offev[:160]} | " if off else "| ") + comp["selection"]["description"])
    s["strategy_statement"] = ("[iteration 18] " + "Timing [VALIDATE-only]: the BTC ladders are re-sided by two public events, the report-specific part of each public Chainlink publish (within 150 ms, never before) "
                               "and Binance USD-M futures moves (>= $2 in 0.5 s), else the Chainlink posture; three quarters of the clean-regime posts follow neither. Side [VALIDATE-only rule R8c; hypothesis for the mechanism]: "
                               "decided windows -> cheaper token, the NYSE-open window -> cheaper token (a fixed fade, clock to be read on 11-02), else the Chainlink posture; the October cheap lean grows with the scheduled "
                               "time-of-day vol for the cluster only, and that lean loses money. " + s["strategy_statement"])
    it = {"n": 18, "minutes": None, "best_validate_score": 0.716, "validate_definition": "2026-10-27..30 (lot second half, aggregate)",
          "paradigm": "the scheduled-volatility hypothesis tested as an input (posture sigma), an identification (market control), a k link, an economic decomposition (exact REDEEM outcomes) and a centre re-fit; plus the report innovation as an event input confirmed on held-out live blocks and added to evaluate()",
          "families": ["X215 profile posture (T1)", "X219 slope identification with market control (T2)", "X215 step 4 k-cycle vs profile (T6)", "X220 event law E / E2 (T3, T3b)", "X226 presence FN by order type (T4)",
                       "X218 11-02 open recorder armed with predictions (T5)", "X223 equity open (T7)", "X225 PnL by forward/trailing ratio (T8)", "X222 GDELT / vol bursts vs off-runs (T9)", "X227 centre with F_sched (T10)",
                       "T11 non-event posts; E3 pre-registered (T12)", "X224 Perps websocket probe"]}
    s["iterations"].append(it)
    s["status"] = "continue"
    s["target_metrics"]["_notes"] = s["target_metrics"].get("_notes", "") + " Iteration 18: unchanged (R8c kept; no frozen decision changed). Reported beside it: law E2 for the live quote side (held-out 11-01 09:15-12:00 0.642 vs posture 0.520)."
    s["updated"] = int(time.time())
    (W / "state.json").write_text(json.dumps(s, indent=1, default=str), encoding="utf-8")
    print("state updated; open catalog:", [k for k, v in c.items() if v.get("status") == "open"])


if __name__ == "__main__":
    main()
