"""Iteration 12: the exposure tracker's PnL correlation against its co-occurrence baseline (the same tracker on a
market-activity-only net-flow model, nf12m), with a paired 2-h block bootstrap of the gain, and per-day stability of the
primary tracker (trk_a_avg). Usage: python trkgain12.py TAPE_DIR"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import track12 as T
C, R, VAL0, H = T.C, T.R, T.VAL0, T.H


def series(win, vo, tapes, mk, var, cids):
    Tf, fin = T.run(win, vo, tapes, mk, var)
    return Tf.groupby("cid").pnl.sum().reindex(cids).fillna(0)


def main():
    tape_dir = sys.argv[1]
    win = pd.read_parquet(f"{C}/windows.parquet").set_index("cid")
    base = pd.read_parquet(f"{C}/val_outcome_it4b.parquet").sort_values(["cid", "rel"])
    nb = pd.read_parquet(f"{C}/it12/nf12b_val.parquet")[["cid", "rel", "nf12b"]]
    nm = pd.read_parquet(f"{C}/it12/nf12m_val.parquet")[["cid", "rel", "nf12m"]]
    v = base.merge(nb, on=["cid", "rel"], how="left").merge(nm, on=["cid", "rel"], how="left").sort_values(["cid", "rel"])
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "shares", "price", "fee_usd", "cid", "start_ts", "is_up", "up_payout"])
    fl = fl[fl.start_ts >= VAL0]
    mk = set(fl.loc[fl.role == "M", "tx"].str.lower())
    parts = []
    for cid in v.cid.unique():
        p = f"{tape_dir}/{cid}.parquet"
        if os.path.exists(p):
            d = pd.read_parquet(p, columns=["proxyWallet", "side", "size", "price", "timestamp", "outcome", "transactionHash"])
            if len(d):
                parts.append(d.assign(cid=cid))
    A = pd.concat(parts, ignore_index=True); del parts
    A = A[(A.side == "BUY") & ~A.proxyWallet.str.lower().isin(T.CL)]
    A["rel"] = A.timestamp - win.loc[A.cid, "start_ts"].to_numpy()
    A = A[(A.rel >= -2) & (A.rel <= 305)]
    A["mk"] = A.transactionHash.str.lower().isin(mk); A["up"] = A.outcome == "Up"
    A = A.sort_values(["cid", "up", "rel"], kind="stable")
    tapes = {}
    for (cid, o), dd in A.groupby(["cid", "up"], sort=False):
        tapes.setdefault(cid, {True: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool)), False: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool))})
        tapes[cid][bool(o)] = (dd.rel.to_numpy(np.int64), dd.price.to_numpy(float), dd["size"].to_numpy(float), dd.mk.to_numpy())
    fl["pnl"] = fl.shares * (np.where(fl.is_up, fl.up_payout, 1 - fl.up_payout) - fl.price) - fl.fee_usd
    cids = v.cid.unique()
    wp = fl.groupby("cid").pnl.sum().reindex(cids).fillna(0).to_numpy()
    va = v.copy(); va["nf"] = 0.5 * (va.nf + va.nf12b.fillna(0))
    vm = v.copy(); vm["nf"] = vm.nf12m.fillna(0)
    ra = series(win, va, tapes, mk, T.VARIANTS["trk_a"], cids).to_numpy()
    rm = series(win, vm, tapes, mk, T.VARIANTS["trk_a"], cids).to_numpy()
    st = win.loc[cids, "start_ts"].to_numpy()
    b = st // 7200; ub = np.unique(b); bi = {u: np.where(b == u)[0] for u in ub}; rng = np.random.default_rng(12)
    gp, gs = [], []
    from scipy.stats import spearmanr
    for _ in range(2000):
        ii = np.concatenate([bi[u] for u in rng.choice(ub, len(ub))])
        gp.append(np.corrcoef(ra[ii], wp[ii])[0, 1] - np.corrcoef(rm[ii], wp[ii])[0, 1])
    for _ in range(300):
        ii = np.concatenate([bi[u] for u in rng.choice(ub, len(ub))])
        gs.append(spearmanr(ra[ii], wp[ii])[0] - spearmanr(rm[ii], wp[ii])[0])
    res = {"tracker_avg": {"pearson": round(float(np.corrcoef(ra, wp)[0, 1]), 4), "spearman": round(float(spearmanr(ra, wp)[0]), 4)},
           "tracker_market_only": {"pearson": round(float(np.corrcoef(rm, wp)[0, 1]), 4), "spearman": round(float(spearmanr(rm, wp)[0]), 4)},
           "gain_pearson_ci95": [round(float(np.quantile(gp, 0.025)), 4), round(float(np.quantile(gp, 0.975)), 4)], "gain_pearson_p_le_0": round(float((np.array(gp) <= 0).mean()), 4),
           "gain_spearman_ci95_300draws": [round(float(np.quantile(gs, 0.025)), 4), round(float(np.quantile(gs, 0.975)), 4)]}
    res["gain_pearson"] = round(res["tracker_avg"]["pearson"] - res["tracker_market_only"]["pearson"], 4)
    res["gain_spearman"] = round(res["tracker_avg"]["spearman"] - res["tracker_market_only"]["spearman"], 4)
    day = (st - VAL0) // 86400
    res["per_day_pearson_avg"] = {int(d): round(float(np.corrcoef(ra[day == d], wp[day == d])[0, 1]), 4) for d in np.unique(day)}
    res["per_day_pearson_market_only"] = {int(d): round(float(np.corrcoef(rm[day == d], wp[day == d])[0, 1]), 4) for d in np.unique(day)}
    print(json.dumps(res, indent=1))
    json.dump(res, open(f"{R}/trkgain12.json", "w"), indent=1)


if __name__ == "__main__":
    main()
