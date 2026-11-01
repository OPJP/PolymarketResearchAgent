"""Iteration 6, panel iter5 assumptions Q1 (X35), mechanics M4 (X33), assumptions Q3 (X37) on CONFIRMED orders.

Confirmed order = a cluster maker order from calldata (original size S, limit price, token) whose posting add
(+S at its level on its side of the Up book, the latest one before the server match) is in the own raw recording.
Server match ms = first 'x' record of the tx. Development live block only (parquet from code6/live6_extract.py).

Measures (descriptive; live BUILD 12-15 UTC vs live VALIDATE 15-18 UTC reported apart):
* placement: at the touch after the add, improved the touch (above the touch just before), joined an existing level
  (level size before the add > 0), deep; fresh vs re-priced (a removal of the same size on the same side <= 50 ms
  before the add);
* trigger: lag from the previous trade in the same market to the add; the previous trade's direction relative to the
  post's side (s's bid hit = taker SELL s or taker BUY complement); post price vs that trade's price;
  nulls: every other at-touch add (any size), other exact-500/100 at-touch adds, random times;
* queue: volume printed at the post's level (same token side) between the add and the match vs the size ahead (level
  size before the add);
* age: add -> match vs the residual age of exact-size (500/100) at-touch rungs at random moments (length-biased null).
    python code6/q1_confirmed.py <start_ts> <end_ts>
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache" / "re" / "directional-maker"
RES = HERE.parent / "results"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
      "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
LIVE_SPLIT = 1793458800 * 1000
rng = np.random.default_rng(6)


def main(a, b):
    ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet")
    tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet").sort_values("s", kind="stable")
    x = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet").sort_values("s", kind="stable")
    for c in ("p", "d", "z", "prev", "bb", "ba"):
        ev[c] = ev[c].astype("float64").round(4)
    acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))]).drop_duplicates(
        subset=["transactionHash", "asset", "w", "size", "price"])
    acts = acts[(acts.type == "TRADE") & (acts.timestamp >= a) & (acts.timestamp < b)]
    tok = {str(r.asset): (r.slug, r.outcome) for r in acts.itertuples()}
    cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet"))])
    cd = cd[cd.maker.str.lower().isin(CL) & (cd.role == "maker")].copy()
    cd["S"] = (np.where(cd.oside == 0, cd.taker_amount, cd.maker_amount) / 1e6).round(2)
    cd["lim"] = np.where(cd.oside == 0, cd.maker_amount / cd.taker_amount, cd.taker_amount / cd.maker_amount).round(3)
    cd["tx"] = cd.tx.str.lower()
    cd["wallet"] = cd.maker.str.lower().map(CL)
    cd = cd[cd.oside == 0].drop_duplicates(subset=["tx", "maker", "salt"])
    cltx = set(cd.tx) | set(acts.transactionHash.str.lower())
    match_s = x.groupby("h").s.min()
    # per market arrays
    X = {w: g for w, g in x.groupby("w")}
    T = {w: (g.s.to_numpy(), g.bb.to_numpy(), g.ba.to_numpy()) for w, g in tch.groupby("w")}
    E = {k: g for k, g in ev.groupby(["w", "side"])}

    def prev_trade(w, t, clean_only=False):
        g = X.get(w)
        if g is None:
            return None
        gs = g.s.to_numpy()
        j = np.searchsorted(gs, t, side="left") - 1
        if clean_only:
            while j >= 0 and g.h.iloc[j] in cltx:
                j -= 1
        if j < 0:
            return None
        return g.iloc[j]

    def touch_before(w, t, side):
        s_, b_, a_ = T[w]
        j = np.searchsorted(s_, t, side="left") - 1
        if j < 0:
            return np.nan
        return b_[j] if side == 1 else a_[j]

    def bid_hit_dir(tr, side):
        """+1 if the trade hit the bid of the post's token side (sold it), -1 if it lifted its ask, 0 unknown."""
        sold_up = (tr.ai == 0 and str(tr.d).upper().startswith("S")) or (tr.ai == 1 and str(tr.d).upper().startswith("B"))
        bought_up = (tr.ai == 0 and str(tr.d).upper().startswith("B")) or (tr.ai == 1 and str(tr.d).upper().startswith("S"))
        if side == 1:  # post is a bid on Up (BUY Up)
            return 1 if sold_up else (-1 if bought_up else 0)
        return 1 if bought_up else (-1 if sold_up else 0)  # post is an ask on Up = BUY Down

    def feats(t, w, side, p):
        out = {}
        pt = prev_trade(w, t)
        if pt is not None:
            out["prev_dt"] = t - pt.s
            out["prev_dir"] = bid_hit_dir(pt, side)
            pp_up = pt.p if pt.ai == 0 else 1 - pt.p  # trade price in Up terms
            out["prev_px_eq"] = bool(abs(pp_up - p) < 1e-6)
            out["prev_px_diff_ticks"] = round((p - pp_up) * 100 * (1 if side == 1 else -1), 1)
            out["prev_is_cluster"] = pt.h in cltx
        old = touch_before(w, t, side)
        out["old_touch"] = old
        out["improve"] = bool(old == old and ((side == 1 and p > old + 1e-9) or (side == 0 and p < old - 1e-9)))
        return out

    conf = []
    for r in cd.itertuples(index=False):
        sm = match_s.get(r.tx)
        t = tok.get(str(r.token_id))
        if sm is None or t is None:
            continue
        slug, outc = t
        if "btc-updown" not in slug:
            continue
        side = 1 if outc == "Up" else 0
        p = round(r.lim, 3) if side == 1 else round(1 - r.lim, 3)
        g = E.get((slug, side))
        if g is None:
            continue
        m = g[(np.abs(g.p - p) < 1e-6) & (np.abs(g.d - r.S) < 0.006) & (g.s <= sm) & (g.s > sm - 30000)]
        if not len(m):
            conf.append({"found": False, "wallet": r.wallet, "S": r.S, "slug": slug, "ms": sm})
            continue
        e = m.iloc[-1]
        at = bool(abs(p - (e.bb if side == 1 else e.ba)) < 1e-6)
        # re-priced: removal of the same size on the same side within 50 ms before the add (any price)
        rem = g[(np.abs(g.d + r.S) < 0.006) & (g.s <= e.s) & (g.s >= e.s - 50)]
        # queue: volume printed at this level (token side) between the add and the match, excluding the fill's tx
        xg = X.get(slug)
        vol = np.nan
        if xg is not None:
            xs = xg[(xg.s >= e.s) & (xg.s < sm) & (xg.h != r.tx)]
            pu = np.where(xs.ai == 0, xs.p, 1 - xs.p)
            vol = float(xs.z[np.abs(pu - p) < 1e-6].sum())
        conf.append({"found": True, "wallet": r.wallet, "S": r.S, "slug": slug, "side": side, "p": p, "ms": sm, "add_s": int(e.s),
                     "age_ms": int(sm - e.s), "at_touch": at, "prev_size": float(e.prev), "joined": bool(at and e.prev > 0),
                     "fresh": len(rem) == 0, "vol_at_level_before_match": vol, "h15": "live_validate" if sm >= LIVE_SPLIT else "live_build",
                     "horizon": "15m" if "15m" in slug else "5m", **feats(int(e.s), slug, side, p)})
    Cf = pd.DataFrame(conf)
    F = Cf[Cf.found == True].copy()
    for c in ("at_touch", "improve", "fresh", "joined", "prev_is_cluster", "prev_px_eq"):
        if c in F:
            F[c] = F[c].fillna(False).astype(bool)
    for c in ("side", "age_ms", "add_s"):
        F[c] = F[c].astype(int)
    # nulls: all other at-touch adds (any size) and other exact 500/100 at-touch adds
    keys = set(zip(F.add_s, F.slug, F.side, F.p))
    adds = ev[(ev.d > 0)].copy()
    adds["att"] = np.where(adds.side == 1, np.abs(adds.p - adds.bb) < 1e-6, np.abs(adds.p - adds.ba) < 1e-6)
    adds = adds[adds["att"]]
    adds = adds[[k not in keys for k in zip(adds.s, adds.w, adds.side, adds.p)]]
    samp_all = adds.sample(min(4000, len(adds)), random_state=1)
    samp_5 = adds[adds.d.isin([500.0, 100.0])]
    samp_5 = samp_5.sample(min(3000, len(samp_5)), random_state=2)

    def null_feats(D):
        rows = []
        for r in D.itertuples(index=False):
            rows.append({**feats(int(r.s), r.w, r.side, r.p), "prev_size": float(r.prev)})
        return pd.DataFrame(rows)
    N_all, N_5 = null_feats(samp_all), null_feats(samp_5)
    # random times in markets with trades
    rt = []
    ws = list(X)
    for _ in range(3000):
        w = ws[rng.integers(len(ws))]
        g = X[w]
        t = int(rng.uniform(g.s.min(), g.s.max()))
        side = int(rng.integers(2))
        pt = prev_trade(w, t)
        if pt is not None:
            rt.append({"prev_dt": t - pt.s, "prev_dir": bid_hit_dir(pt, side)})
    R = pd.DataFrame(rt)

    def summ(D):
        if not len(D):
            return None
        o = {"n": int(len(D))}
        for c, f in [("at_touch", "mean"), ("improve", "mean"), ("fresh", "mean"), ("joined", "mean"), ("prev_is_cluster", "mean")]:
            if c in D:
                o[c] = round(float(D[c].astype(float).mean()), 3)
        if "prev_dt" in D:
            dt = D.prev_dt.dropna()
            o["prev_trade_lag_ms_q"] = dt.quantile([.1, .25, .5, .75, .9]).round(0).to_dict()
            o["P_lag_le_150ms"] = round(float((dt <= 150).mean()), 3)
            o["P_lag_le_300ms"] = round(float((dt <= 300).mean()), 3)
        if "prev_dir" in D:
            pdr = D.prev_dir
            o["prev_trade_hit_post_side_bid"] = round(float((pdr == 1).mean()), 3)
            o["prev_trade_lifted_post_side_ask"] = round(float((pdr == -1).mean()), 3)
        if "prev_px_eq" in D:
            o["post_px_eq_prev_trade_px"] = round(float(D.prev_px_eq.astype(float).mean()), 3)
            o["post_px_minus_prev_trade_ticks"] = D.prev_px_diff_ticks.clip(-3, 3).value_counts(normalize=True).sort_index().round(3).to_dict()
        if "prev_size" in D:
            o["level_size_before_add_zero"] = round(float((D.prev_size <= 1e-6).mean()), 3)
        return o

    res = {"period": [a, b], "cluster_maker_orders_btc": int(len(Cf)), "confirmed": int(len(F)),
           "confirmed_share": round(len(F) / max(len(Cf), 1), 3),
           "confirmed_within_5s_share": round(float((F.age_ms <= 5000).mean()), 3) if len(F) else None,
           "confirmed_all": summ(F), "confirmed_at_touch": summ(F[F.at_touch]), "confirmed_deep": summ(F[~F.at_touch]),
           "by_half": {h: summ(g) for h, g in F.groupby("h15")}, "by_wallet": {h: summ(g) for h, g in F.groupby("wallet")},
           "by_horizon": {h: summ(g) for h, g in F.groupby("horizon")},
           "null_other_at_touch_adds_any_size": summ(N_all), "null_other_at_touch_500_100_adds": summ(N_5),
           "null_random_times": summ(R),
           "age_ms_q_confirmed": F.age_ms.quantile([.1, .25, .5, .75, .9]).round(0).to_dict() if len(F) else None}
    # queue law
    Q = F[F.at_touch & F.vol_at_level_before_match.notna()].copy()
    if len(Q):
        Q["ratio"] = Q.vol_at_level_before_match / Q.prev_size.replace(0, np.nan)
        res["queue"] = {"n": int(len(Q)), "new_level_share": round(float((Q.prev_size <= 1e-6).mean()), 3),
                        "joined_ratio_vol_over_ahead_q": Q.ratio.dropna().quantile([.1, .25, .5, .75, .9]).round(3).to_dict(),
                        "joined_share_ratio_ge_1": round(float((Q.ratio.dropna() >= 1).mean()), 3),
                        "prev_size_q": Q.prev_size.quantile([.25, .5, .75]).round(1).to_dict()}
    # length-biased age null: exact 500/100 at-touch rungs alive at random moments
    ex = ev[ev.d.abs().isin([500.0, 100.0])].sort_values("s", kind="stable")
    alive = {}
    lifetimes = []
    for r in ex.itertuples(index=False):
        k = (r.w, r.side, r.p, abs(r.d))
        if r.d > 0:
            at = (r.side == 1 and abs(r.p - r.bb) < 1e-6) or (r.side == 0 and abs(r.p - r.ba) < 1e-6)
            alive.setdefault(k, []).append((r.s, at))
        else:
            st = alive.get(k)
            if st:
                s0, at = st.pop(0)
                lifetimes.append((s0, r.s, at))
    L = pd.DataFrame(lifetimes, columns=["s0", "s1", "at"])
    if len(L):
        Lt = L[L["at"]]
        lo, hi = Lt.s0.min(), Lt.s1.max()
        ages = []
        s0, s1 = Lt.s0.to_numpy(), Lt.s1.to_numpy()
        for t in rng.uniform(lo, hi, 4000):
            m = (s0 <= t) & (s1 > t)
            ages.extend((t - s0[m]).tolist())
        ages = pd.Series(ages)
        res["age_null_at_touch_500_100_alive_ms_q"] = ages.quantile([.1, .25, .5, .75, .9]).round(0).to_dict() if len(ages) else None
        res["lifetime_at_touch_500_100_ms_q"] = (Lt.s1 - Lt.s0).quantile([.1, .25, .5, .75, .9]).round(0).to_dict()
        res["n_lifetimes_at_touch"] = int(len(Lt))
    out = json.loads(json.dumps(res, default=str))
    (RES / f"iter6_q1_confirmed_{a}_{b}.json").write_text(json.dumps(out, indent=1))
    F.to_parquet(C / "it6" / f"confirmed_{a}_{b}.parquet")
    print(json.dumps(out, indent=1)[:6000])


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
