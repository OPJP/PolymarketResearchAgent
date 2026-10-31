"""Assemble cluster fills (on-chain, own orders) with window context. Dev period only (< H)."""
import glob, sys
import numpy as np, pandas as pd
H = 1792713600
C = "/home/user/PolymarketResearchAgent/.cache/re/btc5m-bot"
W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}


def load_fills():
    fs = sorted(glob.glob(f"{C}/chain/own/*.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    df = df.drop_duplicates(["tx", "li"])
    assert df.ts.max() < H
    df["wallet"] = df.owner.map(W)
    df["role"] = np.where(df.cp.str.endswith("e111180000d2663c0091e4f400237545b87b996b") | df.cp.str.endswith("e2222d279d744050d28e00520010520000310f59"), "T", "M")
    df["cp_wallet"] = df.cp.map(W).fillna("")
    buy = df.side == 0
    df["usdc"] = np.where(buy, df.mamt, df.tamt) / 1e6
    df["shares"] = np.where(buy, df.tamt, df.mamt) / 1e6
    df["price"] = df.usdc / df.shares
    df["fee_usd"] = df.fee / 1e6
    win = pd.read_parquet(f"{C}/windows.parquet")
    up = win[["cid", "start_ts", "end_ts", "up_token", "fee_rate", "up_payout"]].rename(columns={"up_token": "token"}).assign(is_up=True)
    dn = win[["cid", "start_ts", "end_ts", "down_token", "fee_rate", "up_payout"]].rename(columns={"down_token": "token"}).assign(is_up=False)
    tok = pd.concat([up, dn])
    df = df.merge(tok, on="token", how="left")
    df["rel"] = df.ts - df.start_ts
    df = df.sort_values(["block", "li"]).reset_index(drop=True)
    return df[["block", "ts", "tx", "li", "oh", "wallet", "role", "cp_wallet", "side", "token", "usdc", "shares", "price", "fee_usd", "cid", "start_ts", "end_ts", "rel", "is_up", "fee_rate", "up_payout"]]


if __name__ == "__main__":
    df = load_fills()
    print(len(df), "unmapped tokens", df.cid.isna().mean().round(4), "sides", df.side.value_counts().to_dict())
    df.to_parquet(f"{C}/fills.parquet", index=False)
