"""Iteration 11: score the window replay (code11/replay.py) against the cluster's windows.

Pre-registered before any VALIDATE number was read (NOTES iteration 11):
  * candidate set = strict fills (touch 0) with latency L = 2 (the examiner's conventions), every side rule, delta, size
    and flow; the STUDY criterion = mean of Pearson and Spearman of the per-window PnL (cluster maker BUY fills pooled
    over the three wallets) over windows with >= 1 cluster maker fill; the best STUDY candidate is the frozen replay;
  * VALIDATE (10-27..30) is reported as aggregates only, for the frozen candidate and (as a table) for the side rules at
    the frozen delta / size / flow;
  * window net side: windows whose cluster maker BUY shares are >= 70% one side; predicted = sign(replay Up - Down),
    with the window's time-weighted posture majority where the replay has no net position.
    python code11/replay_score.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache" / "re" / "directional-maker" / "it11"
RES = HERE.parent / "results"
SPLIT_V = 1793059200
HALF_V = 1793232000


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return [float("nan"), float("nan")]
    return [float(np.corrcoef(a, b)[0, 1]), float(pd.Series(a).corr(pd.Series(b), method="spearman"))]


def main():
    R = pd.read_parquet(C / "replay_windows.parquet")
    B = pd.read_parquet(C / "replay_window_base.parquet").drop_duplicates("cid").set_index("cid")
    CW = pd.read_parquet(C / "cluster_windows.parquet")
    mk = CW[CW.role == "maker"]
    cl = mk.groupby("cid").agg(pnl=("pnl", "sum"), up=("up", "sum"), dn=("dn", "sum"), usd=("usd", "sum"))
    allb = CW.groupby("cid").agg(pnl_all=("pnl", "sum"))
    cl = cl.join(allb, how="outer")
    B = B.join(cl, how="left")
    B[["pnl", "up", "dn", "usd", "pnl_all"]] = B[["pnl", "up", "dn", "usd", "pnl_all"]].fillna(0.0)
    B["has"] = (B.up + B.dn) > 0
    B["split"] = np.where(B.st < SPLIT_V, "study", "validate")
    tot = B.up + B.dn
    B["maj_share"] = np.where(tot > 0, np.maximum(B.up, B.dn) / tot.where(tot > 0, 1), np.nan)
    B["one_sided"] = B.has & (B.maj_share >= 0.7)
    B["cl_side_up"] = (B.up > B.dn).astype(int)
    perw = {w: g.groupby("cid")["pnl"].sum() for w, g in mk.groupby("wallet")}
    R["key"] = list(zip(R.L, R.flow, R.delta, R.touch, R.side, R.q))
    out = {"n_windows": {s: int((B.split == s).sum()) for s in ("study", "validate")},
           "windows_with_cluster_maker_fills": {s: int((B.has & (B.split == s)).sum()) for s in ("study", "validate")},
           "one_sided_windows": {s: int((B.one_sided & (B.split == s)).sum()) for s in ("study", "validate")}}

    def score(key_df, split, extra=False):
        g = key_df.set_index("cid").reindex(B.index)
        g[["pnl", "up", "dn", "usd"]] = g[["pnl", "up", "dn", "usd"]].fillna(0.0)
        m = (B.split == split)
        res = {}
        a = m & B.has
        res["corr_has"] = corr(g.pnl[a], B.pnl[a])
        res["corr_all"] = corr(g.pnl[m], B.pnl[m])
        res["corr_has_allbuy"] = corr(g.pnl[a], B.pnl_all[a])
        net = g.up - g.dn
        pred_up = np.where(net != 0, (net > 0).astype(int), (B.post_frac_up > 0.5).astype(int))
        o = m & B.one_sided
        res["net_side_acc_one_sided"] = float(np.mean(pred_up[o] == B.cl_side_up[o])) if o.any() else float("nan")
        o2 = o & (net != 0)
        res["net_side_acc_replay_has_net"] = float(np.mean(pred_up[o2] == B.cl_side_up[o2])) if o2.any() else float("nan")
        res["replay_net_coverage_one_sided"] = float(o2.sum() / max(o.sum(), 1))
        res["replay_windows_with_fills"] = int(((g.up + g.dn) > 0)[m].sum())
        res["replay_return_on_usd"] = float(g.pnl[m].sum() / g.usd[m].sum()) if g.usd[m].sum() > 0 else float("nan")
        res["replay_usd"] = float(g.usd[m].sum())
        if extra:
            for h, mh in (("h1", m & (B.st < HALF_V)), ("h2", m & (B.st >= HALF_V))) if split == "validate" else \
                    (("h1", m & (B.st < SPLIT_V - 2 * 86400)), ("h2", m & (B.st >= SPLIT_V - 2 * 86400))):
                ah = mh & B.has
                oh = mh & B.one_sided
                res[f"{h}_corr_has"] = corr(g.pnl[ah], B.pnl[ah])
                res[f"{h}_net_side_acc"] = float(np.mean(pred_up[oh] == B.cl_side_up[oh])) if oh.any() else float("nan")
            for s_, ms in (("us_session", m & (B.sess == 1)), ("off_session", m & (B.sess == 0))):
                a_ = ms & B.has
                o_ = ms & B.one_sided
                res[f"{s_}_corr_has"] = corr(g.pnl[a_], B.pnl[a_])
                res[f"{s_}_net_side_acc"] = float(np.mean(pred_up[o_] == B.cl_side_up[o_])) if o_.any() else float("nan")
                res[f"{s_}_windows_has"] = int(a_.sum())
            pw = {}
            for wname, ser in perw.items():
                s2 = ser.reindex(B.index[m]).dropna()
                pw[wname] = corr(g.pnl.reindex(s2.index), s2)
                pw[wname + "_windows"] = int(len(s2))
            res["per_wallet_corr"] = pw
            # E4: does the replay's net position sit on the winner (corr(net, outcome)) like the cluster's, per day
            byday = {}
            for d_, md in B[m].groupby("day"):
                ii = md.index
                outc = md.pay_up - 0.5
                byday[str(pd.to_datetime(d_, unit="s").date())] = {
                    "replay_corr_net_outcome": corr(net.reindex(ii), outc)[1],
                    "cluster_corr_net_outcome": corr((md.up - md.dn), outc)[1]}
            res["by_day_spearman_net_vs_outcome"] = byday
        return res

    # STUDY: all strict L=2 candidates
    cand = R[(R.L == 2) & (R.touch == 0)]
    tab = []
    for key, g in cand.groupby("key"):
        s = score(g, "study")
        tab.append(dict(L=key[0], flow=key[1], delta=key[2], touch=key[3], side=key[4], q=key[5], pear=s["corr_has"][0],
                        spear=s["corr_has"][1], crit=np.nanmean(s["corr_has"]), side_acc=s["net_side_acc_one_sided"],
                        ret=s["replay_return_on_usd"]))
    T = pd.DataFrame(tab).sort_values("crit", ascending=False)
    T.to_csv(C / "replay_study_table.csv", index=False)
    best = T.iloc[0]
    out["study_top10"] = T.head(10).round(4).to_dict("records")
    out["study_by_side_best"] = T.groupby("side").head(1).round(4).to_dict("records")
    bkey = (int(best.L), best.flow, float(best.delta), int(best.touch), best.side, best.q)
    out["frozen_key"] = list(map(str, bkey))
    gb = R[R.key == bkey]
    out["frozen_study"] = score(gb, "study", extra=True)
    out["frozen_validate"] = score(gb, "validate", extra=True)
    # VALIDATE table for every side rule at the frozen delta / size / flow, strict L=2 (aggregate)
    vt = {}
    for side in ("posture", "two", "cheaper", "fav", "pickoff"):
        k2 = (2, bkey[1], bkey[2], 0, side, bkey[5])
        g2 = R[R.key == k2]
        if len(g2):
            s = score(g2, "validate")
            vt[side] = {"corr_has": s["corr_has"], "corr_all": s["corr_all"], "net_side_acc": s["net_side_acc_one_sided"],
                        "ret": s["replay_return_on_usd"]}
    out["validate_by_side_frozen_params"] = vt
    # sensitivities of the frozen candidate on VALIDATE (aggregate): latency 0, at-touch, other flow, other size
    sens = {}
    for nm, k2 in {"L0": (0,) + bkey[1:], "flow_other": (2, "clean" if bkey[1] == "full" else "full") + bkey[2:],
                   "touch_delta0.01": (2, bkey[1], 0.01, 1, bkey[4], bkey[5]),
                   "q1": bkey[:5] + ("q1",), "q500": bkey[:5] + ("q500",), "qsess": bkey[:5] + ("qsess",),
                   "q100": bkey[:5] + ("q100",)}.items():
        g2 = R[R.key == k2]
        if len(g2):
            s = score(g2, "validate")
            s2 = score(g2, "study")
            sens[nm] = {"validate_corr_has": s["corr_has"], "study_corr_has": s2["corr_has"],
                        "validate_net_side": s["net_side_acc_one_sided"], "validate_ret": s["replay_return_on_usd"]}
    out["sensitivities"] = sens
    RES.mkdir(exist_ok=True)
    (RES / "iter11_replay.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("n_windows", "windows_with_cluster_maker_fills", "one_sided_windows", "frozen_key")}, default=str))
    print("STUDY top:", T.head(8).round(3).to_string(index=False))
    print("STUDY best by side:", T.groupby("side").head(1).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
