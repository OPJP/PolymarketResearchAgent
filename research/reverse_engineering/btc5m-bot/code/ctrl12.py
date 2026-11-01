"""Iteration 12, panel iter11 assumptions P4 steps 1 and 3 (X112): is the take regime the bot's recent race success?
Decisions = it11/large_dec.parquet (won = taker-first matches; lost = located lost-race insertions of it9/ins9b_M,
lost_300 / lost_1000, arrival = insertion - 150 ms, as size11.py). For every clean onset of the 10-31 onset tables: the
operator's decisions on the window in [tau - 120 s, tau) (count n) and the share of them that WON; P(take) by win share
with the count held fixed (count bins), and a linear probability model with 120-s segment fixed effects:
y ~ win_share + log(1 + n) + log|bp| + class. Exogenous-loss split (crowd queued ahead) not done here."""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
D_MS = 150
from regime12 import lpm_fe

dec = pd.read_parquet(f"{C}/it11/large_dec.parquet")
Mi = pd.read_parquet(f"{C}/it9/ins9b_M.parquet")
Mi = Mi[Mi.s_ins.notna() & Mi.rcls.isin(["lost_300", "lost_1000"])]
lost_keys = set(zip(Mi.mstart.astype(int), Mi.w, Mi.is_up.astype(bool), (Mi.s_ins.astype(np.int64) - D_MS)))
dec["won"] = [not ((int(s), w, bool(u), int(a)) in lost_keys) for s, w, u, a in zip(dec.st, dec.w, dec.up, dec.a.astype(np.int64))]
res = {"decisions": int(len(dec)), "lost_matched": int((~dec.won).sum()), "lost_in_ins9b": int(len(Mi))}
G = {int(st): (g.sort_values("a").a.to_numpy(float), g.sort_values("a").won.to_numpy(bool)) for st, g in dec.groupby("st")}
for nm in ("A", "C"):
    e = pd.read_parquet(f"{C}/it11/onset_{nm}.parquet")
    e = e[e.st.isin(list(G))].reset_index(drop=True)
    tau = e.tau.to_numpy(float); st = e.st.to_numpy(np.int64)
    n = np.zeros(len(e)); nw = np.zeros(len(e))
    for i in range(len(e)):
        a, wn = G[int(st[i])]
        i0, i1 = np.searchsorted(a, tau[i] - 120000), np.searchsorted(a, tau[i])
        n[i] = i1 - i0; nw[i] = wn[i0:i1].sum()
    ws = np.where(n > 0, nw / np.maximum(n, 1), np.nan)
    y = e.y.to_numpy(float)
    tab = {}
    for lo, hi in ((1, 3), (3, 8), (8, 20), (20, 10 ** 6)):
        m = (n >= lo) & (n < hi)
        if m.sum() < 50:
            continue
        q = np.nanquantile(ws[m], [1 / 3, 2 / 3])
        tab[f"n{lo}-{hi}"] = {"events": int(m.sum()), "mean_win_share": round(float(np.nanmean(ws[m])), 3),
                              "take_low_ws": round(float(y[m & (ws <= q[0])].mean()), 4) if (m & (ws <= q[0])).any() else None,
                              "take_mid_ws": round(float(y[m & (ws > q[0]) & (ws <= q[1])].mean()), 4) if (m & (ws > q[0]) & (ws <= q[1])).any() else None,
                              "take_high_ws": round(float(y[m & (ws > q[1])].mean()), 4) if (m & (ws > q[1])).any() else None}
    m = n > 0
    base = np.c_[np.log(np.abs(e.bp.to_numpy(float)) + 1e-3), (e.cls == "PRICE").to_numpy(float), (e.cls == "DEPLETE").to_numpy(float)]
    relms = tau - st * 1000.0
    seg = st * 1000 + (relms // 120000)
    b = lpm_fe(y[m], np.c_[ws[m], np.log1p(n[m]), base[m]], seg[m])
    bw = lpm_fe(y[m], np.c_[ws[m], np.log1p(n[m]), base[m]], st[m])
    res[nm] = {"onsets_with_recent_decisions": int(m.sum()), "take_rate": round(float(y[m].mean()), 4), "by_count_bin": tab,
               "lpm_win_share_coef_120s_fe": round(float(b[0]), 4), "lpm_win_share_coef_window_fe": round(float(bw[0]), 4)}
    print(nm, json.dumps(res[nm]), flush=True)
json.dump(res, open(f"{R}/ctrl12.json", "w"), indent=1)
print(json.dumps({k: res[k] for k in ("decisions", "lost_matched", "lost_in_ins9b")}))
