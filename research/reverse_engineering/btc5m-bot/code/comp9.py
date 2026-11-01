"""Iteration 9 (X72 / panel-information P3 with identities): WHO takes the liquidity at the flagged instants the cluster skips,
and does a competitor's presence change the cluster's decision? Interval C (10-31 16:33-17:55, development), FULL hazard on the
decision label fit on A. Taker wallets from data-api /trades (takerOnly, cached adapter) by tx hash. For the top 3% of the score:
the wallets buying o in [t + 100, t + 600) when the cluster did not decide vs when it did; concentration; and P(decision | flagged)
when each top competitor traded on the window in [t - 2000, t) vs not.
Usage: python comp9.py OUT_JSON"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT); sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import sealed
from polyrea.adapters.polymarket import PolymarketData, GAMMA_API
import live_lab as L
import stale9
from sklearn.linear_model import LogisticRegression

C = L.C
OPER = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9",
        "0xd84403efd50b49a1d8a7181627e00307e6ea5908"}


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    gA, _, _ = stale9.grid(*stale9.IV["A"], lost); gC, tkC, _ = stale9.grid(*stale9.IV["C"], lost)
    dA = stale9.stack(gA, 2.0, "any"); dC = stale9.stack(gC, 2.0, "any")
    XA, XC = stale9.X_of(dA, "full"), stale9.X_of(dC, "full")
    mu, sd = XA.mean(0), XA.std(0) + 1e-9
    p = LogisticRegression(max_iter=3000).fit((XA - mu) / sd, dA.y_dec).predict_proba((XC - mu) / sd)[:, 1]
    c0, c1 = stale9.IV["C"]
    starts = sorted(set(int(x) for x in dC.st.unique()))
    for s in starts:
        assert not sealed.is_sealed(s, "btc5m-bot"), s
    pm = PolymarketData()
    cid = {}
    slugs = [f"btc-updown-5m-{s}" for s in starts]
    for i in range(0, len(slugs), 25):
        d, _ = pm.http.get_json(f"{GAMMA_API}/events", [("slug", s) for s in slugs[i:i + 25]] + [("limit", 50)], adapter="gamma.events", max_age=7 * 86400)
        for e in d or []:
            for m in e.get("markets") or []:
                cid[int(str(e.get("slug")).rsplit("-", 1)[1])] = m.get("conditionId")
    tx2w = {}
    for s in starts:
        if not cid.get(s):
            continue
        rows, _, _ = pm.market_trades(cid[s], start=s - 300, end=s + 360, taker_only=True)
        for r in rows:
            h = (r.get("transactionHash") or "").lower()
            if h:
                tx2w[h] = (r.get("proxyWallet") or "").lower()
    print("windows", len(starts), "taker txs", len(tx2w), flush=True)
    # raw-feed BUY trades on C with tx hash, by window and outcome
    tr = []
    for r in L.recs("btc5m_clob_raw2", c0 - 60, c1 + 60):
        if r.get("k") == "x" and r.get("d") == "BUY" and r.get("h"):
            h = r["h"].lower(); w = tx2w.get(h)
            if w and w not in OPER:
                tr.append((int(r["s"]), int(r["m"]), int(r.get("u") or 0), w))
    T = pd.DataFrame(tr, columns=["s", "m", "u", "w"])
    by = {k: (g.s.to_numpy(np.int64), g.w.to_numpy()) for k, g in T.sort_values("s").groupby(["m", "u"])}
    byw = {k: (g.s.to_numpy(np.int64), g.w.to_numpy()) for k, g in T.sort_values("s").groupby("m")}
    t = dC.t.to_numpy(np.int64); st = dC.st.to_numpy(np.int64); o = dC.o.to_numpy(bool); y = dC.y_dec.to_numpy(bool)
    k = p >= np.quantile(p, 0.97)
    idx = np.where(k)[0]
    took_skip, took_dec = [], []
    recent = []
    for i in idx:
        arr = by.get((int(st[i]), int(o[i])))
        ws = []
        if arr is not None:
            j0 = np.searchsorted(arr[0], t[i] + 100); j1 = np.searchsorted(arr[0], t[i] + 600)
            ws = list(arr[1][j0:j1])
        (took_dec if y[i] else took_skip).extend(set(ws))
        a2 = byw.get(int(st[i]))
        rw = set()
        if a2 is not None:
            j0 = np.searchsorted(a2[0], t[i] - 2000); j1 = np.searchsorted(a2[0], t[i])
            rw = set(a2[1][j0:j1])
        recent.append(rw)
    cs = pd.Series(took_skip).value_counts(); cd = pd.Series(took_dec).value_counts()
    top = list(cs.index[:10])
    res = {"flagged": int(len(idx)), "P(decision)": round(float(y[idx].mean()), 4), "distinct_takers_at_skipped": int(len(cs)),
           "top10_share_of_skipped_takers": round(float(cs.iloc[:10].sum() / max(cs.sum(), 1)), 4),
           "top_competitors": [{"w": w[:10], "at_skipped": int(cs.get(w, 0)), "at_decided": int(cd.get(w, 0))} for w in top]}
    eff = []
    yy = y[idx]
    for w in top[:6]:
        pres = np.array([w in rw for rw in recent])
        if pres.any() and (~pres).any():
            eff.append({"w": w[:10], "P(dec|recent)": round(float(yy[pres].mean()), 4), "n_recent": int(pres.sum()), "P(dec|not)": round(float(yy[~pres].mean()), 4)})
    res["competitor_recent_2s_effect"] = eff
    nrec = np.array([len(rw) for rw in recent])
    res["P(decision) by number of distinct other takers in the last 2 s"] = {str(v): [round(float(yy[nrec == v].mean()), 4), int((nrec == v).sum())] for v in range(0, 5) if (nrec == v).any()}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
