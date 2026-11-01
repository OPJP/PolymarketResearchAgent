"""Iteration 3 (late): does Kraken XBT/USD (a Chainlink input; REST trades paged by time, so point-in-time safe) explain
the bot's side in seconds when none of the six archived series moved? Six sampled VALIDATE hours; one-sided seconds
from val_side_it3s.parquet; all moves over [s-4, s-1) (PIT horizon), Up-oriented, bp."""
import os, sys, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import httpx, numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
H = 1792713600
HOURS = [1792195200 + 15 * 3600, 1792281600 + 10 * 3600, 1792368000 + 20 * 3600, 1792454400 + 14 * 3600, 1792540800 + 2 * 3600, 1792627200 + 9 * 3600]
os.makedirs(f"{C}/venues/kraken", exist_ok=True)


def kraken_hour(h0):
    path = f"{C}/venues/kraken/{h0}.parquet"
    if os.path.exists(path):
        return pd.read_parquet(path)
    since = (h0 - 60) * 10**9; rows = []
    while True:
        j = httpx.get("https://api.kraken.com/0/public/Trades", params={"pair": "XBTUSD", "since": str(since), "count": 1000}, timeout=30).json()
        if j.get("error"):
            time.sleep(2); continue
        k = [x for x in j["result"] if x != "last"][0]; tr = j["result"][k]
        rows += [(float(t[2]), float(t[0])) for t in tr]
        assert max(t for t, _ in rows) < H
        if not tr or rows[-1][0] >= h0 + 3605:
            break
        since = int(j["result"]["last"]); time.sleep(1.0)
    df = pd.DataFrame(rows, columns=["t", "p"]).drop_duplicates()
    df = df[df.t < h0 + 3605]
    df["T"] = (df.t * 1000).round().astype(np.int64); df = df[["T", "p"]].sort_values("T")
    df.to_parquet(path, index=False)
    return df


def lpf(df):
    T = df["T"].to_numpy(np.int64); lp = np.log(df.p.to_numpy())
    return lambda t: np.where(np.searchsorted(T, t, side="left") > 0, lp[np.clip(np.searchsorted(T, t, side="left") - 1, 0, None)], np.nan)


S = pd.read_parquet(f"{C}/val_side_it3s.parquet"); S["s"] = (S.start_ts + S.rel).astype(np.int64)
SER = {"F": "fut", "O": "venues/okx", "B": "venues/bybit", "S": "venues/bnspot", "Y": "venues/bybitspot", "K": "venues/okxspot"}
out = []
for h0 in HOURS:
    g = S[(S.s >= h0 + 10) & (S.s < h0 + 3600)].copy()
    if g.empty:
        continue
    d0 = h0 // 86400 * 86400
    t_end = (g.s.to_numpy(np.int64) - 1) * 1000; t_beg = t_end - 3000
    mv = {}
    for p, sub in SER.items():
        fs = [f"{C}/{sub}/{d}.parquet" for d in (d0 - 86400, d0, d0 + 86400) if os.path.exists(f"{C}/{sub}/{d}.parquet")]
        df = pd.concat([pd.read_parquet(f, columns=["T", "p"]) for f in fs]).sort_values("T")
        f = lpf(df); mv[p] = (f(t_end) - f(t_beg)) * 1e4
    kr = kraken_hour(h0); fk = lpf(kr)
    g["kr3"] = (fk(t_end) - fk(t_beg)) * 1e4
    g["kr_m1"] = (fk(t_end + 1000) - fk(t_end)) * 1e4  # [s-1, s), non-PIT diagnostic
    st = np.stack([mv[p] for p in SER], axis=1)
    g["mx6"] = np.nanmax(np.abs(st), axis=1)
    out.append(g)
    print("hour", h0, len(g), len(kr), "kraken trades", flush=True)
D = pd.concat(out, ignore_index=True)
bot = np.where(D.truth_up == 1, 1.0, -1.0)
res = {"hours": HOURS, "n_seconds": int(len(D))}
for nm, mask in [("all", np.ones(len(D), bool)), ("no_move_six_series", D.mx6.to_numpy() <= 0.1)]:
    r = {"share": round(float(mask.mean()), 4)}
    for col in ("kr3", "kr_m1"):
        m = D[col].to_numpy(); k = mask & np.isfinite(m) & (np.abs(m) > 1e-9)
        r[col] = {"agree": round(float((np.sign(m[k]) == bot[k]).mean()), 4) if k.any() else None, "nonzero_share": round(float(k.sum() / max(mask.sum(), 1)), 4), "n": int(k.sum())}
    ok = ((D.ps.to_numpy() >= 0.5) == (D.truth_up.to_numpy() == 1))[mask]
    r["our_side_model_acc"] = round(float(ok.mean()), 4)
    res[nm] = r
json.dump(res, open(f"{R}/results_kraken_iter3.json", "w"), indent=1)
print(json.dumps(res))
