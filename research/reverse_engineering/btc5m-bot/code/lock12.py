"""Iteration 12, panel iter11 assumptions P3 steps 1-2 (X111): split the live decisions into venue-LOCKED and unlocked.
Pre-registered here (01:05 UTC 11-01, before scoring): a decision (it11/large_dec, arrival a, match m = a + 150 ms) is
locked if any of the six series with a kernel7 directional excess >= 0.05 (Binance USD-M BTC / ETH, OKX BTC, Bybit ETH,
Hyperliquid BTC / ETH; btc5m_venues2 exchange stamps) shows a microprice change toward o inside that series' kernel7 peak
bin widened by 25 ms on each side ([m + peak - 25, m + peak + 75)). Placebo: the same test with m shifted by -2,000 and
-4,000 ms (mean). Locked fraction = P(locked) - P(locked | placebo). Locked and unlocked decisions are then compared on the
six-series tick sign, size, wallet, won / lost, rel, |ask - 0.5|, o's ask change and the BTC move since the window start."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import live_lab as L
C = L.C
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
K7 = json.load(open(os.path.join(R, "kernel7_1793458200.json")))["series"]
SER = [k for k, v in K7.items() if v["peak_directional_excess"] >= 0.05]
D_MS = 150
MOVE_BP = 0.1  # amended definition: net microprice move toward o over the widened kernel bin


def main():
    dec = pd.read_parquet(f"{C}/it11/large_dec.parquet")
    Mi = pd.read_parquet(f"{C}/it9/ins9b_M.parquet")
    Mi = Mi[Mi.s_ins.notna() & Mi.rcls.isin(["lost_300", "lost_1000"])]
    lost = set(zip(Mi.mstart.astype(int), Mi.w, Mi.is_up.astype(bool), (Mi.s_ins.astype(np.int64) - D_MS)))
    dec["won"] = [not ((int(s), w, bool(u), int(a)) in lost) for s, w, u, a in zip(dec.st, dec.w, dec.up, dec.a.astype(np.int64))]
    a0, a1 = dec.a.min() / 1000 - 10, dec.a.max() / 1000 + 10
    rows = {k: [] for k in SER}
    want = {(k.split("_")[0], k.split("_")[1]): k for k in SER}
    for r in L.recs("btc5m_venues2", a0 - 30, a1 + 5):
        k = want.get((r.get("v"), r.get("y")))
        if k is not None and r.get("b") and r.get("a"):
            rows[k].append((r.get("E") or r["t"], r["b"], r.get("B") or 0, r["a"], r.get("A") or 0))
    EV = {}
    for k, x in rows.items():
        x = np.array(x, float); x = x[np.argsort(x[:, 0], kind="stable")]
        mic = (x[:, 1] * x[:, 4] + x[:, 3] * x[:, 2]) / np.maximum(x[:, 2] + x[:, 4], 1e-12)
        EV[k] = (x[:, 0], mic)
    del rows
    o = np.where(dec.up.to_numpy(bool), 1.0, -1.0)
    m_ms = dec.a.to_numpy(float) + D_MS

    def locked(shift):
        out = np.zeros(len(dec), bool)
        for k in SER:  # amended 01:08 UTC (before any locked-vs-unlocked comparison was read): NET move >= MOVE_BP toward o over the bin
            E, mic = EV[k]; pk = K7[k]["peak_bin_ms"]
            lo, hi = m_ms + shift + pk - 25, m_ms + shift + pk + 75
            i0, i1 = np.searchsorted(E, lo) - 1, np.searchsorted(E, hi) - 1
            ok = (i0 >= 0) & (i1 > i0)
            mv = np.where(ok, (mic[np.maximum(i1, 0)] - mic[np.maximum(i0, 0)]) / mic[np.maximum(i0, 0)] * 1e4, 0.0) * o
            out |= ok & (mv >= MOVE_BP)
        return out
    lk = locked(0.0); pl = 0.5 * (locked(-2000.0).astype(float) + locked(-4000.0).astype(float))
    res = {"series": SER, "decisions": int(len(dec)), "P_locked": round(float(lk.mean()), 4), "P_locked_placebo": round(float(pl.mean()), 4),
           "locked_fraction_excess": round(float(lk.mean() - pl.mean()), 4)}
    by = {}
    for nm, msk in (("locked", lk), ("unlocked", ~lk)):
        x = dec[msk]
        by[nm] = {"n": int(msk.sum()), "tick_toward_o_share": round(float((x.tick > 0).mean()), 4), "no_tick_share(|tick|<0.05bp)": round(float((x.abstick < 0.05).mean()), 4),
                  "large_share": round(float(x.large.mean()), 4), "won_share": round(float(x.won.mean()), 4),
                  "wallet_share": {w: round(float((x.w == w).mean()), 3) for w in ("DS", "GF", "XM")}, "rel_median": round(float(x.rel.median()), 1),
                  "abs_ask_minus_half_median": round(float((x.ask - 0.5).abs().median()), 3), "dask_up_share": round(float((x.dask > 0).mean()), 4),
                  "since_start_toward_o_share": round(float((x.since_start > 0).mean()), 4)}
    res["by_class"] = by
    for w in ("DS", "GF", "XM"):
        mm = (dec.w == w).to_numpy()
        res.setdefault("by_wallet_locked_excess", {})[w] = round(float(lk[mm].mean() - pl[mm].mean()), 4)
    print(json.dumps(res, indent=1))
    json.dump(res, open(os.path.join(R, "lock12.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
