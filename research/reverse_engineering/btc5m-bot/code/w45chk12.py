"""Iteration 12 leak check: the tape features of every frozen model exclude the three dossier wallets but NOT the operator's
fourth / fifth wallets (W4 0xd844..., W5 0x03b4...), whose fan-out legs precede 7.4% of the cluster's taker seconds by 1-2 s.
This script rebuilds the VALIDATE cells' tape features with W4 / W5 prints also removed (tape_feats.CL patched), recomputes
the reference features, predicts the frozen it4b netflow and nf12b models, re-runs the exposure tracker (trk_a, average
target) and scores the frozen block-second presence model on the rebuilt cells against the frozen pure baseline.
Usage: python w45chk12.py TAPE_DIR"""
import os, sys, glob, json, time
TAPE_DIR_ARG = sys.argv[-1]
sys.argv = [sys.argv[0], "four"]
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
import train5 as t5
import train3 as t3
import tape_feats as tf
import nf12 as nf12mod
import spot as spotmod
from build_cells_day import add_extra
from alt_cells import BETA
from block_bins import block_seconds
from block_presence import keep_mask
import track12 as T
C = t3.C; R = t3.R + "/results"; V0, V1 = t3.V0, t3.V1
W45 = {"0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}


def main():
    t0 = time.time()
    tape_dir = TAPE_DIR_ARG
    tf.TAPE_DIR = tape_dir
    tf.CL = set(tf.CL) | W45
    sp = spotmod.Spot(path=f"{C}/binance_1s.parquet")
    spot = pd.read_parquet(f"{C}/binance_1s.parquet"); spot["sec"] = spot.sec.astype(np.int64)
    px = pd.Series(np.asarray(sp.px, float)).ffill().bfill().to_numpy(float)
    fills = pd.read_parquet(f"{C}/fills.parquet")
    fl_b = fills[["block", "ts"]]
    bs = block_seconds(fl_b[fl_b.ts < V1])
    mn = lgb.Booster(model_file=f"{CODE}/model_it4b_netflow.txt"); mb = lgb.Booster(model_file=f"{CODE}/model_it12_nf12b.txt")
    mf = lgb.Booster(model_file=f"{CODE}/model_it5_blk_full.txt"); mp = lgb.Booster(model_file=f"{CODE}/model_it5_blk_pure.txt")
    files = sorted(f for f in glob.glob(f"{C}/cells/*.parquet") if V0 <= int(os.path.basename(f)[:-8]) < V1)
    P, Y, PF, PP = [], [], [], []
    for fp in files:
        d0 = int(os.path.basename(fp)[:-8])
        c = pd.read_parquet(fp)
        fday = fills[(fills.start_ts >= d0) & (fills.start_ts < d0 + 86400)]
        c = tf.add_tape_feats(c, fday, sp)
        c = add_extra(c)
        RF = t5.ref_feats(c, d0, spot)
        for k in RF.columns:
            c[k] = RF[k].to_numpy()
        del RF
        t5.set_rel(c, BETA)
        n = len(c) // 2
        s = t5.side_rows(c, np.arange(n), n)
        nf = mn.predict(s[t5.SIDE], num_threads=4)
        X = nf12mod.pair_frame(c[["cid", "start_ts", "is_up"] + nf12mod.SPOT + nf12mod.TAPE], px, int(sp.s0), pd.Series(dtype=float))
        pb = pd.Series(mb.predict(X[mb.feature_name()], num_threads=4), index=pd.MultiIndex.from_arrays([X.cid.to_numpy(), X.rel.to_numpy().astype(np.int64)]))
        pb = pb.reindex(pd.MultiIndex.from_arrays([s.cid.to_numpy(), s.rel.to_numpy().astype(np.int64)])).to_numpy()
        P.append(pd.DataFrame({"cid": s.cid.to_numpy(), "rel": s.rel.to_numpy(), "nf": nf, "nf12b": pb, "ask_u": c.ask_o.to_numpy()[:n], "ask_d": c.ask_o.to_numpy()[n:]}))
        t = (c.start_ts.to_numpy() + c.rel.to_numpy()).astype(np.int64)
        k = keep_mask(t, bs)
        cb = c[k]
        PF.append(mf.predict(cb[mf.feature_name()], num_threads=4)); PP.append(mp.predict(cb[mp.feature_name()], num_threads=4)); Y.append(cb.y.to_numpy())
        del c, s, X, cb
        print("day", d0, round(time.time() - t0), flush=True)
    V = pd.concat(P, ignore_index=True)
    V.to_parquet(f"{C}/it12/w45_val.parquet")
    y = np.concatenate(Y); pf = np.concatenate(PF); pp = np.concatenate(PP)
    res = {"presence_block_seconds_rebuilt": {"auc_full": round(float(roc_auc_score(y, pf)), 4), "auc_pure": round(float(roc_auc_score(y, pp)), 4)}}
    res["presence_block_seconds_rebuilt"]["gain"] = round(res["presence_block_seconds_rebuilt"]["auc_full"] - res["presence_block_seconds_rebuilt"]["auc_pure"], 4)
    # tracker on the rebuilt predictions (W4 / W5 also excluded from the fill liquidity)
    T.CL = set(T.CL) | W45
    win = pd.read_parquet(f"{C}/windows.parquet").set_index("cid")
    vo = V.sort_values(["cid", "rel"]).copy(); vo["nf"] = 0.5 * (vo.nf + vo.nf12b.fillna(0))
    fl = fills[fills.start_ts >= V0]
    mk = set(fl.loc[fl.role == "M", "tx"].str.lower())
    parts = []
    for cid in vo.cid.unique():
        p = f"{tape_dir}/{cid}.parquet"
        if os.path.exists(p):
            d = pd.read_parquet(p, columns=["proxyWallet", "side", "size", "price", "timestamp", "outcome", "transactionHash"])
            if len(d):
                parts.append(d.assign(cid=cid))
    A = pd.concat(parts, ignore_index=True); del parts
    A = A[(A.side == "BUY") & ~A.proxyWallet.str.lower().isin(T.CL)]
    A["rel"] = A.timestamp - win.loc[A.cid, "start_ts"].to_numpy(); A = A[(A.rel >= -2) & (A.rel <= 305)]
    A["mk"] = A.transactionHash.str.lower().isin(mk); A["up"] = A.outcome == "Up"
    A = A.sort_values(["cid", "up", "rel"], kind="stable")
    tapes = {}
    for (cid, o), dd in A.groupby(["cid", "up"], sort=False):
        tapes.setdefault(cid, {True: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool)), False: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool))})
        tapes[cid][bool(o)] = (dd.rel.to_numpy(np.int64), dd.price.to_numpy(float), dd["size"].to_numpy(float), dd.mk.to_numpy())
    Tf, fin = T.run(win, vo, tapes, mk, T.VARIANTS["trk_a"])
    cids = vo.cid.unique()
    rp = Tf.groupby("cid").pnl.sum().reindex(cids).fillna(0)
    fl = fl.assign(pnl=fl.shares * (np.where(fl.is_up, fl.up_payout, 1 - fl.up_payout) - fl.price) - fl.fee_usd)
    wp = fl.groupby("cid").pnl.sum().reindex(cids).fillna(0)
    res["tracker_avg_rebuilt"] = {"pearson": round(float(rp.corr(wp)), 4), "spearman": round(float(rp.corr(wp, method="spearman")), 4)}
    for w in ("GF", "XM", "DS"):
        ww = fl[fl.wallet == w].groupby("cid").pnl.sum().reindex(cids).fillna(0)
        res["tracker_avg_rebuilt"][w] = round(float(rp.corr(ww)), 4)
    old = pd.read_parquet(f"{C}/val_outcome_it4b.parquet", columns=["cid", "rel", "nf"]).merge(V[["cid", "rel", "nf"]], on=["cid", "rel"], suffixes=("_old", "_new"))
    res["corr_nf_old_vs_rebuilt"] = round(float(np.corrcoef(old.nf_old, old.nf_new)[0, 1]), 4)
    res["elapsed_s"] = round(time.time() - t0)
    print(json.dumps(res, indent=1))
    json.dump(res, open(f"{R}/w45chk12.json", "w"), indent=1)


if __name__ == "__main__":
    main()
