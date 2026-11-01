"""Iteration 6: the live study found the ETH perp microprice (sized top of book) to be the strongest precursor of the bot's
taker side, including the matches with no trade move. Historical test: Bybit ETHUSDT linear orderbook.200 archive (100-ms
buckets from bybit_ob.py with BYBIT_SYM=ETHUSDT) -> the same point-in-time book features as the BTC book (book_feats, renamed
BE_*), added to the iteration-5 side model (it4b side features + lagged segments + Bybit BTC book BK_*). BUILD one-sided
seconds -> VALIDATE one-sided seconds; compared with model_it5_side_book.txt on the same rows. Usage: python -I side_book_eth6.py"""
import os, sys, glob, json, time
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
sys.argv = [sys.argv[0], "four"]
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from scipy import stats
import train5 as t5
import train3 as t3
import side_lag as sl
from book_feats import BK, book_arrays as _ba, book_feats
C = t3.C; R = t3.R
OB = C + "/bybit_ob"
BE = [k.replace("BK_", "BE_") for k in BK]


def side_day_both(fp, spot):
    d0 = int(os.path.basename(fp)[:-8])
    s = sl.side_day(fp, spot)
    sec = (s.start_ts.to_numpy(np.int64) + s.rel.to_numpy(np.int64))
    A = _ba(d0, {dd: f"{OB}/linear_{dd}.parquet" for dd in (d0 - 86400, d0)})
    bf = book_feats(sec, A)
    for k in BK:
        s[k] = bf[k]
    E = _ba(d0, {dd: f"{OB}/linear_ETHUSDT_{dd}.parquet" for dd in (d0 - 86400, d0)})
    ef = book_feats(sec, E)
    for k in BK:
        s[k.replace("BK_", "BE_")] = ef[k]
    return s


if __name__ == "__main__":
    t0 = time.time()
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    F3 = t5.SIDE + sl.LAG + BK
    F4 = F3 + BE
    keep = list(dict.fromkeys(F4 + ["truth_up", "yT_one", "cid", "rel", "start_ts"]))
    B = pd.concat([side_day_both(fp, spot)[keep] for fp in files if int(os.path.basename(fp)[:-8]) < t3.V0 and os.path.exists(f"{C}/fut/{os.path.basename(fp)}")], ignore_index=True)
    has_b = B.BE_imb.notna() & B.BK_imb.notna()
    print("BUILD rows", len(B), "with ETH book", round(float(has_b.mean()), 3), round(time.time() - t0), flush=True)
    Bb = B[has_b]
    m4 = lgb.train(t3.SPARAMS, lgb.Dataset(Bb[F4], Bb.truth_up), 300); m4.save_model(f"{CODE}/model_it6_side_book_eth.txt")
    mc = lgb.train(t3.SPARAMS, lgb.Dataset(Bb[F3], Bb.truth_up), 300)  # same-rows control without the ETH book
    nB = int(len(Bb)); del B, Bb
    m5 = lgb.Booster(model_file=f"{CODE}/model_it5_side_book.txt")
    V = pd.concat([side_day_both(fp, spot)[keep] for fp in files if t3.V0 <= int(os.path.basename(fp)[:-8]) < t3.V1], ignore_index=True)
    up = V.truth_up.to_numpy() == 1
    has = (V.BE_imb.notna() & V.BK_imb.notna()).to_numpy()
    p4 = m4.predict(V[F4]); p5 = m5.predict(V[F3]); pc = mc.predict(V[F3])
    ok4, ok5, okc = (p4 >= 0.5) == up, (p5 >= 0.5) == up, (pc >= 0.5) == up
    tk = V.yT_one.to_numpy().astype(bool)
    mid = np.median(V.start_ts); h1 = V.start_ts.to_numpy() < mid
    seg = lambda ok, m_: round(float(ok[m_].mean()), 4) if m_.any() else None
    b01, b10 = int((ok4 & ~ok5 & has).sum()), int((~ok4 & ok5 & has).sum())
    res = {"build_rows_with_eth_book": nB, "validate_rows": int(len(V)), "eth_book_coverage_validate": round(float(has.mean()), 4),
           "side_it6_eth_book": seg(ok4, has), "side_it5_frozen_same_rows": seg(ok5, has), "control_retrained_without_eth": seg(okc, has),
           "taker_it6": seg(ok4, has & tk), "taker_it5": seg(ok5, has & tk), "halves_it6": [seg(ok4, has & h1), seg(ok4, has & ~h1)],
           "mcnemar_vs_it5": {"it6_only_right": b01, "it5_only_right": b10, "p": float(stats.binomtest(b01, b01 + b10, 0.5).pvalue) if b01 + b10 else None},
           "eth_book_gain_share": round(float(sum(g for k, g in zip(F4, m4.feature_importance("gain")) if k in BE) / m4.feature_importance("gain").sum()), 4),
           "top_eth_feats": sorted([(k, round(float(g), 1)) for k, g in zip(F4, m4.feature_importance("gain")) if k in BE], key=lambda x: -x[1])[:6]}
    print(json.dumps(res, indent=1)); json.dump(res, open(f"{R}/results_side_book_eth_iter6.json", "w"), indent=1)
    print("done", round(time.time() - t0))
