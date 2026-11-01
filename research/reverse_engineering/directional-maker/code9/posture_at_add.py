"""Iteration 9 (X76): is mo-money's 500 rung a stale rung? For each confirmed filled order of 10-31 14:04-16:13 (iteration 6
confirmed table: wallet, side (1 = Up), size, raw-book add ms, match ms), the posture (Chainlink report stamped
floor((t - 1432)/1000), RTDS TWAP strike, 1.4 x 300-s Binance vol, Up mid from the own touch table) evaluated at the order's
ADD time and at its MATCH time; accuracy by wallet and size class. Development, descriptive."""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code5"))
sys.path.insert(0, str(HERE.parent / "code6"))
from pres_live import load_ref  # noqa: E402
C = HERE.parents[3] / ".cache/re/directional-maker"
a, b = 1793455600, 1793463203
Q = pd.read_parquet(C / "it6" / f"confirmed_{a}_{b}.parquet")
Q = Q[Q.found].drop_duplicates(["wallet", "ms", "add_s"]).copy()
tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
fu, cl, tw = load_ref(a, b)
sp = pd.read_parquet(C / "it9" / "spot1s_rest_1793440800_1793469600.parquet").sort_values("sec")
b0 = int(sp.sec.iloc[0]); px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan); px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
px = pd.Series(px).ffill().to_numpy(); rr = np.r_[0.0, np.diff(np.log(px))]; cs = np.r_[0.0, np.cumsum(rr * rr)]
tg = {w: g.sort_values("s") for w, g in tch.groupby("w")}
rows = []
for r in Q.itertuples(index=False):
    st = int(r.slug.rsplit("-", 1)[1]); L = 900 if "-15m-" in r.slug else 300
    K = tw.get(st)
    g = tg.get(r.slug)
    if K is None or g is None:
        continue
    ts_, bb_, ba_ = g.s.to_numpy(), g.bb.to_numpy(), g.ba.to_numpy()
    rec = {"wallet": r.wallet, "S": r.S, "up": int(r.side == 1), "age": r.age_ms}
    for nm, t in (("add", int(r.add_s)), ("match", int(r.ms))):
        c = cl.get((t - 1432) // 1000)
        i = np.searchsorted(ts_, t, side="left") - 1
        if c is None or i < 0:
            rec[nm] = np.nan
            continue
        k = t // 1000 - 1 - b0
        sg = 1.4 * np.sqrt((cs[k + 1] - cs[k + 1 - 300]) / 300)
        tau = max(st + L - t / 1000, 1.0)
        fair = norm.cdf(np.log(c / K) / (sg * np.sqrt(tau)))
        rec[nm] = int(fair > (bb_[i] + ba_[i]) / 2)
    rows.append(rec)
D = pd.DataFrame(rows).dropna(subset=["add", "match"])
out = {}
for w, g in D.groupby("wallet"):
    for cls, k in (("500", np.isclose(g.S, 500)), ("other", ~np.isclose(g.S, 500))):
        h = g[k]
        if len(h) < 15:
            continue
        out[f"{w}|{cls}"] = {"n": int(len(h)), "posture_at_add": round(float((h["add"] == h.up).mean()), 3),
                             "posture_at_match": round(float((h["match"] == h.up).mean()), 3), "median_age_ms": float(h.age.median()),
                             "flip_between_add_and_match": round(float((h["add"] != h["match"]).mean()), 3)}
print(json.dumps(out, indent=1))
(HERE.parent / "results" / "iter9_posture_at_add.json").write_text(json.dumps(out, indent=1))
