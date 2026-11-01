"""Iteration 4, X49 (assumptions iter3 P3) and X46 (mechanics iter3 P4) on the own recorder (tommy_cs2_near, server
clock s, 10-31 14:50-18:00 UTC, development block), the wallet's dev-unit CS2 markets.

Level events per (token-0 book, side, price): decreases and increases of the resting size, from snapshots (f) and
price changes (pc). A decrease is CONSUMPTION if a trade print (x, either token, mirrored) at that price lies within
+-150 ms, else a CANCEL.
Own-level attribution (size fingerprint, no calldata needed for unfilled orders):
  * a PULL = >= 2 cancels on one book side within 5 ms that all have the same size (its equal-size ladder: 100, or an
    inventory-scaled size such as 54 / 58 / 68), or any single cancel of exactly 100 shares;
  * an OWN ADD = an increase whose size equals the pull size (or 100) at a whole-cent price.
X49: for every wallet taker order (calldata_dev, idx -1, BUY team X, signing t), on the consumed side (asks of X):
  the first own-pull cancel after t, every non-own cancel in [t - 50, t + 300] ms, (i) the share of takes with a
  non-own cancel BEFORE its first own cancel, (ii) the lag of the first non-own cancel after its first own cancel.
X46: every pull in these books; strict FAK-return signature = no own add on that side in [60, 1000) ms after the
  pull and >= 1 own add in [1000, 1150) ms. Pulls are split by whether an on-chain wallet take on the same team lies
  in [-30, +5] ms; directionality = the pulled-asks team's mid move at +10 s (up >= 1c / down >= 1c); control = the
  same detector at random times (pull-free check) and the signature rate after random times.
Output: results/pull_attrib.json
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OWN_SIZES = (100.0, 68.0, 58.0, 54.0)  # its ladder sizes (100 and the inventory-scaled pulls seen after its takes)
OWN0, END = 1793458232, 1793469600  # own recorder v2 start .. end of the 12-18 development block


def read_feed(feed, start, end, keep):
    out = []
    h = int(start // 3600 * 3600)
    while h < end:
        try:
            for r in live.iter_live(feed, max(h, start), min(h + 3600, end)):
                if str(r.get("a")) in keep:
                    out.append(r)
        except Exception as e:  # noqa: BLE001
            print(feed, "stopped", type(e).__name__, flush=True)
        h += 3600
    return out


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    is_t1 = {str(r.tok1) for r in dm.itertuples()}
    recs = read_feed("tommy_cs2_near", OWN0, END, set(t0map))
    recs.sort(key=lambda r: r.get("s", 0))
    # trades per token-0 book, as token-0 prices
    trades = defaultdict(list)
    for r in recs:
        if r.get("k") == "x":
            a = str(r["a"])
            p = float(r["p"]) if a not in is_t1 else 1 - float(r["p"])
            trades[t0map[a]].append((int(r["s"]), round(p, 3)))
    for k in trades:
        trades[k].sort()
    # level events
    ev = defaultdict(list)  # tok0 -> list of (s, side, price, delta, new)
    mids = defaultdict(list)
    book = {}
    for r in recs:
        a = str(r.get("a"))
        if r.get("k") == "f" and a in t0map and a == t0map[a]:
            bd = {float(p): float(z) for p, z in r.get("b") or []}
            od = {float(p): float(z) for p, z in r.get("o") or []}
            book[a] = (bd, od)
            if bd and od:
                mids[a].append((int(r["s"]), (max(bd) + min(od)) / 2))
        elif r.get("k") == "pc" and a in book:
            bd, od = book[a]
            for side, p, z in r["c"]:
                p, z = float(p), float(z)
                bk = bd if side == "BUY" else od
                old = bk.get(p, 0.0)
                if abs(z - old) > 1e-9:
                    ev[a].append((int(r["s"]), side, p, z - old, z))
                if z == 0:
                    bk.pop(p, None)
                else:
                    bk[p] = z
            if bd and od:
                mids[a].append((int(r["s"]), (max(bd) + min(od)) / 2))
    # classify decreases
    rows = []
    for a, L in ev.items():
        tr = trades.get(a, [])
        ts_tr = np.array([x[0] for x in tr], float)
        px_tr = np.array([x[1] for x in tr], float)
        for s, side, p, d, z in L:
            if d >= 0:
                rows.append((a, s, side, p, d, z, "add"))
                continue
            j0, j1 = np.searchsorted(ts_tr, s - 150), np.searchsorted(ts_tr, s + 150)
            cons = bool(np.any(np.abs(px_tr[j0:j1] - p) < 0.0015)) if j1 > j0 else False
            rows.append((a, s, side, p, d, z, "cons" if cons else "cancel"))
    E = pd.DataFrame(rows, columns=["a", "s", "side", "p", "d", "z", "kind"]).sort_values(["a", "side", "s"])
    E["size"] = E.d.abs().round(2)
    E["whole"] = (np.abs(E.p * 100 - np.round(E.p * 100)) < 1e-6)
    E.to_parquet(OUT / "level_events_dev.parquet", index=False)  # intermediate for follow-ups (development block only)
    # pulls: >= 2 equal-size cancels on one side within 5 ms, or a single 100-share cancel
    C = E[E.kind == "cancel"].copy()
    pulls = []
    for (a, side), g in C.groupby(["a", "side"]):
        s = g.s.to_numpy()
        z = g["size"].to_numpy()
        i = 0
        while i < len(g):
            j = i
            while j + 1 < len(g) and s[j + 1] - s[i] <= 5:
                j += 1
            grp = list(range(i, j + 1))
            sizes = pd.Series(z[grp]).value_counts()
            top_size, top_n = float(sizes.index[0]), int(sizes.iloc[0])
            if top_n >= 2 or abs(top_size - 100) < 1e-6:
                pulls.append({"a": a, "side": side, "s": int(s[i]), "size": top_size, "levels": top_n, "n_cancels": len(grp)})
            i = j + 1
    P = pd.DataFrame(pulls)
    # wallet takes
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    tk = cd[(cd.idx == -1) & (cd.maker == WALLET) & (cd.side == 0)].drop_duplicates("tx").copy()
    tk["tok"] = tk.token_id.astype(str)
    tk = tk[tk.tok.isin(t0map) & (tk.sign_ms >= OWN0 * 1000) & (tk.sign_ms < END * 1000)]
    # consumed side in the token-0 book: buying token 0 consumes its asks (SELL side); buying token 1 consumes token-0 bids
    tk["a"] = tk.tok.map(t0map)
    tk["cside"] = np.where(tk.tok.isin(is_t1), "BUY", "SELL")
    res = {"window_utc": ["14:50", "18:00"], "markets": int(len(dm)), "wallet_takes": int(len(tk)), "pulls_detected": int(len(P))}
    # remainders of the wallet's partly filled maker orders (original size - all its fills), in token-0 book terms
    wm = cd[(cd.idx >= 0) & (cd.maker == WALLET) & (cd.side == 0)].copy()
    wm["tok"] = wm.token_id.astype(str)
    wm = wm[wm.tok.isin(t0map)]
    fsum = wm.groupby(["tok", "sign_ms", "price", "shares"]).fill.sum().reset_index()
    fsum["rem"] = (fsum.shares - fsum.fill).round(2)
    fsum = fsum[fsum.rem > 0.009]
    rem = defaultdict(list)  # (tok0, side, price0) -> [(sign_ms, remainder)]
    for r in fsum.itertuples():
        a0 = t0map[r.tok]
        if r.tok in is_t1:
            rem[(a0, "SELL", round(1 - r.price, 3))].append((r.sign_ms, r.rem))
        else:
            rem[(a0, "BUY", round(r.price, 3))].append((r.sign_ms, r.rem))
    # X49
    x49 = []
    between = []
    for r in tk.itertuples():
        g = E[(E.a == r.a) & (E.side == r.cside) & (E.s >= r.sign_ms - 50) & (E.s <= r.sign_ms + 300) & (E.kind == "cancel")]
        pp = P[(P.a == r.a) & (P.side == r.cside) & (P.s >= r.sign_ms) & (P.s <= r.sign_ms + 60)] if len(P) else P
        own_t = float(pp.s.min()) if len(pp) else np.nan
        own_size = set(pp["size"]) | {100.0} if len(pp) else {100.0}
        # own cancels: in a pull cluster (within 5 ms of a pull start) with the pull's size
        own_mask = np.zeros(len(g), bool)
        for ps, sz in zip(pp.s, pp["size"]):
            own_mask |= (np.abs(g.s.to_numpy() - ps) <= 5) & (np.abs(g["size"].to_numpy() - sz) < 1e-6)
        own_mask |= np.abs(g["size"].to_numpy() - 100) < 1e-6
        rem_mask = np.array([any(abs(sz - z) < 0.011 and sg < ts for sg, z in rem.get((r.a, r.cside, round(pp_, 3)), []))
                             for ts, pp_, sz in zip(g.s.to_numpy(), g.p.to_numpy(), g["size"].to_numpy())], bool) if len(g) else np.zeros(0, bool)
        own_mask |= rem_mask
        oth = g[~own_mask]
        if len(pp):
            for _, c in oth[(oth.s >= r.sign_ms) & (oth.s < own_t)].iterrows():
                between.append({"a": r.a, "side": r.cside, "p": float(c.p), "size": float(c["size"]), "rel_ms": float(c.s - r.sign_ms), "take_tx": r.tx})
        first_oth = float(oth.s.min()) if len(oth) else np.nan
        x49.append({"own_pull": bool(len(pp)), "own_t_rel": own_t - r.sign_ms if len(pp) else np.nan,
                    "first_other_rel": first_oth - r.sign_ms if len(oth) else np.nan,
                    "other_before_own": bool(len(oth) and len(pp) and first_oth < own_t),
                    "other_before_sign": bool(len(oth) and first_oth < r.sign_ms),
                    "other_between_sign_and_pull": bool(len(oth) and len(pp) and (oth.s.to_numpy() >= r.sign_ms).any() and (oth.s[oth.s >= r.sign_ms].min() < own_t)),
                    "rem_attributed": int(rem_mask.sum()),
                    "other_lag_after_own": (first_oth - own_t) if (len(oth) and len(pp)) else np.nan,
                    "pull_size": float(pp["size"].iloc[0]) if len(pp) else np.nan, "pull_levels": int(pp.levels.iloc[0]) if len(pp) else 0})
    X = pd.DataFrame(x49)
    q = lambda v, k: round(float(np.nanpercentile(v, k)), 1) if np.isfinite(v).any() else None  # noqa: E731
    res["x49"] = {"takes": int(len(X)), "with_own_pull_0_60ms": round(float(X.own_pull.mean()), 3) if len(X) else None,
                  "own_pull_offset_ms_p10_p50_p90": [q(X.own_t_rel, k) for k in (10, 50, 90)] if len(X) else None,
                  "pull_sizes": X.pull_size.value_counts().head(8).to_dict() if len(X) else None,
                  "share_other_cancel_before_own_pull": round(float(X.other_before_own[X.own_pull].mean()), 3) if X.own_pull.any() else None,
                  "share_other_cancel_in_50ms_before_sign": round(float(X.other_before_sign.mean()), 3) if len(X) else None,
                  "other_first_cancel_lag_after_own_ms_p10_p25_p50_p75": [q(X.other_lag_after_own, k) for k in (10, 25, 50, 75)] if len(X) else None,
                  "other_first_cancel_after_sign_ms_p10_p25_p50": [q(X.first_other_rel, k) for k in (10, 25, 50)] if len(X) else None,
                  "share_other_cancel_between_sign_and_own_pull": round(float(X.other_between_sign_and_pull[X.own_pull].mean()), 3) if X.own_pull.any() else None,
                  "cancels_attributed_as_remainders": int(X.rem_attributed.sum())}
    # base rate: a non-100, non-cluster cancel on a random side within a random 14-ms window
    Cn = C[np.abs(C["size"] - 100) > 1e-6]
    rng0 = np.random.default_rng(1)
    hits = 0
    keys = list(Cn.groupby(["a", "side"]).groups.keys())
    span = (C.s.min(), C.s.max()) if len(C) else (0, 0)
    for _ in range(4000):
        a_, sd_ = keys[rng0.integers(len(keys))]
        t_ = rng0.uniform(*span)
        ss = Cn.s[(Cn.a == a_) & (Cn.side == sd_)].to_numpy()
        hits += bool(((ss >= t_) & (ss < t_ + 14)).any())
    res["x49"]["base_rate_other_cancel_in_random_14ms"] = round(hits / 4000, 4)
    res["x49"]["between_sign_and_pull_cancels"] = between
    # X46: signature of every pull
    adds = E[(E.kind == "add") & E.whole]
    take_t = defaultdict(list)
    for r in tk.itertuples():
        take_t[(r.a, r.cside)].append(r.sign_ms)
    rng = np.random.default_rng(5)
    sig_rows = []

    def signature(a, side, s, sz):
        g = adds[(adds.a == a) & (adds.side == side) & (adds.s > s) & (adds.s <= s + 1150)]
        own = g[(np.abs(g["size"] - sz) < 1e-6) | (np.abs(g["size"] - 100) < 1e-6)]
        rel = own.s - s
        return bool(((rel >= 60) & (rel < 1000)).sum() == 0 and ((rel >= 1000) & (rel < 1150)).sum() >= 1)

    def mid_move(a, side, s):
        m = mids.get(a)
        if not m:
            return np.nan
        ts = np.array([x[0] for x in m], float)
        v = np.array([x[1] for x in m], float)
        k0 = np.searchsorted(ts, s, side="right") - 1
        k1 = np.searchsorted(ts, s + 10000, side="right") - 1
        if k0 < 0 or k1 < 0:
            return np.nan
        mv = (v[k1] - v[k0]) * 100
        return mv if side == "SELL" else -mv  # pulled asks of token 0 -> token-0 team gained

    for r in (P.itertuples() if len(P) else []):
        if r.levels < 2 or not any(abs(r.size - z) < 1e-6 for z in OWN_SIZES):
            continue
        tt = np.array(take_t.get((r.a, r.side), []), float)
        has_take = bool(len(tt) and np.any((r.s - tt >= -5) & (r.s - tt <= 30)))
        sig_rows.append({"has_take": has_take, "sig": signature(r.a, r.side, r.s, r.size), "mv": mid_move(r.a, r.side, r.s)})
    S = pd.DataFrame(sig_rows)
    ctl = []
    if len(E):
        for _ in range(600):
            e = E.iloc[rng.integers(len(E))]  # random anchor
            s = int(e.s) + int(rng.integers(-5000, 5000))
            ctl.append({"sig": signature(e.a, e.side, s, 100.0), "mv": mid_move(e.a, e.side, s)})
    Ct = pd.DataFrame(ctl)

    def summ(df):
        if len(df) == 0:
            return None
        mv = df.mv.dropna()
        return {"n": int(len(df)), "strict_signature": round(float(df.sig.mean()), 3),
                "mid_up_ge1c_10s": round(float((mv >= 1).mean()), 3) if len(mv) else None,
                "mid_down_ge1c_10s": round(float((mv <= -1).mean()), 3) if len(mv) else None}
    res["x46"] = {"multi_level_pulls_with_take": summ(S[S["has_take"]]) if len(S) else None,
                  "multi_level_pulls_without_take": summ(S[~S["has_take"]]) if len(S) else None,
                  "pulls_without_take_with_signature": summ(S[(~S["has_take"]) & S["sig"]]) if len(S) else None,
                  "pulls_without_take_no_signature": summ(S[(~S["has_take"]) & ~S["sig"]]) if len(S) else None,
                  "random_times": summ(Ct)}
    json.dump(res, open(RES / "pull_attrib.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
