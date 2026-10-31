"""H3: corrected public spot model. The market's strike ("price to beat") is the Chainlink 60-s TWAP at the window
start (verified: priceToBeat == previous window's finalPrice for 555/555 windows). The recorded model used the last
Kraken trade at the start as strike. Here strike = mean of Kraken per-second prices over [start-60, start), available
at start (per-second values are available 1 s after their second). Sigma scale fitted on FIT (Brier).
Then: taker match (lag scan on FIT, AUC on TEST vs spot-clock-shift null) + taker and maker backtests on TEST."""
import sys, json, itertools, time
import numpy as np, pandas as pd
from scipy import stats
from common import *
from polyrea.analysis.updown import SpotIndex, auc, decision_metrics, fit_theta
from polyrea.pit import TimeSeries
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue

d, G = load()
ev = np.concatenate([d["fit"]["spot_ev"], d["test"]["spot_ev"]]); vals = np.concatenate([d["fit"]["spot_vals"], d["test"]["spot_vals"]])
o = np.argsort(ev, kind="stable")
SPOT = SpotIndex(TimeSeries.build("spot", zip(ev[o].tolist(), vals[o].tolist()), availability_lag=1))

def fair(spot, start, end, t_dec, scale=1.0, twap=60):
    start, end, t_dec = (np.asarray(x, dtype=np.int64) for x in (start, end, t_dec))
    s0 = spot.mean_between(start - twap, start, start)        # Kraken TWAP over [start-60, start), known at start
    st = spot.price_at(t_dec); sig = spot.sigma_at(t_dec) * scale
    tw = end - twap; before = t_dec < tw
    var_before = (tw - t_dec).clip(min=0) + twap / 3.0
    r = (end - t_dec).clip(min=0).astype(float)
    a_known = spot.mean_between(tw, t_dec, t_dec); a_known = np.where(np.isnan(a_known), st, a_known)
    mean_in = ((twap - r) * a_known + r * st) / twap
    sd_in = (r / twap) * np.sqrt(np.maximum(r, 1e-9) / 3.0)
    mean = np.where(before, st, mean_in); sdu = np.where(before, np.sqrt(var_before), sd_in)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (mean - s0) / (st * sig * sdu)
    p = stats.norm.cdf(z)
    p = np.where(t_dec < start, 0.5, p)
    p = np.where(t_dec >= end, np.where(mean >= s0, 1.0, 0.0), p)
    return p

# --- Brier check + sigma scale on FIT
REL = np.array([10, 30, 60, 90, 120, 150, 180, 210, 240, 255, 270, 285])
def brier_rows(per):
    out = []
    for cid, w in G[per].wins.items():
        t = w.start_ts + REL - 2
        base, up_last, _, _ = G[per].g[cid]
        out.append(pd.DataFrame({"cid": cid, "start": w.start_ts, "end": w.end_ts, "t": t, "y": w.up_payout, "mkt": up_last[np.clip(t - base, 0, len(up_last) - 1)]}))
    return pd.concat(out, ignore_index=True)
BR = {per: brier_rows(per) for per in ("fit", "test")}
scales = (0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4)
def brier_of(per, scale):
    b = BR[per]; p = fair(SPOT, b.start, b.end, b.t, scale); ok = np.isfinite(p)
    return float(np.mean((p[ok] - b.y[ok]) ** 2)), float(np.mean((b.mkt[ok] - b.y[ok]) ** 2)), int(ok.sum())
fit_scan = {s: brier_of("fit", s)[0] for s in scales}
SCALE = min(fit_scan, key=fit_scan.get)
out = {"brier": {"fit_scale_scan": fit_scan, "chosen_scale": SCALE, "fit": brier_of("fit", SCALE), "test": brier_of("test", SCALE), "test_scale1": brier_of("test", 1.0)}}
print("brier", out["brier"], flush=True)

# --- taker match (same design as polyrea.analysis.updown.match_test, corrected fair)
def score(P, L, shift=0):
    fu = fair(SPOT, P.start_ts.to_numpy() + shift, P.end_ts.to_numpy() + shift, P.ts.to_numpy() - L + shift, SCALE)
    return np.where(P.is_up.to_numpy(), fu, 1 - fu) - P.price.to_numpy()
Pf, Pt = d["fit"]["prints"], d["test"]["prints"]
match = {}
for name, wal in W.items():
    yf = (Pf.wallet == wal).to_numpy().astype(int); yt = (Pt.wallet == wal).to_numpy().astype(int)
    lag_scan = {L: auc(score(Pf, L), yf) for L in (-5, -2, -1, 0, 1, 2, 3, 5, 10, 20)}
    L = max((x for x in lag_scan if x >= 0), key=lambda x: lag_scan[x])
    th = fit_theta(score(Pf, L), yf)
    s_te = score(Pt, L); a = auc(s_te, yt)
    rng = np.random.default_rng(7); null = []
    for _ in range(200):
        sh = int(rng.integers(3600, 6 * 3600)) * int(rng.choice([-1, 1]))
        null.append(auc(score(Pt, L, sh), yt))
    null = np.array([x for x in null if np.isfinite(x)])
    match[name] = {"lag_scan_fit": lag_scan, "latency": L, "theta": th, "test_auc": a, "null_mean": float(null.mean()), "null_p95": float(np.percentile(null, 95)),
                   "perm_p": float((1 + (null >= a).sum()) / (1 + len(null))), "decision": decision_metrics(s_te, yt, th)}
    print(name, json.dumps(match[name], default=float), flush=True)
