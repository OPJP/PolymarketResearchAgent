"""Iteration 17, E2 / E7 (brief 2026-11-01): the shape of what the best side rule (dc14, frozen) leaves unexplained, on the operator taker
orders of 10-17..19 (dc14's fit days, in-sample) and 10-20..22 (scored once in iteration 14; aggregates only). Miss = dc14 side !=
the bought outcome. Shape by window minute, UTC hour, price level |price - 0.5|, model confidence |p - 0.5|, wallet, size class
(exact calldata, 10-20..22), slot class (fast / seq / first), and miss clustering: within-window overdispersion (beta-binomial
intraclass correlation of misses per window vs 200 within-day shuffles of the miss labels across windows) and residual_clustering of
the misses' match times across the two outcomes' tracks (period 300 s) as the cross-'market' synchrony check (E7).
Usage: python e2_17.py"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import indicators as ind
S = os.environ["RE16_SCRATCH"]
p = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "osz", "start_ts", "rel", "p_dc14_spot_own"])
p["dd"] = pd.to_datetime(p.start_ts, unit="s").dt.strftime("%m-%d")
mp = pd.concat([pd.read_parquet(f"{S}/it15/l2ord_2026-{d}.parquet", columns=["tx", "cid", "wallet", "m", "price"]) for d in ("10-17", "10-18", "10-19", "10-20", "10-21", "10-22")
                if os.path.exists(f"{S}/it15/l2ord_2026-{d}.parquet")]).drop_duplicates(["cid", "wallet", "m"])
p = p.merge(mp[["cid", "wallet", "m", "price", "tx"]], on=["cid", "wallet", "m"], how="left")
cds = [pd.read_parquet(f"{S}/it16/cdfull_{d}.parquet", columns=["tx", "role", "taker_amt", "oside"]) for d in ("10-20", "10-21", "10-22")]
cd = pd.concat(cds); cd = cd[(cd.role == "T") & (cd.oside == 0)]; cd["tx"] = cd.tx.str.lower()
p["tx"] = p.tx.str.lower()
p = p.merge(cd[["tx", "taker_amt"]].drop_duplicates("tx"), on="tx", how="left")
p["miss"] = ((p.p_dc14_spot_own > 0.5).astype(int) != p.up).astype(int)
q = p.sort_values(["cid", "up", "m"]); gap = q.m - q.groupby(["cid", "up"]).m.shift(); p.loc[q.index, "gap"] = gap
p["slot"] = np.where(p.gap < 150, "fast", np.where(p.gap < 400, "seq", "first"))
p["minute"] = (p.m / 1000.0 - p.start_ts) // 60
p["hour"] = pd.to_datetime(p.m, unit="ms").dt.hour
p["plev"] = pd.cut((p.price - 0.5).abs(), [0, 0.1, 0.2, 0.3, 0.4, 0.5], include_lowest=True).astype(str)
p["conf"] = pd.cut((p.p_dc14_spot_own - 0.5).abs(), [0, 0.1, 0.2, 0.3, 0.4, 0.5], include_lowest=True).astype(str)
p["size"] = np.where(p.taker_amt.isna(), "na", np.where(p.taker_amt >= 90, "large", "small"))
res = {}
for per, days in (("fit_10-17_19_insample", ["10-17", "10-18", "10-19"]), ("scored_10-20_22", ["10-20", "10-21", "10-22"])):
    x = p[p.dd.isin(days)]
    r = {"n": int(len(x)), "miss_rate": round(float(x.miss.mean()), 4)}
    for k in ("minute", "hour", "plev", "conf", "wallet", "slot", "size"):
        g = x.groupby(k).miss.agg(["mean", "size"])
        r[k] = {str(i): [round(float(a), 4), int(b)] for i, (a, b) in g.iterrows()}
    # within-window clustering of misses: ICC via variance of window miss rates vs shuffle within day
    w = x.groupby("start_ts").miss.agg(["sum", "size"]); w = w[w["size"] >= 5]
    obs = float(np.var(w["sum"] / w["size"]))
    rng = np.random.default_rng(1); nul = []
    lab = x[x.start_ts.isin(w.index)].copy()
    for _ in range(200):
        lab["sh"] = lab.groupby("dd").miss.transform(lambda s: rng.permutation(s.to_numpy()))
        ww = lab.groupby("start_ts").sh.mean(); nul.append(float(np.var(ww)))
    r["window_miss_rate_var_obs_vs_null"] = [round(obs, 5), round(float(np.mean(nul)), 5), round(float((np.array(nul) >= obs).mean()), 4)]
    # E7 analogue: misses on the Up track vs the Down track coincide within 2 s beyond rigid 300-s-multiple shifts?
    mm = x[x.miss == 1]
    try:
        rc = ind.residual_clustering(mm.m.to_numpy() / 1000.0, mm.up.to_numpy(), delta_s=2.0, n_null=300, period_s=300, top=5)
        r["E7_residual_clustering_up_vs_down"] = {k: rc[k] for k in ("obs", "null_mean", "ratio", "p") if k in rc}
    except Exception as e:
        r["E7_residual_clustering_up_vs_down"] = str(e)
    res[per] = r
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/e2_17.json", "w"), indent=1, default=str)
for per in res:
    r = res[per]; print(per, r["n"], r["miss_rate"])
    for k in ("minute", "plev", "conf", "slot", "size", "wallet"):
        print(" ", k, r[k])
    print("  hour", {h: v[0] for h, v in r["hour"].items()})
    print("  window var", r["window_miss_rate_var_obs_vs_null"], "E7", r["E7_residual_clustering_up_vs_down"])
