"""Iteration 10 (late): the entry side on the fresh development block 10-31 00:00-06:00 UTC and, for comparison, on the
lot, with sigma-free rules only: "buy the Chainlink favourite" (sign of ln(CL/K)), "buy the market favourite" and "buy the
cheaper side" (last clean print at b - 3). Entry fill = the wallet holds nothing in the window yet (own activity before
the fill's block second). Classes from the calldata original size (a1_0006_class cache for 00-06; r7_side tables for the
lot). Prediction (from the lot result, written before this ran): entries follow the Chainlink favourite more than later
fills do, in both ladders."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE))
import final_rule as F  # noqa: E402
import cl_source  # noqa: E402
import a1_0006 as B  # noqa: E402

C = ROOT / ".cache/re/directional-maker"


def rules(df):
    x = np.log(df.cl.to_numpy(float) / df.K.to_numpy(float))
    m = df.mid_up.to_numpy(float)
    y = df.is_up.to_numpy() == 1
    return {"n": int(len(df)), "cl_favourite": round(float(np.mean((x > 0) == y)), 3), "market_favourite": round(float(np.mean((m > 0.5) == y)), 3),
            "cheaper": round(float(np.mean((m < 0.5) == y)), 3)}


def main():
    act = B.fills()
    act["tx"] = act.transactionHash.str.lower()
    od = pd.read_parquet(C / "calldata" / "it10_0006_orders.parquet")
    om = od.drop_duplicates(["tx", "wn", "token"]).set_index(["tx", "wn", "token"]).orig
    act["orig"] = [om.get((t, w, str(a)), np.nan) for t, w, a in zip(act.tx, act.w, act.asset)]
    act["is_up"] = (act.outcome == "Up").astype(int)
    act = act.sort_values("timestamp")
    # entry: no own BUY in the window before this block second
    first_ts = act.groupby(["w", "st"]).timestamp.transform("min")
    act["entry"] = act.timestamp == first_ts
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    w = F._windows(B.A - 300, B.B + 300)
    w = w[(w.start_ts >= B.A) & (w.start_ts < B.B)]
    ptb = F._ptb(w)
    tk = F._tapes(w, pm, B.B + 600, local=False)
    ctx = set(F._txint(act.transactionHash.str.lower()))
    clean = tk[~tk.tx.isin(ctx)].copy()
    up = dict(zip(w.cid, w.up_token.astype(str)))
    clean["pup"] = np.where(clean.asset.astype(str) == clean.cid.astype(str).map(up), clean.price.astype(float), 1 - clean.price.astype(float))
    G = {k: (g.ts.to_numpy(), g.pup.to_numpy()) for k, g in clean.sort_values("ts", kind="stable").groupby("cid", observed=True)}
    mids = []
    for r in act.itertuples(index=False):
        g = G.get(r.conditionId)
        if g is None:
            mids.append(np.nan)
            continue
        j = np.searchsorted(g[0], int(r.timestamp) - 3, side="right") - 1
        mids.append(g[1][j] if j >= 0 and g[0][j] >= r.st - 60 else np.nan)
    act["mid_up"] = mids
    act["K"] = act.st.map(ptb)
    clv = cl_source.cl_values((act.timestamp.astype(np.int64) - 4).unique(), fetch=False)
    act["cl"] = (act.timestamp.astype(np.int64) - 4).map(clv)
    h = act.dropna(subset=["cl", "K", "mid_up"]).copy()
    o = h.orig.fillna(-1)
    h["c"] = np.where(o.isin([500, 1000, 2000]), "500", np.where(o.isin([62, 61.99, 250, 125]), "62_250", "other"))
    out = {"dev1031_0006": {}}
    for c in ("500", "62_250"):
        out["dev1031_0006"][f"{c}|entry"] = rules(h[(h.c == c) & h.entry])
        out["dev1031_0006"][f"{c}|later"] = rules(h[(h.c == c) & ~h.entry])
    out["dev1031_0006"]["all|entry"] = rules(h[h.entry])
    out["dev1031_0006"]["all|later"] = rules(h[~h.entry])
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_entry_0006.json", "w"), indent=1)


if __name__ == "__main__":
    main()
