"""Iteration 3: who follows the wallet on the same team, and how fast (the current 'pack', defined by behaviour)?

Dev block 10-31 (calldata_dev, signing clocks) and 16-22 Oct (calldata_pub + calldata_all): for each wallet taker
order, other taker orders on the same team in the same market signed in (0, 1.5 s] after it. Per follower address:
count, median lag, and the share of its own taker orders in these markets that follow the wallet this way.
Output: results/followers.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, PACK  # noqa: E402


def table(cd, oi_of, cid_of):
    tk = cd[(cd.idx == -1) & (cd.sign_ms > 1.7e12) & (cd.sign_ms < 1.8e12)].drop_duplicates("tx").copy()
    tk["tok"] = tk.token_id.astype(str)
    tk = tk[tk.tok.isin(oi_of)]
    tk["cid"] = tk.tok.map(cid_of)
    tk["team"] = np.where(tk.side == 0, tk.tok.map(oi_of), 1 - tk.tok.map(oi_of))
    w = tk[tk.maker == WALLET]
    o = tk[tk.maker != WALLET]
    rows = []
    for (c, t), g in w.groupby(["cid", "team"]):
        oo = o[(o.cid == c) & (o.team == t)]
        if len(oo) == 0:
            continue
        s = np.sort(g.sign_ms.to_numpy())
        for r in oo.itertuples():
            k = np.searchsorted(s, r.sign_ms) - 1
            if k >= 0 and 0 < r.sign_ms - s[k] <= 1500:
                rows.append((r.maker, r.sign_ms - s[k]))
    f = pd.DataFrame(rows, columns=["maker", "lag"])
    tot = o.groupby("maker").size()
    g = f.groupby("maker").agg(n=("lag", "size"), lag_p50=("lag", "median"), lag_p10=("lag", lambda v: np.percentile(v, 10)))
    g["share_of_its_takes"] = (g.n / tot.reindex(g.index)).round(3)
    g = g.sort_values("n", ascending=False).head(12)
    return {"wallet_takes": int(len(w)), "follow_rows": int(len(f)),
            "top": [{"maker": k[:10], "pack_iter1_2": k in PACK, "n": int(r.n), "lag_p10": int(r.lag_p10), "lag_p50": int(r.lag_p50),
                     "share_of_its_takes": float(r.share_of_its_takes)} for k, r in g.iterrows()]}


def main():
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "token_id", "oi"]).drop_duplicates("token_id")
    oi_of = dict(zip(o.token_id.astype(str), o.oi))
    cid_of = dict(zip(o.token_id.astype(str), o.cid))
    parts = [pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "side", "token_id", "sign_ms"])]
    for p in (OUT / "calldata_pub").glob("*.parquet"):
        parts.append(pd.read_parquet(p, columns=["tx", "idx", "maker", "side", "token_id", "sign_ms"]))
    res = {"hist_16_22": table(pd.concat(parts), oi_of, cid_of)}
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    oi2, cid2 = {}, {}
    for r in m.itertuples():
        oi2[r.tok0], oi2[r.tok1] = 0, 1
        cid2[r.tok0], cid2[r.tok1] = r.cid, r.cid
    res["dev_10_31"] = table(pd.read_parquet(OUT / "calldata_dev.parquet"), oi2, cid2)
    json.dump(res, open(RES / "followers.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
