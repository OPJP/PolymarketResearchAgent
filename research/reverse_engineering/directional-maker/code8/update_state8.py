"""Iteration 8: bring state.json up to date (catalog X59-X73, components, target_metrics, iteration entry)."""
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "state.json"
s = json.loads(P.read_text())
cat = s["catalog"]

new = {
    "X59": ("open", "source: panel iter7 information I7-1 (the between-report input on its own publish clock: RTDS Binance relay "
            "crypto_prices vs a direct Binance feed). Iteration 8: recorder code8/rtdsbn.py (feed dz_rtdsbn, filters \"\", "
            "btcusdt/ethusdt/solusdt with value stamp, publish ms, receive ms) started 19:12 UTC 10-31, hard stop 11-03 00:00; "
            "status counts show the topic streams (1,314 messages / 657 kept in 2 min); content not inspected (sealed block). "
            "Related June evidence (A5/X73): the June engine signed 100-400 ms after Binance moves (spot-only vs futures-only "
            "enrichment 5.3x vs 3.1x on 06-12 but 3.3x vs 3.1x on 06-16: venue not separable). Test on 11-01 06-12."),
    "X60": ("open", "source: panel iter7 information I7-2 (cross-horizon Polymarket books and Kalshi KXBTC15M as the seller trigger "
            "and posture residual). Not done. Related: M1 (X63) shows each market's ladder hangs off its own mid (S_hat_5m - "
            "S_hat_15m follows S_mid_5m - S_mid_15m, slope 0.83, R^2 0.79), so the cluster does not price 5m off the 15m book."),
    "X61": ("open", "source: panel iter7 information I7-3 (strike publication lag: priceToBeat known from RTDS ~1 s before the open). "
            "Needs polling of Gamma and the crypto-price endpoint during a development block (11-01 06-12). Not done."),
    "X62": ("open", "source: panel iter7 information I7-4 (RTDS activity topic: taker identity in real time). Needs a development-"
            "block recording (11-01 06-12). Not done."),
    "X63": ("tried", "source: panel iter7 mechanics M1 (invert the engine's internal price from simultaneous 5m and 15m quotes). "
            "Iteration 8 code8/m1_invert.py on 10-31 14:06-16:30 (2,266 s with top rungs on both outcomes of both markets): "
            "|S_hat_5m - S_hat_15m| median 2.8 tick-equivalents, within one tick-equivalent 20% (signature needed >= 70%); the "
            "disagreement is the markets' own mids (slope 0.83, R^2 0.79); each S_hat tracks its own mid-implied S (resid sd "
            "$4.7/$5.2) better than futures ($7.8/$11.9) or Chainlink ($9.8/$13.9) or any EMA; best blend beta ~0.2 toward "
            "Chainlink, median error still 2.3-2.5 tick-equivalents. Rejected: no common model price; mid-anchored ladders."),
    "X64": ("open", "source: panel iter7 mechanics M2 (strict-fill replay of the decoded generator against the recorded takers, "
            "back-of-queue fills, realized per-window PnL). Not done; the generator's level is not decodable to a tick (X63), "
            "the replay needs the full-depth recorder of 11-01 06-12 (code8/delayed_rawrec.py)."),
    "X65": ("open", "source: panel iter7 mechanics M3 (the engine's universe from signature-counter conservation; freeze the exam "
            "scope). Scope part done under X69 (rule R6 = BTC 5m + 15m, evaluate() per family and pooled). The counter "
            "conservation (signed rate vs adds in every recorded book family) not done."),
    "X66": ("open", "source: panel iter7 mechanics M4 (the paying counterparty from the taker order struct: markouts by population; "
            "display-only move hazard by population). Panel's STUDY numbers recorded (type 2 Safe +21%, round-USD 107% of PnL, "
            "loose limits 87%); VALIDATE aggregate and the live hazard not done."),
    "X67": ("open", "source: panel iter7 mechanics M5 (historical posture labels from cleared levels in the tape). Not done. The "
            "per-fill side test (iteration 8, live 0.84) is the live analogue; the historical test needs the lot's maker rows."),
    "X68": ("open", "source: panel iter7 mechanics M6 (historical match clock from tx index, signing ms and the speed bump). Not done "
            "(lower priority: the exams run on recorded live blocks with server match ms)."),
    "X69": ("tried", "source: panel iter7 assumptions A1 (freeze the rule for the universe the engine trades). Iteration 8: R6 = R3/R5 "
            "on BTC 5m + R3's model class refitted on BTC 15m (code8/features15.py, panel15.py, train15.py; code/presence15_*.txt). "
            "VALIDATE 10-27..30 (aggregate): 15m presence 0.812 vs activity 0.778, side 0.733 vs 0.615; union pooled presence "
            "0.788 vs 0.780 (gain +0.009 [0.003, 0.016]), side 0.672, PnL corr 0.260/0.327, coverage 0.868 fills / 0.891 abs PnL; "
            "development blocks since 10-27 0.82-0.97 of trades and 0.93-0.95 of dollars in the union. evaluate() reports btc15m, "
            "union_btc5m_15m, scope; pre-registered: a block with BTC 5m off is scored on BTC 15m. Hourly-book recorder (step 5) "
            "not started (hourly families 4-9% of trades)."),
    "X70": ("open", "source: panel iter7 assumptions A2 (what switches BTC 5m off: loss limit vs volatility/message breaker vs module "
            "failure vs Chainlink data-quality breaker, on the full history). Not done (needs the full-history activity; the June "
            "activity of 06-10/12/16 is fetched)."),
    "X71": ("open", "source: panel iter7 assumptions A3 (the ladder is a state machine). Light form tried (code8/a3_hist.py): public "
            "path-history features (touch, futures and Chainlink changes over 1-10 s) do not raise the quote-unit AUC (0.748 -> "
            "0.720-0.737 held out; 10 BUILD windows). Strong form (per-wallet rung resolution, move law, replay) not done."),
    "X72": ("tried", "source: panel iter7 assumptions A4 (fill-presence ceiling with the observed quote as an oracle; quote-unit metric). "
            "Iteration 8 code8/a4_ceiling.py, code8/sel_oracle.py (10-31 14:06-16:30, live split): 10-s fill presence activity 0.624, "
            "public 0.661, + quote oracle 0.796-0.804, + future taker flow no gain -> ceiling ~0.80 < 0.85. Quote unit (window, "
            "side, second; cluster-class 500 at the touch now): activity 0.672, + Chainlink 0.740, + futures 0.748 (gain +0.076, "
            "window bootstrap [0.042, 0.110]). Print selection: activity 0.611, public 0.686, + quote oracle 0.814 (recall 0.62 at "
            "lift 3.32), public + oracle 0.834 (0.685 / 3.40): at the print level the quote is binding and the selection bar is "
            "reachable if the quote is decoded."),
    "X73": ("tried", "source: panel iter7 assumptions A5 (the June engine signed real ms timestamps). Iteration 8 code8/june_*.py: June "
            "10/12/16 activity and calldata (62k orders, 12.5k cluster), Binance futures and spot 50-ms series (06-12, 06-16). "
            "Cluster signing follows Binance moves by 100-400 ms (|move| 4-7x random at 150-400 ms before signing, 1.0x in the last "
            "50 ms and after; other makers 50-100 ms); limit price at signing vs Binance fair corr 0.85 (best lag -250..0 ms), MAD "
            "0.053; venue (spot vs futures) not separable across days; Chainlink not testable for June (30-day endpoint limit)."),
}
for k, (st, ev) in new.items():
    cat[k] = {"status": st, "evidence": ev}

