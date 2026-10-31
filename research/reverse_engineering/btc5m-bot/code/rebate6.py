"""Iteration 6 (X17 / B6, panel-assumptions critique 1): TAKER_REBATE and MAKER_REBATE activity rows per wallet, development
period only (end < H), compared with the wallet's own BTC 5m taker fees per UTC day (on-chain OrderFilled fee field,
fills.parquet, 10-09..H). Writes results_rebate_iter6.json.
Usage: python rebate6.py"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT)
from polyrea.adapters.polymarket import PolymarketData
H = 1792713600
C = _ROOT + "/.cache/re/btc5m-bot"
W = {"GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9",
     "W4": "0xd84403efd50b49a1d8a7181627e00307e6ea5908"}


def main():
    pm = PolymarketData()
    res = {}
    rows_all = []
    for name, w in W.items():
        rows, _, cov = pm.activity(w, start=1780272000, end=H - 1, types=("TAKER_REBATE", "MAKER_REBATE", "REFERRAL_REWARD"))
        df = pd.DataFrame(rows)
        if not len(df):
            res[name] = {"rows": 0}; continue
        df["ts"] = df.timestamp.astype(int); df["usd"] = df.usdcSize.astype(float)
        df["day"] = pd.to_datetime(df.ts, unit="s").dt.strftime("%Y-%m-%d")
        df["wal"] = name
        rows_all.append(df[["wal", "type", "ts", "day", "usd"]])
        res[name] = {t: {"rows": int((df.type == t).sum()), "usd": round(float(df.usd[df.type == t].sum()), 1), "first": str(df.day[df.type == t].min())}
                     for t in df.type.unique()}
    reb = pd.concat(rows_all)
    # own BTC 5m taker fees per wallet and UTC day from the on-chain fills
    f = pd.read_parquet(C + "/fills.parquet")
    f["wal"] = f.wallet
    f = f[f.wal.notna()]
    feecol = "fee_usd" if "fee_usd" in f.columns else None
    if feecol is None:
        f["fee_usd"] = f.fee.astype(float) / 1e6
    f["day"] = pd.to_datetime(f.ts, unit="s").dt.strftime("%Y-%m-%d")
    fees = f.groupby(["wal", "day"]).fee_usd.sum().rename("fee").reset_index()
    tr = reb[reb.type == "TAKER_REBATE"].copy()
    # a rebate row on day d pays for day d-1
    tr["fee_day"] = (pd.to_datetime(tr.day) - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
    m = tr.merge(fees, left_on=["wal", "fee_day"], right_on=["wal", "day"], how="inner", suffixes=("", "_f"))
    m["ratio"] = m.usd / m.fee
    res["taker_rebate_over_prev_day_fees"] = {w: {"n_days": int(len(g)), "median": round(float(g.ratio.median()), 4), "min": round(float(g.ratio.min()), 4), "max": round(float(g.ratio.max()), 4)}
                                             for w, g in m.groupby("wal")}
    val = reb[(reb.ts >= 1792108800 + 86400) & (reb.ts < H)]  # rows paid 10-17..10-22 for fees of 10-16..10-21 (VALIDATE days inside dev)
    res["validate_rebate_rows_10_17_to_10_22"] = {f"{w}_{t}": round(float(g.usd.sum()), 1) for (w, t), g in val.groupby(["wal", "type"])}
    res["fills_fee_total_validate_usd"] = round(float(f[(f.ts >= 1792108800) & (f.ts < H)].fee_usd.sum()), 1)
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_rebate_iter6.json"), "w"), indent=1)
    print(json.dumps(res, indent=1)[:4000])


if __name__ == "__main__":
    main()
