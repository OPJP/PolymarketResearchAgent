"""Re-run the project's tape-only maker (fair = last print) on the 160 sampled markets with the
project's own function, then add the optimistic at-touch fill bound that the methodology says is
reported for maker rules but is absent from RN1's maker_replicability_study.json."""
import json, math, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from common import load, W, S
from polyrea.analysis.tape_maker import tape_maker_backtest
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue

tk, mk, meta = load()
pay = meta["payouts"]; active = {c: tuple(v) for c, v in meta["active"].items()}
flow = tk[["condition_id", "ts", "outcome", "side", "price", "size"]]
fit_flow = flow[flow.condition_id.isin(meta["fit"])]
test_flow = flow[flow.condition_id.isin(meta["test"])]


def at_touch_backtest(flow, payouts, delta, latency, requote_s=10, size_shares=20.0, tick=0.01, active=None):
    """Same as tape_maker_backtest but a print AT the bid also fills (first in queue): optimistic bound."""
    out = []
    for cid, g in flow.groupby("condition_id"):
        g = g.sort_values("ts"); ts = g["ts"].to_numpy()
        p0 = np.where(g["outcome"].to_numpy() == 0, g["price"].to_numpy(), 1 - g["price"].to_numpy())
        start, end = active[cid]
        oc, sd, pr, sz = g.outcome.to_numpy(), g.side.to_numpy(), g.price.to_numpy(), g["size"].to_numpy()
        for t0 in range(int(start), int(end), requote_s):
            k = np.searchsorted(ts, t0 - latency, side="right") - 1
            if k < 0:
                continue
            fair0 = float(p0[k])
            lo, hi = np.searchsorted(ts, t0, side="right"), np.searchsorted(ts, t0 + requote_s, side="right")
            if hi <= lo:
                continue
            for outcome, fair in ((0, fair0), (1, 1 - fair0)):
                q = math.floor((fair - delta) / tick + 1e-9) * tick
                if q < tick or q > 1 - tick:
                    continue
                s = slice(lo, hi)
                m1 = (oc[s] == outcome) & (sd[s] == "SELL") & (pr[s] <= q + 1e-9)
                m2 = (oc[s] != outcome) & (sd[s] == "BUY") & (pr[s] >= 1 - q - 1e-9)
                filled = min(size_shares, float(sz[s][m1].sum() + sz[s][m2].sum()))
                if filled <= 0:
                    continue
                p = payouts[cid] if outcome == 0 else 1 - payouts[cid]
                out.append({"condition_id": cid, "price": q, "shares": filled, "pnl": filled * (p - q)})
    f = pd.DataFrame(out)
    per_m = f.groupby("condition_id")["pnl"].sum()
    usd = float((f.price * f.shares).sum())
    t = hac_t_test(per_m.to_numpy())
    return {"fills": int(len(f)), "markets": int(per_m.size), "usd_bought": usd, "pnl": float(f.pnl.sum()), "return_on_bought": float(f.pnl.sum() / usd),
            "per_market_t": t.statistic, "per_market_p": t.p_value, "per_market_bootstrap_p": stationary_bootstrap_pvalue(per_m.to_numpy(), n_boot=2000).p_value}

grid = [0.005, 0.01, 0.02, 0.03, 0.05]
res = {"n_fit": len(meta["fit"]), "n_test": len(meta["test"])}
fit_scan = {d: tape_maker_backtest(fit_flow, pay, d, latency=2, active=active) for d in grid}
best = max(grid, key=lambda d: fit_scan[d].get("per_market_t") or -1e9)
res["strict_fit_scan"] = {str(d): {k: v for k, v in r.items() if k in ("fills", "return_on_bought", "per_market_t")} for d, r in fit_scan.items()}
res["strict_chosen_delta"] = best
res["strict_test"] = {str(L): {k: v for k, v in tape_maker_backtest(test_flow, pay, best, latency=L, active=active).items() if k in ("fills", "markets", "usd_bought", "pnl", "return_on_bought", "per_market_p")} for L in (0, 2, 5, 30)}
fit_scan_t = {d: at_touch_backtest(fit_flow, pay, d, latency=2, active=active) for d in grid}
best_t = max(grid, key=lambda d: fit_scan_t[d]["per_market_t"])
res["at_touch_fit_scan"] = {str(d): {k: v for k, v in r.items() if k in ("fills", "return_on_bought", "per_market_t")} for d, r in fit_scan_t.items()}
res["at_touch_chosen_delta"] = best_t
res["at_touch_test"] = {str(L): at_touch_backtest(test_flow, pay, best_t, latency=L, active=active) for L in (0, 2, 5, 30)}
print(json.dumps(res, indent=1))
json.dump(res, open(S / "recheck_maker.json", "w"), indent=1)
