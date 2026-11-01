"""X159 / X168 steps 1-2 (information panel iter-11 P2, assumptions P2): a suspension fingerprint of E4 that does not need
Thunderpick's price level. BUILD-live (10-31 14:50-18:00, raw tommy_cs2_near book, calldata-validated own label; book
machinery of take_gap.py).

Own-level occupancy per book (own bid levels on token0 and token1) is replayed; an EVENT-WIDE withdrawal episode is a
period with no own level on ANY recorded book of the event, lasting >= 2 loop ticks (1,008 ms), between the event's
first and last own level of the session. Reported: the duration distribution (mass at three ticks, 1,512 +- 60 ms,
against a broad tail), the share of episodes that start within 2 s after its own take (calldata), and the re-post
level change (own top on token0 after minus before, cents). An odds-product copier predicts variable-length
withdrawals (median >= 3 s, not quantized); an own-model maker predicts short repairs tied to its own takes / pulls.
Output: results/withdrawals.json
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
TICK = 504.0


def main():
    dm = pd.read_parquet(OUT / f"dev_markets{SUF}.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    ev_of = {str(r.tok0): r.event for r in dm.itertuples()}
    t0map = {}
    for r in dm.itertuples():
        t0map[str(r.tok0)] = str(r.tok0); t0map[str(r.tok1)] = str(r.tok0)
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet")
    cd["tok"] = cd.token_id.astype(str)
    mo = cd[(cd.idx >= 0) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(t0map)].drop_duplicates("salt")
    sizes = {}
    for r in mo.itertuples():
        sizes.setdefault(t0map[r.tok], set()).add(round(float(r.shares), 2))
    sizes = {a: v | {100.0} for a, v in sizes.items()}
    tk = cd[(cd.idx == -1) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(t0map)]
    tk = tk[(tk.sign_ms >= OWN0 * 1000) & (tk.sign_ms < END * 1000)]
    takes_by_ev = {}
    for r in tk.itertuples():
        takes_by_ev.setdefault(ev_of[t0map[r.tok]], []).append(float(r.sign_ms) + 24.0)
    LA = pd.read_parquet(OUT / f"linked_adds_dev{SUF}.parquet")
    LA["valid"] = LA.F_mkt & (LA.in_burst | (LA["size"] != 100))
    vset = {(r.a, r.side, round(float(r.p), 3), int(r.s)) for r in LA[LA.valid].itertuples()}
    st = {}
    occ = []  # (s, a, n_own_levels, own_top0)
    last_n = {}
    h = int(OWN0 // 3600 * 3600)
    while h < END:
        try:
            for r in live.iter_live("tommy_cs2_near", max(h, OWN0), min(h + 3600, END)):
                a = r.get("a")
                if a not in ev_of or "s" not in r:
                    continue
                s = float(r["s"]); k = r.get("k")
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
                else:
                    continue
                b, o, ob, oo = st[a]
                n = sum(1 for z in ob.values() if z > 0.5) + sum(1 for z in oo.values() if z > 0.5)
                top0 = max([p for p, z in ob.items() if z > 0.5], default=np.nan)
                if last_n.get(a) != n:
                    occ.append((s, a, n, top0)); last_n[a] = n
        except Exception as e:  # noqa: BLE001
            print("feed", type(e).__name__, e, flush=True)
        h += 3600
    O = pd.DataFrame(occ, columns=["s", "a", "n", "top0"])
    O["event"] = O.a.map(ev_of)
    O.to_parquet(OUT / f"iter12/own_occupancy_rows{SUF}.parquet", index=False)
    eps = []
    for ev, g in O.groupby("event"):
        g = g.sort_values("s")
        cur = {}
        first = last = None
        prev_occ = None; t_off = None; top_before = np.nan
        for r in g.itertuples():
            cur[r.a] = r.n
            tot = sum(cur.values())
            occd = tot > 0
            if occd and first is None:
                first = r.s
            if occd:
                last = r.s
            if prev_occ is True and not occd:
                t_off = r.s; top_before = r.top0
            if prev_occ is False and occd and t_off is not None:
                eps.append({"event": ev, "start": t_off, "end": r.s, "dur": r.s - t_off})
                t_off = None
            prev_occ = occd
    E = pd.DataFrame(eps)
    out = {"events": int(O.event.nunique()), "occupancy_changes": int(len(O))}
    if len(E):
        E = E[E.dur >= 2 * TICK]
        tk_ev = {e: np.sort(np.array(v)) for e, v in takes_by_ev.items()}
        def after_take(row):
            arr = tk_ev.get(row.event)
            if arr is None:
                return False
            j = np.searchsorted(arr, row.start) - 1
            return bool(j >= 0 and row.start - arr[j] <= 2000)
        E["after_take"] = E.apply(after_take, axis=1) if len(E) else []
        E["ticks"] = E.dur / TICK
        out.update({"episodes_ge_2ticks": int(len(E)),
                    "dur_quantiles_s": {q: round(float(E.dur.quantile(q) / 1000), 2) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
                    "share_3ticks_pm60ms": round(float((np.abs(E.dur - 3 * TICK) <= 60).mean()), 3),
                    "share_2to4ticks": round(float(((E.dur >= 2 * TICK) & (E.dur <= 4 * TICK + 60)).mean()), 3),
                    "share_ge_3s": round(float((E.dur >= 3000).mean()), 3),
                    "share_ge_10s": round(float((E.dur >= 10000).mean()), 3),
                    "share_start_within_2s_after_own_take": round(float(E.after_take.mean()), 3),
                    "tick_hist_2_to_12": np.histogram(E.ticks, bins=np.arange(2, 13, 0.5))[0].tolist()})
        E.to_parquet(OUT / f"iter12/withdrawal_episodes{SUF}.parquet", index=False)
    (RES / f"withdrawals{SUF}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
