"""Iteration 6 (X16 decision event across wallets, X14 per-wallet thresholds; panel-assumptions proposals 2 and 4).
Live development taker matches (live6_takers.parquet, server ms per tx) of the three wallets, grouped into fire events:
same window and outcome, consecutive matches less than 300 ms apart. Measures event size, wallet order, inter-wallet lags,
and participation per wallet as a function of the trigger strength (largest Binance BTC/ETH move toward the side over
[m0 - 600, m0 - 100) ms of the event's first match).
Usage: python fanout6.py"""
import os, sys, json, glob
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live6
C = live6.C


def main():
    tk = pd.read_parquet(C + "/live6_takers.parquet").sort_values("m")
    tk = tk.drop_duplicates(["tx", "wal"])
    ev_id = np.zeros(len(tk), int)
    last = {}
    eid = 0
    rows = tk[["start", "is_up", "m"]].to_numpy()
    for i, (st, u, m) in enumerate(rows):
        k = (st, u)
        if k in last and m - last[k][1] < 300:
            ev_id[i] = last[k][0]
        else:
            eid += 1; ev_id[i] = eid
        last[k] = (ev_id[i], m)
    tk["ev"] = ev_id
    g = tk.groupby("ev")
    ev = g.agg(m0=("m", "min"), m1=("m", "max"), n=("wal", "size"), up=("is_up", "first"),
               wals=("wal", lambda s: "".join(sorted(set(s)))), first=("wal", "first"))
    res = {"taker_matches": int(len(tk)), "events": int(len(ev)), "event_size": ev.n.value_counts().sort_index().to_dict(),
           "wallet_sets": ev.wals.value_counts().head(8).to_dict(), "first_wallet": ev["first"].value_counts().to_dict()}
    # inter-wallet lags inside multi-wallet events
    lags = {}
    for e, x in g:
        if x.wal.nunique() < 2:
            continue
        x = x.sort_values("m")
        firsts = x.drop_duplicates("wal")
        w = firsts.wal.tolist(); t = firsts.m.tolist()
        for i in range(len(w) - 1):
            lags.setdefault(f"{w[i]}->{w[i + 1]}", []).append(t[i + 1] - t[i])
    res["lags_ms"] = {k: {"n": len(v), "median": float(np.median(v)), "p10": float(np.quantile(v, 0.1)), "p90": float(np.quantile(v, 0.9))} for k, v in lags.items() if len(v) >= 5}
    # trigger strength of the event (largest Binance BTC/ETH-in-BTC-units move toward the side, [m0-600, m0-100))
    feeds = {}
    for v, sym in [("bnf", "BTCUSDT"), ("bnf", "ETHUSDT"), ("bns", "BTCUSDT"), ("bns", "ETHUSDT")]:
        s = live6.series(sorted(glob.glob(f"{live6.P}/rest6_{v}_{sym}_*.parquet")))
        if s is not None:
            feeds[f"{v}_{sym[:3]}"] = s
    m0 = ev.m0.to_numpy(np.int64); upv = np.where(ev.up.to_numpy(bool), 1.0, -1.0)
    mv = []
    for k, (T, p) in feeds.items():
        x = live6.move_bp(T, p, m0, 500, 100) * upv
        mv.append(x / (1.235 if "ETH" in k else 1.0))
    ev["strength"] = np.nanmax(np.vstack(mv), axis=0) if mv else np.nan
    bins = [-np.inf, 0.1, 0.5, 1.0, 2.0, np.inf]
    ev["sbin"] = pd.cut(ev.strength, bins, labels=["<=0.1", "0.1-0.5", "0.5-1", "1-2", ">2"])
    part = {}
    for w in ("DS", "GF", "XM"):
        ev[w] = ev.wals.str.contains(w)
        part[w] = {str(b): round(float(x[w].mean()), 3) for b, x in ev.groupby("sbin", observed=True)}
    res["participation_by_strength_bp"] = part
    res["events_by_strength"] = {str(b): int(len(x)) for b, x in ev.groupby("sbin", observed=True)}
    res["mean_event_size_by_strength"] = {str(b): round(float(x.n.mean()), 3) for b, x in ev.groupby("sbin", observed=True)}
    return res


if __name__ == "__main__":
    res = main()
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_fanout_iter6.json"), "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:3000])
