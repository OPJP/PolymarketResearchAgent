"""Iteration 9 state.json update (catalog X118-X131, components, hypotheses, target metrics, best, live_lab, iteration)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
P = ROOT / "research/reverse_engineering/tommy-cs2-maker/state.json"
s = json.loads(P.read_text(encoding="utf-8"))
cat = s["catalog"]

X = {
 "X118": ("open", "information panel P1 (iter 8): Valve's key-free Dota spectator state (dota2.com webapi GetLiveGames / GetRealtimeStats) as the public form of the feed's Dota half",
          "Endpoints verified key-free (probe_valve.py: GetLiveGames 200, 9 live league games; GetRealtimeStats 200, ~10 KB, new snapshot every ~4 s; api.steampowered.com needs a key per the panel). Recorder tommy_dota_rt (code/iter9/dota_rt_recorder.py) started 11-01 02:14 UTC: 30-s live list, 1-s snapshots of games matched to open Polymarket Dota events, unit-rule filing, hard stop 11-03 00:00, 250 MB cap. Tests (a)-(c) pre-registered in NOTES iteration 9; no development block with a Dota take yet."),
 "X119": ("tried", "information panel P2 (iter 8): rebuild the Dota ladder's price from spectator-clock events",
          "Price part = X123 (rejected: last print + dV 0.411 vs last print 0.431 on 857 VALIDATE Dota orders; placebo clocks 0.420-0.426). Timing part (dota_burst_events.json, 412 maker signing bursts of 10-22, P4e-only D): 0-6 s after an own-team kill 7.8% vs 5.2% on shifted clocks (p 0.045), any kill 13.4% vs 10.2% (p 0.075); the >= 50% signature fails. The uncensored live version (book events, net worth / positions) is part of X118."),
 "X120": ("tried", "information panel P3 (iter 8): GRID events as a natural experiment (coverage vs relative-speed boundary)",
          "grid_experiment.json (11,702 public taker txs of the 25 GRID CS2 events with most group-G prints decoded into calldata_grid/): group G's lags behind 0xf1ee4842 identical in GRID and non-GRID events (0x7c8cc255 +10.5 vs +6.5 ms, 0x8a80528d +63.5 vs +56.5, 0x67706ec3 +54 vs +57, 0xc7097421 +71.5 vs +66.5, 0xddb6e624 +57.5 vs +43; nulls 0-3); group-G clusters in GRID events have no pre-move (-0.01c vs -0.18c) and LARGER markouts (10 s +1.78 vs +0.89c, diff +0.90c [0.35, 1.45]; 60 s +2.80 vs +1.57c, +1.23c [0.46, 2.01]). The relative-speed reading (pre-moves, small markouts in GRID events) is rejected; the wallet's boundary is the coverage of its product. Step 3 (Dota D-scan on GRID Dota maps) and step 4 (dating the wallet's first co-sign) not run."),
 "X121": ("open", "information panel P4 (iter 8): co-receiver makers as wallet-independent witnesses of the messages behind the alone takes and untriggered pulls",
          "Not run: needs the block's public taker calldata of the recorded books to split alone vs co-signed takes; BUILD-live has only 39 wallet takes on recorded books and no decoded public calldata of those books. Scheduled for VALIDATE-live (11-01 06-12 and later development blocks)."),
 "X122": ("open", "information panel P5 (iter 8): the CS2 game clock from demos (Dota protocol on CS2 ticks)",
          "Needs the user's explicit consent to download demos (50-300 MB each, bo3.gg / HLTV) and to install a demo parser from PyPI; asked in the return. The Dota protocol it would reuse works (finding 24 of iteration 8; lag_spread.json)."),
 "X123": ("tried", "mechanics panel P1 (iter 8): Dota game-state fair value as the maker's anchor",
          "dota_v_anchor.json: V = logistic(gold / xp / kill leads x minute) on 160 OpenDota pro matches of 10-08..10-20 (6,326 minutes, in-sample AUC 0.837), P4e-only D per map, state at tau - 5 s. Within one tick: VALIDATE (857 Dota orders) last print 0.431, last print - s 0.443, last print + dV - s 0.411 (D +-120 / 300 s: 0.420-0.426), |V| - s 0.050; BUILD-live (197) 0.503 / 0.513 / 0.467 (0.411-0.472) / 0.030. Spearman(price - last print, dV) -0.189 at the true clock (bid-ask bounce after own-team gains). Rejected: the private V is not the public game state at minute / kill resolution."),
 "X124": ("tried", "mechanics panel P2 (iter 8): outcome by component knockout in the validated fill engine",
          "knockout.json (X57 engine, 229 markets): A own orders VALIDATE +1.1% (PnL vs wallet 0.43 / 0.33, margin 0.61 / 0.54); B own windows at the public anchor -2.3% (BUILD -4.5%), pair cost 1.002, margin vs wallet 0.19 / 0.14; C own prices quoted continuously +1.3% (BUILD +1.4%), margin vs wallet 0.47 / 0.41 (BUILD 0.66 / 0.61); D public anchor continuous -1.9%, PnL vs wallet 0.25 / 0.09 (below the prints baseline 0.33 / 0.28). The price level carries the margin, not the resting windows: the outcome item is the price item. Group-P share of fills highest for B (18.2%)."),
 "X125": ("ruled_out", "mechanics panel P3 (iter 8): a CS2 round clock from P4e's round-win messages and a round-score fair value",
          "p4e_round_align.json (70 bo3-parsed maps): NW identity of P4e's bought-team sequence vs bo3's round winners 0.785 vs 0.792 permuted / 0.771 random, 2 of 70 maps at p < 0.05, Fisher p 1.0, team-share Spearman 0.12 (p 0.32). With the socket's round part constant for its events (X2) and bo3 timing alignment at the control (X10, 0 of 95 maps), no point-in-time CS2 round clock exists for its events, so the round-score V cannot be scored; the remaining clock is demos (X122, consent)."),
 "X126": ("tried", "mechanics panel P4 (iter 8): the fan-out's delivery structure (broadcast or sequential sender)",
          "fanout_structure.json (4,087 P4e messages, 157 with >= 3 acting subscribers): pair order consistency median 0.573 vs 0.612 under independent marginals (0 of 21 pairs above the null p95): no fixed sending order; lag-residual common mode r 0.864 (shuffled 0.008): one shared message time; queue load: the slow trio +142-188 ms per extra P4e message in the previous 1 s (t 2.6-4.3), the wallet and group G no slope. One broadcast; the trio consumes it sequentially."),
 "X127": ("tried", "assumptions panel P1 (iter 8): selection = group P's coverage (feature rebuilt on the right product)",
          "selection_groupP.json (pre-registered): BUILD-only membership = P4e, 0x2005d16a, 0x72aaaaf9, 0x2529c68d, 0xfe8a28be (GRID share <= 1.6%; group G 28-53%, P93 7.2%). VALIDATE CS2: raw gp72 0.892 (recall 0.917, lift 2.40); act + GRID + gp72 0.962 (unseen 0.974); v4 + gp72 0.973 (unseen 0.974, recall 0.75, lift 3.20) vs v4 0.957 (unseen 0.928). Criterion met -> frozen v5. v5 pooled via evaluate(): AUC 0.970 vs 0.886, gain +0.084 [0.030, 0.152], recall 0.744, lift 3.155; Dota part 0.926 / recall 0.667 (v4 0.963 / 1.0). Forward 10-31 block (development runs skip sealed earlier events): AUC 0.842, recall 0.0."),
 "X128": ("tried", "assumptions panel P2 (iter 8): decode group G's takes where Feed P is absent (vendor structure, Feed P's latency class)",
          "Run with X120 (grid_experiment.json): same delivery order of group G in GRID and non-GRID events (one vendor for group G); 33% of group-G clusters in GRID events led by another wallet (0x6e2c0e94, 0xc0e4f49b, 0x10d79cc7, 0xfc23869c; 41% of them also trade the wallet's markets) vs 10% (+7% group P) in non-GRID events; group G more informed in GRID events. Feed P's own latency class stays unmeasured (it never appears in GRID events). Step 4 (message kinds by class) not run."),
 "X129": ("tried", "assumptions panel P3 (iter 8): machine reader or human scouts (spread of the lag behind in-game events)",
          "Step 1 (lag_spread.json, 10-22 Dota maps, 30 kill-linked anchors, D in 0.1-s steps): net hits at w = 0.8 / 1.2 / 1.6 / 2 / 3 / 4 s = 0.77 / 0.87 / 0.90 / 0.93 / 1.0 / 1.0 of the 3-s count (machine ~0.80 at 0.8 s, scout SD 0.4 s ~0.6); isolated-kill lag SD 0.41 s (26); teamfight later-kill lags +0.55 s (4). Leaning machine on isolated kills, small n. Step 2 (replays, tick-level) needs the user's consent to download; step 3 (coordinated wrong-way clusters) not run."),
 "X130": ("tried", "assumptions panel P4 (iter 8): scope insurance for a third title",
          "scope_titles.json: the wallet's development TRADE rows are CS2 and Dota 2 only (16-22 Oct 35,194 / 1,472; 10-31 block 301 / 358). Group P: P4e CS2 4,796, Dota 91, LoL 3; the slow trio also NBA ~5,500, Valorant ~210, LoL ~190. A third module is possible; v5 keeps CS2 + Dota 2 and _coverage() reports any gap on the lot."),
 "X131": ("tried", "assumptions panel P5 (iter 8): attribute the per-market residual to group G's takes",
          "residual_attrib.json: taker class of the wallet's maker shares group P 14.8%, group G 2.0%, others 83.3%; residual (PnL - locked margin) drop-one partial R^2 group P 0.077, others 0.054, pairs 0.061, group G 0.007; per-share group P -4.1c, others -2.5c, group G +5.4c. Rejected: the residual is group P's (its own feed's earlier subscribers), not group G's; the group-G pull replay was not run (nothing to cut)."),
}
for k, (st, src, ev) in X.items():
    cat[k] = {"status": st, "source": src, "evidence": ev}
cat["X98"]["evidence"] = cat["X98"]["evidence"] + " | Iteration 9: v5 (v4 + group-P coverage) on the 10-31 12-18 block (exam constants): AUC 0.842 (v4 0.851) vs 0.640, recall 0.0 because development runs skip earlier sealed-start events (gp72 ~0); v5b (monotone boost, v4 threshold) added to the forward pool."
cat["X117"]["evidence"] = cat["X117"]["evidence"] + " | Iteration 9: X120 shows group G's fan-out covers GRID events with the same delivery order (so GRID events are not unreadable for every vendor), and X129 step 1 leans machine-timed on isolated Dota kills; the relay census itself is not run."
cat["X88"]["evidence"] = cat["X88"]["evidence"] + " | Iteration 9: superseded for timing by X118 (Valve's 4-s spectator snapshots, recorder tommy_dota_rt)."

comp = s["components"]
comp["selection"] = {"confidence": 0.75, "tag": "VALIDATE-only",
    "description": ("Whole events of non-GRID CS2 and Dota 2 leagues (never a GRID event: CS2 0/122, Dota EPL Masters 0/33) covered by its feed product (group P: P4e, 0x2005d16a, the slow trio, fixed on BUILD). Frozen v5 = logistic(1.25 logit(v4 league/popularity score) + 1.19 log1p(gp72) - 1.11), gp72 = group-P members with a print in another event of the league in the previous 72 h: VALIDATE pooled AUC 0.970 vs activity 0.886 (gain +0.084 [0.030, 0.152]), recall 0.744 at lift 3.155; CS2 0.972, Dota 0.926; coverage 1.0 / 1.0. "
                    "GRID events are covered by group G's fan-out (same delivery order, larger markouts there), so the boundary is the coverage of the wallet's product, not data speed. Forward 10-31 block: AUC 0.842 but recall 0 in development runs (earlier sealed events skipped).")}
comp["timing"]["description"] = comp["timing"]["description"] + " Iteration 9: the fan-out is one broadcast (order consistency at the marginals' null, common-mode lag residual r 0.86) with a load-dependent slow tier (the trio); the Dota kill messages look machine-timed on isolated kills; the Dota maker bursts are only weakly locked to kills (13% vs 10% within 6 s)."
comp["price"] = {"confidence": 0.4, "tag": "VALIDATE-only",
    "description": ("Maker: whole-cent BUY ladders near the touch (adds at touch 28%, +1 14%, -1 10%, down to -5 13%); historical last-print anchor 0.322 (VALIDATE). Live (BUILD-live): touch 0.472 per add. Iteration 9: the price level carries the per-market margin (knockout: its prices quoted continuously +1.3%, its windows at the public anchor -2.3 to -4.5%), but neither a public game-state value (Dota V: 0.41 vs 0.43) nor a public tape-state model (0.285 vs 0.298) predicts its offset from the last print: the level is its private value. Taker: limit = stale ask + its own premium.")}
comp["exit"]["description"] = comp["exit"]["description"] + " Iteration 9: per-market residual is taken by group P (14.8% of maker shares, -4.1c per share on the residual), not group G (2.0%)."

s["hypotheses"] += [
 {"id": "H96", "family": "selection", "description": "R6 / X127: the wallet's selection is the coverage of group P's product (BUILD-fixed members; gp72 in earlier events of the league).",
  "validate_metrics": {"raw_gp72_auc": 0.8919, "v4_plus_gp72_auc_cs2": 0.9734, "v4_auc_cs2": 0.9574, "unseen_v5": 0.9737, "unseen_v4": 0.9276, "v5_pooled_auc": 0.9702, "v5_gain_ci95": [0.0302, 0.1517], "v5_recall": 0.744, "v5_lift": 3.155},
  "verdict": "supported; adopted as frozen v5 under the pre-registered criterion"},
 {"id": "H97", "family": "price", "description": "R4 / X123: the Dota ladder is anchored on a public game-state value V (gold / xp / kills) on the feed's clock.",
  "validate_metrics": {"last_print": 0.4306, "last_print_minus_s": 0.4434, "last_print_plus_dV": 0.4107, "placebo_clocks": [0.4201, 0.4259, 0.4224, 0.4236], "abs_V": 0.0502, "spearman_dev_dV": -0.189},
  "verdict": "rejected"},
 {"id": "H98b", "family": "timing", "description": "X119: Dota ladder re-pricings sit within 6 s of spectator-clock kills (>= 50%).",
  "validate_metrics": {"bursts": 412, "own_kill_share": 0.0777, "own_null": 0.0522, "any_kill_share": 0.1335, "any_null": 0.1021},
  "verdict": "rejected in the strong form (weak locking)"},
 {"id": "H99b", "family": "information source structure", "description": "R7 / X120: GRID events are a relative-speed boundary (a faster official feed moves the market first).",
  "validate_metrics": {"groupG_lag_same_order": True, "pre10_grid_minus_nongrid_c": 0.171, "mk10_diff_c": [0.896, 0.353, 1.447], "mk60_diff_c": [1.233, 0.461, 2.006]},
  "verdict": "rejected; coverage of the wallet's product"},
 {"id": "H100", "family": "outcome", "description": "R5 / X124: the per-market margin is carried by the resting windows rather than the price level.",
  "validate_metrics": {"A_return": 0.0106, "B_return": -0.0231, "C_return": 0.0129, "D_return": -0.0187, "C_margin_corr": [0.468, 0.409], "B_margin_corr": [0.187, 0.142], "D_pnl_corr": [0.245, 0.089]},
  "verdict": "rejected: the price level carries it (outcome = price item)"},
 {"id": "H101", "family": "price", "description": "A public tape-state model predicts the wallet's maker offset from the last print.",
  "validate_metrics": {"gbm_within_tick_actual_prices": 0.2852, "last_print_same_orders": 0.298, "artefact_clipped_class_score": 0.3569},
  "verdict": "rejected (the first score was a clipped-class artefact)"},
 {"id": "H102", "family": "outcome", "description": "X131: group G's takes carry the per-market residual.",
  "validate_metrics": {"share_P": 0.1478, "share_G": 0.0196, "partial_r2_resid": {"P": 0.0767, "G": 0.0074, "O": 0.0542, "pairs": 0.0607}},
  "verdict": "rejected (group P is the informed counterparty)"},
 {"id": "H103", "family": "information source structure", "description": "X126: the fan-out is a sequential sender (positions in a vendor queue).",
  "validate_metrics": {"order_consistency_median": 0.573, "null_median": 0.612, "pairs_above_null": 0, "common_mode_r": 0.864, "trio_ms_per_queued_msg": [141.9, 169.3, 187.6]},
  "verdict": "rejected for the fast subscribers (one broadcast); the slow trio queues"},
 {"id": "H104", "family": "timing", "description": "X125: P4e's take clusters are round-win announcements in sequence (a public CS2 round clock).",
  "validate_metrics": {"maps": 70, "nw_identity": 0.7852, "permuted": 0.7924, "random": 0.7711, "fisher_p": 1.0},
  "verdict": "rejected"},
 {"id": "H105", "family": "information source", "description": "X129: the feed's kill messages are machine-timed (constant lag), not keyed by scouts.",
  "validate_metrics": {"saturation_w0.8": 0.767, "saturation_w1.2": 0.867, "isolated_sd_s": 0.408, "n": 30},
  "verdict": "weakly supported on isolated kills (small n)"},
]

s["target_metrics"] = {"presence_auc": 0.8834, "selection_auc": 0.9702, "selection_recall": 0.744, "selection_lift": 3.155,
                       "presence_baseline": 0.8907, "selection_baseline": 0.8863, "side_accuracy": None, "side_baseline": None,
                       "price_within_tick": 0.322, "pnl_corr_pearson": -0.131, "pnl_corr_spearman": -0.081,
                       "coverage_fills": 1.0, "coverage_abs_pnl": 1.0}
r = json.load(open(ROOT / "research/reverse_engineering/tommy-cs2-maker/results/final_rule_v5_validate.json"))
keep = ["events", "events_traded", "selection_auc", "selection_auc_v4", "gp72_events_gt0", "selection_baseline", "selection_gain", "selection_gain_ci95",
        "selection_gain_p_le0", "selection_recall", "selection_lift", "selection_cs2", "selection_dota2", "presence_auc", "presence_baseline",
        "price_within_tick", "price_exact_last_print", "size_rule_accuracy", "pnl_corr_pearson", "pnl_corr_spearman",
        "pnl_baseline_prints_pearson", "pnl_baseline_prints_spearman", "coverage_fills", "coverage_abs_pnl", "coverage_fills_cs2_only"]
s["best"] = {"rule_id": "tommy-v5-grid-league-dota-groupP", "validate_metrics": {k: r.get(k) for k in keep}}
tmn = s.get("target_metrics_notes", {})
tmn["selection_v5"] = "Iteration 9: v5 = v4 score + group-P coverage gp72 (pre-registered adoption). VALIDATE pooled AUC 0.9702 (v4 0.9528) vs activity 0.8863, gain +0.084 [0.030, 0.152]; recall 0.744, lift 3.155. Development runs on forward blocks skip earlier sealed-start events, so gp72 is under-counted there (10-31 block recall 0.0); the examiner counts all earlier events."
tmn["primary_metric_change"] = "Iteration 9: presence_auc 0.8739 -> 0.8834 because the event score inside the presence rule is now v5's (baseline 0.8907 unchanged)."
tmn["outcome_knockout"] = "Iteration 9 (X124): the validated engine's executable public variant D correlates 0.245 / 0.089 with the wallet's per-market PnL on VALIDATE (0.126 / 0.114 BUILD), below the prints baseline; not adopted. The wallet's own prices quoted continuously keep the margin (C +1.3%), its windows at the public anchor lose (B -2.3%)."
s["target_metrics_notes"] = tmn
s["live_lab"].append({"what": "own recorder, feed tommy_dota_rt (code/iter9/dota_rt_recorder.py): Valve's key-free dota2.com webapi, GetLiveGames every 30 s (all live league games) and GetRealtimeStats every 1 s for games matched to open Polymarket Dota 2 events (a record per new ~4-s snapshot: game time, team score / net worth, per-player kills / deaths / assists / net worth / gold / level / x / y, buildings, gold graph); filed by unit (sealed-start units always sealed) via code/iter5/unit_writer.py; detached (launcher 23824, worker 17524), hard stop 2026-11-03 00:00 UTC, 250 MB cap",
                      "start": 1793498874, "end": 1793664000})
s["iterations"].append({"n": 9, "minutes": 95, "best_validate_score": 0.8834,
    "paradigm": "public game-state fair value as the quote anchor (Dota spectator clock, CS2 round clock) plus a new key-free spectator-state source, the outcome decomposed by component knockout in the validated engine, and selection rebuilt on the feed product the wallet buys (group P)",
    "families": ["group-P product coverage selection, BUILD-fixed membership (X127, adopted as v5)", "Dota game-state fair value V from OpenDota pro matches (X123)", "Dota maker bursts vs kills on the feed clock (X119)", "component knockout of the per-market margin in the X57 engine (X124)", "public tape-state price-offset model and distillation", "GRID natural experiment with decoded GRID-event calldata (X120 / X128)", "fan-out delivery structure: order consistency, common mode, queue load (X126)", "machine vs scout lag spread (X129 step 1)", "P4e round-winner sequence alignment (X125)", "residual attribution by taker class (X131)", "scope titles of the wallet and group P (X130)", "Valve spectator-state endpoints and recorder (X118)"]})
s["status"] = "continue"
s["wall_reason"] = None
s["strategy_statement"] = (
    "CS2 and Dota 2 in-play bot; from 10-16 a buy-only two-sided maker plus an informed taker (one signing key, owner 0x8af810f0, for both legs and both regimes), before that a round-trip taker in GRID tier-1/2 events. "
    "[VALIDATE-only] Selection: whole events (match + all maps) of non-GRID CS2 / Dota 2 leagues that its push-feed product covers (group P: P4e, 0x2005d16a, the slow trio; GRID events are covered by another subscriber group with the same delivery order, so the boundary is its product, not data speed); frozen v5 (league / popularity score + group-P coverage in the previous 72 h) pooled AUC 0.970 vs activity 0.886, recall 0.74 at lift 3.16, coverage 1.0. "
    "[VALIDATE-only] Maker: whole-cent BUY ladders near the touch on both outcome tokens (100 shares in CS2, 10 in Dota 2), never sells, merges pairs in one 300-s loop (97% paired, pair cost 0.978); the per-market margin is made by its price level (its own prices quoted continuously earn +1.3%, the public anchor at its own windows loses 2.3-4.5%), and that level is not predicted by public game state or public tape state. "
    "[hypothesis, BUILD-live] Protection: at its own takes it pulls the complement at +11-19 ms and re-posts after the FAK returns (~1.03 s); between takes it re-prices on the private input (ground-truth wallet cancels -0.94c in 10 s). "
    "[hypothesis] Taker: FAK BUYs on raw in-round messages of one broadcast esports push feed (P4e first, the wallet +50 ms, a slow trio with a load-dependent queue; machine-timed on isolated Dota kills; its Dota half at the spectator delay) of the plant / turn kind, at the stale ask plus its own premium. "
    "[VALIDATE-only] Economics: per-market PnL is the locked pair margin; the informed counterparty that takes its residual is group P (14.8% of its maker shares); public replays do not track its per-market PnL (best executable 0.25 / 0.09, below the co-occurrence baseline).")
s["next_steps"] = [
    "First development block with a Dota take: the X118 tests on tommy_dota_rt (kill-increment lag of P4e / wallet / trio takes; the wallet's 10-share ladder events; net worth / positions before kill-free takes), with the iteration-8 VALIDATE-live runbook unchanged.",
    "X98 forward pool on every development block: v4, v5, v5b (monotone boost) and the earlier variants, no refit.",
    "X121 on VALIDATE-live (co-receiver makers at alone vs co-signed takes, the block's public calldata decoded).",
    "Ask the user: demos (X122 / X37) and Dota replays (X129 step 2) downloads, PandaScore token (X55), HLTV page checks (X64), stream / chat routes (X4 / X22 / X53), odds probes (X48 b), z3 for X96."]
s.setdefault("data_sources", [])
s["data_sources"] += [
    "Valve dota2.com webapi GetLiveGames / GetRealtimeStats (key-free; recorder tommy_dota_rt from 11-01 02:14 UTC)",
    "OpenDota /proMatches and /matches of 160 pro matches started 10-08..10-20 (per-minute gold / xp leads and kills: dota_train_minutes.parquet)",
    "Decoded public taker transactions of 25 GRID CS2 events of 16-22 Oct around group-G prints (11,702 txs: .cache/re/tommy-cs2-maker/calldata_grid/, decoded fields only)",
    "Public data-api activity of the five group-P members, 16-22 Oct (titles only kept in scope_titles.json)"]
P.write_text(json.dumps(s, indent=1), encoding="utf-8")
op = [k for k, v in s["catalog"].items() if v.get("status") == "open"]
print("open", len(op), op)
