"""Examiner round 2: diagnosis for the reverse engineer, from the FIRST (early) half of lot f1 only (window start before
the listing cut 10-31 20:25 UTC); the later half gets aggregate numbers only (computed elsewhere).
Where the rule disagrees with the wallet, per component: presence (by hour block, window-level vs within-window, clock
features), side (by branch, edge band, time in window, run state, wallet), price (miss geometry), outcome (window
classes), selection (print classes)."""
from __future__ import annotations

import json

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from r2_common import CLUSTER, EXC, RES, WS

import sel2  # noqa: E402

EV = EXC / "ev"
CUT = json.loads((RES / "exam_r2_step0.json").read_text())["cut_ts"]


def auc(y, s):
    y = np.asarray(y); s = np.asarray(s, float)
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else float("nan")


def main():
    out = {"scope": "early half only: BTC 5m windows starting 10-31 06:00-11:55 and 18:00-20:20 UTC (101 windows)"}
    p = pd.read_parquet(EXC / "panel5_scored.parquet")
    p = p[p.start_ts < CUT].copy()
    p["blk"] = np.where(p.start_ts < 1793448000, "06-12", "18-20:25")
    p["hr"] = (p.start_ts // 3600 % 24).astype(int)
    pr = {}
    for b, g in p.groupby("blk"):
        pr[b] = {"rule": auc(g.y_ex, g.p_rule), "activity": auc(g.y_ex, g.p_activity), "own": auc(g.y_ex, g.p_own),
                 "pos_rate": float(g.y_ex.mean()), "mean_p_rule": float(g.p_rule.mean()), "mean_p_act": float(g.p_activity.mean()),
                 "active_windows": float(g.groupby("cid").y_ex.max().mean())}
    pr["by_hour"] = {int(h): {"rule": round(auc(g.y_ex, g.p_rule), 3), "act": round(auc(g.y_ex, g.p_activity), 3),
                              "pos": round(float(g.y_ex.mean()), 3), "mp_rule": round(float(g.p_rule.mean()), 3)} for h, g in p.groupby("hr")}
    # window level (does the window get a fill at all) vs within active windows
    wl = p.groupby("cid").agg(y=("y_ex", "max"), r=("p_rule", "mean"), a=("p_activity", "mean"))
    act = p.groupby("cid").y_ex.transform("max") > 0
    pr["window_level_auc"] = {"rule": auc(wl.y, wl.r), "activity": auc(wl.y, wl.a), "active_share": float(wl.y.mean())}
    pr["within_active_windows"] = {"rule": auc(p.y_ex[act], p.p_rule[act]), "activity": auc(p.y_ex[act], p.p_activity[act])}
    # within-window ranking only: AUC per window averaged (windows with >= 1 positive)
    ww = [(auc(g.y_ex, g.p_rule), auc(g.y_ex, g.p_activity)) for _, g in p[act].groupby("cid") if 0 < g.y_ex.sum() < len(g)]
    pr["mean_within_window_auc"] = {"rule": float(np.nanmean([a for a, _ in ww])), "activity": float(np.nanmean([b for _, b in ww])), "windows": len(ww)}
    # clock counterfactual: the same model with the clock features of a weekday US-session-off bin (dow 2) - diagnostic only
    m = lgb.Booster(model_file=str(WS / "code" / "presence3_rule.txt"))
    from train2 import SETS
    F = SETS["all_path_xwin"] + ["hour_utc", "dow", "us_session"]
    q = p.copy(); q["dow"] = 2
    pr["clock_counterfactual_dow_wednesday"] = auc(p.y_ex, m.predict(q[F]))
    imp = dict(sorted(zip(F, m.feature_importance("gain").round(0).tolist()), key=lambda x: -x[1])[:8])
    pr["rule_top_gain_features"] = imp
    # by rel bucket
    p["relb"] = pd.cut(p.rel, [-1, 29, 119, 239, 299], labels=["0-30", "30-120", "120-240", "240-300"])
    pr["by_rel"] = {str(k): {"rule": round(auc(g.y_ex, g.p_rule), 3), "act": round(auc(g.y_ex, g.p_activity), 3), "pos": round(float(g.y_ex.mean()), 3)}
                    for k, g in p.groupby("relb", observed=True)}
    # false negatives: positive bins the rule ranks in its bottom half - what is there
    thr = np.quantile(p.p_rule, 0.5)
    fn = p[(p.y_ex == 1) & (p.p_rule < thr)]
    tp = p[(p.y_ex == 1) & (p.p_rule >= thr)]
    pr["fn_vs_tp"] = {"fn_share_of_pos": float(len(fn) / max((p.y_ex == 1).sum(), 1)),
                      **{c: [round(float(fn[c].median()), 3), round(float(tp[c].median()), 3)] for c in ("last_s", "n_in", "hit_s10", "hit_o10", "vol_s30", "rel", "sig", "edge_s")},
                      "fn_deep_price_share(last_s<0.1 or >0.9)": float(((fn.last_s < 0.1) | (fn.last_s > 0.9)).mean()),
                      "tp_deep_price_share": float(((tp.last_s < 0.1) | (tp.last_s > 0.9)).mean())}
    out["presence"] = pr

    # ---- side
    S = pd.read_parquet(EXC / "price_fills.parquet")
    S = S[S.half == "early"].copy()
    y = S.is_up.to_numpy() == 1
    S["hit"] = S.r8c.to_numpy() == y
    S["dec"] = (S.mid - 0.5).abs() > 0.4
    S["edge"] = np.where(np.isfinite(S.fcl), (S.fcl - S.mid).abs(), np.nan)
    S["rel"] = S.ts - S.st
    S["blk"] = np.where(S.st < 1793448000, "06-12", "18-20:25")
    S["bought_cheap"] = np.where(y, S.mid < 0.5, S.mid > 0.5)
    S["post_up"] = S.fcl > S.mid
    sd = {"n": int(len(S)), "acc": float(S.hit.mean())}
    sd["by_branch"] = {"decided": [float(S.hit[S.dec].mean()), int(S.dec.sum())], "posture": [float(S.hit[~S.dec].mean()), int((~S.dec).sum())]}
    eb = pd.cut(S.edge, [0, 0.02, 0.05, 0.1, 0.2, 1.01])
    sd["posture_by_edge"] = {str(k): [round(float(g.hit.mean()), 3), int(len(g))] for k, g in S[~S.dec].groupby(eb, observed=True)}
    sd["by_rel"] = {str(k): [round(float(g.hit.mean()), 3), int(len(g))] for k, g in S.groupby(pd.cut(S.rel, [-1, 29, 119, 239, 300]), observed=True)}
    sd["by_block"] = {k: [round(float(g.hit.mean()), 3), int(len(g))] for k, g in S.groupby("blk")}
    sd["by_wallet"] = {nm: [round(float(S.hit[S.wallet == nm].mean()), 3), int((S.wallet == nm).sum())] for nm in CLUSTER.values()}
    pf = S.prev_up.to_numpy()
    same_prev = (pf >= 0) & ((pf == 1) == y)
    sd["misses_where_prev_fill_same_side"] = float(np.mean(same_prev[~S.hit.to_numpy()]))
    sd["hits_where_prev_fill_same_side"] = float(np.mean(same_prev[S.hit.to_numpy()]))
    sd["posture_misses_bought_cheap_share"] = float(S.bought_cheap[~S.dec & ~S.hit].mean())
    sd["posture_hits_bought_cheap_share"] = float(S.bought_cheap[~S.dec & S.hit].mean())
    sd["decided_misses"] = {"n": int((S.dec & ~S.hit).sum()), "bought_favourite_share": float((~S.bought_cheap[S.dec & ~S.hit]).mean()) if (S.dec & ~S.hit).any() else None,
                            "median_price": float(S.price[S.dec & ~S.hit].median()) if (S.dec & ~S.hit).any() else None}
    # per-window: fraction of windows where the rule's side is wrong on the majority of fills
    gw = S.groupby("cid").hit.mean()
    sd["windows"] = {"n": int(len(gw)), "majority_wrong": float((gw < 0.5).mean()), "all_right": float((gw == 1).mean())}
    out["side"] = sd

    # ---- price misses (R7 clock in the early half is mostly in-block; block clock reported here)
    S["d_block"] = (S.price - S.pred_block).round(2)
    S["d_match"] = (S.price - S.pred_match).round(2)
    out["price"] = {"block_clock_within_tick": float((S.d_block.abs() <= 0.0105).mean()),
                    "miss_offsets_block": {str(k): int(v) for k, v in S.d_block[S.d_block.abs() > 0.0105].clip(-0.1, 0.1).value_counts().sort_index().items()},
                    "deep_price_fill_share (<0.10 or >0.90)": float(((S.price < 0.1) | (S.price > 0.9)).mean()),
                    "within_tick_deep": float((S.d_block.abs() <= 0.0105)[(S.price < 0.1) | (S.price > 0.9)].mean()),
                    "within_tick_mid": float((S.d_block.abs() <= 0.0105)[(S.price >= 0.1) & (S.price <= 0.9)].mean()),
                    "touch_vs_rule_on_match_clock (18-20:25 only)": {"n": int(S.pred_match.notna().sum()),
                                                                       "rule": float((S.d_match.abs() <= 0.0105)[S.pred_match.notna()].mean()) if S.pred_match.notna().any() else None,
                                                                       "touch": float((np.abs(S.price - S.touch_bid) <= 0.0105)[S.touch_bid.notna()].mean()) if S.touch_bid.notna().any() else None}}
    # ---- outcome: per window, replay vs cluster
    D = pd.read_parquet(EXC / "replay_5m_r8c_full.parquet")
    D = D[D.half == "early"]
    wins = S.groupby("cid").agg(n=("price", "size"), cheap=("bought_cheap", "mean"))
    D = D.join(wins, how="left")
    cw = D[D.index.isin(S.cid.unique())]
    out["outcome"] = {"windows_with_cluster": int(len(cw)), "corr": [float(np.corrcoef(cw.pnl, cw.wal)[0, 1]), float(cw.pnl.corr(cw.wal, method="spearman"))],
                      "sign_agree": float((np.sign(cw.pnl) == np.sign(cw.wal)).mean()),
                      "cluster_win_replay_loss": int(((cw.wal > 0) & (cw.pnl < 0)).sum()), "cluster_loss_replay_win": int(((cw.wal < 0) & (cw.pnl > 0)).sum()),
                      "replay_pnl": round(float(D.pnl.sum()), 1), "replay_usd": round(float(D.usd.sum()), 0), "cluster_pnl": round(float(cw.wal.sum()), 1),
                      "top10_cluster_windows_share_of_cluster_pnl": float(cw.wal.sort_values(ascending=False).head(10).sum() / cw.wal.sum()) if cw.wal.sum() else None,
                      "replay_pnl_in_top10_cluster_windows": round(float(cw.loc[cw.wal.sort_values(ascending=False).head(10).index, "pnl"].sum()), 1)}
    # ---- selection: rule vs activity by print price class
    te = pd.concat([pd.read_parquet(f) for f in sorted(EV.glob("sel_te_*.parquet"))], ignore_index=True)
    te = te[te.start_ts < CUT]
    ms = {nm: lgb.Booster(model_file=str(WS / "code" / f"selection2_{nm}.txt")) for nm in ("all", "activity")}
    te["s_all"] = ms["all"].predict(te[sel2.F_ALL]); te["s_act"] = ms["activity"].predict(te[sel2.F_ACT])
    cls = np.where((te.q < 0.1) | (te.q > 0.9), "deep", "mid")
    out["selection"] = {c: {"rule": sel2.wauc(te.s_all.to_numpy()[cls == c], te.y.to_numpy()[cls == c], te.wt.to_numpy()[cls == c]),
                            "activity": sel2.wauc(te.s_act.to_numpy()[cls == c], te.y.to_numpy()[cls == c], te.wt.to_numpy()[cls == c]),
                            "wallet_prints": int(te.y.to_numpy()[cls == c].sum())} for c in ("deep", "mid")}
    (RES / "exam_r2_diagnosis.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
