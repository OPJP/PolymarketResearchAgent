"""Iteration 3: does ANY public Polymarket trace of the same game event precede the wallet's taker signing?

Server clock, dev block (dev-unit markets the wallet traded; own recorder where it covers a token, else clob_wallets).
For each wallet taker order: (a) a trade message in any market of the same event in [sign - 1 s, sign); (b) a
near-touch book change (any level within 5c of the touch, either side) in any market of the same event in
[sign - 300 ms, sign) and in [sign - 100 ms, sign); (c) the same windows at random times in the same markets.
Output: results/presign_public.json
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, T0, read  # noqa: E402


def main():
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    m = m[m.wallet_trades > 0]
    tok, ev_of = {}, {}
    for r in m.itertuples():
        tok[r.tok0] = r.tok0
        tok[r.tok1] = r.tok0
        ev_of[r.tok0] = r.event
    tok0 = set(m.tok0)
    sh = read("clob_wallets", tok0, T0 + 12 * 3600, time.time())
    ow = read("tommy_cs2_near", tok0, T0 + 12 * 3600, time.time())
    own_first = {}
    for r in ow:
        if r["k"] in ("f", "pc"):
            own_first[r["a"]] = min(own_first.get(r["a"], r["s"]), r["s"])
    trades, changes = defaultdict(list), defaultdict(list)
    for r in sh + ow:
        a = r.get("a")
        if a not in tok0:
            continue
        e = ev_of[a]
        if r["k"] == "x":
            trades[e].append(r["s"])
        elif r["k"] == "pc":
            changes[e].append(r["s"])
        elif r["k"] in ("q",) and r["s"] < own_first.get(a, 1e18):
            changes[e].append(r["s"])
    trades = {e: np.unique(np.array(v, float)) for e, v in trades.items()}
    changes = {e: np.unique(np.array(v, float)) for e, v in changes.items()}
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    w = d[(d.idx == -1) & (d.maker == WALLET) & (d.sign_ms > 1.79e12) & (d.sign_ms < 1.8e12) & d.token_id.astype(str).isin(tok)].drop_duplicates("tx")
    w = w.assign(event=w.token_id.astype(str).map(lambda t: ev_of[tok[t]]))

    def has(arr, lo, hi):
        if arr is None or len(arr) == 0:
            return False
        i = np.searchsorted(arr, lo)
        return bool(i < len(arr) and arr[i] < hi)
    rng = np.random.default_rng(3)
    res = {}
    for lab in ("wallet", "random"):
        a1, b3, b1, n = [], [], [], 0
        for r in w.itertuples():
            E = r.event
            ch = changes.get(E)
            if ch is None or len(ch) == 0 or r.sign_ms < ch[0] + 2000 or r.sign_ms > ch[-1]:
                continue
            ts = [r.sign_ms] if lab == "wallet" else list(rng.uniform(ch[0] + 2000, ch[-1], 20))
            for t in ts:
                n += 1
                a1.append(has(trades.get(E), t - 1000, t))
                b3.append(has(ch, t - 300, t))
                b1.append(has(ch, t - 100, t))
        res[lab] = {"n": n, "trade_any_event_market_[-1s,0)": round(float(np.mean(a1)), 3),
                    "book_change_any_event_market_[-300ms,0)": round(float(np.mean(b3)), 3),
                    "book_change_any_event_market_[-100ms,0)": round(float(np.mean(b1)), 3)}
    json.dump(res, open(RES / "presign_public.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
