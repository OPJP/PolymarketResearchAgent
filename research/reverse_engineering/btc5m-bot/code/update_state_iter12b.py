"""Iteration 12 (late): X102 clone census result, the iteration entry's minutes, open list. Usage: python update_state_iter12b.py MINUTES"""
import os, json, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
P = _ROOT + "/research/reverse_engineering/btc5m-bot/state.json"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
s = json.load(open(P, encoding="utf-8"))
cl = json.load(open(f"{R}/clone12.json")); w5 = json.load(open(f"{R}/w5clone12.json"))
cat = s["catalog"]
cat["X102"] = {"status": "tried", "source": "panel iteration 11, information P3 (pre-signed peer census: clones of the same TypeScript ladder bot and siblings on other burst schedules)",
               "evidence": "Census of the 10-31 match-tx calldata (it9/cd9 + it10/cdall10, 152,576 orders; clone12.py inline, results/clone12.json): the operator's orders have sig_type 3, "
                           "sig length 317, zero builder and metadata (shared by 84k other orders: not distinctive); its distinctive marks are pre-signing (97.5-99.3% signed > 5 s before the "
                           "match, median 66-74 s), the burst phases (99.6-100% within +-3 s of -89.5 / +42.4 / +173.3 s; W4 37%) and same-ms copies (60-81%). Among 551 non-operator wallets with "
                           f">= 40 orders, {len(cl.get('presigned_candidates', []))}+ are mostly pre-signed but only ONE follows the burst schedule: 0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c "
                           f"(64 orders, 100% in-burst, median lag 42 s, 60% same-ms copies, all BUY, 47 maker-role); its signing ms sit {w5.get('sign_ms_gap_to_nearest_operator_order_ms_q')} ms "
                           f"(q10 / q50 / q90) from an operator order's, {w5.get('share_txs_with_operator_order')} of its txs hold an operator order, and its matches fall "
                           f"{w5.get('match_gap_to_nearest_operator_match_same_token_ms_q')} ms from an operator match on the same token ({w5.get('share_match_within_100ms_of_operator_same_token')} "
                           "within 100 ms): a fifth fan-out wallet of the same operator (a sibling, like W4), not an independent clone. No independent clone of the ladder bot exists on 10-31, so "
                           "steps 2-3 (clones' take behaviour, shared software state) have no subject; common-funding checks of the fifth wallet not run."}
jt = json.load(open(f"{R}/joint12.json"))
cat["X106"]["evidence"] += (" | Step 2 (joint12.py, results/joint12.json): P(both wallets decide on o) far exceeds the product of the single rates in every public-score bin (fit A scored C, "
                            f"DS-GF {jt['score_fit_A_on_C']['joint_excess']['DS-GF']['by_score_bin[bin, joint, product]']}; GF-XM {jt['score_fit_A_on_C']['joint_excess']['GF-XM']['by_score_bin[bin, joint, product]']}): "
                            "one operator-level decision fans out to several wallets. Step 3 (rerouting) is not identifiable on clean onsets (no operator decision within 600 ms by construction).")
cat["X107"]["evidence"] = cat["X107"].get("evidence", "") + (" | Iteration 12 note: the iteration-11 assumptions panel measured that only 6.6% of 196 cancelled remainders have a same-wallet "
                                                              "arrival within +-100 ms of the removal (17 vs 4 expected at +100-250 ms): cancel-then-send is not the TTL rule; the simulator part is not built.")
wk = json.load(open(f"{R}/w45chk12.json"))
hy0 = s["hypotheses"]; nx0 = max(int(h["id"][1:]) for h in hy0) + 1
hy0.append({"id": f"H{nx0}", "family": "leak check: operator's fourth / fifth wallets in the tape features", "description": "VALIDATE cells rebuilt with W4 / W5 prints removed; frozen presence, netflow and the tracker re-scored",
            "validate_metrics": wk, "verdict": "no effect (presence gain +0.0557 vs +0.0554; tracker 0.4756 / 0.4394 vs 0.4758 / 0.4404)"})
s["target_metrics_notes"]["iteration12_leak_check"] = ("W4 (0xd844...) and W5 (0x03b4...), the operator's fourth / fifth fan-out wallets, are not excluded from the frozen tape features; rebuilding "
                                                        f"the VALIDATE features without them leaves every metric unchanged (w45chk12.json: {json.dumps(wk)}).")
open_ids = sorted([k for k, v in cat.items() if v.get("status") == "open"], key=lambda k: (k[0], int(k[1:]) if k[1:].isdigit() else 0))
s["catalog_open_after_iteration12"] = open_ids
hy = s["hypotheses"]; nxt = max(int(h["id"][1:]) for h in hy) + 1
hy.append({"id": f"H{nxt}", "family": "clone census (X102)", "description": "burst-phase / pre-signing fingerprint of every wallet in the 10-31 calldata",
           "validate_metrics": {"operator": cl.get("operator"), "fifth_wallet": w5}, "verdict": "no independent clone; a fifth operator fan-out wallet 0x03b4c58b..."})
it = s["iterations"][-1]
assert it["n"] == 12
it["minutes"] = float(sys.argv[1]) if len(sys.argv) > 1 else it["minutes"]
for fam in ("clone census of the ladder fingerprint (X102)", "joint take across wallets (X106 step 2)", "leak check: W4 / W5 prints removed from the tape features"):
    if fam not in it["families"]:
        it["families"].append(fam)
s["data_sources"].append("Iteration 12: fingerprint census of the 10-31 match-tx calldata (it9/cd9 + it10/cdall10): burst phase, pre-signing lag, same-ms copies per wallet")
json.dump(s, open(P, "w", encoding="utf-8"), indent=1)
print("open", len(open_ids), open_ids)
