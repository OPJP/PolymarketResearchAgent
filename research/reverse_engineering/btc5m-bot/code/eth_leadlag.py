"""Iteration 4: ETH lead-lag at 0.5-s resolution. Agreement of the bot's side (one-sided VALIDATE seconds) with the ETH perp
move and the Binance BTC futures move in half-second windows [s-a, s-b) around the block second s, on all one-sided seconds
and on the seconds where none of the six BTC series moved (<= 0.1 bp over the PIT 3 s). Also: does an ETH move lead the
BTC futures move (corr of 0.5-s returns at lags), i.e. is ETH a leading indicator the bot can exploit?"""
import os, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
A = pd.read_parquet(f"{C}/val_side_moves_iter4.parquet"); A["s"] = (A.start_ts + A.rel).astype(np.int64)
WIN = [(-6.0, -4.0), (-4.0, -3.0), (-3.0, -2.5), (-2.5, -2.0), (-2.0, -1.5), (-1.5, -1.0), (-1.0, -0.5), (-0.5, 0.0), (0.0, 1.0), (1.0, 3.0)]


def lpf(df):
    T = df["T"].to_numpy(np.int64); lp = np.log(df.p.to_numpy())
    def f(t):
        i = np.searchsorted(T, t, side="left")
        return np.where(i > 0, lp[np.clip(i - 1, 0, None)], np.nan)
    return f


out = []; cc = {}
for d0, g in A.groupby(A.s // 86400 * 86400):
    g = g.copy(); s = g.s.to_numpy(np.int64) * 1000
    fe = lpf(pd.concat([pd.read_parquet(f"{C}/venues/ethfut/{d}.parquet", columns=["T", "p"]) for d in (d0 - 86400, d0) if os.path.exists(f"{C}/venues/ethfut/{d}.parquet")]).sort_values("T"))
    ff = lpf(pd.concat([pd.read_parquet(f"{C}/fut/{d}.parquet", columns=["T", "p"]) for d in (d0 - 86400, d0) if os.path.exists(f"{C}/fut/{d}.parquet")]).sort_values("T"))
    for a, b in WIN:
        g[f"E_{a}_{b}"] = (fe(s + int(b * 1000)) - fe(s + int(a * 1000))) * 1e4
        g[f"F_{a}_{b}"] = (ff(s + int(b * 1000)) - ff(s + int(a * 1000))) * 1e4
    # 0.5-s return series over the whole day: lead-lag ETH -> BTC futures
    grid = np.arange(d0 * 1000, (d0 + 86400) * 1000, 500, dtype=np.int64)
    re_ = np.diff(fe(grid)); rf = np.diff(ff(grid)); ok = np.isfinite(re_) & np.isfinite(rf)
    for k in (-4, -2, -1, 0, 1, 2, 4):  # k > 0: ETH return at t vs BTC futures return at t + k half-seconds
        x = re_[:len(re_) - k] if k > 0 else re_[-k:]; y = rf[k:] if k > 0 else rf[:len(rf) + k]
        m = np.isfinite(x) & np.isfinite(y) & (x != 0) & (y != 0)
        cc.setdefault(k, []).append(float(np.corrcoef(x[m], y[m])[0, 1]))
    out.append(g)
A = pd.concat(out); up = A.truth_up.to_numpy() == 1
nomove = (A.mx6.to_numpy() <= 0.1) & (A.n6.to_numpy() >= 4)


def agree(x, mask):
    m = mask & np.isfinite(x) & (x != 0)
    return (round(float(((x[m] > 0) == up[m]).mean()), 4), int(m.sum())) if m.sum() else (None, 0)


res = {"windows_rel_block_second": {}, "corr_eth_leads_btcfut_halfsec": {str(k): round(float(np.mean(v)), 4) for k, v in cc.items()}}
for a, b in WIN:
    res["windows_rel_block_second"][f"[s{a:+.1f}, s{b:+.1f})"] = {"eth_all": agree(A[f"E_{a}_{b}"].to_numpy(), np.ones(len(A), bool)),
                                                               "eth_nomove": agree(A[f"E_{a}_{b}"].to_numpy(), nomove),
                                                               "btcfut_all": agree(A[f"F_{a}_{b}"].to_numpy(), np.ones(len(A), bool))}
print(json.dumps(res, indent=1))
json.dump(res, open(f"{R}/results_eth_leadlag_iter4.json", "w"), indent=1)
