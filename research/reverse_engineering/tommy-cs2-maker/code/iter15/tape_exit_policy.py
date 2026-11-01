"""X218, examinable form: the outcome item of evaluate() with a public five-slot ladder that carries the wallet's exit
policy, on the data-api taker tape only (what the examiner's evaluate() already loads), strict trade-through fills.

Engine (event-driven, point in time): per market, walk the wallet-free taker prints in time order from game start.
A print that consumed bids on token z (taker SELL of z at p, or taker BUY of the complement at q: p = 1 - q) reveals
others' bid on z ~ p; it becomes the anchor of z 2 s after its block (lat). Our ladder on z: slots floor(anchor_z) - k c,
k = 0..4 (variant slots), capacity 100 each, refilled every 10 s, pair cap anchor_0 + anchor_1 <= 0.99, band [0.05,
0.95]. Fill: a print on z at average price p strictly below our slot q fills that slot's remaining capacity (price
priority: a sweep whose average lies below q went through q), up to the taker's size, highest slots first; the exit
policy limits the fill on z to max(0, cap - net(z)) and tapers the refilled capacity above net 200. Per-market
settlement PnL (pairs pay 1). Same universe and wallet PnL as evaluate(): markets of v5-selected events plus traded
markets (rule PnL 0 on unselected traded markets).
Variants chosen on BUILD by min(Pearson, Spearman), VALIDATE once (CONSTANTS 'build', as for state.json numbers).
Output: results/tape_exit_policy.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[5]
CODE = ROOT / "research/reverse_engineering/tommy-cs2-maker/code"
sys.path.insert(0, str(CODE))
import final_rule as fr  # noqa: E402

RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
B0, VAL0, H = 1792108800, 1792540800, 1792713600
VARIANTS = {
    "OLD": None,  # the frozen _replay
    "L1_C0": dict(slots=1, cap=np.inf, taper=False),
    "L5_C0": dict(slots=5, cap=np.inf, taper=False),
    "L5_C400": dict(slots=5, cap=400.0, taper=False),
    "L5_C600": dict(slots=5, cap=600.0, taper=False),
    "L5_T26": dict(slots=5, cap=600.0, taper=True),
    "L3_T26": dict(slots=3, cap=600.0, taper=True),
}


def replay_ladder(d, gs, pay0, slots=5, cap=600.0, taper=True, size=100.0, lat=2.0, req=10.0, pair_cap=0.99,
                  band=(0.05, 0.95)):
    if d is None or len(d) < 5:
        return 0.0, 0.0
    d = d.sort_values("timestamp")
    ts = d["timestamp"].to_numpy(float)
    oi = d["outcomeIndex"].astype(int).to_numpy()
    side = d["side"].to_numpy()
    pr = d["price"].astype(float).to_numpy()
    sz = d["size"].astype(float).to_numpy()
    zt = np.where(side == "SELL", oi, 1 - oi)  # token whose bids the print consumed
    pz = np.where(side == "SELL", pr, 1 - pr)  # bid-equivalent price on that token
    anc = [None, None]
    pend = []  # (usable_ts, z, price)
    sh, cost = np.zeros(2), 0.0
    lev = [None, None]  # per token: {"lv": {q: cap}, "reset": t, "anc": a}
    for i in range(len(ts)):
        t = ts[i]
        while pend and pend[0][0] <= t:
            _, zz, val = pend.pop(0)
            anc[zz] = val
        z = int(zt[i])
        if t >= gs and anc[0] is not None and anc[1] is not None:
            a = [np.floor(x * 100 + 1e-6) / 100 for x in anc]
            if a[0] + a[1] <= pair_cap + 1e-9:
                net = sh[z] - sh[1 - z]
                fac = float(np.clip((600.0 - net) / 400.0, 0, 1)) if (taper and net > 200) else 1.0
                want = [round(a[z] - k / 100, 2) for k in range(slots)]
                want = [q for q in want if band[0] - 1e-9 <= q <= band[1] + 1e-9]
                cur = lev[z]
                if cur is None or t - cur["reset"] >= req or cur["anc"] != a[z]:
                    old = {} if cur is None else cur["lv"]
                    fresh = cur is None or t - cur["reset"] >= req
                    lev[z] = {"lv": {q: (size * fac if (fresh or q not in old) else old[q]) for q in want},
                              "reset": t if fresh else cur["reset"], "anc": a[z]}
                room = max(0.0, cap - net)
                left = float(sz[i])
                for q in sorted(lev[z]["lv"], reverse=True):
                    if left <= 1e-9 or room <= 1e-9:
                        break
                    c = lev[z]["lv"][q]
                    if c <= 1e-9 or not (pz[i] < q - 1e-9):
                        continue
                    f = min(c, left, room)
                    lev[z]["lv"][q] -= f
                    left -= f
                    room -= f
                    sh[z] += f
                    cost += f * q
        pend.append((t + lat, z, float(pz[i])))
    return float(sh[0] * pay0 + sh[1] * (1 - pay0) - cost), float(cost)


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 5 or np.std(x) == 0:
        return [None, None, int(len(x))]
    return [round(float(stats.pearsonr(x, y)[0]), 3), round(float(stats.spearmanr(x, y)[0]), 3), int(len(x))]


def split_rows(start, end):
    fr.CONSTANTS = "build"
    C = dict(fr.CALL[fr.CONSTANTS])
    C["league_sum"] = {**C["league_sum"], **fr.DOTA[fr.CONSTANTS]["league_sum"]}
    C["league_n"] = {**C["league_n"], **fr.DOTA[fr.CONSTANTS]["league_n"]}
    iv = [(start, end)]
    u = fr._universe(start, end, iv)
    fills = fr._wallet_fills(u, end)
    traded = set(fills["cid"]) if len(fills) else set()
    bad = set(fills["tx"]) if len(fills) else set()
    pay = fr._payouts(u, end)
    pre, tapes = {}, {}
    for r in u.itertuples():
        d = fr._tape(r.cid, int(r.gs_ts), end)
        if d is None or len(d) == 0:
            pre[r.cid] = (0, 0.0, 0)
            continue
        d = d[~d["transactionHash"].isin(bad)].sort_values("timestamp")
        tapes[r.cid] = d
        tsx = d["timestamp"].to_numpy(np.int64)
        m = (tsx >= r.gs_ts - 3600) & (tsx < r.gs_ts)
        pre[r.cid] = (int(m.sum()), float((d["price"].astype(float) * d["size"].astype(float))[m].sum()), int(d["proxyWallet"][m].nunique()))
    u[["n", "v", "w"]] = pd.DataFrame([pre.get(c, (0, 0.0, 0)) for c in u["cid"]], index=u.index)
    u["y"] = u["cid"].isin(traded).astype(int)
    u["grid"] = u["grid_series_id"].notna()
    ev = u.groupby("event_slug").agg(y=("y", "max"), n=("n", "sum"), v=("v", "sum"), w=("w", "sum"), league=("league", "first"),
                                     tier=("league_tier", "first"), grid=("grid", "max"), gs=("gs_ts", "min")).reset_index()
    u["series"] = u["series"].fillna("10310").astype(str)
    gp = fr._gp72(ev, u, tapes, start, end, iv)
    sc = fr.selection_score_v5(ev, C, gp)
    sel = sc >= fr.V5[fr.CONSTANTS]["thr"]
    selected = set(ev.loc[sel, "event_slug"])
    rows = []
    for r in u.itertuples():
        if r.cid not in pay or (r.event_slug not in selected and r.cid not in traded):
            continue
        size = 10.0 if str(r.series) == "10309" else 100.0
        capk = 1.0 if size == 100.0 else 0.1
        f = fills[fills["cid"] == r.cid] if len(fills) else fills
        wp = float((f["fill"] * np.where(f["oi"] == 0, pay[r.cid], 1 - pay[r.cid]) - f["usdc"]).sum()) if len(f) else 0.0
        dt = tapes.get(r.cid)
        npr = int((dt["timestamp"].to_numpy(np.int64) >= r.gs_ts).sum()) if dt is not None and len(dt) else 0
        rec = {"cid": r.cid, "event": r.event_slug, "gs": r.gs_ts, "w": wp, "prints": npr, "traded": r.cid in traded,
               "sel": r.event_slug in selected}
        for k, P in VARIANTS.items():
            if r.event_slug not in selected:
                rec[k] = 0.0
                rec[k + "_usd"] = 0.0
                continue
            if P is None:
                rec[k] = fr._replay(dt, r.gs_ts, pay[r.cid], size=size)
                rec[k + "_usd"] = np.nan
            else:
                p2 = dict(P)
                p2["cap"] = p2["cap"] * capk
                rec[k], rec[k + "_usd"] = replay_ladder(dt, r.gs_ts, pay[r.cid], size=size, **p2)
        rows.append(rec)
    return pd.DataFrame(rows)


def summarize(X):
    o = {"markets": int(len(X)), "wallet_pnl": round(float(X.w.sum()), 1),
         "prints_baseline": corr(X.prints, X.w)}
    z = np.c_[np.ones(len(X)), np.log1p(X.prints.to_numpy(float))]
    ry = X.w.to_numpy(float) - z @ np.linalg.lstsq(z, X.w.to_numpy(float), rcond=None)[0]
    for k in VARIANTS:
        rx = X[k].to_numpy(float) - z @ np.linalg.lstsq(z, X[k].to_numpy(float), rcond=None)[0]
        o[k] = {"pnl": round(float(X[k].sum()), 1), "usd": round(float(np.nansum(X[k + "_usd"])), 1),
                "corr": corr(X[k], X.w), "partial_given_prints": round(float(np.corrcoef(rx, ry)[0, 1]), 3) if rx.std() > 0 else None,
                "corr_traded_only": corr(X.loc[X.traded, k], X.loc[X.traded, "w"])}
    return o


def main():
    res = {}
    XB = split_rows(B0, VAL0)
    XV = split_rows(VAL0, H)
    res["BUILD"] = summarize(XB)
    res["VALIDATE"] = summarize(XV)
    score = {k: min(x if x is not None else -9 for x in res["BUILD"][k]["corr"][:2]) for k in VARIANTS if k != "OLD"}
    best = max(score, key=score.get)
    res["build_scores"] = score
    res["chosen_on_BUILD"] = best
    res["VALIDATE_chosen"] = res["VALIDATE"][best]
    v = XV.sort_values("gs")
    h = len(v) // 2
    res["VALIDATE_chosen_halves"] = [corr(v.iloc[:h][best], v.iloc[:h].w), corr(v.iloc[h:][best], v.iloc[h:].w)]
    XB.assign(split="BUILD").pipe(lambda a: pd.concat([a, XV.assign(split="VALIDATE")])).to_parquet(
        ROOT / ".cache/re/tommy-cs2-maker/tape_exit_policy_markets.parquet", index=False)
    (RES / "tape_exit_policy.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("build_scores", "chosen_on_BUILD", "VALIDATE_chosen", "VALIDATE_chosen_halves")}, indent=1, default=str))
    for sp in ("BUILD", "VALIDATE"):
        print(sp, {k: res[sp][k]["corr"][:2] for k in VARIANTS}, "prints", res[sp]["prints_baseline"])


if __name__ == "__main__":
    main()
