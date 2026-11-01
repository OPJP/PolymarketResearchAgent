"""VALIDATE metrics (side, price, selection, outcome) from the cached VALIDATE predictions of exp_tape_model_lean."""
import os as _os; _ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))  # repo root
import sys, os, json
sys.path.insert(0, _ROOT + "/research/reverse_engineering/btc5m-bot/code")
import numpy as np, pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot"
CL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
P_THRESH = 0.30
cv = pd.read_parquet(f"{C}/val_pred_tape.parquet")
f = pd.read_parquet(f"{C}/fills.parquet")
win = pd.read_parquet(f"{C}/windows.parquet")
f = f[f.cid.isin(set(cv.cid))]
out = {"windows": int(cv.cid.nunique())}
y = cv.y.to_numpy().astype(bool); flag = cv.p_y.to_numpy() >= P_THRESH
k, n = int(y[flag].sum()), int(flag.sum())
out["presence"] = {"auc_any": round(float(roc_auc_score(cv.y, cv.p_y)), 4), "auc_taker": round(float(roc_auc_score(cv.yT, cv.p_yT)), 4), "auc_maker": round(float(roc_auc_score(cv.yM, cv.p_yM)), 4),
                   "base_rate": round(float(y.mean()), 4), "recall": round(float(flag[y].mean()), 4), "lift": round(float(y[flag].mean() / y.mean()), 3), "flag_share": round(float(flag.mean()), 4),
                   "p_value": float(stats.binomtest(k, n, y.mean(), alternative="greater").pvalue)}
# best threshold diagnostics (recall at lift>=3)
qs = np.quantile(cv.p_y, [0.80, 0.85, 0.90, 0.95])
out["presence"]["recall_lift_by_quantile"] = {f"q{int(q*100)}": {"recall": round(float((cv.p_y >= t)[y].mean()), 3), "lift": round(float(y[cv.p_y >= t].mean() / y.mean()), 2)} for q, t in zip([0.80, 0.85, 0.90, 0.95], qs)}
# side
pv = cv.pivot_table(index=["cid", "rel"], columns="is_up", values=["p_y", "y", "m_last", "flow5", "fv"], aggfunc="first")
one = (pv[("y", True)] + pv[("y", False)]) == 1
sub = pv[one]
tu = sub[("y", True)] == 1
pu = sub[("p_y", True)] >= sub[("p_y", False)]
fav = sub[("m_last", True)] >= 0.5
mom = sub[("flow5", True)] >= 0
b = int(((pu == tu) & (fav != tu)).sum()); c = int(((pu != tu) & (fav == tu)).sum())
out["side"] = {"n_seconds": int(len(sub)), "accuracy": round(float((pu == tu).mean()), 4), "baseline_favourite": round(float((fav == tu).mean()), 4),
               "baseline_tape_flow5": round(float((mom == tu).mean()), 4), "mcnemar_p_vs_favourite": float(stats.binomtest(b, b + c, 0.5, alternative="greater").pvalue) if b + c else None,
               "share_seconds_both_sides": round(float(((pv[("y", True)] + pv[("y", False)]) == 2).sum() / ((pv[("y", True)] + pv[("y", False)]) >= 1).sum()), 4)}
# price within one tick of the last implied ask (<= s-1)
key = cv.set_index(["cid", "is_up", "rel"])[["ask_o", "bid_o"]]
fz = f[(f.rel >= 0) & (f.rel < 300)].join(key, on=["cid", "is_up", "rel"])
out["price"] = {}
for role in ("T", "M"):
    g = fz[fz.role == role]
    d = (g.price - g.ask_o).round(3)
    out["price"][role] = {"n": int(len(g)), "within_1tick_of_last_ask": round(float((np.abs(g.price - g.ask_o) <= 0.0101).mean()), 4),
                          "exact_last_ask": round(float((np.abs(g.price - g.ask_o) <= 0.0001).mean()), 4), "within_1tick_of_last_bid": round(float((np.abs(g.price - g.bid_o) <= 0.0101).mean()), 4),
                          "diff_quantiles": [round(float(x), 3) for x in np.nanquantile(g.price - g.ask_o, [0.1, 0.25, 0.5, 0.75, 0.9])]}
