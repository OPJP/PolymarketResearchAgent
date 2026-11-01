"""Order-level table of the wallet's filled orders (B1), development data only (16 Oct .. H).

Joins the decoded calldata (.cache/re/tommy-cs2-maker/calldata/part_*.parquet) with block timestamps from the
OrderFilled logs. One row per wallet order (identity = salt + sign_ms + token + price + size):
  cid, oi (outcome index), smt, gs_ts, role (maker/taker), price, shares (original size), sign_ts (s),
  first_fill_ts, last_fill_ts, n_fills, filled (shares), fill_frac, n_tx
Also writes every other order in the same transactions (counterparties, co-makers): calldata_all.parquet.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import H, OUT, WALLET  # noqa: E402

EXCH = {"0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"}


def market_meta() -> pd.DataFrame:
    m = json.load(open(OUT / "markets_dev.json"))
    rows = []
    for cid, x in m.items():
        toks = x.get("clobTokenIds")
        toks = json.loads(toks) if isinstance(toks, str) else (toks or [])
        gs = pd.Timestamp(x.get("gameStartTime") or x.get("eventStartTime") or x.get("startDate"))
        for i, t in enumerate(toks):
            rows.append({"token_id": str(t), "cid": cid, "oi": i, "smt": x.get("sportsMarketType"),
                         "gs_ts": int(gs.timestamp()) if pd.notna(gs) else -1, "question": x.get("question"),
                         "event": (x.get("slug") or "").rsplit("-game", 1)[0]})
    return pd.DataFrame(rows)


def load_calldata() -> pd.DataFrame:
    parts = sorted((OUT / "calldata").glob("part_*.parquet"))
    d = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    d = d.drop_duplicates(["tx", "idx"])
    return d


def main() -> None:
    cd = load_calldata()
    logs = pd.read_parquet(OUT / "chain_fills_1792108800_1792713600.parquet")
    bts = logs.groupby("tx")["bts"].first()
    cd["bts"] = cd["tx"].map(bts)
    cd = cd[cd["bts"] < H]
    mm = market_meta()
    cd = cd.merge(mm[["token_id", "cid", "oi", "smt", "gs_ts", "event"]], on="token_id", how="left")
    cd.to_parquet(OUT / "calldata_all.parquet", index=False)
    w = cd[cd["maker"] == WALLET].copy()
    w["role"] = np.where(w["idx"] == -1, "taker", "maker")
    key = ["salt", "sign_ms", "token_id", "price", "shares"]
    g = w.groupby(key, sort=False)
    o = g.agg(cid=("cid", "first"), oi=("oi", "first"), smt=("smt", "first"), gs_ts=("gs_ts", "first"),
              event=("event", "first"), role=("role", "first"), first_fill_ts=("bts", "min"),
              last_fill_ts=("bts", "max"), n_fills=("tx", "size"), filled=("fill", "sum"),
              sig_type=("sig_type", "first"), builder=("builder", "first"), metadata=("metadata", "first")).reset_index()
    o["sign_ts"] = o["sign_ms"] / 1000.0
    o["fill_frac"] = o["filled"] / o["shares"]
    o["life_first"] = o["first_fill_ts"] - o["sign_ts"]
    o["life_last"] = o["last_fill_ts"] - o["sign_ts"]
    o.to_parquet(OUT / "orders.parquet", index=False)
    print("orders", len(o), o["role"].value_counts().to_dict(), "unmapped cid", int(o["cid"].isna().sum()))
    print("calldata rows", len(cd), "tx", cd["tx"].nunique(), "undecoded", int((cd["idx"] == -9).sum()))


if __name__ == "__main__":
    main()
