"""Iteration 13 (X118 = mechanics P1 steps 1-2; pre-registered in NOTES.md iteration 13): (a) the pairing mechanism on VALIDATE
one-sided seconds: logistic of the side (Up = 1) on the frozen side model's logit (offset), the operator's realized LARGE-order
net decayed over [s - 180, s - 2] (K_L), the same for its SMALL orders (placebo, K_S) and the crowd's Up-signed taker flow over
[s - 120, s - 2] (control), by size class of the second; (b) the pre-registered side tilt logit(p) = logit(psb) + b1 z(K_L) +
b2 z(K_L) |logit(psb)|, cross-fitted on VALIDATE halves. Own state (the operator's realized fills): reported with and without,
never part of the presence rule. Writes results/side13.json."""
import os, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
import statsmodels.api as sm
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
VAL0, H = 1792108800, 1792713600
ERA60_END = 1791763200
TAU = 60.0


def kern(times, vals, s_arr, lo=2, hi=180, tau=TAU):
    """sum over events with s - hi <= t <= s - lo of vals * exp(-(s - t) / tau), for sorted times."""
    out = np.zeros(len(s_arr))
    for i, s in enumerate(s_arr):
        a, b = np.searchsorted(times, s - hi, "left"), np.searchsorted(times, s - lo, "right")
        if b > a:
            out[i] = float(np.sum(vals[a:b] * np.exp(-(s - times[a:b]) / tau)))
    return out


