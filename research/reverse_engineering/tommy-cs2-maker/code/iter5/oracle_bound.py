"""Iteration 5, mechanics panel iter4 P1 step 4 (X57, DIAGNOSTIC ONLY, uses the wallet's private take times): how much of
the outcome gap do its own events explain?

Base = the best public ladder of margin_replay.py (top = others' bid observed >= 2 s earlier - 4c, 5 levels 1c apart,
100 shares, K 0.97) on the validated engine. Oracle variants (not executable from public data):
  O1 pull:    at each wallet take (sign s, team X bought), the bot's bids on the complement Z are pulled in [s, s + 1,040].
  O2 re-pair: O1, then for 5 s the bot's top on Z is K_rp - L (L = the wallet's take limit, K_rp = 0.94 from X67), 5 levels.
  O3 follow:  O2 plus a copy of the wallet's taker FILLS (its own take legs at their real prices and sizes).
Per-market PnL correlation with the wallet's, BUILD / VALIDATE; the bot's margin and residual.
Output: results/oracle_bound.json
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
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0 = 1792540800


def replay(txs, gs_ms, win, events, mode, K=0.97, SIZE=100.0, L=5, D=0.04, IMAX=400.0, LAT=2000.0, KRP=0.94, REPAIR_MS=5000.0,
           takes=None):
    txs = sorted(txs, key=lambda r: r[0])
    ob = [None, None]
    inv = np.zeros(2)
    cost = np.zeros(2)
    quote = [None, None]
    pend = []
    ev = sorted(events)  # (s, X, limit)

    def active_event(now, zz):
        out = None
        for s, X, lim in ev:
            if s > now:
                break
            if 1 - X == zz and now <= s + 1040 + REPAIR_MS:
                out = (s, X, lim)
        return out

    def want(zz, now):
        if mode >= 2:
            e = active_event(now, zz)
            if e is not None and now > e[0] + 1040:
                return round(KRP - e[2], 2)
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
        if inv[zz] - inv[1 - zz] > IMAX or p < 0.03 or p > 0.97:
            return None
        return p

    def requote(now):
        for zz in (0, 1):
            p = want(zz, now)
            cur = quote[zz]
            if p is None:
                quote[zz] = None
            elif cur is None or abs(cur[0][0] - p) > 1e-9:
                quote[zz] = [[round(p - 0.01 * k, 2), now, SIZE] for k in range(L)]

    tk = sorted(takes or [])
    ti = 0
    for (m, z, beq, fill, msign, obs, w_taker) in txs:
        while pend and pend[0][0] <= m:
            t_known, zz, val = pend.pop(0)
            ob[zz] = val
            requote(t_known)
        if mode >= 2:
            requote(m)
        while mode >= 3 and ti < len(tk) and tk[ti][0] <= m:
            _, X, sh, px = tk[ti]
            inv[X] += sh
            cost[X] += sh * px
            ti += 1
        if m < gs_ms:
            if obs is not None:
                pend.append((m + LAT, z, obs))
            continue
        pulled = False
        if mode >= 1:
            for s, X, lim in ev:
                if s > m:
                    break
                if 1 - X == z and s <= m <= s + 1040:
                    pulled = True
        if not w_taker and quote[z] is not None and not pulled:
            taken = 0.0
            for lev in quote[z]:
                p, post, rem = lev
                if rem <= 0:
                    continue
                disp = float(fill[(beq < p - 1e-9) | ((np.abs(beq - p) <= 1e-9) & (msign > post))].sum())
                f = min(rem, max(0.0, disp - taken))
                if f > 0:
                    lev[2] -= f
                    inv[z] += f
                    cost[z] += f * p
                    taken += f
            if inv[z] - inv[1 - z] > IMAX:
                quote[z] = None
        if obs is not None:
            pend.append((m + LAT, z, obs))
    pairs = float(min(inv))
    pc = float((cost[0] / inv[0] if inv[0] > 0 else np.nan) + (cost[1] / inv[1] if inv[1] > 0 else np.nan))
    pnl = float(inv[win] - cost.sum())
    margin = pairs * (1 - pc) if np.isfinite(pc) else 0.0
    return {"pnl": pnl, "margin": margin, "resid": pnl - margin, "pair_cost": pc, "pairs": pairs, "usd": float(cost.sum())}


def main():
    cd, gs = load_record()
    pm = pd.read_parquet(OUT / "per_market.parquet")
    pm = pm[pm.cid.isin(set(cd.cid))]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "side", "oi", "price", "sign_ms", "cid", "fill"])
    wt = a[(a.idx == -1) & (a.maker == WALLET) & (a.side == 0) & (a.sign_ms > 1.7e12)].drop_duplicates("tx")
    ev_by = {c: [(float(s), int(o), float(p)) for s, o, p in zip(h.sign_ms, h.oi, h.price)] for c, h in wt.groupby("cid")}
    # its taker fills: shares and average price per tx (maker rows of its taker txs, in the bought token's terms)
    mk = a[a.tx.isin(set(wt.tx)) & (a.idx >= 0)]
    tinfo = wt.set_index("tx")[["oi", "sign_ms", "cid"]]
    tk_by = {}
    for tx, h in mk.groupby("tx"):
        X = int(tinfo.loc[tx, "oi"])
        lv = np.where((h.side == 1) & (h.oi == X), h.price, np.where((h.side == 0) & (h.oi != X), 1 - h.price, np.nan))
        f = h.fill.to_numpy(float)
        ok = np.isfinite(lv)
        if not ok.any():
            continue
        sh = float(f[ok].sum())
        tk_by.setdefault(tinfo.loc[tx, "cid"], []).append((float(tinfo.loc[tx, "sign_ms"]) + 1040.0, X, sh, float(np.sum(lv[ok] * f[ok]) / sh)))
    cd = cd.sort_values(["cid", "m", "tx", "idx"])
    groups = {c: prep_market(h) for c, h in cd.groupby("cid")}
    res = {}
    for mode, nm in ((0, "base_public_D4_L5"), (1, "O1_oracle_pull"), (2, "O2_oracle_pull_repair"), (3, "O3_plus_wallet_take_fills")):
        rows = []
        for r in pm.itertuples():
            g = groups.get(r.cid)
            if g is None:
                continue
            o = replay([tuple(x) for x in g], float(r.gs) * 1000.0, int(r.win), ev_by.get(r.cid, []), mode, takes=tk_by.get(r.cid, []))
            o.update(gs=r.gs, w_pnl=r.pnl)
            rows.append(o)
        x = pd.DataFrame(rows)
        out = {}
        for sp, sel in (("BUILD", x.gs < VAL0), ("VALIDATE", x.gs >= VAL0)):
            y = x[sel]
            out[sp] = {"pnl": round(float(y.pnl.sum()), 0), "margin": round(float(y.margin.sum()), 0), "resid": round(float(y.resid.sum()), 0),
                       "pair_cost_w": round(float(np.average(y.pair_cost.fillna(1), weights=y.pairs + 1e-9)), 4),
                       "corr_pnl_vs_wallet": corr(y.pnl, y.w_pnl)}
        res[nm] = out
        print(nm, json.dumps(out), flush=True)
    (RES / "oracle_bound.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
