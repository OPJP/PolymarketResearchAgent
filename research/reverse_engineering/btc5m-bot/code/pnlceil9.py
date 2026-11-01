"""Iteration 9 (panel iter8 assumptions P3, strong form of X17 / X28): the PnL condition's TEST-RETEST CEILING under a race
lottery, on VALIDATE (2026-10-16 .. 10-23, development).

Model: the operator makes a set of decisions D_w in window w (each with its side, price and size: x_d = the PnL the decision
earns if it fills: shares x (payout - price) - fee + 0.5 fee rebate); each decision fills independently with probability q
(the race). The wallet's observed orders O_w are one q-thinning of D_w; a replay (the true rule run again, e.g. by the
examiner's strict-fill replica with the TRUE decisions) is another. Then, exactly (no distributional assumption):
    Cov(R1, R2) = Var_w(q S_w),  Var(R) = Var_w(q S_w) + (1 - q) E_w[sum_{d in O_w} x_d^2]
so   r(replay, replay) = r(replay, actual) = 1 - (1 - q) * kappa,   kappa = E_w[sum_O x_d^2] / Var_w(O_w).
This is an UPPER bound for the true rule: the own-state size overlay (the size depends on the operator's own fills) adds
replay variance. q is measured on the live book (ins9b.py: decisions per filled order). Also reported: the empirical split-half
correlation (random halves of each window's orders) vs its model prediction (1 - kappa) / (1 + kappa), and 2-h block
bootstrap intervals. Spearman is reported for the Gaussian-copula approximation rho_s = (6 / pi) asin(r / 2).
Usage: python pnlceil9.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd

C = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", ".cache", "re", "btc5m-bot"))
VAL = (1792108800, 1792713600)
QS = (0.5, 0.6, 0.7, 0.8, 0.9)


def order_pnl():
    f = pd.read_parquet(C + "/fills.parquet", columns=["oh", "wallet", "role", "shares", "price", "fee_usd", "start_ts", "is_up", "up_payout"])
    f = f[(f.start_ts >= VAL[0]) & (f.start_ts < VAL[1])].copy()
    won = np.where(f.is_up, f.up_payout, 1 - f.up_payout)
    f["x"] = f.shares * (won - f.price) - f.fee_usd + 0.5 * f.fee_usd * (f.role == "T")
    o = f.groupby(["oh"], sort=False).agg(wallet=("wallet", "first"), w=("start_ts", "first"), x=("x", "sum"), sh=("shares", "sum")).reset_index()
    return o


def kappa_stats(o, by_wallet=None):
    g = o if by_wallet is None else o[o.wallet == by_wallet]
    per = g.groupby("w").agg(O=("x", "sum"), S2=("x", lambda v: float(np.sum(np.square(v)))), n=("x", "size"))
    return per


def ceiling(per):
    var = float(per.O.var(ddof=1)); es2 = float(per.S2.mean())
    kap = es2 / var
    out = {"windows": int(len(per)), "orders_per_window": round(float(per.n.mean()), 1), "kappa": round(kap, 4),
           "split_half_pred": round((1 - kap) / (1 + kap), 4),
           "r_ceiling": {str(q): round(1 - (1 - q) * kap, 4) for q in QS},
           "spearman_gauss": {str(q): round(6 / np.pi * np.arcsin(max(-1, min(1, 1 - (1 - q) * kap)) / 2), 4) for q in QS},
           "q_needed_for_r_0.5": round(1 - 0.5 / kap, 4) if kap > 0 else None}
    return out


def split_half(o, wallet=None, draws=40, seed=1):
    g = o if wallet is None else o[o.wallet == wallet]
    rng = np.random.default_rng(seed)
    rs = []
    w = g.w.to_numpy(); x = g.x.to_numpy()
    uw, inv = np.unique(w, return_inverse=True)
    for _ in range(draws):
        h = rng.random(len(x)) < 0.5
        A = np.bincount(inv, weights=x * h, minlength=len(uw)); B = np.bincount(inv, weights=x * ~h, minlength=len(uw))
        rs.append(np.corrcoef(A, B)[0, 1])
    return round(float(np.mean(rs)), 4)


def boot(per, q, n=2000, seed=7):
    blk = (per.index.to_numpy() // 7200).astype(np.int64)
    ub, inv = np.unique(blk, return_inverse=True)
    rng = np.random.default_rng(seed)
    O = per.O.to_numpy(); S2 = per.S2.to_numpy()
    vals = []
    for _ in range(n):
        pick = rng.integers(0, len(ub), len(ub))
        idx = np.concatenate([np.where(inv == p)[0] for p in pick])
        var = O[idx].var(ddof=1)
        vals.append(1 - (1 - q) * S2[idx].mean() / var)
    return [round(float(x), 4) for x in np.percentile(vals, [2.5, 50, 97.5])]


def main(out):
    o = order_pnl()
    res = {"orders": int(len(o)), "unit": "VALIDATE window x (pooled cluster | wallet)", "pooled": {}, "by_wallet": {}}
    per = kappa_stats(o)
    res["pooled"] = ceiling(per)
    res["pooled"]["split_half_emp"] = split_half(o)
    res["pooled"]["boot_r_q0.61"] = boot(per, 0.61); res["pooled"]["boot_r_q0.70"] = boot(per, 0.70)
    for wl in ("DS", "GF", "XM"):
        pw = kappa_stats(o, wl)
        res["by_wallet"][wl] = ceiling(pw)
        res["by_wallet"][wl]["split_half_emp"] = split_half(o, wl)
        res["by_wallet"][wl]["boot_r_q0.61"] = boot(pw, 0.61)
    # the large-order share of the variance: kappa with orders >= 90 shares removed (what a 30-share replica could reach)
    small = o[o.sh < 90]
    res["pooled_small_orders_only"] = ceiling(kappa_stats(small))
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
