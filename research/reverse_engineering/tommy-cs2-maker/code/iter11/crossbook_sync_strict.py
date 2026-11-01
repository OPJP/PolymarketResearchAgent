"""X154 step 2 (assumptions panel iter-10 P2), live and uncensored: invisible messages seen as cross-book synchrony.

BUILD-live 10-31 14:50-18:00 UTC, level_events_dev (every near-touch level change of the recorded token-0 books, server
clock). Events with >= 2 recorded books: cs2-gls1-pcy-2026-10-31 (match, map 1, map 2) and cs2-shin-isg-2026-10-31 (match,
map 1). Own re-pricings = validated own adds (iteration-7 label, linked_adds_dev). For each, a SYNC hit = a non-own level
change (add, or a decrease that is not one of its own sizes at a whole cent) on a DIFFERENT recorded book of the same
event within +-40 ms (a different market rules out a reaction to its own book; its orders reach the book ~24 ms after
signing). Trigger filter: no consumption ('cons') on any book of the event in the 300 ms before (no public trade).
Null: the same statistic at 2,000 shifted times per class (the own add's time + delta, |delta| uniform in [1, 5] s).
Also by the time since the last consumption on the event (quiet = > 5 s). Strict variant (iteration 11 check): non-own ADDs of any size the wallet uses in that book are dropped (they may be
its own unlabelled adds, e.g. its coherent cross-market re-pricing). Output: results/crossbook_sync_strict.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
C = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def own_sizes_by_asset():
    """Sizes the wallet used as a maker in each recorded book (calldata_dev, both tokens mapped to the token-0 asset) plus
    100: non-own ADDs of these sizes are dropped in the strict variant (they may be its own unlabelled adds)."""
    W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
    dm = pd.read_parquet(C / "dev_markets.parquet")
    t0 = {}
    for r in dm.itertuples():
        t0[str(r.tok0)] = str(r.tok0)
        t0[str(r.tok1)] = str(r.tok0)
    cd = pd.read_parquet(C / "calldata_dev.parquet", columns=["maker", "idx", "token_id", "shares"])
    cd = cd[(cd.maker.str.lower() == W) & (cd.idx >= 0)]
    cd["a"] = cd.token_id.astype(str).map(t0)
    out = {}
    for a, g in cd.dropna(subset=["a"]).groupby("a"):
        out[a] = set(np.round(g.shares.astype(float), 2)) | {100.0}
    return out


def main():
    E = pd.read_parquet(C / "level_events_dev.parquet")
    LA = pd.read_parquet(C / "linked_adds_dev.parquet", columns=["a", "s", "side", "p", "d", "z", "F_mkt", "in_burst", "slug"])
    LA["own"] = LA.F_mkt & (LA.in_burst | (LA.d.round(2) != 100.0))
    slug_of = LA.drop_duplicates("a").set_index("a").slug.to_dict()
    ev_of = {a: s.split("-game")[0] for a, s in slug_of.items()}
    E["ev"] = E.a.map(ev_of)
    E = E[E.ev.notna()]
    E = E.merge(LA[["a", "s", "side", "p", "d", "z", "own"]].drop_duplicates(["a", "s", "side", "p", "d", "z"]),
                on=["a", "s", "side", "p", "d", "z"], how="left")
    E["own"] = E.own.fillna(False).astype(bool)
    whole = (np.abs(E.p * 100 - np.round(E.p * 100)) < 1e-6)
    own_dec = (E.kind != "add") & whole & E.d.abs().round(2).isin([100.0, 50.0, 54.0, 10.0])
    E["nonown"] = ~E.own & ~own_dec & (E.kind != "cons")
    osz = own_sizes_by_asset()
    own_size_add = np.array([(k == "add") and (round(abs(d), 2) in osz.get(a, {100.0})) for a, k, d in zip(E.a, E.kind, E.d)])
    E["nonown"] = E["nonown"] & ~own_size_add  # strict variant: drop adds of its own sizes
    multi = [e for e, g in E.groupby("ev") if g.a.nunique() >= 2]
    out = {"events": multi, "by_event": {}}
    rng = np.random.default_rng(17)
    tot = {"n": 0, "hit": 0, "hit_quiet": 0, "n_quiet": 0, "null": [], "null_quiet": []}
    for e in multi:
        g = E[E.ev == e]
        own = g[(g.kind == "add") & g.own]
        cons_t = np.sort(g[g.kind == "cons"].s.to_numpy(float))
        nonown = {a: np.sort(x.s.to_numpy(float)) for a, x in g[g.nonown].groupby("a")}

        def hit(a, t):
            for b, ts in nonown.items():
                if b == a:
                    continue
                j = np.searchsorted(ts, t - 40)
                if j < len(ts) and ts[j] <= t + 40:
                    return True
            return False

        def trig_ok(t):
            j = np.searchsorted(cons_t, t)
            return not (j > 0 and cons_t[j - 1] >= t - 300)

        def quiet(t):
            j = np.searchsorted(cons_t, t)
            return not (j > 0 and cons_t[j - 1] >= t - 5000)

        n = h = nq = hq = 0
        for r in own.itertuples():
            t = float(r.s)
            if not trig_ok(t):
                continue
            n += 1
            hh = hit(r.a, t)
            h += hh
            if quiet(t):
                nq += 1
                hq += hh
        nulls, nullq = [], []
        ts_own = own.s.to_numpy(float)
        as_own = own.a.to_numpy()
        for _ in range(2000 if len(own) else 0):
            i = rng.integers(0, len(own))
            t = ts_own[i] + rng.choice([-1, 1]) * rng.uniform(200, 1000)
            if not trig_ok(t):
                continue
            hh = hit(as_own[i], t)
            nulls.append(hh)
            if quiet(t):
                nullq.append(hh)
        out["by_event"][e] = {"own_adds_no_trade_300ms": n, "sync_rate": round(h / n, 3) if n else None,
                              "null_rate": round(float(np.mean(nulls)), 3) if nulls else None,
                              "quiet_n": nq, "quiet_sync_rate": round(hq / nq, 3) if nq else None,
                              "quiet_null_rate": round(float(np.mean(nullq)), 3) if nullq else None}
        tot["n"] += n; tot["hit"] += h; tot["n_quiet"] += nq; tot["hit_quiet"] += hq
        tot["null"] += nulls; tot["null_quiet"] += nullq
    out["pooled"] = {"own_adds": tot["n"], "sync_rate": round(tot["hit"] / tot["n"], 3) if tot["n"] else None,
                     "null_rate": round(float(np.mean(tot["null"])), 3) if tot["null"] else None,
                     "quiet_own_adds": tot["n_quiet"], "quiet_sync_rate": round(tot["hit_quiet"] / tot["n_quiet"], 3) if tot["n_quiet"] else None,
                     "quiet_null_rate": round(float(np.mean(tot["null_quiet"])), 3) if tot["null_quiet"] else None}
    pr = out["pooled"]
    if pr["sync_rate"] is not None and pr["null_rate"]:
        out["pooled"]["excess_share"] = round(pr["sync_rate"] - pr["null_rate"], 3)
    if pr.get("quiet_sync_rate") is not None and pr.get("quiet_null_rate"):
        out["pooled"]["quiet_excess_share"] = round(pr["quiet_sync_rate"] - pr["quiet_null_rate"], 3)
    (RES / "crossbook_sync_strict.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
