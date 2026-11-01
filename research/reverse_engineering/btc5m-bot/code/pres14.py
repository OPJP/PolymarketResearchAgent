"""Iteration 14, X129 (information panel P5): audit the block-second presence margin against a CAPTURE-AWARE market baseline.
VALIDATE block seconds of 10-17..22 (the capture exists only there; BUILD has none, so every new model is fitted on 10-17..19 and
scored on 10-20..22 -- a disclosed deviation from the BUILD-fit rule). New market-only inputs from the public capture (server-ms
Polymarket trades; the operator's txs and W4 / W5 taker txs excluded): BUY count and size of OTHERS' prints on the cell's outcome o
and on the other outcome in five 500-ms bins over [tau - 3500, tau - 1000) and SELL count on o (tau = start of block second s; the
same 1-s horizon as the frozen cells). Models (t3.PARAMS, 200 rounds, positives + 30% negatives with weight 1/0.3):
  MSB    = MKT_PURE + AUG (blkaug9) + capture prints   (capture-aware market baseline)
  AUGR   = MKT_PURE + AUG refitted on the same days   (same-split control)
  FULLMS = frozen FULL features + capture prints + knee-clock spot features (outcome-signed microprice slices / sharp ticks)
Scored on 10-20..22 with the frozen model_it5_blk_full.txt and model_it9_blk_aug.txt; gains with the 2-h block bootstrap.
Usage: python pres14.py HF_DIR TAPE_DIR"""
import os, sys, glob, json, time, gc
ARGS = sys.argv[1:3]
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb, pyarrow.parquet as pq
from sklearn.metrics import roc_auc_score
import blkaug9 as ba
t5, t3 = ba.t5, ba.t3
from alt_cells import BETA
from block_bins import block_seconds
from decision_presence import MKT_PURE, FULL
from block_presence import keep_mask
import final_rule as fr

