"""iteration 15 (post hoc, own state, reported): are the later non-BTC fills a continuation of the window's first fill?
Per non-BTC market (5m/15m/4h/hourly; dailies excluded): the share of later fills (>= 20 s) on the outcome of the market's
first cluster fill (own-history baseline), the share on the first OPENING fill's outcome where one exists, and the majority
side (by shares) vs the first fill. Folds: BUILD sample days, STUDY, VALIDATE (aggregate), after T0."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from nb_side import C, RES
a = pd.read_parquet(C / "it15_nb_side.parquet")
a = a[(~a.btc_core) & (~a.fam.str.endswith("-daily"))].sort_values(["slug", "timestamp"], kind="stable")
a["fd"] = np.where(a.fold.str.startswith("STUDY"), "STUDY", a.fold)
rows = []
for slug, g in a.groupby("slug"):
    first_up = g.up.iloc[0]; op = g[g.phase == "open<20s"]
    later = g[g.phase == "later"]
    sh_up = g.loc[g.up == 1, "size"].sum() / g["size"].sum()
    rows.append((slug, g.fd.iloc[0], len(g), len(later), float((later.up == first_up).mean()) if len(later) else np.nan,
                 float((later.up == op.up.iloc[0]).mean()) if (len(op) and len(later)) else np.nan, int(len(op) > 0),
                 float((sh_up > 0.5) == (first_up == 1)), float(later.mktfav_ok.mean()) if len(later) else np.nan))
M = pd.DataFrame(rows, columns=["slug", "fd", "n", "n_later", "later_same_as_first", "later_same_as_open", "has_open", "majority_eq_first", "later_mktfav"])
out = {}
for fd, g in M.groupby("fd"):
    w = g.n_later
    out[fd] = {"markets": int(len(g)), "later_fills": int(w.sum()),
               "later_same_as_first_fillweighted": round(float(np.nansum(g.later_same_as_first * w) / w[g.later_same_as_first.notna()].sum()), 3),
               "later_same_as_open_fillweighted": round(float(np.nansum(g.later_same_as_open * w) / max(w[g.later_same_as_open.notna()].sum(), 1)), 3),
               "markets_with_open": int(g.has_open.sum()),
               "majority_side_eq_first_fill": round(float(g.majority_eq_first.mean()), 3),
               "later_mktfav_fillweighted": round(float(np.nansum(g.later_mktfav * w) / w[g.later_mktfav.notna()].sum()), 3)}
    print(fd, out[fd])
(RES / "iter15_nb_persist.json").write_text(json.dumps(out, indent=1))
