"""Iteration 15 pivot, oracle steps (mechanics P1 step 1 = X140; information P5 step 2-3 = X144): is the operator's realized taker
size the visible ask depth at or below its limit?

Inputs: l2ingest15 outputs (ask vectors at m - 1 / m - 150 / m - 180 for every operator taker order with a capture match ms), the
calldata sample (original size and limit of the taker orders of the sample hours), dcfit14_pred (frozen dc14 side probability of
10-20..22), fills.parquet (window net N over both roles, window PnL).
A. calldata orders: filled taker shares vs min(orig, D<=L(t)) for t = m - 1, m - 150, m - 180.
B. oracle ladder on the true decision record (windows of the ingested days): r(N) and PnL r of sum side x size for size in
   {true total fill (osz), true taker-step fill, public menu E[menu | wallet], min(E-menu, D<=L(t)), E[min(menu, D<=L(t))], D<=L(t)},
   with L = best ask at the bot's view (m - 180) + k_w (wallet pay-up from the fit-day calldata hours), side = dc14 probability
   (2p - 1) or the true side.
Usage: python -I depth15.py IT15_DIR IT14_DIR OUT.json DAY [DAY ...]"""
import sys, json
import numpy as np, pandas as pd
from scipy.stats import pearsonr, spearmanr

D15, D14, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DAYS = sys.argv[4:]
C = ".cache/re/btc5m-bot"
FIT_LO, FIT_HI = 1792195200, 1792454400  # 10-17..19 (fit days for every constant here)


def dle(vec, L):
    """cumulative ask size at cent levels <= L (vec: (n, 101); L: (n,) int cents)."""
    cs = np.cumsum(vec, 1)
    L = np.clip(L, 0, 100).astype(np.int64)
    return cs[np.arange(len(L)), L]


def best(vec):
    pos = vec[:, 1:] > 0
    return np.where(pos.any(1), pos.argmax(1) + 1, 0)


