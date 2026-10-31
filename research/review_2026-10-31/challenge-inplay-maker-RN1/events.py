"""Build the 'touch-fill event' table from the public tape (taker rows + maker rows).

Each event = one taker order (tx) that hit resting BUY interest on outcome o (a taker SELL of o,
or a taker BUY of 1-o matched by minting). For that order we record the touch level q (highest
maker BUY price on o in the tx), the size filled at q, whether the order swept below q (sweep),
and who the makers at q were (is RN1 among them).

PIT features are computed from taker prints with ts <= t - latency - 1 only (strictly earlier seconds),
plus listing-time metadata (family, gameStartTime). Payout is attached for settlement only.
"""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from common import load, W, S, implied_p0


def build(latency=1, jump=0.05, look=30):
    tk, mk, meta = load()
    pay = meta["payouts"]; fam = meta["family"]; gst = meta["gameStartTime"]
    rows = []
    mb = mk[mk.side == "BUY"]
    for cid, g in mb.groupby("condition_id"):
        t = tk[tk.condition_id == cid].sort_values("ts")
        ts = t.ts.to_numpy().astype(np.int64)
        if len(ts) < 5:
            continue
        p0 = implied_p0(t)
        # signed flow: + = pressure to SELL outcome 0 (taker SELL 0 or taker BUY 1)
        sell0 = np.where(((t.outcome == 0) & (t.side == "SELL")) | ((t.outcome == 1) & (t.side == "BUY")), 1.0, -1.0) * (t["size"] * np.where(t.outcome == 0, t.price, 1 - t.price)).to_numpy()
        csum = np.concatenate([[0.0], np.cumsum(sell0)])
        j = np.searchsorted(ts, ts - look, side="right") - 1
        ref = np.where(j >= 0, p0[np.clip(j, 0, None)], np.nan)
        jump_ts = ts[np.abs(p0 - ref) >= jump - 1e-9]
        # per (tx, outcome) touch level among maker BUY fills
        ev = g.groupby(["tx", "outcome"]).agg(ts=("ts", "first"), q=("price", "max"), qmin=("price", "min"),
                                              size_all=("size", "sum")).reset_index()
        at_q = g.merge(ev[["tx", "outcome", "q"]], on=["tx", "outcome"])
        at_q = at_q[np.abs(at_q.price - at_q.q) < 1e-9]
        sz_q = at_q.groupby(["tx", "outcome"])["size"].sum().rename("size_q")
        w_q = at_q.assign(w=at_q.wallet == W).groupby(["tx", "outcome"])["w"].any().rename("rn1_at_q")
        w_sz = at_q[at_q.wallet == W].groupby(["tx", "outcome"])["size"].sum().rename("rn1_size_q")
        w_any = g.assign(w=g.wallet == W).groupby(["tx", "outcome"])["w"].any().rename("rn1_any")
        ev = ev.join(sz_q, on=["tx", "outcome"]).join(w_q, on=["tx", "outcome"]).join(w_sz, on=["tx", "outcome"]).join(w_any, on=["tx", "outcome"])
        ev["rn1_size_q"] = ev["rn1_size_q"].fillna(0.0)
        ev["sweep"] = ev.qmin < ev.q - 1e-9
        cut = ev.ts.to_numpy().astype(np.int64) - latency - 1
        k = np.searchsorted(ts, cut, side="right") - 1
        ok = k >= 0
        lastp0 = np.where(ok, p0[np.clip(k, 0, None)], np.nan)
        kj = np.searchsorted(jump_ts, cut, side="right") - 1
        ev["since_jump"] = np.where(kj >= 0, cut - jump_ts[np.clip(kj, 0, None)], 1e7) if len(jump_ts) else 1e7
        for L in (30, 120):
            lo = np.searchsorted(ts, cut - L, side="right")
            r = np.full(len(cut), np.nan)
            for i in range(len(cut)):
                if ok[i]:
                    seg = p0[min(lo[i], k[i]):k[i] + 1]
                    r[i] = seg.max() - seg.min()
            ev[f"rng{L}"] = r
            ev[f"n{L}"] = np.where(ok, k - lo + 1, 0)
            ev[f"flow{L}"] = np.where(ok, csum[np.clip(k, 0, None) + 1] - csum[np.clip(lo, 0, None)], 0.0)
        ev["last_po"] = np.where(ev.outcome == 0, lastp0, 1 - lastp0)
        # signed flow toward selling the bought outcome
        ev["flow_against60"] = np.where(ev.outcome == 0, 1, -1) * ev["flow120"]
        ev["offset"] = ev.q - ev.last_po
        g0 = pd.Timestamp(gst[cid]).timestamp() if gst.get(cid) else np.nan
        ev["since_start"] = ev.ts - g0
        ev["condition_id"] = cid
        ev["family"] = fam[cid]
        ev["pay"] = np.where(ev.outcome == 0, pay[cid], 1 - pay[cid])
        ev["ret"] = ev.pay - ev.q
        rows.append(ev[ok])
    E = pd.concat(rows, ignore_index=True)
    E["period"] = np.where(E.condition_id.isin(meta["test"]), "test", "fit")
    E["fam2"] = E.family.map(lambda f: "tennis" if f in ("sports:atp", "sports:wta", "sports:itf") else ("esports" if f.startswith("esports") else ("us" if f in ("sports:nfl", "sports:cfb", "sports:nba", "sports:mlb", "sports:nhl", "sports:wnba") else "soccer/other")))
    return E, meta


if __name__ == "__main__":
    E, meta = build(latency=int(sys.argv[1]) if len(sys.argv) > 1 else 1)
    E.to_pickle(S / "events_lat1.pkl")
    print(len(E), "events;", E.rn1_any.sum(), "with RN1 among makers;", E.rn1_at_q.sum(), "RN1 at touch level")
    print(E.groupby("period").size())
    print(E.describe().T[["mean", "50%"]])
