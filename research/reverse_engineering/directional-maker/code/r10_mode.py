"""Iteration 16 reporting blocks for final_rule.evaluate() (reported, not counted; no frozen decision changed).

instance_mode (X177): which engine instances run the main BTC ladder. Per 15-min slot, the cluster's BTC 5m + 15m BUY
fills by price band (deep <= 0.10 or >= 0.90; mid 0.10-0.90) per wallet from data-api activity; a slot is 'split' when
one wallet holds >= 0.80 of the mid-band fills of a slot with >= 20 of them (pre-registered 11-01 09:07 UTC). BUILD 0.9%
of slots, STUDY / VALIDATE 0%, 11-01 07:00-10:00 7 of 10 (bosona alone; mo-money joined the main ladder only 08:30-09:15).

side_nowcast_match_clock (X178 / X179): the per-fill side on the live match clock (shared recorder trade with the fill's
tx hash, server ms; Up mid from its top-10 book just before the match) under the Chainlink report stamped <= T - 1,432
ms (point-in-time safe) and under the latency-corrected nowcast S_now = CL(s) + F(T - 50 ms) - F(s * 1000), F = the
Binance USD-M bookTicker mid (dx_bnf, else dm_bnf), Gamma strike, sigma = 1.0 x the futures 300-s sigma; per wallet, per
|F - mid| band and price band, with the cheaper-token baseline. Development: 10-31 14:00-16:53 report 0.852 / nowcast
0.848 (mid band, n 1,728); 11-01 07:00-09:20 0.560 / 0.685 (n 368; cheaper 0.654).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
KEY = "directional-maker"
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
SPLIT_SHARE = 0.80
SPLIT_MIN = 20
CL_DELAY_MS = 1432
K_NOW = 1.0


def _activity(start_ts, end_ts, intervals, allow_sealed):
    sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
    import sealed
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    spans = [(start_ts, end_ts)] if allow_sealed else sealed.intervals(KEY, start_ts, end_ts, sealed=False)
    fr = []
    for x0, x1 in spans:
        for addr, n in CLUSTER.items():
            rows, _, _ = pm.activity(addr, start=int(x0), end=int(x1) - 1)
            d = pd.DataFrame(rows)
            if len(d):
                d = d[(d.type == "TRADE") & (d.side == "BUY") & (d.timestamp >= x0) & (d.timestamp < x1)].copy()
                d["wallet"] = n
                fr.append(d)
    if not fr:
        return pd.DataFrame()
    d = pd.concat(fr, ignore_index=True).drop_duplicates(["transactionHash", "asset", "wallet", "size", "timestamp"])
    d = d[d.slug.astype(str).str.match(r"^btc-updown-(5m|15m)-\d+$")].copy()
    d["st"] = d.slug.str.rsplit("-", n=1).str[1].astype(int)
    if not allow_sealed:
        d = d[~d.st.map(lambda s: sealed.is_sealed(int(s), KEY))]
    if intervals:
        keep = np.zeros(len(d), dtype=bool)
        for a_, b_ in intervals:
            keep |= (d.st.to_numpy() >= a_) & (d.st.to_numpy() < b_)
        d = d[keep]
    return d


def instance_mode(start_ts: int, end_ts: int, intervals=None, allow_sealed: bool = False) -> dict:
    d = _activity(start_ts, end_ts, intervals, allow_sealed)
    if not len(d):
        return {"n": 0}
    d["band"] = np.where((d.price <= 0.10) | (d.price >= 0.90), "deep", "mid")
    d["slot"] = (d.timestamp // 900) * 900
    mid = d[d.band == "mid"]
    g = mid.groupby(["slot", "wallet"]).size().unstack(fill_value=0)
    for n in CLUSTER.values():
        if n not in g.columns:
            g[n] = 0
    names = list(CLUSTER.values())
    g["n"] = g[names].sum(axis=1)
    g = g[g.n >= SPLIT_MIN]
    out = {"rule": f"split = one wallet >= {SPLIT_SHARE} of mid-band BTC 5m+15m BUY fills in a 15-min slot with >= {SPLIT_MIN}",
           "slots": int(len(g))}
    if len(g):
        top = g[names].max(axis=1) / g.n
        sp = top >= SPLIT_SHARE
        out["split_slots"] = int(sp.sum())
        out["split_share"] = round(float(sp.mean()), 3)
        out["split_by_wallet"] = g[sp][names].idxmax(axis=1).value_counts().to_dict()
        out["split_slot_times"] = [time.strftime("%m-%d %H:%M", time.gmtime(int(s))) for s in g.index[sp]][:40]
        out["median_top_share"] = round(float(top.median()), 3)
    out["per_wallet"] = {n: {"mid": int(((d.wallet == n) & (d.band == "mid")).sum()), "deep": int(((d.wallet == n) & (d.band == "deep")).sum()),
                             "first_fill": time.strftime("%m-%d %H:%M:%S", time.gmtime(int(d.timestamp[d.wallet == n].min()))) if (d.wallet == n).any() else None}
                         for n in names}
    return out


def side_nowcast_match_clock(start_ts: int, end_ts: int, intervals=None, allow_sealed: bool = False, iter_xq=None) -> dict:
    """iter_xq: the caller's final_rule._iter_live_xq (so the examiner's ALLOW_SEALED setting is the one used)."""
    from scipy.stats import norm
    import json
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parent / "code14"))
    if iter_xq is None:
        import final_rule as fr
        iter_xq = fr._iter_live_xq
    import cl_source
    import qu_dx
    from polyrea.workflows.updown_study import fetch_windows
    d = _activity(start_ts, end_ts, intervals, allow_sealed)
    if not len(d):
        return {"n": 0}
    raw = fetch_windows(sorted(set(d.slug)))
    up, K = {}, {}
    for m in raw.values():
        try:
            toks = json.loads(m["clobTokenIds"]) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds")
            outs = json.loads(m["outcomes"]) if isinstance(m.get("outcomes"), str) else m.get("outcomes")
            u = str(toks[outs.index("Up")])
            up[u] = u
            up[str(toks[outs.index("Down")])] = u
        except Exception:  # noqa: BLE001
            continue
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    d["up_tok"] = d.asset.astype(str).map(up)
    ups = set(d.up_tok.dropna())
    match, books = {}, {}
    for r in iter_xq(start_ts - 120, end_ts + 120, ups):
        if r.get("k") == "x":
            h = str(r.get("h", "")).lower()
            if h and h not in match and r.get("s"):
                match[h] = int(r["s"])
        elif r.get("k") == "q" and str(r.get("a")) in ups and r.get("s"):
            b_, o_ = r.get("b") or [], r.get("o") or []
            if b_ and o_:
                books.setdefault(str(r["a"]), []).append((int(r["s"]), (max(float(x[0]) for x in b_) + min(float(x[0]) for x in o_)) / 2))
    bk = {}
    for t_, v in books.items():
        v.sort()
        bk[t_] = (np.array([x[0] for x in v], np.int64), np.array([x[1] for x in v]))
    d["T"] = d.transactionHash.str.lower().map(match)
    d = d[d["T"].notna() & d.up_tok.notna()].copy()
    if not len(d):
        return {"n": 0, "matched_trades": len(match)}
    d["T"] = d["T"].astype(np.int64)
    mid = np.full(len(d), np.nan)
    for i, (u, T) in enumerate(zip(d.up_tok, d["T"])):
        if u in bk:
            s_, m_ = bk[u]
            j = np.searchsorted(s_, T, side="left") - 1
            if j >= 0 and T - s_[j] <= 10000:
                mid[i] = m_[j]
    d["mid"] = mid
    d = d[np.isfinite(d.mid)].copy()
    E, M = qu_dx._fut(start_ts - 900, end_ts + 60, allow_sealed)
    if not len(E):
        return {"n": int(len(d)), "note": "no futures mid recorded"}
    # sigma ($ per root second) of 1-s changes of the last futures mid per second over the previous 300 s
    secs = np.arange(int(E[0] // 1000), int(E[-1] // 1000) + 2)
    last = qu_dx._at(E, M, secs * 1000 + 999)
    sig = pd.Series(np.diff(last, prepend=np.nan), index=secs).rolling(300, min_periods=150).std().shift(1)
    T = d["T"].to_numpy(np.int64)
    s = (T - CL_DELAY_MS) // 1000
    clv = cl_source.cl_values(sorted(set(s.tolist())), allow_sealed=allow_sealed, fetch=False)
    cl = pd.Series(s).map(clv).to_numpy(float)
    now = cl + qu_dx._at(E, M, T - 50) - qu_dx._at(E, M, s * 1000)
    kk = d.slug.map(K).to_numpy(float)
    en = d.st.to_numpy() + np.where(d.slug.str.contains("-15m-"), 900, 300)
    tau = np.maximum(en - T / 1000, 1.0)
    sg = sig.reindex(T // 1000).to_numpy(float)
    y = (d.outcome == "Up").to_numpy()
    md = d.mid.to_numpy(float)
    pr = d.price.to_numpy(float)
    midb = (pr > 0.10) & (pr < 0.90)
    F_rep = norm.cdf((cl - kk) / (K_NOW * sg * np.sqrt(tau)))
    F_now = norm.cdf((now - kk) / (K_NOW * sg * np.sqrt(tau)))
    preds = {"report": F_rep > md, "nowcast": F_now > md, "cheaper": md < 0.5}
    okr, okn = np.isfinite(F_rep), np.isfinite(F_now)
    band = np.abs(F_rep - md)

    def acc(p, m):
        return [round(float(np.mean(p[m] == y[m])), 4) if m.any() else None, int(m.sum())]
    out = {"n": int(len(d)), "matched_trades": len(match), "k": K_NOW, "cl_delay_ms": CL_DELAY_MS}
    for pb, pm_ in (("mid_band", midb), ("deep_band", ~midb)):
        out[pb] = {nm: acc(p, pm_ & (okn if nm == "nowcast" else okr)) for nm, p in preds.items()}
        out[pb]["by_edge"] = {f"{lo}-{hi}": {nm: acc(p, pm_ & okr & okn & (band >= lo) & (band < hi)) for nm, p in preds.items()}
                              for lo, hi in ((0, 0.05), (0.05, 0.1), (0.1, 1.01))}
    out["per_wallet_mid_band"] = {n: {nm: acc(p, midb & (d.wallet == n).to_numpy() & (okn if nm == "nowcast" else okr)) for nm, p in preds.items()}
                                  for n in CLUSTER.values()}
    return out
