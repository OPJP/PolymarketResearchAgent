"""Iteration 14 (own-state description of the uncensored quote; reported, never counted): is the at-touch post on the
outcome the cluster holds more of (inventory) or on the under-held one, and how does that combine with the posture?
Quote unit = it14_quote_unit.parquet (code14/lagged_quote.py, 10-31 14-18). Cluster net position per window before the
post = cumulative Up - Down shares of every cluster BUY (maker or taker; SELLs subtracted) whose transaction's first
server ms is before the post (live activity + trades.parquet)."""
import glob, json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[4]; C = ROOT / ".cache/re/directional-maker"
q = pd.read_parquet(C / "it14_quote_unit.parquet")
X = pd.read_parquet(C / "it13/trades.parquet"); X["h"] = X.h.str.lower()
first = X.groupby("h").s.min()
acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))], ignore_index=True)
acts["tx"] = acts.transactionHash.str.lower()
acts = acts.drop_duplicates(subset=["tx", "asset", "size", "price"])
f = acts[(acts.type == "TRADE") & acts.slug.str.contains("btc-updown-(?:5m|15m)-", regex=True, na=False)].copy()
f["ms"] = f.tx.map(first); f = f[f.ms.notna()]
f["d_up"] = np.where(f.outcome == "Up", 1.0, -1.0) * f["size"] * np.where(f.side == "BUY", 1.0, -1.0)
res = {}
net = np.full(len(q), np.nan)
for w, ix in q.groupby("w").indices.items():
    g = f[f.slug == w].sort_values("ms"); ms = g.ms.to_numpy(np.int64); cs = np.concatenate([[0.0], np.cumsum(g.d_up.to_numpy())])
    k = np.searchsorted(ms, q.s.to_numpy(np.int64)[ix], side="left")
    net[ix] = cs[k]
q["net_up"] = net
q["held_up"] = np.where(q.net_up > 0, 1.0, np.where(q.net_up < 0, 0.0, np.nan))
for h, g in q.groupby("half"):
    ok = g.held_up.notna(); okp = g.P.notna()
    both = ok & okp
    agree = both & (g.held_up == g.P)
    res[h] = {"n": int(len(g)), "flat_share": float((~ok).mean()),
              "post_on_held": float((g.held_up[ok] == g.y[ok]).mean()),
              "posture": float((g.P[okp] == g.y[okp]).mean()),
              "posture_when_flat": float((g.P[okp & ~ok] == g.y[okp & ~ok]).mean()),
              "agree_share": float(agree.sum() / both.sum()),
              "acc_when_agree": float((g.P[agree] == g.y[agree]).mean()),
              "posture_when_disagree": float((g.P[both & ~agree] == g.y[both & ~agree]).mean()),
              "held_when_disagree": float((g.held_up[both & ~agree] == g.y[both & ~agree]).mean())}
print(json.dumps(res, indent=1))
(Path(__file__).resolve().parent.parent / "results/iter14_qu_inventory.json").write_text(json.dumps(res, indent=1))
