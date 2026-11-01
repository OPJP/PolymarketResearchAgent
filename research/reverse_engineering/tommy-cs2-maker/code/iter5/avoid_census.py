"""Iteration 5, assumptions panel iter4 P2 step 1 (X60): avoidance census of informed makers, 16-22 Oct.

For every maker present in >= 1% of in-play other-taker transactions of the wallet's markets: its presence rate in the
wallet's FAK transactions (calldata_all, wallet = taker) divided by its presence rate in other in-play FAK transactions
FAR (> 3 s) from any wallet take in the same market (calldata_pub). r < 0.3 = it is rarely there when the wallet takes
(it pulls, or never quotes, at the wallet's events). Event (market) bootstrap CI for r. For the low-r set: sigType,
whether it also takes, its order sizes, and its share of the wallet's events.
Output: results/avoid_census.json
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def main():
    cols = ["tx", "idx", "maker", "side", "sign_ms", "shares", "sig_type", "token_id", "block"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["cid", "gs_ts", "bts"])
    pub = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(OUT / "calldata_pub/*.parquet")))])
    o = pd.read_parquet(OUT / "orders.parquet", columns=["token_id", "cid", "gs_ts", "role", "sign_ms"])
    tm = o.drop_duplicates("token_id").set_index("token_id")[["cid", "gs_ts"]]
    pub = pub[pub.token_id.isin(tm.index)].copy()
    pub["cid"] = pub.token_id.map(tm.cid)
    pub["gs_ts"] = pub.token_id.map(tm.gs_ts)
    # taker rows
    wt = a[(a.idx == -1) & (a.maker == WALLET)]
    wtx = set(wt.tx)
    wsign = {c: np.sort(g.sign_ms.to_numpy(float)) for c, g in wt.groupby("cid")}
    pt = pub[pub.idx == -1].drop_duplicates("tx")
    pt = pt[(pt.sign_ms > 1.7e12) & (pt.sign_ms < 1.8e12) & (pt.sign_ms / 1000 >= pt.gs_ts + 60)]

    def far(r):
        x = wsign.get(r.cid)
        if x is None or len(x) == 0:
            return True
        j = np.searchsorted(x, r.sign_ms)
        d = min(abs(x[j] - r.sign_ms) if j < len(x) else 1e18, abs(x[j - 1] - r.sign_ms) if j > 0 else 1e18)
        return d > 3000

    pt = pt[[far(r) for r in pt.itertuples()]]
    far_tx = set(pt.tx)
    w_in = wt[(wt.sign_ms / 1000 >= wt.gs_ts + 60)]
    w_tx = set(w_in.tx)
    mk_w = a[(a.idx >= 0) & a.tx.isin(w_tx)][["tx", "maker", "cid"]].drop_duplicates()
    mk_o = pub[(pub.idx >= 0) & pub.tx.isin(far_tx)][["tx", "maker", "cid"]].drop_duplicates()
    n_w, n_o = len(w_tx), len(far_tx)
    pres_o = mk_o.groupby("maker").tx.nunique() / n_o
    pres_w = mk_w.groupby("maker").tx.nunique() / n_w
    cand = pres_o[pres_o >= 0.01].index
    rows = []
    rng = np.random.default_rng(0)
    w_by_c = mk_w.groupby("cid").tx.nunique()
    o_by_c = pt.groupby("cid").tx.nunique()
    cids = np.array(sorted(set(w_by_c.index) | set(o_by_c.index)))
    for m in cand:
        r = pres_w.get(m, 0.0) / pres_o[m]
        # market bootstrap
        wc = mk_w[mk_w.maker == m].groupby("cid").tx.nunique()
        oc = mk_o[mk_o.maker == m].groupby("cid").tx.nunique()
        bs = []
        for _ in range(500):
            pick = rng.choice(cids, len(cids))
            nw = w_by_c.reindex(pick).fillna(0).sum(); no = o_by_c.reindex(pick).fillna(0).sum()
            xw = wc.reindex(pick).fillna(0).sum(); xo = oc.reindex(pick).fillna(0).sum()
            if nw > 0 and no > 0 and xo > 0:
                bs.append((xw / nw) / (xo / no))
        st = pub[(pub.maker == m)].sig_type
        sizes = pub[(pub.maker == m) & (pub.idx >= 0)].shares.round(2).value_counts().head(4).index.tolist()
        takes = int(((pub.maker == m) & (pub.idx == -1)).sum())
        rows.append({"maker": m, "presence_other_far": round(float(pres_o[m]), 4), "presence_wallet_fak": round(float(pres_w.get(m, 0.0)), 4),
                     "ratio": round(float(r), 3), "ratio_ci95": [round(float(np.quantile(bs, 0.025)), 3), round(float(np.quantile(bs, 0.975)), 3)] if bs else None,
                     "sig_type": int(st.mode().iloc[0]) if len(st) else None, "top_sizes": sizes, "taker_orders": takes,
                     "markets": int(mk_o[mk_o.maker == m].cid.nunique())})
    R = pd.DataFrame(rows).sort_values("ratio")
    res = {"wallet_fak_txs": n_w, "other_far_fak_txs": n_o, "n_makers": int(len(R)), "low_ratio": R[R.ratio < 0.3].to_dict("records"),
           "ratio_quantiles": {q: round(float(R.ratio.quantile(q)), 3) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
           "top30_by_presence": R.sort_values("presence_other_far", ascending=False).head(30)[["maker", "presence_other_far", "ratio"]].to_dict("records")}
    (RES / "avoid_census.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "top30_by_presence"}, indent=1)[:6000])


if __name__ == "__main__":
    main()
