"""Iteration 8, panel iter7 assumptions A4 (X72): the fill-presence ceiling with the observed quote as an oracle, and a
quote-unit presence metric (development live block 10-31, BTC 5m; live split fit < 15:00 UTC, test >= 15:00).

(1) Fill presence, unit = (window, side s, 10-s bin), label = cluster maker BUY fill on s in the bin (as code6/pres_live.py).
    Feature sets: activity (pres_live), + futures + Chainlink (public rule), + QUOTE ORACLE (contemporaneous cluster-class
    quote state in the bin from the raw book: exact-500 adds posted at/above the touch of s, bursts of >= 2 same-price
    500s within 20 ms at the touch, the highest 500 price relative to the touch at the bin start, queue ahead at the
    at-touch adds), + FUTURE TAKER FLOW of the bin (clean prints selling s in [T, T+10)). Oracle sets never count toward
    the target; they bound what any quote decoder could reach on fills.
(2) Quote unit, unit = (window, side s, second t), label = an exact-500 add on s at/above the touch in (t-1 s, t] whose
    price is still >= the touch of s at t (a cluster-class 500 at the touch now; 88% of filled exact-500s are the
    cluster's). Public features at t: Chainlink edge (report stamped floor((t - 1432)/1000), digital vs the true strike,
    R3 vol) over the mid, futures edge over the mid, spread, mid, time left; activity baseline: prints in the last 2/10 s,
    ms since the last trade and whether it sold s, ms since the last touch change, mid, spread, time left.
    python code8/a4_ceiling.py 1793455600 1793464202
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
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
sys.path.insert(0, str(HERE.parent / "code6"))
from pres_live import load_ref, CL  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
SPLIT = int(__import__("os").environ.get("A4_SPLIT", "1793458800"))
D_CL = 1432


def bursts(t_ms, p, gap=20):
    """burst id: same price, consecutive adds within gap ms."""
    o = np.lexsort((t_ms, p))
    bid = np.zeros(len(p), dtype=np.int64)
    cur = 0
    for k in range(1, len(o)):
        i, j = o[k - 1], o[k]
        if not (p[j] == p[i] and t_ms[j] - t_ms[i] <= gap):
            cur += 1
        bid[j] = cur
    return bid


def main(a, b):
    import lightgbm as lgb
    x = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet")
    x = x[x.w.str.contains("btc-updown-5m")].sort_values("s", kind="stable").drop_duplicates("h")
    cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet"))])
    cd["maker"] = cd.maker.str.lower()
    cd["tx"] = cd.tx.str.lower()
    acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))]).drop_duplicates(
        subset=["transactionHash", "asset", "w", "size", "price"])
    acts["tx"] = acts.transactionHash.str.lower()
    mk_tx = set(cd.loc[(cd.role == "maker") & cd.maker.isin(CL), "tx"])
    all_cl_tx = set(cd.loc[cd.maker.isin(CL), "tx"]) | set(acts.tx)
    fills = acts[(acts.type == "TRADE") & (acts.side == "BUY") & acts.tx.isin(mk_tx) & acts.slug.str.contains("btc-updown-5m", na=False)]
    ms = x.groupby("h").s.min()
    fills = fills.assign(ms=fills.tx.map(ms).fillna(fills.timestamp * 1000))
    d = x.d.astype(str).str.upper().str[0]
    x["s_up"] = ((x.ai == 0) & (d == "S")) | ((x.ai == 1) & (d == "B"))
    x["p_up"] = np.where(x.ai == 0, x.p, 1 - x.p)
    xc = x[~x.h.isin(all_cl_tx)]
    ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet", columns=["s", "w", "side", "p", "d", "prev", "bb", "ba"])
    ev = ev[ev.w.str.contains("btc-updown-5m")]
    tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
    tch = tch[tch.w.str.contains("btc-updown-5m")]
    e5 = ev[ev.d == 500.0].copy()
    del ev
    fu, cl, tw = load_ref(a, b)
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))
    cls = np.array(sorted(cl))
    clv = np.array([cl[k] for k in cls])
    bins, secs = [], []
    for slug in sorted(set(x.w)):
        st = int(slug.split("-")[-1])
        if st < a or st + 300 > b:
            continue
        K_c = tw.get(st)
        if K_c is None:
            continue
        g = xc[xc.w == slug]
        gs, gp, gup, gz = g.s.to_numpy(), g.p_up.to_numpy(), g.s_up.to_numpy(), g.z.to_numpy()
        f = fills[fills.slug == slug]
        K_f = ms_sec[np.searchsorted(sec, st - 60):np.searchsorted(sec, st)].mean()
        tw_ = tch[tch.w == slug].sort_values("s")
        ts_, bb_, ba_ = tw_.s.to_numpy(), tw_.bb.to_numpy(), tw_.ba.to_numpy()
        if not len(ts_):
            continue
        q = {}
        for s_up in (True, False):
            gq = e5[(e5.w == slug) & (e5.side == (1 if s_up else 0))]
            tq, pq = gq.s.to_numpy(np.int64), gq.p.to_numpy()
            pz = pq if s_up else 1 - pq
            touch_at = gq.bb.to_numpy() if s_up else 1 - gq.ba.to_numpy()
            at = pz >= touch_at - 1e-9
            bid = bursts(tq, pq) if len(tq) else np.zeros(0, dtype=np.int64)
            bsz = pd.Series(bid).map(pd.Series(bid).value_counts()).to_numpy() if len(bid) else np.zeros(0)
            q[s_up] = dict(t=tq, p=pz, at=at, burst=(bsz >= 2), qa=gq.prev.to_numpy())

        def touch(Tms, s_up):
            i = np.searchsorted(ts_, Tms, side="right") - 1
            if i < 0:
                return np.nan, np.nan
            bbv, bav = bb_[i], ba_[i]
            return (bbv, bav) if s_up else (1 - bav, 1 - bbv)

        for t in range(0, 300):
            T = (st + t) * 1000
            jj = np.searchsorted(sec, st + t)
            sig = np.std(r1[max(jj - 300, 0):jj]) * 1.4
            tau = max(300 - t, 1.0)
            fmid = fm[max(np.searchsorted(fs, T, side="right") - 1, 0)]
            fair_f = norm.cdf(np.log(fmid / K_f) / (sig * np.sqrt(tau))) if sig > 0 else np.nan
            k = np.searchsorted(cls, (T - D_CL) // 1000, side="right") - 1
            fair_c = norm.cdf(np.log(clv[k] / K_c) / (sig * np.sqrt(tau))) if (k >= 0 and sig > 0) else np.nan
            j = np.searchsorted(gs, T, side="right") - 1
            n2 = int(((gs > T - 2000) & (gs <= T)).sum())
            n10 = int(((gs > T - 10000) & (gs <= T)).sum())
            last_age = (T - gs[j]) if j >= 0 else 99999
            it = np.searchsorted(ts_, T, side="right") - 1
            tch_age = (T - ts_[it]) if it >= 0 else 99999
            for s_up in (True, False):
                bbs, bas = touch(T, s_up)
                if bbs != bbs:
                    continue
                mid = (bbs + bas) / 2
                Q = q[s_up]
                m = (Q["t"] > T - 1000) & (Q["t"] <= T) & Q["at"]
                lab = int(m.any() and (Q["p"][m].max() >= bbs - 1e-9))
                fc = fair_c if s_up else 1 - fair_c
                ff = fair_f if s_up else 1 - fair_f
                last_sold_s = int(j >= 0 and gup[j] == s_up)
                secs.append(dict(st=st, rel=t, s_up=int(s_up), y=lab, e_cl=fc - mid, e_f=ff - mid, spread=bas - bbs, mid=mid,
                                 tau=tau, n2=n2, n10=n10, last_age=last_age, last_sold_s=last_sold_s, tch_age=tch_age))
                if t % 10 == 0:
                    lp = (gp[j] if s_up else 1 - gp[j]) if j >= 0 else np.nan
                    y = int(((f.outcome == ("Up" if s_up else "Down")) & (f.ms >= T) & (f.ms < T + 10000)).any())
                    mb = (Q["t"] >= T) & (Q["t"] < T + 10000)
                    mbt = mb & Q["at"]
                    m15 = (Q["t"] > T - 1500) & (Q["t"] < T + 10000)
                    top = Q["p"][m15].max() if m15.any() else np.nan
                    fl = (gs >= T) & (gs < T + 10000)
                    w10 = (gs >= T - 10000) & (gs < T)
                    bins.append(dict(st=st, rel=t, s_up=int(s_up), y=y, n10=n10, n30=int(((gs >= T - 30000) & (gs < T)).sum()),
                                     sold10=float(gz[w10 & (gup == s_up)].sum()), bought10=float(gz[w10 & (gup != s_up)].sum()),
                                     last=lp, age=(T - gs[j]) / 1000 if j >= 0 else 999.0,
                                     edge_f=ff - lp if lp == lp else np.nan, edge_c=fc - lp if lp == lp else np.nan, c_minus_f=fc - ff,
                                     o_n500=int(mb.sum()), o_ntouch=int(mbt.sum()), o_nburst_touch=int((mbt & Q["burst"]).sum()),
                                     o_top_gap=(top - bbs) if top == top else -1.0,
                                     o_qahead=float(np.median(Q["qa"][mbt])) if mbt.any() else -1.0,
                                     f_nsold=int((fl & (gup == s_up)).sum()), f_zsold=float(gz[fl & (gup == s_up)].sum()),
                                     f_n=int(fl.sum())))
    B, S = pd.DataFrame(bins), pd.DataFrame(secs)
    S.to_parquet(C / "it6" / f"a4_secs_{a}_{b}.parquet", index=False)
    P = dict(objective="binary", num_leaves=7, min_data_in_leaf=40, learning_rate=0.05, lambda_l2=10, max_bin=63, verbose=-1, seed=8)
    out = {"fill_presence": {"bins": int(len(B)), "windows": int(B.st.nunique()), "pos_rate": round(float(B.y.mean()), 4),
                             "test_windows": int(B[B.st >= SPLIT].st.nunique()), "test_pos": int(B[B.st >= SPLIT].y.sum())}}
    ACT = ["rel", "s_up", "n10", "n30", "sold10", "bought10", "last", "age"]
    PUB = ACT + ["edge_f", "edge_c", "c_minus_f"]
    OR = ["o_n500", "o_ntouch", "o_nburst_touch", "o_top_gap", "o_qahead"]
    FL = ["f_nsold", "f_zsold", "f_n"]
    tr, te = B[B.st < SPLIT], B[B.st >= SPLIT]
    for nm, cols in (("activity", ACT), ("public_rule", PUB), ("activity+quote_oracle", ACT + OR), ("public+quote_oracle", PUB + OR),
                     ("activity+future_flow", ACT + FL), ("activity+quote_oracle+future_flow", ACT + OR + FL),
                     ("all_oracles", PUB + OR + FL)):
        mdl = lgb.train(P, lgb.Dataset(tr[cols], tr.y), 200)
        out["fill_presence"][nm] = round(float(roc_auc_score(te.y, mdl.predict(te[cols]))), 4)
    for c in OR:
        out["fill_presence"]["univariate_" + c] = round(float(roc_auc_score(te.y, te[c])), 4)
    out["quote_unit"] = {"seconds": int(len(S)), "pos_rate": round(float(S.y.mean()), 4),
                         "test_pos_rate": round(float(S[S.st >= SPLIT].y.mean()), 4)}
    QA = ["rel", "s_up", "spread", "mid", "tau", "n2", "n10", "last_age", "last_sold_s", "tch_age"]
    trs, tes = S[S.st < SPLIT], S[S.st >= SPLIT].copy()
    for nm, cols in (("activity", QA), ("activity+futures", QA + ["e_f"]), ("activity+chainlink", QA + ["e_cl"]),
                     ("activity+futures+chainlink", QA + ["e_f", "e_cl"]), ("chainlink_only", ["e_cl", "tau", "s_up"])):
        mdl = lgb.train(P, lgb.Dataset(trs[cols], trs.y), 300)
        sc = mdl.predict(tes[cols])
        out["quote_unit"][nm] = round(float(roc_auc_score(tes.y, sc)), 4)
        tes["sc_" + nm] = sc
    a1, a2 = "sc_activity", "sc_activity+futures+chainlink"
    ws = tes.st.unique()
    rng = np.random.default_rng(8)
    gains = []
    for _ in range(300):
        pick = rng.choice(ws, len(ws), replace=True)
        sub = pd.concat([tes[tes.st == w] for w in pick])
        if sub.y.nunique() < 2:
            continue
        gains.append(roc_auc_score(sub.y, sub[a2]) - roc_auc_score(sub.y, sub[a1]))
    out["quote_unit"]["gain_ci95_window_bootstrap"] = [round(float(np.quantile(gains, .025)), 4), round(float(np.quantile(gains, .975)), 4)]
    out["quote_unit"]["univariate_e_cl"] = round(float(roc_auc_score(tes.y, tes.e_cl.fillna(0))), 4)
    out["quote_unit"]["univariate_e_f"] = round(float(roc_auc_score(tes.y, tes.e_f.fillna(0))), 4)
    out["quote_unit"]["test_windows"] = int(len(ws))
    (HERE.parent / "results" / f"iter8_a4_ceiling_{a}_{b}_split{SPLIT}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
