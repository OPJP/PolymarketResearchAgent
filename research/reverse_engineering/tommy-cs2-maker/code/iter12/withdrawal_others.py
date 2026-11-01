"""X159 add-on: during the wallet's event-wide withdrawals (withdrawals.py), do the other makers withdraw too?
BUILD-live raw book (tommy_cs2_near), own levels removed with the validated label (as take_gap.py). For each episode and
each recorded book of the event: the others' resting size within 3c of their best bid plus within 3c of their best ask
(token0 book, both sides), read 3 s before the episode start (pre), 0.5 s after it (in) and 0.5 s after its end (post);
the same at control instants 60-300 s away in the same event. A common suspension predicts a drop at 'in' for the
others too; an own policy predicts others unchanged. Output: results/withdrawal_others.json
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
import os as _os
SUF = _os.environ.get("TOMMY_BLOCK_SUFFIX", "")
OWN0, END = int(_os.environ.get("TOMMY_BLOCK_START", 1793458232)), int(_os.environ.get("TOMMY_BLOCK_END", 1793469600))


def main():
    E = pd.read_parquet(OUT / f"iter12/withdrawal_episodes{SUF}.parquet")
    dm = pd.read_parquet(OUT / f"dev_markets{SUF}.parquet")
    dmt = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    books_of = {ev: [str(t) for t in g.tok0] for ev, g in dmt.groupby("event")}
    t0map = {}
    for r in dmt.itertuples():
        t0map[str(r.tok0)] = str(r.tok0); t0map[str(r.tok1)] = str(r.tok0)
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet"); cd["tok"] = cd.token_id.astype(str)
    mo = cd[(cd.idx >= 0) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(t0map)].drop_duplicates("salt")
    sizes = {}
    for r in mo.itertuples():
        sizes.setdefault(t0map[r.tok], set()).add(round(float(r.shares), 2))
    sizes = {a: v | {100.0} for a, v in sizes.items()}
    LA = pd.read_parquet(OUT / f"linked_adds_dev{SUF}.parquet")
    LA["valid"] = LA.F_mkt & (LA.in_burst | (LA["size"] != 100))
    vset = {(r.a, r.side, round(float(r.p), 3), int(r.s)) for r in LA[LA.valid].itertuples()}
    rng = np.random.default_rng(4)
    q = {}
    qid = 0
    meta = {}
    for r in E.itertuples():
        for ctrl in (0, 1, 2):
            off = 0.0 if ctrl == 0 else float(rng.choice([-1, 1]) * rng.uniform(60000, 300000))
            st, en = r.start + off, r.end + off
            if st < OWN0 * 1000 or en > END * 1000:
                continue
            for a in books_of.get(r.event, []):
                for ph, tq in (("pre", st - 3000), ("in", st + 500), ("post", en + 500)):
                    q.setdefault(a, []).append((tq, qid, ph))
                meta[qid] = (r.event, a, ctrl, r.dur)
                qid += 1
    for a in q:
        q[a].sort()
    stt, qi, ans = {}, {a: 0 for a in q}, {}

    def near_depth(a):
        b, o, ob, oo = stt[a]
        ob_ = {p: z - ob.get(p, 0.0) for p, z in b.items() if z - ob.get(p, 0.0) > 0.5}
        oo_ = {p: z - oo.get(p, 0.0) for p, z in o.items() if z - oo.get(p, 0.0) > 0.5}
        d = 0.0
        if ob_:
            bb = max(ob_); d += sum(z for p, z in ob_.items() if p >= bb - 0.03 - 1e-9)
        if oo_:
            aa = min(oo_); d += sum(z for p, z in oo_.items() if p <= aa + 0.03 + 1e-9)
        own = sum(z for z in ob.values() if z > 0.5) + sum(z for z in oo.values() if z > 0.5)
        return d, own

    def answer(a, upto):
        qa = q[a]
        while qi[a] < len(qa) and qa[qi[a]][0] < upto:
            t, i, ph = qa[qi[a]]; qi[a] += 1
            if a in stt:
                ans[(i, ph)] = near_depth(a)

    h = int(OWN0 // 3600 * 3600)
    while h < END:
        try:
            for r in live.iter_live("tommy_cs2_near", max(h, OWN0), min(h + 3600, END)):
                a = r.get("a")
                if a not in q or "s" not in r:
                    continue
                s = float(r["s"])
                answer(a, s)
                k = r.get("k")
                if k == "x":
                    continue
                own_sz = sizes.get(a, {100.0})
                if k in ("q", "f"):
                    b = {float(p): float(z) for p, z in (r.get("b") or [])}
                    o = {float(p): float(z) for p, z in (r.get("o") or [])}
                    if a in stt:
                        ob = {p: min(v, b.get(p, 0.0)) for p, v in stt[a][2].items()}
                        oo = {p: min(v, o.get(p, 0.0)) for p, v in stt[a][3].items()}
                    else:
                        ob, oo = {}, {}
                    stt[a] = (b, o, ob, oo)
                elif k == "pc" and a in stt:
                    b, o, ob, oo = stt[a]
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
            print("feed", type(e).__name__, e, flush=True)
        h += 3600
    for a in q:
        answer(a, 1e18)
    rows = []
    for i, (ev, a, ctrl, dur) in meta.items():
        if (i, "pre") in ans and (i, "in") in ans and (i, "post") in ans:
            pre, inn, post = ans[(i, "pre")], ans[(i, "in")], ans[(i, "post")]
            rows.append({"event": ev, "a": a, "ctrl": int(ctrl > 0), "dur": dur, "oth_pre": pre[0], "oth_in": inn[0], "oth_post": post[0],
                         "own_pre": pre[1], "own_in": inn[1], "own_post": post[1]})
    D = pd.DataFrame(rows)
    D.to_parquet(OUT / f"iter12/withdrawal_others_rows{SUF}.parquet", index=False)
    out = {}
    for c, g in D.groupby("ctrl"):
        g = g[g.oth_pre > 0]
        r_in = g.oth_in / g.oth_pre; r_post = g.oth_post / g.oth_pre
        out["control" if c else "episodes"] = {"n_book_episodes": int(len(g)), "others_in_over_pre_median": round(float(r_in.median()), 3),
                                               "share_others_drop_ge50pct": round(float((r_in <= 0.5).mean()), 3),
                                               "others_post_over_pre_median": round(float(r_post.median()), 3),
                                               "own_pre_median": float(g.own_pre.median()), "own_in_median": float(g.own_in.median())}
    (RES / f"withdrawal_others{SUF}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
