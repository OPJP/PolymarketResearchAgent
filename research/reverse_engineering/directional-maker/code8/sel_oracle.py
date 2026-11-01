"""Iteration 8 (A4 / X72 continued): print-level selection ceiling with the observed quote as an oracle.

Unit = clean BTC 5m print (one per transaction; cluster taker transactions removed), label = the transaction holds a
cluster maker fill. Development live block 10-31 14:06-16:30 UTC; fit on windows starting before 15:00, test after.
Feature sets at the print's server ms T:
  activity: time in window, print size, price of the sold token, prints in the last 2 / 10 s, ms since the previous
            print, same-direction prints in the last 2 s, spread and the sold token's best bid vs the price;
  public:   + Chainlink edge of the sold token (report stamped floor((T - 1432)/1000)) and futures edge vs the price;
  oracle:   + cluster-class quote state on the sold side just before T: an exact-500 add at a price the print reaches
            (>= p on the sold token) in (T - 1500, T], the highest such add minus p, burst multiplicity, its age, and
            the queue that stood at its level when it was added. (Never counts toward the target: it uses the
            cluster's own quotes.)
    python code8/sel_oracle.py 1793455600 1793464202
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
sys.path.insert(0, str(HERE))
from pres_live import load_ref, CL  # noqa: E402
from a4_ceiling import bursts  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
SPLIT = 1793458800
D_CL = 1432


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
    mk_tx = set(cd.loc[(cd.role == "maker") & cd.maker.isin(CL), "tx"]) | set(
        acts.loc[(acts.type == "TRADE") & (acts.side == "BUY"), "tx"])
    tk_tx = set(cd.loc[(cd.role == "taker") & cd.maker.isin(CL), "tx"])
    x["h"] = x.h.str.lower()
    x = x[~x.h.isin(tk_tx)].copy()
    d = x.d.astype(str).str.upper().str[0]
    x["s_up"] = ((x.ai == 0) & (d == "S")) | ((x.ai == 1) & (d == "B"))
    x["p_up"] = np.where(x.ai == 0, x.p, 1 - x.p)
    x["y"] = x.h.isin(mk_tx).astype(int)
    ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet", columns=["s", "w", "side", "p", "d", "prev"])
    e5 = ev[(ev.d == 500.0) & ev.w.str.contains("btc-updown-5m")].copy()
    del ev
    tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
    fu, cl, tw = load_ref(a, b)
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))
    cls = np.array(sorted(cl))
    clv = np.array([cl[k] for k in cls])
    rows = []
    for slug, g in x.groupby("w"):
        st = int(slug.split("-")[-1])
        if st < a or st + 300 > b or tw.get(st) is None:
            continue
        K_c = tw[st]
        K_f = ms_sec[np.searchsorted(sec, st - 60):np.searchsorted(sec, st)].mean()
        tg = tch[tch.w == slug].sort_values("s")
        ts_, bb_, ba_ = tg.s.to_numpy(), tg.bb.to_numpy(), tg.ba.to_numpy()
        Q = {}
        for side in (1, 0):
            gq = e5[(e5.w == slug) & (e5.side == side)]
            tq, pq = gq.s.to_numpy(np.int64), gq.p.to_numpy()
            bid = bursts(tq, pq) if len(tq) else np.zeros(0, dtype=np.int64)
            bsz = pd.Series(bid).map(pd.Series(bid).value_counts()).to_numpy() if len(bid) else np.zeros(0)
            Q[side] = (tq, pq, bsz, gq.prev.to_numpy())
        gs, gup, gz = g.s.to_numpy(np.int64), g.s_up.to_numpy(), g.z.to_numpy()
        for i, r in enumerate(g.itertuples()):
            T = int(r.s)
            s_up = bool(r.s_up)
            p = r.p_up if s_up else 1 - r.p_up
            jj = np.searchsorted(sec, T // 1000)
            sig = np.std(r1[max(jj - 300, 0):jj]) * 1.4
            tau = max(st + 300 - T / 1000, 1.0)
            fmid = fm[max(np.searchsorted(fs, T, side="right") - 1, 0)]
            ff = norm.cdf(np.log(fmid / K_f) / (sig * np.sqrt(tau))) if sig > 0 else np.nan
            k = np.searchsorted(cls, (T - D_CL) // 1000, side="right") - 1
            fc = norm.cdf(np.log(clv[k] / K_c) / (sig * np.sqrt(tau))) if (k >= 0 and sig > 0) else np.nan
            if not s_up:
                ff, fc = 1 - ff, 1 - fc
            it = np.searchsorted(ts_, T - 1, side="right") - 1
            if it >= 0:
                bbs, bas = (bb_[it], ba_[it]) if s_up else (1 - ba_[it], 1 - bb_[it])
            else:
                bbs, bas = np.nan, np.nan
            tq, pq, bsz, qa = Q[1 if s_up else 0]
            m = (tq > T - 1500) & (tq <= T)
            pz = pq[m] if s_up else 1 - pq[m]
            reach = pz >= p - 1e-9
            if reach.any():
                jbest = np.argmax(np.where(reach, pz, -1))
                o_gap = float(pz[jbest] - p)
                o_burst = int(bsz[m][jbest])
                o_age = float(T - tq[m][jbest])
                o_q = float(qa[m][jbest])
            else:
                o_gap, o_burst, o_age, o_q = (float(pz.max() - p) if len(pz) else -1.0), 0, 9999.0, -1.0
            prev = gs[i - 1] if i > 0 else T - 99999
            rows.append(dict(st=st, y=int(r.y), rel=T / 1000 - st, z=float(r.z), p=p, n2=int(((gs > T - 2000) & (gs < T)).sum()),
                             n10=int(((gs > T - 10000) & (gs < T)).sum()), gap_prev=T - prev,
                             same2=int(((gs > T - 2000) & (gs < T) & (gup == s_up)).sum()), spread=bas - bbs, p_vs_bb=p - bbs,
                             e_cl=fc - p, e_f=ff - p, e_cl_mid=fc - (bbs + bas) / 2, e_f_mid=ff - (bbs + bas) / 2,
                             o_reach=int(reach.any()), o_n=int(reach.sum()), o_gap=o_gap,
                             o_burst=o_burst, o_age=o_age, o_q=o_q))
    D = pd.DataFrame(rows)
    ACT = ["rel", "z", "p", "n2", "n10", "gap_prev", "same2", "spread", "p_vs_bb"]
    PUB = ACT + ["e_cl", "e_f"]
    OR = ["o_reach", "o_n", "o_gap", "o_burst", "o_age", "o_q"]
    P = dict(objective="binary", num_leaves=15, min_data_in_leaf=50, learning_rate=0.05, lambda_l2=10, max_bin=63, verbose=-1, seed=8)
    tr, te = D[D.st < SPLIT], D[D.st >= SPLIT]
    out = {"prints": int(len(D)), "pos": int(D.y.sum()), "test_prints": int(len(te)), "test_pos": int(te.y.sum())}
    PUB2 = PUB + ["e_cl_mid", "e_f_mid"]
    for nm, cols in (("activity", ACT), ("public", PUB), ("public+posture_vs_mid", PUB2), ("activity+quote_oracle", ACT + OR),
                     ("public+quote_oracle", PUB + OR)):
        mdl = lgb.train(P, lgb.Dataset(tr[cols], tr.y), 300)
        s_tr, s_te = mdl.predict(tr[cols]), mdl.predict(te[cols])
        th = np.quantile(s_tr, 0.85)
        flag = s_te >= th
        rec = float(te.y[flag].sum() / max(te.y.sum(), 1))
        lift = rec / max(flag.mean(), 1e-9)
        out[nm] = {"auc": round(float(roc_auc_score(te.y, s_te)), 4), "recall_at_build_top15": round(rec, 3), "lift": round(lift, 2)}
    out["oracle_reach_rate"] = {"cluster_prints": round(float(te.o_reach[te.y == 1].mean()), 3),
                                "other_prints": round(float(te.o_reach[te.y == 0].mean()), 3)}
    (HERE.parent / "results" / f"iter8_sel_oracle2_{a}_{b}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
