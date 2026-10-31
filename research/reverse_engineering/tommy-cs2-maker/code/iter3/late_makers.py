"""Iteration 3, mechanics panel P4 (X28) and a calldata proxy for canceller identity (X21 / X34).

In every wallet taker transaction (16-22 Oct, calldata_all; and the 10-31 dev block, calldata_dev), the maker orders
signed AFTER the wallet's FAK were posted into its 1-s in-play delay window. Their signing offsets (maker sign_ms -
wallet sign_ms, both signer clocks) show how fast other makers react to the same game event; a cancel-and-replace
maker that saw the event re-posts within tens of ms. Reported: offset distribution, the makers (address prefixes) with
the most late USD and their offset medians, their price relative to the wallet's limit, and the same for the pack's
taker transactions in the dev block (event time = the pack order's own signing). Output: results/late_makers.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, PACK  # noqa: E402


def late_table(cd, takers):
    tk = cd[(cd.idx == -1) & cd.maker.isin(takers)].drop_duplicates("tx")[["tx", "sign_ms", "price", "maker"]]
    tk = tk.rename(columns={"sign_ms": "t_sign", "price": "t_price", "maker": "taker"})
    mk = cd[cd.idx >= 0].merge(tk, on="tx")
    mk = mk[(mk.sign_ms > 1.7e12) & (mk.sign_ms < 1.8e12)]
    mk["off"] = mk.sign_ms - mk.t_sign
    mk["usd"] = mk.fill * mk.price
    return mk


def summarize(mk):
    late = mk[mk.off > 0]
    bins = [0, 20, 50, 100, 200, 500, 1000, 1500, 3000, 1e9]
    h = pd.cut(late.off, bins).value_counts().sort_index()
    out = {"maker_rows": int(len(mk)), "late_rows": int(len(late)), "late_usd_share": round(float(late.usd.sum() / max(mk.usd.sum(), 1e-9)), 3),
           "late_offset_ms_hist": {str(k): int(v) for k, v in h.items()},
           "late_offset_ms_p10_p25_p50_p75": [int(np.percentile(late.off, q)) for q in (10, 25, 50, 75)] if len(late) >= 5 else None}
    g = late.groupby("maker").agg(usd=("usd", "sum"), n=("usd", "size"), off_p50=("off", "median"),
                                 off_p10=("off", lambda v: np.percentile(v, 10)))
    tot = mk.groupby("maker").usd.sum()
    g["late_share_of_its_usd"] = (g.usd / tot.reindex(g.index)).round(3)
    g = g.sort_values("usd", ascending=False).head(10)
    out["top_late_makers"] = [{"maker": k[:10], "late_usd": round(float(r.usd)), "n": int(r.n), "off_p10": int(r.off_p10),
                               "off_p50": int(r.off_p50), "late_share_of_its_usd": float(r.late_share_of_its_usd)} for k, r in g.iterrows()]
    return out


def main():
    res = {}
    cd = pd.read_parquet(OUT / "calldata_all.parquet")
    res["hist_wallet_takes"] = summarize(late_table(cd, {WALLET}))
    dv = pd.read_parquet(OUT / "calldata_dev.parquet")
    dv = dv[(dv.sign_ms > 1.79e12) & (dv.sign_ms < 1.8e12)]
    res["dev_wallet_takes"] = summarize(late_table(dv, {WALLET}))
    res["dev_pack_takes"] = summarize(late_table(dv, PACK))
    # all other takers in the dev block (baseline: how late are makers in ordinary takers' transactions?)
    others = set(dv[(dv.idx == -1)].maker) - PACK - {WALLET}
    res["dev_other_takes"] = summarize(late_table(dv, others))
    json.dump(res, open(RES / "late_makers.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
