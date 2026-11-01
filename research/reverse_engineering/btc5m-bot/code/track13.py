"""Iteration 13: the pre-registered two-stream exposure tracker (NOTES.md iteration 13, 02:17 UTC). Same replica, constants and
strict-fill convention as track12.run (trk_a); targets:
  trk_a_2s  (PRIMARY candidate): 0.5 x (nf_it4b + L13 + S13)
  trk_a_LS  (secondary): L13 + S13
  per-wallet secondaries: a_w L13 + b_w S13 with BUILD per-window OLS loadings of the wallet's net on the pooled L and S nets.
Usage: python track13.py TAPE_DIR"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import track12 as t12
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
VAL0, H = t12.VAL0, t12.H


def load_tapes(tape_dir, cids, win, mk_tx):
    parts = []
    for cid in cids:
        p = f"{tape_dir}/{cid}.parquet"
        if os.path.exists(p):
            d = pd.read_parquet(p, columns=["proxyWallet", "side", "size", "price", "timestamp", "outcome", "transactionHash"])
            if len(d):
                parts.append(d.assign(cid=cid))
    A = pd.concat(parts, ignore_index=True)
    A = A[(A.side == "BUY") & ~A.proxyWallet.str.lower().isin(t12.CL)]
    A["rel"] = A.timestamp - win.loc[A.cid, "start_ts"].to_numpy()
    A = A[(A.rel >= -2) & (A.rel <= 305)]
    A["mk"] = A.transactionHash.str.lower().isin(mk_tx)
    A["up"] = A.outcome == "Up"
    A = A.sort_values(["cid", "up", "rel"], kind="stable")
    tapes = {}
    for (cid, o), dd in A.groupby(["cid", "up"], sort=False):
        tapes.setdefault(cid, {True: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool)), False: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool))})
        tapes[cid][bool(o)] = (dd.rel.to_numpy(np.int64), dd.price.to_numpy(float), dd["size"].to_numpy(float), dd.mk.to_numpy())
    return tapes


def score(T, fin, cids, W, win):
    rp = T.groupby("cid").pnl.sum().reindex(cids).fillna(0)
    out = {"fills": int(len(T)), "usd": round(float((T.price * T.shares).sum()), 1), "pnl_before_rebates": round(float(T.pnl.sum()), 1)}
    for w, wp in W.items():
        out[f"pnl_corr_{w}"] = {"pearson": round(float(rp.corr(wp)), 4), "spearman": round(float(rp.corr(wp, method="spearman")), 4)}
    half = win.loc[cids, "start_ts"].to_numpy() < (VAL0 + H) // 2
    for w, wp in W.items():
        x, y = rp.to_numpy(), wp.to_numpy()
        out[f"halves_{w}"] = [round(float(np.corrcoef(x[m], y[m])[0, 1]), 4) for m in (half, ~half)]
    blocks = win.loc[cids, "start_ts"].to_numpy() // 7200
    rng = np.random.default_rng(13); ub = np.unique(blocks); bidx = {b: np.where(blocks == b)[0] for b in ub}
    x, y = rp.to_numpy(), W["pool"].to_numpy(); bs = []
    for _ in range(1000):
        ii = np.concatenate([bidx[b] for b in rng.choice(ub, len(ub))]); bs.append(np.corrcoef(x[ii], y[ii])[0, 1])
    out["pool_pearson_block_ci95"] = [round(float(np.quantile(bs, 0.025)), 4), round(float(np.quantile(bs, 0.975)), 4)]
    return out, rp


def main():
    tape_dir = sys.argv[1]
    win = pd.read_parquet(f"{C}/windows.parquet").set_index("cid")
    vo = pd.read_parquet(f"{C}/val_outcome_it4b.parquet").sort_values(["cid", "rel"])
    ls = pd.read_parquet(f"{C}/it13/ls13_val.parquet")
    nb = pd.read_parquet(f"{C}/it12/nf12b_val.parquet")[["cid", "rel", "nf12b"]]
    vo = vo.merge(ls, on=["cid", "rel"], how="left").merge(nb, on=["cid", "rel"], how="left").sort_values(["cid", "rel"])
    for c in ("L13", "S13", "nf12b"):
        vo[c] = vo[c].fillna(0)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "shares", "price", "fee_usd", "cid", "start_ts", "is_up", "up_payout"])
    fl = fl[(fl.start_ts >= VAL0) & (fl.start_ts < H)]
    mk_tx = set(fl.loc[fl.role == "M", "tx"].str.lower())
    cids = vo.cid.unique()
    tapes = load_tapes(tape_dir, cids, win, mk_tx)
    fl["pay"] = np.where(fl.is_up, fl.up_payout, 1 - fl.up_payout)
    fl["pnl"] = fl.shares * (fl.pay - fl.price) - fl.fee_usd
    W = {w: fl[fl.wallet == w].groupby("cid").pnl.sum().reindex(cids).fillna(0) for w in ("GF", "XM", "DS")}
    W["pool"] = fl.groupby("cid").pnl.sum().reindex(cids).fillna(0)
    D = pd.read_parquet(f"{C}/it13/streams_win.parquet")
    b = D[D.start_ts < VAL0]
    load = {w: np.linalg.lstsq(np.c_[b.L, b.S], b["T" + w].to_numpy(), rcond=None)[0] for w in ("GF", "XM", "DS")}
    var = t12.VARIANTS["trk_a"]
    res = {"loadings_BUILD": {w: [round(float(x), 4) for x in v] for w, v in load.items()}}
    targets = {"trk_a_avg_check": 0.5 * (vo.nf + vo.nf12b), "trk_a_2s": 0.5 * (vo.nf + vo.L13 + vo.S13), "trk_a_LS": vo.L13 + vo.S13}
    for w, (a_, b_) in load.items():
        targets[f"trk_w_{w}"] = a_ * vo.L13 + b_ * vo.S13
    for nm, tg in targets.items():
        v2 = vo.assign(nf=tg.to_numpy())
        T, fin = t12.run(win, v2, tapes, mk_tx, var)
        r, rp = score(T, fin, cids, W, win)
        res[nm] = r
        print(nm, json.dumps({k: r[k] for k in r if k.startswith("pnl_corr") or k in ("pool_pearson_block_ci95", "halves_pool")}), flush=True)
    json.dump(res, open(f"{R}/track13.json", "w"), indent=1)


if __name__ == "__main__":
    main()
