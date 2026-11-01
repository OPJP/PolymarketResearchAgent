"""Iteration 18 state.json update. Reads the sib18 result JSONs and writes catalog, dimensions, indicators, components,
strategy_statement, target_metrics_notes and the iterations entry. Usage: python -I update_state_iter18.py"""
import json, time
B = "research/reverse_engineering/btc5m-bot"
s = json.load(open(f"{B}/state.json", encoding="utf-8"))
F = json.load(open(f"{B}/results/sib18_10-21_10-22.json"))   # forward: fit 10-20, score 10-21,22
Rv = json.load(open(f"{B}/results/sib18_10-20.json"))        # reverse: fit 10-21,22, score 10-20

def ag(d, k):
    return d["agreement_with_true_S"][k]
def rN(d, k):
    return d["pnl_proxy"][k]["rN"]
def pS(d, k):
    return d["pnl_proxy"][k]["pnl_S"]
def bo(d, k):  # bootstrap gain-vs-menu summary for variant k: "gain [lo, hi]"
    g = d["gain_vs_menu_block_boot"][k]; return f"{g['pnlS_gain_vs_menu']} {g['pnlS_CI']}"
CIsent = (f"Paired 2-h block bootstrap of the PnL-proxy Spearman gain vs the menu (no-sibling) baseline: sib "
          f"{bo(F,'smach_sib')} (forward) / {bo(Rv,'smach_sib')} (reverse), hyb {bo(F,'smach_hyb')} / {bo(Rv,'smach_hyb')} -- the "
          f"lower CI bound is > 0 on both splits, so the sibling size signal is a significant, reproducible gain over the baseline that "
          f"already contains W4/W5 prints as market activity.")

# --- short evidence string for X182 ---
x182 = (f"PIVOT (sib18, pre-registration 15): the operator's size state S read from the siblings' public large prints (W4/W5 taker "
  f"BUY filled>=60 confirmed-large, usable block_ts+2s, shared txs excluded). PARTIAL. Forward (fit 10-20, score 10-21..22) / "
  f"reverse (fit 10-21..22, score 10-20). S agreement with the operator's true S: sib {ag(F,'smach_sib')}/{ag(Rv,'smach_sib')}, "
  f"hyb {ag(F,'smach_hyb')}/{ag(Rv,'smach_hyb')}, own {ag(F,'smach_own')}/{ag(Rv,'smach_own')} (iter17 own 0.546/0.558). "
  f"P(large) AUC: hyb {F['auc_large']['hyb']}/{Rv['auc_large']['hyb']}, sib {F['auc_large']['sib']}/{Rv['auc_large']['sib']}, "
  f"own {F['auc_large']['own']}/{Rv['auc_large']['own']}, true_state {F['auc_large']['true_state']}/{Rv['auc_large']['true_state']}. "
  f"window-net rN: menu {rN(F,'menu')}/{rN(Rv,'menu')}, sib {rN(F,'smach_sib')}/{rN(Rv,'smach_sib')}, hyb {rN(F,'smach_hyb')}/"
  f"{rN(Rv,'smach_hyb')}, true_state {rN(F,'smach_true_state')}/{rN(Rv,'smach_true_state')}; PnL proxy Spearman menu {pS(F,'menu')}/"
  f"{pS(Rv,'menu')}, hyb {pS(F,'smach_hyb')}/{pS(Rv,'smach_hyb')}, true_state {pS(F,'smach_true_state')}/{pS(Rv,'smach_true_state')}. "
  f"pub coverage {F['pub_coverage_sco']}/{Rv['pub_coverage_sco']}. VERDICT: the siblings carry PART of the within-window size state "
  f"(sib / hyb PnL-proxy Spearman beat own-memory {pS(F,'smach_own')}/{pS(Rv,'smach_own')} and menu {pS(F,'menu')}/{pS(Rv,'menu')} on "
  f"both splits) but below the 0.75 agreement bar and ~60% of the true-state ceiling. {CIsent} Size PROXY/ceiling only (E[size], not "
  f"the executable tracker); pending X170 (W4/W5 admissibility); treated as other-trader market activity as the frozen rule already does.")

