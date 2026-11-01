"""Iteration 12: EXPOSURE-TRACKER replica (pre-registered in NOTES.md iteration 12, 00:20 UTC) on VALIDATE, offline from the
frozen it4b per-second netflow predictions (val_outcome_it4b.parquet: nf, ask_u, ask_d per (cid, rel), PIT) and the
rebuilt data-api taker tapes (tapes12.py). Strict fills against other traders' taker BUY prints only.
Usage: python track12.py TAPE_DIR [variant ...]"""
import os, sys, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
VAL0, H = 1792108800, 1792713600
FEE = 0.07
CL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
if os.environ.get("TRK_EXCL_W45"):  # check: also drop the operator's fourth / fifth wallets (W4, W5) from the fill liquidity
    CL = CL | {"0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}
VARIANTS = {  # name: (lot, slack, lo, hi (print window rel to s), step to next decision, capture, exclude cluster-maker txs)
    "trk_a": (10, 0.02, 1, 3, 4, 1.0, True), "trk_b": (10, 0.02, 0, 2, 3, 1.0, True),
    "trk_a_s0": (10, 0.0, 1, 3, 4, 1.0, True), "trk_a_s01": (10, 0.01, 1, 3, 4, 1.0, True), "trk_a_s05": (10, 0.05, 1, 3, 4, 1.0, True),
    "trk_a_lot5": (5, 0.02, 1, 3, 4, 1.0, True), "trk_a_lot30": (30, 0.02, 1, 3, 4, 1.0, True),
    "trk_a_cap05": (10, 0.02, 1, 3, 4, 0.5, True), "trk_a_keepmk": (10, 0.02, 1, 3, 4, 1.0, False),
}


def run(win, vo, tapes, mk_tx, var):
    lot, slack, lo, hi, step, cap, excl = var
    rows = []; fin = {}
    for cid, g in vo.groupby("cid", sort=False):
        if cid not in tapes:
            continue
        st0, pay_up = win.at[cid, "start_ts"], win.at[cid, "up_payout"]
        nf = g.nf.to_numpy(float); au = g.ask_u.to_numpy(float); ad = g.ask_d.to_numpy(float); rel = g.rel.to_numpy(np.int64)
        tgt = np.cumsum(np.nan_to_num(nf))
        P = tapes[cid]
        if excl:
            P = {o: tuple(a[~m] for a in arr) for o, (arr, m) in ((o, (P[o][:3], P[o][3])) for o in (True, False))}
        else:
            P = {o: P[o][:3] for o in (True, False)}
        Rn = 0.0; nxt = 0
        for i in range(len(rel)):
            s = rel[i]
            if s < nxt:
                continue
            d = tgt[i] - Rn
            if abs(d) < lot:
                continue
            o = d > 0
            a = au[i] if o else ad[i]
            if not (np.isfinite(a) and 0.05 < a < 0.95):
                continue
            lim = min(a + slack, 0.99)
            q = np.floor(abs(d) / lot) * lot
            Rr, Pp, Zz = P[o]
            k0, k1 = np.searchsorted(Rr, s + lo, "left"), np.searchsorted(Rr, s + hi, "right")
            left = q; pay = pay_up if o else 1 - pay_up
            for k in range(k0, k1):
                if Pp[k] <= lim + 1e-9:
                    sh = min(left, cap * Zz[k]); left -= sh
                    if sh > 0:
                        rows.append((cid, o, Pp[k], sh, sh * (pay - Pp[k]) - FEE * Pp[k] * (1 - Pp[k]) * sh))
                        Rn += sh if o else -sh
                    if left <= 1e-9:
                        break
            nxt = s + step
        fin[cid] = (Rn, tgt[-1])
    T = pd.DataFrame(rows, columns=["cid", "up", "price", "shares", "pnl"])
    return T, fin


def main():
    tape_dir = sys.argv[1]
    names = sys.argv[2:] or list(VARIANTS)
    win = pd.read_parquet(f"{C}/windows.parquet").set_index("cid")
    vo = pd.read_parquet(f"{C}/val_outcome_it4b.parquet").sort_values(["cid", "rel"])
    TGT = os.environ.get("TRK_TARGET", "nf")  # nf (it4b netflow, pre-registered primary) | avg (0.5 (nf + nf12b)) | nf12b
    if TGT != "nf":
        nb = pd.read_parquet(f"{C}/it12/nf12b_val.parquet")[["cid", "rel", "nf12b"]]
        vo = vo.merge(nb, on=["cid", "rel"], how="left").sort_values(["cid", "rel"])
        if TGT == "ens3":  # pre-registration 3: (nf_it4b + nf12b + nf12c) / 3
            nc = pd.read_parquet(f"{C}/it12/nf12c_val.parquet")[["cid", "rel", "nf12c"]]
            vo = vo.merge(nc, on=["cid", "rel"], how="left").sort_values(["cid", "rel"])
            vo["nf"] = (vo.nf + vo.nf12b.fillna(0) + vo.nf12c.fillna(0)) / 3.0
        elif TGT == "mkt":  # co-occurrence check: market-activity-only net-flow model (no spot / venue input)
            nm_ = pd.read_parquet(f"{C}/it12/nf12m_val.parquet")[["cid", "rel", "nf12m"]]
            vo = vo.merge(nm_, on=["cid", "rel"], how="left").sort_values(["cid", "rel"])
            vo["nf"] = vo.nf12m.fillna(0)
        else:
            vo["nf"] = 0.5 * (vo.nf + vo.nf12b.fillna(0)) if TGT == "avg" else vo.nf12b.fillna(0)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "shares", "price", "fee_usd", "cid", "start_ts", "is_up", "up_payout"])
    fl = fl[fl.start_ts >= VAL0]
    mk_tx = set(fl.loc[fl.role == "M", "tx"].str.lower())
    t0 = time.time(); tapes = {}; parts = []
    for cid in vo.cid.unique():
        p = f"{tape_dir}/{cid}.parquet"
        if os.path.exists(p):
            d = pd.read_parquet(p, columns=["proxyWallet", "side", "size", "price", "timestamp", "outcome", "transactionHash"])
            if len(d):
                parts.append(d.assign(cid=cid))
    A = pd.concat(parts, ignore_index=True); del parts
    A = A[(A.side == "BUY") & ~A.proxyWallet.str.lower().isin(CL)]
    A["rel"] = A.timestamp - win.loc[A.cid, "start_ts"].to_numpy()
    A = A[(A.rel >= -2) & (A.rel <= 305)]
    A["mk"] = A.transactionHash.str.lower().isin(mk_tx)
    A["up"] = A.outcome == "Up"
    A = A.sort_values(["cid", "up", "rel"], kind="stable")
    for (cid, o), dd in A.groupby(["cid", "up"], sort=False):
        tapes.setdefault(cid, {True: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool)), False: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool))})
        tapes[cid][bool(o)] = (dd.rel.to_numpy(np.int64), dd.price.to_numpy(float), dd["size"].to_numpy(float), dd.mk.to_numpy())
    print("tapes", len(tapes), round(time.time() - t0, 1), flush=True)
    fl["pay"] = np.where(fl.is_up, fl.up_payout, 1 - fl.up_payout)
    fl["pnl"] = fl.shares * (fl.pay - fl.price) - fl.fee_usd
    fl["sg"] = np.where(fl.is_up, 1.0, -1.0) * fl.shares
    cids = vo.cid.unique()
    W = {w: fl[fl.wallet == w].groupby("cid").pnl.sum().reindex(cids).fillna(0) for w in ("GF", "XM", "DS")}
    W["pool"] = fl.groupby("cid").pnl.sum().reindex(cids).fillna(0)
    NET = fl.groupby("cid").sg.sum().reindex(cids).fillna(0)
    blocks = (win.loc[cids, "start_ts"].to_numpy() // 7200)
    out = {}
    for nm in names:
        t1 = time.time()
        T, fin = run(win, vo, tapes, mk_tx, VARIANTS[nm])
        rp = T.groupby("cid").pnl.sum().reindex(cids).fillna(0)
        rn = pd.Series({k: v[0] for k, v in fin.items()}).reindex(cids).fillna(0)
        tg = pd.Series({k: v[1] for k, v in fin.items()}).reindex(cids).fillna(0)
        r = {"fills": int(len(T)), "usd": round(float((T.price * T.shares).sum()), 1), "pnl_before_rebates": round(float(T.pnl.sum()), 1),
             "fee_usd": round(float((FEE * T.price * (1 - T.price) * T.shares).sum()), 1)}
        r["return_before_rebates"] = round(r["pnl_before_rebates"] / r["usd"], 4) if r["usd"] else None
        r["return_with_50pct_fee_rebate"] = round((r["pnl_before_rebates"] + 0.5 * r["fee_usd"]) / r["usd"], 4) if r["usd"] else None
        r["corr_realized_net_target_net"] = round(float(rn.corr(tg)), 4)
        r["corr_realized_net_wallet_net"] = round(float(rn.corr(NET)), 4)
        for w, wp in W.items():
            r[f"pnl_corr_{w}"] = {"pearson": round(float(rp.corr(wp)), 4), "spearman": round(float(rp.corr(wp, method="spearman")), 4)}
        # 2-h block bootstrap of the pooled Pearson
        rng = np.random.default_rng(12); ub = np.unique(blocks); bidx = {b: np.where(blocks == b)[0] for b in ub}
        bs = []
        x, y = rp.to_numpy(), W["pool"].to_numpy()
        for _ in range(1000):
            ii = np.concatenate([bidx[b] for b in rng.choice(ub, len(ub))])
            bs.append(np.corrcoef(x[ii], y[ii])[0, 1])
        r["pnl_corr_pool_pearson_block_ci95"] = [round(float(np.quantile(bs, 0.025)), 4), round(float(np.quantile(bs, 0.975)), 4)]
        half = win.loc[cids, "start_ts"].to_numpy() < (VAL0 + H) // 2
        r["pnl_corr_pool_halves"] = [round(float(np.corrcoef(x[m], y[m])[0, 1]), 4) for m in (half, ~half)]
        r["elapsed_s"] = round(time.time() - t1, 1)
        out[nm] = r
        print(nm, json.dumps(r), flush=True)
    json.dump(out, open(f"{R}/track12{'' if TGT == 'nf' else '_' + TGT}{'_exclW45' if os.environ.get('TRK_EXCL_W45') else ''}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
