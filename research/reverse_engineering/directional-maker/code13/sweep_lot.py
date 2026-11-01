"""Historical replication of the fill-class decomposition (X136 / X130) on the lot: a cluster maker fill is a 'sweep fill'
when another maker order in the same matchOrders transaction sits at a strictly better Up-book price on the same side
(the taker went through better levels before reaching the cluster's rung: the class-(ii) mechanism), else 'top fill'.
Up-book mapping: BUY Up at L = bid L; BUY Down at L = ask 1 - L; SELL Up at L = ask L; SELL Down at L = bid 1 - L.
Inputs: b1_all_makers_{study,valid} (calldata of every cluster fill transaction), it12/typed_fills (block clock, real
Chainlink posture). STUDY case by case allowed; VALIDATE aggregate only."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
CL = {"0x32ed2e546b187ca15e2841edc82b22c713cf8ec3", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed"}
d = pd.read_parquet(C / "it12/typed_fills.parquet")
W = pd.read_parquet(C / "exam/windows_5m.parquet", columns=["cid", "up_token"]).set_index("cid")
res = {}
for half in ("study", "valid"):
    A = pd.read_parquet(C / f"b1_all_makers_{half}.parquet", columns=["maker", "token_id", "oside", "tx", "lim", "role", "cond"])
    A = A[A.role == "maker"].copy()
    A["maker"] = A.maker.str.lower(); A["tx"] = A.tx.str.lower(); A["token_id"] = A.token_id.astype(str)
    A["cid"] = A.cond.str.lower()
    up = A.cid.map(W.up_token.astype(str))
    A = A[up.notna()].copy(); up = up[up.notna()]
    isu = A.token_id == up
    buy = A.oside == 0
    A["side_b"] = np.where(isu == buy, "bid", "ask")
    A["px"] = np.where(isu, A.lim, 1 - A.lim)
    A["is_cl"] = A.maker.isin(CL)
    best_bid = A[~A.is_cl & (A.side_b == "bid")].groupby("tx").px.max()
    best_ask = A[~A.is_cl & (A.side_b == "ask")].groupby("tx").px.min()
    c = A[A.is_cl & buy].copy()
    c["bb_o"] = c.tx.map(best_bid); c["ba_o"] = c.tx.map(best_ask)
    c["sweep"] = np.where(c.side_b == "bid", c.bb_o > c.px + 1e-9, c.ba_o < c.px - 1e-9)
    c = c.drop_duplicates(["tx", "maker", "token_id"])
    key = dict(zip(zip(c.tx, c.maker, c.token_id), c.sweep))
    t = d.copy()
    t["k"] = list(zip(t.txh.str.lower(), t.wallet.str.lower(), t.token.astype(str)))
    t["sweep"] = t.k.map(key)
    t = t[t.sweep.notna() & ((t.en - t.st) == 300) & t.mid_up.notna()].copy()
    if half == "study":
        t = t[t.st < 1793059200]
    else:
        t = t[t.st >= 1793059200]
    okc = t.cl.notna() & t.Kg.notna() & t.v300.notna() & t.tau_cl.notna()
    fu = norm.cdf(np.log(t.cl / t.Kg) / (1.4 * t.v300 * np.sqrt(np.maximum(t.tau_cl, 1.0))))
    post = np.where(okc, fu > t.mid_up, t.f_bn > t.mid_up)
    dec = (t.mid_up - 0.5).abs() > 0.4
    pub = np.where(dec, t.mid_up < 0.5, post)
    y = (t.is_up == 1).to_numpy()
    sw = t.sweep.astype(bool).to_numpy()
    nd = ~dec.to_numpy()
    r = {"fills_joined": int(len(t)), "sweep_share": float(sw.mean())}
    for nm, m in (("top", ~sw), ("sweep", sw)):
        r[nm] = {"n": int(m.sum()), "public": float((pub == y)[m].mean()), "posture_not_decided": float((post == y)[m & nd].mean()) if (m & nd).any() else None,
                 "cheaper": float(((t.mid_up < 0.5).to_numpy() == y)[m].mean())}
    r["per_wallet_sweep_share"] = {w: float(g.sweep.astype(bool).mean()) for w, g in t.groupby("w")}
    r["per_wallet_posture_top_vs_sweep"] = {w: [float((pub == y)[(t.w == w).to_numpy() & ~sw].mean()), float((pub == y)[(t.w == w).to_numpy() & sw].mean())] for w in sorted(set(t.w))}
    res[half] = r
print(json.dumps(res, indent=1))
(HERE.parent / "results/iter13_sweep_lot.json").write_text(json.dumps(res, indent=1))
