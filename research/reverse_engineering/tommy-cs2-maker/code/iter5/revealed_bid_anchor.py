"""Iteration 5 (price, X67 follow-up): an h1/h2-examinable maker price anchor from the matched-order record.

For each wallet maker order on token Z (in play, 16-22 Oct), the other makers' best bid on Z REVEALED by the latest
public transaction (no wallet order in it) that consumed bids on Z: the highest bid-equivalent price among its maker
rows (maker BUY Z at p -> p; maker SELL of the complement at q -> 1 - q). Availability: (a) block time < signing (the
on-chain record, like the last-print anchor), (b) match time (taker sign + 1,040 ms, capped at block time) < signing.
Also the revealed best ASK on Z (from public txs that consumed asks on Z) minus 1c, and max(bid, ask - 1c).
Within one in-play tick (0.0105) of the order price, BUILD and VALIDATE, against the last public print on the same rows.
Output: results/revealed_bid_anchor.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter4"))
from queue_replay import load_record  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0 = 1792540800


def main():
    cd, gs = load_record()
    cd = cd[cd.m.notna()].copy()
    o = pd.read_parquet(OUT / "orders.parquet")
    o = o[(o.role == "maker") & (o.sign_ms > 1.7e12) & o.event.astype(str).str.startswith("cs2")]
    rows = []
    for cid, g in cd.groupby("cid"):
        g = g.sort_values(["m", "tx", "idx"])
        tx = g.tx.to_numpy(); idx = g.idx.to_numpy(); side = g.side.to_numpy().astype(int); oi = g.oi.to_numpy().astype(int)
        pr = g.price.to_numpy(float); mm = g.m.to_numpy(float); mk = g.maker.to_numpy(); bt = g.bts.to_numpy(float) * 1000.0
        cut = np.flatnonzero(tx[1:] != tx[:-1]) + 1
        ev = []  # (block_ms, match_ms, token whose bids were consumed or None, best bid-eq, token whose asks were consumed, best ask-eq, print price token0)
        for lo, hi in zip(np.r_[0, cut], np.r_[cut, len(g)]):
            if (mk[lo:hi] == WALLET).any():
                continue
            ti = np.flatnonzero(idx[lo:hi] == -1)
            if len(ti) == 0:
                continue
            t = lo + ti[0]
            ms = np.arange(lo, hi)[idx[lo:hi] >= 0]
            if len(ms) == 0:
                continue
            # taker SELL of oi or BUY of 1-oi consumes bids on z; taker BUY of oi consumes asks on oi
            z = int(oi[t]) if side[t] == 1 else 1 - int(oi[t])
            beq = np.where((side[ms] == 0) & (oi[ms] == z), pr[ms], np.where((side[ms] == 1) & (oi[ms] != z), 1 - pr[ms], np.nan))
            bb = float(np.nanmax(beq)) if np.isfinite(beq).any() else np.nan
            # the same tx seen from the other token: consumed asks on 1 - z at price 1 - (bid-eq)
            p0 = float(pr[t]) if oi[t] == 0 else 1 - float(pr[t])
            ev.append((bt[t], mm[t], z, bb, p0))
        if not ev:
            continue
        E = pd.DataFrame(ev, columns=["b", "m", "z", "bb", "p0"]).sort_values("b")
        om = o[o.cid == cid]
        for avail in ("b", "m"):
            Es = E.sort_values(avail)
            ta = Es[avail].to_numpy(float)
            zz = Es.z.to_numpy(int); bbv = Es.bb.to_numpy(float); p0v = Es.p0.to_numpy(float)
            for r in om.itertuples():
                s = r.sign_ms
                j = int(np.searchsorted(ta, s, side="left")) - 1
                if j < 0:
                    continue
                Z = int(r.oi)
                # latest revealed bid on Z and latest revealed ask on Z (= 1 - bid on the complement)
                k = j
                bidZ = askZ = np.nan
                while k >= 0 and (np.isnan(bidZ) or np.isnan(askZ)) and j - k < 400:
                    if zz[k] == Z and np.isnan(bidZ):
                        bidZ = bbv[k]
                    if zz[k] != Z and np.isnan(askZ) and np.isfinite(bbv[k]):
                        askZ = 1 - bbv[k]
                    k -= 1
                lp = p0v[j] if Z == 0 else 1 - p0v[j]
                rows.append((cid, float(r.gs_ts), avail, float(r.price), bidZ, askZ, lp, s / 1000.0 >= r.gs_ts))
    D = pd.DataFrame(rows, columns=["cid", "gs", "avail", "p", "bid", "ask", "lp", "inplay"])
    D = D[D.inplay]
    D["split"] = np.where(D.gs < VAL0, "BUILD", "VALIDATE")
    res = {}
    for (sp, av), x in D.groupby(["split", "avail"]):
        r = {"n": int(len(x))}
        ok = x.bid.notna()
        r["bid_coverage"] = round(float(ok.mean()), 3)
        w = lambda a: round(float((np.abs(x.p - a) <= 0.0105).mean()), 4)
        r["revealed_bid"] = w(x.bid.fillna(x.lp))
        r["revealed_ask_minus_1c"] = w((x.ask - 0.01).fillna(x.lp))
        r["max_bid_askm1"] = w(np.fmax(x.bid, x.ask - 0.01).fillna(x.lp))
        r["min_bid_askm1"] = w(np.fmin(x.bid, x.ask - 0.01).fillna(x.lp))
        r["last_print"] = w(x.lp)
        r["exact_revealed_bid"] = round(float((np.abs(x.p - x.bid.fillna(x.lp)) <= 0.0005).mean()), 4)
        res[f"{sp}_{av}"] = r
    (RES / "revealed_bid_anchor.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
