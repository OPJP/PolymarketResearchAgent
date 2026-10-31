"""Iteration 5, mechanics panel iter4 P3 (X59): the event size schedule s_e(t) = clip(round(a + b X_e(t)), 50, 100).

CS2 maker orders (orders.parquet, 16-22 Oct, sizes >= 20: the 5-share start-up run of 10-16/17 dropped). Candidates X:
  own_pairs  = the event's paired shares so far, sum over its markets of min(S0, S1) from the wallet's own fills
               (block time <= signing; OWN STATE, allowed for the policy, reported as such);
  pub_usd    = the event's cumulative in-play taker USD on the public tape (txs with a wallet order excluded);
  elapsed    = minutes since game start.
One (a, b) per X fitted on BUILD (least absolute error on the clipped model); scored on VALIDATE: exact (round) and
within one share, over all CS2 maker orders and over the non-100 ones; baseline "always 100".
Start size: Spearman of the event's first maker size with pre-game taker USD ([gs - 1 h, gs), events_sel e_pre_v).
Output: results/size_schedule.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, stats

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
VAL0, H = 1792540800, 1792713600


def main():
    o = pd.read_parquet(OUT / "orders.parquet")
    o = o[(o.sign_ms > 1.7e12)].copy()
    cs2 = o.event.astype(str).str.startswith("cs2")
    mo = o[(o.role == "maker") & cs2 & (o.shares >= 20)].copy()
    f = pd.read_parquet(OUT / "chain_fills_1792108800_1792713600.parquet", columns=["bts", "tx", "token_id", "shares"])
    tm = o.drop_duplicates("token_id").set_index("token_id")[["cid", "oi", "event"]]
    f = f[f.token_id.isin(tm.index)].copy()
    f["cid"] = f.token_id.map(tm.cid)
    f["oi"] = f.token_id.map(tm.oi).astype(int)
    f["event"] = f.token_id.map(tm.event)
    wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx"]).tx)
    rows = []
    for ev, g in mo.groupby("event"):
        fe = f[f.event == ev].sort_values("bts")
        # own pairs path
        S = {}
        tt, pairs = [], []
        cur = 0.0
        for r in fe.itertuples():
            s0, s1 = S.get(r.cid, (0.0, 0.0))
            old = min(s0, s1)
            if r.oi == 0:
                s0 += r.shares
            else:
                s1 += r.shares
            S[r.cid] = (s0, s1)
            cur += min(s0, s1) - old
            tt.append(r.bts)
            pairs.append(cur)
        tt, pairs = np.array(tt, float), np.array(pairs, float)
        # public in-play USD path over the event's markets
        gs = float(g.gs_ts.min())
        pts, pus = [], []
        for cid in g.cid.unique():
            p = OUT / "tapes" / f"{cid}_tkw.parquet"
            if p.exists():
                d = pd.read_parquet(p, columns=["timestamp", "price", "size", "transactionHash"])
                d = d[~d.transactionHash.isin(wtx) & (d.timestamp >= gs)]
                pts.append(d.timestamp.to_numpy(float))
                pus.append((d.price * d["size"]).to_numpy(float))
        if pts:
            pt = np.concatenate(pts)
            pu = np.concatenate(pus)
            k = np.argsort(pt)
            pt, pu = pt[k], np.cumsum(pu[k])
        else:
            pt, pu = np.array([]), np.array([])
        for r in g.itertuples():
            s = r.sign_ms / 1000.0
            j = int(np.searchsorted(tt, s, side="right")) - 1
            jp = int(np.searchsorted(pt, s, side="right")) - 1
            rows.append({"event": ev, "gs": gs, "s": s, "size": float(r.shares), "own_pairs": pairs[j] if j >= 0 else 0.0,
                         "pub_usd": pu[jp] if jp >= 0 else 0.0, "elapsed": (s - gs) / 60.0})
    D = pd.DataFrame(rows)
    D["split"] = np.where(D.gs < VAL0, "BUILD", "VALIDATE")
    res = {"n": D.split.value_counts().to_dict(), "share_100": {sp: round(float((g["size"].round() == 100).mean()), 3) for sp, g in D.groupby("split")}}

    def model(par, x):
        return np.clip(np.round(par[0] + par[1] * x), 50, 100)

    for X in ("own_pairs", "pub_usd", "elapsed"):
        b = D[D.split == "BUILD"]
        x, y = b[X].to_numpy(float), b["size"].to_numpy(float)
        sc = np.nanmedian(x[x > 0]) if (x > 0).any() else 1.0
        best = None
        for a0 in (40, 50, 55, 60, 70):
            for b0 in np.geomspace(1e-4, 10, 30) / sc * 50:
                v = np.mean(np.abs(np.clip(a0 + b0 * x, 50, 100) - y))
                if best is None or v < best[0]:
                    best = (v, a0, b0)
        r = optimize.minimize(lambda p: np.mean(np.abs(np.clip(p[0] + p[1] * x, 50, 100) - y)), [best[1], best[2]], method="Nelder-Mead",
                              options={"xatol": 1e-9, "fatol": 1e-6, "maxiter": 4000})
        par = r.x
        out = {"a": round(float(par[0]), 3), "b": float(par[1])}
        for sp in ("BUILD", "VALIDATE"):
            d = D[D.split == sp]
            pred = model(par, d[X].to_numpy(float))
            yy = d["size"].to_numpy(float)
            non = np.round(yy) != 100
            out[sp] = {"exact": round(float(np.mean(np.round(yy) == pred)), 4), "within1": round(float(np.mean(np.abs(yy - pred) <= 1.0001)), 4),
                       "non100_exact": round(float(np.mean((np.round(yy) == pred)[non])), 4) if non.any() else None,
                       "non100_within1": round(float(np.mean((np.abs(yy - pred) <= 1.0001)[non])), 4) if non.any() else None,
                       "always100_exact": round(float(np.mean(np.round(yy) == 100)), 4)}
        res[X] = out
    # start size vs pre-game USD
    es = pd.read_parquet(OUT / "events_sel.parquet", columns=["event_slug", "e_pre_v"])
    first = D.sort_values("s").groupby("event").first().reset_index().merge(es, left_on="event", right_on="event_slug", how="left")
    ok = first.e_pre_v.notna()
    res["start_size_spearman_pre_usd"] = round(float(stats.spearmanr(first["size"][ok], first.e_pre_v[ok])[0]), 3)
    res["start_below_100_share"] = round(float((first["size"] < 99.5).mean()), 3)
    res["start_size_median_pre_usd_below_vs_at_100"] = [round(float(first[ok & (first["size"] < 99.5)].e_pre_v.median()), 0),
                                                        round(float(first[ok & (first["size"] >= 99.5)].e_pre_v.median()), 0)]
    (RES / "size_schedule.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
