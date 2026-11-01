"""X153 (assumptions panel iter-10 P1), version 2 on the RAW feed: a freshness-filtered touch as the public form of V.

Version 1 (fresh_touch.py) rebuilt the book from level_events_dev, which has no snapshots, so levels resting before
the window were missing and its touch scored only 0.20 on adds (iteration 7's raw-feed touch: 0.38): not a fair base.
This version reuses the iteration-7 book machinery (code/iter7/live_price_relabel.py: tommy_cs2_near snapshots 'q'/'f'
plus price changes 'pc', server clock, the 'valid' own tracker = validated own adds (F_mkt & (in_burst | size != 100))
and whole-cent decreases of its sizes where it holds size) and adds, per level, the server time of its last NON-own
change (a snapshot that shows a new level or a size change not explained by own state also counts as non-own).
BUILD-live 10-31 14:50-18:00 UTC (development block 12-18), the wallet's dev-unit CS2 token-0 books.
Populations: (1) its filled maker orders (calldata_dev), query at sign_ms - 100 ms (as iteration 7);
(2) its validated own adds, query at the add's server time - 30 ms; token 1 through the complement asks.
Anchors: J (touch without own size), FT_D = best level with a non-own change in [t - D, t - 20 ms] (fallback J),
D in {0.25, 0.5, 1, 2, 5, 15, 60} s; D and an offset k (whole cents) fitted on the first half (time), scored on the second.
Panel signature: true iff FT beats J by >= 0.10 on fills (to >= 0.57) and top changes (to >= 0.73); false iff FT <= J +
0.03 for every D. Output: results/fresh_touch_v2.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OWN0, END = 1793458232, 1793469600
VIEW = 100.0
DS = [0.25, 0.5, 1, 2, 5, 15, 60]
KS = [-0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03]


def tickhit(p, a):
    p, a = np.asarray(p, float), np.asarray(a, float)
    t = np.where((a >= 0.04) & (a <= 0.96), 0.01, 0.001)
    return np.isfinite(a) & (np.abs(p - a) <= t + 1e-9)


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    tok = {r.cid: (str(r.tok0), str(r.tok1)) for r in dm.itertuples()}
    t0map = {v[0]: v[0] for v in tok.values()}
    t0map.update({v[1]: v[0] for v in tok.values()})
    slug_of = {str(r.tok0): r.slug for r in dm.itertuples()}
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    cd["tok"] = cd.token_id.astype(str)
    mo = cd[(cd.idx >= 0) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(t0map)].drop_duplicates("salt")
    mo = mo[(mo.sign_ms >= OWN0 * 1000) & (mo.sign_ms < END * 1000)]
    sizes = {}
    for r in mo.itertuples():
        sizes.setdefault(t0map[r.tok], set()).add(round(float(r.shares), 2))
    sizes = {a: v | {100.0} for a, v in sizes.items()}
    LA = pd.read_parquet(OUT / "linked_adds_dev.parquet")
    LA["valid"] = LA.F_mkt & (LA.in_burst | (LA["size"] != 100))
    V = LA[LA.valid]
    vset = {(r.a, r.side, round(float(r.p), 3), int(r.s)) for r in V.itertuples()}
    # queries: (time, kind, oi, price)
    q = {}
    for r in mo.itertuples():
        a = t0map[r.tok]
        q.setdefault(a, []).append((float(r.sign_ms) - VIEW, "fill", 0 if r.tok == a else 1, round(float(r.price), 3)))
    for r in V.itertuples():
        if r.a not in sizes and r.a not in q:
            continue
        oi = 0 if r.side == "BUY" else 1
        pr = float(r.p) if oi == 0 else 1 - float(r.p)
        q.setdefault(r.a, []).append((float(r.s) - 30.0, "add", oi, round(pr, 3)))
    for a in q:
        q[a].sort()
    st = {}
    qi = {a: 0 for a in q}
    rows = []

    def answer(a, upto):
        b, o, ob, oo, lb, lo_ = st[a]
        qa = q[a]
        while qi[a] < len(qa) and qa[qi[a]][0] < upto:
            t, kind, oi, price = qa[qi[a]]
            qi[a] += 1
            rec = {"a": a, "slug": slug_of.get(a), "t": t, "kind": kind, "oi": oi, "p": price}
            if oi == 0:
                lv = [(p, lb.get(p, -1e18)) for p, z in b.items() if z - ob.get(p, 0.0) > 0.5]
                J = max((p for p, _ in lv), default=np.nan)
                own_top = max((p for p, z in ob.items() if z > 0.5), default=np.nan)
            else:
                lv = [(1 - p, lo_.get(p, -1e18)) for p, z in o.items() if z - oo.get(p, 0.0) > 0.5]
                J = max((p for p, _ in lv), default=np.nan)
                own_top = max((1 - p for p, z in oo.items() if z > 0.5), default=np.nan)
            rec["J"] = J
            rec["own_top"] = own_top
            for D in DS:
                lo, hi = t - D * 1000.0, t - 20.0
                c = [p for p, ts in lv if lo <= ts <= hi]
                rec[f"FT{D}"] = max(c) if c else np.nan
            rows.append(rec)

    h = int(OWN0 // 3600 * 3600)
    while h < END:
        try:
            for r in live.iter_live("tommy_cs2_near", max(h, OWN0), min(h + 3600, END)):
                a = r.get("a")
                if a not in q or "s" not in r:
                    continue
                s = float(r["s"])
                if a in st:
                    answer(a, s)
                k = r.get("k")
                if k == "x":
                    continue
                own_sz = sizes.get(a, {100.0})
                if k in ("q", "f"):
                    b = {float(p): float(z) for p, z in (r.get("b") or [])}
                    o = {float(p): float(z) for p, z in (r.get("o") or [])}
                    if a in st:
                        b0, o0, ob0, oo0, lb, lo_ = st[a]
                        ob = {p: min(v, b.get(p, 0.0)) for p, v in ob0.items()}
                        oo = {p: min(v, o.get(p, 0.0)) for p, v in oo0.items()}
                        for p, z in b.items():
                            if abs(z - b0.get(p, 0.0)) > 0.5:
                                lb[p] = s
                        for p, z in o.items():
                            if abs(z - o0.get(p, 0.0)) > 0.5:
                                lo_[p] = s
                    else:
                        ob, oo, lb, lo_ = {}, {}, {}, {}
                    st[a] = (b, o, ob, oo, lb, lo_)
                elif k == "pc" and a in st:
                    b, o, ob, oo, lb, lo_ = st[a]
                    for sd, p, z in r.get("c") or []:
                        p, z = float(p), float(z)
                        book = b if sd == "BUY" else o
                        ow = ob if sd == "BUY" else oo
                        last = lb if sd == "BUY" else lo_
                        d = z - book.get(p, 0.0)
                        whole = abs(p * 100 - round(p * 100)) < 1e-6
                        fz = whole and round(abs(d), 2) in own_sz
                        own_change = False
                        if d > 0 and (a, sd, round(p, 3), int(s)) in vset:
                            ow[p] = ow.get(p, 0.0) + d
                            own_change = True
                        elif d < 0 and fz and ow.get(p, 0.0) > 0.5:
                            ow[p] = max(0.0, ow.get(p, 0.0) + d)
                            own_change = True
                        if not own_change and abs(d) > 1e-9:
                            last[p] = s
                        if z == 0:
                            book.pop(p, None)
                        else:
                            book[p] = z
                        if p in ow:
                            ow[p] = min(ow[p], book.get(p, 0.0))
        except Exception as e:  # noqa: BLE001
            print("feed", type(e).__name__, flush=True)
        h += 3600
    for a in q:
        if a in st:
            answer(a, 1e18)
    R = pd.DataFrame(rows)
    R = R[R.p.between(0.04, 0.96) & R.J.notna()]
    R["new_top"] = R.own_top.isna() | (R.p > R.own_top + 1e-9)
    out = {"n": {k: int(v) for k, v in R.kind.value_counts().items()}}
    for kind in ("fill", "add"):
        S = R[R.kind == kind]
        tm = S.t.median()
        fit, sco = S[S.t < tm], S[S.t >= tm]
        o = {"n": int(len(S)), "touch_all": round(float(tickhit(S.p, S.J).mean()), 3), "by_D_all": {}}
        for D in DS:
            f = S[f"FT{D}"].to_numpy(float)
            cov = np.isfinite(f)
            o["by_D_all"][str(D)] = {"within_tick": round(float(tickhit(S.p, np.where(cov, f, S.J)).mean()), 3),
                                     "coverage": round(float(cov.mean()), 3),
                                     "on_covered_FT": round(float(tickhit(S.p[cov], f[cov]).mean()), 3) if cov.any() else None,
                                     "on_covered_touch": round(float(tickhit(S.p[cov], S.J[cov]).mean()), 3) if cov.any() else None}
        best = max(((float(tickhit(fit.p, np.where(np.isfinite(fit[f"FT{D}"]), fit[f"FT{D}"], fit.J) + k).mean()), D, k)
                    for D in DS for k in KS))
        bj = max(((float(tickhit(fit.p, fit.J + k).mean()), k) for k in KS))
        D, k = best[1], best[2]
        f2 = sco[f"FT{D}"].to_numpy(float)
        hitF = tickhit(sco.p, np.where(np.isfinite(f2), f2, sco.J) + k)
        hitJ = tickhit(sco.p, sco.J + bj[1])
        nt = sco.new_top.to_numpy()
        ev = sco.slug.fillna("?").to_numpy()
        ue = np.unique(ev)
        rng = np.random.default_rng(5)
        diffs = []
        for _ in range(500):
            pick = rng.choice(ue, len(ue))
            m = np.concatenate([np.where(ev == e)[0] for e in pick])
            diffs.append(hitF[m].mean() - hitJ[m].mean())
        o["fitted"] = {"D": D, "k": k, "fit_FT": round(best[0], 3), "fit_touch": round(bj[0], 3), "touch_k": bj[1],
                       "second_half": {"n": int(len(sco)), "FT": round(float(hitF.mean()), 3), "touch": round(float(hitJ.mean()), 3),
                                       "gain_ci95_event_boot": [round(float(np.percentile(diffs, 2.5)), 3), round(float(np.percentile(diffs, 97.5)), 3)],
                                       "new_top_n": int(nt.sum()),
                                       "new_top_FT": round(float(hitF[nt].mean()), 3) if nt.any() else None,
                                       "new_top_touch": round(float(hitJ[nt].mean()), 3) if nt.any() else None}}
        out[kind] = o
    (RES / "fresh_touch_v2.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