cat = s["catalog"]
new = {
 "X178": ("open", "panel iter17 information P1", "Score the frozen exam route (dc_exam14 side, dc_hazard14 presence, touch price) out of time on the public capture's own 10-31 / 11-01 day files on the collector clock (stable, +-9 ms/h). Needs the examiner's access ruling (footer-only row-group selection inside development blocks) + X170; not runnable by this agent. The clean out-of-time test of whether the side route transfers to the new regime."),
 "X179": ("open", "panel iter17 information P2", "Restamp the live Binance spot book with the same process's exchange-stamped USD-M + trade messages (spot/USD-M residual r=0.78; spot q90 42->9.6 ms after correction), pre-register '11c', score the 11-01 06-12 record with the cut-shift scan; build a minimal-latency recorder for the next dev blocks. Clock repair for the live route (condition 3 out of time)."),
 "X180": ("open", "panel iter17 information P3", "Re-stamp the CAPTURE's Binance book to exchange time in bursts (burst lag +6..13 ms median, opposite sign to the ~4 ms bookTicker lead), rebuild dcclock14/hazard14, refit conditions 2/3 once on 10-17..19 -> 10-20..22 + reverse, non-inferiority first. The condition-2 decision-clock gain is decided at tens of ms."),
 "X181": ("open", "panel iter17 information P4", "The size-class RATE as an Obsidian-tier weighted-volume controller on POOLED operator wV (no wallet reached $10M alone, all paid 50%, pooled $11.6-12.3M). Test: tier steps vs pooled/per-wallet wV crossings; daily large share vs projected pooled slack S(d) (Spearman, date-rotation null); config change-points on low-slack days; Wayback rule-change diffs. Development fee days only. The next pivot for the size RATE (vs this iteration's size STATE)."),
 "X182": ("tried", "panel iter17 mechanics P1", x182),
 "X183": ("open", "panel iter17 mechanics P2", "A stall-proof Binance clock for the live route: re-stamp every bookTicker by its arrival-order bracket [T_prev,T_next] (u strictly monotone in receive order), depth@100ms update-id anchors, an isolated recorder. Clean-feed frozen side already 0.78-0.80; 19% of 11-01 orders sit on a stalled feed (0.67-0.71). Clock repair; overlaps X179."),
 "X184": ("open", "panel iter17 mechanics P3", "Prove XM's 60-share class is post-only with a GTC counterfactual on the recorded event-level book (insert each XM-60 at t_post-150 ms; post-only predicts 0/274 takes, GTC predicts >=30%); then fit the XM-60 routing rule and replicate XM's resting stream. = X177 follow-on + X188."),
 "X185": ("open", "panel iter17 mechanics P4", "If the salt generator is recovered (JSC WeakRandom xorshift128+, carry-aware z3 SMT on 4-6 outputs), count its draws between a wallet's consecutive bursts = a direct measurement of the take coin's denominator. Self-test on synthetic JSC salts first. = X149 follow-on; 32-bit and V8 already excluded."),
 "X186": ("open", "panel iter17 assumptions P1", "Re-target conditions 5/7 for the post-T0 regime: score the frozen tracker on the 142 windows of the 10-31 development blocks and 11-01 06-12 (maker variance share 0.51-0.65 vs 0.165, corr(W,maker) 0.80-0.87, XM vs pooled 0.73-0.78); pre-register a two-stream tracker (taker trk_a + resting remainders + XM 60-share quote), fit 10-31 00-06, score 10-31 12-18 / 11-01 / 11-02. The regime-specific PnL route; overlaps X182/X133/X174."),
 "X187": ("open", "panel iter17 assumptions P2", "Is the 'new regime' a weekend mode? Every post-T0 development hour is 10-31 Sat / 11-01 Sun; pre-H weekends already show DS/GF maker shares 0.45-0.50 vs 0.29-0.38. Replicate census17 / regime_pnl31 on 11-02 00-06 / 12-18 (weekday dev blocks) when they end; regress pre-H day shares on weekday/weekend + BTC activity + crowd volume."),
 "X188": ("open", "panel iter17 assumptions P3", "Decode the 60-share class as a post-only quote with its own trigger (knee move toward o then o's ask steps up within the hold) and lifetime (from book traces); replica posts at L, decoded life, strict fills, queued behind operator size; per-window corr with XM's maker PnL. = X177 / X184."),
 "X189": ("open", "panel iter17 assumptions P4", "Run the exam route out of time on a development-only extract of the capture's 10-31 day file (examiner-made extract restricted to 00-06/12-18, or a footer-only row-group ruling). = X178; needs the examiner + X170."),
 "X190": ("open", "panel iter17 assumptions P5", "Make the presence unit an ORDER (taker submission at m-150 + maker postings from the book), not a fill second, before the next claim: on the 10-31 dev blocks split the frozen block-second presence gain by the role of each positive second (maker-only vs taker); the order-level knee hazard vs a book-aware baseline at the e cut (decision-clock gain +0.058 [0.050,0.065] already). = D1 / X146 / X72; the strongest route to flip condition 2."),
}
for k, (st, src, ev) in new.items():
    cat[k] = {"status": st, "source": src, "evidence": ev}
