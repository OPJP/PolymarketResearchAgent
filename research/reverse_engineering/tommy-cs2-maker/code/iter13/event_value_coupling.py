"""X173 (information panel iter-12 P2), historical form on the filled record: one game value per EVENT? For the
wallet's same-tick map / match re-pricings (a map-book burst and a match-book burst of the same event signed within
+-5 ms), does the match-book change follow the public series sensitivity s times the map-book change (one value
mapped through a series model, or public co-motion, which also scales with s), or is it the same increment on both
books whatever s (a mechanical coupling)?

Units: CS2 Bo3 events of 16-22 Oct (two listed map markets), the wallet's filled maker BUY orders (calldata_all),
bursts per token within 50 ms (level = top), team-A space (A = outcome 0 of the match market; map tokens oriented by
outcome names). dV = change of the burst top on the same token since its previous burst (<= 30 s earlier; both books
nonzero). s (point in time): map 1: 2r(1-r); map 2 after A won map 1: 1 - r; after A lost map 1: r; r = last public
print of the map market (team A) before the burst; the map-1 result from the market's resolution, which is public
before map 2 starts. Statistics: direction agreement, OLS slope of dV_match on dV_map and on s * dV_map (with and
without intercept), the ratio dV_match / dV_map by s tercile; the same on loop-phase-shifted control pairs is
not needed (pairs are already conditioned on co-occurrence). Also the public analogue: the change of the two books'
last public prints over the same intervals.
Output: results/event_value_coupling.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def main():
    u = pd.read_parquet(OUT / "universe.parquet", columns=["event_slug", "slug", "smt", "outcomes", "res_outcome_prices", "cid", "tokens"])
    u = u[u.smt.isin(["moneyline", "child_moneyline"])]
    nmap = u[u.smt == "child_moneyline"].groupby("event_slug").size()
    bo3 = set(nmap[nmap == 2].index)
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "token_id", "price", "sign_ms", "salt", "cid", "oi", "event", "gs_ts"])
    cd["maker"] = cd.maker.str.lower()
    wtx = set(cd.loc[cd.maker == W, "tx"])
    wo = cd[(cd.maker == W) & (cd.idx != -1) & cd.event.isin(bo3)].drop_duplicates(["salt", "sign_ms"]).copy()
    info = {}
    for r in u[u.event_slug.isin(bo3)].itertuples():
        outs = json.loads(r.outcomes) if isinstance(r.outcomes, str) else list(r.outcomes)
        m = re.search(r"game(\d)$", str(r.slug))
        info[r.cid] = {"ev": r.event_slug, "kind": "match" if r.smt == "moneyline" else "map", "map": int(m.group(1)) if m else 0,
                       "outs": [norm(o) for o in outs], "res": json.loads(r.res_outcome_prices) if isinstance(r.res_outcome_prices, str) else r.res_outcome_prices}
    # orientation: team A = outcome 0 of the match market
    orient = {}
    for ev in bo3:
        ms = [c for c, v in info.items() if v["ev"] == ev and v["kind"] == "match"]
        if not ms:
            continue
        a = info[ms[0]]["outs"][0]
        for c, v in info.items():
            if v["ev"] == ev:
                orient[c] = 0 if v["outs"][0] == a else (1 if len(v["outs"]) > 1 and v["outs"][1] == a else None)
    wo = wo[wo.cid.map(lambda c: orient.get(c) is not None)]
    wo["y"] = np.where(wo.oi.astype(int) == wo.cid.map(orient).astype(int), wo.price, 1 - wo.price)
    wo["kind"] = wo.cid.map(lambda c: info[c]["kind"])
    wo["mapn"] = wo.cid.map(lambda c: info[c]["map"])
    # bursts
    rows = []
    for tok, g in wo.sort_values("sign_ms").groupby("token_id"):
        s = g.sign_ms.to_numpy(np.int64)
        st = 0
        for i in range(1, len(s) + 1):
            if i == len(s) or s[i] - s[i - 1] > 50:
                gg = g.iloc[st:i]
                top_i = gg.price.idxmax()
                rows.append((tok, gg.cid.iloc[0], gg.event.iloc[0], gg.kind.iloc[0], gg.mapn.iloc[0], int(s[st]), float(gg.loc[top_i, "y"]), float(gg.price.max())))
                st = i
    b = pd.DataFrame(rows, columns=["tok", "cid", "ev", "kind", "mapn", "t", "y", "top"]).sort_values(["tok", "t"])
    b["dV"] = b.groupby("tok").y.diff()
    b["dt"] = b.groupby("tok").t.diff()
    b = b[(b.top > 0.06) & (b.top < 0.94)]
    # public prints per market (wallet txs excluded)
    pr = {}
    for cid in b.cid.unique():
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if p.exists():
            d = pd.read_parquet(p, columns=["timestamp", "price", "outcomeIndex", "transactionHash"])
            d = d[~d.transactionHash.isin(wtx)].sort_values("timestamp")
            o = orient[cid]
            yy = np.where(d.outcomeIndex.astype(int) == o, d.price.astype(float), 1 - d.price.astype(float))
            pr[cid] = (d.timestamp.to_numpy(float), yy)

    def lastp(cid, t_ms):
        if cid not in pr:
            return np.nan
        ts, yy = pr[cid]
        k = np.searchsorted(ts, t_ms / 1000.0, side="left") - 1
        return yy[k] if k >= 0 else np.nan
    mp = b[b.kind == "map"]
    mt = b[b.kind == "match"]
    pairs = []
    for ev, g in mp.groupby("ev"):
        h = mt[mt.ev == ev].sort_values("t")
        if not len(h):
            continue
        ht = h.t.to_numpy(np.int64)
        res1 = None
        m1 = [c for c, v in info.items() if v["ev"] == ev and v["kind"] == "map" and v["map"] == 1]
        if m1 and info[m1[0]]["res"] is not None:
            rr = info[m1[0]]["res"]
            try:
                res1 = 1 if float(rr[orient[m1[0]]]) > 0.5 else 0
            except Exception:  # noqa: BLE001
                res1 = None
        for row in g.itertuples():
            j = np.searchsorted(ht, row.t)
            for jj in (j - 1, j):
                if 0 <= jj < len(ht) and abs(int(ht[jj]) - row.t) <= 5:
                    hr = h.iloc[jj]
                    r_ = lastp(row.cid, row.t)
                    if np.isnan(r_):
                        continue
                    if row.mapn == 1:
                        s = 2 * r_ * (1 - r_)
                    elif row.mapn == 2 and res1 is not None:
                        s = (1 - r_) if res1 == 1 else r_
                    else:
                        continue
                    # public analogue over the same intervals
                    pm0, pm1 = lastp(row.cid, row.t - (row.dt if row.dt == row.dt else 0)), r_
                    hdt = hr["dt"]; ph0, ph1 = lastp(hr["cid"], hr["t"] - (hdt if hdt == hdt else 0)), lastp(hr["cid"], hr["t"])
                    pairs.append({"ev": ev, "mapn": int(row.mapn), "s": float(s), "dV_map": row.dV, "dV_match": hr["dV"],
                                  "dt_map": row.dt, "dt_match": hdt, "dP_map": pm1 - pm0, "dP_match": ph1 - ph0})
                    break
    P = pd.DataFrame(pairs)
    P = P[(P.dt_map <= 30000) & (P.dt_match <= 30000)].dropna(subset=["dV_map", "dV_match"])
    nz = P[(P.dV_map != 0) & (P.dV_match != 0)].copy()
    out = {"pairs_all": int(len(P)), "pairs_both_nonzero": int(len(nz)), "events": int(P.ev.nunique()) if len(P) else 0}
    if len(nz) >= 10:
        out["direction_agreement"] = round(float(np.mean(np.sign(nz.dV_map) == np.sign(nz.dV_match))), 3)
        x1, x2, yv = nz.dV_map.to_numpy(), (nz.s * nz.dV_map).to_numpy(), nz.dV_match.to_numpy()
        out["slope_on_dVmap_no_icpt"] = round(float(np.sum(x1 * yv) / np.sum(x1 * x1)), 3)
        out["slope_on_s_dVmap_no_icpt"] = round(float(np.sum(x2 * yv) / np.sum(x2 * x2)), 3)
        out["r2_dVmap"] = round(float(1 - np.sum((yv - out["slope_on_dVmap_no_icpt"] * x1) ** 2) / np.sum(yv ** 2)), 3)
        out["r2_s_dVmap"] = round(float(1 - np.sum((yv - out["slope_on_s_dVmap_no_icpt"] * x2) ** 2) / np.sum(yv ** 2)), 3)
        nz["ratio"] = nz.dV_match / nz.dV_map
        nz["s_bin"] = pd.qcut(nz.s, 3, labels=["low", "mid", "high"], duplicates="drop")
        out["ratio_by_s_tercile"] = {str(k): {"n": int(len(g)), "s_median": round(float(g.s.median()), 3), "ratio_median": round(float(g.ratio.median()), 3),
                                              "abs_ratio_median": round(float(g.ratio.abs().median()), 3),
                                              "agree": round(float(np.mean(np.sign(g.dV_map) == np.sign(g.dV_match))), 3)}
                                     for k, g in nz.groupby("s_bin", observed=True)}
        out["ratio_by_map"] = {int(k): {"n": int(len(g)), "s_median": round(float(g.s.median()), 3), "abs_ratio_median": round(float(g.ratio.abs().median()), 3)}
                               for k, g in nz.groupby("mapn")}
        from scipy.stats import spearmanr
        rho = spearmanr(nz.s, nz.ratio.abs())
        out["spearman_s_vs_abs_ratio"] = [round(float(rho.correlation), 3), float(rho.pvalue)]
        pz = nz[(nz.dP_map.abs() > 0) & nz.dP_match.notna()]
        if len(pz) >= 10:
            out["public_prints_same_intervals"] = {"n": int(len(pz)), "abs_ratio_median": round(float((pz.dP_match / pz.dP_map).abs().median()), 3),
                                                   "spearman_s_vs_abs_ratio": round(float(spearmanr(pz.s, (pz.dP_match / pz.dP_map).abs()).correlation), 3)}
    (RES / "event_value_coupling.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
