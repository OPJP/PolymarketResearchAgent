"""Iteration 4: cross-asset lead. Does the Binance ETHUSDT perpetual move explain the side of the bot, in particular in
seconds when none of the six archived BTC series moved? All VALIDATE one-sided seconds (val_side_it3s.parquet); moves are
Up-oriented log moves (bp) over windows ending at the PIT horizon (s-1)*1000 ms. Also: ETH move relative to BTC
(ETH 3-s move minus beta x BTC futures 3-s move), and the side-model residual."""
import os, sys, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
S = pd.read_parquet(f"{C}/val_side_it3s.parquet"); S["s"] = (S.start_ts + S.rel).astype(np.int64)
SER = {"F": "fut", "O": "venues/okx", "B": "venues/bybit", "S": "venues/bnspot", "Y": "venues/bybitspot", "K": "venues/okxspot",
       "E": "venues/ethfut"}


def lpf(df):
    T = df["T"].to_numpy(np.int64); lp = np.log(df.p.to_numpy())
    def f(t):
        i = np.searchsorted(T, t, side="left")
        return np.where(i > 0, lp[np.clip(i - 1, 0, None)], np.nan)
    return f


out = []
for d0, g in S.groupby(S.s // 86400 * 86400):
    g = g.copy(); te = (g.s.to_numpy(np.int64) - 1) * 1000
    for p, sub in SER.items():
        fs = [f"{C}/{sub}/{d}.parquet" for d in (d0 - 86400, d0) if os.path.exists(f"{C}/{sub}/{d}.parquet")]
        if not fs:
            for w in (1000, 2000, 3000, 5000, 10000):
                g[f"{p}{w}"] = np.nan
            continue
        df = pd.concat([pd.read_parquet(f, columns=["T", "p"]) for f in fs]).sort_values("T")
        f = lpf(df)
        for w in (1000, 2000, 3000, 5000, 10000):
            g[f"{p}{w}"] = (f(te) - f(te - w)) * 1e4
        if p == "E":
            g["E_m1"] = (f(te + 1000) - f(te)) * 1e4
        del df
    out.append(g); print(d0, len(g), flush=True)
A = pd.concat(out)
up = A.truth_up.to_numpy() == 1
st = A[[f"{p}3000" for p in "FOBSYK"]].to_numpy()
A["mx6"] = np.nanmax(np.abs(st), axis=1); A["n6"] = np.isfinite(st).sum(axis=1)
nomove = (A.mx6.to_numpy() <= 0.1) & (A.n6.to_numpy() >= 4)
res = {"n_one_sided": int(len(A)), "share_nomove": round(float(nomove.mean()), 4), "nomove_n": int(nomove.sum())}


def agree(x, mask):
    m = mask & np.isfinite(x) & (x != 0)
    if m.sum() == 0:
        return {"n": 0}
    a = float(((x[m] > 0) == up[m]).mean())
    return {"n": int(m.sum()), "agree": round(a, 4), "z": round((a - 0.5) / np.sqrt(0.25 / m.sum()), 2)}


allm = np.ones(len(A), bool)
# beta of ETH on BTC futures 3-s moves (all seconds with both finite)
x = A.F3000.to_numpy(); y = A.E3000.to_numpy(); m = np.isfinite(x) & np.isfinite(y)
beta = float(np.sum(x[m] * y[m]) / np.sum(x[m] ** 2)); res["beta_eth_on_btcfut_3s"] = round(beta, 3)
res["corr_eth_btcfut_3s"] = round(float(np.corrcoef(x[m], y[m])[0, 1]), 3)
A["Erel3000"] = A.E3000 - beta * A.F3000.fillna(0)
for nm in ["E1000", "E2000", "E3000", "E5000", "E10000", "E_m1", "Erel3000"]:
    v = A[nm].to_numpy()
    res[nm] = {"all": agree(v, allm), "nomove": agree(v, nomove),
               "nomove_eth_ge_1bp": agree(np.where(np.abs(v) >= 1.0, v, 0), nomove),
               "nomove_eth_ge_2bp": agree(np.where(np.abs(v) >= 2.0, v, 0), nomove)}
ps = A.ps.to_numpy()
res["model_acc_nomove"] = round(float(((ps[nomove] >= 0.5) == up[nomove]).mean()), 4)
v = A.E3000.to_numpy(); m2 = nomove & np.isfinite(v) & (np.abs(v) >= 1.0)
dis = (v[m2] > 0) != (ps[m2] >= 0.5)
res["E3000_ge1bp_nomove_vs_model"] = {"n": int(m2.sum()), "model_acc": round(float(((ps[m2] >= 0.5) == up[m2]).mean()), 4),
                                      "eth_acc": round(float(((v[m2] > 0) == up[m2]).mean()), 4), "disagree_n": int(dis.sum()),
                                      "eth_right_when_disagree": round(float(((v[m2] > 0) == up[m2])[dis].mean()), 4) if dis.sum() else None}
print(json.dumps(res, indent=1))
json.dump(res, open(f"{R}/results_eth_iter4.json", "w"), indent=1)
A[["cid", "rel", "start_ts", "truth_up", "yT_one", "ps", "mx6", "n6", "E1000", "E2000", "E3000", "E5000", "F3000", "F2000", "O3000", "B3000", "S3000", "Y3000", "K3000"]].to_parquet(f"{C}/val_side_moves_iter4.parquet", index=False)