upd = {
    "X21": ("tried", " | iteration 8: closed by X69 (R6 = BTC 5m + 15m; VALIDATE coverage 0.868 / 0.891; evaluate() per family)."),
    "X50": ("tried", " | iteration 8: per-fill side with the same rule (sign of the Chainlink edge over the mid at the match ms): live "
            "VALIDATE 0.841 (5m, n 1,207) / 0.874 (15m, n 199), through evaluate()'s shared-recorder path 0.836 (n 1,341) vs "
            "market-only baselines <= 0.61; live BUILD 0.66 (one bad half hour 0.45)."),
    "X19": ("tried", " | iteration 8: structural inversion (X63) rejects a common model price; each ladder is anchored to its own mid "
            "with a ~0.2 Chainlink skew; the level is not decodable to a tick from public inputs (21% iteration 5)."),
    "X40": ("tried", " | iteration 8 (X63): the 15m center follows the 15m mid, not the 5m book (S_hat_5m - S_hat_15m tracks the "
            "two mids' disagreement, slope 0.83): Q6's '15m priced off the 5m book' is not supported."),
}
for k, (st, add) in upd.items():
    cat[k]["status"] = st
    cat[k]["evidence"] = cat[k].get("evidence", "") + add
for k, add in {"X58": " | iteration 8: not advanced (A2 / X70 is its strong form).",
               "X9": " | iteration 8: see X70.", "D2": " | iteration 8: structural inversion (X63) and quote-unit LightGBM; no hazard/HMM yet.",
               "D3": " | iteration 8: strict-fill replay still open (X64)."}.items():
    if k in cat:
        cat[k]["evidence"] = cat[k].get("evidence", "") + add

