"""Prepend an iteration-18 paragraph to FINAL_RULE.md and refresh the component-tag line, from the sib18 JSONs.
Usage: python -I prepend_final18.py"""
import json
B = "research/reverse_engineering/btc5m-bot"
F = json.load(open(f"{B}/results/sib18_10-21_10-22.json"))
Rv = json.load(open(f"{B}/results/sib18_10-20.json"))
def ag(d, k): return d["agreement_with_true_S"][k]
def al(d, k): return d["auc_large"][k]
def rN(d, k): return d["pnl_proxy"][k]["rN"]
def pS(d, k): return d["pnl_proxy"][k]["pnl_S"]
sync = F["claims"]["S_agree_ge_0.75_hyb"] and Rv["claims"]["S_agree_ge_0.75_hyb"]
liftrN = F["claims"]["rN_ge_menu+0.05_hyb"] and Rv["claims"]["rN_ge_menu+0.05_hyb"]

para = (f"""# btc5m-bot: frozen rule (iteration 18: UNCHANGED executable rule from iteration 14; this iteration decodes the SIZE STATE as a public lagged dimension)

Iteration 18 in one paragraph (PIVOT; no executable candidate adopted; code/final_rule.py and target_metrics are UNCHANGED). New DATA
SOURCE: the sibling wallets W4 / W5. The one undecoded quantity that bounds conditions 5 and 7 is WHICH decisions are large; iteration
17 drove the size state S (side of the last large order) from a replica's OWN draws and it did not synchronize with the operator
(agreement 0.55), so the class selection looked like a private coin. This iteration (pre-registration 15, sib18) reads S from the
SIBLINGS' public large prints instead: a W4 / W5 taker BUY filled >= 60 shares is a confirmed large print, public on chain within ~2 s,
shared txs excluded. RESULT (forward = fit 10-20 / score 10-21..22; reverse), PARTIAL: S read from the siblings agrees with the
operator's WITHIN-window true S on {ag(F,'smach_sib')} / {ag(Rv,'smach_sib')} (public only) and {ag(F,'smach_hyb')} /
{ag(Rv,'smach_hyb')} (hybrid: own draws overwritten by a more-recent public print), against 0.556 from own memory -- below the 0.75
bar, coverage ~0.5 (the panel's 0.814 was a CROSS-window state on its covered subset). On the PnL proxy (window signed-net x payout vs
window PnL, Spearman) the public sibling state BEATS own-memory and the menu on BOTH splits: sib {pS(F,'smach_sib')} /
{pS(Rv,'smach_sib')}, hyb {pS(F,'smach_hyb')} / {pS(Rv,'smach_hyb')} vs own {pS(F,'smach_own')} / {pS(Rv,'smach_own')} vs menu
{pS(F,'menu')} / {pS(Rv,'menu')}, but reaches only ~60% of the true-state ceiling {pS(F,'smach_true_state')} / {pS(Rv,'smach_true_state')}
(class-oracle {pS(F,'class_oracle')} / {pS(Rv,'class_oracle')}); the hybrid P(large) AUC is {al(F,'hyb')} / {al(Rv,'hyb')} (own
{al(F,'own')} / {al(Rv,'own')}; ceiling {al(F,'true_state')} / {al(Rv,'true_state')}). So the size STATE 'which side is the current
large lean' is PARTLY a public lagged dimension (the operator's decision memory, leaked by the siblings), not a fully private coin, but
the within-window coin and commitment E remain undecoded. This is a VALIDATE ceiling / attainability result (an E[size] expectation
proxy, not the strict-fill executable tracker), so it does not move target_metrics.pnl_corr this iteration; it raises condition 5's
ceiling and points the next iteration at feeding the public sibling signal into the mix14 tracker. It rests on W4 / W5 being 'other
traders' (X170, pending the examiner's ruling): the frozen rule already treats their prints as market activity and removing them leaves
every metric unchanged (iter12). Pre-registration 15 scorecard: the rN-lift bar (window-net r >= menu + 0.05 on both splits) is MET by
the public and the hybrid state ({rN(F,'smach_sib')} / {rN(Rv,'smach_sib')} vs menu {rN(F,'menu')} / {rN(Rv,'menu')}); the S-agreement
bar (>= 0.75) is NOT met. TAG: size = VALIDATE-only (the executable per-wallet menu rate is unchanged); the sibling-state enhancement
is a hypothesis pending X170.

""")
md = open(f"{B}/FINAL_RULE.md", encoding="utf-8").read()
if "Iteration 18 in one paragraph" not in md:
    # replace the old top title line with the new para (keep everything from 'Iteration 17 in one paragraph' onward)
    marker = "\nIteration 17 in one paragraph"
    i = md.index(marker)
    md = para + md[i + 1:]
    open(f"{B}/FINAL_RULE.md", "w", encoding="utf-8").write(md)
    print("prepended iteration-18 paragraph; sync", sync, "liftrN", liftrN)
else:
    print("iteration-18 paragraph already present; skipped")
