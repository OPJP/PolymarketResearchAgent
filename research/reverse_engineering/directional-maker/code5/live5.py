"""Live lab, iteration 5 (development block 2026-10-31 12:00-18:00 UTC): the cluster's quotes in the raw book.

1. Raw CLOB events (dm_clob_raw) -> per (market, book side, price) size deltas (+S add, -S cancel); book snapshots
   (sent after every trade) reset the levels. Up-book representation: a BUY Down at p is an ask at 1 - p.
2. Fingerprint: for every cluster maker order filled in the block (data-api activity tx hash -> calldata original size
   S, limit price, token; server match time from the raw 'x' records), the latest +S add at its level before the match.
3. All exact-500 / exact-100 events: lifetimes (add -> removal at the same level), replace pattern, both-sides
   synchrony, placement vs the touch, and lead-lag against every reference feed on server clocks (10-ms bins).
    python live5.py <start_ts> <end_ts>
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from rawread import iter_dm  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
      "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}


def load_clob(a, b):
    lv, ev, trades, books = {}, [], [], []
    for r in iter_dm("dm_clob_raw", a, b):
        k, w = r["k"], r.get("w")
        if k == "bk":
            L = {(1, p): z for p, z in r["b"]}
            L.update({(0, p): z for p, z in r["o"]})
            lv[w] = L
            bb = max((p for p, z in r["b"]), default=np.nan)
            ba = min((p for p, z in r["o"]), default=np.nan)
            books.append((r["s"], w, bb, ba))
        elif k == "pc":
            L = lv.setdefault(w, {})
            for side, p, z, bb, ba, nc in r["c"]:
                if side > 1:
                    continue
                d = z - L.get((side, p), 0.0)
                L[(side, p)] = z
                ev.append((r["s"], r["t"], w, side, p, round(d, 4), z, bb, ba))
        elif k == "x":
            trades.append((r["s"], w, r["ai"], r["p"], r["z"], r["d"], (r.get("h") or "").lower()))
    ev = pd.DataFrame(ev, columns=["s", "t", "w", "side", "p", "d", "z", "bb", "ba"])
    trades = pd.DataFrame(trades, columns=["s", "w", "ai", "p", "z", "d", "h"])
    books = pd.DataFrame(books, columns=["s", "w", "bb", "ba"])
    return ev, trades, books


def load_ref(a, b):
    out = {}
    fut = [(r["r"][2], r["r"][3], r["r"][5]) for r in iter_dm("dm_bnf", a, b) if r["r"][0] == "b"]  # T, bid, ask
    out["bn_fut_bt"] = pd.DataFrame(fut, columns=["s", "bid", "ask"])
    fa = [(r["r"][1], r["r"][3]) for r in iter_dm("dm_bnfa", a, b) if r["r"][0] == "a"]
    out["bn_fut_tr"] = pd.DataFrame(fa, columns=["s", "px"])
    sa = [(r["r"][1], r["r"][3]) for r in iter_dm("dm_bns", a, b) if r["r"][0] == "a"]
    out["bn_spot_tr"] = pd.DataFrame(sa, columns=["s", "px"])
    cb = [(r["r"][0], r["r"][1]) for r in iter_dm("dm_cb", a, b)]
    out["coinbase"] = pd.DataFrame(cb, columns=["s", "px"])
    ok = [(r["r"][1], r["r"][2]) for r in iter_dm("dm_okx", a, b) if r["r"][0] == "t"]
    out["okx_swap"] = pd.DataFrame(ok, columns=["s", "px"])
    by = [(r["r"][1], r["r"][2]) for r in iter_dm("dm_byb", a, b) if r["r"][0] == "t"]
    out["bybit_perp"] = pd.DataFrame(by, columns=["s", "px"])
    hl = [(r["r"][1], r["r"][2]) for r in iter_dm("dm_hl", a, b) if r["r"][0] == "t"]
    out["hyperliquid"] = pd.DataFrame(hl, columns=["s", "px"])
    for k, v in out.items():
        if "bid" in v:
            v["px"] = (v.bid + v.ask) / 2
        out[k] = v.sort_values("s").reset_index(drop=True)
    return out


def cluster_orders(a, b):
    acts = [pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))]
    act = pd.concat(acts).drop_duplicates(subset=["transactionHash", "asset", "w", "size", "price"])
    act = act[(act.type == "TRADE") & (act.timestamp >= a) & (act.timestamp < b)]
    cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet"))])
    cd = cd[cd.maker.str.lower().isin(CL)].copy()
    cd["S"] = np.where(cd.oside == 0, cd.taker_amount, cd.maker_amount) / 1e6
    cd["lim"] = np.where(cd.oside == 0, cd.maker_amount / cd.taker_amount, cd.taker_amount / cd.maker_amount).round(3)
    cd["tx"] = cd.tx.str.lower()
    return act, cd


def lead_lag(evt_s, ref, lags, thr):
    """P(event in a 10-ms bin | reference moved by >= thr USD in the bin L ms earlier) / base rate."""
    if len(ref) < 10 or len(evt_s) < 10:
        return None
    t0 = min(evt_s.min(), ref.s.min())
    rb = ((ref.s.to_numpy() - t0) // 10).astype(np.int64)
    px = ref.px.to_numpy()
    mv = np.zeros(rb.max() + 1)
    d = np.abs(np.diff(px, prepend=px[0]))
    np.maximum.at(mv, rb, d)
    eb = ((evt_s - t0) // 10).astype(np.int64)
    n = max(rb.max(), eb.max()) + 1
    ev = np.zeros(n)
    np.add.at(ev, eb[eb >= 0], 1)
    mvf = np.zeros(n)
    mvf[: len(mv)] = mv
    base = ev.mean()
    out = {}
    for L in lags:
        k = L // 10
        if k >= 0:
            m = np.r_[np.zeros(k), mvf[: n - k]] >= thr
        else:
            m = np.r_[mvf[-k:], np.zeros(-k)] >= thr
        out[L] = round(float(ev[m].mean() / base), 3) if m.sum() > 20 else None
    return out


def main(a, b):
    ev, trades, books = load_clob(a, b)
    res = {"period": [a, b], "pc_events": int(len(ev)), "trades": int(len(trades)), "book_msgs": int(len(books))}
    hist = ev.d.round(2).value_counts()
    res["delta_counts"] = {str(s): [int(hist.get(float(s), 0)), int(hist.get(float(-s), 0)), int(hist.get(float(s - 1), 0)), int(hist.get(float(s + 1), 0))]
                           for s in (5, 10, 12, 50, 62, 100, 125, 250, 500, 1000)}
    # --- 2. fingerprint the cluster's filled orders
    act, cd = cluster_orders(a, b)
    mk = cd[cd.role == "maker"]
    tx_s = trades.groupby("h").s.min()
    hits = []
    evg = {k: g for k, g in ev.groupby(["w", "side", "p"])}
    slug_of_tok = {}
    for r in act.itertuples(index=False):
        slug_of_tok[str(r.asset)] = (r.slug, r.outcome)
    for r in mk.itertuples(index=False):
        s_match = tx_s.get(r.tx)
        tok = str(r.token_id)
        if s_match is None or tok not in slug_of_tok:
            continue
        slug, outc = slug_of_tok[tok]
        if outc == "Up":
            key = (slug, 1, round(r.lim, 2))
        else:
            key = (slug, 0, round(1 - r.lim, 2))
        g = evg.get(key)
        found = None
        if g is not None:
            gg = g[(g.s <= s_match) & (np.abs(g.d - r.S) < 0.01)]
            if len(gg):
                found = gg.iloc[-1]
        hits.append({"S": r.S, "lim": r.lim, "found": found is not None, "age_ms": float(s_match - found.s) if found is not None else np.nan,
                     "at_touch": bool(found is not None and ((key[1] == 1 and abs(found.bb - key[2]) < 1e-6) or (key[1] == 0 and abs(found.ba - key[2]) < 1e-6))),
                     "slug5": slug.startswith("btc-updown-5m")})
    h = pd.DataFrame(hits)
    if len(h):
        hf = h[h.found]
        res["fingerprint"] = {"cluster_maker_orders_with_match_time": int(len(h)), "found_add_of_exact_size": float(h.found.mean()),
                              "by_size": {str(k): float(v) for k, v in h.groupby("S").found.mean().items()},
                              "age_ms_quantiles": hf.age_ms.quantile([.1, .25, .5, .75, .9]).round(0).to_dict() if len(hf) else None,
                              "add_was_at_touch": float(hf.at_touch.mean()) if len(hf) else None}
    # --- 3. all exact-500 / exact-100 events
    for S in (500.0, 100.0):
        e = ev[np.abs(np.abs(ev.d) - S) < 0.01].sort_values("s", kind="stable")
        adds, rems = e[e.d > 0], e[e.d < 0]
        # lifetime: FIFO pairing per level
        life = []
        for key, g in e.groupby(["w", "side", "p"]):
            q = []
            for r in g.itertuples(index=False):
                if r.d > 0:
                    q.append(r.s)
                elif q:
                    life.append(r.s - q.pop(0))
        life = np.array(life)
        # placement: is the add at the touch after the change (bid side: price == best bid; ask side: price == best ask)?
        at_touch = np.where(adds.side == 1, np.abs(adds.p - adds.bb) < 1e-6, np.abs(adds.p - adds.ba) < 1e-6)
        # replace pattern: a removal followed within 100 ms by an add of the same size on the same side of the same market
        rep = 0
        ad = adds.groupby(["w", "side"]).s.apply(np.array).to_dict()
        for r in rems.itertuples(index=False):
            arr = ad.get((r.w, r.side))
            if arr is not None:
                i = np.searchsorted(arr, r.s)
                if i < len(arr) and arr[i] - r.s <= 100:
                    rep += 1
        # inter-event times of adds per (market, side)
        iet = np.concatenate([np.diff(np.sort(v)) for v in ad.values() if len(v) > 1]) if ad else np.array([])
        res[f"size_{int(S)}"] = {"adds": int(len(adds)), "removals": int(len(rems)),
                                 "adds_per_s": round(len(adds) / max((b - a), 1), 3),
                                 "lifetime_ms_quantiles": {str(k): float(v) for k, v in pd.Series(life).quantile([.1, .25, .5, .75, .9]).round(0).items()} if len(life) else None,
                                 "add_at_touch": float(at_touch.mean()) if len(adds) else None,
                                 "removal_then_add_within_100ms": float(rep / max(len(rems), 1)),
                                 "add_interval_ms_quantiles": {str(k): float(v) for k, v in pd.Series(iet).quantile([.1, .25, .5, .75, .9]).round(0).items()} if len(iet) else None}
    # lead-lag of the 500 adds+removals vs each reference feed
    refs = load_ref(a, b)
    e500 = ev[np.abs(np.abs(ev.d) - 500) < 0.01].s.to_numpy().astype(np.int64)
    eall = ev[(np.abs(ev.d) >= 5)].s.to_numpy().astype(np.int64)
    lags = [-500, -200, -100, -50, 0, 20, 50, 100, 150, 200, 300, 500, 750, 1000, 1500, 2000, 3000]
    res["lead_lag_500"] = {k: lead_lag(e500, v, lags, 2.0) for k, v in refs.items()}
    res["lead_lag_all_events"] = {k: lead_lag(eall, v, lags, 2.0) for k, v in refs.items()}
    res["ref_rows"] = {k: int(len(v)) for k, v in refs.items()}
    out = HERE.parent / "results" / f"iter5_live_{a}_{b}.json"
    out.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
