"""directional-maker iteration 14, X162 (own, pre-registered 06:31 UTC): QUOTE presence at event time. Same panel and features as
code14/pres_event.py, but the label is the uncensored quote: an at-touch 500/1000 post on the outcome in [T, T+1) (rebuilt
full-depth table it14_qu_rebuilt_*.parquet), and the posture uses the quote form (stamp <= T - 1,000 ms, k 1.0).
Original docstring: fill presence at event time.

Unit = (BTC 5m or 15m window, outcome s, 1-s bin [T, T+1)) on the match clock (server ms of the CLOB trade stream),
label = a cluster maker BUY fill on s whose transaction's first print falls in the bin. The same panel is also
aggregated to the pre-registered 10-s unit for comparison. Features at T (server ms; nothing at or after T):
  activity (market only; prints of cluster transactions dropped): rel, s_up, is15, clean prints in the last 1/2/5/10/30 s,
  shares sold on s (bid of s hit) and bought on s in the last 1/5/10 s, the last clean print in s terms and its age,
  whether the last clean print hit s's bid, the Up mid of the book in s terms (touch from the raw book, any maker);
  reference (rule): Chainlink posture edge of s = F_CL(stamp <= T - 1.25 s; 1.4 x 300-s futures-mid sigma) - mid(s),
  the change of F_CL since the report one second earlier, whether a new report arrived, the futures mid move toward s
  over the last 1 and 3 s, and the futures digital fair minus the mid.
Pre-registered (NOTES iteration 14): fit 10-31 14:00-16:00, test 16:00-18:00; LightGBM (num_leaves 7, 200 rounds,
max_bin 63), activity vs activity + reference; 2-h block halves reported; no own state.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code14/pres_event.py 1793455200 1793469600
"""
from __future__ import annotations

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
sys.path.insert(0, str(HERE))
from lagged_quote import fut_mid, at, sec_sigma, cl_source  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
IT13 = C / "it13"
CLU = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88",
       "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


LAG_MS = 1000


