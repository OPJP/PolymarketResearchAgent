"""Iteration 8, X48 (panel-information iter7 P5): co-terminal cross-market consistency with the Polymarket BTC 15m windows.
A 5m window that starts 600 s after a 15m window's start settles on the same TWAP-60 at the same instant. Given the 15m
market's last Up price p15 before second s (data-api taker tape, prints with ts <= s - 1) and both strikes (Gamma priceToBeat,
known at each window's open), with a common v = sigma sqrt(tau_eff) (sigma = Deribit DVOL of the last complete hour):
z5 = Phi^-1(p15) + ln(K15 / K5) / v, P5_implied = Phi(z5). Side rule: buy Up iff P5_implied > m_last (the 5m tape Up price at
s - 1). Scored on the cluster's VALIDATE one-sided seconds in co-terminal 5m windows (seeded sample of 15m windows), all and
quiet; time-shift null = the 15m price 60 s earlier. Usage: python coterm8.py DVOL_JSON [n_windows]"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT)
import numpy as np, pandas as pd
from scipy.stats import norm
from polyrea.adapters.polymarket import PolymarketData, GAMMA_API

C = _ROOT + "/.cache/re/btc5m-bot"
VAL0, H = 1792108800, 1792713600
dv = pd.DataFrame(json.load(open(sys.argv[1]))["result"]["data"], columns=["t", "o", "h", "l", "c"])
DVC = dict(zip((dv.t // 1000).astype(int), dv.c / 100.0))
N = int(sys.argv[2]) if len(sys.argv) > 2 else 120
v = pd.read_parquet(C + "/val_side_it5book.parquet", columns=["cid", "rel", "start_ts", "truth_up", "psb", "m_last"])
w = pd.read_parquet(C + "/val_side_book_it5.parquet", columns=["cid", "rel", "nomove"])
v = v.merge(w.drop_duplicates(["cid", "rel"]), on=["cid", "rel"], how="left")
v = v[((v.start_ts - 600) % 900 == 0)]
st15_all = sorted(set((v.start_ts - 600).astype(int)))
rng = np.random.default_rng(48)
st15 = sorted(rng.choice(st15_all, min(N, len(st15_all)), replace=False).tolist())
ptb5 = pd.read_parquet(C + "/ptb.parquet").set_index("start").priceToBeat
pm = PolymarketData()
meta = {}
for i in range(0, len(st15), 25):
    part = st15[i:i + 25]
    d, _ = pm.http.get_json(f"{GAMMA_API}/events", [("slug", f"btc-updown-15m-{s}") for s in part] + [("limit", 50)], adapter="gamma.events", max_age=30 * 86400)
    for e in d or []:
        s0 = int(e["slug"].rsplit("-", 1)[1]); md = e.get("eventMetadata") or {}
        mk = (e.get("markets") or [{}])[0]
        if md.get("priceToBeat") is not None and mk.get("conditionId"):
            meta[s0] = (mk["conditionId"], float(md["priceToBeat"]))  # listing / open-time fields only
print("15m windows", len(st15), "with meta", len(meta), flush=True)
rows = []
for s0, (cid15, K15) in meta.items():
    s5 = s0 + 600
    if s5 not in ptb5.index:
        continue
    tr, _, cov = pm.market_trades(cid15, start=s5 - 120, end=min(s5 + 300, H - 1), taker_only=True)
    t = pd.DataFrame(tr)
    if not len(t):
        continue
    t = t[t.side == "BUY"]
    up = np.where(t.outcome == "Up", t.price.astype(float), 1 - t.price.astype(float))  # implied Up price of each print
    tt = t.timestamp.to_numpy(np.int64); o = np.argsort(tt, kind="stable"); tt, up = tt[o], up[o]
    vv = v[v.start_ts == s5]
    for r in vv.itertuples():
        s = s5 + int(r.rel)
        for shift, nm in ((0, "real"), (60, "null_shift60")):
            i = np.searchsorted(tt, s - 1 - shift, "right") - 1
            if i < 0:
                continue
            p15 = float(np.clip(up[i], 0.01, 0.99))
            hr = (s // 3600) * 3600 - 3600
            sig = DVC.get(int(hr), np.nan) / np.sqrt(365.0 * 86400.0)
            tau = s5 + 300 - s
            vtau = sig * np.sqrt(max(tau - 40, tau / 3))
            K5 = float(ptb5[s5])
            p5 = float(norm.cdf(norm.ppf(p15) + np.log(K15 / K5) / max(vtau, 1e-9)))
            rows.append((nm, s5, int(r.rel), int(r.truth_up), float(r.psb), float(r.m_last), bool(r.nomove) if r.nomove == r.nomove else False, p5, p15))
D = pd.DataFrame(rows, columns=["kind", "s5", "rel", "truth", "psb", "m_last", "quiet", "p5_impl", "p15"])
res = {"windows_15m": len(meta), "seconds": int((D.kind == "real").sum())}
for kind in ("real", "null_shift60"):
    x = D[D.kind == kind]
    gap = x.p5_impl - x.m_last
    r = {}
    for nm, k in (("all", np.ones(len(x), bool)), ("quiet", x.quiet.to_numpy(bool)), ("gap_gt_2c", (gap.abs() > 0.02).to_numpy()), ("quiet_gap_gt_2c", x.quiet.to_numpy(bool) & (gap.abs() > 0.02).to_numpy())):
        xx = x[k]; gg = gap[k]
        r[nm] = {"n": int(len(xx)), "gap_rule": round(float(((gg > 0).astype(int) == xx.truth).mean()), 4) if len(xx) else None,
                 "psb": round(float(((xx.psb > 0.5).astype(int) == xx.truth).mean()), 4) if len(xx) else None,
                 "mean_abs_gap_c": round(float(gg.abs().mean() * 100), 2) if len(xx) else None}
    res[kind] = r
    print(kind, json.dumps(r), flush=True)
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/coterm8.json", "w"), indent=1)