# update related items
def app(k, suffix):
    base = cat[k]["evidence"].split(" | Iteration 18")[0]  # strip any prior iteration-18 suffix, then re-add (idempotent)
    cat[k]["evidence"] = base + suffix
app("X169", f" | Iteration 18 (sib18): under the smach17 WITHIN-window S the siblings' public large prints carry PART of the state (S_hyb agree {ag(F,'smach_hyb')}/{ag(Rv,'smach_hyb')} vs own 0.556; PnL-proxy Spearman sib {pS(F,'smach_sib')}/{pS(Rv,'smach_sib')} vs own {pS(F,'smach_own')}/{pS(Rv,'smach_own')} vs menu {pS(F,'menu')}/{pS(Rv,'menu')}), short of the 0.75 bar and the true-state ceiling {pS(F,'smach_true_state')}/{pS(Rv,'smach_true_state')}.")
app("X170", " | Iteration 18: a reason to get the ruling: the size state is PARTLY recoverable from W4/W5 public large prints (X182), which would convert part of condition 5's size coin into a public lagged state IF they are 'other traders'.")
app("X66", f" | Iteration 18 (X182): W4/W5 confirmed-large (filled>=60) BUY prints carry part of the operator's within-window size state S (sib PnL-proxy Spearman {pS(F,'smach_sib')}/{pS(Rv,'smach_sib')} vs menu {pS(F,'menu')}/{pS(Rv,'menu')}).")

# dimensions
dim = s["dimensions"]
dim["own_decision_memory"]["best_indicator"] = f"S=side of last large order; recoverable from W4/W5 public large prints (S_hyb agree {ag(F,'smach_hyb')}/{ag(Rv,'smach_hyb')} with true S)"
dim["own_decision_memory"]["verdict"] = "drives"
dim["own_decision_memory"]["status"] = "proxy"  # the operator-level state is observed via the siblings' public prints
dim["operator_sibling_wallets"]["best_indicator"] = f"last W4/W5 large (>=60) print side = operator S ({ag(F,'smach_sib')}/{ag(Rv,'smach_sib')}); hybrid lifts P(large) AUC to {F['auc_large']['hyb']}/{Rv['auc_large']['hyb']}"
dim["operator_sibling_wallets"]["verdict"] = "drives"

