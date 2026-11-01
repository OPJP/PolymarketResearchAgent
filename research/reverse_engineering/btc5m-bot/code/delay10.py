"""Iteration 10 (panel iter9 information P1 = X73): Polymarket's crypto TAKER DELAY in the decision record.
(1) D from the signing-to-match floor of FRESH-signed taker orders of other wallets (calldata of every cluster tx of 10-31
    12:00-17:56, it9/cd9.parquet; match = min server ms of the recorded trade with the same tx hash: btc5m_clob_raw2 from 14:55,
    clob_crypto before), per hour; (2) per-wallet floor of the gap between consecutive cluster taker matches (D + RTT if a
    wallet waits for each delayed order); (3) the point-in-time clean live vote: the frozen exam-feed vote (final_rule._live_vote)
    over [a - 500, a - delta) with a = m - D (D = 150, delta = 30 -> [m - 650, m - 180)) and neighbours, against the frozen
    [m - 600, m - 100); (4) the price as o's ask at m - L for L = 50 (frozen), 150 (= a), 180 (= a - delta), 250.
Usage: python delay10.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import final_rule as FR

C = L.C
W4 = "0xd84403efd50b49a1d8a7181627e00307e6ea5908"
DEV = [(1793404800, 1793426400), (1793448000, 1793469600)]  # 10-31 00-06, 12-18 (development blocks)


def main(out):
    res = {}
    # ---- match ms by tx hash: raw2 (from 14:55) and clob_crypto (shared recorder)
    mt = {}
    for feed in ("btc5m_clob_raw2", "clob_crypto"):
        for r in L.recs(feed, 1793448000, 1793469600):
            if r.get("k") == "x" and r.get("h"):
                h = r["h"].lower(); s = int(r["s"])
                if h not in mt or s < mt[h][0]:
                    mt[h] = (s, feed)
    cd = pd.read_parquet(C + "/it9/cd9.parquet")
    cd["txl"] = cd.tx.str.lower()
    cd["m"] = cd.txl.map(lambda h: mt.get(h, (np.nan, None))[0]); cd["feed"] = cd.txl.map(lambda h: mt.get(h, (np.nan, None))[1])
    ops = set(L.W) | {W4}
    ot = cd[(cd.role == "T") & ~cd.maker.isin(ops) & cd.m.notna()].copy()
    ot["dt"] = ot.m - ot.sign_ms
    fr = ot[(ot.dt > -500) & (ot.dt < 2000)]
    res["fresh_other_takers"] = {"n_with_match_ms": int(len(ot)), "n_dt_-500_2000": int(len(fr)),
                                 "n_dt<0": int((fr.dt < 0).sum()), "n_0_150": int(((fr.dt >= 0) & (fr.dt < 150)).sum()),
                                 "n_150_180": int(((fr.dt >= 150) & (fr.dt < 180)).sum()), "n_180_250": int(((fr.dt >= 180) & (fr.dt < 250)).sum()),
                                 "q_of_0_2000": [float(x) for x in np.percentile(fr[fr.dt >= 0].dt, [1, 5, 10, 25, 50])],
                                 "by_feed": fr.groupby("feed").dt.apply(lambda x: [float(v) for v in np.percentile(x[x >= 0], [1, 5, 10])] if (x >= 0).sum() > 20 else None).to_dict()}
    fr = fr.assign(hour=(fr.m // 3600000).astype(int))
    res["fresh_other_takers"]["by_hour_q1_q5_min>=0_n"] = {str(pd.to_datetime(h * 3600, unit="s"))[11:16]: [float(np.percentile(g[g.dt >= 0].dt, 1)), float(np.percentile(g[g.dt >= 0].dt, 5)),
                                                                                                         float(g[g.dt >= 0].dt.min()), int(len(g))] for h, g in fr.groupby("hour") if (g.dt >= 0).sum() >= 30}
    # per signer wallet minimum (fast wallets)
    mins = fr[fr.dt >= 0].groupby("maker").dt.agg(["min", "size"]).query("size >= 15").sort_values("min").head(12)
    res["fresh_other_takers"]["fastest_wallet_minima"] = {k[:10]: [float(v["min"]), int(v["size"])] for k, v in mins.iterrows()}
    # ---- per-wallet gap floor between consecutive cluster taker matches
    cl = cd[(cd.role == "T") & cd.maker.isin(list(L.W)) & cd.m.notna()].drop_duplicates("txl").copy()
    cl["w"] = cl.maker.map(L.W)
    gaps = {}
    for w, g in cl.groupby("w"):
        m = np.sort(g.m.to_numpy(np.int64)); d = np.diff(m)
        gaps[w] = {"n": int(len(m)), "min": float(d.min()) if len(d) else None, "q1_5_10_25": [float(x) for x in np.percentile(d, [1, 5, 10, 25])] if len(d) else None,
                   "n_gap<240": int((d < 240).sum())}
    allm = np.sort(cl.m.to_numpy(np.int64)); da = np.diff(allm)
    gaps["cluster_any_wallet"] = {"q1_5_10": [float(x) for x in np.percentile(da, [1, 5, 10])], "share_gap<100": round(float((da < 100).mean()), 4)}
    res["taker_match_gap_floor"] = gaps
    # ---- PIT-clean live vote and price (exam feeds), development intervals of 10-31 12-18 with exam recordings
    win = FR.load_windows(1793448000, 1793469600)
    win = win[win.up_payout.notna()].reset_index(drop=True)
    st = win.start_ts.to_numpy()
    keep = np.zeros(len(win), bool)
    for a, b in DEV:
        keep |= (st >= a) & (st < b)
    win = win[keep].reset_index(drop=True)
    fills = FR.cluster_fills(1793448000, 1793469600, win)
    res["fills"] = int(len(fills))
    scans = {}
    for nm, w in (("frozen_600_100", (600, 100)), ("pit_650_180 (a=m-150, delta=30)", (650, 180)), ("pit_650_150 (a=m-150, delta=0)", (650, 150)),
                  ("pit_700_200", (700, 200)), ("pit_750_250", (750, 250)), ("pit_800_300", (800, 300))):
        FR.LIVE_VOTE_WIN_MS = w
        for a, b in ((1793462640, 1793469300),):  # 16:04-17:55, exam feeds start 16:03
            v = FR._live_vote(fills, win, a, b)
            if v:
                scans[nm] = {k: v.get(k) for k in ("n_taker_matches", "cover", "agree_on_voted", "placebo_agree", "placebo_cover")}
                scans[nm]["full_coverage"] = (v.get("full_coverage") or {}).get("accuracy")
                scans[nm]["by_wallet"] = v.get("by_wallet")
    FR.LIVE_VOTE_WIN_MS = (600, 100)
    res["live_vote_window_scan_16:04-17:55"] = scans
    pr = {}
    for L_ in (50, 100, 150, 180, 250, 400):
        FR.PRE_MATCH_MS = float(L_)
        t = FR._live_touch(fills, win, 1793462640, 1793469300)
        if t:
            pr[str(L_)] = {k: t.get(k) for k in ("n_taker_orders", "within_1tick_ask_match", "exact_ask_match")}
    FR.PRE_MATCH_MS = 50.0
    res["price_ask_at_m_minus_L_16:04-17:55"] = pr
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))[:6000])


if __name__ == "__main__":
    main(sys.argv[1])
