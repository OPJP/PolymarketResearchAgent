"""Iteration 5 (catalog C2, strong form): does the cluster copy another wallet? For 300 seeded-random VALIDATE windows
(taker tapes re-read through the cached data-api adapter), for every other wallet with >= 200 in-window taker BUY prints:
the share of the cluster's taker orders (first fill per order hash, block second s, outcome o) preceded by that wallet's
taker BUY of the SAME outcome at s - L (L = 0..10 s), against a placebo (the wallet's prints moved by +60 s within the
window), and the size ratio. A copied leader would show a consistent positive lag and a fixed size ratio; a co-racer
shows lag 0-2 s (block-time jitter). Writes results_c2_copy_iter5.json."""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from polyrea.adapters.polymarket import PolymarketData
from fetch_tapes2 import fetch_one
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
V0, H = 1792108800, 1792713600
W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
W4 = "0xd84403efd50b49a1d8a7181627e00307e6ea5908"
OUT = C + "/c2_tapes"

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    win = pd.read_parquet(f"{C}/windows.parquet")
    win = win[(win.start_ts >= V0) & (win.end_ts <= H)].sample(300, random_state=5)
    pm = PolymarketData()
    for r in win.itertuples():
        fetch_one(pm, r.cid, r.start_ts, r.end_ts, H, OUT)
    tp = []
    for r in win.itertuples():
        d = pd.read_parquet(f"{OUT}/{r.cid}.parquet")
        if not len(d) or "timestamp" not in d:
            continue
        d = d[(d.timestamp >= r.start_ts) & (d.timestamp < r.start_ts + 300) & (d.side == "BUY")]
        tp.append(pd.DataFrame({"cid": r.cid, "s": (d.timestamp - r.start_ts).to_numpy(int), "up": (d.outcome == "Up").to_numpy(),
                                "w": d.proxyWallet.str.lower().to_numpy(), "size": d["size"].to_numpy(float)}))
    tp = pd.concat(tp, ignore_index=True)
    f = pd.read_parquet(f"{C}/fills.parquet", columns=["cid", "ts", "oh", "role", "rel", "is_up", "shares", "wallet"])
    f = f[f.cid.isin(win.cid) & (f.role == "T")].sort_values("ts").drop_duplicates("oh")
    ords = pd.DataFrame({"cid": f.cid.to_numpy(), "s": f.rel.to_numpy(int), "up": f.is_up.to_numpy()})
    others = tp[~tp.w.isin(W)]
    cnt = others.w.value_counts()
    big = cnt[cnt >= 200].index.tolist()
    res = {"windows": int(len(win)), "cluster_taker_orders": int(len(ords)), "other_wallets_ge200": len(big), "wallets": {}}
    key_o = set(zip(ords.cid, ords.up, ords.s))
    rows = []
    for x in big:
        e = others[others.w == x]
        ev = set(zip(e.cid, e.up, e.s))
        evp = set((c, u, s + 60) for c, u, s in ev)  # placebo: shifted 60 s
        prof = {}
        for L in range(0, 11):
            hit = sum((c, u, s - L) in ev for c, u, s in key_o) / len(key_o)
            hp = sum((c, u, s - L) in evp for c, u, s in key_o) / len(key_o)
            prof[L] = (round(hit, 4), round(hp, 4))
        lead = sum(prof[L][0] for L in range(2, 11)); leadp = sum(prof[L][1] for L in range(2, 11))
        rows.append((x, int(cnt[x]), prof[0][0], prof[1][0], lead, leadp, round(float(e["size"].median()), 1)))
        res["wallets"][x] = {"n_prints": int(cnt[x]), "profile_lag_share_vs_placebo": prof, "median_size": round(float(e["size"].median()), 1)}
    df = pd.DataFrame(rows, columns=["w", "n", "lag0", "lag1", "lead2_10", "lead2_10_placebo", "med_size"])
    df["lead_lift"] = df.lead2_10 / df.lead2_10_placebo.replace(0, np.nan)
    res["top_by_lag0_1"] = df.assign(l01=df.lag0 + df.lag1).sort_values("l01", ascending=False).head(10).to_dict("records")
    res["top_by_lead2_10"] = df.sort_values("lead2_10", ascending=False).head(10).to_dict("records")
    res["fourth_wallet"] = res["wallets"].get(W4)
    json.dump(res, open(f"{R}/results_c2_copy_iter5.json", "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in res.items() if k != "wallets"}, indent=1, default=str))
