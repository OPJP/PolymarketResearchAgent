"""Examiner r1: DIAGNOSIS material from the FIRST half of the h1 lot only (10-23, 10-25): where the frozen rule disagrees with the wallets,
by component, market (window), time (hour, Globex session, time in the window) and state. Second half: aggregate metrics only.
Inputs: an/pres_*.npz (+ msb_*.npy), an/side_orders.parquet, an/pnl_windows.parquet, chunk fills. Usage: python an_diag.py OUT_JSON"""
import os, sys, json, glob
ARGS = sys.argv[1:]
ROOT = os.getcwd(); CODE = f"{ROOT}/research/reverse_engineering/btc5m-bot/code"; sys.path.insert(0, CODE)
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from scipy import stats
import dc_exam14

EX = f"{ROOT}/.cache/exam/btc5m-bot"; AN = f"{EX}/an"
CUT = 1793059200
LOT = [(1792713600, 1792800000), (1792886400, 1792972800), (1793059200, 1793145600), (1793232000, 1793318400)]


def auc(y, s):
    return round(float(roc_auc_score(y, s)), 4) if len(y) and 0 < y.sum() < len(y) else None


def main(out_json):
    res = {"scope": "first half = windows starting 10-23 and 10-25 (case detail); second half = aggregates only"}
    # ---------------- presence
    F = sorted(glob.glob(f"{AN}/pres_*.npz")); P = []
    for f in F:
        z = np.load(f, allow_pickle=True); kb = z["kb"]
        m = f.replace("pres_", "msb_").replace(".npz", ".npy")
        d = pd.DataFrame({"t": z["t"][kb], "rel": z["rel"][kb], "y": z["y"][kb], "yT": z["yT"][kb], "yM": z["yM"][kb], "yGF": z["yGF"][kb], "yXM": z["yXM"][kb],
                          "yDS": z["yDS"][kb], "pf": z["pf"], "pp": z["pp"], "own": z["own_MKTX"][kb], "cid": z["cid"][kb], "up": z["is_up"][kb]})
        d["msb"] = np.load(m) if os.path.exists(m) else np.nan
        P.append(d)
    P = pd.concat(P, ignore_index=True)
    P["hour"] = (P.t % 86400) // 3600
    P["globex_open"] = dc_exam14.globex_open_ms(P.t.to_numpy() * 1000)
    H1 = P[P.t < CUT]; H2 = P[P.t >= CUT]
    base = "msb" if np.isfinite(P.msb).all() else "own"
    pr = {"baseline_used": base}
    pr["first_half_by_hour"] = {int(h): {"full": auc(g.y, g.pf), "base": auc(g.y, g[base]), "pos_rate": round(float(g.y.mean()), 4)} for h, g in H1.groupby("hour")}
    pr["first_half_by_globex"] = {("open" if k else "closed"): {"full": auc(g.y, g.pf), "base": auc(g.y, g[base]), "n": int(len(g))} for k, g in H1.groupby("globex_open")}
    H1r = H1.assign(rb=(H1.rel // 60) * 60)
    pr["first_half_by_rel_minute"] = {int(k): {"full": auc(g.y, g.pf), "base": auc(g.y, g[base]), "pos_rate": round(float(g.y.mean()), 4)} for k, g in H1r.groupby("rb")}
    pr["first_half_by_label_type"] = {"taker_fill_cells": {"full": auc(H1.yT, H1.pf), "base": auc(H1.yT, H1[base])}, "maker_fill_cells": {"full": auc(H1.yM, H1.pf), "base": auc(H1.yM, H1[base])},
                                      "maker_only_cells_share_of_positives": round(float(((H1.yM == 1) & (H1.yT == 0)).sum() / max(H1.y.sum(), 1)), 4)}
    fl = H1.pf >= 0.30
    pos = H1[H1.y == 1]
    pr["first_half_missed_positives_at_0.30"] = {"share_missed": round(float((pos.pf < 0.30).mean()), 4),
                                                 "missed_share_maker_only": round(float(((pos.pf < 0.30) & (pos.yM == 1) & (pos.yT == 0)).sum() / max((pos.pf < 0.30).sum(), 1)), 4),
                                                 "recall_taker_cells": round(float((pos[pos.yT == 1].pf >= 0.30).mean()), 4), "recall_maker_only_cells": round(float((pos[(pos.yM == 1) & (pos.yT == 0)].pf >= 0.30).mean()), 4),
                                                 "recall_by_wallet": {w: round(float((pos[pos[f"y{w}"] == 1].pf >= 0.30).mean()), 4) for w in ("GF", "XM", "DS")}}
    # windows with the worst within-window AUC / the largest share of missed positives
    ww = []
    for c, g in H1.groupby("cid"):
        if 0 < g.y.sum() < len(g):
            ww.append((c, int(g.t.min() // 300 * 300), auc(g.y, g.pf), int(g.y.sum())))
    ww = pd.DataFrame(ww, columns=["cid", "start", "auc", "pos"])
    pr["first_half_within_window_auc"] = {"median": round(float(ww.auc.median()), 4), "q10": round(float(ww.auc.quantile(0.1)), 4),
                                          "corr_auc_with_positives": round(float(stats.spearmanr(ww.auc, ww.pos).correlation), 4)}
    pr["first_half_where_score_and_activity_disagree"] = {
        "share_of_positives_with_no_other_print_in_last_2s": None}
    pr["second_half_aggregate"] = {"full": auc(H2.y, H2.pf), "base": auc(H2.y, H2[base]), "by_globex": {("open" if k else "closed"): {"full": auc(g.y, g.pf), "base": auc(g.y, g[base])} for k, g in H2.groupby("globex_open")}}
    res["presence"] = pr
    # ---------------- side
    S = pd.read_parquet(f"{AN}/side_orders.parquet")
    S["ok"] = (S.p > 0.5) == S.up; S["rel"] = S.m / 1000 - S.st; S["hour"] = (S.m // 1000 % 86400) // 3600
    S["globex_open"] = dc_exam14.globex_open_ms(S.m.to_numpy()); S["dist"] = np.abs(S.pU0 - 0.5); S["conf"] = np.abs(S.p - 0.5)
    S["fav"] = np.where(S.up, S.pU0 >= 0.5, S.pU0 < 0.5)
    S1 = S[S.st < CUT]; S2 = S[S.st >= CUT]
    sd = {"first_half_n": int(len(S1)), "first_half_acc": round(float(S1.ok.mean()), 4)}
    sd["by_rel_minute"] = {int(k): [round(float(g.ok.mean()), 4), int(len(g))] for k, g in S1.groupby((S1.rel // 60).clip(0, 4))}
    sd["by_wallet"] = {w: [round(float(g.ok.mean()), 4), int(len(g))] for w, g in S1.groupby("wallet")}
    sd["by_first_leg"] = {("first" if k else "follower"): [round(float(g.ok.mean()), 4), int(len(g))] for k, g in S1.groupby("first")}
    sd["by_globex"] = {("open" if k else "closed"): [round(float(g.ok.mean()), 4), int(len(g))] for k, g in S1.groupby("globex_open")}
    sd["by_hour"] = {int(k): [round(float(g.ok.mean()), 4), int(len(g))] for k, g in S1.groupby("hour")}
    sd["by_price_distance"] = {str(k): [round(float(g.ok.mean()), 4), int(len(g))] for k, g in S1.groupby(pd.cut(S1.dist, [-0.01, 0.1, 0.2, 0.3, 0.4, 0.5]))}
    sd["by_bought_favourite"] = {("favourite" if k else "underdog"): [round(float(g.ok.mean()), 4), int(len(g))] for k, g in S1.groupby("fav")}
    sd["by_model_confidence"] = {str(k): [round(float(g.ok.mean()), 4), int(len(g))] for k, g in S1.groupby(pd.cut(S1.conf, [-0.01, 0.1, 0.2, 0.3, 0.4, 0.5]))}
    q = S1.assign(mv=np.abs(S1.mic250.fillna(0)))
    sd["by_abs_spot_microprice_move_250ms_bp"] = {str(k): [round(float(g.ok.mean()), 4), int(len(g))] for k, g in q.groupby(pd.cut(q.mv, [-0.001, 0.05, 0.2, 0.5, 1.0, 100]))}
    sd["by_order_size_filled"] = {str(k): [round(float(g.ok.mean()), 4), int(len(g))] for k, g in S1.groupby(pd.cut(S1.shares, [0, 10, 29.9, 30.1, 99.9, 1000]))}
    # errors vs own inventory (does the error side follow the short leg?)
    err = S1[~S1.ok]
    sd["errors_share_buying_cluster_short_leg"] = round(float((np.sign(-err.invc) == np.where(err.up, 1, -1)).mean()), 4)
    sd["correct_share_buying_cluster_short_leg"] = round(float((np.sign(-S1[S1.ok].invc) == np.where(S1[S1.ok].up, 1, -1)).mean()), 4)
    sd["second_half_aggregate"] = {"acc": round(float(S2.ok.mean()), 4), "by_wallet": {w: round(float(g.ok.mean()), 4) for w, g in S2.groupby("wallet")}}
    res["side"] = sd
    # ---------------- PnL
    W = pd.read_parquet(f"{AN}/pnl_windows.parquet"); W["hour"] = (W.start_ts % 86400) // 3600
    W1 = W[W.start_ts < CUT]; W2 = W[W.start_ts >= CUT]
    x, y = W1["rule_pnl_a_c1.0"], W1.wallet_pnl
    pn = {"first_half_pearson_spearman": [round(float(x.corr(y)), 4), round(float(x.corr(y, method="spearman")), 4)]}
    pn["sign_agreement"] = round(float((np.sign(x) == np.sign(y)).mean()), 4)
    big = W1[W1.wallet_pnl.abs() >= W1.wallet_pnl.abs().quantile(0.9)]
    pn["top_decile_abs_wallet_pnl_windows"] = {"n": int(len(big)), "sign_agreement": round(float((np.sign(big["rule_pnl_a_c1.0"]) == np.sign(big.wallet_pnl)).mean()), 4),
                                               "share_of_abs_wallet_pnl": round(float(big.wallet_pnl.abs().sum() / W1.wallet_pnl.abs().sum()), 4),
                                               "rule_pnl_mean": round(float(big["rule_pnl_a_c1.0"].mean()), 2), "wallet_pnl_mean": round(float(big.wallet_pnl.mean()), 2)}
    pn["by_hour_pearson"] = {int(h): round(float(g["rule_pnl_a_c1.0"].corr(g.wallet_pnl)), 3) for h, g in W1.groupby("hour") if len(g) > 5}
    pn["per_wallet_first_half"] = {w: [round(float(x.corr(W1[f"pnl_{w}"])), 4), round(float(x.corr(W1[f"pnl_{w}"], method="spearman")), 4)] for w in ("GF", "XM", "DS")}
    pn["cross_wallet_window_pnl_corr_first_half"] = {f"{a}-{b}": round(float(W1[f"pnl_{a}"].corr(W1[f"pnl_{b}"])), 4) for a, b in (("GF", "XM"), ("GF", "DS"), ("XM", "DS"))}
    pn["rule_fills_per_window_first_half"] = round(float(W1["rule_fills_a_c1.0"].mean()), 2)
    pn["second_half_aggregate"] = [round(float(W2["rule_pnl_a_c1.0"].corr(W2.wallet_pnl)), 4), round(float(W2["rule_pnl_a_c1.0"].corr(W2.wallet_pnl, method="spearman")), 4)]
    # wallet's net lean vs outcome, first half (what the rule would have to reproduce)
    FL = []
    for p in sorted(glob.glob(f"{EX}/chunks/*_*/fills.parquet")):
        a = int(os.path.basename(os.path.dirname(p)).split("_")[0])
        if any(x0 <= a < y0 for x0, y0 in LOT[:2]):
            FL.append(pd.read_parquet(p, columns=["cid", "wallet", "is_up", "shares", "usdc", "up_payout", "role"]))
    if FL:
        fl = pd.concat(FL); fl["net"] = np.where(fl.is_up, fl.shares, -fl.shares)
        net = fl.groupby("cid").net.sum(); out = fl.groupby("cid").up_payout.first()
        pn["first_half_wallet_net_sign_matches_outcome"] = round(float((np.sign(net) == np.sign(out - 0.5)).mean()), 4)
        j = W1.set_index("cid").join(net.rename("net"))
        pn["first_half_corr_wallet_pnl_with_net_x_outcome"] = round(float(j.wallet_pnl.corr(j.net * (2 * j.pay_up - 1))), 4)
    res["pnl"] = pn
    json.dump(res, open(out_json, "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:8000])


if __name__ == "__main__":
    main(ARGS[0])
