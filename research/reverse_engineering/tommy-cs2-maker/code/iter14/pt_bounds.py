"""X197 (mechanics panel iter-13 P4), steps 1 and 4 in simplified form: do wallet-free public trades bound the
wallet's quote tightly enough to add observations of its value?

Every public taker transaction without a wallet order (calldata_pub minus calldata_all, 16-22 Oct) that filled maker
BUY orders on token A (bids on A, direct or through mint matching) consumed A's bids down to p_worst = the lowest
filled maker BUY price on A in that tx. Under price priority the wallet then had no bid on A above p_worst at the match
time (bound: own top on A <= p_worst). Exact levels: the wallet's own filled maker BUY orders (B1). For each bound at
match time m: the wallet's latest exact level on A signed before m (within 60 s) and its next exact level signed after
m (within 60 s). Binding = the bound is within 1c above the next exact level (p_worst - next <= 1c); violated = the
previous exact level is above p_worst by more than 1c (its order was either gone or the bound is wrong). Counts per
market and the number of bounds per exact observation. Output: results/pt_bounds.json
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

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def main():
    wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx"]).tx)
    cd, _ = load_record()
    pub = cd[~cd.tx.isin(wtx) & (cd.idx >= 0) & (cd.side == 0) & (cd.fill > 0) & cd.m.notna()]
    b = pub.groupby(["tx", "tok"]).agg(m=("m", "first"), pw=("price", "min"), cid=("cid", "first")).reset_index()
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "price", "token_id", "role", "cid"])
    o = o[(o.role == "maker")].copy()
    o["tok"] = o.token_id.astype(str)
    ex = {k: (g.sign_ms.to_numpy(float), g.price.to_numpy(float)) for k, g in o.sort_values("sign_ms").groupby("tok")}
    rows = []
    for r in b.itertuples():
        x = ex.get(r.tok)
        if x is None:
            continue
        ts, ps = x
        j = np.searchsorted(ts, r.m, side="left")
        prev = ps[j - 1] if j - 1 >= 0 and r.m - ts[j - 1] <= 60000 else np.nan
        nxt = ps[j] if j < len(ts) and ts[j] - r.m <= 60000 else np.nan
        rows.append({"cid": r.cid, "tok": r.tok, "m": r.m, "pw": r.pw, "prev": prev, "next": nxt})
    X = pd.DataFrame(rows)
    out = {"bounds": int(len(X)), "markets": int(X.cid.nunique()) if len(X) else 0, "exact_levels": int(len(o))}
    if len(X):
        nx = X.dropna(subset=["next"])
        pv = X.dropna(subset=["prev"])
        gap_n = (nx.pw - nx.next) * 100
        gap_p = (pv.prev - pv.pw) * 100
        out.update({"with_next_exact_60s": int(len(nx)), "with_prev_exact_60s": int(len(pv)),
                    "binding_share_(pw - next <= 1c)": round(float((gap_n.round(6) <= 1.0).mean()), 3) if len(nx) else None,
                    "bound_below_next_exact_(pw < next)": round(float((gap_n.round(6) < 0).mean()), 3) if len(nx) else None,
                    "tight_share_(0 <= pw - next <= 1c)": round(float(((gap_n.round(6) >= 0) & (gap_n.round(6) <= 1.0)).mean()), 3) if len(nx) else None,
                    "exact_share_(pw == next)": round(float((gap_n.round(6) == 0).mean()), 3) if len(nx) else None,
                    "gap_pw_minus_next_c_quantiles": [round(float(q), 2) for q in np.quantile(gap_n, [0.1, 0.25, 0.5, 0.75, 0.9])] if len(nx) else None,
                    "violated_share_(prev > pw + 1c)": round(float((gap_p.round(6) > 1.0).mean()), 3) if len(pv) else None,
                    "bounds_per_exact_level": round(len(X) / max(len(o), 1), 2)})
    (RES / "pt_bounds.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
