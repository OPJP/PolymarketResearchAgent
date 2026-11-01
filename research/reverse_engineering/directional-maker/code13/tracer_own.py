"""X135 law (d) and X139 (P5) check: the tracer against the wallet's own state at the re-sign (OWN STATE; development
block 10-31 12-18). Own state from the wallet's data-api activity (TRADE rows, block seconds; a fill counts from its
block second + 1). Laws: (d) cost lock min(1 - vwap_held - m, ask - 0.01); (a+d) min(F_own(L=1250 ms) - h,
1 - vwap_held - m, ask - 0.01); size check: tracer size vs the wallet's |imbalance| just before the re-sign."""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(HERE))
import cl_source
from tracer_laws import spot, snap, score, cap
OUT = ROOT / ".cache/re/directional-maker/it13"
W = {"0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
     "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona"}
R = pd.read_parquet(OUT / "tracer_features.parquet")
R = R[R.side_ok & R.bid_ex.notna() & R.ask.notna() & R.K.notna()].copy()
orders = R.groupby("order").fill_ms.first().sort_values()
R["fit"] = R.order.isin(set(orders.index[: len(orders) // 2]))
L = 1250
clv = cl_source.cl_values(sorted(set(((R.s - L) // 1000).astype(int))), allow_sealed=False, fetch=True, max_requests=200)
cl = ((R.s - L) // 1000).map(clv).to_numpy(float)
sp = spot(int(R.s.min() // 1000) - 7200, int(R.s.max() // 1000) + 5)
s300 = sp.sigma((R.s // 1000).to_numpy(), look=300)
fu = norm.cdf(np.log(cl / R.K.to_numpy(float)) / (1.4 * s300 * np.sqrt(R.tau.to_numpy())))
R["F2"] = np.where(R.is_up == 1, fu, 1 - fu)
fs = sorted(glob.glob(str(ROOT / ".cache/re/directional-maker/live_activity_17934*.parquet")))
A = pd.concat([pd.read_parquet(f) for f in fs]).drop_duplicates(["transactionHash", "asset", "side", "size", "price", "w"])
A = A[(A.type == "TRADE") & A.slug.isin(set(R.w))].copy()
A["wallet"] = A.w.map(lambda x: x if x in W.values() else W.get(str(x).lower(), x))
A["isup"] = (A.outcome.astype(str).str.lower() == "up")
A["sgn"] = np.where(A.side == "BUY", 1.0, -1.0)
rows = []
for (wal, slug), g in R.groupby(["wallet", "w"]):
    a = A[(A.wallet == wal) & (A.slug == slug)].sort_values("timestamp")
    ta = a.timestamp.to_numpy() + 1
    for idx, r in g.iterrows():
        m = ta * 1000 <= r.s
        b = a[m]
        up_sh = (b.sgn * b["size"] * b.isup).sum(); dn_sh = (b.sgn * b["size"] * ~b.isup).sum()
        held_up = up_sh > dn_sh
        hb = b[(b.isup == held_up) & (b.side == "BUY")]
        vw = (hb.price * hb["size"]).sum() / hb["size"].sum() if hb["size"].sum() > 0 else np.nan
        rows.append((idx, up_sh - dn_sh, vw, int(held_up)))
O = pd.DataFrame(rows, columns=["idx", "imb", "vwap_held", "held_up"]).set_index("idx")
R = R.join(O)
R["under_ok"] = ((R.imb > 0) & (R.is_up == 0)) | ((R.imb < 0) & (R.is_up == 1))
R["size_match"] = (np.abs(np.abs(R.imb) - R["size"]) <= 0.02)
out = {"n": int(len(R)), "share_on_under_held_outcome": float(R.under_ok.mean()), "share_size_equals_wallet_imbalance": float(R.size_match.mean()),
       "share_size_within_1pct": float((np.abs(np.abs(R.imb) - R["size"]) <= 0.01 * R["size"]).mean())}
F, T = R[R.fit & R.vwap_held.notna()], R[~R.fit & R.vwap_held.notna()]
def grid(fn, G, X):
    b = None
    for g in G:
        s = score(fn(X, g), X.p_own)["within_tick"]
        if b is None or s > b[1]: b = (g, s)
    return b
fd = lambda X, m: cap(1 - X.vwap_held - m, X.ask)
md, _ = grid(fd, np.arange(-0.10, 0.40, 0.005), F)
out["d_cost_lock"] = {"m": float(md), "fit": score(fd(F, md), F.p_own), "test": score(fd(T, md), T.p_own)}
best = None
for h in np.arange(-0.10, 0.30, 0.01):
    for m in np.arange(-0.05, 0.30, 0.01):
        s = score(np.minimum(cap(F.F2 - h, F.ask), snap(1 - F.vwap_held - m)), F.p_own)["within_tick"]
        if best is None or s > best[2]: best = (h, m, s)
h_, m_ = best[0], best[1]
fad = lambda X: np.minimum(cap(X.F2 - h_, X.ask), snap(1 - X.vwap_held - m_))
out["a_plus_d"] = {"h": float(h_), "m": float(m_), "fit": score(fad(F), F.p_own), "test": score(fad(T), T.p_own)}
fa = lambda X, h: cap(X.F2 - h, X.ask)
ha, _ = grid(fa, np.arange(-0.10, 0.40, 0.005), F)
out["a_L1250_same_rows"] = {"h": float(ha), "test": score(fa(T, ha), T.p_own)}
# which constraint binds and how close the price is to each
R["lock"] = 1 - R.vwap_held
out["pair_cost_at_resign_q"] = np.nanpercentile(R.p_own + R.vwap_held, [10, 25, 50, 75, 90]).round(3).tolist()
out["pair_cost_at_fill_q"] = np.nanpercentile((R.lim + R.vwap_held)[R.j == R.n_adds - 1], [10, 25, 50, 75, 90]).round(3).tolist()
print(json.dumps(out, indent=1, default=float))
(HERE.parent / "results/iter13_tracer_own.json").write_text(json.dumps(out, indent=1, default=float))
R.to_parquet(OUT / "tracer_features_own.parquet", index=False)