out["taker_match"] = match

# --- taker backtest LA(theta, latency) with corrected fair: theta/latency chosen on FIT by per-window t
def taker_bt_rule(P, L, th, cap=25.0):
    p = P[P.up_payout.notna()].copy(); e = score(p, L)
    sel = np.isfinite(e) & (e > th)
    return taker_bt(p.assign(rel=0), pd.Series(sel, index=p.index), cap=cap)
scan = []
for L, th in itertools.product((1, 2, 3, 5), (0.02, 0.04, 0.06, 0.08, 0.10, 0.15)):
    r = taker_bt_rule(Pf, L, th)
    if r["trades"] >= 300:
        scan.append({"L": L, "theta": th, **{k: r[k] for k in ("trades", "pnl", "ret", "per_window_t")}})
bst = max(scan, key=lambda r: r["per_window_t"])
out["taker_backtest"] = {"fit_best": bst, "fit_share_positive": float(np.mean([r["pnl"] > 0 for r in scan])), "test": taker_bt_rule(Pt, bst["L"], bst["theta"]),
                         "test_latency": {str(bst["L"] + x): {k: v for k, v in taker_bt_rule(Pt, bst["L"] + x, bst["theta"]).items() if k in ("trades", "pnl", "ret", "per_window_p")} for x in (1, 3, 5)}}
print("taker_bt", json.dumps(out["taker_backtest"], default=float), flush=True)

# --- maker backtest with corrected fair (strict trade-through and at-touch), delta/requote chosen on FIT
FLOW = {per: {cid: (g.ts.to_numpy().astype(np.int64), g.is_up.to_numpy(), (g.side == "SELL").to_numpy(), g.price.to_numpy(), g["size"].to_numpy()) for cid, g in d[per]["flow"].groupby("condition_id")} for per in ("fit", "test")}
def maker(per, delta, L=1, R=5, stop=0, at_touch=False, size=20.0, tick=0.001, queue=1.0):
    rows = []
    for cid, w in G[per].wins.items():
        if w.up_payout is None or cid not in FLOW[per]: continue
        ticks = np.arange(w.start_ts + 2, w.end_ts - stop, R)  # strike known from start; first quote at start+2
        fu = fair(SPOT, np.full(len(ticks), w.start_ts), np.full(len(ticks), w.end_ts), ticks - L, SCALE)
        ts, iu, se, pr, s = FLOW[per][cid]
        j = (ts - ticks[0] - 1) // R if len(ticks) else ts * 0
        ok = (ts > ticks[0]) & (j >= 0) & (j < len(ticks))
        j, iu2, se2, pr2, s2 = j[ok], iu[ok], se[ok], pr[ok], s[ok]
        eps = -1e-9 if at_touch else 1e-9
        for side_up in (True, False):
            fr = fu if side_up else 1 - fu
            q = np.floor((fr - delta) / tick + 1e-9) * tick
            valid = np.isfinite(fu) & (q >= 0.01) & (q <= 0.99)
            qj = q[j]
            thr = ((iu2 == side_up) & se2 & (pr2 < qj - eps)) | ((iu2 != side_up) & ~se2 & (pr2 > 1 - qj + eps))
            avail = np.bincount(j[thr], weights=s2[thr], minlength=len(ticks)) * queue
            filled = np.where(valid, np.minimum(size, avail), 0.0)
            pay = w.up_payout if side_up else 1 - w.up_payout
            for i in np.nonzero(filled > 0)[0]:
                rows.append((cid, float(q[i]), float(filled[i]), float(filled[i] * (pay - q[i]))))
    if not rows: return {"fills": 0}
    f = pd.DataFrame(rows, columns=["cid", "q", "sh", "pnl"])
    pw = f.groupby("cid").pnl.sum().reindex(list(G[per].wins), fill_value=0.0)
    t = hac_t_test(pw.to_numpy()); usd = float((f.q * f.sh).sum())
    return {"fills": len(f), "usd": usd, "pnl": float(f.pnl.sum()), "ret": float(f.pnl.sum() / usd), "per_window_t": t.statistic, "per_window_p": t.p_value,
            "bootstrap_p": stationary_bootstrap_pvalue(pw.to_numpy(), n_boot=2000).p_value}
mk = {}
for mode in ("strict", "at_touch"):
    at = mode == "at_touch"; sc = []
    for delta, R, stop in itertools.product((0.0, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12), (2, 5), (0, 60)):
        r = maker("fit", delta, R=R, stop=stop, at_touch=at)
        if r["fills"] >= 200: sc.append({"delta": delta, "R": R, "stop": stop, **{k: r[k] for k in ("fills", "pnl", "ret", "per_window_t")}})
    b = max(sc, key=lambda r: r["per_window_t"])
    mk[mode] = {"fit_best": b, "fit_share_positive": float(np.mean([r["pnl"] > 0 for r in sc])), "test": maker("test", b["delta"], R=b["R"], stop=b["stop"], at_touch=at),
                "test_latency": {str(1 + x): {k: v for k, v in maker("test", b["delta"], L=1 + x, R=b["R"], stop=b["stop"], at_touch=at).items() if k in ("fills", "pnl", "ret", "per_window_p")} for x in (1, 4)}}
    print("maker", mode, json.dumps(mk[mode], default=float), flush=True)
out["maker_backtest"] = mk
json.dump(out, open("h3_twapstrike.json", "w"), indent=1, default=float)
