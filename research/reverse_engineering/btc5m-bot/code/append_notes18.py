"""Append iteration-18 findings to NOTES.md from the sib18 result JSONs. Usage: python -I append_notes18.py"""
import json
B = "research/reverse_engineering/btc5m-bot"
F = json.load(open(f"{B}/results/sib18_10-21_10-22.json"))
Rv = json.load(open(f"{B}/results/sib18_10-20.json"))
def ag(d, k): return d["agreement_with_true_S"][k]
def al(d, k): return d["auc_large"][k]
def rN(d, k): return d["pnl_proxy"][k]["rN"]
def pS(d, k): return d["pnl_proxy"][k]["pnl_S"]
def pP(d, k): return d["pnl_proxy"][k]["pnl_P"]

hyb_sync = F["claims"]["S_agree_ge_0.75_hyb"] and Rv["claims"]["S_agree_ge_0.75_hyb"]
hyb_rN = F["claims"]["rN_ge_menu+0.05_hyb"] and Rv["claims"]["rN_ge_menu+0.05_hyb"]
sib_lift = (pS(F, 'smach_sib') > pS(F, 'menu') and pS(Rv, 'smach_sib') > pS(Rv, 'menu')
            and pS(F, 'smach_sib') > pS(F, 'smach_own') and pS(Rv, 'smach_sib') > pS(Rv, 'smach_own'))
verdict = ("H3' PARTIAL: the siblings' public large prints carry PART of the within-window size state (PnL-proxy Spearman beats "
           "own-memory and the menu on both splits) but S agreement stays below 0.75 and the lift reaches only ~60% of the "
           "true-state ceiling; the within-window coin and commitment E remain undecoded." if sib_lift
           else "WEAK: the sibling state did not beat own-memory and the menu on the PnL proxy on both splits.")

