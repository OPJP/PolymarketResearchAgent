"""Iteration 2 price rule: predict the limit price q of each cluster maker BUY fill (BTC 5m) from public state
at the fill (clean tape strictly before the fill second, Binance seconds published by ts-2).

Rules compared on VALIDATE (fitted on BUILD where needed):
  P0 last clean print on s - 0.01 (iteration-1 rule on the clean tape)
  P1 floor_0.01(fair_s - m), m fitted on BUILD
  P2 LightGBM regression on [fair_s, last clean print on s, last clean bid-hit on s, last clean ask-lift on s,
     ages, rel, sig, z] -> rounded to 0.01
  P3 (own-state, reported separately) P2 + the cluster's previous fill price on s in this window
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up  # noqa: E402
from panel2 import OUT, WALLETS  # noqa: E402

VAL0 = 1792108800


def fill_table(d, w, sp, fills, ctx, cw):
    tk = pd.read_parquet(OUT / f"taker5m_day_{d}.parquet")
    wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400)]
    clean = tk[~(tk["tx"].isin(ctx) | tk["wallet"].isin(cw))].merge(wd[["cid", "up_token"]], on="cid")
    is_up = clean["asset"].to_numpy() == clean["up_token"].to_numpy()
    buy = clean["side"].astype(str).to_numpy() == "BUY"
    clean["up_px"] = np.where(is_up, clean["price"], 1 - clean["price"])
    clean["hit_up"] = (is_up & ~buy) | (~is_up & buy)
    clean = clean.sort_values(["cid", "ts"], kind="stable")
    f = fills[(fills["day"] == d) & (fills["role"] == "maker")].copy()
    tu = dict(zip(wd["up_token"], wd["cid"]))
    td = dict(zip(wd["down_token"], wd["cid"]))
    f["cid"] = [tu.get(t) or td.get(t) for t in f["token_id"]]
    f["is_up"] = f["token_id"].isin(tu.keys())
    f = f.dropna(subset=["cid"]).merge(wd[["cid", "start_ts", "end_ts"]], on="cid").sort_values(["cid", "ts"]).reset_index(drop=True)
    for c in ("last_s", "lb_s", "la_s", "age_last", "age_lb", "age_la"):
        f[c] = np.nan
    groups = dict(tuple(clean.groupby("cid", sort=False)))
    for cid, idx in f.groupby("cid", sort=False).indices.items():
        g = groups.get(cid)
        if g is None:
            continue
        ts = g["ts"].to_numpy()
        up = g["up_px"].to_numpy()
        hu = g["hit_up"].to_numpy()
        t = f.loc[idx, "ts"].to_numpy()
        s_up = f.loc[idx, "is_up"].to_numpy()
        j = np.searchsorted(ts, t, side="left") - 1
        lu = np.where(j >= 0, up[np.clip(j, 0, None)], np.nan)
        f.loc[idx, "last_s"] = np.where(s_up, lu, 1 - lu)
        f.loc[idx, "age_last"] = np.where(j >= 0, t - ts[np.clip(j, 0, None)], 999)
        # last bid-hit on Up (= Up bid level) and last ask-lift on Up (= Down bid level)
        for nm, m in (("bu", hu), ("bd", ~hu)):
            tt, pp = ts[m], up[m]
            k = np.searchsorted(tt, t, side="left") - 1
            v = np.where(k >= 0, pp[np.clip(k, 0, None)] if len(pp) else np.nan, np.nan)
            a = np.where(k >= 0, t - (tt[np.clip(k, 0, None)] if len(tt) else 0), 999)
            f.loc[idx, nm] = v
            f.loc[idx, "age_" + nm] = a
    f["lb_s"] = np.where(f["is_up"], f["bu"], 1 - f["bd"])  # last hit bid on s
    f["la_s"] = np.where(f["is_up"], f["bd"], 1 - f["bu"])  # last price where s was bought aggressively
    f["age_lb"] = np.where(f["is_up"], f["age_bu"], f["age_bd"])
    f["age_la"] = np.where(f["is_up"], f["age_bd"], f["age_bu"])
    fu, z = fair_up(sp, f["start_ts"].to_numpy(), f["end_ts"].to_numpy(), f["ts"].to_numpy() - 2)
    f["fair_s"] = np.where(f["is_up"], fu, 1 - fu)
    f["z_s"] = np.where(f["is_up"], z, -z)
    f["sig"] = sp.sigma(f["ts"].to_numpy() - 2) * 1e4
    f["rel"] = f["ts"] - f["start_ts"]
    f["side_up"] = f["is_up"].astype(int)
    # own-state: previous cluster fill price on s in this window (strictly earlier second)
    f["prev_own"] = np.nan
    for (cid, su), idx in f.groupby(["cid", "is_up"], sort=False).indices.items():
        g = f.loc[idx].sort_values("ts")
        t = g["ts"].to_numpy()
        pr = g["price"].to_numpy()
        k = np.searchsorted(t, t, side="left") - 1
        f.loc[g.index, "prev_own"] = np.where(k >= 0, pr[np.clip(k, 0, None)], np.nan)
    return f


def main():
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    fills = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
    from panel2 import cluster_trades
    ctx = set(cluster_trades()["tx"])
    cw = set(WALLETS.values())
    days = sorted(int(x.stem.split("_")[-1]) for x in OUT.glob("taker5m_day_*.parquet"))
    f = pd.concat([fill_table(d, w, sp, fills, ctx, cw) for d in days], ignore_index=True)
    f.to_parquet(OUT / "fills_price2.parquet", index=False)
    b, v = f[f["start_ts"] < VAL0], f[f["start_ts"] >= VAL0]
    res = {"n_build": len(b), "n_val": len(v), "grid_0.01_share_val": float((np.abs(v["price"] * 100 - np.round(v["price"] * 100)) < 1e-6).mean())}

    def score(pred, q):
        e = np.abs(np.round(pred, 2) - q)
        return {"exact": float(np.mean(e < 0.0005)), "within_0.01": float(np.mean(e <= 0.0105)), "mae": float(np.mean(np.abs(pred - q)))}

    res["P0_last_clean_minus_0.01"] = score(v["last_s"].fillna(0.5) - 0.01, v["price"])
    res["P4_last_ask_lift_minus_0.01"] = score(v["la_s"].fillna(0.5) - 0.01, v["price"])
    res["P5_last_hit_bid"] = score(v["lb_s"].fillna(0.5), v["price"])
    res["P6_min(last_clean, last_ask_lift) - 0.01"] = score(np.fmin(v["last_s"], v["la_s"]).fillna(0.5) - 0.01, v["price"])
    res["dist_price_minus_la_val"] = {str(k): float(x) for k, x in (np.round(v["price"] - v["la_s"], 2)).value_counts(normalize=True).head(8).items()}
    # same rules on BUILD (choice of the price rule is made on VALIDATE; BUILD shown for stability)
    res["build_P0"] = score(b["last_s"].fillna(0.5) - 0.01, b["price"])
    res["build_P4"] = score(b["la_s"].fillna(0.5) - 0.01, b["price"])
    best = None
    for m in np.arange(0.0, 0.101, 0.005):
        sc = score(np.floor((b["fair_s"] - m) * 100) / 100, b["price"])["within_0.01"]
        best = (sc, m) if best is None or sc > best[0] else best
    res["P1_floor_fair_minus_m"] = {"m_build": float(best[1]), **score(np.floor((v["fair_s"] - best[1]) * 100) / 100, v["price"])}
    feats = ["fair_s", "last_s", "lb_s", "la_s", "age_last", "age_lb", "age_la", "rel", "sig", "z_s", "side_up"]
    prm = dict(objective="l1", learning_rate=0.05, num_leaves=31, min_data_in_leaf=100, max_bin=63, verbose=-1, seed=7, num_threads=2)
    for nm, fs in (("P2_lgbm_public", feats), ("P3_lgbm_plus_own_prev_price", feats + ["prev_own"])):
        m = lgb.train(prm, lgb.Dataset(b[fs], b["price"]), 400)
        res[nm] = score(m.predict(v[fs]), v["price"])
        res[nm]["imp"] = dict(sorted(zip(fs, m.feature_importance("gain").round(0).tolist()), key=lambda x: -x[1])[:6])
        if nm.startswith("P2"):
            m.save_model(str(HERE / "price2_lgbm_public.txt"))
    res["dist_price_minus_last_clean_val"] = {str(k): float(x) for k, x in (np.round(v["price"] - v["last_s"], 2)).value_counts(normalize=True).head(8).items()}
    res["dist_price_minus_lb_val"] = {str(k): float(x) for k, x in (np.round(v["price"] - v["lb_s"], 2)).value_counts(normalize=True).head(8).items()}
    print(json.dumps(res, indent=1, default=str))
    (HERE.parent / "results_iter2_price.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
