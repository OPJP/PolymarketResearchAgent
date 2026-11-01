"""Iteration 7 (assumptions P3, X55): the Chainlink gain in print selection against a STRONGER activity baseline
(adds sub-second book state from the raw touch series: spread, ms since the last touch change, 500-ms mid move toward s,
whether the print hit the pre-trade best bid of the sold token). Book depth is not used (it contains the cluster's own
resting 500s). Based on code7/sel_clock.py (mechanics M1 step 3, X49): code6/sel_live.py with the Chainlink input on several clocks. edge_clD uses the value
stamped floor((t - D) / 1000) for D = 700 ms (the engine clock of panel M1: a latency oracle), 1083 ms (median RTDS publish delay
measured on 10-31 17:29-17:38), 1432 ms (p90 publish delay), 2000 and 3000 ms (the t-2 / t-3 conventions).
Original docstring of code6/sel_live.py: print-level selection on the match clock, live block.

Population: every trade print (first CLOB 'x' record of a tx) in a BTC 5m window, seen as a hit on the bid of the token
s it sells (taker SELL s, or taker BUY of the complement); the cluster can only be the maker on that bid. Label: the tx
holds a cluster maker fill. Prints of the cluster's own taker txs are dropped; prior prints in cluster txs are never
used in features. Features at the match ms t (server clocks):
  activity: time since the previous clean print, whether it sold the same token and at the same price, clean prints and
  shares sold on s in the last 1 / 5 s, size, time in window, price level;
  reference: futures digital fair of s (bookTicker mid at t - 50 ms vs the futures TWAP of [start-60, start), realised
  1-s vol of the last 300 s x 1.4) minus the print price; futures mid move toward s over 1 s and 3 s.
Pre-registered time split: fit on live BUILD (< 15:00 UTC), test on live VALIDATE (>= 15:00 UTC).
    python code6/sel_live.py <start_ts> <end_ts>
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
HERE = HERE.parent / "code6" if HERE.name == "code7" else HERE
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
from rawread import iter_dm  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88",
      "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
SPLIT = 1793458800 * 1000
DS = (1083, 1432, 2000)


def main(a, b):
    x = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet")
    x = x[x.w.str.contains("btc-updown-5m")].sort_values("s", kind="stable").drop_duplicates("h")
    cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet"))])
    cd["maker"] = cd.maker.str.lower()
    cd["tx"] = cd.tx.str.lower()
    mk_tx = set(cd.loc[(cd.role == "maker") & cd.maker.isin(CL), "tx"])
    tk_tx = set(cd.loc[(cd.role == "taker") & cd.maker.isin(CL), "tx"])
    acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))])
    all_cl_tx = mk_tx | tk_tx | set(acts.transactionHash.str.lower())
    d = x.d.astype(str).str.upper().str[0]
    # s = 1 if the print sells Up (taker SELL Up or BUY Down), 0 if it sells Down
    x["s_up"] = ((x.ai == 0) & (d == "S")) | ((x.ai == 1) & (d == "B"))
    x["p_s"] = np.where((x.ai == 0) == x.s_up, x.p, 1 - x.p)
    x["y"] = x.h.isin(mk_tx).astype(int)
    x["own_taker"] = x.h.isin(tk_tx)
    x["clean_prior"] = ~x.h.isin(all_cl_tx)
    fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", a - 400, b) if r["r"][0] == "b" and r["r"][2]]
    fu = pd.DataFrame(fut, columns=["s", "m"]).sort_values("s").drop_duplicates("s", keep="last")
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))

    cl, tw = {}, {}
    for r in iter_dm("dm_rtds", a - 400, b + 60):
        try:
            jj_ = json.loads(r["m"])
        except ValueError:
            continue
        for x_ in (jj_.get("payload") or {}).get("data", []) or []:
            (cl if r["q"] == "crypto_prices_chainlink" else tw)[int(x_["timestamp"]) // 1000] = float(x_["value"])
    cls = np.array(sorted(cl))
    clv = np.array([cl[k] for k in cls])

    def mid_at(t):
        i = np.searchsorted(fs, t, side="right") - 1
        return fm[i] if i >= 0 else np.nan
    rows = []
    for w, g in x.groupby("w"):
        st = int(w.split("-")[-1])
        g = g[(g.s >= st * 1000) & (g.s < (st + 300) * 1000)]
        if not len(g):
            continue
        k0, k1 = np.searchsorted(sec, st - 60), np.searchsorted(sec, st)
        K = ms_sec[k0:k1].mean() if k1 > k0 else np.nan
        cg = g[g.clean_prior]
        cs, cup, cps, cz = cg.s.to_numpy(), cg.s_up.to_numpy(), cg.p_s.to_numpy(), cg.z.to_numpy()
        for r in g.itertuples(index=False):
            if r.own_taker:
                continue
            t = int(r.s)
            j = np.searchsorted(cs, t, side="left") - 1
            o = {"y": r.y, "t": t, "w": w, "rel": t / 1000 - st, "p_s": r.p_s, "lz": np.log1p(r.z), "s_up": int(r.s_up)}
            if j >= 0:
                o["dt_prev"] = min(t - cs[j], 60000)
                o["prev_same_side"] = int(cup[j] == r.s_up)
                ps_prev = cps[j] if cup[j] == r.s_up else 1 - cps[j]
                o["prev_same_px"] = int(abs(ps_prev - r.p_s) < 1e-6)
                o["d_px_prev"] = r.p_s - ps_prev
            for L in (1000, 5000):
                m = (cs >= t - L) & (cs < t)
                o[f"n{L}"] = int(m.sum())
                o[f"sold_s{L}"] = float(cz[m & (cup == r.s_up)].sum())
            m0 = mid_at(t - 50)
            sgn = 1 if r.s_up else -1
            o["mv1000"] = sgn * (m0 - mid_at(t - 1050))
            o["mv3000"] = sgn * (m0 - mid_at(t - 3050))
            jj = np.searchsorted(sec, (t - 50) // 1000)
            sig = np.std(r1[max(jj - 300, 0):jj]) * 1.4 if jj > 30 else np.nan
            tau = max(st + 300 - t / 1000, 1.0)
            fu_up = norm.cdf(np.log(m0 / K) / (sig * np.sqrt(tau))) if (K == K and sig == sig and sig > 0) else np.nan
            o["edge"] = (fu_up if r.s_up else 1 - fu_up) - r.p_s
            Kc = tw.get(st)
            k2 = np.searchsorted(cls, t // 1000 - 2, side="right") - 1
            if k2 >= 6:
                o["cl_noise"] = (clv[k2] - clv[k2 - 4:k2].mean()) * (1 if r.s_up else -1)
            for D in DS:
                k = np.searchsorted(cls, (t - D) // 1000, side="right") - 1
                if Kc is not None and k >= 0 and sig == sig and sig > 0:
                    cu = norm.cdf(np.log(clv[k] / Kc) / (sig * np.sqrt(tau)))
                    o[f"edge_cl{D}"] = (cu if r.s_up else 1 - cu) - r.p_s
            rows.append(o)
    D = pd.DataFrame(rows)
    tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
    TT = {w: (g.s.to_numpy(np.int64), g.bb.to_numpy(), g.ba.to_numpy()) for w, g in tch.sort_values("s").groupby("w")}
    sp_, dtt_, dm_, atb_ = [], [], [], []
    for w, t, su, ps in zip(D.w, D.t, D.s_up, D.p_s):
        T = TT.get(w)
        if T is None:
            sp_.append(np.nan); dtt_.append(np.nan); dm_.append(np.nan); atb_.append(np.nan)
            continue
        i = np.searchsorted(T[0], t - 50, side="right") - 1
        j = np.searchsorted(T[0], t - 550, side="right") - 1
        if i < 0:
            sp_.append(np.nan); dtt_.append(np.nan); dm_.append(np.nan); atb_.append(np.nan)
            continue
        bb, ba = T[1][i], T[2][i]
        sp_.append(ba - bb)
        dtt_.append(min(t - T[0][i], 60000))
        m1 = (bb + ba) / 2
        m0 = (T[1][j] + T[2][j]) / 2 if j >= 0 else m1
        dm_.append((m1 - m0) * (1 if su else -1))
        best_s = bb if su else 1 - ba
        atb_.append(float(abs(ps - best_s) < 1e-6))
    D["spread"], D["dt_touch"], D["dmid500"], D["at_best"] = sp_, dtt_, dm_, atb_
    ACT = ["rel", "p_s", "lz", "s_up", "dt_prev", "prev_same_side", "prev_same_px", "d_px_prev", "n1000", "n5000", "sold_s1000", "sold_s5000"]
    REF = ["edge", "mv1000", "mv3000"]
    CLF = [f"edge_cl{D}" for D in DS]
    CLF2 = CLF + ["cl_noise"]
    tr, te = D[D.t < SPLIT], D[D.t >= SPLIT]
    import lightgbm as lgb
    out = {"prints": int(len(D)), "pos": int(D.y.sum()), "pos_rate": round(float(D.y.mean()), 4), "train": int(len(tr)), "test": int(len(te)),
           "test_pos": int(te.y.sum())}
    P = dict(objective="binary", num_leaves=15, min_data_in_leaf=200, learning_rate=0.05, lambda_l2=10, max_bin=63, verbose=-1, seed=6)
    BOOK = ["spread", "dt_touch", "dmid500", "at_best"]
    for nm, cols in [("activity", ACT), ("strong", ACT + BOOK), ("strong+ref", ACT + BOOK + REF)] + [(f"strong+ref+cl@{D}", ACT + BOOK + REF + [f"edge_cl{D}"]) for D in DS]:
        m = lgb.train(P, lgb.Dataset(tr[cols], tr.y), 300)
        s = m.predict(te[cols])
        auc = roc_auc_score(te.y, s)
        thr = np.quantile(m.predict(tr[cols]), 0.85)
        flag = s >= thr
        rec = float(flag[te.y.to_numpy() == 1].mean())
        lift = float(te.y[flag].mean() / te.y.mean()) if flag.any() else float("nan")
        imp = dict(zip(cols, np.round(m.feature_importance("gain") / max(m.feature_importance("gain").sum(), 1), 3)))
        out[nm] = {"test_auc": round(auc, 4), "recall_at_train_top15": round(rec, 3), "lift": round(lift, 2), "gain_share": imp}
    for col in REF + [f"edge_cl{D}" for D in DS] + ["cl_noise"]:
        v = te[[col, "y"]].dropna()
        out[f"univariate_test_auc_{col}"] = round(float(roc_auc_score(v.y, v[col])), 3)
    # within-window strata AUC of activity+ref vs activity (mean over windows with both classes)
    (HERE.parent / "results" / f"iter7_p3_strong_{a}_{b}.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "gain_share"}) for k, v in out.items()}, indent=1, default=str))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
