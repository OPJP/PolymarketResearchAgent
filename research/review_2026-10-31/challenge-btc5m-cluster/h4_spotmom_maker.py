"""H4 (executable form of the matched maker-side rule): spot-momentum maker.
Every R s at t0 (window start .. end-stop), with Kraken spot available at t0-L: r = log S(t0-L)/S(t0-L-k), k=2.
Rest a BUY bid on Up only if r > theta, on Down only if r < -theta, at floor((anchor_side - delta)/0.001)*0.001,
anchor = last implied price of that side from the tape (block ts <= t0-L). Fills on taker prints in (t0, t0+R]:
strict = trades through the bid; at_touch = at or through (first in queue). Maker pays no fee; rebates excluded.
(theta, delta, R, L) chosen on FIT by per-window HAC t; TEST untouched. Also decision metrics of the match score."""
import sys, json, itertools
import numpy as np, pandas as pd
from common import *
from polyrea.analysis.updown import auc, decision_metrics
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue
d, G = load()
FLOW = {per: {cid: (g.ts.to_numpy().astype(np.int64), g.is_up.to_numpy(), (g.side == "SELL").to_numpy(), g.price.to_numpy(), g["size"].to_numpy()) for cid, g in d[per]["flow"].groupby("condition_id")} for per in ("fit", "test")}
def run(per, theta, delta, R=1, L=1, k=2, stop=0, at_touch=False, size=20.0, tick=0.001, queue=1.0):
    g = G[per]; rows = []
    for cid, w in g.wins.items():
        if w.up_payout is None or cid not in FLOW[per]: continue
        ticks = np.arange(w.start_ts, w.end_ts - stop, R)
        base, up_last, _, _ = g.g[cid]
        anchor = up_last[np.clip(ticks - L - base, 0, len(up_last) - 1)]
        r = np.log(g.spot.price_at(ticks - L) / g.spot.price_at(ticks - L - k))
        ts, iu, se, pr, s = FLOW[per][cid]
        j = (ts - w.start_ts - 1) // R
        ok = (ts > w.start_ts) & (j >= 0) & (j < len(ticks))
        j, iu2, se2, pr2, s2 = j[ok], iu[ok], se[ok], pr[ok], s[ok]
        eps = -1e-9 if at_touch else 1e-9
        for side_up in (True, False):
            gate = (r > theta) if side_up else (r < -theta)
            fr = anchor if side_up else 1 - anchor
            q = np.floor((fr - delta) / tick + 1e-9) * tick
            valid = gate & np.isfinite(r) & (q >= 0.01) & (q <= 0.99)
            qj = q[j]
            thr = ((iu2 == side_up) & se2 & (pr2 < qj - eps)) | ((iu2 != side_up) & ~se2 & (pr2 > 1 - qj + eps))
            avail = np.bincount(j[thr], weights=s2[thr], minlength=len(ticks)) * queue
            filled = np.where(valid, np.minimum(size, avail), 0.0)
            pay = w.up_payout if side_up else 1 - w.up_payout
            for i in np.nonzero(filled > 0)[0]:
                rows.append((cid, float(q[i]), float(filled[i]), float(filled[i] * (pay - q[i]))))
    if not rows: return {"fills": 0}
    f = pd.DataFrame(rows, columns=["cid", "q", "sh", "pnl"])
    pw = f.groupby("cid").pnl.sum().reindex(list(g.wins), fill_value=0.0)
    t = hac_t_test(pw.to_numpy()); usd = float((f.q * f.sh).sum())
    return {"fills": len(f), "usd": usd, "pnl": float(f.pnl.sum()), "ret": float(f.pnl.sum() / usd), "per_window_t": t.statistic, "per_window_p": t.p_value,
            "bootstrap_p": stationary_bootstrap_pvalue(pw.to_numpy(), n_boot=2000).p_value, "fill_win_rate": float((f.pnl > 0).mean())}
out = {}
for mode in ("strict", "at_touch"):
    at = mode == "at_touch"; sc = []
    for theta, delta, R, L in itertools.product((0.0, 1e-5, 2e-5, 4e-5), (0.0, 0.01, 0.02, 0.04), (1, 2), (1, 2)):
        r = run("fit", theta, delta, R=R, L=L, at_touch=at)
        if r["fills"] >= 200: sc.append({"theta": theta, "delta": delta, "R": R, "L": L, **{kk: r[kk] for kk in ("fills", "pnl", "ret", "per_window_t")}})
    b = max(sc, key=lambda r: r["per_window_t"])
    te = run("test", b["theta"], b["delta"], R=b["R"], L=b["L"], at_touch=at)
    deg = {str(b["L"] + x): {kk: v for kk, v in run("test", b["theta"], b["delta"], R=b["R"], L=b["L"] + x, at_touch=at).items() if kk in ("fills", "pnl", "ret", "per_window_p")} for x in (1, 3)}
    # optimistic: zero latency (L=0) on TEST with the chosen theta/delta, for reference only
    l0 = {kk: v for kk, v in run("test", b["theta"], b["delta"], R=b["R"], L=0, at_touch=at).items() if kk in ("fills", "pnl", "ret", "per_window_p")}
    out[mode] = {"fit_best": b, "fit_share_positive": float(np.mean([r["pnl"] > 0 for r in sc])), "fit_n": len(sc), "test": te, "test_latency": deg, "test_L0_reference": l0}
    print(mode, json.dumps(out[mode], default=float), flush=True)
# decision metrics of the single-feature match score (L=1, k=2) at FIT max-MCC threshold
def mframe(per):
    P = d[per]["maker_prints"]; return P[(P.ts - P.start_ts >= 0) & (P.ts - P.start_ts < 300)].reset_index(drop=True)
Pf, Pt = mframe("fit"), mframe("test")
def sret(P, L=1, k=2):
    sp = G["fit"].spot if P is Pf else G["test"].spot
    t = P.ts.to_numpy() - L; r = np.log(sp.price_at(t) / sp.price_at(t - k)); return np.where(P.is_up.to_numpy(), r, -r)
dm = {}
sf, st = sret(Pf), sret(Pt)
for n, w in W.items():
    yf = (Pf.wallet == w).to_numpy().astype(int); yt = (Pt.wallet == w).to_numpy().astype(int)
    okf = np.isfinite(sf)
    grid = np.nanquantile(sf, np.linspace(0.5, 0.99, 50))
    th = max(grid, key=lambda x: (lambda v: v if np.isfinite(v) else -1)(decision_metrics(sf, yf, x)["mcc"]))
    dm[n] = {"test_auc": auc(st, yt), "decision": decision_metrics(st, yt, th)}
    print(n, json.dumps(dm[n], default=float))
out["match_score_decision_metrics"] = dm
json.dump(out, open("h4_spotmom_maker.json", "w"), indent=1, default=float)
