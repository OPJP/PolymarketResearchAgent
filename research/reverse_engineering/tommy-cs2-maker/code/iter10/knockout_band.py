"""Iteration 10, X141 (assumptions panel iter-9 P2): the knockout replays of iteration 9 (X124) re-run with the wallet's hard
price band [0.05, 0.95] applied to the public-anchor quote sets B and D (A and C use the wallet's own prices, which all lie
in the band). Everything else is unchanged (copied from code/iter9/knockout.py).

Iteration 9, X124 (mechanics panel iter8 P2): which quote component carries the per-market pair cost / PnL?
Validated X57 engine (strict price-time re-allocation of each public tx's maker volume along the merged queue; the
wallet's own maker rows are replaced by ours), 16-22 Oct, its 229 markets. Quote sets per market:
  A  the wallet's own filled maker orders at their prices, resting [sign + 24 ms, match time of the last real fill]
  B  A's windows at the public anchor: floor(last observed others' best bid on the token, usable 2 s after its tx)
  C  A's prices quoted continuously: on each token one level at the price of the latest wallet maker order signed
     before the tx (capacity = that order's size, reset when a new order is signed), no lifetimes
  D  public price, A-free timing: continuous level at the B anchor on both tokens (capacity 100, reset every 10 s)
Per set: maker-only per-market pair cost, pairs, settlement PnL; correlation of the set's PnL with the wallet's total
PnL and with its real maker-only PnL; share of the set's fill shares taken by group P (feed subscribers). BUILD and
VALIDATE separately. Diagnostic (A-C use the wallet's own orders: oracle components, never a rule).
Output: results/knockout.json
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
LO, HI = 0.05, 0.95
from queue_replay import load_record  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0, H = 1792540800, 1792713600
POST_MS, LAT = 24.0, 2000.0


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    k = np.isfinite(x) & np.isfinite(y)
    if k.sum() < 5 or np.std(x[k]) == 0:
        return [None, None, int(k.sum())]
    return [round(float(stats.pearsonr(x[k], y[k])[0]), 3), round(float(stats.spearmanr(x[k], y[k])[0]), 3), int(k.sum())]


def main():
    GP = set(json.load(open(RES / "selection_groupP.json"))["members"])
    cd, gs = load_record()
    cd = cd[cd.m.notna()].copy()
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "salt"])
    a["salt"] = a.salt.astype(str)
    cd = cd.merge(a, on=["tx", "idx"], how="left")
    o = pd.read_parquet(OUT / "orders.parquet", columns=["salt", "role"])
    wms = set(o[o.role == "maker"].salt.astype(str))
    pm = pd.read_parquet(OUT / "per_market.parquet").set_index("cid")
    rows = []
    for cid, g in cd.groupby("cid"):
        if cid not in pm.index:
            continue
        g = g.sort_values(["m", "tx", "idx"])
        gsm = float(gs.get(cid, 0)) * 1000.0
        win = int(pm.loc[cid, "win"])
        wm = g[(g.idx >= 0) & (g.maker == W) & g.salt.isin(wms)]
        if wm.empty:
            continue
        ords = wm.groupby("salt").agg(oi=("oi", "first"), side=("side", "first"), p=("price", "first"), size=("shares", "first"),
                                      sign=("sign_ms", "first"), end=("m", "max")).reset_index()
        ords = ords[(ords.side == 0) & (ords.sign > 1.7e12)].sort_values("sign")
        ords["post"] = ords.sign + POST_MS
        ob = [None, None]
        pend = []
        sets = {k: {"sh": np.zeros(2), "cost": np.zeros(2), "gp": 0.0, "tot": 0.0} for k in "ABCD"}
        remA = dict(zip(ords.salt, ords["size"].astype(float)))
        remB = dict(remA)
        anchorB = {}
        lastC = {0: None, 1: None}  # [price, post, rem, salt]
        lastD = {0: None, 1: None}
        real = {"sh": np.zeros(2), "cost": np.zeros(2)}
        ord_by_tok = {z: ords[ords.oi == z] for z in (0, 1)}
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
            if not isw.any() and str(t.maker).lower() != W:  # brief: txs with a wallet order are never features
                pend.append((m + LAT, z, float(beq.max())))
            if m < gsm or str(t.maker).lower() == W:
                continue
            F = float(mk.fill.sum())
            base = [(float(b), float(s), float(f), None) for b, s, f, w in zip(beq, mk.sign_ms.to_numpy(float), mk.fill.to_numpy(float), isw) if not w]
            # real wallet maker fills in this tx (maker-only real record)
            for p_, f_ in zip(mk.price[isw].to_numpy(float), mk.fill[isw].to_numpy(float)):
                real["sh"][z] += f_
                real["cost"][z] += f_ * p_
            oz = ord_by_tok[z]
            act = oz[(oz.post <= m) & (oz.end >= m - 1e-6)]
            gpt = str(t.maker).lower() in GP
            # update C / D levels from the latest wallet order signed before m (C) and the B anchor (D)
            prior = oz[oz.post <= m]
            if len(prior):
                lr = prior.iloc[-1]
                if lastC[z] is None or lastC[z][3] != lr.salt:
                    lastC[z] = [float(lr.p), float(lr.post), float(lr["size"]), lr.salt]
            if ob[z] is not None:
                pdq = np.floor(ob[z] * 100 + 1e-6) / 100
                if lastD[z] is None or m - lastD[z][1] >= 10000 or abs(lastD[z][0] - pdq) > 1e-9:
                    lastD[z] = [pdq, m, 100.0, "D"]
            for key in "ABCD":
                q = list(base)
                if key == "A":
                    for r in act.itertuples():
                        if remA.get(r.salt, 0) > 1e-9:
                            q.append((float(r.p), float(r.post), remA[r.salt], ("A", r.salt)))
                elif key == "B":
                    for r in act.itertuples():
                        if r.salt not in anchorB:
                            anchorB[r.salt] = None
                        if anchorB[r.salt] is None:
                            # anchor fixed at the order's post time from the state known then
                            anchorB[r.salt] = np.floor(ob[z] * 100 + 1e-6) / 100 if ob[z] is not None else np.nan
                        pb = anchorB[r.salt]
                        if np.isfinite(pb) and LO - 1e-9 <= pb <= HI + 1e-9 and remB.get(r.salt, 0) > 1e-9:
                            q.append((float(pb), float(r.post), remB[r.salt], ("B", r.salt)))
                elif key == "C":
                    if lastC[z] is not None and lastC[z][2] > 1e-9:
                        q.append((lastC[z][0], lastC[z][1], lastC[z][2], ("C", z)))
                else:
                    if lastD[z] is not None and lastD[z][2] > 1e-9 and LO - 1e-9 <= lastD[z][0] <= HI + 1e-9:
                        q.append((lastD[z][0], lastD[z][1], lastD[z][2], ("D", z)))
                q.sort(key=lambda x: (-x[0], x[1]))
                left = F
                for b, s, cap, sid in q:
                    if left <= 1e-9:
                        break
                    take = min(cap, left)
                    left -= take
                    if sid is None or take <= 0:
                        continue
                    S = sets[key]
                    S["sh"][z] += take
                    S["cost"][z] += take * b
                    S["tot"] += take
                    S["gp"] += take if gpt else 0.0
                    if sid[0] == "A":
                        remA[sid[1]] -= take
                    elif sid[0] == "B":
                        remB[sid[1]] -= take
                    elif sid[0] == "C":
                        lastC[z][2] -= take
                    else:
                        lastD[z][2] -= take
        rec = {"cid": cid, "gs": float(gs.get(cid, 0)), "w_pnl": float(pm.loc[cid, "pnl"])}
        rec["real_maker_pnl"] = float(real["sh"][win] - real["cost"].sum())
        rec["real_maker_margin"] = float(min(real["sh"]) * (1 - ((real["cost"][0] / real["sh"][0]) + (real["cost"][1] / real["sh"][1])))) if min(real["sh"]) > 0 else 0.0
        for key, S in sets.items():
            rec[f"{key}_pnl"] = float(S["sh"][win] - S["cost"].sum())
            rec[f"{key}_pairs"] = float(min(S["sh"]))
            rec[f"{key}_pc"] = float(S["cost"][0] / S["sh"][0] + S["cost"][1] / S["sh"][1]) if min(S["sh"]) > 0 else np.nan
            rec[f"{key}_margin"] = float(min(S["sh"]) * (1 - rec[f"{key}_pc"])) if min(S["sh"]) > 0 else 0.0
            rec[f"{key}_gp_share"] = S["gp"] / S["tot"] if S["tot"] else np.nan
            rec[f"{key}_usd"] = float(S["cost"].sum())
        rows.append(rec)
    X = pd.DataFrame(rows)
    X["real_pc"] = np.nan
    res = {}
    for sp, sel in (("BUILD", X.gs < VAL0), ("VALIDATE", (X.gs >= VAL0) & (X.gs < H))):
        y = X[sel]
        o = {"markets": int(len(y)), "wallet_pnl": round(float(y.w_pnl.sum()), 1), "real_maker_pnl": round(float(y.real_maker_pnl.sum()), 1),
             "real_maker_pnl_vs_wallet": corr(y.real_maker_pnl, y.w_pnl), "real_maker_margin_vs_wallet": corr(y.real_maker_margin, y.w_pnl)}
        for key in "ABCD":
            o[key] = {"pnl": round(float(y[f"{key}_pnl"].sum()), 1), "usd": round(float(y[f"{key}_usd"].sum()), 1),
                      "return": round(float(y[f"{key}_pnl"].sum() / max(y[f"{key}_usd"].sum(), 1e-9)), 4),
                      "pnl_vs_wallet": corr(y[f"{key}_pnl"], y.w_pnl), "margin_vs_wallet": corr(y[f"{key}_margin"], y.w_pnl),
                      "pnl_vs_real_maker": corr(y[f"{key}_pnl"], y.real_maker_pnl),
                      "pair_cost_median": round(float(np.nanmedian(y[f"{key}_pc"])), 4),
                      "pairs_vs_wallet_pairs": corr(y[f"{key}_pairs"], y[f"A_pairs"]),
                      "group_P_share": round(float(np.nanmean(y[f"{key}_gp_share"])), 4)}
        res[sp] = o
    X.to_parquet(OUT / "knockout_band_markets.parquet", index=False)
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "knockout_band.json", "w"), indent=1)


if __name__ == "__main__":
    main()
