"""iteration 15 (post hoc): is the decoded opening quote profitable? Return per $ of the non-daily non-BTC fills by agreement
with the public posture (k 0.7 vs the last clean print), opening vs later, per fold (Binance stand-in settlement as in
nb_pnl.py)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from nb_side import Spot, C, RES
fr = [pd.read_parquet(C / f) for f in ("it15_nb_public_lot.parquet", "it15_nb_public_build.parquet") if (C / f).exists()]
a = pd.concat(fr, ignore_index=True)
sp = Spot()
win = a.drop_duplicates("slug")[["slug", "fam", "sym", "st", "L", "K"]].reset_index(drop=True)
end = (win.st + win.L).to_numpy(np.int64); se = np.full(len(win), np.nan)
for sym, g in win.groupby("sym"):
    e = end[g.index]; tw = g.fam.str.contains(r"-(?:5m|15m|4h)$").to_numpy()
    se[g.index] = np.where(tw, sp.twap60(sym, e), sp.close_at(sym, e - 1))
win["SE"] = se
a = a.merge(win[["slug", "SE"]], on="slug", how="left")
a = a[np.isfinite(a.SE) & np.isfinite(a.K) & a["post_pub_k0.7"].notna()]
a["pay"] = np.where(a.up == (a.SE >= a.K).astype(float), 1.0, 0.0)
a["cost"] = a.price * a["size"]; a["pnl"] = (a.pay - a.price) * a["size"]
a["fd"] = np.where(a.fold.str.startswith("STUDY"), "STUDY", a.fold)
g = a.groupby(["fd", "phase", "post_pub_k0.7"]).agg(n=("pnl", "size"), cost=("cost", "sum"), pnl=("pnl", "sum"), win=("pay", "mean")).reset_index()
g["ret"] = (g.pnl / g.cost).round(4)
print(g.round(3).to_string(index=False))
(RES / "iter15_nb_pub_pnl.json").write_text(json.dumps(g.to_dict("records"), indent=1, default=float))
