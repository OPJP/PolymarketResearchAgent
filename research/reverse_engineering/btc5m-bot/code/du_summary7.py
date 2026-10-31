"""Iteration 7: pool the side.decision_units of every evaluate() chunk run in iteration 7 (VALIDATE 2-h chunks)."""
import os, json, glob
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
tot = {}
chunks = []
for p in sorted(glob.glob(_ROOT + "/.cache/re/btc5m-bot/eval_it7_17*.log")):
    s = open(p).read(); i = s.find("{")
    try:
        d = json.loads(s[i:])
    except Exception:
        continue
    du = d["side"].get("decision_units") or {}
    chunks.append(os.path.basename(p)[9:19])
    for w, v in du.items():
        t = tot.setdefault(w, {"orders": 0, "ok": 0.0, "base_ok": 0.0, "win": 0, "win_ok": 0.0})
        n = v.get("taker_orders") or 0
        t["orders"] += n; t["ok"] += n * (v.get("accuracy_per_order") or 0); t["base_ok"] += n * (v.get("baseline_market_only_per_order") or 0)
        nw = v.get("n_windows_scored") or 0
        if nw:
            t["win"] += nw; t["win_ok"] += nw * (v.get("accuracy_per_one_sided_window_first_decision") or 0)
res = {"chunks": chunks, "by_wallet": {w: {"taker_orders": t["orders"], "accuracy_per_order": round(t["ok"] / t["orders"], 4) if t["orders"] else None,
                                           "baseline_market_only_per_order": round(t["base_ok"] / t["orders"], 4) if t["orders"] else None,
                                           "one_sided_windows_scored": t["win"], "accuracy_per_one_sided_window": round(t["win_ok"] / t["win"], 4) if t["win"] else None}
                                       for w, t in tot.items()}}
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/side_decision_units7.json", "w"), indent=1)
print(json.dumps(res))
