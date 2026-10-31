"""Iteration 5: is the maker quote a PAIR-COMPLETION price off its own inventory cost? (assumptions panel iter4 P3
generalised: after any own fill, not only after takes; own state, reported as such.)

For every maker order of the wallet (orders.parquet, 16-22 Oct), the inventory at signing time from its on-chain
fills with block time <= sign time (maker + taker fills, all BUYs): shares S and cost C on each token of the market.
Anchors for the price p of a BUY on token Z (other token O):
  A_avg   = K - C_O / S_O            (avg cost of everything bought on O)
  A_last  = K - last fill price on O
  A_lifo  = K - avg cost of the unpaired excess on O (LIFO: its most recent S_O - S_Z shares), only when long O
  A_take  = K - limit of its last TAKER order on O within W s (the assumptions panel's top_Y = K - L)
  public  = last print on Z's market (block time < sign), converted to Z's price; rebuilt touch is in price_touch.json
K is fitted on BUILD (mode of p + anchor-cost over a 0.01 grid), scored on VALIDATE: share within one in-play tick
(0.01; 0.001 before the in-play tick change is ignored: 90% of VALIDATE orders are at the 0.01 tick).
By inventory state: completing (long O), adding (long Z), flat (|net| < 1 share).
Output: results/own_cost_anchor.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
VAL0, H = 1792540800, 1792713600


def main():
    o = pd.read_parquet(OUT / "orders.parquet")
    o = o[(o.gs_ts < H) & (o.sign_ms > 1.7e12)].copy()
    tokmap = o.drop_duplicates("token_id").set_index("token_id")[["cid", "oi"]]
    f = pd.read_parquet(OUT / "chain_fills_1792108800_1792713600.parquet")
    f = f[f.token_id.isin(tokmap.index)].copy()
    f["cid"] = f.token_id.map(tokmap.cid)
    f["oi"] = f.token_id.map(tokmap.oi).astype(int)
    f["px"] = f.usdc / f.shares
    # taker limits by market (its taker orders)
    tk = o[o.role == "taker"][["cid", "oi", "sign_ms", "price"]].sort_values("sign_ms")
    # tapes for the public last print (windowed taker tapes: all taker prints)
    rows = []
    for cid, om in o[o.role == "maker"].groupby("cid"):
        fm = f[f.cid == cid].sort_values(["bts", "tx"])
        bts = fm.bts.to_numpy(float)
        oi_f = fm.oi.to_numpy(int)
        sh = fm.shares.to_numpy(float)
        px = fm.px.to_numpy(float)
        cs = np.zeros((len(fm) + 1, 2))
        cc = np.zeros((len(fm) + 1, 2))
        for i in range(len(fm)):
            cs[i + 1] = cs[i]
            cc[i + 1] = cc[i]
            cs[i + 1, oi_f[i]] += sh[i]
            cc[i + 1, oi_f[i]] += sh[i] * px[i]
        tp = OUT / "tapes" / f"{cid}_tkw.parquet"
        lp_t = lp_p = None
        if tp.exists():
            d = pd.read_parquet(tp, columns=["timestamp", "price", "outcomeIndex", "proxyWallet"])
            d = d[d.proxyWallet.str.lower() != "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"].sort_values("timestamp")
            lp_t = d.timestamp.to_numpy(float)
            lp_p = np.where(d.outcomeIndex.to_numpy(int) == 0, d.price.to_numpy(float), 1 - d.price.to_numpy(float))  # price of token 0
        tkm = tk[tk.cid == cid]
        for r in om.itertuples():
            t = r.sign_ms / 1000.0
            k = int(np.searchsorted(bts, t, side="right"))
            z = int(r.oi)
            oo = 1 - z
            S, C = cs[k], cc[k]
            rec = {"cid": cid, "gs": int(r.gs_ts), "p": float(r.price), "z": z, "Sz": S[z], "So": S[oo], "Cz": C[z], "Co": C[oo],
                   "sign": t, "shares": float(r.shares)}
            # last fill price on O, and LIFO excess cost on O
            mo = np.flatnonzero(oi_f[:k] == oo)
            rec["last_o"] = float(px[mo[-1]]) if len(mo) else np.nan
            rec["last_o_age"] = float(t - bts[mo[-1]]) if len(mo) else np.nan
            ex = S[oo] - S[z]
            if ex > 1 and len(mo):
                need, cst = ex, 0.0
                for j in mo[::-1]:
                    q = min(need, sh[j])
                    cst += q * px[j]
                    need -= q
                    if need <= 1e-9:
                        break
                rec["lifo_o"] = cst / (ex - max(need, 0)) if ex - max(need, 0) > 0 else np.nan
            else:
                rec["lifo_o"] = np.nan
            # last own taker order on O
            kk = tkm[(tkm.oi == oo) & (tkm.sign_ms < r.sign_ms)]
            if len(kk):
                rec["take_o"] = float(kk.price.iloc[-1])
                rec["take_o_age"] = float(t - kk.sign_ms.iloc[-1] / 1000.0)
            else:
                rec["take_o"], rec["take_o_age"] = np.nan, np.nan
            if lp_t is not None:
                j = int(np.searchsorted(lp_t, t, side="left")) - 1
                rec["last_print"] = (lp_p[j] if z == 0 else 1 - lp_p[j]) if j >= 0 else np.nan
            else:
                rec["last_print"] = np.nan
            rows.append(rec)
    d = pd.DataFrame(rows)
    d = d[d.sign >= d.gs]  # in play
    d["net"] = d.Sz - d.So
    d["state"] = np.where(d.net < -1, "completing", np.where(d.net > 1, "adding", "flat"))
    d["avg_o"] = d.Co / d.So.replace(0, np.nan)
    d["split"] = np.where(d.gs < VAL0, "BUILD", "VALIDATE")
    res = {"n": {s: int((d.split == s).sum()) for s in ("BUILD", "VALIDATE")},
           "state_share": {s: d[d.split == s].state.value_counts(normalize=True).round(3).to_dict() for s in ("BUILD", "VALIDATE")}}

    def fitK(x):
        x = x[np.isfinite(x)]
        if len(x) < 20:
            return None
        grid = np.round(np.arange(0.85, 1.06, 0.01), 2)
        sc = [np.mean(np.abs(x - g) <= 0.0105) for g in grid]
        return float(grid[int(np.argmax(sc))])

    out = {}
    for name, col in [("avg_o", "avg_o"), ("last_o", "last_o"), ("lifo_o", "lifo_o"), ("take_o", "take_o")]:
        out[name] = {}
        for st in ("completing", "adding", "flat", "all"):
            b = d[(d.split == "BUILD") & ((d.state == st) | (st == "all"))]
            v = d[(d.split == "VALIDATE") & ((d.state == st) | (st == "all"))]
            K = fitK((b.p + b[col]).to_numpy(float))
            if K is None:
                continue
            ev = {}
            for nm, dd in (("BUILD", b), ("VALIDATE", v)):
                ok = dd[col].notna()
                pred = K - dd[col]
                within = (np.abs(dd.p - pred) <= 0.0105) & ok
                lp_ok = dd.last_print.notna()
                ev[nm] = {"n": int(len(dd)), "coverage": round(float(ok.mean()), 3) if len(dd) else None,
                          "within_tick_on_covered": round(float(within[ok].mean()), 3) if ok.any() else None,
                          "within_tick_all": round(float(within.mean()), 3) if len(dd) else None,
                          "last_print_within_tick_same_rows": round(float((np.abs(dd.p - dd.last_print) <= 0.0105)[ok & lp_ok].mean()), 3) if (ok & lp_ok).any() else None,
                          "sum_p_plus_cost_p25_p50_p75": [round(float(x), 3) for x in np.nanpercentile((dd.p + dd[col]).to_numpy(float), [25, 50, 75])] if ok.any() else None}
            out[name][st] = {"K": K, **ev}
    # take anchor by age (assumptions P3 windows)
    ages = [(0, 1.04), (1.04, 5), (5, 30), (30, 120), (120, 1e9)]
    tw = {}
    Kt = out.get("take_o", {}).get("all", {}).get("K")
    if Kt:
        for a, b_ in ages:
            for sp in ("BUILD", "VALIDATE"):
                dd = d[(d.split == sp) & (d.take_o_age >= a) & (d.take_o_age < b_)]
                if len(dd) == 0:
                    continue
                w = (np.abs(dd.p - (Kt - dd.take_o)) <= 0.0105).mean()
                lp = (np.abs(dd.p - dd.last_print) <= 0.0105)[dd.last_print.notna()].mean()
                tw[f"{sp}_{a}-{b_}s"] = {"n": int(len(dd)), "K_minus_L": round(float(w), 3), "last_print": round(float(lp), 3)}
    res["anchors"] = out
    res["take_anchor_by_age"] = tw
    # overall public baseline
    for sp in ("BUILD", "VALIDATE"):
        dd = d[(d.split == sp) & d.last_print.notna()]
        res[f"last_print_within_tick_{sp}"] = round(float((np.abs(dd.p - dd.last_print) <= 0.0105).mean()), 3)
    d.to_parquet(OUT / "own_cost_anchor.parquet")
    (RES / "own_cost_anchor.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1)[:6000])


if __name__ == "__main__":
    main()
