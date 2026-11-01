"""iteration 16, X187 step 2 (light): the cluster's BTC 4h ladder as a quote. The 400-share size is the cluster's (purity
1.00, n 19, code16/purity_4h.py). From the shared recorder's top-10 books (clob_crypto 'q', server ms) of the BTC 4h windows
of a development span, every +400 size increase at a bid level of either outcome is a cluster add. For each add: the Up
mid just before it, the posture F_up = Phi((CL - K) / (k sigma_fut sqrt(tau))) (Chainlink report stamped <= t - 1,432 ms,
Gamma priceToBeat, Binance USD-M 300-s sigma, k 1.0 / 2.0 / 4.0), the cheaper token, and the add's price relative to the
token's best bid and mid.
    python q4h.py <a> <b>"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(HERE.parent / "code14"))
import final_rule as fr  # noqa: E402
from lagged_quote import fut_mid, at, sec_sigma, cl_source  # noqa: E402

a, b = int(sys.argv[1]), int(sys.argv[2])
from polyrea.workflows.updown_study import fetch_windows  # noqa: E402
slugs = [f"btc-updown-4h-{s}" for s in range(a - a % 14400, b, 14400)]
raw = fetch_windows(slugs)
info, K = {}, {}
for m in raw.values():
    t = json.loads(m["clobTokenIds"]) if isinstance(m.get("clobTokenIds"), str) else m["clobTokenIds"]
    o = json.loads(m["outcomes"]) if isinstance(m.get("outcomes"), str) else m["outcomes"]
    u, d = str(t[o.index("Up")]), str(t[o.index("Down")])
    info[u] = (m["slug"], 1, u); info[d] = (m["slug"], 0, u)
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None:
            K[m["slug"]] = float(v)
prev, mids, adds = {}, {}, []
for r in fr._iter_live_xq(a, b, set(info)):
    if r.get("k") != "q" or str(r.get("a")) not in info or not r.get("s"):
        continue
    tk = str(r["a"]); s = int(r["s"])
    bids = {round(float(p), 3): float(z) for p, z in (r.get("b") or [])}
    askd = {round(float(p), 3): float(z) for p, z in (r.get("o") or [])}
    if bids and askd:
        bb, ba = max(bids), min(askd)
        mids.setdefault(tk, []).append((s, (bb + ba) / 2, bb))
        if info[tk][1] == 1:  # the Up book also shows the Down bids as Up asks (Down bid q = Up ask 1 - q)
            dn = [k for k, v in info.items() if v[0] == info[tk][0] and v[1] == 0]
            if dn:
                mids.setdefault(dn[0], []).append((s, 1 - (bb + ba) / 2, 1 - ba))
    old = prev.get(tk)
    if old is not None:
        ob, oa = old
        for p, z in bids.items():
            if abs((z - ob.get(p, 0.0)) - 400.0) < 0.02:
                adds.append((tk, s, p))
        if info[tk][1] == 1:
            dn = [k for k, v in info.items() if v[0] == info[tk][0] and v[1] == 0]
            for p, z in askd.items():
                if dn and abs((z - oa.get(p, 0.0)) - 400.0) < 0.02:
                    adds.append((dn[0], s, round(1 - p, 3)))
    prev[tk] = (bids, askd)
ser = {}
for tk, v in mids.items():
    v.sort(); ser[tk] = (np.array([x[0] for x in v], np.int64), np.array([x[1] for x in v]), np.array([x[2] for x in v]))
A = pd.DataFrame(adds, columns=["tok", "s", "p"])
A["slug"] = A.tok.map(lambda t: info[t][0]); A["is_up"] = A.tok.map(lambda t: info[t][1]); A["up_tok"] = A.tok.map(lambda t: info[t][2])
mid_up = np.full(len(A), np.nan); bb_tok = np.full(len(A), np.nan); mid_tok = np.full(len(A), np.nan)
for i, (tk, u, s) in enumerate(zip(A.tok, A.up_tok, A.s)):
    if u in ser:
        mid_up[i] = at(ser[u][0], ser[u][1], np.array([s - 1]))[0]
    if tk in ser:
        bb_tok[i] = at(ser[tk][0], ser[tk][2], np.array([s - 1]))[0]
        mid_tok[i] = at(ser[tk][0], ser[tk][1], np.array([s - 1]))[0]
A["mid_up"], A["bb"], A["mid_tok"] = mid_up, bb_tok, mid_tok
E, M = fut_mid(a - 900, b)
sig = sec_sigma(E, M, 300)
t = A.s.to_numpy(np.int64)
clv = cl_source.cl_values(sorted(set(((t - 1432) // 1000).tolist())), allow_sealed=False, fetch=False)
cl = pd.Series((t - 1432) // 1000).map(clv).to_numpy(float)
st = A.slug.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
tau = np.maximum(st + 14400 - t / 1000, 1.0)
s0 = sig.reindex(t // 1000).to_numpy(float)
kk = A.slug.map(K).to_numpy(float)
y = A.is_up.to_numpy() == 1
ok = np.isfinite(A.mid_up.to_numpy()) & np.isfinite(cl) & np.isfinite(s0) & np.isfinite(kk)
out = {"span": [a, b], "adds": int(len(A)), "scored": int(ok.sum()), "windows": sorted(set(A.slug))}
for k in (1.0, 2.0, 4.0):
    F = norm.cdf((cl - kk) / (k * s0 * np.sqrt(tau)))
    out[f"posture_k{k}"] = round(float(((F > A.mid_up.to_numpy()) == y)[ok].mean()), 3)
out["cheaper"] = round(float(((A.mid_up.to_numpy() < 0.5) == y)[ok].mean()), 3)
out["always_up"] = round(float(y[ok].mean()), 3)
out["at_or_above_touch"] = round(float((A.p.to_numpy() >= A.bb.to_numpy() - 1e-9)[ok].mean()), 3)
out["dist_below_mid_median"] = round(float(np.nanmedian((A.mid_tok - A.p).to_numpy()[ok])), 4)
out["dist_below_mid_iqr"] = [round(float(np.nanpercentile((A.mid_tok - A.p).to_numpy()[ok], q)), 4) for q in (25, 75)]
out["touch_minus_add_median"] = round(float(np.nanmedian((A.bb - A.p).to_numpy()[ok])), 4)
# rung depth below the token's mid by time left and by mid level (description of the 4h price law)
dist = (A.mid_tok - A.p).to_numpy()
tb = np.digitize(tau, [1800, 3600, 7200, 10800])
for j, lab in enumerate(["<0.5h", "0.5-1h", "1-2h", "2-3h", ">=3h"]):
    m = ok & (tb == j)
    out[f"depth_tau_{lab}"] = [round(float(np.nanmedian(dist[m])), 4), int(m.sum())] if m.any() else None
mt = A.mid_tok.to_numpy()
for lo, hi in ((0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 1.0)):
    m = ok & (mt >= lo) & (mt < hi)
    out[f"depth_mid_{lo}-{hi}"] = [round(float(np.nanmedian(dist[m])), 4), int(m.sum())] if m.any() else None
for h in (0.05, 0.06, 0.07):
    out[f"within_tick_mid_minus_{h}"] = round(float((np.abs(np.round(mt - h, 2) - A.p.to_numpy()) <= 0.0101)[ok].mean()), 3)
out["within_tick_touch_minus_0.05"] = round(float((np.abs(np.round(A.bb.to_numpy() - 0.05, 2) - A.p.to_numpy()) <= 0.0101)[ok].mean()), 3)
print(json.dumps(out, indent=1))
(HERE.parent / "results" / f"iter16_q4h_{a}_{b}.json").write_text(json.dumps(out, indent=1))
