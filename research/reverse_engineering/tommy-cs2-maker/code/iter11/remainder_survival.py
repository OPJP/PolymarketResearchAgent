"""X149 step 2 (mechanics panel iter-10 P1): survival of the stale remainder after the wallet's take, on the recorded book
(BUILD-live 10-31 14:50-18:00 UTC, tommy_cs2_near raw feed with snapshots, server clock; book machinery of
fresh_touch_v2.py with the validated own label).

For each of its in-play FAK BUYs on the dev-unit CS2 books (calldata_dev, taker rows of the wallet; limit price, its
filled shares F = the maker fills of its tx) the consumed side is read at t = sign + 1040 ms + delta, delta in
{-300, -100, -50, 0, 20, 40, 60, 80, 100, 150, 200, 300, 500, 1000} ms (sign + 1040 ms = its median match time): the
depth available to a BUY at <= its limit, own levels removed (token 0: asks <= limit; token 1: token-0 bids >= 1 - limit).
Refill share at delta = min(F, D(delta) + F * [delta >= 0]) / F: what a copy of its take delayed by delta would still get
if the wallet had not taken (its own fill added back; depth that others add at <= the limit counts too).
Reported: medians and means over takes, the share of takes keeping >= 50% of F, and D(delta) / D(-50 ms).
Panel signature: true iff the curve keeps >= 50% of its refill at delta = 300 ms; false iff it loses > 80% by +100 ms.
Output: results/remainder_survival.json
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
DELTAS = [-1040, -900, -700, -500, -300, -200, -100, -50, 0, 20, 50, 100, 200, 300, 500, 1000]


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    tok = {r.cid: (str(r.tok0), str(r.tok1)) for r in dm.itertuples()}
    t0map = {v[0]: v[0] for v in tok.values()}
    t0map.update({v[1]: v[0] for v in tok.values()})
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    cd["tok"] = cd.token_id.astype(str)
    mo = cd[(cd.idx >= 0) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(t0map)].drop_duplicates("salt")
    mo = mo[(mo.sign_ms >= OWN0 * 1000) & (mo.sign_ms < END * 1000)]
    sizes = {}
    for r in mo.itertuples():
        sizes.setdefault(t0map[r.tok], set()).add(round(float(r.shares), 2))
    sizes = {a: v | {100.0} for a, v in sizes.items()}
    tk = cd[(cd.idx == -1) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(t0map) & (cd.side == 0)].drop_duplicates("tx")
    tk = tk[(tk.sign_ms >= OWN0 * 1000) & (tk.sign_ms < END * 1000 - 5000)]
    fills = cd[cd.idx >= 0].groupby("tx").fill.sum()
    LA = pd.read_parquet(OUT / "linked_adds_dev.parquet")
    LA["valid"] = LA.F_mkt & (LA.in_burst | (LA["size"] != 100))
    vset = {(r.a, r.side, round(float(r.p), 3), int(r.s)) for r in LA[LA.valid].itertuples()}
    q = {}
    meta = {}
    for i, r in enumerate(tk.itertuples()):
        a = t0map[r.tok]
        z = 0 if r.tok == a else 1
        F = float(fills.get(r.tx, 0.0))
        if F <= 0:
            continue
        meta[i] = {"z": z, "lim": round(float(r.price), 3), "F": F, "a": a}
        for d in DELTAS:
            q.setdefault(a, []).append((float(r.sign_ms) + 1040.0 + d, i, d))
    for a in q:
        q[a].sort()
    st = {}
    qi = {a: 0 for a in q}
    D = {}

    def answer(a, upto):
        b, o, ob, oo = st[a]
        qa = q[a]
        while qi[a] < len(qa) and qa[qi[a]][0] < upto:
            t, i, d = qa[qi[a]]
            qi[a] += 1
            m = meta[i]
            if m["z"] == 0:
                dep = sum(z - oo.get(p, 0.0) for p, z in o.items() if p <= m["lim"] + 1e-9 and z - oo.get(p, 0.0) > 0.5)
            else:
                dep = sum(z - ob.get(p, 0.0) for p, z in b.items() if p >= 1 - m["lim"] - 1e-9 and z - ob.get(p, 0.0) > 0.5)
            D[(i, d)] = dep

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
                        ob = {p: min(v, b.get(p, 0.0)) for p, v in st[a][2].items()}
                        oo = {p: min(v, o.get(p, 0.0)) for p, v in st[a][3].items()}
                    else:
                        ob, oo = {}, {}
                    st[a] = (b, o, ob, oo)
                elif k == "pc" and a in st:
                    b, o, ob, oo = st[a]
                    for sd, p, z in r.get("c") or []:
                        p, z = float(p), float(z)
                        book = b if sd == "BUY" else o
                        ow = ob if sd == "BUY" else oo
                        d = z - book.get(p, 0.0)
                        whole = abs(p * 100 - round(p * 100)) < 1e-6
                        fz = whole and round(abs(d), 2) in own_sz
                        if d > 0 and (a, sd, round(p, 3), int(s)) in vset:
                            ow[p] = ow.get(p, 0.0) + d
                        elif d < 0 and fz and ow.get(p, 0.0) > 0.5:
                            ow[p] = max(0.0, ow.get(p, 0.0) + d)
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
    rows = []
    for i, m in meta.items():
        if (i, -50) not in D:
            continue
        base = D[(i, -50)]
        sig = D.get((i, -1040), np.nan)
        for d in DELTAS:
            if (i, d) not in D:
                continue
            dep = D[(i, d)]
            # iteration-11 fix: adding its own fill back makes the post-match refill 1 by construction (the
            # counterfactual cancels of the consumed makers are unobservable). Report instead (a) depth at <= limit
            # relative to its value at SIGNING (the decay through the 1-s delay window) and (b) the RESIDUAL depth at
            # <= limit after its match relative to its fill (what a delayed copy finds beyond the wallet's own take).
            rows.append({"i": i, "d": d, "F": m["F"], "dep": dep, "base": base,
                         "refill": min(m["F"], dep) / m["F"], "rel": dep / base if base > 0 else np.nan,
                         "rel_sign": dep / sig if np.isfinite(sig) and sig > 0 else np.nan})
    R = pd.DataFrame(rows)
    out = {"takes": int(R.i.nunique()) if len(R) else 0, "F_median": round(float(np.median([m["F"] for m in meta.values()])), 1) if meta else None,
           "curve": {}}
    for d in DELTAS:
        S = R[R.d == d]
        if S.empty:
            continue
        out["curve"][str(d)] = {"n": int(len(S)), "refill_median": round(float(S.refill.median()), 3),
                                "refill_mean": round(float(S.refill.mean()), 3),
                                "share_refill_ge_50pct": round(float((S.refill >= 0.5).mean()), 3),
                                "depth_rel_to_minus50_median": round(float(S.rel.median()), 3) if S.rel.notna().any() else None,
                                "depth_rel_to_signing_median": round(float(S.rel_sign.median()), 3) if S.rel_sign.notna().any() else None,
                                "depth_rel_to_signing_mean": round(float(S.rel_sign.mean()), 3) if S.rel_sign.notna().any() else None}
    (RES / "remainder_survival.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