s["components"] = {
    "selection": {"confidence": 0.4, "tag": "hypothesis",
                  "description": "one engine over crypto Up/Down; rule universe R6 = BTC 5m + BTC 15m (VALIDATE 0.868 of fills / 0.891 "
                                 "of abs PnL; development blocks since 10-27 0.82-0.97 of trades); nearly every window quoted; BTC 5m "
                                 "switched off for hours at a time by an operator or loss controller (10-31 16:53, own state; trigger "
                                 "undecoded, X58/X70); BTC 15m presence 0.812 vs 0.778 activity [VALIDATE-only]."},
    "timing": {"confidence": 0.78, "tag": "VALIDATE-only",
               "description": "October: a re-price pass of the ladders within ~0-150 ms of each Chainlink report's publish on the "
                              "public RTDS relay, plus re-posts 50-250 ms after Binance futures moves [live]; June (real signing ms): "
                              "orders signed 100-400 ms after Binance moves, price current at signing [development, other version]; "
                              "filled orders are fresh at-touch posts matched ~0.7 s later; withdraws in the last ~30 s."},
    "side": {"confidence": 0.7, "tag": "VALIDATE-only",
             "description": "the outcome it buys is the one whose Chainlink edge over the Polymarket mid is positive: per fill 0.84 on live "
                            "VALIDATE (5m 0.836-0.841, 15m 0.834-0.874; through evaluate() 0.836, n 1,341) vs market-only baselines <= "
                            "0.61, no fitted parameter; quote side per report 0.79; fails in some windows (14:30-15:00 0.45, live BUILD "
                            "0.66). Historical block-clock bin side 0.663 (exam 0.655), union 0.672."},
    "price": {"confidence": 0.65, "tag": "exam-verified",
              "description": "fill price = last clean print - 0.01 (the trivial anchor): block clock 0.709 VALIDATE 5m (exam 0.688), 15m "
                             "0.666; match clock 0.83-0.86 live [VALIDATE-only]. Ladder level: each market's ladder hangs off its own mid "
                             "with a ~0.2 Chainlink skew (no common model price across markets, X63); not decodable to a tick."},
    "size": {"confidence": 0.7, "tag": "VALIDATE-only",
             "description": "October: 500 x 2^k with a one-fifth level; 500 in the weekday 12-21 UTC session or high 300-s futures vol, "
                            "else 62/250; June: 50/100/300; remainders re-posted; no edge dependence."},
    "exit": {"confidence": 0.55, "tag": "VALIDATE-only",
             "description": "holds to resolution; small complement taker buys and merges (2-4% of PnL); maker-maker pairs ~90% of paired shares."},
}
s["strategy_statement"] = (
    "[engine: VALIDATE-only] One engine signs every order of the three wallets (per-wallet salt counters; real ms timestamps "
    "until ~06-21, timestamp 0 since). [selection: hypothesis] It quotes nearly every BTC 5m and 15m Up/Down window (rule "
    "universe R6 = both, 87-97% of fills) plus some hourly/4h/ETH/SOL; BTC 5m is switched off for hours by an operator or loss "
    "controller (trigger undecoded). [timing: VALIDATE-only live] Both outcomes carry ladders of 500-share bids hung off each "
    "market's own Polymarket mid; on each Chainlink BTC/USD report (the settlement stream) the ladders are re-priced within "
    "~0-150 ms of the public RTDS relay's publish, and re-posted 50-250 ms after Binance moves between reports (June engine: "
    "signs 100-400 ms after Binance moves). [side: VALIDATE-only live] The outcome it buys is the one whose Chainlink edge over "
    "the mid is positive: 0.84 per fill on live VALIDATE vs <= 0.61 for market-only baselines (no fitted parameter); the "
    "Chainlink skew of the ladder (~0.2 of the edge) puts that outcome's 500 at the touch, and sellers who follow the futures "
    "fill it. [price: exam-verified block clock, VALIDATE-only match clock] fill price = last print - 1 tick on the match clock "
    "(0.83-0.86 live). [size: VALIDATE-only] 500 in the weekday US session or high futures vol, else 62/250. [exit: "
    "VALIDATE-only] holds to resolution with small complement buys and merges. Presence of fills is taker-bound: even with "
    "the quote observed, 10-s fill presence reaches only ~0.80 (A4), while print-level selection with the quote observed "
    "reaches 0.81-0.83 at recall 62-69% and lift 3.3-3.4. Profit = spread on at-touch posts that sellers hit, skewed by the "
    "settlement stream's own (noisy) reading; not decoded: the ladder level to a tick, the BTC 5m on/off trigger.")
