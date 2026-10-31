"""Part (2c): does the A1 outcome depend on the PnL field? Re-run the full screen
(own code) on every field of the user-pnl series and on a de-spiked economic
series (one-day mark-to-market spikes that reverse the next day are netted).
A wallet that passes under any alternative is listed for review."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RepoCacheRO, daily_pnl, holm, load_a1, reasons, screen_metrics, user_pnl_url  # noqa: E402

a1 = load_a1()
W = [w["wallet"] for w in a1["wallets"]]
rc = RepoCacheRO()
pts = {w: ((json.loads(rc.get_raw(user_pnl_url(w))[1]) or {}).get("data") or {}).get("points") or [] for w in W}


def despike(x: np.ndarray, k: float = 6.0):
    """Net day pairs (t, t+1) with opposite signs, both |x| > k * robust sd, that cancel within 25%."""
    x = x.copy()
    if len(x) < 10:
        return x, 0
    med = np.median(x)
    rsd = 1.4826 * np.median(np.abs(x - med))
    rsd = rsd if rsd > 0 else np.std(x)
    n = 0
    t = 0
    while t < len(x) - 1:
        a, b = x[t], x[t + 1]
        if rsd > 0 and a * b < 0 and min(abs(a), abs(b)) > k * rsd and abs(a + b) < 0.25 * max(abs(a), abs(b)):
            x[t + 1] = a + b
            x[t] = 0.0
            n += 1
            t += 2
        else:
            t += 1
    return x, n


variants = ["economic_pnl", "trade_pnl", "position_pnl", "settled_pnl", "realized_pnl", "economic_despiked"]
res = {}
for v in variants:
    ms = {}
    for w in W:
        field = "economic_pnl" if v == "economic_despiked" else v
        _, x = daily_pnl(pts[w], field=field)
        nspk = 0
        if v == "economic_despiked":
            x, nspk = despike(x)
        if len(x) == 0:
            ms[w] = {"n": 0}
            continue
        m = screen_metrics(x, boot=False)
        m["spikes_netted"] = nspk
        ms[w] = m
    pv = [ms[w]["p_pre"] if ms[w].get("pre_days", 0) >= 60 else 1.0 for w in W]
    ph = holm(pv)
    passed = []
    for w, p in zip(W, ph):
        m = ms[w]
        m["p_holm"] = float(p)
        if not m.get("n"):
            m["reasons"] = ["no history"]
            continue
        # bootstrap only where it can matter (everything else passes)
        pre_r = reasons({**m, "p_boot_pre": 0.0}, float(p))
        if not pre_r:
            field = "economic_pnl" if v == "economic_despiked" else v
            _, x = daily_pnl(pts[w], field=field)
            if v == "economic_despiked":
                x, _ = despike(x)
            from common import stationary_bootstrap_p
            m["p_boot_pre"] = stationary_bootstrap_p(x[: m["pre_days"]], 20000)
        m["reasons"] = reasons(m, float(p))
        if not m["reasons"]:
            passed.append(w)
    res[v] = {"passed": passed, "metrics": ms}
    print(f"{v:20s} passes: {len(passed)}", flush=True)

base = set(res["economic_pnl"]["passed"])
rank = {w["wallet"]: (w["rank"], w["name"]) for w in a1["wallets"]}
print("recorded A1 passes == my economic_pnl passes:", base == set(a1["evidence"]["derived"]["a1_pass"]))
extra = {}
for v in variants[1:]:
    for w in res[v]["passed"]:
        if w not in base:
            extra.setdefault(w, []).append(v)
    lost = base - set(res[v]["passed"])
    print(f"  {v}: extra passes {[rank[w][0] for w in res[v]['passed'] if w not in base]}  lost {sorted(rank[w][0] for w in lost)}")
print("wallets passing only under an alternative series:")
for w, vs in extra.items():
    me = res["economic_pnl"]["metrics"][w]
    print(" ", rank[w], w, vs, "economic reasons:", me.get("reasons"))
spk = [(rank[w][0], w, res["economic_despiked"]["metrics"][w].get("spikes_netted", 0)) for w in W if res["economic_despiked"]["metrics"][w].get("spikes_netted")]
print("wallets with netted spike pairs:", len(spk))
# near-pass under alternatives: fail exactly one check
for v in variants:
    one = [(rank[w][0], rank[w][1], res[v]["metrics"][w]["reasons"]) for w in W if len(res[v]["metrics"][w].get("reasons", [])) == 1]
    print(f"  {v}: fail-exactly-one: {len(one)}")
(OUT / "alt_series.json").write_text(json.dumps({v: {"passed": res[v]["passed"], "reasons": {w: res[v]["metrics"][w].get("reasons") for w in W},
                                                    "spikes": {w: res[v]["metrics"][w].get("spikes_netted", 0) for w in W}} for v in variants}, indent=0))