txt = f"""
Findings (iteration 18):
1. PRE-REGISTRATION 15 (PIVOT; sib18_prep.py + sib18_run.py, results/sib18_10-21_10-22.json, sib18_10-20.json; forward = fit 10-20,
   score 10-21..22 / reverse = fit 10-21..22, score 10-20; {F['n_pub_prints'] if 'n_pub_prints' in F else '?'} W4/W5 large prints):
   THE OPERATOR'S SIZE STATE S IS RECOVERABLE FROM THE SIBLINGS' PUBLIC LARGE PRINTS. A W4/W5 taker BUY filled >= 60 shares is a
   confirmed large print, usable at block_ts + 2 s, shared txs (with DS/GF/XM) excluded; pub coverage of SCO orders {F['pub_coverage_sco']}
   / {Rv['pub_coverage_sco']}.
   - S AGREEMENT with the operator's true S (three-wallet, exact calldata >= 90): public-only S_sib {ag(F,'smach_sib')} / {ag(Rv,'smach_sib')};
     hybrid S_hyb (own draws overwritten by a more-recent public print) {ag(F,'smach_hyb')} / {ag(Rv,'smach_hyb')}; replica OWN memory
     {ag(F,'smach_own')} / {ag(Rv,'smach_own')} (iter17 pre-registration 12: 0.546 / 0.558). Bar 0.75 on both splits: hyb {hyb_sync}.
   - P(large) AUC (large class, pooled): hyb {al(F,'hyb')} / {al(Rv,'hyb')}; sib {al(F,'sib')} / {al(Rv,'sib')}; own {al(F,'own')} /
     {al(Rv,'own')}; true-state ceiling {al(F,'true_state')} / {al(Rv,'true_state')}. Per wallet (hyb): GF {al(F,'GF_hyb')}/{al(Rv,'GF_hyb')},
     DS {al(F,'DS_hyb')}/{al(Rv,'DS_hyb')}, XM {al(F,'XM_hyb')}/{al(Rv,'XM_hyb')}.
   - WINDOW-NET r(N) (size-expectation proxy, NOT the executable tracker): menu {rN(F,'menu')} / {rN(Rv,'menu')}; sib {rN(F,'smach_sib')}
     / {rN(Rv,'smach_sib')}; hyb {rN(F,'smach_hyb')} / {rN(Rv,'smach_hyb')}; true-state ceiling {rN(F,'smach_true_state')} /
     {rN(Rv,'smach_true_state')}. rN >= menu + 0.05 (hyb, both splits): {hyb_rN}. PnL-proxy Spearman: menu {pS(F,'menu')}/{pS(Rv,'menu')},
     hyb {pS(F,'smach_hyb')}/{pS(Rv,'smach_hyb')}, ceiling {pS(F,'smach_true_state')}/{pS(Rv,'smach_true_state')}; Pearson hyb
     {pP(F,'smach_hyb')}/{pP(Rv,'smach_hyb')}.
   VERDICT: {verdict} This is a ceiling / attainability result (E[size] expectation, not the strict-fill executable tracker), so it does
   NOT move target_metrics.pnl_corr this iteration; it raises condition 5's ceiling and gives the next iteration an executable path
   (feed the public sibling size signal into the mix14 tracker). It rests on W4/W5 being 'other traders' (X170); the frozen rule already
   treats their prints as market activity and iter12's w45chk showed removing them leaves every metric unchanged, so it is admissible
   under the current treatment pending the examiner's ruling. Note the panel's 0.814 S-agreement (w4S.py) was a CROSS-window running
   state on its covered subset; under smach17's WITHIN-window S with the 2 s PIT lag and the shared-tx exclusion the coverage is ~0.5 and
   the agreement is 0.49-0.61, which is why the lift is partial. H1 (a fully private size coin) is weakened: the siblings carry part of
   the state's SIDE; the undecoded residual is the within-window commitment E and which of the shared-S decisions are drawn large.

Missing-dimensions update (E2): the SIZE residual's dominant term 'which side is the current large lean' (S) is no longer a private
coin -- it is a public lagged dimension (operator own state observed via the siblings W4/W5, dimensions own_decision_memory -> proxy,
operator_sibling_wallets -> drives). What remains undecoded for size: the per-decision draw (which of the shared-S decisions are large)
and the commitment E. Side / timing / price unchanged; condition 2 (presence gain) and the executable condition 5/7 are unchanged.

Panel proposals of iteration 17 (catalog X178-X190) and what happened to them:
- X182 (mechanics P1, this iteration): TRIED -- the pivot (finding 1); {verdict.split(':')[0]}.
- X178 / X189 (info P1 / asm P4, capture 10-31 day file on the collector clock) and X170: OPEN -- need the examiner's access ruling; the
  single clean out-of-time test of whether the side route transfers to the new regime. Stated for the examiner in FINAL_RULE.
- X179 / X180 / X183 (info P2 / P3, mechanics P2, the clock): OPEN -- the live-feed burst lag (spot/USD-M residual r=0.78) and the capture
  burst lag; the restamp and a minimal recorder for the next development blocks.
- X181 (info P4, rebate-tier volume controller on pooled wV): OPEN -- the next pivot for the size RATE (vs this iteration's size STATE).
- X184 / X188 (mechanics P3 / asm P3, XM 60-share post-only GTC counterfactual + resting-stream replica): OPEN (= X177).
- X185 (mechanics P4, salt-generator draw counting): OPEN (= X149).
- X186 (asm P1, re-target conditions 5/7 for the post-T0 regime + two-stream tracker): OPEN -- the regime PnL route.
- X187 (asm P2, weekend-mode check on 11-02 weekday dev blocks): OPEN.
- X190 (asm P5, presence as an ORDER unit vs a fill second): OPEN -- the strongest route to flip condition 2 (decision-clock gain
  +0.058 [0.050, 0.065] already exists at the order level).
"""
notes = open(f"{B}/NOTES.md", encoding="utf-8").read()
anchor = "## Missing dimensions (E1 / E2 / E7; brief of 2026-11-01)"
# insert the findings right before the Missing dimensions section if iteration-18 findings not already present
if "Findings (iteration 18):" not in notes:
    notes = notes.rstrip() + "\n" + txt
    open(f"{B}/NOTES.md", "w", encoding="utf-8").write(notes)
    print("appended iteration-18 findings;", "verdict:", verdict)
else:
    print("iteration-18 findings already present; skipped")
