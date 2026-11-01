"""Iteration 5, mechanics panel iter4 P1 step 3 (X57): public-input ladder variants on the VALIDATED engine.

engine_check2.py showed the X44 engine reproduces the wallet's own orders (88-89% of its real maker shares in the same
tx, 6.5% phantom, maker-only pair cost 0.975 vs the real 0.978), so the replay's 1.005 is the quote rule, not the
engine. Here the quote moves away from the touch: top = others' last observed best bid (LAT = 2 s) - d, L levels 1c
apart, 100 shares, pair-sum cap K on the tops, no bid on a side whose net inventory exceeds IMAX (residual cap).
Scored per market against (a) the wallet's per-market PnL and (b) its maker-only locked margin (from engine_check rows),
with the rule's own locked margin and residual reported separately. Variants are chosen on BUILD only.
Output: results/margin_replay.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter4"))
from queue_replay import corr, load_record, prep_market  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
VAL0, H = 1792540800, 1792713600


def replay(txs, gs_ms, win, K=0.97, SIZE=100.0, L=1, D=0.0, IMAX=400.0, LAT=2000.0, PMIN=0.03, PMAX=0.97):
    txs = sorted(txs, key=lambda r: r[0])
    ob = [None, None]
    inv = np.zeros(2)
    cost = np.zeros(2)
    quote = [None, None]
    pend = []

    def want(zz):
        b0, b1 = ob
        if b0 is None or b1 is None:
            return None
        q = [np.floor(b0 * 100 + 1e-6) / 100 - D, np.floor(b1 * 100 + 1e-6) / 100 - D]
        ex = q[0] + q[1] - K
        if ex > 1e-9:
            if inv[0] > inv[1] + 1e-9:
                q[0] -= ex
            elif inv[1] > inv[0] + 1e-9:
                q[1] -= ex
            else:
                q[0 if q[0] >= q[1] else 1] -= ex
        p = round(q[zz], 2)
        if inv[zz] - inv[1 - zz] > IMAX or p < PMIN or p > PMAX:
            return None
        return p

    def requote(now):
        for zz in (0, 1):
            p = want(zz)
            cur = quote[zz]
            if p is None:
                quote[zz] = None
            elif cur is None or abs(cur[0][0] - p) > 1e-9:
                quote[zz] = [[round(p - 0.01 * k, 2), now, SIZE] for k in range(L)]

    for (m, z, beq, fill, msign, obs, w_taker) in txs:
        while pend and pend[0][0] <= m:
            t_known, zz, val = pend.pop(0)
            ob[zz] = val
            requote(t_known)
        if m < gs_ms:
            if obs is not None:
                pend.append((m + LAT, z, obs))
            continue
        if not w_taker and quote[z] is not None:
            # levels are filled best first: the taker reaches our deeper levels only after our better ones
            taken = 0.0
            for lev in quote[z]:
                p, post, rem = lev
                if rem <= 0:
                    continue
                disp = float(fill[(beq < p - 1e-9) | ((np.abs(beq - p) <= 1e-9) & (msign > post))].sum())
                f = min(rem, max(0.0, disp - taken))  # volume reaching a deeper level must pass our better ones first
                if f > 0:
                    lev[2] -= f
                    inv[z] += f
                    cost[z] += f * p
                    taken += f
                if inv[z] - inv[1 - z] > IMAX:
                    break
            if inv[z] - inv[1 - z] > IMAX:
                quote[z] = None
        if obs is not None:
            pend.append((m + LAT, z, obs))
    pairs = float(min(inv))
    pc = float((cost[0] / inv[0] if inv[0] > 0 else np.nan) + (cost[1] / inv[1] if inv[1] > 0 else np.nan))
    pnl = float(inv[win] - cost.sum())
    margin = pairs * (1 - pc) if np.isfinite(pc) else 0.0
    return {"pnl": pnl, "pairs": pairs, "pair_cost": pc, "usd": float(cost.sum()), "margin": margin, "resid": pnl - margin}


def main():
    cd, gs = load_record()
    pm = pd.read_parquet(OUT / "per_market.parquet")
    pm = pm[pm.cid.isin(set(cd.cid))]
    # wallet maker-only locked margin per market (engine_check rows, real fills)
    V = pd.read_parquet(OUT / "engine_check_rows.parquet")
    mm = {}
    for cid, h in V.groupby("cid"):
        s0 = h[h.z == 0].real.sum(); s1 = h[h.z == 1].real.sum()
        if s0 > 0 and s1 > 0:
            c0 = (h[h.z == 0].real * h[h.z == 0].p).sum() / s0
            c1 = (h[h.z == 1].real * h[h.z == 1].p).sum() / s1
            mm[cid] = min(s0, s1) * (1 - c0 - c1)
        else:
            mm[cid] = 0.0
    pm["w_mmargin"] = pm.cid.map(mm).fillna(0.0)
    cd = cd.sort_values(["cid", "m", "tx", "idx"])
    groups = {c: prep_market(h) for c, h in cd.groupby("cid")}
    print("prepared", flush=True)
    grid = [dict(D=0.0, L=1), dict(D=1.0, L=3), dict(D=2.0, L=3), dict(D=1.0, L=5), dict(D=2.0, L=5), dict(D=3.0, L=5),
            dict(D=2.0, L=5, IMAX=200.0), dict(D=4.0, L=5)]
    res = {"wallet_maker_margin_vs_pnl": {}, "variants": []}
    for sp, sel in (("BUILD", pm.gs < VAL0), ("VALIDATE", pm.gs >= VAL0)):
        y = pm[sel]
        res["wallet_maker_margin_vs_pnl"][sp] = corr(y.w_mmargin, y.pnl)
    for par in grid:
        rows = []
        for r in pm.itertuples():
            g = groups.get(r.cid)
            if g is None:
                continue
            o = replay([tuple(x) for x in g], float(r.gs) * 1000.0, int(r.win), **{k: (v / 100.0 if k == "D" else v) for k, v in par.items()})
            o.update(cid=r.cid, gs=r.gs, w_pnl=r.pnl, w_mm=r.w_mmargin, w_pairs=r.pairs)
            rows.append(o)
        x = pd.DataFrame(rows)
        out = {"params": par}
        for sp, sel in (("BUILD", x.gs < VAL0), ("VALIDATE", x.gs >= VAL0)):
            y = x[sel]
            out[sp] = {"bot_pnl": round(float(y.pnl.sum()), 0), "bot_usd": round(float(y.usd.sum()), 0),
                       "bot_return": round(float(y.pnl.sum() / max(y.usd.sum(), 1e-9)), 4),
                       "bot_margin": round(float(y.margin.sum()), 0), "bot_resid": round(float(y.resid.sum()), 0),
                       "pair_cost_w": round(float(np.average(y.pair_cost.fillna(1), weights=y.pairs + 1e-9)), 4),
                       "corr_pnl_vs_wallet_pnl": corr(y.pnl, y.w_pnl), "corr_margin_vs_wallet_pnl": corr(y.margin, y.w_pnl),
                       "corr_pnl_vs_wallet_maker_margin": corr(y.pnl, y.w_mm), "corr_pairs": corr(y.pairs, y.w_pairs)}
        res["variants"].append(out)
        print(json.dumps(out), flush=True)
    (RES / "margin_replay.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