def main():
    rep = {"days": DAYS}
    od, ov = [], []
    for day in DAYS:
        od.append(pd.read_parquet(f"{D15}/l2ord_{day}.parquet")); ov.append(np.load(f"{D15}/l2ord_{day}.npy"))
    od = pd.concat(od, ignore_index=True); ov = np.concatenate(ov)
    od["b180"] = best(ov[:, 2]); od["b150"] = best(ov[:, 1]); od["b1"] = best(ov[:, 0])
    od["tx_l"] = od.tx.str.lower()
    # calldata taker orders: original size and limit
    cd = pd.read_parquet(f"{C}/calldata_sample.parquet", columns=["tx", "role", "maker", "token", "maker_amt", "taker_amt", "sign_ms"])
    W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
    cd["wallet"] = cd.maker.str.lower().map(W)
    cd = cd[(cd.role == "T") & cd.wallet.notna()].copy()
    cd["orig"] = cd.taker_amt.astype(float); cd["L"] = np.round(cd.maker_amt.astype(float) / cd.taker_amt.astype(float) * 100).astype(int)
    cd["tx_l"] = cd.tx.str.lower(); cd["token"] = cd.token.astype(str)
    od["token"] = od.token.astype(str)
    # wallet pay-up k_w on the fit days' calldata hours (limit - best ask at the bot's view); needs the fit days' books -> fall back to
    # the iteration-13/14 measured medians if those days are not ingested
    j = od.merge(cd[["tx_l", "wallet", "token", "orig", "L", "sign_ms"]], on=["tx_l", "wallet", "token"], how="left")
    od["orig"] = j.orig.to_numpy(); od["Lcd"] = j.L.to_numpy()
    fitj = od[(od.start_ts >= FIT_LO) & (od.start_ts < FIT_HI) & od.Lcd.notna() & (od.b180 > 0)]
    if len(fitj) > 200:
        kw = (fitj.Lcd - fitj.b180).groupby(fitj.wallet).median().to_dict(); kw_src = "fit-day calldata"
    else:
        kw = {"DS": 0, "GF": 1, "XM": 1}; kw_src = "iteration-13 finding 12 medians (DS ~0, GF ~1 c, XM 1-3 c), rounded"
    rep["k_w"] = {k: float(v) for k, v in kw.items()}; rep["k_w_source"] = kw_src
    od["Lpub"] = (od.b180 + od.wallet.map(kw).fillna(1)).clip(1, 99)
    for t, ix in (("m1", 0), ("m150", 1), ("m180", 2)):
        od[f"Dpub_{t}"] = dle(ov[:, ix], od.Lpub.to_numpy())
        lc = od.Lcd.fillna(0).astype(int).to_numpy()
        od[f"Dcd_{t}"] = np.where(od.Lcd.notna(), dle(ov[:, ix], lc), np.nan)
    # ---- A. calldata orders
    a = od[od.orig.notna()].copy()
    A = {"n": int(len(a)), "share_depth_bound": float((a.shares < a.orig - 1e-6).mean()) if len(a) else None}
    for t in ("m1", "m150", "m180"):
        pred = np.minimum(a.orig, a[f"Dcd_{t}"])
        db = a.shares < a.orig - 1e-6
        within = (np.abs(a.shares - pred) <= 0.1 * np.maximum(pred, 1))
        A[t] = {"r_filled_pred": float(pearsonr(a.shares, pred)[0]) if len(a) > 10 else None,
                "within10_all": float(within.mean()), "within10_depth_bound": float(within[db].mean()) if db.any() else None,
                "pred_ge_filled_share": float((pred >= a.shares - 1e-6).mean()),
                "median_D_depth_bound": float(a.loc[db, f"Dcd_{t}"].median()) if db.any() else None,
                "large_r": float(pearsonr(a.shares[a.orig >= 90], pred[a.orig >= 90])[0]) if (a.orig >= 90).sum() > 10 else None}
        # how much depth was there at the bot's view vs filled for depth-bound orders
    a["lim_minus_best180"] = a.Lcd - a.b180
    A["limit_minus_best180_by_wallet"] = a.groupby("wallet").lim_minus_best180.describe()[["count", "mean", "50%"]].round(3).to_dict()
    A["Lpub_eq_Lcd"] = float((a.Lpub == a.Lcd).mean()) if len(a) else None
    rep["A_calldata"] = A
    # ---- B. oracle ladder on the true decision record
    p = pd.read_parquet(f"{D14}/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "osz", "start_ts", "p_dc14_spot_own"])
    od2 = od.merge(p, on=["cid", "wallet", "m"], how="inner", suffixes=("", "_p"))
    rep["B_orders_joined"] = int(len(od2)); rep["B_orders_l2"] = int(len(od))
    od2["sg"] = np.where(od2.is_up, 1.0, -1.0); od2["ps"] = 2 * od2.p_dc14_spot_own - 1
    # public menu: E[size] and P(large) by wallet from the fit days' calldata (orig sizes)
    cdf = cd.merge(pd.read_parquet(f"{C}/calldata_sample_txs.parquet").assign(tx_l=lambda x: x.tx.str.lower())[["tx_l", "ts"]], on="tx_l", how="left")
    cdf = cdf[(cdf.ts >= FIT_LO) & (cdf.ts < FIT_HI)]
    big = cdf.orig >= 90
    pl = big.groupby(cdf.wallet).mean().to_dict(); emenu = cdf.groupby("wallet").orig.mean().to_dict()
    # on 10-19..22 the menu is (30, 100)
    rep["menu_fit"] = {"P_large": {k: round(v, 4) for k, v in pl.items()}, "E_menu": {k: round(v, 2) for k, v in emenu.items()}, "n_fit_orders": int(len(cdf))}
    od2["Emenu"] = od2.wallet.map(lambda w: 30 * (1 - pl.get(w, 0.2)) + 100 * pl.get(w, 0.2))
    for t in ("m1", "m150", "m180"):
        D = od2[f"Dpub_{t}"]
        od2[f"minE_{t}"] = np.minimum(od2.Emenu, D)
        od2[f"Emin_{t}"] = (1 - od2.wallet.map(pl).fillna(0.2)) * np.minimum(30, D) + od2.wallet.map(pl).fillna(0.2) * np.minimum(100, D)
        od2[f"D_{t}"] = D
    f = pd.read_parquet(f"{C}/fills.parquet", columns=["wallet", "role", "is_up", "shares", "price", "fee_usd", "start_ts", "up_payout"])
    f = f[f.start_ts.isin(od2.start_ts.unique())].copy()
    f["sgs"] = np.where(f.is_up, 1.0, -1.0) * f.shares
    f["pay"] = np.where(f.is_up, f.up_payout, 1 - f.up_payout); f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd
    Wn = f.groupby("start_ts").agg(N=("sgs", "sum"), pnl=("pnl", "sum"), up=("up_payout", "first"))
    Wn_w = f.groupby(["wallet", "start_ts"]).agg(N=("sgs", "sum"), pnl=("pnl", "sum"), up=("up_payout", "first"))
    sizes = {"osz_true_total": "osz", "taker_step_true": "shares", "Emenu_public": "Emenu", "unit": None,
             "minE_m1": "minE_m1", "minE_m150": "minE_m150", "minE_m180": "minE_m180", "Emin_m1": "Emin_m1", "Emin_m180": "Emin_m180",
             "D_m180": "D_m180", "D_m1": "D_m1"}
    B = {}
    for side in ("ps", "sg"):
        for nm, col in sizes.items():
            x = od2[side] * (od2[col] if col else 1.0)
            agg = x.groupby(od2.start_ts).sum()
            J = Wn.join(agg.rename("x"), how="inner").fillna(0); J["o"] = J.up - 0.5
            r = {"rN": round(float(pearsonr(J.x, J.N)[0]), 4), "pnlP": round(float(pearsonr(J.x * J.o, J.pnl)[0]), 4), "pnlS": round(float(spearmanr(J.x * J.o, J.pnl)[0]), 4), "n": int(len(J))}
            for w in ("DS", "GF", "XM"):
                xw = x[od2.wallet == w].groupby(od2.start_ts[od2.wallet == w]).sum()
                Jw = Wn_w.loc[w].join(xw.rename("x"), how="left").fillna(0); Jw["o"] = Jw.up - 0.5
                r[w] = {"rN": round(float(pearsonr(Jw.x, Jw.N)[0]), 4), "pnlP": round(float(pearsonr(Jw.x * Jw.o, Jw.pnl)[0]), 4)}
            B[f"{side}|{nm}"] = r
    rep["B_ladder"] = B
    # depth-bound diagnostics on all joined orders
    db = od2.shares < od2.Emenu
    rep["B_diag"] = {"r_taker_step_vs_D_m180": float(pearsonr(od2.shares, od2.D_m180)[0]), "r_taker_step_vs_D_m1": float(pearsonr(od2.shares, od2.D_m1)[0]),
                     "r_taker_step_vs_minE_m1": float(pearsonr(od2.shares, od2.minE_m1)[0]), "r_taker_step_vs_Emin_m1": float(pearsonr(od2.shares, od2.Emin_m1)[0]),
                     "r_osz_vs_Emin_m1": float(pearsonr(od2.osz, od2.Emin_m1)[0]),
                     "median_shares": float(od2.shares.median()), "median_D_m180": float(od2.D_m180.median()), "median_D_m1": float(od2.D_m1.median()),
                     "share_best180_zero": float((od2.b180 == 0).mean())}
    od2[["start_ts", "cid", "wallet", "m", "is_up", "shares", "osz", "orig", "Lcd", "Lpub", "b180", "b1", "D_m1", "D_m150", "D_m180", "ps", "sg", "Emenu"]].to_parquet(f"{D15}/depth15_orders.parquet", index=False)
    json.dump(rep, open(OUT, "w"), indent=1)
    print(json.dumps(rep, indent=1)[:6000])


if __name__ == "__main__":
    main()
