"""Iteration 9 (information I8-3 = X76): per-wallet posture accuracy by Chainlink reference delay (fill_side table of
iteration 8, 10-31 14:06-16:30, edges with the frozen sigma) and by fill age proxies. Development, descriptive."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
C = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker"
d = pd.read_parquet(C / "it6" / "fill_side_1793455600_1793464202.parquet")
y = d.up.to_numpy() == 1
out = {}
for w in ("bosona", "almach", "momoney"):
    g = (d.wallet == w).to_numpy()
    rec = {"n": int(g.sum())}
    for D_ in ("D700", "D1083", "D1432", "D2000", "D3000"):
        rec[D_] = float(np.mean(((d[f"e_cl_{D_}"] > 0).to_numpy() == y)[g]))
    rec["block_clock"] = float(np.mean(((d.e_cl_block > 0).to_numpy() == y)[g]))
    rec["at_touch_share"] = float(d.at_touch[g].mean())
    rec["at_touch_acc"] = float(np.mean(((d.e_cl > 0).to_numpy() == y)[g & (d.at_touch == 1).to_numpy()]))
    rec["deep_acc"] = float(np.mean(((d.e_cl > 0).to_numpy() == y)[g & (d.at_touch == 0).to_numpy()])) if (g & (d.at_touch == 0).to_numpy()).any() else None
    rec["median_shares"] = float(d.shares[g].median())
    rec["share_500"] = float((d.shares[g] >= 490).mean())
    out[w] = rec
# same windows only: windows where all three wallets have >= 3 fills
key = d.st.astype(str) + d.fam
cnt = d.groupby([key, d.wallet]).size().unstack(fill_value=0)
common = set(cnt.index[(cnt >= 3).all(axis=1)])
m = key.isin(common).to_numpy()
out["common_windows"] = {"windows": len(common), **{w: float(np.mean(((d.e_cl > 0).to_numpy() == y)[m & (d.wallet == w).to_numpy()])) for w in ("bosona", "almach", "momoney")}}
# same taker event: fills of different wallets in the same tx-ms (T within 5 ms): does mo-money disagree with the others?
d = d.sort_values("T")
grp = (d["T"].diff().fillna(1e9) > 5).cumsum()
ev = d.groupby(grp).agg(n=("wallet", "nunique"), up=("up", "mean"))
out["multi_wallet_events"] = {"events": int((ev.n >= 2).sum()), "mixed_side_share": float(((ev.up > 0) & (ev.up < 1))[ev.n >= 2].mean())}
print(json.dumps(out, indent=1))
(Path(__file__).resolve().parents[1] / "results" / "iter9_wallet_delay.json").write_text(json.dumps(out, indent=1))
