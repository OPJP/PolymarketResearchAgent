"""Iteration 7 (catalog X29 = panel-assumptions iter6 P2): is the LARGE size an event-level decision?
Data: the B1 calldata sample of 11 whole development hours (b1_orders_sample.parquet: 13,443 distinct cluster orders with
the SIGNED size and limit, first/last fill block ts, roles), Binance 1-s klines (binance_1s.parquet). Development only.
1. Large = the largest size of the hour's menu (100 on 10-09..13 and 10-19..22, 50 on 10-15, 200 on 10-16; the 10-17/18
   hours run 30/50 at ~50/50 and are reported separately).
2. Co-occurrence: pairs of TAKER-first orders of two different wallets on the same token with first fills within 1 s;
   P(partner large | order large) vs P(partner large | order small), against a permutation null that shuffles the large
   labels within (wallet, hour) (2,000 draws).
3. P(large | point-in-time features) for taker-first orders: |limit - 0.5|, rel, signed and absolute BTC 1-s move over the
   2-4 s before the first fill, wallet; AUC on the VALIDATE hours of a model fit on the BUILD hours (logistic), and the
   AUC of each single feature.
Usage: python size7.py"""
import os, json
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
OUT = _ROOT + "/research/reverse_engineering/btc5m-bot/results/size7.json"


def main():
    b = pd.read_parquet(f"{C}/b1_orders_sample.parquet")
    b["hour"] = (b.first_ts // 3600).astype(int)
    menu = b.groupby("hour")["size"].agg(lambda s: sorted(s.value_counts()[lambda v: v >= 0.02 * len(s)].index))
    b["menu"] = b.hour.map(lambda h: tuple(menu[h]))
    b["large"] = b.apply(lambda r: r["size"] == max(r.menu), axis=1)
    b["even_menu"] = b.hour.map(lambda h: pd.to_datetime(h * 3600, unit="s").strftime("%m-%d") in ("10-17", "10-18"))
    res = {"menus": {pd.to_datetime(h * 3600, unit="s").strftime("%m-%d %H"): [float(x) for x in m] for h, m in menu.items()}}
    res["large_share_by_wallet"] = {w: round(float(g.large.mean()), 4) for w, g in b[~b.even_menu].groupby("wal")}
    tk = b[(b.roles.str.contains("T")) & ~b.even_menu].copy()
    tk = tk.sort_values("first_ts").reset_index(drop=True)
    # 2. co-occurrence across wallets
    pairs = []
    for tok, g in tk.groupby("token"):
        t = g.first_ts.to_numpy(); w = g.wal.to_numpy(); idx = g.index.to_numpy()
        for i in range(len(g)):
            j = i + 1
            while j < len(g) and t[j] - t[i] <= 1:
                if w[j] != w[i]:
                    pairs.append((idx[i], idx[j]))
                j += 1
    P = np.array(pairs)
    L = tk.large.to_numpy()

    def stat(lab):
        a, c = lab[P[:, 0]], lab[P[:, 1]]
        both = (a & c).mean(); exp = a.mean() * c.mean()
        return both / exp if exp > 0 else np.nan

    obs = stat(L)
    rng = np.random.default_rng(7)
    grp = tk.groupby(["wal", "hour"]).indices
    null = []
    for _ in range(2000):
        lab = L.copy()
        for ii in grp.values():
            lab[ii] = rng.permutation(L[ii])
        null.append(stat(lab))
    null = np.array(null)
    a, c = L[P[:, 0]], L[P[:, 1]]
    res["cooccurrence"] = {"pairs": int(len(P)), "both_large_over_independence": round(float(obs), 3),
                           "null_mean": round(float(np.nanmean(null)), 3), "null_p975": round(float(np.nanpercentile(null, 97.5)), 3),
                           "p_one_sided": float((np.sum(null >= obs) + 1) / (len(null) + 1)),
                           "P_partner_large_given_large": round(float(np.r_[c[a], a[c]].mean()), 4),
                           "P_partner_large_given_small": round(float(np.r_[c[~a], a[~c]].mean()), 4)}
    # 3. P(large | PIT features)
    sp = pd.read_parquet(f"{C}/binance_1s.parquet")
    sec = sp.iloc[:, 0].to_numpy(np.int64) if sp.columns[0] != "close" else sp.index.to_numpy(np.int64)
    cl = sp["close"].to_numpy(float) if "close" in sp else sp.iloc[:, 1].to_numpy(float)
    order = np.argsort(sec); sec, cl = sec[order], cl[order]

    def px(t):
        i = np.searchsorted(sec, t, "right") - 1
        return np.where(i >= 0, cl[np.clip(i, 0, len(cl) - 1)], np.nan)

    t = tk.first_ts.to_numpy(np.int64)
    sgn = np.where(tk.is_up, 1.0, -1.0)
    for lo, hi in [(4, 2), (6, 2), (12, 2), (32, 2)]:
        r = (px(t - hi) / px(t - lo) - 1) * 1e4
        tk[f"mv{lo}"] = r * sgn
        tk[f"amv{lo}"] = np.abs(r)
    tk["dist"] = (tk["limit"] - 0.5).abs()
    tk["rel"] = tk.first_ts - tk.start_ts
    tk["isDS"] = (tk.wal == "DS").astype(float); tk["isGF"] = (tk.wal == "GF").astype(float)
    feats = ["dist", "rel", "mv4", "amv4", "mv6", "amv6", "mv12", "amv12", "mv32", "amv32", "isDS", "isGF"]
    tk = tk.dropna(subset=feats)
    single = {}
    for fn in feats:
        try:
            single[fn] = round(float(roc_auc_score(tk.large, tk[fn])), 4)
        except ValueError:
            pass
    res["single_feature_auc_all_hours"] = single
    tr, te = tk[~tk.val], tk[tk.val]
    out = {}
    for nm, fs in [("wallet_only", ["isDS", "isGF"]), ("all", feats), ("no_wallet", feats[:-2])]:
        m = LogisticRegression(max_iter=2000).fit(tr[fs], tr.large)
        p = m.predict_proba(te[fs])[:, 1]
        out[nm] = {"auc_validate": round(float(roc_auc_score(te.large, p)), 4), "n_build": int(len(tr)), "n_val": int(len(te)),
                   "within_wallet_auc": {w: round(float(roc_auc_score(te.large[te.wal == w], p[te.wal.to_numpy() == w])), 4) for w in ["DS", "GF", "XM"] if te.large[te.wal == w].nunique() == 2}}
    res["p_large_model"] = out
    # large share by |move| bin (VALIDATE + BUILD), and by event size
    tk["amv_bin"] = pd.cut(tk.amv4, [-1, 0.05, 0.5, 1, 2, 100])
    res["large_share_by_abs_move_bp"] = {str(k): [round(float(g.large.mean()), 4), int(len(g))] for k, g in tk.groupby("amv_bin", observed=True)}
    tk["dist_bin"] = pd.cut(tk.dist, [-0.01, 0.1, 0.2, 0.3, 0.4, 0.5])
    res["large_share_by_dist"] = {str(k): [round(float(g.large.mean()), 4), int(len(g))] for k, g in tk.groupby("dist_bin", observed=True)}
    json.dump(res, open(OUT, "w"), indent=1)
    print(json.dumps(res, indent=1)[:5000])


if __name__ == "__main__":
    main()
