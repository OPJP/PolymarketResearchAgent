"""X211 step 2 (simplified follower-free outcome): the dark new-high decisions of dark_newhigh.py split by whether any
non-own maker JOINED the new top within 2 s (an order of another maker signed in (t, t + 2 s] on the same token at the new
top +-1c as a BUY, or on the complement at 1 - top +-1c as a SELL; full matched-order record of its markets, calldata of
every public tx, 16-22 Oct). If the joiner-free dark new highs still move the clean print their way, the dark decisions
are value updates rather than follower effects. Output: results/dark_joinerfree.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter4"))
from queue_replay import load_record  # noqa: E402

SP = Path(r"C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/m14/dark_split.parquet")
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def main():
    d = pd.read_parquet(SP).sort_values(["tok", "t"])
    pm = d.groupby("tok").top.transform(lambda x: x.shift(1).rolling(3, min_periods=1).max())
    d["new_high"] = (d.dtop > 0) & (d.top > pm + 1e-9)
    q = d[d.new_high & d.vis.isin(["dark", "visible_agree"])].copy()
    cd, _ = load_record()
    cd = cd[(cd.idx >= 0) & (cd.maker.str.lower() != W) & (cd.sign_ms > 1.7e12)].drop_duplicates(["tx", "idx"])
    cd["tok"] = cd.token_id.astype(str)
    # complement token of each market
    o = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/orders.parquet", columns=["cid", "oi", "token_id"]).drop_duplicates("token_id")
    comp = {}
    for cid, g in o.groupby("cid"):
        t = dict(zip(g.oi, g.token_id.astype(str)))
        if 0 in t and 1 in t:
            comp[t[0]], comp[t[1]] = t[1], t[0]
    by_tok = {t: (g.sign_ms.to_numpy(float), g.price.to_numpy(float), g.side.to_numpy(int)) for t, g in cd.groupby("tok")}
    joined = []
    for r in q.itertuples():
        tk = str(r.tok)
        j = False
        a = by_tok.get(tk)
        if a is not None:
            s, p, sd = a
            m = (s > r.t) & (s <= r.t + 2000) & (sd == 0) & (np.abs(p - r.top) <= 0.01 + 1e-9)
            j = bool(m.any())
        if not j and tk in comp:
            b = by_tok.get(comp[tk])
            if b is not None:
                s, p, sd = b
                m = (s > r.t) & (s <= r.t + 2000) & (sd == 1) & (np.abs((1 - p) - r.top) <= 0.01 + 1e-9)
                j = bool(m.any())
        joined.append(j)
    q["joined"] = joined
    out = {}
    for per in ("BUILD", "VALIDATE"):
        x = q[q.period == per]
        o2 = {}
        for nm, m in (("dark_new_high_all", x.vis == "dark"), ("dark_new_high_joinerfree", (x.vis == "dark") & ~x.joined),
                      ("dark_new_high_joined", (x.vis == "dark") & x.joined), ("visible_new_high_joinerfree", (x.vis == "visible_agree") & ~x.joined)):
            y = x[m]
            o2[nm] = {"n": int(len(y)), "m10_c": round(float(y.m10.mean()), 2), "m60_c": round(float(y.m60.mean()), 2),
                      "share_up60": round(float((y.m60 > 0).mean()), 3), "share_down60": round(float((y.m60 < 0).mean()), 3)}
        o2["joined_share_dark"] = round(float(x.loc[x.vis == "dark", "joined"].mean()), 3)
        out[per] = o2
    (RES / "dark_joinerfree.json").write_text(json.dumps(out, indent=1))
    for per, o2 in out.items():
        print(per, json.dumps(o2))


if __name__ == "__main__":
    main()
