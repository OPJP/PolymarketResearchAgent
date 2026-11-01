"""X209 statistics on decided_early_rows_print.parquet: per end class, the winner-signed change of V and of the print by
window around the print-anchored round end e_r, V's before-anchor share, and a map-cluster bootstrap of the difference
in before-share between decided-early and elimination rounds (V and, as the control, the print).
Output: results/decided_early.json"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
ANCHOR = os.environ.get("TOMMY_CLOCK_ANCHOR", "print")
D = pd.read_parquet(ROOT / f".cache/re/tommy-cs2-maker/iter15/decided_early_rows_{ANCHOR}.parquet")
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = ["mid", "late", "end", "after", "post"]
D["grp"] = np.select([D.cls.isin(["CT_elim_T", "T_elim_CT"]), D.cls.isin(["defuse_after_T_wiped", "bombed_CT_alive"])],
                     ["elimination", "decided_early"], "other")


def share(g, pre):
    m = {k: g[f"d{pre}_{k}"].mean() for k in W}
    tot = sum(m.values())
    return (m["mid"] + m["late"]) / tot if tot and np.isfinite(tot) and abs(tot) > 1e-9 else np.nan, m


out = {"rounds": int(len(D)), "by_class": {}, "by_group": {}}
for nm, g in list(D.groupby("cls")) + [("ALL", D)]:
    sv, mv = share(g, "V")
    sp, mp = share(g, "P")
    out["by_class"][nm] = {"n": int(len(g)), "V_c": {k: round(float(v * 100), 2) for k, v in mv.items()},
                           "P_c": {k: round(float(v * 100), 2) for k, v in mp.items()},
                           "V_before_share": round(float(sv), 3) if np.isfinite(sv) else None,
                           "P_before_share": round(float(sp), 3) if np.isfinite(sp) else None}
for nm, g in D.groupby("grp"):
    sv, mv = share(g, "V")
    sp, mp = share(g, "P")
    out["by_group"][nm] = {"n": int(len(g)), "V_c": {k: round(float(v * 100), 2) for k, v in mv.items()},
                           "P_c": {k: round(float(v * 100), 2) for k, v in mp.items()},
                           "V_before_share": round(float(sv), 3), "P_before_share": round(float(sp), 3)}
rng = np.random.default_rng(1)
maps = D.cid.unique()
bd = {"V": [], "P": []}
# per-map sums by group and window (fast cluster bootstrap)
S = {}
for pre in ("V", "P"):
    for gname in ("elimination", "decided_early"):
        sub = D[D.grp == gname]
        S[(pre, gname)] = sub.groupby("cid")[[f"d{pre}_{k}" for k in W]].sum().reindex(maps).fillna(0).to_numpy()
cnt = {g: D[D.grp == g].groupby("cid").size().reindex(maps).fillna(0).to_numpy() for g in ("elimination", "decided_early")}
for _ in range(2000):
    idx = rng.integers(0, len(maps), len(maps))
    if cnt["elimination"][idx].sum() < 5 or cnt["decided_early"][idx].sum() < 5:
        continue
    for pre in ("V", "P"):
        sh_ = []
        for gname in ("decided_early", "elimination"):
            m = S[(pre, gname)][idx].sum(axis=0)
            tot = m.sum()
            sh_.append((m[0] + m[1]) / tot if abs(tot) > 1e-12 else np.nan)
        bd[pre].append(sh_[0] - sh_[1])
for pre in ("V", "P"):
    x = np.array([v for v in bd[pre] if np.isfinite(v)])
    out[f"diff_before_share_decided_minus_elim_{pre}"] = {"point": round(float(out["by_group"]["decided_early"][f"{pre}_before_share"] - out["by_group"]["elimination"][f"{pre}_before_share"]), 3),
                                                        "ci95": [round(float(np.quantile(x, 0.025)), 3), round(float(np.quantile(x, 0.975)), 3)], "draws": int(len(x))}
# within bombed_CT_alive: before-share by gap proxy (bo3 duration tercile; longer rounds = later plant / longer decided gap)
b = D[D.cls == "bombed_CT_alive"].copy()
if len(b) >= 15:
    b["q"] = pd.qcut(b.dur_bo3, 3, labels=["short", "mid", "long"])
    out["bombed_CT_alive_by_duration"] = {str(q): {"n": int(len(g)), "V_before_share": round(float(share(g, "V")[0]), 3),
                                                   "P_before_share": round(float(share(g, "P")[0]), 3)} for q, g in b.groupby("q", observed=True)}
(RES / f"decided_early_{ANCHOR}.json").write_text(json.dumps(out, indent=1, default=float))
print(json.dumps(out, indent=1, default=float))
