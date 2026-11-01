"""Iteration 8, catalog D2 (hazard model of when it acts): per 50-ms bin of each (market, Up-book side), the hazard that
the cluster posts a burst (>= 2 same-price exact-500 adds within 20 ms on that side; the three-wallet signature) in the
bin, as a function of public clocks only: ms since the latest Chainlink publish (dy_rtds publish ms where recorded, else
value stamp + 1,090 ms), |Chainlink change| of that report, ms since the latest Binance futures mid change and its
|move| over the last 250 ms, ms since the latest trade in that market and its size, time left. Development block 10-31,
own raw recorder; logistic and LightGBM fitted on the first 60% of the period, AUC held out on the last 40%.
    python code8/d2_hazard.py 1793455600 1793464202
    python code8/d2_hazard.py 1793467740 1793469600 pub     (true publish ms from dy_rtds)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
sys.path.insert(0, str(HERE.parent / "code6"))
from pres_live import load_ref  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
BIN = 50


def main(a, b):
    import lightgbm as lgb
    ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet", columns=["s", "w", "side", "p", "d"])
    e5 = ev[ev.d == 500.0].sort_values("s")
    del ev
    x = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet").sort_values("s")
    fu, cl, tw = load_ref(a, b)
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    chg = np.r_[True, np.diff(fm) != 0]
    fcs, fcm = fs[chg], fm[chg]
    cls = np.array(sorted(cl))
    clv = np.array([cl[k] for k in cls])
    pub = cls * 1000 + 1090   # publish proxy (median publish delay)
    dcl = np.r_[0.0, np.abs(np.diff(clv))]
    if USE_PUB:
        from rawread import iter_dm
        P = {}
        for r in iter_dm("dy_rtds", a - 60, b + 5):
            if r.get("k") == "u" and r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P") and r.get("ts"):
                P.setdefault(int(r["ts"]) // 1000, (int(r["P"]), float(r["v"])))
        ks = np.array(sorted(P))
        pub = np.array([P[k][0] for k in ks], dtype=np.int64)
        vv = np.array([P[k][1] for k in ks])
        o = np.argsort(pub)
        pub, vv = pub[o], vv[o]
        dcl = np.r_[0.0, np.abs(np.diff(vv))]
    rows = []
    for w, g in e5.groupby("w"):
        st = int(w.split("-")[-1])
        L = 900 if "-15m-" in w else 300
        t0, t1 = max(st * 1000, a * 1000), min((st + L - 30) * 1000, b * 1000)
        if t1 - t0 < 60000:
            continue
        grid = np.arange(t0, t1, BIN)
        xs = x[x.w == w]
        xt, xz = xs.s.to_numpy(np.int64), xs.z.to_numpy()
        for side in (1, 0):
            gs = g[g.side == side]
            ts, ps = gs.s.to_numpy(np.int64), gs.p.to_numpy()
            # bursts: same price, >= 2 adds within 20 ms -> event time = first add
            ev_t = []
            i = 0
            while i < len(ts):
                j = i
                while j + 1 < len(ts) and ts[j + 1] - ts[i] <= 20:
                    j += 1
                same = (ps[i:j + 1] == ps[i]).sum()
                if same >= 2:
                    ev_t.append(ts[i])
                i = j + 1
            ev_t = np.array(ev_t, dtype=np.int64)
            y = np.zeros(len(grid), dtype=np.int8)
            if len(ev_t):
                k = (ev_t - t0) // BIN
                k = k[(k >= 0) & (k < len(grid))]
                y[k] = 1
            ip = np.searchsorted(pub, grid, side="right") - 1
            iff = np.searchsorted(fcs, grid, side="right") - 1
            ix = np.searchsorted(xt, grid, side="right") - 1
            f250 = np.searchsorted(fs, grid - 250, side="right") - 1
            fnow = np.searchsorted(fs, grid, side="right") - 1
            D = pd.DataFrame({"y": y, "t": grid, "side": side, "fam15": int(L == 900),
                              "ms_pub": np.where(ip >= 0, grid - pub[np.clip(ip, 0, None)], 99999),
                              "dcl": np.where(ip >= 0, dcl[np.clip(ip, 0, None)], 0.0),
                              "ms_fut": np.where(iff >= 0, grid - fcs[np.clip(iff, 0, None)], 99999),
                              "fut250": np.abs(fm[np.clip(fnow, 0, None)] - fm[np.clip(f250, 0, None)]),
                              "ms_trade": np.where(ix >= 0, grid - xt[np.clip(ix, 0, None)], 99999),
                              "z_trade": np.where(ix >= 0, xz[np.clip(ix, 0, None)], 0.0),
                              "tleft": (st + L) * 1000 - grid})
            rows.append(D)
    D = pd.concat(rows, ignore_index=True)
    cut = D.t.quantile(0.6)
    tr, te = D[D.t < cut], D[D.t >= cut]
    P = dict(objective="binary", num_leaves=15, min_data_in_leaf=200, learning_rate=0.05, lambda_l2=10, max_bin=63, verbose=-1, seed=8)
    sets = {"time_left_side": ["tleft", "side", "fam15"], "trade_clock": ["ms_trade", "z_trade", "tleft", "side", "fam15"],
            "futures_clock": ["ms_fut", "fut250", "tleft", "side", "fam15"], "chainlink_clock": ["ms_pub", "dcl", "tleft", "side", "fam15"],
            "all_public_clocks": ["ms_pub", "dcl", "ms_fut", "fut250", "ms_trade", "z_trade", "tleft", "side", "fam15"]}
    out = {"bins": int(len(D)), "events": int(D.y.sum()), "event_rate": round(float(D.y.mean()), 5)}
    for nm, cols in sets.items():
        m = lgb.train(P, lgb.Dataset(tr[cols], tr.y), 300)
        out[nm] = round(float(roc_auc_score(te.y, m.predict(te[cols]))), 4)
    # hazard by ms since the latest publish (proxy) and since the latest futures change
    out["rate_by_ms_since_publish"] = D.groupby(pd.cut(D.ms_pub, [0, 50, 100, 150, 200, 300, 500, 1000, 2000, 99999]), observed=True).y.mean().round(5).rename(index=str).to_dict()
    out["rate_by_ms_since_futures_change"] = D.groupby(pd.cut(D.ms_fut, [0, 50, 100, 150, 200, 300, 500, 1000, 99999]), observed=True).y.mean().round(5).rename(index=str).to_dict()
    (HERE.parent / "results" / f"iter8_d2_hazard_{a}_{b}{'_pub' if USE_PUB else ''}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


USE_PUB = False

if __name__ == "__main__":
    USE_PUB = "pub" in sys.argv[3:]
    main(int(sys.argv[1]), int(sys.argv[2]))
