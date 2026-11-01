"""Examiner: truncation / corruption test of the frozen rule's decision features.

For a fixed sample of holdout windows (seeded), for every 10-s bin t of each sampled window, the panel row is
rebuilt (features2.build_panel, the rule's code) from inputs (1) truncated at t (taker prints with ts >= t and Binance
seconds >= t deleted, cluster fills with ts >= t deleted) and (2) corrupted after t (prices, sizes, sides and wallets of
every print at/after t randomised, Binance seconds >= t replaced by a random walk, fake cluster fills added after t).
The rule's features (R2 and the activity baseline) and the three models' predictions must be identical to the full-data
run. The price rule (last clean print strictly before the fill second) is checked the same way. A selection check
rebuilds sampled prints' selection features (sel2.day_prints, the rule's code) from data truncated at the print.

python exam_trunc.py N_WINDOWS SEED
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CODE = HERE.parent / "code"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CODE))
from features2 import Spot, build_panel, clean_tape  # noqa: E402
from train2 import SETS  # noqa: E402
import sel2  # noqa: E402
from exam_panel import CLUSTER, EX, MODELS, cluster_trades, load_tape  # noqa: E402

FEATS = sorted(set(SETS["all_path_xwin"]) | set(SETS["activity"]) | set(SETS["all_path_xwin+own"]))


def same(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return (a == b) | (np.isnan(a) & np.isnan(b))


def main(n_win: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    w = pd.read_parquet(EX / "windows_5m.parquet").sort_values("start_ts").reset_index(drop=True)
    days = sorted(int(f.stem.split("_")[-1]) for f in EX.glob("taker5m_day_*.parquet"))
    spd = pd.read_parquet(EX / "spot_btc_1s.parquet")
    sec_all, px_all = spd["sec"].to_numpy(), spd["px"].to_numpy()
    ct = cluster_trades(int(w["end_ts"].max()))
    ctx, cw = set(ct["tx"]), set(CLUSTER)
    models = {nm: lgb.Booster(model_file=str(CODE / f"presence2_{nm}.txt")) for nm in MODELS}
    res = {"n_windows": 0, "rows": 0, "trunc_feature_mismatch": 0, "corrupt_feature_mismatch": 0, "trunc_pred_mismatch": 0,
           "corrupt_pred_mismatch": 0, "control_t_minus_1_feature_mismatch": 0, "control_t_minus_1_pred_mismatch": 0,
           "mismatch_features": {}, "price_checked": 0, "price_mismatch": 0}
    sel_checked, sel_mismatch, sel_bad = 0, 0, {}
    for d in days:
        wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400)].reset_index(drop=True)
        tk = load_tape(d)
        toks = set(wd["up_token"]) | set(wd["down_token"])
        b = ct[(ct["side"] == "BUY") & ct["token_id"].isin(toks)].copy()
        own = tk[tk["wallet"].isin(cw)]
        tp = set(zip(own["tx"], own["wallet"]))
        b["role"] = ["taker" if (x, y) in tp else "maker" for x, y in zip(b["tx"], b["wallet"])]
        mk = b[b["role"] == "maker"]
        clean = clean_tape(tk, ctx, cw)
        pick = rng.choice(np.arange(1, len(wd)), size=max(1, n_win // len(days)), replace=False)
        for i in pick:
            pair = wd.iloc[[i - 1, i]].reset_index(drop=True)
            cid, s0 = pair.loc[1, "cid"], int(pair.loc[1, "start_ts"])
            cl = clean[clean["cid"].isin(set(pair["cid"]))]
            ok = (sec_all >= s0 - 7200) & (sec_all < s0 + 400)
            sec, px = sec_all[ok], px_all[ok]
            full = build_panel(pair, Spot(sec, px), cl, mk)
            full = full[full["cid"] == cid].reset_index(drop=True)
            for nm in MODELS:
                full["p_" + nm] = models[nm].predict(full[SETS[nm]])
            res["n_windows"] += 1
            for rel in range(0, 300, 10):
                t = s0 + rel
                # (1) truncated at t
                ks = sec < t
                tr = build_panel(pair, Spot(sec[ks], px[ks]), cl[cl["ts"] < t], mk[mk["ts"] < t])
                # (2) corrupted after t
                cc = cl.copy()
                aft = cc["ts"].to_numpy() >= t
                na = int(aft.sum())
                if na:
                    cc.loc[aft, "price"] = rng.integers(1, 100, na).astype(np.float32) / 100
                    cc.loc[aft, "size"] = rng.integers(1, 2000, na).astype(np.float32)
                    cc["side"] = cc["side"].astype(str)
                    cc.loc[aft, "side"] = np.where(rng.random(na) < 0.5, "BUY", "SELL")
                    cc.loc[aft, "asset"] = np.where(rng.random(na) < 0.5, pair.loc[1, "up_token"], pair.loc[1, "down_token"])
                    cc.loc[aft, "ts"] = np.sort(rng.integers(t, s0 + 300, na))
                    cc["wallet"] = cc["wallet"].astype(str)
                    cc.loc[aft, "wallet"] = [f"0xfake{k}" for k in rng.integers(0, 50, na)]
                pxc = px.copy()
                pa = sec >= t
                pxc[pa] = px[~pa][-1] * np.exp(np.cumsum(rng.normal(0, 0.002, int(pa.sum()))))
                fake = pd.DataFrame({"token_id": [pair.loc[1, "up_token"], pair.loc[1, "down_token"]] * 5,
                                     "ts": rng.integers(t, s0 + 300, 10), "shares": 500.0})
                mkc = pd.concat([mk[mk["ts"] < t], fake], ignore_index=True)
                co = build_panel(pair, Spot(sec, pxc), cc, mkc)
                # positive control: truncating one second too early (t - 1) must change features
                kc = sec < t - 1
                ctl = build_panel(pair, Spot(sec[kc], px[kc]), cl[cl["ts"] < t - 1], mk[mk["ts"] < t - 1])
                for nm_, df in (("trunc", tr), ("corrupt", co), ("control_t_minus_1", ctl)):
                    df = df[(df["cid"] == cid) & (df["rel"] == rel)].reset_index(drop=True)
                    ref = full[full["rel"] == rel].reset_index(drop=True)
                    bad = [f for f in FEATS if not same(ref[f], df[f]).all()]
                    if bad:
                        res[f"{nm_}_feature_mismatch"] += 1
                        for f in (bad if nm_ != "control_t_minus_1" else []):
                            res["mismatch_features"][f] = res["mismatch_features"].get(f, 0) + 1
                    for nm in MODELS:
                        pr = models[nm].predict(df[SETS[nm]])
                        if not np.allclose(pr, ref["p_" + nm].to_numpy(), rtol=0, atol=1e-12):
                            res[f"{nm_}_pred_mismatch"] += 1
                            break
                res["rows"] += 2
            # price rule: last clean print strictly before the fill second, from data truncated at the fill second
            mf = mk[mk["token_id"].isin({pair.loc[1, "up_token"], pair.loc[1, "down_token"]})]
            c1 = cl[cl["cid"] == cid].sort_values("ts", kind="stable")
            for r in mf.itertuples(index=False):
                def last(c):
                    c = c[c["ts"] < r.ts]
                    if not len(c):
                        return np.nan
                    up = c["price"].iloc[-1] if c["asset"].iloc[-1] == pair.loc[1, "up_token"] else 1 - c["price"].iloc[-1]
                    return up if r.token_id == pair.loc[1, "up_token"] else 1 - up
                a1 = last(c1)
                a2 = last(c1[c1["ts"] <= r.ts])
                res["price_checked"] += 1
                res["price_mismatch"] += int(not same([a1], [a2])[0])
        # selection features of sampled prints: full day vs data truncated at the print (all negatives kept)
        mk_tx = set(mk["tx"])
        for i in pick[:3]:
            cid = wd.loc[i, "cid"]
            s0 = int(wd.loc[i, "start_ts"])
            tkw = tk[tk["cid"] == cid]
            pan = build_panel(wd.iloc[[i - 1, i]].reset_index(drop=True), Spot(sec_all, px_all), clean[clean["cid"].isin(set(wd["cid"].iloc[[i - 1, i]]))], mk)
            ref, _, _ = sel2.day_prints(d, wd, Spot(sec_all, px_all), mk_tx, cw, 1.0, np.random.default_rng(0), tk=tkw, pan=pan)
            ref = ref.sort_values(["ts"], kind="stable").reset_index(drop=True)
            idx = rng.choice(len(ref), size=min(15, len(ref)), replace=False)
            for j in idx:
                T = int(ref.loc[j, "ts"])
                ks = sec_all < T - 2
                tt = tkw[tkw["ts"] <= T]
                got, _, _ = sel2.day_prints(d, wd, Spot(sec_all[ks], px_all[ks]), mk_tx, cw, 1.0, np.random.default_rng(0), tk=tt, pan=pan)
                got = got.sort_values(["ts"], kind="stable").reset_index(drop=True)
                # same print = same position among the rows at that second (stable order)
                rr = ref[ref["ts"] == T].reset_index(drop=True)
                gg = got[got["ts"] == T].reset_index(drop=True)
                k = int((ref.index[ref["ts"] == T] <= j).sum()) - 1
                sel_checked += 1
                bad = [f for f in sel2.PRINTF if not same(rr.loc[[k], f], gg.loc[[k], f]).all()]
                if bad:
                    sel_mismatch += 1
                    for f in bad:
                        sel_bad[f] = sel_bad.get(f, 0) + 1
        print("day", d, json.dumps({k: v for k, v in res.items() if k != "mismatch_features"}), "sel", sel_checked, sel_mismatch, flush=True)
        del tk, clean
    res["selection_prints_checked"], res["selection_feature_mismatch"], res["selection_mismatch_features"] = sel_checked, sel_mismatch, sel_bad
    print(json.dumps(res, indent=1))
    (HERE.parent / "results" / "exam_truncation.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
