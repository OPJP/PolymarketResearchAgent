"""H2: tape-anchored two-sided maker (no spot data; optional blend with the Kraken spot fair).

Every R seconds from window start until `stop` s before the end, with information L seconds old:
  anchor_up = implied Up price of the last taker print with block ts <= t0 - L  (blend: w*anchor + (1-w)*spot_fair)
  rest BUY bids: Up at floor((anchor_up - delta)/0.01)*0.01, Down at floor((1 - anchor_up - delta)/0.01)*0.01
Fills on later taker prints in (t0, t0+R]: strict = trades THROUGH the bid; at_touch = also at the bid (first in queue).
Maker pays no fee; rebates excluded. Settlement at resolution only. (delta, R, stop, w) fitted on FIT; TEST untouched.
"""
import sys, json, itertools, time
import numpy as np, pandas as pd
from common import *
from polyrea.analysis.updown import fair_up_vectorized
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue

d, G = load()
FLOW = {}
for per in ("fit", "test"):
    f = d[per]["flow"]
    FLOW[per] = {cid: (g.ts.to_numpy().astype(np.int64), g.is_up.to_numpy(), (g.side == "SELL").to_numpy(), g.price.to_numpy(), g["size"].to_numpy()) for cid, g in f.groupby("condition_id")}

def run(per, delta, L=2, R=5, stop=0, w=1.0, size=20.0, at_touch=False, queue=1.0, tick=0.01):
    g = G[per]; rows = []
    for cid, win in g.wins.items():
        if win.up_payout is None or cid not in FLOW[per]:
            continue
        ticks = np.arange(win.start_ts, win.end_ts - stop, R)
        base, up_last, _, _ = g.g[cid]
        anchor = up_last[np.clip(ticks - L - base, 0, len(up_last) - 1)]
        if w < 1.0:
            fu = fair_up_vectorized(g.spot, np.full(len(ticks), win.start_ts), np.full(len(ticks), win.end_ts), ticks - L, 60)
            fu = np.where(np.isfinite(fu), fu, anchor)
            anchor = w * anchor + (1 - w) * fu
        ts, is_up, sell, price, sz = FLOW[per][cid]
        j = (ts - win.start_ts - 1) // R
        ok = (ts > win.start_ts) & (j >= 0) & (j < len(ticks))
        j, iu, se, pr, s = j[ok], is_up[ok], sell[ok], price[ok], sz[ok]
        buy = ~se
        eps = -1e-9 if at_touch else 1e-9
        for side_up in (True, False):
            fair = anchor if side_up else 1 - anchor
            q = np.floor((fair - delta) / tick + 1e-9) * tick
            valid = (q >= tick) & (q <= 1 - tick)
            qj = q[j]
            thr = ((iu == side_up) & se & (pr < qj - eps)) | ((iu != side_up) & buy & (pr > 1 - qj + eps))
            avail = np.bincount(j[thr], weights=s[thr], minlength=len(ticks)) * queue
            filled = np.where(valid, np.minimum(size, avail), 0.0)
            idx = np.nonzero(filled > 0)[0]
            pay = win.up_payout if side_up else 1 - win.up_payout
            for i in idx:
                rows.append((cid, int(ticks[i]), side_up, float(q[i]), float(filled[i]), float(filled[i] * (pay - q[i]))))
    if not rows:
        return {"fills": 0}
    f = pd.DataFrame(rows, columns=["cid", "ts", "up", "q", "sh", "pnl"])
    per_w = f.groupby("cid").pnl.sum().reindex(list(g.wins), fill_value=0.0)  # windows with no fills count as 0
    t = hac_t_test(per_w.to_numpy()); b = stationary_bootstrap_pvalue(per_w.to_numpy(), n_boot=2000)
    usd = float((f.q * f.sh).sum())
    pairs = f.groupby(["cid", "up"]).sh.sum().unstack(fill_value=0.0)
    return {"fills": int(len(f)), "usd": usd, "pnl": float(f.pnl.sum()), "ret": float(f.pnl.sum() / usd), "per_window_t": t.statistic, "per_window_p": t.p_value, "bootstrap_p": b.p_value,
            "fill_win_rate": float((f.pnl > 0).mean()), "avg_q": float(f.q.mean()), "matched_pair_share": float(np.minimum(pairs.get(True, 0), pairs.get(False, 0)).sum() / max(1e-9, f.sh.sum() / 2))}

t0 = time.time()
out = {}
for mode in ("strict", "at_touch"):
    at = mode == "at_touch"
    scan = []
    for delta, R, stop, w in itertools.product((0.0, 0.01, 0.02, 0.03, 0.05, 0.08), (2, 5, 10), (0, 60, 120), (1.0, 0.5)):
        r = run("fit", delta, R=R, stop=stop, w=w, at_touch=at)
        if r["fills"] < 200:
            continue
        scan.append({"delta": delta, "R": R, "stop": stop, "w": w, **{k: r[k] for k in ("fills", "pnl", "ret", "per_window_t")}})
    best = max(scan, key=lambda r: r["per_window_t"])
    p = dict(delta=best["delta"], R=best["R"], stop=best["stop"], w=best["w"])
    test = run("test", at_touch=at, **p)
    deg = {str(2 + x): {k: v for k, v in run("test", L=2 + x, at_touch=at, **p).items() if k in ("fills", "pnl", "ret", "per_window_p")} for x in (1, 3, 8)}
    q = {str(qs): {k: v for k, v in run("test", at_touch=at, queue=qs, **p).items() if k in ("fills", "pnl", "ret", "per_window_p")} for qs in (0.5, 0.25)}
    out[mode] = {"chosen_on_fit": p, "fit_best": best, "fit_scan_n": len(scan), "fit_scan_share_positive": float(np.mean([r["pnl"] > 0 for r in scan])),
                 "fit_scan_max_ret": max(r["ret"] for r in scan), "test": test, "test_latency_degradation": deg, "test_queue_share": q,
                 "fit_top5": sorted(scan, key=lambda r: -r["per_window_t"])[:5]}
    print(mode, json.dumps(out[mode], default=float), round(time.time() - t0), flush=True)
# the wallets' own maker fills on TEST (rebates excluded), for comparison
mp = d["test"]["maker_prints"]
mp = mp[mp.up_payout.notna()]
own = {}
for name, wal in W.items():
    m = mp[mp.wallet == wal]
    pay = np.where(m.is_up, m.up_payout, 1 - m.up_payout)
    pnl = m["size"] * (pay - m.price)
    per_w = pd.Series(pnl.to_numpy(), index=m.condition_id.to_numpy()).groupby(level=0).sum()
    own[name] = {"fills": int(len(m)), "usd": float((m["size"] * m.price).sum()), "pnl": float(pnl.sum()), "ret": float(pnl.sum() / (m["size"] * m.price).sum()), "per_window_p": hac_t_test(per_w.to_numpy()).p_value}
out["wallet_own_maker_fills_test"] = own
print(json.dumps(own, default=float))
json.dump(out, open("h2_maker.json", "w"), indent=1, default=float)