def main():
    SC = os.environ.get("SIDE_COL", "psb")
    sd = pd.read_parquet(f"{C}/val_side_it5book.parquet", columns=["cid", "rel", "start_ts", "truth_up", SC]).rename(columns={SC: "psb"})
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["oh", "shares", "cid", "rel", "is_up", "start_ts"])
    fl = fl[(fl.start_ts >= VAL0 - 600) & (fl.start_ts < H)]
    tot = fl.groupby("oh").shares.sum()
    thr = np.where(fl.start_ts < ERA60_END, 80.0, 45.0)
    fl["large"] = tot.reindex(fl.oh).to_numpy() >= thr
    fl["sg"] = np.where(fl.is_up, 1.0, -1.0) * fl.shares
    st = pd.read_parquet(f"{C}/it13/streams_sec.parquet", columns=["cid", "rel", "yL", "yS"]).set_index(["cid", "rel"])
    # crowd Up-signed taker flow per second (cells flow1 of the Up cell), VALIDATE days only
    cf = []
    for fn in sorted(os.listdir(f"{C}/cells")):
        if int(fn.split(".")[0]) < VAL0:
            continue
        d = pd.read_parquet(f"{C}/cells/{fn}", columns=["cid", "rel", "is_up", "flow1"])
        cf.append(d[d.is_up][["cid", "rel", "flow1"]])
    cf = pd.concat(cf, ignore_index=True).sort_values(["cid", "rel"])
    KL, KS, CR = np.zeros(len(sd)), np.zeros(len(sd)), np.zeros(len(sd))
    sd = sd.reset_index(drop=True)
    gfl = {c: g.sort_values("rel") for c, g in fl.groupby("cid")}
    gcf = {c: g for c, g in cf.groupby("cid")}
    for cid, idx in sd.groupby("cid").indices.items():
        s_arr = sd.rel.to_numpy()[idx].astype(float)
        g = gfl.get(cid)
        if g is not None:
            for big, out in ((True, KL), (False, KS)):
                h = g[g.large == big]
                out[idx] = kern(h.rel.to_numpy(float), h.sg.to_numpy(float), s_arr)
        c = gcf.get(cid)
        if c is not None:
            cs = np.r_[0, np.cumsum(c.flow1.to_numpy(float))]; rr = c.rel.to_numpy(float)
            a = np.searchsorted(rr, s_arr - 120, "left"); b = np.searchsorted(rr, s_arr - 2, "right")
            CR[idx] = cs[b] - cs[a]
    sd["KL"], sd["KS"], sd["CR"] = KL, KS, CR
    ix = pd.MultiIndex.from_arrays([sd.cid.to_numpy(), sd.rel.to_numpy().astype(np.int64)])
    sd["yL"] = st.yL.reindex(ix).fillna(0).to_numpy(); sd["yS"] = st.yS.reindex(ix).fillna(0).to_numpy()
    sd["cls"] = np.where(sd.yL != 0, "large", "small")
    p = np.clip(sd.psb.to_numpy(float), 1e-4, 1 - 1e-4); sd["lg"] = np.log(p / (1 - p))
    y = sd.truth_up.to_numpy(int)
    res = {"n": int(len(sd)), "psb_acc": round(float(((sd.psb > 0.5).astype(int) == y).mean()), 4), "share_small_seconds": round(float((sd.cls == "small").mean()), 4)}
    z = lambda x: (x - x.mean()) / (x.std() + 1e-9)
    # (a) mechanism: logistic with offset, by size class
    mech = {}
    for cls in ("small", "large", "all"):
        m = (sd.cls == cls).to_numpy() if cls != "all" else np.ones(len(sd), bool)
        Xm = pd.DataFrame({"KL": z(sd.KL[m]), "KS": z(sd.KS[m]), "CR": z(sd.CR[m])})
        Xm = sm.add_constant(Xm)
        fit = sm.GLM(y[m], Xm, family=sm.families.Binomial(), offset=sd.lg.to_numpy()[m]).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(sd.cid[m])[0]})
        mech[cls] = {"n": int(m.sum()), "coef": {k: round(float(v), 4) for k, v in fit.params.items()}, "t": {k: round(float(v), 2) for k, v in fit.tvalues.items()}}
    res["mechanism_offset_logit"] = mech
    # raw complement rate on small seconds with a sizable realized large net
    sm_ = (sd.cls == "small") & (sd.KL.abs() >= 30)
    res["small_seconds_KL30"] = {"n": int(sm_.sum()), "complement_rate": round(float(((sd.KL[sm_] > 0) != (y[sm_] == 1)).mean()), 4),
                                 "psb_acc_there": round(float(((sd.psb[sm_] > 0.5).astype(int) == y[sm_]).mean()), 4)}
    smS = (sd.cls == "small") & (sd.KS.abs() >= 30)
    res["small_seconds_KS30_placebo"] = {"n": int(smS.sum()), "complement_rate": round(float(((sd.KS[smS] > 0) != (y[smS] == 1)).mean()), 4)}
    nz = sd.KL != 0
    res["own_inventory_only_rule_complement_of_KL"] = {"coverage": round(float(nz.mean()), 4), "acc_where_nonzero": round(float(((sd.KL[nz] < 0).astype(int) == y[nz]).mean()), 4)}
    # (b) pre-registered tilt, cross-fit on VALIDATE halves
    half = (sd.start_ts < (VAL0 + H) // 2).to_numpy()
    zk = z(sd.KL).to_numpy(); ab = np.abs(sd.lg.to_numpy())
    Xt = sm.add_constant(pd.DataFrame({"zK": zk, "zK_abs": zk * ab}))
    acc_new, acc_old, out = np.zeros(len(sd), bool), np.zeros(len(sd), bool), {}
    for fit_m, sc_m, nm in ((half, ~half, "fit_h1_score_h2"), (~half, half, "fit_h2_score_h1")):
        fit = sm.GLM(y[fit_m], Xt[fit_m], family=sm.families.Binomial(), offset=sd.lg.to_numpy()[fit_m]).fit()
        eta = sd.lg.to_numpy()[sc_m] + Xt[sc_m].to_numpy() @ fit.params.to_numpy()
        pn = 1 / (1 + np.exp(-eta))
        acc_new[sc_m] = (pn > 0.5).astype(int) == y[sc_m]
        acc_old[sc_m] = (sd.psb.to_numpy()[sc_m] > 0.5).astype(int) == y[sc_m]
        out[nm] = {"coef": {k: round(float(v), 4) for k, v in fit.params.items()}, "acc_tilt": round(float(acc_new[sc_m].mean()), 4), "acc_psb": round(float(acc_old[sc_m].mean()), 4)}
    out["pooled_cross_fit"] = {"acc_tilt": round(float(acc_new.mean()), 4), "acc_psb": round(float(acc_old.mean()), 4)}
    for cls in ("small", "large"):
        m = (sd.cls == cls).to_numpy()
        out["by_class_" + cls] = {"acc_tilt": round(float(acc_new[m].mean()), 4), "acc_psb": round(float(acc_old[m].mean()), 4)}
    res["tilt_cross_fit"] = out
    json.dump(res, open(f"{R}/side13{'' if SC == 'psb' else '_' + SC}.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
