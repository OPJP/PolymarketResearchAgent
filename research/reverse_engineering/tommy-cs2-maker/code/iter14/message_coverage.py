"""How much of its re-pricing process sits at VISIBLE feed messages? Share of its maker V-change decisions (E3-1
decision set) with an informed take (I1, group P) or an informed cluster (I2) on the same event signed in the
preceding [0, W] s (W = 1, 3, 10), against the same share at decision times shifted by +-[30, 120] s inside the same
market (20 shifts), and the excess share attributable to visible messages. Also the share whose direction agrees with
the message's team. BUILD and VALIDATE. Output: results/message_coverage.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e3_screen as E  # noqa: E402

RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def share(dt, ds, ev_t, ev_s, W):
    j = np.searchsorted(ev_t, dt, side="right") - 1
    ok = j >= 0
    lag = np.where(ok, dt - ev_t[np.maximum(j, 0)], np.inf)
    hit = (lag >= 0) & (lag <= W)
    agree = hit & (ds == ev_s[np.maximum(j, 0)]) if ev_s is not None else hit
    return float(hit.mean()), float(agree.mean())


def main():
    out = {}
    rng = np.random.default_rng(0)
    for per in ("BUILD", "VALIDATE"):
        dt, ds, units, strata, inds = E.build(per)
        res = {"decisions": int(len(dt))}
        for name in ("I1_informed_take", "I2_informed_cluster"):
            et, es = inds[name]
            for W in (1, 3, 10):
                h, a = share(dt, ds, et, es, W)
                hn, an = [], []
                for _ in range(20):
                    sh = rng.uniform(30, 120, len(dt)) * rng.choice([-1, 1], len(dt))
                    x = dt + sh
                    # keep shifted times inside their unit
                    k = np.searchsorted(units[:, 0], dt, side="right") - 1
                    x = np.clip(x, units[k, 0], units[k, 1] - 1e-3)
                    o = np.argsort(x)
                    h2, a2 = share(x[o], ds[o], et, es, W)
                    hn.append(h2); an.append(a2)
                res[f"{name}_W{W}s"] = {"share": round(h, 4), "null": round(float(np.mean(hn)), 4), "excess": round(h - float(np.mean(hn)), 4),
                                        "agree_share": round(a, 4), "agree_null": round(float(np.mean(an)), 4)}
        out[per] = res
        print(per, json.dumps(res), flush=True)
    (RES / "message_coverage.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
