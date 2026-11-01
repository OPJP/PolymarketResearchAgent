"""Update state.json for iteration 15 (catalog X163-X176 from the iter14 panels, statuses, hypotheses, components,
strategy statement, iteration entry). Run once at the end of the iteration."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent / "state.json"
s = json.loads(P.read_text(encoding="utf-8"))
R = HERE.parent / "results"


def rj(name):
    f = R / name
    return json.loads(f.read_text()) if f.exists() else {}


pub = rj("iter15_nb_public.json")
pub_line = ""
if pub.get("by_fold"):
    bf = {r["fold"]: r for r in pub["by_fold"]}
    def g(f, k):
        return bf.get(f, {}).get(k)
    bp = {(r["fold"], r["phase"]): r for r in pub.get("by_fold_phase", [])}
    pub_line = (f" | T1d public price (last clean taker print <= T-2, dailies excluded): opening fills posture k0.7 VALIDATE "
                f"{bp.get(('VALIDATE', 'open<20s'), {}).get('post_pub_k0.7')} (n {bp.get(('VALIDATE', 'open<20s'), {}).get('n')}; market "
                f"{bp.get(('VALIDATE', 'open<20s'), {}).get('mktfav_pub')}), STUDY {bp.get(('STUDY', 'open<20s'), {}).get('post_pub_k0.7')}; later "
                f"fills posture k0.7 VALIDATE {bp.get(('VALIDATE', 'later'), {}).get('post_pub_k0.7')} vs market {bp.get(('VALIDATE', 'later'), {}).get('mktfav_pub')}"
                f"; all: posture k1.0 "
                f"STUDY {g('STUDY', 'post_pub_k1.0')} / VALIDATE {g('VALIDATE', 'post_pub_k1.0')} / after T0 {g('dev_after_T0', 'post_pub_k1.0')}; "
                f"market favourite from the same print {g('STUDY', 'mktfav_pub')} / {g('VALIDATE', 'mktfav_pub')} / {g('dev_after_T0', 'mktfav_pub')}; "
                f"itm {g('STUDY', 'itm')} / {g('VALIDATE', 'itm')} / {g('dev_after_T0', 'itm')}")

cat = s["catalog"]
new = {
    "X163": ("open", "panel iter14 information I14-1", "presence and side on the relay's publish clock (one cell per Chainlink publish)",
             "iteration 15 step (no fitting, code15/pub_unit.py): 10-31 17:29-18:00 (BTC 15m, 1,774 publishes, 7,010 cells, 119 non-extreme "
             "500 posts in [P_i, P_i+300 ms)): report-i posture level AUC 0.794, WHICH 0.866; no-fit activity 0.53 / 0.52; placebo before "
             "the publish 0.625 / 0.652; posture CHANGE i-1 -> i 0.665 / 0.706 after vs 0.429 / 0.424 before (trigger signature). 11-01 "
             "07:00-07:55: 0.675 / 0.717 (n 60), placebo 0.609 / 0.633. Fitted (code15/pub_fit.py, 11-01 07:00-08:07, 138 pure 500 posts, fit first 60% / test rest): activity 0.748, activity + report-i posture 0.730, gain -0.018 [-0.055, +0.028] (placebo -0.045). Open: the fitted test with an activity model of the same class "
             "(fit 07:00-09:30, test 09:30-12:00 of 11-01) and the fill label F, once the block is complete."),
    "X164": ("tried", "panel iter14 information I14-2", "recording-free settlement reference per family for the weekend blocks",
             "code15/nb_side.py (T1): in the money under the family's Binance reference (hourly/daily: the settlement source; Chainlink "
             "TWAP families: Binance TWAP-60 stand-in strike, same basis), no fitting. Idle STUDY days 10-24 / 10-25: 0.775 / 0.767 vs "
             "market favourite 0.737 / 0.710 and cheaper token 0.263 / 0.290 (>= cheaper + 0.05: yes; >= 0.75: yes on these two days); "
             "VALIDATE aggregate 0.576 (market 0.539); after T0 0.543. Not run: the crypto-price endpoint variant for the Chainlink "
             "families and the hourly natural experiment (Chainlink vs Binance disagreement)." + pub_line),
    "X165": ("open", "panel iter14 information I14-3", "competition at the cluster's own prices around the weekend switch-offs",
             "not run in iteration 15 (needs maker rows of ~2,000 windows around 32 events)."),
    "X166": ("tried", "panel iter14 information I14-4", "the settlement average's variance law as the time-left profile",
             "code15/qu_law.py: non-extreme 500 posts 10-31 14-18, no fitting. Safe lag: law 0.779 = k1.0 0.779 (n 4,887); last 120 s "
             "law 0.749 (fit 0.813 / test 0.705) vs k1.0 0.731, band 0.761; exact publish clock 17:29-18:00: law 0.835 vs k1.0 0.866 "
             "(n 447). Signature (last 120 s >= 0.83 on both halves) not met: rejected."),
    "X167": ("tried", "panel iter14 information I14-5", "clock integrity: server stamps everywhere, clk offsets, resync",
             "dy_rtds clk offsets 0.677 s (06:03) -> 0.898 s (07:13 UTC 11-01), +0.031 s / 10 min; w32tm not synchronized since 02:29 "
             "UTC. Code guard in code/final_rule.py (_iter_live_x, _iter_live_xq: server stamp s must be development; no laptop-t "
             "fallback for match ms and books) and code/cl_source.py (value stamp / publish ms must be development). The user must "
             "resync Windows time before 11-01 12:00 UTC (agents may not change system settings)."),
    "X168": ("tried", "panel iter14 mechanics P1", "per-family configured size vector (module table)",
             "activity fill sizes (code15/nb_side.py size_table): per-family modes identical in the three wallets (BTC hourly 38 / 300, "
             "BTC 4h 400, ETH 15m 30, SOL 15m 30, ETH 5m 50 / 150, SOL 5m 50 / 100, XRP 5m 10 / 50, BNB 5m 10, DOGE 5m 10 / 40, "
             "dailies 50, BTC daily 200); calldata 11-01 06:00-07:40 (code15/today_sizes.py): BTC 5m 500 / 100, ETH 5m 150, ETH 15m 30, "
             "dailies 50, XRP 5m 50. Universe = every crypto family (reported in evaluate() as r9_nonbtc_module). Not run: the BUILD "
             "calldata fit of base_f x m (>= 85% exact)."),
    "X169": ("open", "panel iter14 mechanics P2", "publish-anchored resting state 250 ms after each publish",
             "label A (posts in (p, p + 300 ms]) scored without fitting in code15/pub_unit.py (see X163); label B (resting state from "
             "exact adds and removes) and the fitted activity baseline not built."),
    "X170": ("tried", "panel iter14 mechanics P3", "label purity of the quote unit",
             "code15/qu_law.py class split (10-31 14-18; purity from the panel's all-match calldata of 15:20-15:40: exact 500s 88% the "
             "cluster's, 1000/250 0%): posture k1.0 on 500 at non-extreme bids 0.779 (safe lag) / 0.866 (exact publish clock, n 447), "
             "500 extreme 0.57-0.69, 1000 0.70-0.87, 250 0.49-0.61, 62 0.49-0.53. Pure non-extreme 500s >= 0.85 on the exact clock: met "
             "on 30 min; on 11-01 07:00-07:50 0.624 (n 218; X160 replication fails there)."),
    "X171": ("open", "panel iter14 mechanics P4", "FIFO replay with the recorded L2 queue (oracle vs public quote)", "not run in iteration 15."),
    "X172": ("open", "panel iter14 mechanics P5", "mo-money's deficit as a slower cancel path", "not run in iteration 15."),
    "X173": ("tried", "panel iter14 assumptions P1", "the non-BTC module as an opening strike-gap quoter with fixed per-family sizes",
             "code15/nb_side.py (pre-registered, no fitting): opening fills (< 20 s) in the money 0.814 BUILD (n 2,097; market favourite "
             "0.622), STUDY 0.72 / 0.90 / 0.86 / 0.84, VALIDATE 0.778 (n 535; 0.485); later fills 0.598 / 0.64-0.75 / 0.552 (= the "
             "market favourite); alt 5m opening 0.848 / 0.77-0.90 / 0.791. Signature (>= 0.85 every BUILD week and STUDY) not met; "
             "opening fills are 13% of non-BTC fills. PnL (code15/nb_pnl.py): in-the-money opening fills lose (-2.4% BUILD, -8.7% "
             "VALIDATE); the profit is in the later 4h / hourly fills (+7.5-10% per $). Fill-price posture k1.0 (description): 0.667 / "
             "0.753 / 0.676." + pub_line),
    "X174": ("tried", "panel iter14 assumptions P2", "examiner-split emulation on weekend mock lots",
             "code15/mock_halves.py (light: scope per half from activity): R8 universe trades / $ earlier vs later half: 10-10/11 "
             "0.86/0.92 vs 0.83/0.89; 10-17/18 0.87/0.92 vs 0.41/0.61; 10-24/25 0.39/0.38 vs 0.28/0.32: R8 fails scope in a half of "
             "two of three mock lots; only the all-family universe holds. Not run: R8's evaluate() per half on the mock lots."),
    "X175": ("tried", "panel iter14 assumptions P3", "settlement-source fair per family for hourly, daily and 4h",
             "code15/nb_side.py / nb_posture.py: hourly later fills in the money 0.692 BUILD / 0.76-0.78 STUDY / 0.578 VALIDATE (market "
             "0.643 / 0.74-0.78 / 0.537); 4h 0.668 / 0.71-0.82 / 0.496; daily 0.453 / 0.35-0.71 / 0.498. Fill-price posture k1.0: "
             "4h 0.822 / 0.833 / 0.689, daily 0.790 / 0.803 / 0.786, hourly 0.659 / 0.656 / 0.630. Signature (fair favourite >= 0.85 "
             "per market, cheaper <= 0.25) not met; the strict per-market replay not run."),
    "X176": ("tried", "panel iter14 assumptions P4", "print-level selection on the opening unit of the non-BTC families",
             "code15/sel_open.py (no fitting): 167,734 taker prints of the alt 5m/15m windows the cluster traded (STUDY, VALIDATE, after T0), "
             "3,587 cluster-fill prints (2.1%). Frozen score (maker-BUY outcome itm + opening + small size) AUC 0.621 (recall@k 0.12, lift 5.6); "
             "itm alone 0.615; activity-only score (opening + taker size rank) 0.730; opening prints 0.605 / 0.632 / 0.617; VALIDATE 0.581 / "
             "0.584 / 0.714. Signature (opening >= 0.85; all >= 0.80 with recall >= 50% at lift >= 3) not met: rejected (the taker's size "
             "selects the cluster's fills)."),
}
for k, (st, src, title, ev) in new.items():
    cat[k] = {"status": st, "source": src, "title": title, "evidence": ev}
cat["X172"]["evidence"] = ("crude form run (code15/cancel_lag.py): mo-money class (ii) posture 0.617 at the fill, 0.669 at fill - 312 ms, "
                           "0.752 at fill - 1 s (bosona 0.78-0.80, almach 0.84-0.87 at 0-500 ms): its resting rungs carry the posture of ~1 s "
                           "earlier; open: the proper form with the mid series at fill - L and the cancel-latency measurement on 11-01.")
cat["X160"]["evidence"] += (" | iteration 15: 11-01 07:00-07:50 (12 windows, 279 non-extreme 500 posts; cluster BTC 5m orders are 500s per calldata): "
                            "exact publish clock k1.0 0.624 (n 218), safe lag 0.599, best k x reference 0.697 (futures minus basis, k1.4), "
                            "cheaper 0.663: the 10-31 quote side does not replicate on the first 50 minutes; score the full block 07-12 next.")
cat["X161"].update({"status": "tried", "evidence": cat["X161"]["evidence"] + (
    " | iteration 15: built as a reported block (code/r9_nonbtc.py, evaluate() 'r9_nonbtc_module'); the cheaper-token fallback is the "
    "anti-rule on the non-BTC fills (0.39-0.46) and is not used; the in-the-money rule and the fill-price posture are reported; not "
    "counted (VALIDATE non-BTC side 0.58 / 0.68 < 0.80).")})
cat["X151"].update({"status": "tried", "evidence": cat["X151"]["evidence"] + (
    " | iteration 15: examiner-style halves on the mock lots (X174): R8 fails scope in a half of 2 of 3; the all-family universe is "
    "reported by evaluate().")})
cat["X83"].update({"status": "tried", "evidence": cat["X83"]["evidence"] + (
    " | iteration 15: the family-general universe is reported (r9_nonbtc_module: scope pooled, per wallet, per half); module state "
    "stays own state (X152).")})

s["hypotheses"] += [
    {"id": "H15-NB-ITM-OPEN", "family": "side (non-BTC module)", "description": "opening fills (< 20 s) buy the outcome in the money under the family's Binance reference vs the strike",
     "validate_metrics": {"BUILD": 0.814, "STUDY": [0.722, 0.897, 0.860, 0.837], "VALIDATE": 0.778, "market_favourite_VALIDATE": 0.485},
     "verdict": "real (+0.19-0.29 over the market favourite) but below 0.85 and only 13% of non-BTC fills; its fills lose money"},
    {"id": "H15-NB-POSTURE-FP", "family": "side (non-BTC module, description)", "description": "relative value vs a Binance-vol fair (k 1.0) with the fill price as the market price",
     "validate_metrics": {"BUILD": 0.667, "STUDY": 0.753, "VALIDATE": 0.676}, "verdict": "description only (uses the fill price); public version in T1d"},
    {"id": "H15-TWAP-LAW", "family": "side (quote unit)", "description": "settlement-average variance law as k(tau)",
     "validate_metrics": {"safe_lag_all": 0.779, "k1_all": 0.779, "last120_law": 0.749, "exact_law": 0.835, "exact_k1": 0.866}, "verdict": "rejected"},
    {"id": "H15-PUB-UNIT", "family": "presence/side (quote unit, publish clock)", "description": "500 posts in [P_i, P_i+300 ms) vs the report-i posture (no fitting)",
     "validate_metrics": {"1031_level_auc": 0.794, "1031_which": 0.866, "placebo_before": [0.625, 0.652], "change_after_before": [0.665, 0.429], "1101_level_which": [0.675, 0.717]},
     "verdict": "trigger signature confirmed on 30 min; fitted gain over activity not yet measured"},
    {"id": "H15-X160-REPL", "family": "side (quote unit)", "description": "replication of the quote-unit posture side on 11-01 07:00-07:50",
     "validate_metrics": {"exact_k1": 0.624, "cheaper": 0.663, "best_scan": 0.697}, "verdict": "fails on 50 min (12 windows)"},
]
comp = s["components"]
comp["size"]["description"] = ("Iteration 15: a configured size per family, identical in the three wallets (activity fill-size modes and 11-01 calldata): "
                               "BTC 5m/15m 500 x 2^k with 1/8, 1/2 and 1/5 levels; BTC hourly 38 / 300; BTC 4h 400; ETH 5m 50 / 150; ETH/SOL 15m 30; "
                               "SOL 5m 50 / 100; XRP 5m 10 / 50; BNB 5m 10; DOGE 5m 10 / 40; dailies 50 (BTC 200); plus imbalance pairing sizes. "
                               "Not reward-driven (rewardsMinSize 50 on every family). | " + comp["size"]["description"])[:2000]
comp["side"]["description"] = ("Iteration 15: outside BTC 5m/15m the cluster's opening fills (< 20 s) buy the outcome in the money under the family's "
                               "Binance reference (BUILD 0.81, VALIDATE 0.78 vs market favourite 0.62 / 0.49), later fills follow the market favourite "
                               "(0.55-0.75); the pure BTC 500 ladder follows the Chainlink posture at 0.866 on the exact publish clock (10-31, 30 min) but "
                               "0.62 on 11-01 07:00-07:50 (not replicated). | " + comp["side"]["description"])[:2400]
comp["selection"]["description"] = ("Iteration 15: R8's universe fails scope in a half of 2 of 3 weekend mock lots (10-17/18 later 0.41 / 0.61; 10-24/25 0.39 / 0.32); "
                                    "only every crypto family holds; reported as r9_nonbtc_module. | " + comp["selection"]["description"])[:2400]
s["strategy_statement"] = (
    "[engine: VALIDATE-only] One engine runs three accounts with three owner keys and posts each decision in all of them; it quotes every "
    "crypto Up/Down family at a configured size per family (BTC 5m/15m 500 x 2^k with 1/8, 1/2, 1/5 levels; other families 10-400). "
    "[selection: hypothesis] Modules are switched on and off by hand (BTC 5m off on some weekend evenings and after losing stretches); in the "
    "idle weekend blocks only the non-BTC families trade, so R8's BTC universe fails scope there (mock-lot halves 0.28-0.41 of trades). "
    "[timing: VALIDATE-only] The BTC ladders are re-sided by each public Chainlink publish within ~300 ms (publish-anchored posts: report-i "
    "posture AUC 0.79 after the publish vs 0.63 before; 10-31, 30 min) and re-posted after Binance moves; it stops ~45 s + TWAP lookback before "
    "the end; outside BTC the fills concentrate at the window open for the 5m alts. [side: VALIDATE-only] BTC: decided window -> cheaper token, "
    "else the Chainlink posture (0.693 per fill VALIDATE); the uncensored pure 500 quote follows the posture at 0.78 (safe lag) / 0.87 (exact "
    "publish clock) on 10-31 but 0.62 on 11-01 07:00-07:50; non-BTC: opening fills buy the outcome in the money under the family's Binance "
    "reference (0.78-0.81 vs market 0.49-0.62), later fills follow the market favourite. [price: exam-verified block clock; VALIDATE-only "
    "in-block] last clean trade minus 0.01 on the fastest clock (0.807 in-block VALIDATE); it does not carry to the thin non-BTC books (0.44). "
    "[size: VALIDATE-only] the per-family configured table plus imbalance pairing sizes. [exit: VALIDATE-only] holds to resolution, pairs "
    "imbalances with bids for the missing shares about a fifth of the time, merges near the end. Money: the BTC ladders earn the spread "
    "from minting takers when first at the touch (strict replays at 2 s lose); outside BTC the profit is in the later 4h and hourly fills "
    "(+5-10% per $), not in the opening in-the-money buys (which lose).")
s["iterations"].append({"n": 15, "minutes": 98, "best_validate_score": 0.716, "validate_definition": "2026-10-27..30 (lot second half, aggregate)",
                        "paradigm": "the non-BTC module decoded on its own terms (opening in-the-money rule, per-family sizes, settlement references) and "
                                    "the publish-anchored quote unit (trigger placebo), plus clock integrity, label purity and the examiner's halves",
                        "families": ["X173/X175/X164 non-BTC side (itm, fill-price posture, public-price posture)", "X168 per-family size table + calldata 11-01",
                                     "X166 TWAP variance law", "X170 purity classes", "X163/X169 publish-anchored unit (no fit, placebo)",
                                     "X160 replication on 11-01 07:00-07:50", "X174 mock-lot halves", "X167 clock guard", "R9 reporting block in evaluate()",
                                     "non-BTC PnL by phase", "X176 print-level selection (non-BTC)", "X172 cancel lag (crude)",
                                     "X170 purity on 11-01 (calldata)", "X163 fitted on 11-01 07:00-08:07"]})
s["status"] = "continue"
s["wall_reason"] = None
s["live_lab_note"] = (s.get("live_lab_note") or "") + (" | iteration 15: the laptop clock drifts ~0.19 s/h slow (0.898 s at 11-01 07:13 UTC; "
                                                       "w32tm not synchronized since 02:29 UTC); records are filed by receive time, so a resync by the user is "
                                                       "needed before 11-01 12:00 UTC; own readers in code/ now filter by server stamps.")
s["best"]["rule_id"] = s["best"]["rule_id"].replace("(iteration 14: unchanged; reported blocks quote_unit_side and quote_presence_event_time added)",
                                                    "(iterations 14-15: unchanged; reported blocks quote_unit_side, quote_presence_event_time and r9_nonbtc_module added)")
P.write_text(json.dumps(s, indent=1, default=str), encoding="utf-8")
op = sorted([k for k, v in s["catalog"].items() if v.get("status") == "open"], key=lambda k: (k[0], int(k[1:]) if k[1:].isdigit() else 0))
print("open", len(op), op)
