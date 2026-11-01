"""X136 step 1 (panel iter12 mechanics P2): is a run switch a quote move or a sweep? Development block 10-31 14-18
(dm_clob_raw via code13/tracers.py outputs; calldata live1031 for the filled orders).

For every cluster maker BUY fill whose transaction is in the raw trade stream: the filled order's post = the latest add of
exactly its calldata original size at exactly its limit price on its book side before the fill (schedule sizes within
0.20 of the touch from sched_adds; non-schedule sizes from the tracer table). Class (i) 'quote move': the post was at or
above the own-token touch at the post time (the cluster moved its quote to the touch); class (ii) 'market move': the
post rested below the touch and the market came down to it. Runs = consecutive cluster fills of one window on one
outcome (all three wallets); a switch = the first fill of every run after the first.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / ".cache/re/directional-maker/it13"
CL = {"0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
      "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona"}
SCHED = {5, 10, 12, 20, 25, 31, 40, 50, 62, 100, 125, 200, 250, 300, 400, 500, 1000, 2000}


def main():
    fs = sorted(glob.glob(str(ROOT / ".cache/re/directional-maker/calldata/live1031*"))) + \
        glob.glob(str(ROOT / ".cache/re/directional-maker/calldata/liveall1031*"))
    d = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    d["maker"] = d.maker.str.lower()
    o = d[d.maker.isin(set(CL)) & (d.role == "maker") & (d.oside == 0)].copy()
    o["orig"] = (o.taker_amount / 1e6).round(2)
    o["lim"] = (o.maker_amount / o.taker_amount).round(3)
    o["tx"] = o.tx.str.lower()
    o = o.drop_duplicates(["tx", "maker", "salt"])
    X = pd.read_parquet(OUT / "trades.parquet")
    fx = X.drop_duplicates("h").set_index("h")
    o = o[o.tx.isin(fx.index)].copy()
    o["w"] = o.tx.map(fx.w)
    o["fill_ms"] = o.tx.map(fx.s).astype(np.int64)
    # Up/Down of the order's token from the trade stream: the cluster's maker BUY of token T printed with asset index ai
    import json as _j
    from polyrea.workflows.updown_study import fetch_windows
    sys.path.insert(0, str(ROOT))
    raw = fetch_windows(sorted(set(o.w)))
    up_tok = {}
    for m in raw.values():
        toks = _j.loads(m.get("clobTokenIds") or "[]")
        outs = _j.loads(m.get("outcomes") or "[]")
        up_tok[m["slug"]] = str(toks[0 if (outs and str(outs[0]).lower() == "up") else 1])
    o["is_up"] = (o.token_id.astype(str) == o.w.map(up_tok)).astype(int)
    o["sd"] = np.where(o.is_up == 1, 1, 0)
    o["bp"] = np.where(o.is_up == 1, o.lim, (1 - o.lim).round(3))   # price in the Up book
    S = pd.read_parquet(OUT / "sched_adds.parquet")
    T = pd.read_parquet(OUT / "tracer_events.parquet")
    Tt = T[["w", "s", "sd", "p", "bb", "ba"]].assign(dz=T["size"])
    A = pd.concat([S[["w", "s", "sd", "p", "dz", "bb", "ba"]], Tt], ignore_index=True)
    A["p"] = A.p.round(3)
    A["dz"] = A.dz.round(2)
    key = A.groupby(["w", "sd", "p", "dz"])
    idx = {k: g.sort_values("s") for k, g in key}
    rows = []
    for r in o.itertuples(index=False):
        g = idx.get((r.w, int(r.sd), round(float(r.bp), 3), round(float(r.orig), 2)))
        if g is None:
            rows.append((np.nan, np.nan, np.nan))
            continue
        g = g[g.s <= r.fill_ms]
        if g.empty:
            rows.append((np.nan, np.nan, np.nan))
            continue
        a = g.iloc[-1]
        own_touch = a.bb if r.sd == 1 else a.ba
        at = (r.bp >= own_touch - 1e-9) if r.sd == 1 else (r.bp <= own_touch + 1e-9)
        dist = (r.bp - own_touch) if r.sd == 1 else (own_touch - r.bp)
        rows.append((int(a.s), float(at), float(dist)))
    o[["post_ms", "post_at_touch", "post_dist"]] = pd.DataFrame(rows, index=o.index)
    o["age"] = (o.fill_ms - o.post_ms) / 1000
    o["sched"] = o.orig.isin(SCHED)
    # runs over the pooled cluster fills (one row per filled order and fill tx)
    o = o.sort_values(["w", "fill_ms"], kind="stable")
    o["run"] = o.groupby("w").is_up.transform(lambda s: (s != s.shift()).cumsum())
    first = o.groupby(["w", "run"]).head(1).copy()
    first["kind"] = np.where(first.run == 1, "entry_run_start", "switch")
    cont = o.drop(first.index)
    out = {"orders": int(len(o)), "post_found": float(o.post_ms.notna().mean())}

    def summ(g):
        k = g.post_ms.notna()
        return {"n": int(len(g)), "post_found": float(k.mean()), "quote_move_share": float(g.post_at_touch[k].mean()) if k.any() else None,
                "age_median_s": float(g.age[k].median()) if k.any() else None, "age_q75_s": float(g.age[k].quantile(0.75)) if k.any() else None,
                "dist_below_touch_median": float(g.post_dist[k & (g.post_at_touch == 0)].median()) if (k & (g.post_at_touch == 0)).any() else None}
    out["all"] = summ(o)
    out["continuation"] = summ(cont)
    out["entry_run_start"] = summ(first[first.kind == "entry_run_start"])
    out["switch"] = summ(first[first.kind == "switch"])
    out["switch_by_class"] = {"schedule": summ(first[(first.kind == "switch") & first.sched]), "pairing": summ(first[(first.kind == "switch") & ~first.sched])}
    out["by_wallet"] = {CL[m]: summ(g) for m, g in o.groupby("maker")}
    print(json.dumps(out, indent=1, default=float))
    (HERE.parent / "results/iter13_switch_class.json").write_text(json.dumps(out, indent=1, default=float))
    o.to_parquet(OUT / "fills_posts.parquet", index=False)


if __name__ == "__main__":
    main()
