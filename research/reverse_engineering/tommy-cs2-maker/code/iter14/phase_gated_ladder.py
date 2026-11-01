"""X202 (assumptions panel iter-13 P4): a round-phase-gated public ladder for the outcome item, in the validated X57
engine (strict price-time re-allocation of each public tx's maker volume along the merged queue; the wallet's own
maker rows are removed and ours inserted; knockout.py machinery, 16-22 Oct, the wallet's markets).

Point-in-time round clock: informed take clusters = >= 2 distinct members of group P (selection_groupP.json, fixed on
BUILD in iteration 9) or group G (the assumptions panel's list, identified on BUILD in iterations 7-9) whose taker
orders on any book of the event are signed within 300 ms of each other; the cluster is usable from the latest block
time of its txs + 2 s (u).

Quote sets per market (public anchor = floor(others' best bid-equivalent on the token in the latest wallet-free tx,
usable 2 s after that tx); both tokens; BUY only):
  D        continuous single level at the anchor, capacity 100, reset every 10 s (iteration 9's knockout D);
  L5       continuous five-slot ladder anchor, anchor-1c ... anchor-4c, capacity 100 each, reset every 10 s, pair cap
           (anchor_A + anchor_B <= 0.99, else no new level), band [0.05, 0.95];
  G(d, W)  L5 quoted only in [u + d, u + d + W] after the latest cluster u (pulled otherwise), d in {5, 10, 20} s,
           W in {20, 40, 60} s; (d, W) chosen on BUILD by min(Pearson, Spearman) of the per-market PnL with the
           wallet's.
Per market: settlement PnL of each set (pairs pay 1), USD spent; correlation with the wallet's PnL (per_market.parquet),
return, BUILD and VALIDATE. Prints baseline from iteration 6 (0.33 / 0.28) for reference.
Output: results/phase_gated_ladder.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter4"))
from queue_replay import load_record  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0, H = 1792540800, 1792713600
LAT = 2000.0
GG = {"0xf1ee4842fa0c7283632185e42577027452d4519c", "0x8a80528dce46711a54aa3455c2cc81dea51e11c5",
      "0xddb6e6246546230503f153506ac1e9914978b9b3", "0x7c8cc25556ef9c0962b41d0ebb74d2fd17a42d81",
      "0x67706ec33d1bc5ed0db5cf0681b74b57b64ec3bd", "0xc70974218b9c6570f7701cd6fafc04ed490fbda9"}
DS, WS = (5, 10, 20), (20, 40, 60)


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    k = np.isfinite(x) & np.isfinite(y)
    if k.sum() < 5 or np.std(x[k]) == 0:
        return [None, None, int(k.sum())]
    return [round(float(stats.pearsonr(x[k], y[k])[0]), 3), round(float(stats.spearmanr(x[k], y[k])[0]), 3), int(k.sum())]


def main():
    GP = set(json.load(open(RES / "selection_groupP.json"))["members"])
    INF = GP | GG
    cd, gs = load_record()
    cd = cd[cd.m.notna()].copy()
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "event"]).drop_duplicates("cid")
    ev_of = dict(zip(o.cid, o.event))
    cd["event"] = cd.cid.map(ev_of)
    pm = pd.read_parquet(OUT / "per_market.parquet").set_index("cid")
    # informed clusters per event
    tk = cd[(cd.idx == -1)].drop_duplicates("tx")
    tk = tk[tk.maker.str.lower().isin(INF) & (tk.sign_ms > 1.7e12)]
    clusters = {}
    for ev, g in tk.groupby("event"):
        g = g.sort_values("sign_ms")
        s, mk, mm = g.sign_ms.to_numpy(), g.maker.str.lower().to_numpy(), g.m.to_numpy(float)
        out, i = [], 0
        while i < len(g):
            j = i
            while j + 1 < len(g) and s[j + 1] - s[i] <= 300:
                j += 1
            if len(set(mk[i:j + 1])) >= 2:
                out.append(float(mm[i:j + 1].max()) + LAT)
                i = j + 1
            else:
                i += 1
        clusters[ev] = np.array(sorted(out))
    variants = ["D", "L5"] + [f"G_{d}_{w}" for d in DS for w in WS]
    rows = []
    for cid, g in cd.groupby("cid"):
        if cid not in pm.index:
            continue
        g = g.sort_values(["m", "tx", "idx"])
        gsm = float(gs.get(cid, 0)) * 1000.0
        win = int(pm.loc[cid, "win"])
        cl = clusters.get(ev_of.get(cid), np.array([]))
        ob = [None, None]
        pend = []
        S = {k: {"sh": np.zeros(2), "cost": np.zeros(2)} for k in variants}
        lev = {k: {0: None, 1: None} for k in variants}  # per token: dict price -> [cap, post]; plus reset time
        for tx, h in g.groupby("tx", sort=False):
            t = h[h.idx == -1]
            if t.empty:
                continue
            t = t.iloc[0]
            m = float(t.m)
            while pend and pend[0][0] <= m:
                _, zz, val = pend.pop(0)
                ob[zz] = val
            z = int(t.oi) if int(t.side) == 1 else 1 - int(t.oi)
            mk = h[h.idx >= 0]
            beq = np.where((mk.side.to_numpy() == 0) & (mk.oi.to_numpy() == z), mk.price.to_numpy(float),
                           np.where((mk.side.to_numpy() == 1) & (mk.oi.to_numpy() != z), 1 - mk.price.to_numpy(float), np.nan))
            ok = np.isfinite(beq)
            if not ok.any():
                continue
            mk, beq = mk[ok], beq[ok]
            isw = (mk.maker == W).to_numpy()
            if not isw.any() and str(t.maker).lower() != W:
                pend.append((m + LAT, z, float(beq.max())))
                pend.sort()
            if m < gsm or str(t.maker).lower() == W:
                continue
            F = float(mk.fill.sum())
            base = [(float(b), float(s), float(f), None) for b, s, f, w in zip(beq, mk.sign_ms.to_numpy(float), mk.fill.to_numpy(float), isw) if not w]
            k_cl = np.searchsorted(cl, m, side="right") - 1
            since = m - cl[k_cl] if k_cl >= 0 else np.inf
            anc = [np.floor(x * 100 + 1e-6) / 100 if x is not None else None for x in ob]
            pair_ok = anc[0] is not None and anc[1] is not None and anc[0] + anc[1] <= 0.99 + 1e-9
            for key in variants:
                L = lev[key]
                if key == "D":
                    want = [anc[z]] if anc[z] is not None else []
                else:
                    if not pair_ok or anc[z] is None:
                        want = []
                    else:
                        want = [round(anc[z] - k / 100, 2) for k in range(5)]
                        want = [p for p in want if 0.05 - 1e-9 <= p <= 0.95 + 1e-9]
                    if key.startswith("G_"):
                        _, d, w = key.split("_")
                        d, w = float(d) * 1000, float(w) * 1000
                        if not (d <= since <= d + w):
                            want = []
                cur = L[z]
                if cur is None or m - cur["reset"] >= 10000 or set(cur["lv"]) != set(want):
                    keep = {} if cur is None else cur["lv"]
                    newlv = {}
                    for p in want:
                        if cur is not None and p in keep and m - cur["reset"] < 10000:
                            newlv[p] = keep[p]
                        else:
                            newlv[p] = [100.0, m]
                    L[z] = {"lv": newlv, "reset": m if (cur is None or m - cur["reset"] >= 10000) else cur["reset"]}
                q = list(base)
                for p, (cap, post) in L[z]["lv"].items():
                    if cap > 1e-9:
                        q.append((p, post, cap, p))
                q.sort(key=lambda x: (-x[0], x[1]))
                left = F
                for b, s, cap, sid in q:
                    if left <= 1e-9:
                        break
                    take = min(cap, left)
                    left -= take
                    if sid is None or take <= 0:
                        continue
                    S[key]["sh"][z] += take
                    S[key]["cost"][z] += take * b
                    L[z]["lv"][sid][0] -= take
        rec = {"cid": cid, "gs": float(gs.get(cid, 0)), "w_pnl": float(pm.loc[cid, "pnl"]), "clusters": int(len(cl))}
        for key in variants:
            rec[f"{key}_pnl"] = float(S[key]["sh"][win] - S[key]["cost"].sum())
            rec[f"{key}_usd"] = float(S[key]["cost"].sum())
        rows.append(rec)
    X = pd.DataFrame(rows)
    res = {"clusters_per_event_median": float(np.median([len(v) for v in clusters.values()])) if clusters else 0}
    for sp, sel in (("BUILD", X.gs < VAL0), ("VALIDATE", (X.gs >= VAL0) & (X.gs < H))):
        y = X[sel]
        o2 = {"markets": int(len(y)), "wallet_pnl": round(float(y.w_pnl.sum()), 1)}
        for key in variants:
            o2[key] = {"pnl": round(float(y[f"{key}_pnl"].sum()), 1), "usd": round(float(y[f"{key}_usd"].sum()), 1),
                       "return": round(float(y[f"{key}_pnl"].sum() / max(y[f"{key}_usd"].sum(), 1e-9)), 4),
                       "pnl_vs_wallet": corr(y[f"{key}_pnl"], y.w_pnl)}
        res[sp] = o2
    gk = [k for k in variants if k.startswith("G_")]
    score = {k: min(x if x is not None else -9 for x in res["BUILD"][k]["pnl_vs_wallet"][:2]) for k in gk}
    best = max(score, key=score.get)
    res["chosen_on_BUILD"] = best
    res["VALIDATE_chosen"] = res["VALIDATE"][best]
    # halves of VALIDATE by game start
    v = X[(X.gs >= VAL0) & (X.gs < H)].sort_values("gs")
    hlf = len(v) // 2
    res["VALIDATE_chosen_halves"] = [corr(v.iloc[:hlf][f"{best}_pnl"], v.iloc[:hlf].w_pnl), corr(v.iloc[hlf:][f"{best}_pnl"], v.iloc[hlf:].w_pnl)]
    X.to_parquet(OUT / "phase_gated_markets.parquet", index=False)
    (RES / "phase_gated_ladder.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("chosen_on_BUILD", "VALIDATE_chosen", "VALIDATE_chosen_halves")}, indent=1))
    for sp in ("BUILD", "VALIDATE"):
        print(sp, {k: (res[sp][k]["return"], res[sp][k]["pnl_vs_wallet"][:2]) for k in variants})


if __name__ == "__main__":
    main()
