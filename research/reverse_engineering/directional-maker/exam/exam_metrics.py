"""Examiner: independent holdout metrics from the scored panels (exam_panel.py), the holdout tapes and the cluster's
fills. Own implementations of AUC (rank-based Mann-Whitney), window-cluster bootstrap, side tests, price rule,
per-window PnL and returns.

python exam_metrics.py   -> results/exam_metrics_holdout.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue  # noqa: E402
from exam_panel import CLUSTER, EX, txint  # noqa: E402

RES = HERE.parent / "results"
FWD0 = 1793318400  # as_of
R2, BASE, OWN = "p_all_path_xwin", "p_activity", "p_all_path_xwin+own"


def auc(y, s) -> float:
    y = np.asarray(y).astype(bool)
    s = np.asarray(s, dtype=float)
    ok = np.isfinite(s)
    y, s = y[ok], s[ok]
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = stats.rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def boot_auc(p: pd.DataFrame, cols, n=300, seed=3):
    """Window-cluster bootstrap of AUCs and of their differences."""
    rng = np.random.default_rng(seed)
    cid = pd.factorize(p["cid"])[0]
    nw = cid.max() + 1
    idx_by = pd.Series(np.arange(len(p))).groupby(cid).apply(lambda x: x.to_numpy()).to_list()
    out = {c: [] for c in cols}
    y = p["y"].to_numpy()
    S = {c: p[c].to_numpy() for c in cols}
    for _ in range(n):
        pick = rng.integers(0, nw, nw)
        ii = np.concatenate([idx_by[k] for k in pick])
        for c in cols:
            out[c].append(auc(y[ii], S[c][ii]))
    return {c: np.array(v) for c, v in out.items()}


def main() -> None:
    w = pd.read_parquet(EX / "windows_5m.parquet").sort_values("start_ts").reset_index(drop=True)
    days = sorted(int(f.stem.split("_")[-1]) for f in EX.glob("panel_day_*.parquet"))
    cols = ["cid", "start_ts", "rel", "side_up", "y", "last_s", "fair_s", "won_s", "hit_s10", "hit_o10", R2, BASE, OWN]
    p = pd.concat([pd.read_parquet(EX / f"panel_day_{d}.parquet", columns=cols) for d in days], ignore_index=True)
    w = w[w["cid"].isin(set(p["cid"]))].reset_index(drop=True)
    res = {"days": [str(pd.Timestamp(d, unit="s").date()) for d in days], "windows": int(p["cid"].nunique()), "bins": int(len(p)),
           "pos_rate": float(p["y"].mean())}
    act = p.groupby("cid")["y"].transform("max") > 0
    res["active_window_share"] = float(p.groupby("cid")["y"].max().mean())
    # ---------------- presence
    pr = {"auc_R2": auc(p["y"], p[R2]), "auc_activity_baseline": auc(p["y"], p[BASE]), "auc_R2_with_own_inventory": auc(p["y"], p[OWN]),
          "auc_R2_within_active_windows": auc(p.loc[act, "y"], p.loc[act, R2]),
          "auc_baseline_within_active_windows": auc(p.loc[act, "y"], p.loc[act, BASE])}
    pr["gain_over_baseline"] = pr["auc_R2"] - pr["auc_activity_baseline"]
    orc = np.where(act, p[R2], 0.0)
    pr["auc_R2_with_window_oracle_ceiling"] = auc(p["y"], orc)
    bs = boot_auc(p, [R2, BASE])
    diff = bs[R2] - bs[BASE]
    pr["bootstrap_windows"] = {"n": 300, "R2_ci95": [float(np.quantile(bs[R2], 0.025)), float(np.quantile(bs[R2], 0.975))],
                               "gain_ci95": [float(np.quantile(diff, 0.025)), float(np.quantile(diff, 0.975))],
                               "p_gain_le_0": float((1 + (diff <= 0).sum()) / (len(diff) + 1)),
                               "p_R2_ge_0.85": float((1 + (bs[R2] >= 0.85).sum()) / (len(diff) + 1))}
    dd = p.assign(d=p["start_ts"] // 86400 * 86400)
    pr["daily"] = {str(pd.Timestamp(d, unit="s").date()): {"R2": round(auc(g["y"], g[R2]), 4), "baseline": round(auc(g["y"], g[BASE]), 4),
                                                         "active_share": round(float(g.groupby("cid")["y"].max().mean()), 3)}
                   for d, g in dd.groupby("d")}
    fw = p["start_ts"] >= FWD0
    pr["forward_days"] = {"auc_R2": auc(p.loc[fw, "y"], p.loc[fw, R2]), "auc_activity_baseline": auc(p.loc[fw, "y"], p.loc[fw, BASE]),
                          "bins": int(fw.sum())} if fw.any() else None
    res["presence"] = pr
    # ---------------- side (bins with a fill on exactly one side)
    key = ["cid", "rel"]
    up = p[p["side_up"] == 1].set_index(key)
    dn = p[p["side_up"] == 0].set_index(key).reindex(up.index)
    lab = up["y"].astype(int) - dn["y"].astype(int)
    one = lab != 0
    U, D = up[one], dn[one]
    true_up = (lab[one] > 0).to_numpy()
    cand = {
        "R2_higher_p": (U[R2] > D[R2]).to_numpy(),
        "mkt_favourite_last_print": (U["last_s"].fillna(0.5) > 0.5).to_numpy(),
        "mkt_underdog_last_print": (U["last_s"].fillna(0.5) < 0.5).to_numpy(),
        "mkt_more_bid_hits_10s": np.where(U["hit_s10"] == D["hit_s10"], U["last_s"].fillna(0.5) > 0.5, U["hit_s10"] > D["hit_s10"]),
        "mkt_activity_model_higher_p": (U[BASE] > D[BASE]).to_numpy(),
        "ref_binance_favourite": (U["fair_s"] > 0.5).to_numpy(),
        "ref_binance_underdog": (U["fair_s"] < 0.5).to_numpy(),
    }
    acc = {k: float(np.mean(v == true_up)) for k, v in cand.items()}
    mkt = {k: v for k, v in acc.items() if k.startswith("mkt_")}
    best = max(mkt, key=mkt.get)
    a, b = cand["R2_higher_p"] == true_up, cand[best] == true_up
    n10, n01 = int((a & ~b).sum()), int((~a & b).sum())
    side = {"n_one_sided_bins": int(one.sum()), "accuracy": acc, "best_market_only": best,
            "mcnemar_vs_best": {"R2_right_base_wrong": n10, "R2_wrong_base_right": n01,
                                "p_one_sided": float(stats.binomtest(n10, n10 + n01, 0.5, alternative="greater").pvalue) if n10 + n01 else float("nan")},
            "p_acc_ge_0.80": float(stats.binomtest(int(a.sum()), len(a), 0.80, alternative="greater").pvalue)}
    rel = U.reset_index()["rel"].to_numpy()
    side["by_time"] = {f"{lo}-{hi}s": float(np.mean(a[(rel >= lo) & (rel < hi)])) for lo, hi in ((0, 30), (30, 120), (120, 300))}
    conf = np.abs(U[R2].to_numpy() - D[R2].to_numpy())
    qq = np.quantile(conf, 0.75)
    side["top25pct_confidence_acc"] = float(np.mean(a[conf >= qq]))
    res["side"] = side
    # ---------------- fills, price rule, PnL
    f = pd.read_parquet(EX / "fills_holdout.parquet")
    f = f[f["cid"].isin(set(w["cid"]))]
    tok_up = dict(zip(w["up_token"], w["cid"]))
    tok_dn = dict(zip(w["down_token"], w["cid"]))
    pay = dict(zip(w["cid"], w["up_payout"]))
    f["wcid"] = [tok_up.get(t, tok_dn.get(t)) for t in f["token_id"]]
    f["is_up"] = f["token_id"].isin(set(w["up_token"]))
    f["payout"] = [pay[c] if u else 1 - pay[c] for c, u in zip(f["wcid"], f["is_up"])]
    f["pnl"] = (f["payout"] - f["price"]) * f["shares"]
    f["usd"] = f["price"] * f["shares"]
    mk = f[f["role"] == "maker"]
    # price rule: last clean taker print on s strictly before the fill second - 0.01
    ctx = set(txint(pd.Series(pd.concat([pd.read_parquet(EX / f"activity_{n}.parquet", columns=["transactionHash"]) for n in CLUSTER.values()])["transactionHash"])))
    pe = {"n": 0, "exact": 0, "within_1tick": 0, "base_last_print_within_1tick": 0, "base_last_minus_2c_within_1tick": 0}
    for d in days:
        tk = pd.read_parquet(EX / f"taker5m_day_{d}.parquet", columns=["cid", "ts", "asset", "price", "wallet", "tx"])
        tk["tx"] = txint(tk["tx"])
        tk = tk[~tk["tx"].isin(ctx) & ~tk["wallet"].isin(set(CLUSTER))]
        wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400)]
        tk = tk.merge(wd[["cid", "up_token"]], on="cid")
        tk["up_px"] = np.where(tk["asset"].astype(str) == tk["up_token"].astype(str), tk["price"], 1 - tk["price"])
        tk = tk.sort_values(["cid", "ts"], kind="stable")  # stable: keeps the tape's within-second order
        by = {c: (g["ts"].to_numpy(), g["up_px"].to_numpy()) for c, g in tk.groupby("cid", sort=False)}
        m = mk[mk["wcid"].isin(set(wd["cid"]))]
        for r in m.itertuples(index=False):
            if r.wcid not in by:
                continue
            ts_, px_ = by[r.wcid]
            i = np.searchsorted(ts_, r.ts, side="left") - 1
            if i < 0:
                continue
            ls = px_[i] if r.is_up else 1 - px_[i]
            pe["n"] += 1
            pe["exact"] += int(abs(round(ls - 0.01, 2) - r.price) < 0.0005)
            pe["within_1tick"] += int(abs(round(ls - 0.01, 2) - r.price) <= 0.0105)
            pe["base_last_print_within_1tick"] += int(abs(round(ls, 2) - r.price) <= 0.0105)
            pe["base_last_minus_2c_within_1tick"] += int(abs(round(ls - 0.02, 2) - r.price) <= 0.0105)
        del tk, by
    for k in list(pe):
        if k != "n":
            pe[k] = pe[k] / pe["n"] if pe["n"] else float("nan")
    res["price"] = pe
    # wallet's own BTC 5m return on the holdout windows
    per_w_wallet = mk.groupby("wcid")["pnl"].sum().reindex(w["cid"], fill_value=0.0)
    tw = hac_t_test(per_w_wallet.to_numpy())
    res["wallet"] = {"maker_fills": int(len(mk)), "taker_fills": int((f["role"] == "taker").sum()), "maker_usd": float(mk["usd"].sum()),
                     "maker_pnl": float(mk["pnl"].sum()), "maker_return": float(mk["pnl"].sum() / mk["usd"].sum()),
                     "all_buys_return": float(f["pnl"].sum() / f["usd"].sum()), "all_buys_pnl": float(f["pnl"].sum()),
                     "maker_fill_win_rate": float((mk["pnl"] > 0).mean()), "maker_avg_price": float(mk["usd"].sum() / mk["shares"].sum()),
                     "per_window_t": tw.statistic, "per_window_p_one_sided": tw.p_value,
                     "per_window_bootstrap_p": stationary_bootstrap_pvalue(per_w_wallet.to_numpy(), n_boot=5000).p_value,
                     "active_windows": int(mk["wcid"].nunique()),
                     "daily": {str(pd.Timestamp(d, unit="s").date()): {"pnl": round(float(g["pnl"].sum()), 1), "usd": round(float(g["usd"].sum()), 1),
                                                                     "ret": round(float(g["pnl"].sum() / g["usd"].sum()), 4) if g["usd"].sum() else None,
                                                                     "fills": int(len(g))}
                               for d, g in mk.assign(d=mk["ts"] // 86400 * 86400).groupby("d")}}
    fwm = mk[mk["ts"] >= FWD0]
    res["wallet"]["forward_days"] = {"maker_pnl": float(fwm["pnl"].sum()), "maker_usd": float(fwm["usd"].sum()),
                                     "maker_return": float(fwm["pnl"].sum() / fwm["usd"].sum()) if len(fwm) else None, "fills": int(len(fwm))}
    # per-window PnL correlation: (a) the rule's expected PnL (final_rule's definition) on windows the wallet traded,
    # (b) the strict-fill backtest (primary config) on all windows
    q = p.dropna(subset=["won_s"]).copy()
    q["rule_pnl"] = q[R2] * (q["won_s"] - (q["last_s"].fillna(0.5) - 0.01).round(2))
    rp = q.groupby("cid")["rule_pnl"].sum()
    wal = mk.groupby("wcid")["pnl"].sum()
    j = pd.concat([wal.rename("wallet"), rp.rename("rule")], axis=1).dropna()
    corr = {"expected_rule_pnl_vs_wallet_on_wallet_windows": {"n": int(len(j)), "pearson": float(j.corr().iloc[0, 1]),
                                                              "spearman": float(j.corr(method="spearman").iloc[0, 1])}}
    bt = EX / "bt_fills_holdout.parquet"
    if bt.exists():
        b = pd.read_parquet(bt)
        bw = b.groupby("cid")["pnl"].sum().reindex(w["cid"], fill_value=0.0)
        jj = pd.concat([per_w_wallet.rename("wallet"), bw.rename("rule")], axis=1)
        corr["strict_backtest_vs_wallet_all_windows"] = {"n": int(len(jj)), "pearson": float(jj.corr().iloc[0, 1]),
                                                         "spearman": float(jj.corr(method="spearman").iloc[0, 1])}
        jw = jj[jj.index.isin(set(wal.index))]
        corr["strict_backtest_vs_wallet_on_wallet_windows"] = {"n": int(len(jw)), "pearson": float(jw.corr().iloc[0, 1]),
                                                               "spearman": float(jw.corr(method="spearman").iloc[0, 1])}
    res["pnl_correlation"] = corr
    res["fee_rate_values"] = {str(k): int(v) for k, v in w["fee_rate"].value_counts().items()}
    (RES / "exam_metrics_holdout.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
