"""Iteration 13: R8's public side per burst start on the lot (block clock; STUDY case by case, VALIDATE aggregate), the
decision unit of the information panel (C1/C4): bursts = consecutive cluster fills of one window on one outcome with
block-second gaps < 3 s. Public = decided (|mid - 0.5| > 0.4) -> cheaper, else the posture (report b - 4, Gamma strike,
1.4 x 300-s vol; Binance stand-in f_bn where the Chainlink value is missing). Own-history baseline = previous fill side."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
d = pd.read_parquet(ROOT / ".cache/re/directional-maker/it12/typed_fills.parquet")
d = d[((d.en - d.st) == 300) & d.mid_up.notna()].sort_values(["cid", "b"], kind="stable").copy()
okc = d.cl.notna() & d.Kg.notna() & d.v300.notna() & d.tau_cl.notna()
fu = norm.cdf(np.log(d.cl / d.Kg) / (1.4 * d.v300 * np.sqrt(np.maximum(d.tau_cl, 1.0))))
post = np.where(okc, fu > d.mid_up, d.f_bn > d.mid_up)
dec = (d.mid_up - 0.5).abs() > 0.4
d["pub"] = np.where(dec, d.mid_up < 0.5, post)
d["y"] = d.is_up == 1
same = d.cid.eq(d.cid.shift())
gap = np.where(same, d.b - d.b.shift(), np.inf)
chg = (~same) | d.is_up.ne(d.is_up.shift())
d["bs"] = (gap >= 3) | chg
d["gap"] = gap
d["prev"] = np.where(same, d.is_up.shift() == 1, np.nan)
d["half"] = np.where(d.st >= 1793059200, "validate", "study")
res = {}
for h, g in d.groupby("half"):
    b = g[g.bs]
    o = {"fills": int(len(g)), "per_fill_public": float((g.pub == g.y).mean()), "burst_starts": int(len(b)),
         "burst_public": float((b.pub == b.y).mean()), "burst_cheaper": float(((b.mid_up < 0.5) == b.y).mean()),
         "burst_prev_side": float(((b.prev == 1) == b.y)[b.prev.notna()].mean())}
    for lo, hi in ((3, 10), (10, 30), (30, np.inf)):
        bb = b[(b.gap >= lo) & (b.gap < hi)]
        o[f"gap_{lo}_{hi}"] = {"n": int(len(bb)), "public": float((bb.pub == bb.y).mean()), "prev_side": float(((bb.prev == 1) == bb.y).mean())}
    first = b[~b.cid.duplicated()]
    o["window_first_burst_public"] = [int(len(first)), float((first.pub == first.y).mean())]
    res[h] = o
print(json.dumps(res, indent=1))
(HERE.parent / "results/iter13_burst_side_lot.json").write_text(json.dumps(res, indent=1))
