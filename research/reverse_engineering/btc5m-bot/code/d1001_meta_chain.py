"""Iteration 5: cluster fills for 2026-10-01 00:00..END UTC (BUILD side, < H): Gamma windows (token map) and on-chain V2
OrderFilled logs with topic2 = cluster order owner. Output: .cache/re/btc5m-bot/d1001/{windows,fills}.parquet.
Usage: python d1001_meta_chain.py END_HOURS"""
import os, sys, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import rpc
from fetch_chain import decode, W, H
from polyrea.workflows.updown_study import window_slugs, fetch_windows
from polyrea.analysis.updown import windows_from_markets

OUT = _ROOT + "/.cache/re/btc5m-bot/d1001"
DAY0 = 1790812800


def block_at(ts, lo=94700000, hi=94800000):
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if rpc.block_ts(mid) < ts:
            lo = mid
        else:
            hi = mid
    return hi


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    end_ts = DAY0 + int(float(sys.argv[1]) * 3600); assert end_ts < H
    t0 = time.time()
    markets = fetch_windows(window_slugs("btc", "5m", DAY0, end_ts))
    wins = windows_from_markets(markets)
    wdf = pd.DataFrame([{"cid": w.condition_id, "start_ts": w.start_ts, "end_ts": w.end_ts, "up_token": w.up_token, "down_token": w.down_token,
                         "fee_rate": w.fee_rate, "twap": w.twap_seconds, "up_payout": w.up_payout} for w in wins])
    wdf = wdf[(wdf.start_ts >= DAY0) & (wdf.end_ts <= end_ts)]
    wdf.to_parquet(f"{OUT}/windows.parquet", index=False)
    print("windows", len(wdf), round(time.time() - t0), flush=True)
    a, b = block_at(DAY0), block_at(end_ts) - 1
    print("blocks", a, b, flush=True)
    pads = [rpc.pad(x) for x in W.values()]
    rows = []
    for s in range(a, b + 1, 2000):
        e = min(s + 1999, b)
        for attempt in range(6):
            try:
                logs = rpc.call("eth_getLogs", [{"address": rpc.V2_EXCHANGES, "fromBlock": hex(s), "toBlock": hex(e), "topics": [rpc.TOPIC_V2, None, pads]}])
                break
            except Exception:
                time.sleep(5 * (attempt + 1))
        else:
            print("FAILED", s, e, flush=True); continue
        rows += [decode(l) for l in logs]
    df = pd.DataFrame(rows).drop_duplicates(["tx", "li"])
    assert df.ts.max() < H
    inv = {v.lower(): k for k, v in W.items()}
    df["wallet"] = df.owner.str.lower().map(inv)
    df["role"] = np.where(df.cp.str.endswith("e111180000d2663c0091e4f400237545b87b996b") | df.cp.str.endswith("e2222d279d744050d28e00520010520000310f59"), "T", "M")
    buy = df.side == 0
    df["usdc"] = np.where(buy, df.mamt, df.tamt) / 1e6
    df["shares"] = np.where(buy, df.tamt, df.mamt) / 1e6
    df["price"] = df.usdc / df.shares
    up = wdf[["cid", "start_ts", "up_token"]].rename(columns={"up_token": "token"}).assign(is_up=True)
    dn = wdf[["cid", "start_ts", "down_token"]].rename(columns={"down_token": "token"}).assign(is_up=False)
    df = df.merge(pd.concat([up, dn]), on="token", how="left")
    print("logs", len(df), "unmapped", round(df.cid.isna().mean(), 4), "buy share", round(buy.mean(), 4), flush=True)
    df = df[df.cid.notna()].copy(); df["is_up"] = df.is_up.astype(bool); df["rel"] = df.ts - df.start_ts
    df[["block", "ts", "tx", "li", "oh", "wallet", "role", "side", "token", "usdc", "shares", "price", "cid", "start_ts", "rel", "is_up"]].to_parquet(f"{OUT}/fills.parquet", index=False)
    print("fills", len(df), "wallets", df.wallet.value_counts().to_dict(), "roles", df.role.value_counts().to_dict(), round(time.time() - t0), "s", flush=True)
