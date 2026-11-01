"""Iteration 8, X112 step 3: the Dota 2 module's components from the decoded calldata (10-22) and activity (10-22 and
the 10-31 12-18 development block, development units only): maker size, whole-cent prices, taker share, merges in the
300-s loop, pair cost, settlement PnL. Output: results/dota_module.json"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def main():
    ud = pd.read_parquet(OUT / "universe_dota.parquet")
    dcid = set(ud.cid)
    cd = pd.read_parquet(OUT / "calldata_all.parquet")
    cd = cd[(cd.maker.str.lower() == W) & cd.cid.isin(dcid)]
    o = cd.drop_duplicates(["salt", "sign_ms"])
    mk, tk = o[o.idx >= 0], o[o.idx == -1]
    res = {"orders": int(len(o)), "maker_orders": int(len(mk)), "taker_orders": int(len(tk)),
           "maker_size_top": mk.shares.round(0).value_counts().head(5).to_dict(),
           "maker_whole_cent": round(float((np.abs(mk.price * 100 - np.round(mk.price * 100)) < 1e-6).mean()), 3),
           "taker_size_median": round(float(tk.shares.median()), 1) if len(tk) else None,
           "fills_maker": int((cd.idx >= 0).sum()), "fills_taker": int((cd.idx == -1).sum()),
           "taker_usd_share": round(float((cd.loc[cd.idx == -1, "fill"] * cd.loc[cd.idx == -1, "price"]).sum() / (cd.fill * cd.price).sum()), 3)}
    a = pd.read_parquet(OUT / "activity_dev.parquet")
    b = pd.read_parquet(OUT / "activity_devblocks.parquet")
    for name, df in (("10-22", a), ("10-31_12-18_to_1455", b)):
        df = df[df.conditionId.isin(dcid)].copy()
        for c in ("size", "usdcSize"):
            df[c] = df[c].astype(float)
        mg = df[df.type == "MERGE"].sort_values("timestamp")
        allm = (a if name == "10-22" else b)
        allm = allm[allm.type == "MERGE"].copy()
        allm["timestamp"] = allm.timestamp.astype(float)
        # same 300-s loop: a Dota merge within 60 s of a CS2 merge pass
        cs = np.sort(allm.loc[~allm.conditionId.isin(dcid), "timestamp"].to_numpy(float))
        near = [bool(len(cs) and np.min(np.abs(cs - t)) <= 30) for t in mg.timestamp.astype(float)]
        tr = df[df.type == "TRADE"]
        sh = tr.groupby(["conditionId", "outcomeIndex"]).size.sum() if False else tr.groupby(["conditionId", "outcomeIndex"])["size"].sum().unstack(fill_value=0)
        pairs = sh.min(axis=1).sum() if len(sh) else 0
        res[name] = {"trades": int(len(tr)), "merges": int(len(mg)), "merge_usd": round(float(mg.usdcSize.sum()), 1),
                     "merges_within_30s_of_a_cs2_merge": round(float(np.mean(near)), 3) if near else None,
                     "paired_share_of_shares": round(float(2 * pairs / max(sh.to_numpy().sum(), 1e-9)), 3) if len(sh) else None,
                     "avg_buy_price": round(float(tr.usdcSize.sum() / tr["size"].sum()), 4) if len(tr) else None}
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "dota_module.json", "w"), indent=1)


if __name__ == "__main__":
    main()
