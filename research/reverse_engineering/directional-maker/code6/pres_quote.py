"""Iteration 6 VARIANT (pres_quote.py): label = exact-500 add within one tick of the touch on side s in the bin (quote presence via the 88%-precision fingerprint). Base: presence (primary-metric unit) on the live block with the Chainlink input (panel I2 follow-up, X27).

Unit = (BTC 5m window, side s, 10-s bin [t, t+10)), label = cluster maker BUY fill on s in the bin (match ms from the
CLOB trade stream, else the activity second). Features at the bin start T (server ms), point-in-time:
  activity: clean prints (no cluster tx) in the last 10 / 30 s, shares sold on s in the last 10 s, the last clean print
  in s terms and its age, time in window;
  futures: digital fair of s from the futures bookTicker mid at T (strike = futures TWAP of [start-60, start)) minus the
  last print;
  chainlink: digital fair of s from the RTDS Chainlink value stamped <= T - 2 s (published with a measured <= 1.8 s delay,
  so known by T) against the true strike (RTDS TWAP-60 stamped at the window start) minus the last print; chainlink fair
  minus futures fair.
Pre-registered split: fit on windows starting before 15:00 UTC, test on the later ones.
    python code6/pres_live.py <start_ts> <end_ts>
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
from rawread import iter_dm  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88",
      "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
SPLIT = 1793458800
CL_LAG_S = 2


def load_ref(a, b):
    fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", a - 400, b) if r["r"][0] == "b" and r["r"][2]]
    fu = pd.DataFrame(fut, columns=["s", "m"]).sort_values("s").drop_duplicates("s", keep="last")
    cl, tw = {}, {}
    for r in iter_dm("dm_rtds", a - 400, b + 60):
        try:
            j = json.loads(r["m"])
        except ValueError:
            continue
        for x in (j.get("payload") or {}).get("data", []) or []:
            (cl if r["q"] == "crypto_prices_chainlink" else tw)[int(x["timestamp"]) // 1000] = float(x["value"])
    return fu, cl, tw


def main(a, b):
    evq = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet")
    evq = evq[evq.w.str.contains("btc-updown-5m") & (evq.d == 500.0)]
    evq = evq[np.where(evq.side == 1, (evq.bb - evq.p) <= 0.0105, (evq.p - evq.ba) <= 0.0105)]
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
    fu, cl, tw = load_ref(a, b)
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))
    cls = np.array(sorted(cl))
    clv = np.array([cl[k] for k in cls])
    rows = []
    for slug in sorted(set(x.w)):
        st = int(slug.split("-")[-1])
        if st < a or st + 300 > b:
            continue
        g = xc[xc.w == slug]
        gs, gp, gup, gz = g.s.to_numpy(), g.p_up.to_numpy(), g.s_up.to_numpy(), g.z.to_numpy()
        f = fills[fills.slug == slug]
        K_f = ms_sec[np.searchsorted(sec, st - 60):np.searchsorted(sec, st)].mean()
        K_c = tw.get(st)
        for t in range(0, 300, 10):
            T = (st + t) * 1000
            j = np.searchsorted(gs, T, side="left") - 1
            last_up = gp[j] if j >= 0 else np.nan
            age = (T - gs[j]) / 1000 if j >= 0 else 999.0
            jj = np.searchsorted(sec, st + t)
            sig = np.std(r1[max(jj - 300, 0):jj]) * 1.4
            tau = max(300 - t, 1.0)
            fmid = fm[max(np.searchsorted(fs, T, side="right") - 1, 0)]
            fair_f = norm.cdf(np.log(fmid / K_f) / (sig * np.sqrt(tau))) if sig > 0 else np.nan
            k = np.searchsorted(cls, st + t - CL_LAG_S, side="right") - 1
            fair_c = norm.cdf(np.log(clv[k] / K_c) / (sig * np.sqrt(tau))) if (K_c is not None and k >= 0 and sig > 0) else np.nan
            m10 = (gs >= T - 10000) & (gs < T)
            m30 = (gs >= T - 30000) & (gs < T)
            for s_up in (True, False):
                qq = evq[(evq.w == slug) & (evq.side == (1 if s_up else 0)) & (evq.s >= T) & (evq.s < T + 10000)]
                y = int(len(qq) > 0)
                lp = last_up if s_up else 1 - last_up
                rows.append({"y": y, "st": st, "rel": t, "s_up": int(s_up), "n10": int(m10.sum()), "n30": int(m30.sum()),
                             "sold10": float(gz[m10 & (gup == s_up)].sum()), "bought10": float(gz[m10 & (gup != s_up)].sum()),
                             "last": lp, "age": age,
                             "edge_f": (fair_f if s_up else 1 - fair_f) - lp, "edge_c": (fair_c if s_up else 1 - fair_c) - lp,
                             "c_minus_f": (fair_c - fair_f) * (1 if s_up else -1)})
    D = pd.DataFrame(rows)
    ACT = ["rel", "s_up", "n10", "n30", "sold10", "bought10", "last", "age"]
    tr, te = D[D.st < SPLIT], D[D.st >= SPLIT]
    import lightgbm as lgb
    P = dict(objective="binary", num_leaves=7, min_data_in_leaf=40, learning_rate=0.05, lambda_l2=10, max_bin=63, verbose=-1, seed=6)
    out = {"bins": int(len(D)), "windows": int(D.st.nunique()), "pos_rate": round(float(D.y.mean()), 4),
           "train_bins": int(len(tr)), "test_bins": int(len(te)), "test_windows": int(te.st.nunique())}
    te = te.copy()
    for nm, cols in (("activity", ACT), ("activity+futures", ACT + ["edge_f"]), ("activity+chainlink", ACT + ["edge_c", "c_minus_f"]),
                     ("activity+futures+chainlink", ACT + ["edge_f", "edge_c", "c_minus_f"])):
        m = lgb.train(P, lgb.Dataset(tr[cols], tr.y), 200)
        s = m.predict(te[cols])
        te["sc_" + nm] = s
        out[nm] = round(float(roc_auc_score(te.y, s)), 4)
    # side: (window, bin) pairs where exactly one side fills; predicted side = the side with the larger score / edge
    piv = te.pivot_table(index=["st", "rel"], columns="s_up", values=["y", "edge_c", "edge_f"] + [c for c in te.columns if c.startswith("sc_")])
    one = piv[(piv["y"][1] + piv["y"][0]) == 1]
    side = {"n_one_sided_bins": int(len(one))}
    for col in ["edge_c", "edge_f"] + [c for c in te.columns if c.startswith("sc_")]:
        pred_up = one[col][1] > one[col][0]
        side[col] = round(float((pred_up == (one["y"][1] == 1)).mean()), 3)
    side["always_up"] = round(float((one["y"][1] == 1).mean()), 3)
    out["side_test"] = side
    for col in ("edge_f", "edge_c", "c_minus_f"):
        v = te[[col, "y"]].dropna()
        out[f"univariate_test_auc_{col}"] = round(float(roc_auc_score(v.y, v[col])), 3)
    # side: bins where exactly one side fills; predicted side = higher score of the full model vs activity
    (HERE.parent / "results" / f"iter6_pres_quote_{a}_{b}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
