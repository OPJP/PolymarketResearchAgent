"""Iteration 4, mechanics panel iter3 P2 (X49): outcome by a QUEUE-AWARE replay of a public quote rule on the full
matched-order record (wallet txs: calldata_all; every public taker tx of its markets: calldata_pub), 16-22 Oct.

Rule (point-in-time, executable, strict fills, latency LAT):
  * state = the last OBSERVED best bid of the other makers on each token (others' book). A public tx that consumed
    bids on token Z reveals the best bid on Z just before it: the highest bid-equivalent price among its NON-wallet
    maker orders (maker BUY Z at p -> p; maker SELL of the complement at q -> 1 - q). Observations become usable
    LAT ms after the tx's match time.
  * quote: join others' best bid on both tokens (whole cents); if the two bids sum to more than K, shade the side the
    bot is long (flat: the higher-priced side) by the excess; no bid on a side whose net inventory exceeds IMAX;
    no bid outside [PMIN, PMAX]. One level of SIZE shares per token (variant: L levels 1c apart). In play only.
  * fills (strict, price-time priority): a public tx that consumed bids on Z fills our bid b on Z only with the
    volume it gave to makers at a bid-equivalent price strictly below b, or equal to b with a later signing time than
    our post time (we would have been ahead of them). The wallet's own maker volume is treated as displaceable (the
    bot replaces the wallet). The wallet's own taker txs are removed from the flow (private-information decisions).
  * pairs merge at 1, the residual settles at the outcome; no fees for makers; rebates ignored.
  Variant (b), diagnostic oracle only: the bot also pulls its bid on the complement of the team the wallet buys,
  from the wallet's taker signing to +1,040 ms (its observed pull), then re-joins.
Per-market PnL vs the wallet's per-market settlement PnL (per_market.parquet), Pearson / Spearman, BUILD (gs < 10-21)
and VALIDATE (10-21..22) separately; also pair cost and paired volume. Parameters are fixed a priori (K from the
mechanics panel's live estimate 0.97), a small grid is reported but chosen on BUILD only.
Output: results/queue_replay.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0, H = 1792540800, 1792713600


def load_record():
    cols = ["tx", "block", "idx", "maker", "side", "token_id", "price", "shares", "sign_ms", "fill"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["bts"])
    parts = [pd.read_parquet(p, columns=cols) for p in sorted((OUT / "calldata_pub").glob("*.parquet"))]
    b = pd.concat(parts, ignore_index=True)
    b = b[~b.tx.isin(set(a.tx))]
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "token_id", "oi", "gs_ts"]).drop_duplicates("token_id")
    tok = dict(zip(o.token_id.astype(str), zip(o.cid, o.oi)))
    # block timestamps of public txs from the windowed taker tapes
    cids = set(o.cid)
    ts = {}
    for cid in cids:
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if p.exists():
            d = pd.read_parquet(p, columns=["transactionHash", "timestamp"])
            ts.update(dict(zip(d.transactionHash, d.timestamp.astype(float))))
    b["bts"] = b.tx.map(ts)
    cd = pd.concat([a, b], ignore_index=True)
    cd["tok"] = cd.token_id.astype(str)
    cd = cd[cd.tok.isin(tok)].copy()
    cd["cid"] = cd.tok.map(lambda t: tok[t][0])
    cd["oi"] = cd.tok.map(lambda t: tok[t][1]).astype(int)
    cd = cd[cd.bts.notna()]
    tk = cd[cd.idx == -1].drop_duplicates("tx").set_index("tx")
    sg = tk.sign_ms.where((tk.sign_ms > 1.7e12) & (tk.sign_ms < 1.8e12))
    blk = tk.bts * 1000.0
    m = np.where(sg.notna() & (sg + 1040 < blk + 1) & (sg + 1040 > blk - 15000), np.minimum(blk, sg + 1040), blk)
    cd["m"] = cd.tx.map(pd.Series(m, index=tk.index))
    cd["t_maker"] = cd.tx.map(tk.maker)
    cd["t_side"] = cd.tx.map(tk.side)
    cd["t_oi"] = cd.tx.map(tk.oi)
    return cd, dict(zip(o.cid, o.gs_ts))


def prep_market(g):
    """Per-tx tuples of one market (computed once): (m, Z, bid-eq prices, fills, maker signs, obs, wallet_taker)."""
    g = g.sort_values(["m", "tx", "idx"])
    txa = g.tx.to_numpy()
    cut = np.flatnonzero(txa[1:] != txa[:-1]) + 1
    idx = g.idx.to_numpy(); side = g.side.to_numpy(); oi = g.oi.to_numpy(); pr = g.price.to_numpy(float)
    fl = g.fill.to_numpy(float); sg = g.sign_ms.to_numpy(float); mk = g.maker.to_numpy(); mm = g.m.to_numpy(float)
    txs = []
    for lo, hi in zip(np.r_[0, cut], np.r_[cut, len(g)]):
        ti = np.flatnonzero(idx[lo:hi] == -1)
        if len(ti) == 0:
            continue
        t = lo + ti[0]
        ms = np.arange(lo, hi)[idx[lo:hi] >= 0]
        if len(ms) == 0:
            continue
        z = int(oi[t]) if int(side[t]) == 1 else 1 - int(oi[t])
        beq = np.where((side[ms] == 0) & (oi[ms] == z), pr[ms], np.where((side[ms] == 1) & (oi[ms] != z), 1 - pr[ms], np.nan))
        ok = np.isfinite(beq)
        if not ok.any():
            continue
        # brief: the wallet's own prints and prints in txs where it was a maker are never features
        has_w = bool((mk[lo:hi] == WALLET).any())
        obs = float(np.nanmax(beq[ok])) if not has_w else None
        txs.append((float(mm[t]), z, beq[ok], fl[ms][ok], sg[ms][ok], obs, mk[t] == WALLET))
    return txs


def replay_market(txs, gs_ms, win, K=0.97, SIZE=100.0, L=1, IMAX=400.0, LAT=2000.0, PMIN=0.03, PMAX=0.97,
                  pulls=None):
    """txs: prep_market output. Returns dict with pnl, pairs, pair_cost, usd, n_fills."""
    txs.sort(key=lambda r: r[0])
    ob = [None, None]
    inv = np.zeros(2)
    cost = np.zeros(2)
    quote = [None, None]  # (price, post_ms, remaining) per token; L levels -> list
    pend = []
    nf = 0

    def want(zz):
        b0, b1 = ob
        if b0 is None or b1 is None:
            return None
        q = [np.floor(b0 * 100 + 1e-6) / 100, np.floor(b1 * 100 + 1e-6) / 100]
        ex = q[0] + q[1] - K
        if ex > 1e-9:
            if inv[0] > inv[1] + 1e-9:
                q[0] -= ex
            elif inv[1] > inv[0] + 1e-9:
                q[1] -= ex
            else:
                hi = 0 if q[0] >= q[1] else 1
                q[hi] -= ex
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

    pi = 0
    pulls = pulls or []  # list of (start_ms, end_ms, token pulled)
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
            pulled = any(a <= m <= b and tz == z for a, b, tz in pulls)
            if not pulled:
                for lev in quote[z]:
                    p, post, rem = lev
                    if rem <= 0:
                        continue
                    disp = fill[(beq < p - 1e-9) | ((np.abs(beq - p) <= 1e-9) & (msign > post))].sum()
                    f = min(rem, float(disp))
                    if f > 0:
                        lev[2] -= f
                        inv[z] += f
                        cost[z] += f * p
                        nf += 1
        if obs is not None:
            pend.append((m + LAT, z, obs))
    pairs = float(min(inv))
    pay = inv[win]
    pnl = float(pay - cost.sum())
    pc = float((cost[0] / inv[0] if inv[0] > 0 else np.nan) + (cost[1] / inv[1] if inv[1] > 0 else np.nan))
    return {"pnl": pnl, "pairs": pairs, "pair_cost": pc, "usd": float(cost.sum()), "n_fills": nf,
            "net": float(inv[0] - inv[1])}


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    k = np.isfinite(x) & np.isfinite(y)
    if k.sum() < 5 or np.std(x[k]) == 0:
        return [None, None, int(k.sum())]
    return [round(float(stats.pearsonr(x[k], y[k])[0]), 3), round(float(stats.spearmanr(x[k], y[k])[0]), 3), int(k.sum())]


def main():
    cd, gs = load_record()
    pm = pd.read_parquet(OUT / "per_market.parquet")
    pm = pm[pm.cid.isin(set(cd.cid))]
    cd = cd.sort_values(["cid", "m", "tx", "idx"])
    # wallet pulls (oracle variant): its taker BUY of token X at sign -> pull our bid on the complement (Z = 1 - X)
    wt = cd[(cd.idx == -1) & (cd.maker == WALLET) & (cd.side == 0)].drop_duplicates("tx")
    pulls_by = {c: [(s, s + 1040.0, 1 - int(o)) for s, o in zip(h.sign_ms, h.oi)] for c, h in wt.groupby("cid")}
    groups = {c: prep_market(h) for c, h in cd.groupby("cid")}
    print('prepared', sum(len(v) for v in groups.values()), 'txs', flush=True)
    grid = [dict(K=0.97, L=1), dict(K=0.97, L=3), dict(K=0.96, L=1), dict(K=0.98, L=1), dict(K=0.97, L=1, IMAX=200.0),
            dict(K=0.97, L=1, LAT=1000.0)]
    res = {"n_markets": int(len(pm)), "variants": []}
    for par in grid:
        for oracle in (False, True):
            rows = []
            for r in pm.itertuples():
                g = groups.get(r.cid)
                if g is None:
                    continue
                o = replay_market(g, float(r.gs) * 1000.0, int(r.win), pulls=pulls_by.get(r.cid) if oracle else None, **par)
                o.update(cid=r.cid, gs=r.gs, w_pnl=r.pnl, w_pc=r.pair_cost, w_pairs=r.pairs)
                rows.append(o)
            x = pd.DataFrame(rows)
            out = {"params": par, "oracle_pulls": oracle}
            for split, sel in (("BUILD", x.gs < VAL0), ("VALIDATE", (x.gs >= VAL0) & (x.gs < H))):
                y = x[sel]
                out[split] = {"markets": int(len(y)), "bot_pnl": round(float(y.pnl.sum()), 1),
                              "bot_usd": round(float(y.usd.sum()), 1),
                              "bot_return": round(float(y.pnl.sum() / max(y.usd.sum(), 1e-9)), 4),
                              "wallet_pnl": round(float(y.w_pnl.sum()), 1),
                              "pnl_corr_pearson_spearman_n": corr(y.pnl, y.w_pnl),
                              "pair_cost_corr": corr(y.pair_cost, y.w_pc),
                              "pairs_corr": corr(y.pairs, y.w_pairs),
                              "bot_pair_cost_median": round(float(np.nanmedian(y.pair_cost)), 4),
                              "bot_pairs_share": round(float(2 * y.pairs.sum() / max((y.usd / np.maximum(y.pair_cost / 2, 1e-9)).sum(), 1e-9)), 3)}
            res["variants"].append(out)
            print(json.dumps(out), flush=True)
            if par == grid[0] and not oracle:
                x.to_parquet(OUT / "queue_replay_markets.parquet", index=False)
    json.dump(res, open(RES / "queue_replay.json", "w"), indent=1)


if __name__ == "__main__":
    main()
