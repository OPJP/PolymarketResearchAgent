"""X218 (assumptions panel iter-14 P4): outcome replay of a public five-slot ladder that carries the wallet's own exit
policy, in the validated X57 engine (strict price-time re-allocation of each public tx's maker volume along the merged
queue; the wallet's own maker rows removed and ours inserted; machinery of phase_gated_ladder.py / knockout.py,
16-22 Oct, the wallet's markets).

Quote set L5 (X202): public anchor = floor(others' best bid-equivalent on the token in the latest wallet-free tx, usable
2 s after that tx); both tokens; BUY only; five slots anchor .. anchor - 4c, capacity 100 each, reset every 10 s; pair
cap (anchor_A + anchor_B <= 0.99, else no new level); band [0.05, 0.95].
Exit policy variants (net(z) = our shares of token z minus our shares of the complement, own state of the RULE):
  C0    no cap (X202's L5)
  C400  hard cap: total fill on z limited to max(0, 400 - net(z))
  C600  hard cap at 600
  T26   taper: level capacity at (re)post = 100 x clip((600 - net) / 400, 0, 1) when net > 200, plus the hard cap 600
  T26S  T26 with the measured skew: slots shifted down 1c when net(z) >= 200
Chosen on BUILD by min(Pearson, Spearman) of the per-market PnL with the wallet's; VALIDATE scored once with halves.
Output: results/exit_policy_ladder.json, .cache/re/tommy-cs2-maker/exit_policy_markets.parquet
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
VARIANTS = {"C0": dict(cap=np.inf, taper=False, skew=False), "C400": dict(cap=400.0, taper=False, skew=False),
            "C600": dict(cap=600.0, taper=False, skew=False), "T26": dict(cap=600.0, taper=True, skew=False),
            "T26S": dict(cap=600.0, taper=True, skew=True)}


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    k = np.isfinite(x) & np.isfinite(y)
    if k.sum() < 5 or np.std(x[k]) == 0:
        return [None, None, int(k.sum())]
    return [round(float(stats.pearsonr(x[k], y[k])[0]), 3), round(float(stats.spearmanr(x[k], y[k])[0]), 3), int(k.sum())]


def main():
    cd, gs = load_record()
    cd = cd[cd.m.notna()].copy()
    pm = pd.read_parquet(OUT / "per_market.parquet").set_index("cid")
    rows = []
    for cid, g in cd.groupby("cid"):
        if cid not in pm.index:
            continue
        g = g.sort_values(["m", "tx", "idx"])
        gsm = float(gs.get(cid, 0)) * 1000.0
        win = int(pm.loc[cid, "win"])
        ob = [None, None]
        pend = []
        S = {k: {"sh": np.zeros(2), "cost": np.zeros(2), "nf": 0} for k in VARIANTS}
        lev = {k: {0: None, 1: None} for k in VARIANTS}
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
            anc = [np.floor(x * 100 + 1e-6) / 100 if x is not None else None for x in ob]
            pair_ok = anc[0] is not None and anc[1] is not None and anc[0] + anc[1] <= 0.99 + 1e-9
            for key, P in VARIANTS.items():
                L = lev[key]
                net = S[key]["sh"][z] - S[key]["sh"][1 - z]
                if not pair_ok or anc[z] is None:
                    want = []
                else:
                    sh = 1 if (P["skew"] and net >= 200) else 0
                    want = [round(anc[z] - (k + sh) / 100, 2) for k in range(5)]
                    want = [p for p in want if 0.05 - 1e-9 <= p <= 0.95 + 1e-9]
                fac = float(np.clip((600.0 - net) / 400.0, 0, 1)) if (P["taper"] and net > 200) else 1.0
                cur = L[z]
                if cur is None or m - cur["reset"] >= 10000 or set(cur["lv"]) != set(want):
                    keep = {} if cur is None else cur["lv"]
                    newlv = {}
                    for p in want:
                        if cur is not None and p in keep and m - cur["reset"] < 10000:
                            newlv[p] = keep[p]
                        else:
                            newlv[p] = [100.0 * fac, m]
                    L[z] = {"lv": newlv, "reset": m if (cur is None or m - cur["reset"] >= 10000) else cur["reset"]}
                room = max(0.0, P["cap"] - net)
                q = list(base)
                for p, (cap, post) in L[z]["lv"].items():
                    if cap > 1e-9:
                        q.append((p, post, cap, p))
                q.sort(key=lambda x: (-x[0], x[1]))
                left = F
                for b, s, cap, sid in q:
                    if left <= 1e-9:
                        break
                    if sid is not None:
                        cap = min(cap, room)
                    take = min(cap, left)
                    left -= take
                    if sid is None or take <= 0:
                        continue
                    room -= take
                    S[key]["sh"][z] += take
                    S[key]["cost"][z] += take * b
                    S[key]["nf"] += 1
                    L[z]["lv"][sid][0] -= take
        rec = {"cid": cid, "gs": float(gs.get(cid, 0)), "w_pnl": float(pm.loc[cid, "pnl"]),
               "w_max_abs_net": float(pm.loc[cid, "max_abs_net"]), "w_unpaired": float(pm.loc[cid, "unpaired"])}
        for key in VARIANTS:
            sh, cost = S[key]["sh"], S[key]["cost"]
            rec[f"{key}_pnl"] = float(sh[win] - cost.sum())
            rec[f"{key}_usd"] = float(cost.sum())
            rec[f"{key}_pairs"] = float(min(sh))
            rec[f"{key}_resid"] = float(sh[win] - min(sh))  # residual shares on the winner (paid 1)
            rec[f"{key}_unp"] = float(abs(sh[0] - sh[1]))
            rec[f"{key}_margin"] = float(min(sh) - (cost.sum() - (abs(sh[0] - sh[1]) * (cost[int(np.argmax(sh))] / max(sh.max(), 1e-9)))))
        rows.append(rec)
    X = pd.DataFrame(rows)
    res = {"markets": int(len(X))}
    for sp, sel in (("BUILD", X.gs < VAL0), ("VALIDATE", (X.gs >= VAL0) & (X.gs < H))):
        y = X[sel]
        o2 = {"markets": int(len(y)), "wallet_pnl": round(float(y.w_pnl.sum()), 1)}
        for key in VARIANTS:
            o2[key] = {"pnl": round(float(y[f"{key}_pnl"].sum()), 1), "usd": round(float(y[f"{key}_usd"].sum()), 1),
                       "return": round(float(y[f"{key}_pnl"].sum() / max(y[f"{key}_usd"].sum(), 1e-9)), 4),
                       "pnl_vs_wallet": corr(y[f"{key}_pnl"], y.w_pnl),
                       "unpaired_vs_wallet": corr(y[f"{key}_unp"], y.w_unpaired),
                       "pairs_vs_wallet_pnl": corr(y[f"{key}_pairs"], y.w_pnl),
                       "median_unpaired": round(float(y[f"{key}_unp"].median()), 1)}
        res[sp] = o2
    score = {k: min(x if x is not None else -9 for x in res["BUILD"][k]["pnl_vs_wallet"][:2]) for k in VARIANTS}
    best = max(score, key=score.get)
    res["build_scores"] = score
    res["chosen_on_BUILD"] = best
    res["VALIDATE_chosen"] = res["VALIDATE"][best]
    v = X[(X.gs >= VAL0) & (X.gs < H)].sort_values("gs")
    hlf = len(v) // 2
    res["VALIDATE_chosen_halves"] = [corr(v.iloc[:hlf][f"{best}_pnl"], v.iloc[:hlf].w_pnl), corr(v.iloc[hlf:][f"{best}_pnl"], v.iloc[hlf:].w_pnl)]
    X.to_parquet(OUT / "exit_policy_markets.parquet", index=False)
    (RES / "exit_policy_ladder.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("build_scores", "chosen_on_BUILD", "VALIDATE_chosen", "VALIDATE_chosen_halves")}, indent=1))
    for sp in ("BUILD", "VALIDATE"):
        print(sp, {k: (res[sp][k]["return"], res[sp][k]["pnl_vs_wallet"][:2]) for k in VARIANTS})


if __name__ == "__main__":
    main()