# indicators ledger (idempotent: drop any prior iteration-18 sibling-state row)
s["indicators"] = [r for r in s.get("indicators", []) if not (isinstance(r, dict) and "S_hyb" in str(r.get("definition", "")))]
s.setdefault("indicators", []).append({
  "dimension": "own_decision_memory / operator_sibling_wallets",
  "definition": "S_hyb = size hysteresis state (side of last large order), replica own draws overwritten by W4/W5 public large (>=60) prints (block_ts+2s, shared txs excluded)",
  "event": "state value at each operator taker order; target = original-size large class (>=90)",
  "period": "VALIDATE (capture days 10-20..22, fit 10-20 / reverse)",
  "result": {"S_agreement_true": {"sib": [ag(F,'smach_sib'), ag(Rv,'smach_sib')], "hyb": [ag(F,'smach_hyb'), ag(Rv,'smach_hyb')], "own": [ag(F,'smach_own'), ag(Rv,'smach_own')]},
             "auc_large": {"hyb": [F['auc_large']['hyb'], Rv['auc_large']['hyb']], "true_state": [F['auc_large']['true_state'], Rv['auc_large']['true_state']]},
             "pnl_proxy_rN": {"menu": [rN(F,'menu'), rN(Rv,'menu')], "hyb": [rN(F,'smach_hyb'), rN(Rv,'smach_hyb')], "true_state": [rN(F,'smach_true_state'), rN(Rv,'smach_true_state')]}},
  "verdict": "drives (size STATE recoverable from public sibling prints); PnL proxy/ceiling only; pending X170"})

# components: size
sz = s["components"]["size"]
sz["description"] = (f"Original size is a large(>=90)/small class; the side of every large order is public (dc14 0.878). WHICH decisions "
  f"are large follows the operator's shared decision memory S (side of the last large order) + commitment E. Iteration 18 (sib18, "
  f"pre-registration 15): the siblings' public large prints (W4/W5 taker BUY filled>=60, lagged ~2 s, shared txs excluded) carry PART "
  f"of the within-window state S but do NOT fully synchronise it: S_pub agrees with the operator's true S on {ag(F,'smach_sib')}/"
  f"{ag(Rv,'smach_sib')} (public only), S_hyb {ag(F,'smach_hyb')}/{ag(Rv,'smach_hyb')} (own memory {ag(F,'smach_own')}/{ag(Rv,'smach_own')}), "
  f"below the 0.75 bar, coverage {F['pub_coverage_sco']}/{Rv['pub_coverage_sco']}. On the PnL proxy (window signed-net x payout vs window "
  f"PnL, Spearman) the public state beats own-memory and the menu on BOTH splits: sib {pS(F,'smach_sib')}/{pS(Rv,'smach_sib')}, hyb "
  f"{pS(F,'smach_hyb')}/{pS(Rv,'smach_hyb')} vs own {pS(F,'smach_own')}/{pS(Rv,'smach_own')} vs menu {pS(F,'menu')}/{pS(Rv,'menu')}, but "
  f"reaches only ~60% of the true-state ceiling {pS(F,'smach_true_state')}/{pS(Rv,'smach_true_state')} (class-oracle {pS(F,'class_oracle')}/"
  f"{pS(Rv,'class_oracle')}). {CIsent} So the size STATE is PARTLY a public lagged dimension (not a fully private coin); the undecoded "
  f"residual is the within-window commitment E and which of the shared-S decisions are drawn large. Ceiling/attainability result (E[size] proxy, not "
  f"the strict-fill tracker), pending the X170 ruling on W4/W5.")

# strategy statement: append size clause
s["strategy_statement"] = s["strategy_statement"].split(" || iteration18 (size):")[0] + (
  f" || iteration18 (size): the undecoded size STATE 'which side is the current large lean' is PARTLY recoverable from the sibling "
  f"wallets' (W4/W5) public large prints (PnL-proxy Spearman sib {pS(F,'smach_sib')}/{pS(Rv,'smach_sib')} vs own-memory "
  f"{pS(F,'smach_own')}/{pS(Rv,'smach_own')} vs menu {pS(F,'menu')}/{pS(Rv,'menu')}, both splits), but under the within-window PIT "
  f"definition it stays below the 0.75 agreement bar (hyb {ag(F,'smach_hyb')}/{ag(Rv,'smach_hyb')}) and ~60% of the true-state ceiling "
  f"{pS(F,'smach_true_state')}/{pS(Rv,'smach_true_state')}; the within-window coin and commitment E remain undecoded (pending X170).")

