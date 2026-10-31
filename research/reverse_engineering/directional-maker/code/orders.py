"""Reconstruct the cluster's resting orders from on-chain OrderFilled logs and
describe them (BUILD period only unless --period validate).

Joins chain fills to data-api activity (exact timestamp, market, outcome) by
(tx, token, shares). Writes .cache/re/directional-maker/fills_enriched.parquet.
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".cache/re/directional-maker"
H = 1792713600
BUILD = (1791504000, 1792108800)
VALID = (1792108800, 1792713600)
NAMES = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
         "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}


def load_chain() -> pd.DataFrame:
    fs = sorted(glob.glob(str(OUT / "chain_fills_*.parquet")))
    df = pd.concat([pd.read_parquet(f) for f in fs]).drop_duplicates(["tx", "log_index"])
    df["wallet"] = df["maker"].map(NAMES)
    df["price"] = (df["usdc"] / df["shares"]).round(6)
    return df


def load_activity() -> pd.DataFrame:
    parts = []
    for n in NAMES.values():
        p = OUT / f"activity_{n}.parquet"
        if p.exists():
            a = pd.read_parquet(p)
            a["wallet"] = n
            parts.append(a)
    return pd.concat(parts) if parts else pd.DataFrame()


def enrich(chain: pd.DataFrame, act: pd.DataFrame) -> pd.DataFrame:
    a = act[act["type"] == "TRADE"].copy()
    a["asset"] = a["asset"].astype(str)
    # one tx can hold several fills of a wallet; map tx+asset -> market fields and timestamp
    meta = a.groupby(["transactionHash", "asset", "wallet"]).agg(ts=("timestamp", "min"), cid=("conditionId", "first"),
                                                                 outcome=("outcome", "first"), slug=("slug", "first")).reset_index()
    m = chain.merge(meta, left_on=["tx", "token_id", "wallet"], right_on=["transactionHash", "asset", "wallet"], how="left")
    m["ts"] = m["ts"].fillna(m["block_ts_interp"].round()).astype("int64")
    return m.drop(columns=["transactionHash", "asset"])


if __name__ == "__main__":
    chain = load_chain()
    act = load_activity()
    print("chain rows", len(chain), chain["role"].value_counts().to_dict(), "activity rows", len(act))
    m = enrich(chain, act)
    print("joined to activity", m["cid"].notna().mean().round(4))
    m.to_parquet(OUT / "fills_enriched.parquet", index=False)
