"""Per-requote-slot fill table for a slow public-data two-sided maker (same mechanics as the
project's tape_maker_backtest: every 10 s, rest BUY bids on both outcomes at floor(fair - delta),
fair = last taker print known at t0 - latency, fills only from prints in [t0, t0+10)).

For each slot we store the PIT state used by filters (computed from prints with ts <= t0 - latency)
and the fills under strict trade-through and at-touch (optimistic) models for several deltas, so any
quote-pulling filter can be evaluated as a mask over slots. Extra columns: sibling-market calm state
(H-B) when sibling tapes are available.
"""
import json, math, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from common import load, W, S, implied_p0

DELTAS = (0.005, 0.01, 0.02)
REQ = 10
SIZE = 20.0
TICK = 0.01


def jump_times(ts, p0, jump, look):
    j = np.searchsorted(ts, ts - look, side="right") - 1
    ref = np.where(j >= 0, p0[np.clip(j, 0, None)], np.nan)
    return ts[np.abs(p0 - ref) >= jump - 1e-9]


def since(ev_ts, q):
    if len(ev_ts) == 0:
        return np.full(len(q), 1e7)
    k = np.searchsorted(ev_ts, q, side="right") - 1
    return np.where(k >= 0, q - ev_ts[np.clip(k, 0, None)], 1e7)


def build(latency, sib=None):
    tk, mk, meta = load()
    pay = meta["payouts"]; active = {c: tuple(v) for c, v in meta["active"].items()}
    gst = meta["gameStartTime"]
    out = []
    for cid in meta["cids"]:
        g = tk[tk.condition_id == cid].sort_values("ts")
        if len(g) < 2:
            continue
        ts = g.ts.to_numpy().astype(np.int64); p0 = implied_p0(g)
        oc, sd, pr, sz = g.outcome.to_numpy(), g.side.to_numpy(), g.price.to_numpy(), g["size"].to_numpy()
        start, end = active[cid]
        t0s = np.arange(int(start), int(end), REQ)
        k = np.searchsorted(ts, t0s - latency, side="right") - 1
        lo = np.searchsorted(ts, t0s, side="right"); hi = np.searchsorted(ts, t0s + REQ, side="right")
        keep = (k >= 0) & (hi > lo)
        t0s, k, lo, hi = t0s[keep], k[keep], lo[keep], hi[keep]
        if len(t0s) == 0:
            continue
        cut = t0s - latency
        rec = {"condition_id": cid, "t0": t0s, "fair0": p0[k]}
        # own-market calm state (H-A)
        for J in (0.03, 0.05, 0.10):
            rec[f"sj{int(J*100)}"] = since(jump_times(ts, p0, J, 30), cut)
        lo30 = np.searchsorted(ts, cut - 30, side="right")
        rec["rng30"] = np.array([p0[min(a, b):b + 1].max() - p0[min(a, b):b + 1].min() for a, b in zip(lo30, k)])
        # sibling calm state (H-B): jumps in the top-2 sibling markets' public taker tapes
        if sib is not None:
            s = sib[sib.target == cid]
            for J in (0.03, 0.05, 0.10):
                jt = []
                for _, sg in s.groupby("sib"):
                    sg = sg[sg.outcome >= 0].sort_values("ts")
                    if len(sg) < 2:
                        continue
                    sts = sg.ts.to_numpy().astype(np.int64)
                    sp0 = np.where(sg.outcome.to_numpy() == 0, sg.price.to_numpy(), 1 - sg.price.to_numpy())
                    jt.append(jump_times(sts, sp0, J, 30))
                jt = np.sort(np.concatenate(jt)) if jt else np.array([], dtype=np.int64)
                rec[f"sib_sj{int(J*100)}"] = since(jt, cut)
        g0 = pd.Timestamp(gst[cid]).timestamp() if gst.get(cid) else np.nan
        rec["since_start"] = t0s - g0
        for d in DELTAS:
            for o in (0, 1):
                fair = rec["fair0"] if o == 0 else 1 - rec["fair0"]
                q = np.floor((fair - d) / TICK + 1e-9) * TICK
                fs, ft = np.zeros(len(t0s)), np.zeros(len(t0s))
                for i in range(len(t0s)):
                    if q[i] < TICK or q[i] > 1 - TICK:
                        continue
                    a, b = lo[i], hi[i]
                    o_, s_, p_, z_ = oc[a:b], sd[a:b], pr[a:b], sz[a:b]
                    m_s = ((o_ == o) & (s_ == "SELL") & (p_ < q[i] - 1e-9)) | ((o_ != o) & (s_ == "BUY") & (p_ > 1 - q[i] + 1e-9))
                    m_t = ((o_ == o) & (s_ == "SELL") & (p_ <= q[i] + 1e-9)) | ((o_ != o) & (s_ == "BUY") & (p_ >= 1 - q[i] - 1e-9))
                    fs[i] = min(SIZE, z_[m_s].sum()); ft[i] = min(SIZE, z_[m_t].sum())
                payo = pay[cid] if o == 0 else 1 - pay[cid]
                tag = f"d{int(d*1000)}_o{o}"
                rec[f"q_{tag}"] = q
                rec[f"strict_{tag}"] = fs
                rec[f"touch_{tag}"] = ft
                rec[f"pay_o{o}"] = np.full(len(t0s), payo)
        out.append(pd.DataFrame(rec))
    G = pd.concat(out, ignore_index=True)
    G["period"] = np.where(G.condition_id.isin(meta["test"]), "test", "fit")
    return G


if __name__ == "__main__":
    lat = int(sys.argv[1])
    sib = pd.read_pickle(S / "sibling_taker.pkl") if (S / "sibling_taker.pkl").exists() else None
    G = build(lat, sib)
    G.to_pickle(S / f"grid_lat{lat}.pkl")
    print("slots", len(G), "markets", G.condition_id.nunique(), "sibling cols", sib is not None)
