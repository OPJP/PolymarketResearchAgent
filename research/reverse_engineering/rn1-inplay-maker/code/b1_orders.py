"""B1/B2: what the decoded orders say about RN1's quotes (development data only).

For every sampled transaction: RN1's own orders (maker or taker role), the counterparty taker order and the other
makers. Block timestamps from the OrderFilled-log days (exact per-block interpolation from anchors).
Prints summary statistics; writes results/b1_orders.json.
Usage: python b1_orders.py [p0] [p1]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import C, R, W, BUILD, VALID  # noqa: E402


def block_ts_map(days):
    parts = []
    for d in days:
        f = C / "chain" / f"chain_{d}.parquet"
        if f.exists():
            parts.append(pd.read_parquet(f, columns=["block", "ts"]))
    b = pd.concat(parts).drop_duplicates("block").sort_values("block")
    return b["block"].to_numpy(), b["ts"].to_numpy()


def load_cd(p0, p1):
    days = list(range(p0, p1, 86400))
    parts = [pd.read_parquet(C / "calldata" / f"cd_{d}.parquet") for d in days if (C / "calldata" / f"cd_{d}.parquet").exists()]
    cd = pd.concat(parts, ignore_index=True)
    cd = cd[cd["sel"] == "0x3c2b4399"].copy()
    acts = [pd.read_parquet(C / "activity" / f"act_{d}.parquet", columns=["transactionHash", "timestamp"]) for d in days
            if (C / "activity" / f"act_{d}.parquet").exists()]
    tmap = pd.concat(acts).drop_duplicates("transactionHash").set_index("transactionHash")["timestamp"]
    cd["bts"] = cd["tx"].map(tmap).astype(float)
    cd["sign_s"] = cd["sign_ms"] / 1000.0
    cd["age"] = cd["bts"] - cd["sign_s"]
    buy = cd["side"] == 0
    cd["px"] = np.where(buy, cd["maker_amount"] / cd["taker_amount"], cd["taker_amount"] / cd["maker_amount"])
    cd["shares"] = np.where(buy, cd["taker_amount"], cd["maker_amount"]) / 1e6
    cd["is_rn1"] = cd["maker"].str.lower() == W
    return cd


def q(x, qs=(0.05, 0.25, 0.5, 0.75, 0.95)):
    x = pd.Series(x).dropna()
    return {str(k): round(float(v), 3) for k, v in x.quantile(list(qs)).items()} | {"n": int(len(x))}


def main(p0=VALID[0], p1=VALID[1]):
    cd = load_cd(p0, p1)
    out = {"period": [p0, p1], "n_tx": int(cd["tx"].nunique()), "n_orders": int(len(cd))}
    rn = cd[cd["is_rn1"]]
    rm = rn[rn["role"] == "maker"]
    rt = rn[rn["role"] == "taker"]
    out["rn1_orders"] = {"maker": int(len(rm)), "taker": int(len(rt)), "sig_type": rn["sig_type"].value_counts().to_dict(),
                         "side": rn["side"].value_counts().to_dict(), "builder_nonzero": int((rn["builder"].str.strip("0") != "").sum()),
                         "metadata_nonzero": int((rn["metadata"].str.strip("0") != "").sum()), "signers": rn["signer"].value_counts().head(5).to_dict()}
    out["rn1_maker_age_s"] = q(rm["age"], (0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99))
    out["rn1_taker_age_s"] = q(rt["age"], (0.05, 0.25, 0.5, 0.75, 0.95))
    out["neg_age_share"] = float((rn["age"] < -2).mean())
    # taker orders hitting RN1's resting orders: the counterparties' latency (sign -> block), shows the delay
    txs_rm = set(rm["tx"])
    tk = cd[(cd["role"] == "taker") & cd["tx"].isin(txs_rm) & ~cd["is_rn1"]]
    out["taker_vs_rn1_age_s"] = q(tk["age"], (0.05, 0.25, 0.5, 0.75, 0.95))
    # other makers in RN1's maker transactions
    om = cd[(cd["role"] == "maker") & cd["tx"].isin(txs_rm) & ~cd["is_rn1"]]
    out["other_maker_age_s"] = q(om["age"], (0.05, 0.25, 0.5, 0.75, 0.95))
    # sizes and prices of RN1's resting orders
    out["rn1_maker_shares"] = q(rm["shares"], (0.05, 0.25, 0.5, 0.75, 0.95, 0.99))
    vc = rm["shares"].round(2).value_counts()
    out["rn1_maker_top_sizes"] = {str(k): int(v) for k, v in vc.head(15).items()}
    out["rn1_maker_share_of_top10_sizes"] = float(vc.head(10).sum() / len(rm))
    usd = (rm["px"] * rm["shares"]).round(0)
    out["rn1_maker_top_usd"] = {str(k): int(v) for k, v in usd.value_counts().head(10).items()}
    out["rn1_maker_fill_ratio"] = q(rm["fill"] / np.where(rm["side"] == 0, rm["maker_amount"], rm["maker_amount"]), (0.1, 0.25, 0.5, 0.75, 0.9))
    # price tick structure
    cents = (rm["px"] * 1000).round().astype(int) % 10
    out["rn1_maker_px_mill_digit"] = {str(k): int(v) for k, v in cents.value_counts().sort_index().items()}
    # signing ms fractions (loop cadence)
    ms = (rn["sign_ms"] % 1000)
    out["rn1_sign_ms_mod1000_hist10"] = np.histogram(ms, bins=10, range=(0, 1000))[0].tolist()
    # queue position of RN1 among makers in the tx
    pos = rm.merge(cd[cd["role"] == "maker"].groupby("tx").size().rename("nm"), left_on="tx", right_index=True)
    out["rn1_maker_pos"] = {"first_share": float((pos["pos"] == 0).mean()), "n_makers_median": float(pos["nm"].median())}
    # same price as other makers in the tx?  (all makers of a BUY taker are matched at their own limit)
    # salt structure (C8)
    salts = rn["salt"].astype(str)
    lens = salts.str.len()
    out["rn1_salt_digits"] = {str(k): int(v) for k, v in lens.value_counts().head(5).items()}
    s_num = pd.to_numeric(salts, errors="coerce")
    ratio = s_num / rn["sign_ms"]
    out["rn1_salt_over_sign_ms"] = q(ratio, (0.01, 0.25, 0.5, 0.75, 0.99))
    print(json.dumps(out, indent=1))
    (R / "results").mkdir(exist_ok=True)
    json.dump(out, open(R / "results" / f"b1_orders_{p0}_{p1}.json", "w"), indent=1)
    return cd


if __name__ == "__main__":
    a = [int(x) for x in sys.argv[1:3]]
    main(*a) if a else main()
