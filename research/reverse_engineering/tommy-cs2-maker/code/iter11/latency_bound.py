"""X155 (assumptions panel iter-10 P3) + X149 step 1 (mechanics panel iter-10 P1): the outcome item's latency bound.

Validated X57 engine (code/iter9/knockout.py set A: strict price-time re-allocation of each public tx's maker volume
along the merged queue; the wallet's maker rows replaced by ours), 16-22 Oct, its 229 markets.
Maker leg A_L: every own filled maker order delayed by L: resting [sign + 24 ms + L, its last real fill + L]
(L in {0, 50, 100, 250, 500, 1000, 2000} ms; the shifted end assumes its observed lifetime, a stated assumption
because cancels are not on chain).
Taker leg T_L for each own take (FAK BUY at its limit, size cap = its real filled shares), matched at its real match
time + L, two bounds on the stale remainder it would still find:
  T_lo: only liquidity at <= its limit that public BUY takers on the same token actually consumed in
        [m_real + L, m_real + L + 30 s] (known to have survived), at those prices;
  T_hi: its real fill minus what public BUY followers consumed at <= its limit in (m_real, m_real + L] (no maker
        cancels; an upper bound), at its real VWAP.
T_0 = its real taker leg. Per market PnL at settlement; Pearson / Spearman of A_L + T_L (and A_L + real taker leg,
A_L alone) against the wallet's per-market PnL on BUILD (game start < 10-21) and VALIDATE; pair cost of A_L.
Oracle-timed (its own decisions shifted): a feasibility bound, never a rule. Output: results/latency_bound.json
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
LS = [0, 50, 100, 250, 500, 1000, 2000]


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    k = np.isfinite(x) & np.isfinite(y)
    if k.sum() < 5 or np.std(x[k]) == 0:
        return [None, None, int(k.sum())]
    return [round(float(stats.pearsonr(x[k], y[k])[0]), 3), round(float(stats.spearmanr(x[k], y[k])[0]), 3), int(k.sum())]


def main():
    cd, gs = load_record()
    cd = cd[cd.m.notna()].copy()
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "salt"])
    a["salt"] = a.salt.astype(str)
    cd = cd.merge(a, on=["tx", "idx"], how="left")
    o = pd.read_parquet(OUT / "orders.parquet")
    o["salt"] = o.salt.astype(str)
    wms = set(o[o.role == "maker"].salt)
    pm = pd.read_parquet(OUT / "per_market.parquet").set_index("cid")
    tk_own = o[o.role == "taker"].copy()
    # the wallet's real taker fills per take (chain fills by tx) and real match time of each take
    f = pd.read_parquet(OUT / "chain_fills_1792108800_1792713600.parquet")
    f = f[(f.bts < H) & (f.role == "taker")]
    rows = []
    for cid, g in cd.groupby("cid"):
        if cid not in pm.index:
            continue
        g = g.sort_values(["m", "tx", "idx"])
        gsm = float(gs.get(cid, 0)) * 1000.0
        win = int(pm.loc[cid, "win"])
        wm = g[(g.idx >= 0) & (g.maker == W) & g.salt.isin(wms)]
        ords = wm.groupby("salt").agg(oi=("oi", "first"), side=("side", "first"), p=("price", "first"), size=("shares", "first"),
                                      sign=("sign_ms", "first"), end=("m", "max")).reset_index() if len(wm) else pd.DataFrame()
        if len(ords):
            ords = ords[(ords.side == 0) & (ords.sign > 1.7e12)].sort_values("sign")
        # public tx list (taker rows) with their maker rows, excluding txs where the wallet is the taker
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
            base = [(float(b), float(s), float(fl)) for b, s, fl, w in zip(beq, mk.sign_ms.to_numpy(float), mk.fill.to_numpy(float), isw) if not w]
            txs.append((m, z, float(mk.fill.sum()), base, int(t.oi), int(t.side)))
        rec = {"cid": cid, "gs": float(gs.get(cid, 0)), "w_pnl": float(pm.loc[cid, "pnl"])}
        for L in LS:
            sh, cost = np.zeros(2), np.zeros(2)
            if len(ords):
                rem = dict(zip(ords.salt, ords["size"].astype(float)))
                post = (ords.sign + POST_MS + L).to_numpy()
                endv = (ords.end + L).to_numpy()
                byz = {zz: np.where(ords.oi.to_numpy() == zz)[0] for zz in (0, 1)}
                salts = ords.salt.to_numpy()
                prices = ords.p.to_numpy(float)
                for m, z, F, base, _, _ in txs:
                    if m < gsm:
                        continue
                    ii = byz[z]
                    act = ii[(post[ii] <= m) & (endv[ii] >= m - 1e-6)]
                    qq = list(base) + [(prices[i], post[i], rem[salts[i]], i) for i in act if rem[salts[i]] > 1e-9]
                    qq = [(x[0], x[1], x[2], x[3] if len(x) > 3 else None) for x in qq]
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
            rec[f"A{L}_pnl"] = float(sh[win] - cost.sum())
            rec[f"A{L}_pc"] = float(cost[0] / sh[0] + cost[1] / sh[1]) if min(sh) > 0 else np.nan
        # taker legs
        tko = tk_own[tk_own.cid == cid]
        ff = f[f.tx.isin(set(g.tx))]
        real_val = 0.0
        lo = {L: 0.0 for L in LS}
        hi = {L: 0.0 for L in LS}
        for r in tko.itertuples():
            if r.filled <= 0:
                continue
            gt = g[(g.idx == -1) & (g.maker == W) & (g.salt == str(r.salt))]
            if gt.empty:
                continue
            m0 = float(gt.m.iloc[0])
            z = int(r.oi)
            lim = float(r.price)
            pay = float(ff[ff.tx == gt.tx.iloc[0]].usdc.sum()) if len(ff) else float(r.filled) * lim
            vw = pay / float(r.filled) if r.filled > 0 else lim
            real_val += float(r.filled) * (1.0 if z == win else 0.0) - pay
            # public BUY takers on token z after m0 (consumed maker liquidity at <= lim)
            # fix (iteration 11, found during the write-up; the first run, kept as .cache/re/tommy-cs2-maker/latency_bound_buggy_followers.json,
            # used the opposite direction and is superseded): in the engine record zz is the token whose BIDS a
            # public tx consumes; a public BUY of token z consumes bids on 1 - z (BUY-equivalent price b), i.e. asks on z
            # at 1 - b. Followers of its take are therefore txs with zz == 1 - z, at ask prices 1 - b <= its limit.
            evs = [(m, sum(fl for b, s, fl in base if (1 - b) <= lim + 1e-9), [((1 - b), fl) for b, s, fl in base if (1 - b) <= lim + 1e-9])
                   for m, zz, F, base, toi, tsd in txs if zz == 1 - z and m > m0]
            for L in LS:
                # lower bound: what others consumed in [m0 + L, m0 + L + 30 s]
                need = float(r.filled)
                val = 0.0
                for m, q_, lv in evs:
                    if m < m0 + L or m > m0 + L + 30000 or need <= 1e-9:
                        continue
                    for b, fl in sorted(lv):
                        tke = min(fl, need)
                        need -= tke
                        val += tke * ((1.0 if z == win else 0.0) - b)
                        if need <= 1e-9:
                            break
                lo[L] += val if L > 0 else float(r.filled) * (1.0 if z == win else 0.0) - pay
                # upper bound: real fill minus followers' consumption in (m0, m0 + L]
                cons = sum(q_ for m, q_, lv in evs if m <= m0 + L)
                got = max(0.0, float(r.filled) - cons) if L > 0 else float(r.filled)
                hi[L] += got * ((1.0 if z == win else 0.0) - vw)
        rec["T_real"] = real_val
        for L in LS:
            rec[f"Tlo{L}"] = lo[L]
            rec[f"Thi{L}"] = hi[L]
        rows.append(rec)
    X = pd.DataFrame(rows)
    X.to_parquet(OUT / "latency_bound_markets.parquet", index=False)
    res = {}
    for sp, sel in (("BUILD", X.gs < VAL0), ("VALIDATE", (X.gs >= VAL0) & (X.gs < H))):
        y = X[sel]
        r = {"markets": int(len(y)), "T_real_vs_wallet": corr(y.T_real, y.w_pnl)}
        for L in LS:
            r[f"L{L}"] = {"A_alone": corr(y[f"A{L}_pnl"], y.w_pnl),
                          "A_plus_real_taker": corr(y[f"A{L}_pnl"] + y.T_real, y.w_pnl),
                          "A_plus_T_lo": corr(y[f"A{L}_pnl"] + y[f"Tlo{L}"], y.w_pnl),
                          "A_plus_T_hi": corr(y[f"A{L}_pnl"] + y[f"Thi{L}"], y.w_pnl),
                          "A_pnl": round(float(y[f"A{L}_pnl"].sum()), 1),
                          "A_pair_cost_median": round(float(np.nanmedian(y[f"A{L}_pc"])), 4),
                          "T_lo_pnl": round(float(y[f"Tlo{L}"].sum()), 1), "T_hi_pnl": round(float(y[f"Thi{L}"].sum()), 1)}
        res[sp] = r
    (RES / "latency_bound.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
