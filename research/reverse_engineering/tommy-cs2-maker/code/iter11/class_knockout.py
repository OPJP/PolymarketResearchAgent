"""X151 (mechanics panel iter-10 P3): localize the outcome item by decision class with a class-wise knockout of the
wallet's own maker record in the validated X57 engine (16-22 Oct, its 229 markets).

Start from E = its own filled maker orders (set A of code/iter9/knockout.py) + its real taker leg (0.89 / 0.82 VALIDATE).
Knockouts (one engine replay each; signing times, lifetimes and sizes kept):
  quiet / follow / msg (msg + own_msg) / repair: that ledger class (ledger_rows_iter10.cls) re-priced at the public
  anchor = the last public print on the token at signing, rounded to the cent (ledger a_last; rows without one keep
  their price), i.e. the class's private price replaced by the public one;
  endgame: its orders on the eventual loser priced below 0.15 removed (a stop at 0.15);
  quiet+follow: both classes re-priced (the 92% of orders away from messages and repairs);
  all: every class re-priced (the public-anchor version of its own timing).
Per market PnL at settlement = maker replay + real taker leg; Pearson / Spearman vs its PnL, BUILD and VALIDATE, pair
cost of the maker replay, and the Spearman loss per knockout with a 500-draw event bootstrap (VALIDATE).
Diagnostic with its own orders (oracle timing), never a rule. Output: results/class_knockout.json
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
POST_MS = 24.0
KOS = {"none": set(), "quiet": {"quiet"}, "follow": {"follow"}, "msg": {"msg", "own_msg"}, "repair": {"repair"},
       "quiet+follow": {"quiet", "follow"}, "all": {"quiet", "follow", "msg", "own_msg", "repair"}, "endgame": set()}


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    k = np.isfinite(x) & np.isfinite(y)
    if k.sum() < 5 or np.std(x[k]) == 0:
        return [None, None, int(k.sum())]
    return [round(float(stats.pearsonr(x[k], y[k])[0]), 3), round(float(stats.spearmanr(x[k], y[k])[0]), 3), int(k.sum())]


def main():
    import os
    if os.environ.get("CK_STATS_ONLY"):
        X = pd.read_parquet(OUT / "class_knockout_markets.parquet")
        return stats_part(X)
    cd, gs = load_record()
    cd = cd[cd.m.notna()].copy()
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "salt"])
    a["salt"] = a.salt.astype(str)
    cd = cd.merge(a, on=["tx", "idx"], how="left")
    o = pd.read_parquet(OUT / "orders.parquet")
    o["salt"] = o.salt.astype(str)
    wms = set(o[o.role == "maker"].salt)
    L = pd.read_parquet(OUT / "ledger_rows_iter10.parquet", columns=["salt", "cls", "a_last"])
    L["salt"] = L.salt.astype(str)
    cls_of = dict(zip(L.salt, L.cls))
    anc_of = dict(zip(L.salt, L.a_last))
    pm = pd.read_parquet(OUT / "per_market.parquet").set_index("cid")
    f = pd.read_parquet(OUT / "chain_fills_1792108800_1792713600.parquet")
    f = f[(f.bts < H)]
    tok_oi = o.drop_duplicates("token_id").set_index("token_id")[["cid", "oi"]]
    f = f.merge(tok_oi, left_on="token_id", right_index=True, how="left")
    f = f[f.cid.isin(pm.index)]
    f["win"] = f.cid.map(pm.win)
    f["val"] = f.shares * (f.oi == f.win) - f.usdc
    taker_leg = f[f.role == "taker"].groupby("cid").val.sum()
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
        ords["cls"] = ords.salt.map(cls_of)
        ords["anc"] = ords.salt.map(anc_of)
        txs = []
        for tx, h in g.groupby("tx", sort=False):
            t = h[h.idx == -1]
            if t.empty:
                continue
            t = t.iloc[0]
            if str(t.maker).lower() == W:
                continue
            m = float(t.m)
            z = int(t.oi) if int(t.side) == 1 else 1 - int(t.oi)
            mk = h[h.idx >= 0]
            beq = np.where((mk.side.to_numpy() == 0) & (mk.oi.to_numpy() == z), mk.price.to_numpy(float),
                           np.where((mk.side.to_numpy() == 1) & (mk.oi.to_numpy() != z), 1 - mk.price.to_numpy(float), np.nan))
            ok = np.isfinite(beq)
            if not ok.any():
                continue
            mk, beq = mk[ok], beq[ok]
            isw = (mk.maker == W).to_numpy()
            base = [(float(b), float(s), float(fl), None) for b, s, fl, w in zip(beq, mk.sign_ms.to_numpy(float), mk.fill.to_numpy(float), isw) if not w]
            txs.append((m, z, float(mk.fill.sum()), base))
        rec = {"cid": cid, "gs": float(gs.get(cid, 0)), "w_pnl": float(pm.loc[cid, "pnl"]), "T": float(taker_leg.get(cid, 0.0))}
        post = (ords.sign + POST_MS).to_numpy()
        endv = ords.end.to_numpy()
        byz = {zz: np.where(ords.oi.to_numpy() == zz)[0] for zz in (0, 1)}
        salts = ords.salt.to_numpy()
        for ko, cs in KOS.items():
            pr = ords.p.to_numpy(float).copy()
            keep = np.ones(len(ords), bool)
            if cs:
                sel = ords.cls.isin(cs).to_numpy() & np.isfinite(ords.anc.to_numpy(float))
                pr[sel] = np.clip(np.round(ords.anc.to_numpy(float)[sel], 2), 0.05, 0.95)
            if ko == "endgame":
                keep = ~((ords.oi.to_numpy() != win) & (pr < 0.15))
            rem = dict(zip(salts, ords["size"].astype(float)))
            sh, cost = np.zeros(2), np.zeros(2)
            for m, z, F, base in txs:
                if m < gsm:
                    continue
                ii = byz[z]
                act = ii[(post[ii] <= m) & (endv[ii] >= m - 1e-6) & keep[ii]]
                qq = list(base) + [(pr[i], post[i], rem[salts[i]], i) for i in act if rem[salts[i]] > 1e-9]
                qq.sort(key=lambda x: (-x[0], x[1]))
                left = F
                for b, s, cap, sid in qq:
                    if left <= 1e-9:
                        break
                    take = min(cap, left)
                    left -= take
                    if sid is None:
                        continue
                    rem[salts[sid]] -= take
                    sh[z] += take
                    cost[z] += take * b
            rec[f"{ko}_pnl"] = float(sh[win] - cost.sum())
            rec[f"{ko}_pc"] = float(cost[0] / sh[0] + cost[1] / sh[1]) if min(sh) > 0 else np.nan
        rows.append(rec)
    X = pd.DataFrame(rows)
    X.to_parquet(OUT / "class_knockout_markets.parquet", index=False)
    stats_part(X)


def stats_part(X):
    res = {}
    rng = np.random.default_rng(7)
    for sp, sel in (("BUILD", X.gs < VAL0), ("VALIDATE", (X.gs >= VAL0) & (X.gs < H))):
        y = X[sel].reset_index(drop=True)
        r = {"markets": int(len(y))}
        base_s = stats.spearmanr(y["none_pnl"] + y["T"], y.w_pnl)[0]
        for ko in KOS:
            tot = y[f"{ko}_pnl"] + y["T"]
            c = corr(tot, y.w_pnl)
            boots = []
            for _ in range(500):
                ix = rng.integers(0, len(y), len(y))
                boots.append(stats.spearmanr(y["none_pnl"].iloc[ix] + y["T"].iloc[ix], y.w_pnl.iloc[ix])[0] -
                             stats.spearmanr(tot.iloc[ix], y.w_pnl.iloc[ix])[0])
            r[ko] = {"maker_plus_real_taker": c, "maker_alone": corr(y[f"{ko}_pnl"], y.w_pnl),
                     "maker_pnl": round(float(y[f"{ko}_pnl"].sum()), 1), "pair_cost_median": round(float(np.nanmedian(y[f"{ko}_pc"])), 4),
                     "spearman_loss": round(float(base_s - c[1]), 3) if c[1] is not None else None,
                     "spearman_loss_ci95": [round(float(np.percentile(boots, 2.5)), 3), round(float(np.percentile(boots, 97.5)), 3)]}
        res[sp] = r
    (RES / "class_knockout.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
