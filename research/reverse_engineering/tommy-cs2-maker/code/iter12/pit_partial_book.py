"""X165 (mechanics panel iter-11 P3, step 1): a point-in-time partial-fill book as the historical price anchor.

The operator's matched record lists every filled maker order with its full size (calldata). An order of another maker
that has been partly filled in a block at or before t - LAG_S and whose cumulative fill is below its size is known, at
t, to have been resting at its price (it may have been cancelled since; the age cutoff since its last fill limits that).
PIT bid on token X at the wallet's signing time t = the highest price among other makers' BUY orders on X qualifying
at t; PIT ask cap = 1 - the highest qualifying BUY on the complement. Block times: calldata_all's block timestamps,
interpolated for blocks seen only in calldata_pub. Every wallet order's own fills and every tx with a wallet order
are excluded from the book.
Anchors scored within one tick (1c) of the wallet's filled maker orders: PIT bid (age cutoff A fitted on BUILD from a
grid), PIT bid capped at ask cap - 1c, and the last public print (rule anchor), on BUILD (gs < 10-21) and VALIDATE.
The panel's pre-registered bar: freeze in evaluate() only if VALIDATE gains >= +0.05 over the last print.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
SPLIT, H = 1792540800, 1792713600
LAG_S = 2.0
AGES = (10, 30, 60, 120, 300)
TICK = 0.0101


def main():
    cols = ["tx", "block", "idx", "maker", "side", "token_id", "price", "shares", "salt", "fill"]
    ca = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["bts"])
    pub = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(OUT / "calldata_pub/*.parquet")))])
    bk = ca.drop_duplicates("block")[["block", "bts"]].sort_values("block")
    pub["bts"] = np.interp(pub.block.to_numpy(float), bk.block.to_numpy(float), bk.bts.to_numpy(float))
    allo = pd.concat([ca, pub], ignore_index=True)
    allo["mk"] = allo.maker.str.lower()
    wtx = set(allo.loc[allo.mk == WALLET, "tx"])
    m = allo[(allo.idx >= 0) & (allo.side == 0) & (allo.mk != WALLET) & ~allo.tx.isin(wtx) & (allo.bts < H)].copy()
    m["token_id"] = m.token_id.astype(str)
    m = m.drop_duplicates(["tx", "mk", "salt"])
    m = m.sort_values("bts")
    ev_by_tok = {t: g[["bts", "mk", "salt", "price", "shares", "fill"]].to_numpy() for t, g in m.groupby("token_id")}
    tok2 = {}
    mk = json.load(open(OUT / "markets_dev.json"))
    for cid, x in mk.items():
        toks = x.get("clobTokenIds"); toks = json.loads(toks) if isinstance(toks, str) else (toks or [])
        if len(toks) == 2:
            tok2[str(toks[0])] = str(toks[1]); tok2[str(toks[1])] = str(toks[0])
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "token_id", "price", "role", "gs_ts", "cid", "oi"])
    o = o[(o.role == "maker") & (o.sign_ms / 1000 < H)].copy()
    o["token_id"] = o.token_id.astype(str)
    led = pd.read_parquet(OUT / "ledger_rows_iter10.parquet", columns=["sign_ms", "cid", "oi", "price", "a_last", "cls"])
    o = o.merge(led.drop_duplicates(["sign_ms", "cid", "oi", "price"]), on=["sign_ms", "cid", "oi", "price"], how="left")
    o["t"] = o.sign_ms / 1000.0

    def pit_best(tok, times, age):
        """highest qualifying price at each time (vector), per token, sweeping events once."""
        ev = ev_by_tok.get(tok)
        out = np.full(len(times), np.nan)
        if ev is None:
            return out
        order = np.argsort(times)
        state = {}  # (mk, salt) -> [price, shares, cum, last]
        j = 0
        for ii in order:
            tcut = times[ii] - LAG_S
            while j < len(ev) and ev[j][0] <= tcut:
                bts, mkr, salt, price, shares, fill = ev[j]
                k = (mkr, salt)
                if k in state:
                    state[k][2] += float(fill); state[k][3] = float(bts)
                else:
                    state[k] = [float(price), float(shares), float(fill), float(bts)]
                j += 1
            best = np.nan
            dead = []
            for k, (pr, sh, cum, last) in state.items():
                if cum >= sh - 0.5:
                    dead.append(k); continue
                if times[ii] - last > max(AGES):
                    dead.append(k); continue
                if times[ii] - last <= age and (not np.isfinite(best) or pr > best):
                    best = pr
            for k in dead:
                state.pop(k, None)
            out[ii] = best
        return out

    res = {}
    for age in AGES:
        bid = np.full(len(o), np.nan); cap = np.full(len(o), np.nan)
        for tok, g in o.groupby("token_id"):
            idx = g.index.to_numpy()
            tt = g.t.to_numpy()
            pos = o.index.get_indexer(idx)
            bid[pos] = pit_best(tok, tt, age)
            c = tok2.get(tok)
            if c is not None:
                cb = pit_best(c, tt, age)
                cap[pos] = 1 - cb
        o[f"bid{age}"] = bid; o[f"cap{age}"] = cap
    o["split"] = np.where(o.gs_ts < SPLIT, "BUILD", "VALIDATE")
    o.to_parquet(OUT / "iter12/pit_partial_book_rows.parquet", index=False)
    for sp, X in o.groupby("split"):
        r = {"orders": int(len(X)), "last_print_within_tick": round(float((np.abs(X.price - X.a_last) <= TICK).mean()), 3)}
        for age in AGES:
            b = X[f"bid{age}"]; cp = X[f"cap{age}"]
            capped = np.where(np.isfinite(cp), np.minimum(b, np.round(cp - 0.01, 2)), b)
            cov = np.isfinite(b)
            r[f"age{age}"] = {"coverage": round(float(cov.mean()), 3),
                              "bid_within_tick_covered": round(float((np.abs(X.price - b) <= TICK)[cov].mean()), 3) if cov.any() else None,
                              "bid_within_tick_fallback_last": round(float(np.where(cov, np.abs(X.price - b) <= TICK, np.abs(X.price - X.a_last) <= TICK).mean()), 3),
                              "capped_within_tick_fallback_last": round(float(np.where(cov, np.abs(X.price - capped) <= TICK, np.abs(X.price - X.a_last) <= TICK).mean()), 3),
                              "union_bid_or_last": round(float(((np.abs(X.price - b) <= TICK) | (np.abs(X.price - X.a_last) <= TICK)).mean()), 3)}
        res[sp] = r
    # choose age on BUILD (fallback-to-last unit), report VALIDATE at that age
    bA = max(AGES, key=lambda a: res["BUILD"][f"age{a}"]["bid_within_tick_fallback_last"])
    bC = max(AGES, key=lambda a: res["BUILD"][f"age{a}"]["capped_within_tick_fallback_last"])
    res["chosen_on_BUILD"] = {"bid_age": bA, "VALIDATE_bid_fallback": res["VALIDATE"][f"age{bA}"]["bid_within_tick_fallback_last"],
                              "capped_age": bC, "VALIDATE_capped_fallback": res["VALIDATE"][f"age{bC}"]["capped_within_tick_fallback_last"],
                              "VALIDATE_last_print": res["VALIDATE"]["last_print_within_tick"]}
    # event bootstrap of the VALIDATE gain at the chosen age
    V = o[o.split == "VALIDATE"].copy()
    b = V[f"bid{bA}"]
    hit_new = np.where(np.isfinite(b), np.abs(V.price - b) <= TICK, np.abs(V.price - V.a_last) <= TICK).astype(float)
    hit_old = (np.abs(V.price - V.a_last) <= TICK).astype(float)
    V["d"] = hit_new - hit_old
    ev = V.cid.to_numpy()
    uniq = np.unique(ev)
    rng = np.random.default_rng(7)
    gsum = V.groupby("cid").d.sum(); gn = V.groupby("cid").size()
    boots = []
    for _ in range(2000):
        s = rng.choice(uniq, len(uniq), replace=True)
        boots.append(gsum.loc[s].sum() / gn.loc[s].sum())
    res["VALIDATE_gain_bid_fallback"] = {"gain": round(float(V.d.mean()), 4), "ci95": [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)]}
    (RES / "pit_partial_book.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
