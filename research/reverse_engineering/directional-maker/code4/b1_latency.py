"""Cancel/requote latency at ms resolution (STUDY day 2026-10-26): Binance move just before each maker BUY fill's match
time (= the taker order's signing ms from calldata), cluster vs other makers vs random times."""
import glob
import numpy as np, pandas as pd
C = ".cache/re/directional-maker/"
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
D0, D1 = 1792972800, 1793059200
agg = pd.read_parquet(C + "agg_2026-10-26.parquet", columns=["ms", "px"])
ms, px = agg.ms.to_numpy(), agg.px.to_numpy()
def px_at(t):  # last trade price at or before t (ms)
    i = np.searchsorted(ms, t, side="right") - 1
    return px[np.clip(i, 0, len(px) - 1)]
win = pd.read_parquet(C + "exam/windows_5m.parquet")
sgn = {**{t: 1 for t in win.up_token}, **{t: -1 for t in win.down_token}}
st = {**dict(zip(win.up_token, win.start_ts)), **dict(zip(win.down_token, win.start_ts))}
def load(pattern):
    d = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(C + "calldata/" + pattern))], ignore_index=True)
    tk = d[d.role == "taker"].set_index("tx")
    mk = d[(d.role == "maker") & (d.oside == 0)].copy()
    mk["m"] = mk.tx.map(tk.sign_ms)
    mk["tk_oside"] = mk.tx.map(tk.oside)
    mk["sg"] = mk.token_id.map(sgn)
    mk["st"] = mk.token_id.map(st)
    return mk[mk.sg.notna() & (mk.m > D0 * 1000) & (mk.m < D1 * 1000)]
clu = load("study_*.parquet"); clu = clu[clu.maker.isin(W)]
pub = load("pub1026_*.parquet"); pub = pub[~pub.maker.isin(W)]
pub["age"] = pub.m / 1000 - pub.sign_ms / 1000  # other makers' order age at match (s)
rng = np.random.default_rng(3)
rnd = pub.sample(len(pub), replace=True, random_state=5).copy()
rnd["m"] = (rnd.st.to_numpy() * 1000 + rng.uniform(5000, 270000, len(rnd))).astype("int64")
L = [100, 250, 500, 750, 1000, 1500, 2000, 3000, 5000]
out = {}
for name, g in (("cluster", clu), ("other_makers_public", pub), ("random_times", rnd)):
    m = g.m.to_numpy().astype("int64"); s = g.sg.to_numpy()
    p0 = px_at(m)
    row = {"n": int(len(g))}
    for l in L:
        r = s * (p0 - px_at(m - l))  # >0 favourable to the maker's token, <0 adverse
        row[f"mean_{l}"] = round(float(np.mean(r)), 2)
        row[f"adv5_{l}"] = round(float(np.mean(r < -5)), 4)  # adverse move > $5 (~0.7 bp)
    out[name] = row
for k, v in out.items():
    print(k, v)
# other makers split by order age: are old orders the ones hit after adverse moves?
for lo, hi in ((0, 2), (2, 5), (5, 30), (30, 1e9)):
    g = pub[(pub.age >= lo) & (pub.age < hi)]
    m = g.m.to_numpy().astype("int64"); s = g.sg.to_numpy(); p0 = px_at(m)
    print("other makers age", lo, hi, "n", len(g), "mean adverse-signed move 1s/3s", round(float(np.mean(s * (p0 - px_at(m - 1000)))), 2), round(float(np.mean(s * (p0 - px_at(m - 3000)))), 2))
# taker latency: block ts - taker sign
tk = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(C + "calldata/study_*.parquet"))])
tk = tk[(tk.role == "taker") & (tk.sign_ms > 0)]
