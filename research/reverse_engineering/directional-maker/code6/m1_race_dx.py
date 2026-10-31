"""Iteration 6, X41 first look: Deribit (index, perp mid) and Bitstamp vs Chainlink on the ladder-center skew, live
15:55-16:30 UTC only (exam recorder dx_* feeds started 15:53); in-sample R^2 on the same seconds (descriptive, no split).
    python code6/m1_race_dx.py <ev_a> <ev_b> <w_a>"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
from rawread import iter_dm
C = ROOT / ".cache/re/directional-maker"
a, b, wa = map(int, sys.argv[1:4])
ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet"); ev = ev[ev.w.str.contains("btc-updown-5m") & (ev.d == 500.0)]
tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
s0, s1 = wa - 400, b + 60
sec = np.arange(s0, s1)
def ser(pairs):
    d = pd.DataFrame(pairs, columns=["s", "px"]).dropna().sort_values("s")
    idx = np.searchsorted(d.s.to_numpy(), (sec + 1) * 1000, side="left") - 1
    return pd.Series(np.where(idx >= 0, d.px.to_numpy()[np.clip(idx, 0, None)], np.nan), index=sec)
V = {}
V["futures"] = ser([(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dx_bnf", s0, s1) if r["r"][0] == "b" and r["r"][2]])
V["deribit_index"] = ser([(r["r"][1], r["r"][2]) for r in iter_dm("dx_drb", s0, s1) if r["r"][0] == "i"])
V["deribit_perp_mid"] = ser([(r["r"][1], (r["r"][2] + r["r"][3]) / 2) for r in iter_dm("dx_drb", s0, s1) if r["r"][0] == "k" and r["r"][2] and r["r"][3]])
V["bitstamp"] = ser([(r["r"][0] // 1000, r["r"][1]) for r in iter_dm("dx_bst", s0, s1)])
cl = {}
for r in iter_dm("dx_rtds", s0, s1):
    if r["q"] != "crypto_prices_chainlink": continue
    try: j = json.loads(r["m"])
    except ValueError: continue
    for x in (j.get("payload") or {}).get("data", []) or []: cl[int(x["timestamp"]) // 1000] = float(x["value"])
V["chainlink"] = pd.Series(cl).sort_index().reindex(sec).ffill()
r1 = np.log(V["futures"]).diff()
rows = []
for w, g in ev.groupby("w"):
    st = int(w.split("-")[-1])
    if st < wa or st + 300 > b: continue
    K = {k: v.loc[st - 60:st - 1].mean() for k, v in V.items()}
    tw_ = tch[tch.w == w].sort_values("s"); ts_, bb_, ba_ = tw_.s.to_numpy(), tw_.bb.to_numpy(), tw_.ba.to_numpy()
    gb, ga = g[g.side == 1], g[g.side == 0]
    for t in range(st + 5, st + 270):
        T = t * 1000
        mb = gb[(gb.s > T - 1500) & (gb.s <= T)]; ma = ga[(ga.s > T - 1500) & (ga.s <= T)]
        if not len(mb) or not len(ma): continue
        qu, au = float(mb.p.max()), float(ma.p.min()); i = np.searchsorted(ts_, T, side="right") - 1
        if au <= qu or i < 0: continue
        mid = (bb_[i] + ba_[i]) / 2
        sig = float(r1.loc[t - 300:t - 1].std()) * 1.4; tau = max(st + 300 - t, 1.0)
        row = {"sk": (qu + au) / 2 - mid, "mid": mid}
        for k, v in V.items():
            for lag in (0, 1, 2, 3):
                px = v.get(t - lag, np.nan)
                row[f"{k}{lag}"] = norm.cdf(np.log(px / K[k]) / (sig * np.sqrt(tau))) if (px == px and K[k] == K[k] and sig > 0) else np.nan
        rows.append(row)
D = pd.DataFrame(rows)
res = {"seconds": int(len(D))}
for X in [c for c in D.columns if c not in ("sk", "mid")]:
    d = D[[X, "sk", "mid"]].dropna()
    if len(d) < 100: continue
    res[X] = [round(float(np.corrcoef(d[X] - d.mid, d.sk)[0, 1] ** 2), 3), int(len(d))]
(HERE.parent / "results" / f"iter6_m1_race_dx_{wa}_{b}.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res))
