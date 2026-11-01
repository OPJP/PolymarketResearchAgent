"""Iteration 2: Binance SPOT BTCUSDT aggTrades (ms timestamps, aggressor flag) via the public REST API for a seeded
random sample of whole UTC hours in BUILD and VALIDATE (all < H). One parquet per hour in
.cache/re/btc5m-bot/aggtrades/<hour0>.parquet with T (ms), p, q, m (True = buyer is maker = sell-initiated).
Usage: python fetch_aggtrades.py N_BUILD_HOURS N_VAL_HOURS [seed]"""
import os, sys, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT)
import numpy as np, pandas as pd
from polyrea.adapters.http import shared_client
H = 1792713600; B0, V0 = 1791504000, 1792108800
C = _ROOT + "/.cache/re/btc5m-bot/aggtrades"
URL = "https://api.binance.com/api/v3/aggTrades"


def hours(nb, nv, seed):
    rng = np.random.default_rng(seed)
    hb = rng.choice(np.arange(B0 + 2 * 86400, V0, 3600), nb, replace=False)  # BUILD hours from 10-11 on
    hv = rng.choice(np.arange(V0, H, 3600), nv, replace=False)
    return sorted(int(x) for x in np.r_[hb, hv])


def fetch_hour(h, h0):
    path = f"{C}/{h0}.parquet"
    if os.path.exists(path):
        return 0
    assert h0 + 3600 <= H
    d, _ = h.get_json(URL, {"symbol": "BTCUSDT", "startTime": h0 * 1000, "endTime": h0 * 1000 + 59_999, "limit": 1000}, adapter="binance.aggtrades", max_age=None)
    rows = list(d)
    while True:
        nxt = rows[-1]["a"] + 1
        d, _ = h.get_json(URL, {"symbol": "BTCUSDT", "fromId": nxt, "limit": 1000}, adapter="binance.aggtrades", max_age=None)
        d = [x for x in d if x["T"] < (h0 + 3600) * 1000]
        rows += d
        if len(d) < 1000:
            break
    df = pd.DataFrame({"T": [x["T"] for x in rows], "p": [float(x["p"]) for x in rows], "q": [float(x["q"]) for x in rows], "m": [bool(x["m"]) for x in rows]})
    df = df[(df["T"] >= h0 * 1000) & (df["T"] < (h0 + 3600) * 1000)].drop_duplicates()
    assert df["T"].max() < H * 1000
    df["q"] = df.q.astype(np.float32)
    df.to_parquet(path + ".tmp", index=False); os.replace(path + ".tmp", path)
    return len(df)


if __name__ == "__main__":
    nb, nv = int(sys.argv[1]), int(sys.argv[2]); seed = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    os.makedirs(C, exist_ok=True); h = shared_client(); t0 = time.time()
    hs = hours(nb, nv, seed)
    # interleave BUILD and VALIDATE so that a partial run has both
    hs = sorted(hs, key=lambda x: (hs.index(x) % 2, x))
    for i, h0 in enumerate(hs):
        n = fetch_hour(h, h0)
        print(i, h0, "BUILD" if h0 < V0 else "VAL", n, round(time.time() - t0), flush=True)
    print("DONE", round(time.time() - t0), flush=True)