s["target_metrics"] = {
    "presence_auc": 0.7883, "presence_baseline": 0.7796,
    "selection_auc": 0.6854, "selection_recall": 0.2947, "selection_lift": 2.8665, "selection_baseline": 0.6508,
    "side_accuracy": 0.672, "side_baseline": 0.6129, "price_within_tick": 0.7048,
    "pnl_corr_pearson": 0.2601, "pnl_corr_spearman": 0.3267, "coverage_fills": 0.868, "coverage_abs_pnl": 0.891,
    "_notes": ("rule R6 = R5 on BTC 5m (unchanged) + R3's model class refitted on BTC 15m, scored on the historical VALIDATE "
               "2026-10-27..30 over the union universe (pooled bins; code8/union_val.py): presence 0.7883 vs activity 0.7796 "
               "(gain +0.009); BTC 5m alone 0.716 / 0.684 (the pre-registered primary metric, unchanged); BTC 15m alone 0.812 / "
               "0.778. side = bin-level presence-score side pooled (5m 0.663, 15m 0.733). price = block clock pooled (5m 0.709, "
               "15m 0.666). pnl = expectation proxy per window pooled (5m 0.329/0.325, 15m 0.180/0.345). selection = BTC 5m only "
               "(R2's print model; not extended). Live VALIDATE (10-31 15:00-16:30, pre-registered live split): per-fill side "
               "with the Chainlink posture rule 0.836-0.846 (n 1,341-1,406) vs market-only <= 0.61; match-clock price 0.83-0.86; "
               "see target_metrics_live. coverage = BTC 5m + 15m on VALIDATE (iteration 5 cash-flow PnL).")}
tml = s.get("target_metrics_live", {})
tml.update({"side_accuracy_posture_per_fill_iter8": 0.836, "side_posture_n_iter8": 1341,
            "side_posture_per_family_iter8": {"5m": 0.836, "15m": 0.834},
            "side_posture_per_wallet_iter8": {"bosona": 0.858, "almach": 0.871, "momoney": 0.787},
            "side_posture_baselines_iter8": {"binance_spot_edge": 0.562, "cheaper_side": 0.550, "always_up": 0.608},
            "side_posture_note_iter8": ("evaluate() side_posture_match_clock on 10-31 15:00-16:30 (shared recorder 'q' mid, live Chainlink "
                                        "recordings, Gamma strike); code8/fill_side.py on the own raw touch: 5m 0.841, 15m 0.874; live "
                                        "BUILD 14:06-15:00 0.66 (14:30-15:00 0.45)."),
            "presence_fill_ceiling_with_quote_oracle_iter8": 0.804, "quote_unit_presence_auc_iter8": 0.748,
            "quote_unit_presence_baseline_iter8": 0.672, "print_selection_ceiling_with_quote_oracle_iter8": {"auc": 0.834, "recall": 0.685, "lift": 3.40}})
s["target_metrics_live"] = tml
s["best"] = {"rule_id": "R6 = R5 (BTC 5m) + R3-class BTC 15m presence + per-fill Chainlink posture side (match clock) + R4 price",
             "validate_metrics": {"historical_union": s["target_metrics"], "live": {k: v for k, v in tml.items() if k.endswith("iter8")}}}
s["status"] = "continue"
s["live_lab"] = s.get("live_lab", []) + [
    {"what": "code8/rtdsbn.py: dz_rtdsbn, RTDS crypto_prices (Polymarket Binance relay) with filters \"\": btcusdt/ethusdt/solusdt value, "
             "value stamp, publish ms, receive ms; unknown shapes raw (capped); disk cap 60 MB", "start": 1793474000, "end": 1793664000},
    {"what": "code8/delayed_rawrec.py: code5/rawrec.py full-depth dm_* feeds for the development block 11-01 06-12 (gate 05:55 UTC)",
     "start": 1793512500, "end": 1793534400}]
