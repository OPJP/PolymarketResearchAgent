"""Descriptive decode of the wallet's filled orders (B1): lifetimes, sizes, price grid, two-sided structure,
signing cadence, counterparties. Development data only (16 Oct .. H). Prints a compact summary and writes
results/describe_orders.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RES, WALLET  # noqa: E402


def q(x, ps=(0.05, 0.25, 0.5, 0.75, 0.95)):
    x = pd.Series(x).dropna()
    return {f"p{int(p*100)}": round(float(x.quantile(p)), 3) for p in ps} | {"n": int(len(x))}


def main() -> None:
    o = pd.read_parquet(OUT / "orders.parquet")
    cd = pd.read_parquet(OUT / "calldata_all.parquet")
    res = {}
    mk = o[o["role"] == "maker"].copy()
    tk = o[o["role"] == "taker"].copy()
    res["n_orders"] = {"maker": len(mk), "taker": len(tk)}
    res["life_first_s"] = q(mk["life_first"])
    res["life_last_s"] = q(mk["life_last"])
    res["taker_life_s"] = q(tk["life_first"])
    res["size_top"] = mk["shares"].round(2).value_counts().head(15).to_dict()
    res["taker_size_top"] = tk["shares"].round(2).value_counts().head(10).to_dict()
    res["fill_frac"] = q(mk["fill_frac"])
    res["n_fills"] = q(mk["n_fills"])
    cents = (np.abs(mk["price"] * 100 - np.round(mk["price"] * 100)) < 1e-6)
    halfc = (np.abs(mk["price"] * 200 - np.round(mk["price"] * 200)) < 1e-6)
    res["price_on_cent"] = float(cents.mean())
    res["price_on_halfcent"] = float(halfc.mean())
    res["sig_type"] = mk["sig_type"].value_counts().to_dict()
    res["builder_nonzero"] = float((mk["builder"] != "0x" + "0" * 64).mean())
    res["metadata_nonzero"] = float((mk["metadata"] != "0x" + "0" * 64).mean())
    # signing cadence: orders signed in the same millisecond / within 50 ms in the same market
    mk = mk.sort_values(["cid", "sign_ms"])
    d = mk.groupby("cid")["sign_ms"].diff()
    res["inter_sign_ms_same_market"] = q(d)
    res["share_same_ms_as_prev"] = float((d == 0).mean())
    res["share_within_50ms"] = float((d <= 50).mean())
    # bursts: group orders of a market whose sign times are within 200 ms of the previous one
    mk["burst"] = (d.isna() | (d > 200)).cumsum()
    b = mk.groupby("burst").agg(cid=("cid", "first"), n=("price", "size"), n_out=("oi", "nunique"),
                                t=("sign_ts", "first"), pmin=("price", "min"), pmax=("price", "max"))
    res["burst_size"] = b["n"].value_counts().head(10).to_dict()
    res["burst_two_sided_share"] = float((b["n_out"] == 2).mean())
    # two-sided pairs: for bursts with both outcomes, sum of the best (highest) bid on each outcome
    two = mk[mk["burst"].isin(b.index[b["n_out"] == 2])]
    best = two.groupby(["burst", "oi"])["price"].max().unstack()
    if len(best):
        s = best.sum(axis=1)
        res["two_sided_bid_sum"] = q(s)
    # ladder: within a burst on one outcome, price gaps between levels
    lad = mk.groupby(["burst", "oi"])["price"].apply(lambda x: np.diff(np.sort(x.to_numpy())) if len(x) > 1 else np.array([]))
    gaps = np.concatenate([g for g in lad if len(g)]) if len(lad) else np.array([])
    res["ladder_gap"] = q(gaps)
    res["ladder_gap_top"] = pd.Series(np.round(gaps, 3)).value_counts().head(8).to_dict() if len(gaps) else {}
    # counterparties (takers in transactions where the wallet was a maker)
    wtx = set(cd.loc[(cd["maker"] == WALLET) & (cd["idx"] >= 0), "tx"])
    ct = cd[(cd["idx"] == -1) & cd["tx"].isin(wtx)]
    vc = ct["maker"].value_counts()
    res["counterparties"] = {"n_tx": int(len(ct)), "n_distinct": int(vc.size), "top10_share": float(vc.head(10).sum() / vc.sum()),
                             "top5": {k[:10]: int(v) for k, v in vc.head(5).items()}}
    ct = ct.assign(lat=ct["bts"] - ct["sign_ms"] / 1000)
    res["taker_sign_to_block_s"] = q(ct["lat"])
    # co-makers in the same transactions
    cm = cd[(cd["idx"] >= 0) & cd["tx"].isin(wtx) & (cd["maker"] != WALLET)]
    vm = cm["maker"].value_counts()
    res["co_makers"] = {"n_distinct": int(vm.size), "top5": {k[:10]: int(v) for k, v in vm.head(5).items()}}
    # by market type
    res["by_smt"] = mk.groupby("smt").agg(n=("price", "size"), life_med=("life_first", "median"), px_med=("price", "median")).round(3).to_dict("index")
    (RES / "results").mkdir(exist_ok=True)
    json.dump(res, open(RES / "results/describe_orders.json", "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
