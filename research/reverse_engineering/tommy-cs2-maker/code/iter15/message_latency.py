"""X217 step 2 (assumptions panel iter-14 P5): latency of its V-change decisions behind the visible feed message.
E3-1 decision set and indicators (iter14/e3_screen.build): for each decision, the lag behind the latest preceding
informed take (I1, group P, wallet-free) on the event whose team agrees with the decision's direction; the excess lag
density over the shifted-time null (20 shifts of +-30..120 s inside the unit) in 50-ms bins over [0, 3] s; its CDF and
quantiles. A source of latency L after the message precedes the decision in 1 - CDF(L) of the message-locked decisions.
Output: results/message_latency.json"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter14"))
import e3_screen as E  # noqa: E402

RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
BINS = np.arange(0, 3.0001, 0.05)


def lags(dt, ds, et, es):
    j = np.searchsorted(et, dt, side="right") - 1
    ok = j >= 0
    lag = np.where(ok, dt - et[np.maximum(j, 0)], np.inf)
    agree = ok & (ds == es[np.maximum(j, 0)])
    return lag[agree & (lag >= 0) & (lag <= 3)]


out = {}
rng = np.random.default_rng(0)
for per in ("BUILD", "VALIDATE"):
    dt, ds, units, strata, inds = E.build(per)
    for name in ("I1_informed_take", "I2_informed_cluster"):
        et, es = inds[name]
        h = np.histogram(lags(dt, ds, et, es), BINS)[0].astype(float)
        hn = np.zeros_like(h)
        for _ in range(20):
            sh = rng.uniform(30, 120, len(dt)) * rng.choice([-1, 1], len(dt))
            k = np.searchsorted(units[:, 0], dt, side="right") - 1
            x = np.clip(dt + sh, units[k, 0], units[k, 1] - 1e-3)
            o = np.argsort(x)
            hn += np.histogram(lags(x[o], ds[o], et, es), BINS)[0]
        hn /= 20
        ex = np.clip(h - hn, 0, None)
        cdf = np.cumsum(ex) / max(ex.sum(), 1e-9)
        q = {str(p): round(float(BINS[1:][np.searchsorted(cdf, p)]), 3) for p in (0.1, 0.25, 0.5, 0.75, 0.9)}
        out[f"{per}_{name}"] = {"decisions": int(len(dt)), "locked_raw": int(h.sum()), "null": round(float(hn.sum()), 1),
                                "excess": round(float(ex.sum()), 1), "excess_lag_quantiles_s": q,
                                "share_after_L": {str(L): round(float(1 - cdf[int(round(L / 0.05)) - 1]), 3) for L in (0.1, 0.25, 0.35, 0.5, 1.0)},
                                "excess_first_500ms_by_50ms": [round(float(v), 1) for v in ex[:10]]}
        print(per, name, json.dumps(out[f"{per}_{name}"]), flush=True)
(RES / "message_latency.json").write_text(json.dumps(out, indent=1))