s["data_sources"] = s.get("data_sources", []) + [
    "iteration 8: cluster activity 2026-06-10/12/16 (data-api, cached) and calldata of 11,631 sampled transactions (62k orders; publicnode)",
    "iteration 8: Binance BTCUSDT USD-M futures and spot aggTrades 2026-06-12 and 06-16 reduced to 50-ms last prices (archives, SHA-256 checked)",
    "iteration 8: BTC 15m clean panels 2026-10-09..30 (.cache/re/directional-maker/p15)",
    "iteration 8: Binance REST 1-s klines fallback in evaluate() for days whose archive is not yet published"]
hyp = s.get("hypotheses", [])
hyp += [
    {"id": "A4-ceiling", "family": "X72", "description": "10-s fill presence with the observed quote as an oracle",
     "validate_metrics": {"activity": 0.624, "public": 0.661, "quote_oracle": 0.804, "with_future_flow": 0.803}, "verdict": "ceiling ~0.80 < 0.85: fills taker-bound"},
    {"id": "A4-quote-unit", "family": "X72", "description": "quote unit: cluster-class 500 at the touch now, public inputs",
     "validate_metrics": {"activity": 0.672, "chainlink": 0.740, "all": 0.748, "gain_ci": [0.042, 0.110]}, "verdict": "gain > 0.05, AUC 0.75 < 0.85"},
    {"id": "A4-selection-ceiling", "family": "X72", "description": "print selection with the observed quote as an oracle",
     "validate_metrics": {"activity": 0.611, "public": 0.686, "oracle": 0.814, "public_oracle": 0.834, "recall": 0.685, "lift": 3.40}, "verdict": "the quote is binding at the print level"},
    {"id": "M1-common-price", "family": "X63", "description": "one internal price behind the 5m and 15m ladders",
     "validate_metrics": {"within_one_tick_equiv": 0.20, "slope_on_mid_disagreement": 0.83, "r2": 0.79}, "verdict": "rejected"},
    {"id": "A3-light", "family": "X71", "description": "public path-history features for the quote unit",
     "validate_metrics": {"auc_with_history": 0.720, "auc_without": 0.748}, "verdict": "no gain (small BUILD)"},
    {"id": "A5-june-trigger", "family": "X73", "description": "June signing ms vs Binance moves",
     "validate_metrics": {"peak_rel_move_futures": 4.8, "peak_lag_ms": "150-400", "last_50ms_rel": 1.0, "price_corr_at_signing": 0.849}, "verdict": "Binance-reactive re-signer, 100-400 ms"},
    {"id": "R6-union", "family": "X69", "description": "R5 on 5m + R3-class 15m presence over the union",
     "validate_metrics": {"presence": 0.7883, "baseline": 0.7796, "btc15m": 0.8118, "btc15m_baseline": 0.7775, "coverage": [0.868, 0.891]}, "verdict": "adopted for scope"},
    {"id": "posture-fill-side", "family": "X50", "description": "fill side = sign of the Chainlink edge over the mid at the match ms",
     "validate_metrics": {"live_validate_5m": 0.841, "live_validate_15m": 0.874, "evaluate_path": 0.836, "baselines_max": 0.608}, "verdict": "adopted (side component of R6)"},
]
s["hypotheses"] = hyp
it = {"n": 8, "minutes": 100, "best_validate_score": 0.716, "validate_definition": "2026-10-27..30 (lot second half); live VALIDATE 10-31 15:00-16:30",
      "paradigm": "the quote as the unit: oracle ceilings for fills and prints, structural inversion across markets, per-fill posture side, June signed-ms decision times, union scope",
      "families": ["X72 fill-presence and print-selection ceilings with the quote oracle; quote-unit metric", "X63 two-market inversion of the internal price",
                   "X71 public path history (light)", "X73 June signed ms vs Binance (trigger, price at signing)", "X69 BTC 15m R3-class model and union scope; evaluate() per family",
                   "X50 per-fill posture side (live, and through evaluate())", "X59 RTDS Binance relay recorder started", "full-depth recorder scheduled for 11-01 06-12",
                   "fixes: R4 price tx-key bug in evaluate(), Binance REST fallback"]}
s["iterations"] = s.get("iterations", []) + [it]
P.write_text(json.dumps(s, indent=1))
print("open:", [k for k, v in cat.items() if v["status"] == "open"])
