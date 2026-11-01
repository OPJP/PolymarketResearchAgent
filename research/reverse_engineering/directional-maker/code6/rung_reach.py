"""Iteration 6, M2 step 3 (X31) explicit form: rung-reach rule at the print level, live block.
Center F*_up(t) = mid_up + c0 + lam * (fair_cl_up - mid_up) (Chainlink value stamped <= t - 2 s, true strike, futures vol
x 1.4), fitted on live BUILD seconds by OLS (code6/m1_center.py construction); top rung on s = center_s - h(time left)
with h = BUILD median h* (by last minute or not). A print selling s at p_s reaches the cluster iff gap = rung_s - p_s >= 0.
Scores: AUC of gap, recall/lift of gap >= 0 (and >= -0.01), on live VALIDATE prints. python code6/rung_reach.py <a> <b>"""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_auc_score
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5")); sys.path.insert(0, str(HERE))
from rawread import iter_dm
C = ROOT / ".cache/re/directional-maker"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
SPLIT = 1793458800
a, b = int(sys.argv[1]), int(sys.argv[2])
ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet"); ev = ev[ev.w.str.contains("btc-updown-5m") & (ev.d == 500.0)]
tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
x = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet"); x = x[x.w.str.contains("btc-updown-5m")].sort_values("s", kind="stable").drop_duplicates("h")
cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet"))])
cd["maker"] = cd.maker.str.lower(); cd["tx"] = cd.tx.str.lower()
mk_tx = set(cd.loc[(cd.role == "maker") & cd.maker.isin(CL), "tx"]); tk_tx = set(cd.loc[(cd.role == "taker") & cd.maker.isin(CL), "tx"])
fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", a - 400, b) if r["r"][0] == "b" and r["r"][2]]
fu = pd.DataFrame(fut, columns=["s", "m"]).sort_values("s").drop_duplicates("s", keep="last")
fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))
cl, tw = {}, {}
for r in iter_dm("dm_rtds", a - 400, b + 60):
    try: j = json.loads(r["m"])
    except ValueError: continue
    for q in (j.get("payload") or {}).get("data", []) or []:
        (cl if r["q"] == "crypto_prices_chainlink" else tw)[int(q["timestamp"]) // 1000] = float(q["value"])
cls = np.array(sorted(cl)); clv = np.array([cl[k] for k in cls])
def fair_cl_up(st, t_ms):
    K = tw.get(st)
    k = np.searchsorted(cls, t_ms // 1000 - 2, side="right") - 1
    jj = np.searchsorted(sec, t_ms // 1000); sig = np.std(r1[max(jj - 300, 0):jj]) * 1.4
    tau = max(st + 300 - t_ms / 1000, 1.0)
    if K is None or k < 0 or not sig > 0: return np.nan
    return norm.cdf(np.log(clv[k] / K) / (sig * np.sqrt(tau)))
T = {w: (g.s.to_numpy(), g.bb.to_numpy(), g.ba.to_numpy()) for w, g in tch.sort_values("s").groupby("w")}
def mid_before(w, t):
    s_, b_, a_ = T[w]; i = np.searchsorted(s_, t, side="left") - 1
    return (b_[i] + a_[i]) / 2 if i >= 0 else np.nan
# 1) fit the center on BUILD seconds (F* from exact-500 adds)
rows = []
for w, g in ev.groupby("w"):
    st = int(w.split("-")[-1])
    if st < a or st + 300 > SPLIT: continue
    gb, ga = g[g.side == 1], g[g.side == 0]
    for t in range(st + 5, st + 270):
        Tm = t * 1000
        mb = gb[(gb.s > Tm - 1500) & (gb.s <= Tm)]; ma = ga[(ga.s > Tm - 1500) & (ga.s <= Tm)]
        if not len(mb) or not len(ma): continue
        qu, au = float(mb.p.max()), float(ma.p.min())
        if au <= qu: continue
        mid = mid_before(w, Tm + 1)
        fc = fair_cl_up(st, Tm)
        rows.append((st + 300 - t, (qu + au) / 2 - mid, (au - qu) / 2, fc - mid))
B = pd.DataFrame(rows, columns=["left", "sk", "h", "xc"]).dropna()
lam, c0 = np.polyfit(B.xc, B.sk, 1)
h_late, h_main = float(B[B.left <= 60].h.median()), float(B[B.left > 60].h.median())
# 2) score VALIDATE prints
d = x.d.astype(str).str.upper().str[0]
x["s_up"] = ((x.ai == 0) & (d == "S")) | ((x.ai == 1) & (d == "B"))
x["p_s"] = np.where((x.ai == 0) == x.s_up, x.p, 1 - x.p)
out_rows = []
for r in x[(x.s >= SPLIT * 1000)].itertuples(index=False):
    if r.h in tk_tx: continue
    st = int(r.w.split("-")[-1]); t = int(r.s)
    if not (st * 1000 <= t < (st + 300) * 1000) or (st + 300) > b: continue
    mid = mid_before(r.w, t); fc = fair_cl_up(st, t)
    if not (mid == mid and fc == fc): continue
    cen_up = mid + c0 + lam * (fc - mid)
    h = h_late if (st + 300 - t / 1000) <= 60 else h_main
    rung = (cen_up - h) if r.s_up else (1 - cen_up - h)
    out_rows.append((int(r.h in mk_tx), rung - r.p_s, (1 if r.s_up else -1) * (fc - mid)))
D = pd.DataFrame(out_rows, columns=["y", "gap", "xc_s"])
res = {"lam": round(float(lam), 3), "c0": round(float(c0), 4), "h_main": h_main, "h_last_minute": h_late, "fit_seconds": int(len(B)),
       "test_prints": int(len(D)), "test_pos": int(D.y.sum()), "auc_gap": round(float(roc_auc_score(D.y, D.gap)), 4)}
base = D.y.mean()
for thr in (0.0, -0.01, -0.02, -0.03):
    f = D.gap >= thr
    res[f"gap_ge_{thr}"] = {"flag_share": round(float(f.mean()), 3), "recall": round(float(f[D.y == 1].mean()), 3),
                            "lift": round(float(D.y[f].mean() / base), 2) if f.any() else None}
(HERE.parent / "results" / f"iter6_rung_reach_{a}_{b}.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
