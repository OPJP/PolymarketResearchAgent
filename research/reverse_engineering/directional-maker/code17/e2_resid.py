"""iteration 17, E2 + E7 (pre-registered in NOTES.md 10:52 UTC 11-01).
T1 presence out of fold on BUILD 10-09..22 (panel2_day; GroupKFold(5) over 2-h blocks; rule = all_path_xwin + clock,
   baseline = activity); miss shape (FN below the OOF 85th percentile, FP above the 99th).
T2 side residual on BUILD fills, one decision per (tx, token): BTC 5m R8 public side (fills_price2), non-BTC rule_ok
   (it15_nb_side); miss shape.
T3 residual_clustering on misses vs hits (period 900 / 3600; cross-asset).
    python e2_resid.py [presence|side|all]"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from train2 import SETS, PARAMS, ROUNDS  # noqa: E402
import indicators as ind  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
B0, B1 = 1791504000, 1792713600  # BUILD 10-09 .. 10-23 (exclusive)
OUT = {}


def clock(p):
    t = pd.to_datetime(p["start_ts"], unit="s")
    p["hour_utc"] = (t.dt.hour + t.dt.minute / 60).astype(np.float32).to_numpy()
    p["dow"] = t.dt.day_of_week.astype(np.int8).to_numpy()
    p["us_session"] = ((p["dow"] < 5) & (p["hour_utc"] >= 12) & (p["hour_utc"] < 21)).astype(np.int8)
    return p


def shape(df, flag, keys):
    res = {}
    for k in keys:
        g = df.groupby(k, observed=True)[flag].agg(["mean", "size"])
        res[k] = {str(i): [round(float(r["mean"]), 4), int(r["size"])] for i, r in g.iterrows()}
    return res


def presence():
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold
    rule = SETS["all_path_xwin"] + ["hour_utc", "dow", "us_session"]
    act = SETS["activity"]
    cols = sorted(set(rule + act + ["cid", "start_ts", "y"]) - {"hour_utc", "dow", "us_session"})
    fr = []
    for f in sorted(C.glob("panel2_day_*.parquet")):
        d = int(f.stem.split("_")[-1])
        if B0 <= d < B1:
            fr.append(pd.read_parquet(f, columns=cols))
    p = clock(pd.concat(fr, ignore_index=True))
    p = p[(p.start_ts >= B0) & (p.start_ts + 300 <= B1)].reset_index(drop=True)
    for c in set(rule + act):
        if p[c].dtype == np.float64:
            p[c] = p[c].astype(np.float32)
    grp = (p.start_ts // 7200).to_numpy()
    y = p.y.to_numpy().astype(int)
    oof = {}
    for nm, fs in (("rule", rule), ("activity", act)):
        s = np.zeros(len(p))
        for tr, te in GroupKFold(5).split(p, y, grp):
            m = lgb.train(PARAMS, lgb.Dataset(p.iloc[tr][fs], y[tr]), ROUNDS)
            s[te] = m.predict(p.iloc[te][fs])
        oof[nm] = s
        OUT[f"presence_oof_auc_{nm}"] = round(float(roc_auc_score(y, s)), 4)
        print(nm, OUT[f"presence_oof_auc_{nm}"], flush=True)
    s = oof["rule"]
    p["score"] = s
    p["score_act"] = oof["activity"]
    q85, q99 = np.quantile(s, 0.85), np.quantile(s, 0.99)
    p["fn"] = ((y == 1) & (s < q85)).astype(float)
    p["fp"] = ((y == 0) & (s >= q99)).astype(float)
    pos = p[p.y == 1].copy()
    pos["rel_b"] = (pos.rel // 60 * 60).astype(int)
    pos["edge_b"] = pd.cut(pos.edge_s.abs(), [-1, 0.05, 0.1, 0.2, 0.4, 2]).astype(str)
    pos["sig_t"] = pd.qcut(pos.sig.rank(method="first"), 3, labels=["lo", "mid", "hi"]).astype(str)
    pos["hour"] = pos.hour_utc.astype(int)
    pos["side"] = np.where(pos.side_up == 1, "up", "down")
    OUT["presence_n_cells"] = int(len(p))
    OUT["presence_n_pos"] = int(len(pos))
    OUT["presence_unexplained_share_fn"] = round(float(pos.fn.mean()), 4)
    OUT["presence_fn_shape"] = shape(pos, "fn", ["hour", "dow", "us_session", "rel_b", "edge_b", "sig_t", "side"])
    # does the miss rate depend on activity the rule already sees? (FN among cells the activity model ranks high)
    pos["act_hi"] = (pos.score_act >= np.quantile(oof["activity"], 0.85)).astype(int)
    OUT["presence_fn_by_activity_top15"] = shape(pos, "fn", ["act_hi"])
    neg = p[p.y == 0]
    OUT["presence_fp_share_of_top1pct"] = round(float(1 - p[p.score >= q99].y.mean()), 4)
    # FN times: first cluster fill second in the bin (cluster_btc5m_fills, maker BUY)
    cf = pd.read_parquet(C / "cluster_btc5m_fills.parquet", columns=["ts", "cid", "token_id", "side", "role", "tx"])
    cf = cf[(cf.role == "maker") & (cf.side == "BUY") & (cf.ts >= B0) & (cf.ts < B1)]
    w = pd.read_parquet(C / "windows_5m.parquet", columns=["cid", "start_ts", "up_token"])
    cf = cf.merge(w, on="cid", how="inner")
    cf["side_up"] = (cf.token_id.astype(str) == cf.up_token.astype(str)).astype(int)
    cf["rel"] = ((cf.ts - cf.start_ts) // 10 * 10).astype(int)
    first = cf.groupby(["cid", "side_up", "rel"]).ts.min().rename("t_fill").reset_index()
    pos = pos.merge(first, on=["cid", "side_up", "rel"], how="left")
    OUT["presence_pos_with_fill_time"] = int(pos.t_fill.notna().sum())
    pos[["cid", "start_ts", "rel", "side_up", "score", "score_act", "fn", "t_fill", "hour_utc", "edge_s"]].to_parquet(
        C / "it17_presence_oof_pos.parquet")
    del p, neg
    return pos


def side():
    f = pd.read_parquet(C / "fills_price2.parquet", columns=["wallet", "tx", "token_id", "ts", "price", "cid", "is_up",
                                                             "start_ts", "fair_s", "bu", "bd", "last_s", "rel"])
    f = f[(f.ts >= B0) & (f.ts < B1)].copy()
    lu = np.where(f.is_up, f.last_s, 1 - f.last_s)
    mid_up = np.where(np.isfinite(f.bu) & np.isfinite(f.bd), (f.bu + f.bd) / 2, lu)
    mid_s = np.where(f.is_up, mid_up, 1 - mid_up)
    decided = np.abs(mid_up - 0.5) > 0.4
    ok = np.where(decided, mid_s < 0.5, f.fair_s > mid_s)
    good = np.isfinite(mid_up) & np.isfinite(f.fair_s)
    f["ok"] = np.where(good, ok.astype(float), np.nan)
    f["band"] = np.abs(f.fair_s - mid_s)
    f["fam"] = "btc-5m"
    f["coin"] = "btc"
    f["sec_in"] = f.ts - f.start_ts
    f["L"] = 300
    b = f[["wallet", "tx", "token_id", "ts", "price", "cid", "ok", "band", "fam", "coin", "sec_in", "L"]]
    nb = pd.read_parquet(C / "it15_nb_side.parquet", columns=["timestamp", "conditionId", "asset", "price", "transactionHash",
                                                             "wallet", "fam", "coin", "L", "fold", "btc_core", "sec_in",
                                                             "phase", "rule_ok", "cheap_ok", "mktfav_ok"])
    nb = nb[(~nb.btc_core) & (nb.timestamp >= B0) & (nb.timestamp < B1) & nb.rule_ok.notna()].copy()
    OUT["nb_rule_ok_by_phase"] = {str(k): [round(float(v.rule_ok.mean()), 3), int(len(v))] for k, v in nb.groupby("phase")}
    nb = nb.rename(columns={"timestamp": "ts", "conditionId": "cid", "asset": "token_id", "transactionHash": "tx",
                            "rule_ok": "ok"})
    nb["band"] = np.nan
    a = pd.concat([b, nb[["wallet", "tx", "token_id", "ts", "price", "cid", "ok", "band", "fam", "coin", "sec_in", "L"]]],
                  ignore_index=True)
    a = a[a.ok.notna() & (a.price > 0.03) & (a.price < 0.97)]
    # one decision per (tx, token) across the three accounts
    dd = a.sort_values("ts").groupby(["tx", "token_id"], as_index=False).agg(
        ts=("ts", "min"), cid=("cid", "first"), ok=("ok", "mean"), band=("band", "first"), fam=("fam", "first"),
        coin=("coin", "first"), sec_in=("sec_in", "first"), L=("L", "first"), price=("price", "first"),
        n_acc=("wallet", "nunique"))
    dd["miss"] = (dd.ok < 0.5).astype(float)
    dd["hour"] = ((dd.ts % 86400) // 3600).astype(int)
    dd["dow"] = pd.to_datetime(dd.ts, unit="s").dt.day_of_week
    dd["tin"] = pd.cut(dd.sec_in / dd.L, [-0.01, 0.1, 0.33, 0.67, 0.9, 1.01]).astype(str)
    dd["band_b"] = pd.cut(dd.band, [-1, 0.05, 0.1, 0.2, 2]).astype(str)
    OUT["side_n_decisions"] = int(len(dd))
    OUT["side_miss_share"] = round(float(dd.miss.mean()), 4)
    OUT["side_shape"] = shape(dd, "miss", ["fam", "hour", "dow", "tin", "band_b", "n_acc"])
    dd.to_parquet(C / "it17_side_decisions.parquet")
    return dd


def e7(dd):
    res = {}
    sets = {
        "a_5m15m_p900": (dd.L.isin([300, 900]), 900),
        "b_with_1h_p3600": (dd.L.isin([300, 900, 3600]), 3600),
    }
    for nm, (m, per) in sets.items():
        for lab, sel in (("miss", dd.miss == 1), ("hit", dd.miss == 0)):
            x = dd[m & sel]
            if len(x) < 50:
                continue
            r = ind.residual_clustering(x.ts.to_numpy(float), x.cid.astype(str).to_numpy(), delta_s=2.0, n_null=1000,
                                        period_s=per, top=10)
            res[f"{nm}_{lab}"] = {k: r[k] for k in ("near_pairs", "band_pairs", "expected_near", "ratio", "p", "n",
                                                    "n_markets", "null")}
            res[f"{nm}_{lab}"]["top_clusters"] = r["top_clusters"][:5]
            print(nm, lab, round(r["ratio"], 3), r["p"], r["n"], flush=True)
    # cross-asset only: BTC vs non-BTC as two 'markets' (pairs within an asset class are removed by construction)
    m = dd.L.isin([300, 900])
    for lab, sel in (("miss", dd.miss == 1), ("hit", dd.miss == 0)):
        x = dd[m & sel]
        mk = np.where(x.coin == "btc", "btc", "alt")
        r = ind.residual_clustering(x.ts.to_numpy(float), mk, delta_s=2.0, n_null=1000, period_s=900, top=10)
        res[f"c_btc_vs_alt_p900_{lab}"] = {k: r[k] for k in ("near_pairs", "band_pairs", "expected_near", "ratio", "p",
                                                             "n", "n_markets", "null")}
        res[f"c_btc_vs_alt_p900_{lab}"]["top_clusters"] = r["top_clusters"][:5]
        print("btc_vs_alt", lab, round(r["ratio"], 3), r["p"], r["n"], flush=True)
    return res


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("side", "all"):
        dd = side()
        print(json.dumps({k: OUT[k] for k in ("side_n_decisions", "side_miss_share", "nb_rule_ok_by_phase")}), flush=True)
        OUT["e7"] = e7(dd)
    if what in ("presence", "all"):
        presence()
    (HERE.parent / "results" / f"iter17_e2_{what}.json").write_text(json.dumps(OUT, indent=1, default=str))
    print("done")
