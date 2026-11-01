"""X128 (own, iteration 12): is the opening ladder one-sided? BTC 5m windows of 10-31 14:00-16:53 (dm_clob_raw):
schedule-size adds of 500 / 1000 (the US-session cluster ladder; ~12% of exact-500 fills are other makers', X36) within
0.20 of the touch, per outcome, in the window's first 30 s and in the 10 s before its first cluster fill. One-sidedness =
max(Up, Down) / (Up + Down) per window; agreement of the dominant outcome with the outcome of the window's first
cluster fill and with the Chainlink posture at the first fill's post."""
import json
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
OUT = ROOT / ".cache/re/directional-maker/it13"
S = pd.read_parquet(OUT / "sched_adds.parquet")
S = S[S.w.str.contains("-5m-") & S.dz.isin([500.0, 1000.0])].copy()
S["start"] = S.w.str.rsplit("-", n=1).str[1].astype(int)
S["t"] = S.s / 1000 - S.start
o = pd.read_parquet(OUT / "fills_posts.parquet")
o = o[o.w.str.contains("-5m-")].sort_values("fill_ms")
first = o.groupby("w").head(1).set_index("w")
rows = []
for w, g in S.groupby("w"):
    st = int(w.rsplit("-", 1)[1])
    if st < 1793455200 or st >= 1793465400:
        continue
    a = g[(g.t >= 0) & (g.t < 30)]
    up, dn = int((a.sd == 1).sum()), int((a.sd == 0).sum())
    r = {"w": w, "up30": up, "dn30": dn}
    if w in first.index:
        f = first.loc[w]
        b = g[(g.s >= f.fill_ms - 10000) & (g.s <= f.fill_ms)]
        r.update(first_up=int(f.is_up), upb=int((b.sd == 1).sum()), dnb=int((b.sd == 0).sum()), first_t=float(f.fill_ms / 1000 - st))
    rows.append(r)
D = pd.DataFrame(rows)
D["n30"] = D.up30 + D.dn30
d30 = D[D.n30 >= 3]
one30 = (np.maximum(d30.up30, d30.dn30) / d30.n30)
Db = D[D.first_up.notna() & ((D.upb + D.dnb) >= 2)].copy()
oneb = np.maximum(Db.upb, Db.dnb) / (Db.upb + Db.dnb)
dom_up = Db.upb > Db.dnb
agree = (dom_up == (Db.first_up == 1))[Db.upb != Db.dnb]
res = {"windows": int(len(D)), "with_adds_first30": int(len(d30)), "onesided_share_first30_q": np.percentile(one30, [25, 50, 75]).round(3).tolist(),
       "share_windows_ge90pct_one_outcome_first30": float((one30 >= 0.9).mean()),
       "pre_first_fill_windows": int(len(Db)), "onesided_pre_first_fill_q": np.percentile(oneb, [25, 50, 75]).round(3).tolist() if len(Db) else None,
       "share_ge90pct_pre_first_fill": float((oneb >= 0.9).mean()) if len(Db) else None,
       "dominant_outcome_is_first_fill_outcome": float(agree.mean()) if len(agree) else None, "n_agree": int(len(agree)),
       "first_fill_time_in_window_q": np.percentile(Db.first_t, [25, 50, 75]).round(1).tolist() if len(Db) else None}
print(json.dumps(res, indent=1))
(HERE.parent / "results/iter13_entry_ladder.json").write_text(json.dumps(res, indent=1))
