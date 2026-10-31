"""Iteration 6, check of iteration 5's "near-touch 500/100 re-posts follow the futures mid within 50-250 ms" by size class
(exact 500 = mostly the cluster's per the calldata identity check; exact 100 = other makers'). A re-post = an add of size S
within 3 ticks of the touch preceded <= 50 ms by a removal of S on the same side at another price. Agreement = sign of
the price change equals the sign of the futures bookTicker mid move over [t-250, t-50] ms (Up-book terms), when it moved.
    python code6/repost_dir.py <a> <b>"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
from rawread import iter_dm
C = ROOT / ".cache/re/directional-maker"
a, b = int(sys.argv[1]), int(sys.argv[2])
ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet")
ev = ev[ev.d.abs().isin([500.0, 100.0])].sort_values("s", kind="stable")
fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", a - 60, b) if r["r"][0] == "b" and r["r"][2]]
fu = pd.DataFrame(fut, columns=["s", "m"]).sort_values("s").drop_duplicates("s", keep="last")
fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
def mid_at(t):
    i = np.searchsorted(fs, t, side="right") - 1
    return fm[i] if i >= 0 else np.nan
out = {}
for S in (500.0, 100.0):
    e = ev[ev.d.abs() == S]
    rows = []
    for (w, side), g in e.groupby(["w", "side"]):
        g = g.sort_values("s", kind="stable")
        s_, d_, p_, bb_, ba_ = g.s.to_numpy(), g.d.to_numpy(), g.p.to_numpy(), g.bb.to_numpy(), g.ba.to_numpy()
        last_rem = None
        for i in range(len(g)):
            if d_[i] < 0:
                last_rem = (s_[i], p_[i]); continue
            near = (side == 1 and p_[i] >= bb_[i] - 0.031) or (side == 0 and p_[i] <= ba_[i] + 0.031)
            if last_rem is None or not near or s_[i] - last_rem[0] > 50 or abs(p_[i] - last_rem[1]) < 1e-9:
                continue
            dp = np.sign(p_[i] - last_rem[1])
            fmv = mid_at(s_[i] - 50) - mid_at(s_[i] - 250)
            fmv1 = mid_at(s_[i] - 50) - mid_at(s_[i] - 1050)
            rows.append((dp, np.sign(fmv), np.sign(fmv1)))
    R = pd.DataFrame(rows, columns=["dp", "f", "f1"])
    m = R.f != 0; m1 = R.f1 != 0
    out[f"S{int(S)}"] = {"reposts": int(len(R)), "share_with_fut_move_50_250ms": round(float(m.mean()), 3),
                         "agree_50_250ms": round(float((R.dp[m] == R.f[m]).mean()), 3) if m.any() else None, "n_moved": int(m.sum()),
                         "agree_50_1050ms": round(float((R.dp[m1] == R.f1[m1]).mean()), 3) if m1.any() else None, "n_moved_1s": int(m1.sum())}
(HERE.parent / "results" / f"iter6_repost_dir_{a}_{b}.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