s.setdefault("target_metrics_notes", {})["iteration18"] = (
  f"target_metrics UNCHANGED (no executable candidate adopted; sib18 is a size PROXY/ceiling result, not the mix14 tracker). PIVOT "
  f"(pre-registration 15): the operator size state S read from the siblings' public large prints (W4/W5 filled>=60, 2 s lag, shared txs "
  f"excluded). PARTIAL. S agreement with the operator's within-window true S: sib {ag(F,'smach_sib')}/{ag(Rv,'smach_sib')}, hyb "
  f"{ag(F,'smach_hyb')}/{ag(Rv,'smach_hyb')} (iter17 own 0.546/0.558), below the 0.75 bar; pub coverage {F['pub_coverage_sco']}/"
  f"{Rv['pub_coverage_sco']}. PnL-proxy Spearman (window signed-net x payout vs PnL): sib {pS(F,'smach_sib')}/{pS(Rv,'smach_sib')}, hyb "
  f"{pS(F,'smach_hyb')}/{pS(Rv,'smach_hyb')} BEAT own {pS(F,'smach_own')}/{pS(Rv,'smach_own')} and menu {pS(F,'menu')}/{pS(Rv,'menu')} on "
  f"both splits, ~60% of the true-state ceiling {pS(F,'smach_true_state')}/{pS(Rv,'smach_true_state')} (class-oracle {pS(F,'class_oracle')}/"
  f"{pS(Rv,'class_oracle')}). P(large) AUC hyb {F['auc_large']['hyb']}/{Rv['auc_large']['hyb']} (own {F['auc_large']['own']}/"
  f"{Rv['auc_large']['own']}; true-state {F['auc_large']['true_state']}/{Rv['auc_large']['true_state']}). Signed-net rN hyb "
  f"{rN(F,'smach_hyb')}/{rN(Rv,'smach_hyb')} vs menu {rN(F,'menu')}/{rN(Rv,'menu')} (pre-registered bar rN>=menu+0.05 MET both splits). "
  f"{CIsent} Ceiling/attainability only; pending X170.")

# catalog_open snapshot
openids = [k for k, v in cat.items() if v.get("status") == "open"]
s["catalog_open_after_iteration18"] = sorted(openids, key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0))

# iterations entry (idempotent: drop any prior n==18)
s["iterations"] = [it for it in s["iterations"] if it.get("n") != 18]
s["iterations"].append({
  "n": 18, "minutes": None, "best_validate_score": 0.9132, "block_seconds_presence": 0.8701, "block_seconds_stronger_baseline": 0.8464,
  "side_accuracy": 0.8369, "pnl_corr": 0.5065, "pnl_corr_spearman": 0.4674,
  "paradigm": "Operator decision-memory size STATE read from the sibling wallets' (W4/W5) public large prints (a new data source): PARTIAL -- the siblings carry part of the within-window size state (PnL-proxy lift over own-memory/menu on both splits) but below the 0.75 agreement bar and ~60% of the true-state ceiling",
  "size_state_S_agreement_hyb": [ag(F, 'smach_hyb'), ag(Rv, 'smach_hyb')],
  "pnl_proxy_spearman_sib_vs_menu_vs_ceiling": {"sib": [pS(F, 'smach_sib'), pS(Rv, 'smach_sib')], "menu": [pS(F, 'menu'), pS(Rv, 'menu')], "true_state": [pS(F, 'smach_true_state'), pS(Rv, 'smach_true_state')]},
  "pnlS_gain_vs_menu_sib_boot": {"forward": F["gain_vs_menu_block_boot"]["smach_sib"], "reverse": Rv["gain_vs_menu_block_boot"]["smach_sib"]},
  "families": ["sibling public large prints as the operator's size-state input (pre-registration 15, X182 = panel mechanics P1)",
               "S agreement with the operator's within-window true S: sib / hybrid / own, both splits (0.49-0.61, below 0.75)",
               "replica P(large) AUC and PnL proxy under the hybrid/public state vs own-memory and the true-state ceiling",
               "catalog additions X178-X190 (panel iter17); dimensions own_decision_memory -> proxy, operator_sibling_wallets -> drives"]})
json.dump(s, open(f"{B}/state.json", "w"), indent=1)
print("updated state.json; open catalog:", len(openids))
print("X182 S_hyb agree", ag(F, 'smach_hyb'), ag(Rv, 'smach_hyb'), "| rN hyb vs menu", rN(F, 'smach_hyb'), rN(F, 'menu'))
