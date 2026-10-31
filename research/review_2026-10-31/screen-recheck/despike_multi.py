"""Part (2d): broader artifact check. Net 2-3 day episodes whose first day is a
>= K robust-sd move and whose sum cancels to within 25% of the largest move;
re-run the full screen on all 500 (own code) and list outcome changes."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RepoCacheRO, daily_pnl, holm, load_a1, reasons, reason_codes, screen_metrics, stationary_bootstrap_p, user_pnl_url

def despike(x, k):
    x = x.copy(); n = 0
    if len(x) < 10: return x, 0
    rsd = 1.4826 * np.median(np.abs(x - np.median(x))) or np.std(x)
    t = 0
    while t < len(x) - 1:
        done = False
        if abs(x[t]) > k * rsd:
            for L in (2, 3):
                seg = x[t:t + L]
                if len(seg) < L: break
                if np.max(np.abs(seg[1:])) > k * rsd and abs(seg.sum()) < 0.25 * np.max(np.abs(seg)):
                    s = seg.sum(); x[t:t + L] = 0; x[t + L - 1] = s; n += 1; t += L; done = True; break
        if not done: t += 1
    return x, n

a1 = load_a1(); WR = a1["wallets"]; W = [w["wallet"] for w in WR]; rec = {w["wallet"]: w for w in WR}
rc = RepoCacheRO()
X = {w: daily_pnl(((json.loads(rc.get_raw(user_pnl_url(w))[1]) or {}).get("data") or {}).get("points") or [])[1] for w in W}
for K in (4.0, 6.0):
    M = {}; ns = {}
    for w in W:
        if len(X[w]) == 0: continue
        y, ns[w] = despike(X[w], K); M[w] = screen_metrics(y, boot=False); M[w]["_y"] = y
    ph = dict(zip(W, holm([M[w]["p_pre"] if w in M and M[w]["pre_days"] >= 60 else 1.0 for w in W])))
    passed = []
    for w in M:
        if not reasons({**M[w], "p_boot_pre": 0.0}, float(ph[w])):
            M[w]["p_boot_pre"] = stationary_bootstrap_p(M[w]["_y"][:M[w]["pre_days"]], 20000)
            if not reasons(M[w], float(ph[w])): passed.append(w)
    base = set(a1["evidence"]["derived"]["a1_pass"])
    print(f"K={K}: wallets with netted episodes {sum(1 for v in ns.values() if v)}; passes {len(passed)}; new {[(rec[w]['rank'], rec[w]['name'], reason_codes(rec[w]['stage_a1_reasons'])) for w in passed if w not in base]}; lost {[rec[w]['rank'] for w in base if w not in passed]}")
    one = [(rec[w]['rank'], rec[w]['name'], reasons({**M[w], 'p_boot_pre': M[w].get('p_boot_pre', 0.0)}, float(ph[w]))) for w in M if len(reasons({**M[w], 'p_boot_pre': M[w].get('p_boot_pre', 0.0)}, float(ph[w]))) == 1 and ns[w]]
    print("   fail exactly one check after netting (and had episodes):", one)
