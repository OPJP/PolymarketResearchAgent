"""Examiner r1: aggregate the frozen evaluate() outputs of the 16 lot chunks (counts-weighted where the output allows it; per-chunk
AUCs listed, since AUCs do not average -- the pooled AUCs come from an_presence.py / an_selection.py). Usage: python an_evalagg.py OUT_JSON"""
import os, sys, json, glob
ARGS = sys.argv[1:]
ROOT = os.getcwd()
import numpy as np
EX = f"{ROOT}/.cache/exam/btc5m-bot"
LOT = [(1792713600, 1792800000), (1792886400, 1792972800), (1793059200, 1793145600), (1793232000, 1793318400)]


def g(d, *ks):
    for k in ks:
        d = (d or {}).get(k) if isinstance(d, dict) else None
    return d


def main(out_json):
    E = []
    for p in sorted(glob.glob(f"{EX}/chunks/*_*/evaluate.json")):
        a, b = map(int, os.path.basename(os.path.dirname(p)).split("_"))
        if any(x <= a < y for x, y in LOT):
            E.append((a, b, json.load(open(p))))
    out = {"chunks": len(E), "errors": [(a, e.get("historical_error")) for a, b, e in E if e.get("historical_error")],
           "elapsed_s_total": round(sum(e["_exam"]["elapsed_s"] for _, _, e in E), 1), "peak_mb_max": max(e["_exam"]["peak_working_set_mb"] for _, _, e in E),
           "windows": sum(e.get("windows", 0) for _, _, e in E), "cluster_fills": sum(e.get("cluster_fills", 0) for _, _, e in E)}
    out["per_chunk_target_metrics"] = {str(a): {k: e["target_metrics"].get(k) for k in ("presence_auc", "presence_baseline", "selection_auc", "selection_baseline", "side_accuracy",
                                                                                     "side_accuracy_block_clock", "side_baseline", "price_within_tick", "pnl_corr_pearson", "pnl_corr_spearman",
                                                                                     "presence_decision_clock_auc", "presence_decision_clock_baseline", "share_one_sided_windows")} for a, b, e in E}
    # decision-clock side, weighted by matched orders
    num = den = 0; byw = {}; orders = 0; placebo = []
    for _, _, e in E:
        s = e.get("side_decision_clock") or {}
        if s.get("matched"):
            num += s["accuracy_per_order"] * s["matched"]; den += s["matched"]; orders += s["orders"]
            for w, (acc, n) in (s.get("by_wallet") or {}).items():
                byw.setdefault(w, [0, 0]); byw[w][0] += acc * n; byw[w][1] += n
            placebo.append(s.get("placebo_m_minus_plus_3s"))
    out["side_decision_clock"] = {"accuracy_per_order": round(num / den, 4) if den else None, "matched": den, "orders": orders,
                                  "match_coverage": round(den / orders, 4) if orders else None, "by_wallet": {w: round(v[0] / v[1], 4) for w, v in byw.items()},
                                  "placebo_m_pm_3s_per_chunk": placebo}
    gx = {}
    for _, _, e in E:
        for k, (acc, n) in ((g(e, "side_decision_clock", "by_globex_session") or {}).items()):
            if acc is not None and n:
                gx.setdefault(k, [0, 0]); gx[k][0] += acc * n; gx[k][1] += n
    out["side_decision_clock"]["by_globex_session"] = {k: [round(v[0] / v[1], 4), v[1]] for k, v in gx.items()}
    # block-clock side per one-sided second
    num = den = 0; numb = 0
    for _, _, e in E:
        y = g(e, "side", "y") or {}
        if y.get("n_seconds"):
            num += y["accuracy_side_model"] * y["n_seconds"]; numb += y["baseline_market_only_model"] * y["n_seconds"]; den += y["n_seconds"]
    out["side_block_clock"] = {"accuracy": round(num / den, 4) if den else None, "baseline_market_only": round(numb / den, 4) if den else None, "n_seconds": den}
    # price (calldata touch), weighted
    num = den = 0
    for _, _, e in E:
        c = g(e, "price", "calldata_touch") or {}
        if c.get("n_taker_orders"):
            num += c["within_1tick_touch"] * c["n_taker_orders"]; den += c["n_taker_orders"]
    out["price_calldata_touch"] = {"within_1tick": round(num / den, 4) if den else None, "n_taker_orders": den}
    # B1 ladder check
    num = den = 0
    for _, _, e in E:
        b1 = e.get("order_generation_b1") or {}
        if b1.get("orders"):
            num += b1["share_signed_in_predicted_batches"] * b1["orders"]; den += b1["orders"]
    out["b1_share_signed_in_predicted_batches"] = round(num / den, 4) if den else None
    # strict 30-share replica and trackers: sums
    for key, path in (("strict30", ("outcome", "strict_fill_backtest")), ("tracker_mix14_a", ("outcome", "exposure_tracker", "mix14_a")), ("tracker_avg_a", ("outcome", "exposure_tracker", "avg_a"))):
        pn = us = 0.0; nf = 0
        for _, _, e in E:
            x = g(e, *path) or {}
            if x.get("rule_usd"):
                pn += x["rule_pnl_before_rebates"]; us += x["rule_usd"]; nf += x["rule_fills"]
        out[key] = {"fills": nf, "usd": round(us, 1), "pnl_before_rebates": round(pn, 1), "return_before_rebates": round(pn / us, 4) if us else None}
    # side applicability as reported by evaluate (per chunk, windows-weighted)
    sc = {}
    for _, _, e in E:
        for w, v in (e.get("side_condition_by_wallet") or {}).items():
            sc.setdefault(w, [0, 0]); sc[w][0] += v["share_one_sided_windows"] * v["windows"]; sc[w][1] += v["windows"]
    out["side_condition_by_wallet"] = {w: {"share_one_sided_windows": round(v[0] / v[1], 4), "windows": v[1]} for w, v in sc.items()}
    out["live_components"] = {k: [e.get(k) for _, _, e in E][:1] for k in ("side_live_decision", "presence_live_decision")}
    out["wallet_return_before_rebates_per_chunk"] = [g(e, "outcome", "wallet_return_before_rebates") for _, _, e in E]
    json.dump(out, open(out_json, "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in out.items() if k != "per_chunk_target_metrics"}, indent=1, default=str))


if __name__ == "__main__":
    main(ARGS[0])
