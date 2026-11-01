"""Examiner r1: exit / inventory and income checks on the h1 lot (exam HTTP cache only):
  - non-TRADE activity of the three wallets (MERGE, SPLIT, REDEEM, CONVERSION, REWARD, MAKER_REBATE, TAKER_REBATE, YIELD) on the lot days
    and the day after each (rebates are paid the next day), counts and USDC by type, wallet and day;
  - the wallets' own SELL fills on chain (the frozen cluster_fills keeps BUY rows only): re-read the cached OrderFilled logs of every
    lot chunk and count side == 1 rows of the wallets' own orders.
Usage: python an_activity.py OUT_JSON"""
import os, sys, json, glob, time
ARGS = sys.argv[1:]
assert os.environ.get("POLYREA_CACHE_DIR", "").replace("\\", "/").rstrip("/").endswith(".cache/exam/btc5m-bot")
ROOT = os.getcwd(); CODE = f"{ROOT}/research/reverse_engineering/btc5m-bot/code"; sys.path.insert(0, CODE); sys.path.insert(0, ROOT)
import numpy as np, pandas as pd
from polyrea.adapters.polymarket import PolymarketData
import final_rule as fr, rpc

EX = f"{ROOT}/.cache/exam/btc5m-bot"
LOT = [(1792713600, 1792800000), (1792886400, 1792972800), (1793059200, 1793145600), (1793232000, 1793318400)]
W = fr.WALLETS
TYPES = ("MERGE", "SPLIT", "REDEEM", "CONVERSION", "REWARD", "MAKER_REBATE", "TAKER_REBATE", "YIELD")


def main(out_json):
    pm = PolymarketData(); out = {"activity": {}, "sell_fills": {}}
    for w, nm in W.items():
        rows = []
        for a, b in LOT:
            r, _, cov = pm.activity(w, start=a, end=b + 86400, types=TYPES)
            rows += r
        d = pd.DataFrame(rows).drop_duplicates() if rows else pd.DataFrame(columns=["type"])
        if len(d):
            d["day"] = pd.to_datetime(d.timestamp, unit="s").dt.strftime("%Y-%m-%d")
            d["usdc"] = pd.to_numeric(d.get("usdcSize", 0), errors="coerce")
            out["activity"][nm] = {"by_type": {t: {"n": int(len(g)), "usdc": round(float(g.usdc.sum()), 2)} for t, g in d.groupby("type")},
                                   "by_type_day": {f"{t}|{dd}": round(float(g.usdc.sum()), 2) for (t, dd), g in d.groupby(["type", "day"])}}
        else:
            out["activity"][nm] = {}
        print(nm, "activity rows", len(d), flush=True)
    # SELL fills of the wallets' own orders (cached logs)
    pads = [rpc.pad(x) for x in W]
    for p in sorted(glob.glob(f"{EX}/chunks/*_*/evaluate.json")):
        a, b = map(int, os.path.basename(os.path.dirname(p)).split("_"))
        if not any(x <= a < y for x, y in LOT):
            continue
        b0, b1 = fr._find_block(a), fr._find_block(b)
        n_side = {0: 0, 1: 0}; by_w = {}
        for s in range(b0, b1, 3000):
            e = min(s + 2999, b1 - 1)
            for ex in fr.EXCHANGES:
                for l in fr._get_logs_chunked(ex, s, e, [rpc.TOPIC_V2, None, pads]):
                    r = fr._decode(l); n_side[r["side"]] = n_side.get(r["side"], 0) + 1
                    if r["side"] == 1:
                        by_w[W.get(r["owner"].lower(), r["owner"])] = by_w.get(W.get(r["owner"].lower(), r["owner"]), 0) + 1
        out["sell_fills"][str(a)] = {"buy_rows": n_side.get(0, 0), "sell_rows": n_side.get(1, 0), "sell_by_wallet": by_w}
        print("logs", a, n_side, flush=True)
    json.dump(out, open(out_json, "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main(ARGS[0])
