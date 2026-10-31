"""Size/power of match_test's spot-clock-shift null, using synthetic wallets.

H0 wallets pick prints using ONLY the print price (no spot information at all),
so a valid test must give roughly uniform p-values. H1 wallet picks prints using
the spot-model edge at latency 2 s (the exact LA rule family) plus a mild
preference for cheap prices.

Compared with an alternative null that (i) shifts the spot clock by whole
5-minute windows *within the same loaded 2-hour block* (so every shifted score is
finite) and (ii) uses a price-stratified AUC (within each 1-cent price bucket), so
the price term cannot leak into the statistic.
"""
import pickle
from pathlib import Path
import numpy as np, pandas as pd
from polyrea.analysis.updown import SpotIndex, score_prints, auc, match_test, fair_up_vectorized

D = pickle.load(open(Path(__file__).parent / "data" / "btc5m.pkl", "rb"))
spot = SpotIndex(D["spot_ts"])
fitp, testp = D["fit"]["prints"].copy(), D["test"]["prints"].copy()
blocks = np.array(D["test_blocks"])


def strat_auc(s, y, pb):
    ok = np.isfinite(s)
    df = pd.DataFrame({"s": s[ok], "y": y[ok], "pb": pb[ok]})
    df["r"] = df.groupby("pb")["s"].rank()
    g = df.groupby("pb").agg(n1=("y", "sum"), n=("y", "size"))
    r1 = df[df.y == 1].groupby("pb")["r"].sum()
    g = g.join(r1.rename("r1")).fillna(0)
    g["n0"] = g["n"] - g["n1"]
    g = g[(g.n1 > 0) & (g.n0 > 0)]
    U = (g.r1 - g.n1 * (g.n1 + 1) / 2).sum()
    return float(U / (g.n1 * g.n0).sum())


def within_block_scores(p, lat, k):
    st = p["start_ts"].to_numpy(); en = p["end_ts"].to_numpy(); t = p["ts"].to_numpy() - lat
    bi = np.searchsorted(blocks[:, 0], st, side="right") - 1
    a = blocks[bi, 0]
    new_start = a + (st - a + 300 * k) % 7200
    sh = new_start - st
    fu = fair_up_vectorized(spot, st + sh, en + sh, t + sh, 60)
    fs = np.where(p["is_up"].to_numpy(), fu, 1 - fu)
    return fs - p["price"].to_numpy()


def alt_test(p, y, lat, n=23):
    pb = np.round(p["price"].to_numpy(), 2)
    obs = strat_auc(score_prints(p, spot, lat), y, pb)
    null = np.array([strat_auc(within_block_scores(p, lat, k), y, pb) for k in range(1, n + 1)])
    fin = np.mean([np.isfinite(within_block_scores(p, lat, k)).mean() for k in (1, 7, 13)])
    return obs, null, (1 + (null >= obs).sum()) / (1 + len(null)), fin


def run(name, wallet_col_fit, wallet_col_test, n_perm=200):
    f, t = fitp.assign(wallet=wallet_col_fit), testp.assign(wallet=wallet_col_test)
    mt = match_test(f, t, "0xsyn" if name != "real" else REAL, spot, n_perm=n_perm, seed=7)
    w = "0xsyn" if name != "real" else REAL
    y = (t["wallet"] == w).to_numpy().astype(int)
    obs, null, p_alt, fin = alt_test(t, y, mt["chosen_latency_s"])
    te = mt["test"]
    print(f"{name:28s} code: lat={mt['chosen_latency_s']:>2} AUC={te['auc']:.4f} null_mean={te['auc_null_mean']:.4f} perm_p={te['auc_perm_p']:.3f} | "
          f"alt(within-block shift, price-stratified AUC): obs={obs:.4f} null_mean={null.mean():.4f} null_max={null.max():.4f} p={p_alt:.3f} finite={fin:.3f}")


rng = np.random.default_rng(123)
def syn(p, prob):
    sel = rng.random(len(p)) < prob
    return np.where(sel, "0xsyn", p["wallet"].to_numpy()), sel

REAL = "0xc53375ff94e96100f2b30a4b5775db35218d69a9"
for name, fn in [
    ("H0 uniform 2%", lambda p: np.full(len(p), 0.02)),
    ("H0 prefers cheap (1-p)^3", lambda p: 0.06 * (1 - p["price"].to_numpy()) ** 3),
    ("H0 prefers expensive p^3", lambda p: 0.06 * p["price"].to_numpy() ** 3),
    ("H0 prefers mid-price", lambda p: 0.08 * np.exp(-((p["price"].to_numpy() - 0.5) / 0.12) ** 2)),
]:
    wf, _ = syn(fitp, fn(fitp)); wt, sel = syn(testp, fn(testp))
    run(name, wf, wt)

# H1: the LA rule at latency 2 s (uses the spot edge) + cheap preference
def h1(p):
    s = score_prints(p, spot, 2)
    s = np.nan_to_num(s, nan=-1)
    return 0.05 * (1 - p["price"].to_numpy()) ** 2 * (s > 0.03)
wf, _ = syn(fitp, h1(fitp)); wt, _ = syn(testp, h1(testp))
run("H1 edge>0.03 @2s + cheap", wf, wt)
run("real", fitp["wallet"].to_numpy(), testp["wallet"].to_numpy())
REAL = "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6"
run("real", fitp["wallet"].to_numpy(), testp["wallet"].to_numpy())