# selection: all in-window taker prints (every trader) scored by the cell score
rows = []
for cid in cv.cid.unique():
    d = pd.read_parquet(f"{C}/tapes/{cid}.parquet")
    if len(d) and "timestamp" in d:
        rows.append(d[["proxyWallet", "outcome", "timestamp", "price"]].assign(cid=cid))
tp = pd.concat(rows).merge(win[["cid", "start_ts"]], on="cid")
tp["rel"] = tp.timestamp - tp.start_ts
tp = tp[(tp.rel >= 0) & (tp.rel < 300)]
tp["is_up"] = tp.outcome == "Up"
tp = tp.join(cv.set_index(["cid", "is_up", "rel"])["p_y"], on=["cid", "is_up", "rel"])
lab = tp.proxyWallet.str.lower().isin(CL).to_numpy()
sc = tp.p_y.to_numpy()
fl = sc >= P_THRESH
k, n = int(lab[fl].sum()), int(fl.sum())
# within-window stratified AUC: rank within window (removes window-level activity effects)
tp["lab"] = lab
aucs = []
for cid, g in tp.groupby("cid"):
    if 0 < g.lab.sum() < len(g):
        aucs.append((roc_auc_score(g.lab, g.p_y), len(g)))
out["selection"] = {"taker_prints": int(len(tp)), "cluster_share": round(float(lab.mean()), 4), "auc_pooled": round(float(roc_auc_score(lab, sc)), 4),
                    "auc_within_window_weighted": round(float(np.average([a for a, _ in aucs], weights=[w for _, w in aucs])), 4),
                    "recall": round(float(fl[lab].mean()), 4), "lift": round(float(lab[fl].mean() / lab.mean()), 3), "p_value": float(stats.binomtest(k, n, lab.mean(), alternative="greater").pvalue)}
# outcome: crude proxy
c2 = cv[(cv.p_y >= P_THRESH) & np.isfinite(cv.ask_o) & (cv.ask_o > 0.05) & (cv.ask_o < 0.95)].merge(win[["cid", "up_payout"]], on="cid")
pay = np.where(c2.is_up, c2.up_payout, 1 - c2.up_payout)
c2["pnl"] = 30 * (pay - c2.ask_o - 0.07 * c2.ask_o * (1 - c2.ask_o)); c2["usd"] = 30 * c2.ask_o
fw = f.assign(pay=np.where(f.is_up, f.up_payout, 1 - f.up_payout))
fw["pnl"] = fw.shares * (fw.pay - fw.price) - fw.fee_usd
both = pd.concat([c2.groupby("cid").pnl.sum().rename("rule"), fw.groupby("cid").pnl.sum().rename("wallet")], axis=1).reindex(cv.cid.unique()).fillna(0)
out["outcome"] = {"per_window_pnl_corr_pearson": round(float(both.rule.corr(both.wallet)), 4), "per_window_pnl_corr_spearman": round(float(both.rule.corr(both.wallet, method="spearman")), 4),
                  "rule_return_crude": round(float(c2.pnl.sum() / c2.usd.sum()), 4), "rule_trades": int(len(c2)),
                  "wallet_return_before_rebates": round(float(fw.pnl.sum() / fw.usdc.sum()), 4), "wallet_return_taker": round(float(fw[fw.role == "T"].pnl.sum() / fw[fw.role == "T"].usdc.sum()), 4),
                  "wallet_return_maker": round(float(fw[fw.role == "M"].pnl.sum() / fw[fw.role == "M"].usdc.sum()), 4)}
json.dump(out, open(f"{R}/results_validate_metrics.json", "w"), indent=1)
print(json.dumps(out, indent=1))
