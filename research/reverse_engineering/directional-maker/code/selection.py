"""Selection pilot: among all taker orders that trade inside BTC 5m windows, which ones
fill a cluster maker order? Features at the print use only data published before the
print's second (earlier prints, Binance closes up to the previous second). Label = the
transaction contains a cluster maker fill (on-chain roles). BUILD fit -> VALIDATE.
No rotation null yet (pilot)."""
from __future__ import annotations

import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from features import Spot, fair_up  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".cache/re/directional-maker"
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=1000, feature_fraction=0.8,
         bagging_fraction=0.8, bagging_freq=1, lambda_l2=10.0, verbose=-1, seed=7, num_threads=2)


def prints(lo, hi, sp, ch_tx):
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[(w.start_ts >= lo) & (w.end_ts <= hi)]
    tk = pd.read_parquet(OUT / f"taker_5m_{lo}_{hi}.parquet")
    tk = tk.merge(w[["cid", "start_ts", "end_ts", "up_token"]], on="cid")
    tk = tk[(tk.ts >= tk.start_ts) & (tk.ts < tk.end_ts)].copy()
    tk["is_up"] = tk.asset == tk.up_token
    buy = tk.side == "BUY"
    # maker side = the token whose BID the taker hits: taker BUY of X hits bids on the complement (mint) or asks on X;
    # label below only uses cluster BUY (bid) fills, so define the bid side hit: complement for BUY, same for SELL
    tk["mside_up"] = np.where(buy, ~tk.is_up, tk.is_up)
    tk["mprice"] = np.where(buy, 1 - tk.price, tk.price)  # implied bid price on the maker side
    tk = tk.sort_values(["cid", "ts"]).reset_index(drop=True)
    fu, z = fair_up(sp, tk.start_ts.to_numpy(), tk.end_ts.to_numpy(), tk.ts.to_numpy())
    sgn = np.where(tk.mside_up, 1, -1)
    tk["fair_m"] = np.where(tk.mside_up, fu, 1 - fu)
    tk["edge_m"] = tk.fair_m - tk.mprice
    tk["z_m"] = z * sgn
    tk["rel"] = tk.ts - tk.start_ts
    t = tk.ts.to_numpy()
    st = sp.last(t)
    for k in (1, 3, 10, 30):
        tk[f"r{k}"] = np.log(st / sp.last(t - k)) * 1e4 * sgn
    tk["sig"] = sp.sigma(t) * 1e4
    # previous print in the same window strictly earlier second (implied Up price) -> move into this print
    tk["up_px"] = np.where(tk.is_up, tk.price, 1 - tk.price)
    g = tk.groupby("cid")
    prev_ts = g.ts.shift(1)
    tk["dt_prev"] = (tk.ts - prev_ts).fillna(999)
    tk["dpx_prev"] = ((tk.up_px - g.up_px.shift(1)) * sgn).fillna(0)
    tk["n_prior"] = g.cumcount()
    tk["y"] = tk.tx.isin(ch_tx).astype(int)
    return tk


def main():
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    sp = Spot(spd.sec.to_numpy(), spd.px.to_numpy())
    ch = pd.read_parquet(OUT / "fills_enriched.parquet")
    ch_tx = set(ch.loc[(ch.role == "maker") & (ch.side == "BUY"), "tx"])
    tr = prints(1791504000, 1792108800, sp, ch_tx)
    va = prints(1792108800, 1792713600, sp, ch_tx)
    feats = ["rel", "mside_up", "mprice", "fair_m", "edge_m", "z_m", "r1", "r3", "r10", "r30", "sig", "size", "dt_prev", "dpx_prev", "n_prior"]
    if "nosize" in sys.argv[1:]:
        feats = [f for f in feats if f != "size"]
    print("prints", len(tr), len(va), "base rate", round(tr.y.mean(), 4), round(va.y.mean(), 4))
    m = lgb.train(P, lgb.Dataset(tr[feats], tr.y), 300)
    pv = m.predict(va[feats])
    auc = roc_auc_score(va.y, pv)
    thr = np.quantile(m.predict(tr[feats]), 0.85)  # flag the top 15% of BUILD scores
    flag = pv >= thr
    recall = float(flag[va.y == 1].mean())
    lift = float(va.y[flag].mean() / va.y.mean())
    print(f"selection pilot VALIDATE AUC {auc:.4f}; threshold = BUILD top 15%: recall {recall:.3f}, lift {lift:.2f}, flagged {flag.mean():.3f}")
    imp = sorted(zip(feats, m.feature_importance("gain")), key=lambda x: -x[1])[:8]
    print("gain", [(a, int(b)) for a, b in imp])
    from polyrea.analysis.updown import stratified_auc
    strata = (np.clip((va.mprice.to_numpy() * 10).astype(int), 0, 9) * 100 + np.clip((va.rel.to_numpy() // 30).astype(int), 0, 9) * 10
              + va.mside_up.to_numpy().astype(int))
    print("stratified AUC (implied price decile x 30-s bucket x side)", round(stratified_auc(pv, va.y.to_numpy(), strata), 4))
    for k in ("edge_m", "mprice", "size", "rel"):
        print("univariate", k, round(roc_auc_score(va.y, va[k]), 4))


if __name__ == "__main__":
    main()