def main(a, b):
    mid_t = a + (b - a) // 2
    X = pd.read_parquet(IT13 / "trades.parquet")
    X = X[(X.s >= (a - 60) * 1000) & (X.s < b * 1000)].sort_values("s", kind="stable")
    cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet")) +
                    glob.glob(str(C / "calldata" / "liveall1031_*.parquet"))], ignore_index=True)
    cd["maker"] = cd.maker.str.lower(); cd["tx"] = cd.tx.str.lower()
    mk = cd[(cd.role == "maker") & cd.maker.isin(CLU) & (cd.oside == 0)].copy()
    acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))], ignore_index=True)
    acts["tx"] = acts.transactionHash.str.lower()
    acts = acts.drop_duplicates(subset=["tx", "asset", "size", "price"])
    fills = acts[(acts.type == "TRADE") & (acts.side == "BUY") & acts.tx.isin(set(mk.tx))].copy()
    first = X.groupby(X.h.str.lower()).s.min()
    fills["ms"] = fills.tx.map(first)
    fills = fills[fills.ms.notna() & fills.slug.str.contains("btc-updown-(?:5m|15m)-", regex=True, na=False)]
    fills["up"] = (fills.outcome == "Up").astype(int)
    print("cluster maker BUY fills with a match ms", len(fills), "txs", fills.tx.nunique())
    clean = X[~X.cluster_tx].drop_duplicates("h").copy()
    d = clean.d.astype(str).str.upper().str[0]
    clean["hit_up"] = (((clean.ai == 0) & (d == "S")) | ((clean.ai == 1) & (d == "B"))).astype(int)
    clean["p_up"] = np.where(clean.ai == 0, clean.p, 1 - clean.p)
    QU = pd.read_parquet(C / f"it14_qu_rebuilt_{a}_{b}.parquet")
    S = pd.read_parquet(IT13 / "sched_adds.parquet", columns=["w", "s", "bb", "ba"])
    S = S[(S.s >= (a - 60) * 1000) & (S.s < b * 1000)].sort_values(["w", "s"], kind="stable")
    E, M = fut_mid(a - 3600, b)
    sig = sec_sigma(E, M, 300)
    clv = cl_source.cl_values(list(range(a - 10, b + 1)), allow_sealed=False, fetch=True, max_requests=200)
    from polyrea.workflows.updown_study import fetch_windows
    wins = sorted(w for w in set(X.w) if int(w.rsplit("-", 1)[1]) >= a and int(w.rsplit("-", 1)[1]) < b)
    raw = fetch_windows(wins)
    K = {}
    for m in raw.values():
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    rows = []
    for w in wins:
        st = int(w.rsplit("-", 1)[1]); L = 900 if "-15m-" in w else 300
        if st + L > b + 1 or w not in K:
            continue
        T = (st + np.arange(L)) * 1000
        g = clean[clean.w == w]; gs = g.s.to_numpy(np.int64)
        gz = g.z.to_numpy(float); gh = g.hit_up.to_numpy(int); gp = g.p_up.to_numpy(float)
        sb = S[S.w == w]; ss = sb.s.to_numpy(np.int64); smid = ((sb.bb + sb.ba) / 2).to_numpy(float)
        mid_up = at(ss, smid, T - 1)
        lp = at(gs, gp, T - 1)
        j = np.searchsorted(gs, T, side="left") - 1
        age = np.where(j >= 0, (T - gs[np.clip(j, 0, None)]) / 1000, 999.0)
        lasthit = np.where(j >= 0, gh[np.clip(j, 0, None)], -1)
        cz = np.concatenate([[0], np.cumsum(gz)]); czu = np.concatenate([[0], np.cumsum(gz * gh)])

        def cnt(win):
            i0 = np.searchsorted(gs, T - win * 1000, side="left"); i1 = np.searchsorted(gs, T, side="left")
            return i1 - i0, cz[i1] - cz[i0], czu[i1] - czu[i0]
        feats = {}
        for win in (1, 2, 5, 10, 30):
            n_, z_, zu_ = cnt(win)
            feats[f"n{win}"] = n_
            if win in (1, 5, 10):
                feats[f"zup{win}"] = zu_; feats[f"zdn{win}"] = z_ - zu_
        cl0 = clv.reindex((T - LAG_MS) // 1000).to_numpy(float)
        cl1 = clv.reindex((T - LAG_MS - 1000) // 1000).to_numpy(float)
        sg = sig.reindex(T // 1000).to_numpy(float) * 1.0
        tau = np.maximum(st + L - T / 1000, 1.0)
        F0 = norm.cdf((cl0 - K[w]) / (sg * np.sqrt(tau))); F1 = norm.cdf((cl1 - K[w]) / (sg * np.sqrt(tau)))
        f0 = at(E, M, T - 50); f1 = at(E, M, T - 1000); f3 = at(E, M, T - 3000)
        Kf = np.nanmean(at(E, M, (st - 60 + np.arange(60)) * 1000))
        Ff = norm.cdf((f0 - Kf) / (sg * np.sqrt(tau)))
        fw = QU[(QU.w == w) & QU.dz.isin([500.0, 1000.0])]
        for s_up in (1, 0):
            sgn = 1 if s_up else -1
            lab = np.zeros(L, int)
            fm = fw[fw.sd == s_up].s.to_numpy(np.int64)
            k_ = ((fm - st * 1000) // 1000).astype(int)
            k_ = k_[(k_ >= 0) & (k_ < L)]
            lab[k_] = 1
            m_s = mid_up if s_up else 1 - mid_up
            r = pd.DataFrame({"y": lab, "w": w, "st": st, "T": T // 1000, "rel": np.arange(L), "is15": int(L == 900), "s_up": s_up,
                              "last": lp if s_up else 1 - lp, "age": age,
                              "lasthit_s": np.where(lasthit < 0, -1, (lasthit == s_up).astype(int)),
                              "mid_s": m_s,
                              "edge_cl": (F0 if s_up else 1 - F0) - m_s, "dF_cl": (F0 - F1) * sgn,
                              "new_rep": (np.abs(cl0 - cl1) > 1e-9).astype(int),
                              "fut1": (f0 - f1) * sgn, "fut3": (f0 - f3) * sgn, "edge_fut": (Ff if s_up else 1 - Ff) - m_s})
            for k2, v in feats.items():
                if k2.startswith("zup"):
                    r[("sold" if s_up else "bought") + k2[3:]] = v
                elif k2.startswith("zdn"):
                    r[("bought" if s_up else "sold") + k2[3:]] = v
                else:
                    r[k2] = v
            rows.append(r)
    D = pd.concat(rows, ignore_index=True)
    D = D[D.mid_s.notna()]
    ACT = ["rel", "is15", "s_up", "last", "age", "lasthit_s", "mid_s", "n1", "n2", "n5", "n10", "n30",
           "sold1", "sold5", "sold10", "bought1", "bought5", "bought10"]
    REF = ["edge_cl", "dF_cl", "new_rep", "fut1", "fut3", "edge_fut"]
    import lightgbm as lgb
    P = dict(objective="binary", num_leaves=7, min_data_in_leaf=40, learning_rate=0.05, lambda_l2=10, max_bin=63,
             verbose=-1, seed=14)
    tr, te = D[D["T"] < mid_t], D[D["T"] >= mid_t].copy()
    out = {"cells": int(len(D)), "pos_rate": float(D.y.mean()), "train": int(len(tr)), "test": int(len(te)),
           "test_pos": int(te.y.sum()), "windows": int(D.w.nunique())}
    for nm, cols in (("activity", ACT), ("activity+ref", ACT + REF), ("activity+chainlink", ACT + ["edge_cl", "dF_cl", "new_rep"])):
        m = lgb.train(P, lgb.Dataset(tr[cols], tr.y), 200)
        te["sc_" + nm] = m.predict(te[cols])
        if LAG_MS == 1432:   # frozen models: point-in-time-safe stamp lag (p90 publish delay)
            (HERE / "models").mkdir(exist_ok=True)
            m.save_model(str(HERE / "models" / f"quote_presence_{nm.replace('+', '_')}.txt"))
        out[nm] = {"auc_1s": float(roc_auc_score(te.y, te["sc_" + nm]))}
        if nm == "activity+ref":
            imp = dict(zip(cols, m.feature_importance("gain").round(1)))
            out["importance_gain"] = dict(sorted(imp.items(), key=lambda kv: -kv[1])[:12])
        for fam, g in te.groupby("is15"):
            out[nm][f"auc_1s_{'15m' if fam else '5m'}"] = float(roc_auc_score(g.y, g["sc_" + nm]))
    # 10-s aggregation of the same scores (max over the bin's first-second scores is NOT point-in-time; use the bin-start
    # second's score only, i.e. features at the 10-s bin start), for the unit comparison
    te["b10"] = te.rel // 10
    agg = te.groupby(["w", "s_up", "b10"]).agg(y=("y", "max"), rel=("rel", "min"))
    first = te[te.rel % 10 == 0].set_index(["w", "s_up", "b10"])
    j = agg.join(first[[c for c in te.columns if c.startswith("sc_")]], how="inner")
    out["unit_10s_bin_start_scores"] = {c[3:]: float(roc_auc_score(j.y, j[c])) for c in j.columns if c.startswith("sc_")}
    out["unit_10s_pos_rate"] = float(j.y.mean())
    # proper 10-s unit (iteration 14 addendum): label = any post in [t, t+10), features at the bin start, models refit
    D["b10"] = D.rel // 10
    lab10 = D.groupby(["w", "s_up", "b10"]).y.max().rename("y10")
    D10 = D[D.rel % 10 == 0].join(lab10, on=["w", "s_up", "b10"])
    tr10, te10 = D10[D10["T"] < mid_t], D10[D10["T"] >= mid_t].copy()
    out["unit_10s_refit"] = {"cells_test": int(len(te10)), "pos_rate_test": float(te10.y10.mean())}
    for nm, cols in (("activity", ACT), ("activity+ref", ACT + REF), ("activity+chainlink", ACT + ["edge_cl", "dF_cl", "new_rep"])):
        m10 = lgb.train(P, lgb.Dataset(tr10[cols], tr10.y10), 200)
        te10["sc_" + nm] = m10.predict(te10[cols])
        out["unit_10s_refit"][nm] = float(roc_auc_score(te10.y10, te10["sc_" + nm]))
    out["unit_10s_refit"]["gain"] = out["unit_10s_refit"]["activity+ref"] - out["unit_10s_refit"]["activity"]
    gain = out["activity+ref"]["auc_1s"] - out["activity"]["auc_1s"]
    out["gain_1s"] = gain
    # block bootstrap of the gain over 20-min blocks of the test half (2-h blocks would leave one block)
    rng = np.random.default_rng(14)
    te["blk"] = (te["T"] - mid_t) // 1200
    bl = te.blk.unique(); gs_ = []
    for _ in range(300):
        pick = rng.choice(bl, len(bl), replace=True)
        s_ = pd.concat([te[te.blk == k] for k in pick])
        if s_.y.nunique() < 2:
            continue
        gs_.append(roc_auc_score(s_.y, s_["sc_activity+ref"]) - roc_auc_score(s_.y, s_["sc_activity"]))
    out["gain_1s_boot_20min_q025_q975"] = [float(np.quantile(gs_, 0.025)), float(np.quantile(gs_, 0.975))]
    (HERE.parent / "results" / f"iter14_pres_quote_{a}_{b}{'' if LAG_MS == 1000 else '_L' + str(LAG_MS)}.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    if len(sys.argv) > 3:
        LAG_MS = int(sys.argv[3])
    main(int(sys.argv[1]), int(sys.argv[2]))