C = t3.C
R = C.replace(".cache/re/btc5m-bot", "research/reverse_engineering/btc5m-bot/results")
H = 1792713600
DAYS0 = [1792195200 + 86400 * i for i in range(6)]
FITD = set(DAYS0[:3])
W45 = {"0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}
PMF = [f"pm_{side}_{q}_{j}" for side in ("o", "x") for q in ("n", "v") for j in range(5)] + ["pm_o_sell"]
SPF = [f"sp_dm{j}" for j in range(5)] + ["sp_rmax", "sp_rmin", "sp_rsum", "sp_rcnt"]


def at(T, X, t):
    i = np.searchsorted(T, t, "left") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def day_extra(day, d0, c, win_tok, excl, A):
    """capture features for the cells c (cid, is_up, rel, start_ts)."""
    tau = ((c.start_ts.to_numpy(np.int64) + c.rel.to_numpy(np.int64)) * 1000)
    n = len(c); out = {k: np.zeros(n, np.float32) for k in PMF}
    tr = pd.read_parquet(f"{A}/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash", "tokenId", "tradeSize", "tradeSide"])
    tr = tr[~tr.transactionHash.str.lower().isin(excl)]
    tr = tr.assign(tokenId=tr.tokenId.astype(str)).sort_values("exchangeTimestampMs", kind="stable")
    bt = {k: (g.exchangeTimestampMs.to_numpy(np.int64), np.concatenate([[0.0], np.cumsum(g.tradeSize.to_numpy(float))])) for k, g in tr[tr.tradeSide == "BUY"].groupby("tokenId")}
    st = {k: g.exchangeTimestampMs.to_numpy(np.int64) for k, g in tr[tr.tradeSide == "SELL"].groupby("tokenId")}
    del tr
    cid = c.cid.to_numpy(); up = c.is_up.to_numpy(bool)
    keys = pd.DataFrame({"cid": cid, "up": up}).groupby(["cid", "up"]).indices
    for (cc, uu), ii in keys.items():
        if cc not in win_tok:
            continue
        to, tx = (win_tok[cc][0], win_tok[cc][1]) if uu else (win_tok[cc][1], win_tok[cc][0])
        tt = tau[ii]
        for side, tk in (("o", to), ("x", tx)):
            if tk not in bt:
                continue
            T_, cs = bt[tk]
            for j in range(5):
                a = np.searchsorted(T_, tt - 3500 + 500 * j, "left"); b = np.searchsorted(T_, tt - 3000 + 500 * j, "left")
                out[f"pm_{side}_n_{j}"][ii] = b - a; out[f"pm_{side}_v_{j}"][ii] = cs[b] - cs[a]
        if to in st:
            T_ = st[to]; out["pm_o_sell"][ii] = np.searchsorted(T_, tt - 1000, "left") - np.searchsorted(T_, tt - 3500, "left")
    # knee-clock spot features (Up-signed per window second, then outcome-signed)
    sp = {k: np.full(n, np.nan, np.float32) for k in SPF}
    G = np.arange(-3250, -999, 50)
    for h0 in range(0, 24, 4):
        lo, hi = (d0 + h0 * 3600) * 1000, (d0 + (h0 + 4) * 3600) * 1000
        sel = np.where((tau >= lo) & (tau < hi))[0]
        if not len(sel):
            continue
        t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity"],
                          filters=[("type", "=", "book"), ("receivedTimestampMs", ">=", lo - 8000), ("receivedTimestampMs", "<", hi + 2000)])
        Tb = t.column("receivedTimestampMs").to_numpy() - 131
        bp, bq, ap, aq = (t.column(k).to_numpy().astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
        mic = (bp * aq + ap * bq) / (bq + aq); o = np.argsort(Tb, kind="stable"); Tb, mic = Tb[o], mic[o]
        del t, bp, bq, ap, aq
        tt = tau[sel]
        for j in range(5):
            sp[f"sp_dm{j}"][sel] = (at(Tb, mic, tt - 1000 - 500 * j) / at(Tb, mic, tt - 1500 - 500 * j) - 1) * 1e4
        for c0 in range(0, len(sel), 20000):
            ss = sel[c0:c0 + 20000]; tg = tau[ss][:, None] + G[None, :]
            r = np.nan_to_num((at(Tb, mic, tg.ravel()) / at(Tb, mic, tg.ravel() - 250) - 1).reshape(tg.shape) * 1e4)
            big = np.abs(r) >= 0.5
            sp["sp_rmax"][ss] = r.max(1); sp["sp_rmin"][ss] = r.min(1); sp["sp_rsum"][ss] = (r * big).sum(1)
            sp["sp_rcnt"][ss] = (big & (r > 0)).sum(1) - (big & (r < 0)).sum(1)
        del Tb, mic; gc.collect()
    sg = np.where(up, 1.0, -1.0).astype(np.float32)
    for j in range(5):
        out[f"sp_dm{j}"] = sp[f"sp_dm{j}"] * sg
    out["sp_rmax"] = np.where(up, sp["sp_rmax"], -sp["sp_rmin"]).astype(np.float32)
    out["sp_rmin"] = np.where(up, sp["sp_rmin"], -sp["sp_rmax"]).astype(np.float32)
    out["sp_rsum"] = sp["sp_rsum"] * sg; out["sp_rcnt"] = sp["sp_rcnt"] * sg
    return out


def main():
    A, TD = ARGS
    t0 = time.time(); rng = np.random.default_rng(14)
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "ts", "tx", "start_ts"])
    bs = block_seconds(fl[fl.ts < H])
    op_tx = set(fl.loc[fl.start_ts >= 1792195200, "tx"].str.lower())
    win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "start_ts", "up_token", "down_token"])
    win = win[(win.start_ts >= DAYS0[0]) & (win.start_ts < H)]
    win_tok = {r.cid: (str(r.up_token), str(r.down_token)) for r in win.itertuples()}
    w45 = set()
    for cc in win.cid:
        p = f"{TD}/{cc}.parquet"
        if os.path.exists(p):
            d = pd.read_parquet(p, columns=["proxyWallet", "transactionHash"])
            w45 |= set(d.loc[d.proxyWallet.str.lower().isin(W45), "transactionHash"].str.lower())
    excl = op_tx | w45
    need = sorted(set(t3.COLS) | {"age_last", "ask_o", "m_last", "sig", "tau", "r3", "z", "wi"} | set(ba.OTH) | {"yGF", "yXM", "yDS"})
    mf = lgb.Booster(model_file=f"{CODE}/model_it5_blk_full.txt"); ma = lgb.Booster(model_file=f"{CODE}/model_it9_blk_aug.txt")
    FCOL = mf.feature_name()
    SETS = {"MSB": MKT_PURE + ba.AUG + PMF, "AUGR": MKT_PURE + ba.AUG, "FULLMS": FCOL + PMF + SPF}
    tr_parts, sc_parts = [], []
    for d0 in DAYS0:
        day = time.strftime("%Y-%m-%d", time.gmtime(d0))
        c = pd.read_parquet(f"{C}/cells/{d0}.parquet", columns=need)
        c = ba.add_aug(c)
        t = (c.start_ts.to_numpy() + c.rel.to_numpy()).astype(np.int64)
        k = keep_mask(t, bs); c = c[k].reset_index(drop=True); t = t[k]
        RF = t5.ref_feats(c, d0, spot)
        for k2 in RF.columns:
            c[k2] = RF[k2].to_numpy()
        del RF
        t5.set_rel(c, BETA)
        ex = day_extra(day, d0, c, win_tok, excl, A)
        for k2, v in ex.items():
            c[k2] = v
        cols = sorted(set(sum(SETS.values(), [])))
        if d0 in FITD:
            sel = (c.y.to_numpy() == 1) | (rng.random(len(c)) < 0.3)
            sub = c.loc[sel, cols + ["y"]].copy(); sub["w"] = np.where(sub.y == 1, 1.0, 1 / 0.3)
            tr_parts.append(sub)
        else:
            sc_parts.append(c[cols + ["y", "yGF", "yXM", "yDS"]].assign(t=t, pf=mf.predict(c[FCOL]).astype(np.float32), pa=ma.predict(c[MKT_PURE + ba.AUG]).astype(np.float32)))
        del c; gc.collect()
        print(day, round(time.time() - t0), flush=True)
    B = pd.concat(tr_parts, ignore_index=True); del tr_parts
    S = pd.concat(sc_parts, ignore_index=True); del sc_parts
    auc = lambda yy, q: round(float(roc_auc_score(yy, q)), 4)
    res = {"fit_cells_sampled": int(len(B)), "score_cells": int(len(S)), "w45_tx_excluded": len(w45),
           "auc_frozen_full": auc(S.y, S.pf), "auc_frozen_aug_baseline": auc(S.y, S.pa)}
    P = {"pf": S.pf.to_numpy(), "pa": S.pa.to_numpy()}
    for nm, cols in SETS.items():
        m = lgb.train(t3.PARAMS, lgb.Dataset(B[cols], B.y, weight=B.w), num_boost_round=200)
        P[nm] = m.predict(S[cols]).astype(np.float32)
        res[f"auc_{nm}"] = auc(S.y, P[nm])
        if nm == "MSB":
            imp = pd.Series(m.feature_importance("gain"), index=cols).sort_values(ascending=False)
            res["MSB_importance_top10"] = {k: round(float(v / imp.sum()), 4) for k, v in imp.head(10).items()}
            res["MSB_capture_share_of_gain"] = round(float(imp[PMF].sum() / imp.sum()), 4)
        print(nm, res[f"auc_{nm}"], round(time.time() - t0), flush=True)
    y = S.y.to_numpy(); blocks = S.t.to_numpy() // 7200
    res["gain_frozen_full_vs_MSB"] = round(res["auc_frozen_full"] - res["auc_MSB"], 4)
    res["gain_FULLMS_vs_MSB"] = round(res["auc_FULLMS"] - res["auc_MSB"], 4)
    res["gain_frozen_full_vs_AUGR"] = round(res["auc_frozen_full"] - res["auc_AUGR"], 4)
    res["boot_frozen_full_vs_MSB"] = fr._block_boot_gain(y, P["pf"], P["MSB"], blocks, n_boot=2000)
    res["boot_FULLMS_vs_MSB"] = fr._block_boot_gain(y, P["FULLMS"], P["MSB"], blocks, n_boot=2000)
    res["by_wallet"] = {}
    for w in ("GF", "XM", "DS"):
        yw = S[f"y{w}"].to_numpy()
        res["by_wallet"][w] = {k: auc(yw, P[k]) for k in ("pf", "MSB", "FULLMS", "AUGR")}
    half = S.t.to_numpy() < int(pd.Timestamp("2026-10-21 12:00", tz="UTC").timestamp())
    res["halves"] = {nm: {k: auc(y[m], P[k][m]) for k in ("pf", "MSB", "FULLMS")} for nm, m in (("first", half), ("second", ~half))}
    json.dump(res, open(f"{R}/pres14.json", "w"), indent=1)
    print(json.dumps(res, indent=1)); print("done", round(time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
