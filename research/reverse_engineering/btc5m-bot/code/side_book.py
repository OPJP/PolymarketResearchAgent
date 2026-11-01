"""Iteration 5: Bybit BTCUSDT perpetual ORDER-BOOK features (public orderbook.200 archive, 100-ms buckets from bybit_ob.py) in the
side model. Features are point-in-time at the horizon X = (s-1)*1000 ms (buckets with id < (s-1)*10): touch imbalance, top-5
depth imbalance, their 1-s means and 1-s changes, microprice deviation, mid moves over 1 s / 3 s and the [s-3, s-2) segment, spread.
Side model = iteration-4 frozen side features (train5.SIDE + side_lag.LAG) + BK_*; same parameters; BUILD -> VALIDATE one-sided
seconds; compared with model_it4b_side_lag.txt on the same rows. Usage: python -I side_book.py"""
import os, sys, glob, json, time
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
sys.argv = [sys.argv[0], "four"]
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from scipy import stats
import train5 as t5
import train3 as t3
import side_lag as sl
C = t3.C; R = t3.R
OB = C + "/bybit_ob"
from book_feats import BK as _BK, BK_LAG, book_arrays as _ba, book_feats
VARIANT = os.environ.get("BOOK_VARIANT", "base")  # "lag": + decision-lag book segments
BK = list(_BK) + (list(BK_LAG) if VARIANT == "lag" else [])
SUF = "" if VARIANT == "base" else "_" + VARIANT


def book_arrays(d0):
    return _ba(d0, {dd: f"{OB}/linear_{dd}.parquet" for dd in (d0 - 86400, d0)})


def side_day_book(fp, spot):
    d0 = int(os.path.basename(fp)[:-8])
    s = sl.side_day(fp, spot)
    A = book_arrays(d0)
    sec = (s.start_ts.to_numpy(np.int64) + s.rel.to_numpy(np.int64))
    bf = book_feats(sec, A)
    for k in BK:
        s[k] = bf[k]
    return s


if __name__ == "__main__":
    t0 = time.time()
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    F2 = t5.SIDE + sl.LAG
    F3 = F2 + BK
    keep = list(dict.fromkeys(F3 + ["truth_up", "yT_one", "cid", "rel", "start_ts"]))
    B = pd.concat([side_day_book(fp, spot)[keep] for fp in files if int(os.path.basename(fp)[:-8]) < t3.V0 and os.path.exists(f"{C}/fut/{os.path.basename(fp)}")], ignore_index=True)
    print("BUILD side rows", len(B), "with book", round(float(B.BK_imb.notna().mean()), 3), round(time.time() - t0), flush=True)
    Bb = B[B.BK_imb.notna()]
    m = lgb.train(t3.SPARAMS, lgb.Dataset(Bb[F3], Bb.truth_up), 300); m.save_model(f"{CODE}/model_it5_side_book{SUF}.txt")
    # same-rows control: iteration-4 features retrained on exactly the book-covered BUILD rows
    mc = lgb.train(t3.SPARAMS, lgb.Dataset(Bb[F2], Bb.truth_up), 300)
    del B, Bb
    m0 = lgb.Booster(model_file=f"{CODE}/model_it4b_side_lag.txt")
    V = pd.concat([side_day_book(fp, spot) for fp in files if t3.V0 <= int(os.path.basename(fp)[:-8]) < t3.V1], ignore_index=True)
    up = V.truth_up.to_numpy() == 1; has = V.BK_imb.notna().to_numpy()
    p1 = m.predict(V[F3]); p0 = m0.predict(V[F2]); pc = mc.predict(V[F2])
    ok1, ok0, okc = (p1 >= 0.5) == up, (p0 >= 0.5) == up, (pc >= 0.5) == up
    tk = V.yT_one.to_numpy().astype(bool)
    # no-move segment: none of the six BTC series moved > 0.1 bp over [s-4, s-1) (C6 largest move) and |ETH| small
    mx6 = V[[f"{q}_pm3000" for q in ("F", "O", "B", "S", "Y", "K")]].abs().max(axis=1).fillna(0).to_numpy()
    eth = (V["E_pm3000"].abs().fillna(0) / 1.235).to_numpy()
    nomove = (mx6 <= 0.1) & (eth <= 0.1)
    b01, b10 = int((ok1 & ~ok0 & has).sum()), int((~ok1 & ok0 & has).sum())
    seg = lambda ok, m_: round(float(ok[m_].mean()), 4) if m_.any() else None
    res = {"n": int(len(V)), "book_coverage": round(float(has.mean()), 4),
           "side_book_all": seg(ok1, np.ones(len(V), bool)), "side_it4b_lag_all": seg(ok0, np.ones(len(V), bool)),
           "on_book_rows": {"n": int(has.sum()), "book": seg(ok1, has), "it4b_lag_frozen": seg(ok0, has), "control_retrained_same_rows": seg(okc, has),
                            "taker_book": seg(ok1, has & tk), "taker_it4b": seg(ok0, has & tk),
                            "maker_only_book": seg(ok1, has & ~tk), "maker_only_it4b": seg(ok0, has & ~tk),
                            "no_move_n": int((has & nomove).sum()), "no_move_book": seg(ok1, has & nomove), "no_move_it4b": seg(ok0, has & nomove),
                            "moving_book": seg(ok1, has & ~nomove), "moving_it4b": seg(ok0, has & ~nomove)},
           "mcnemar_vs_frozen": {"book_only_right": b01, "frozen_only_right": b10, "p": float(stats.binomtest(b01, b01 + b10, 0.5).pvalue) if b01 + b10 else None},
           "book_gain_share": round(float(sum(g for k, g in zip(F3, m.feature_importance("gain")) if k in BK) / m.feature_importance("gain").sum()), 4),
           "top_book_feats": sorted([(k, round(float(g), 1)) for k, g in zip(F3, m.feature_importance("gain")) if k in BK], key=lambda x: -x[1])[:6]}
    # single-signal agreement on VALIDATE
    side = np.where(up, 1, -1)
    for k in ("BK_imb", "BK_imb5", "BK_imb_avg1", "BK_micro", "BK_mid1", "BK_mid3"):
        x = V[k].to_numpy(float)
        for nm, mm in (("all", has), ("no_move", has & nomove)):
            mm2 = mm & (x != 0) & np.isfinite(x)
            res.setdefault("agreement", {}).setdefault(k, {})[nm] = {"n": int(mm2.sum()), "agree": round(float((np.sign(x[mm2]) == side[mm2]).mean()), 4) if mm2.any() else None}
    # where the touch imbalance disagrees with the frozen model: who is right?
    x = V.BK_imb_avg1.to_numpy(float)
    for thr in (0.3, 0.5, 0.7):
        dm = has & (np.abs(x) >= thr) & (np.sign(x) != np.sign(p0 - 0.5))
        res.setdefault("disagree_with_frozen", {})[str(thr)] = {"n": int(dm.sum()), "book_right": round(float((np.sign(x[dm]) == side[dm]).mean()), 4) if dm.any() else None}
    V[["cid", "rel", "start_ts", "truth_up", "yT_one"]].assign(ps_book=p1.astype(np.float32), ps_frozen=p0.astype(np.float32), has_book=has, nomove=nomove).to_parquet(f"{C}/val_side_book_it5{SUF}.parquet", index=False)
    print(json.dumps(res, indent=0)); json.dump(res, open(f"{R}/results_side_book_iter5{SUF}.json", "w"), indent=1)
    print("done", round(time.time() - t0))
