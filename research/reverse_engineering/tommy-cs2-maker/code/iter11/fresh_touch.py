"""X153 (assumptions panel iter-10 P1): a freshness-filtered touch as the public form of V (BUILD-live 10-31 14:50-18:00).

Data: level_events_dev (every near-touch level change of the wallet's dev-unit CS2 token-0 books from tommy_cs2_near,
server clock 's' in ms; kinds add / cancel / cons) and linked_adds_dev (the same adds with the iteration-7 validated
own-add label columns). Own state:
  own add    = validated label of iteration 7 (F_mkt & (in_burst | size != 100));
  own remove = a decrease at a level where the tracked own size covers it and |d| equals an own add size there
               (cancel or consumption of its own order).
Every other change is NON-OWN; each level keeps the server time of its last non-own change.
Decision population (uncensored): the validated own adds (BUY side). Decision time t = s - 24 ms (its post latency).
Anchors at t (book state strictly before t, own size removed):
  J      = best bid among levels with (size - own) > 0.5 (the touch);
  FT_D   = best bid among levels with (size - own) > 0.5 whose last non-own change lies in [t - D, t - 20 ms],
           D in {0.25, 0.5, 1, 2, 5, 15, 60} s; falls back to J when no level qualifies (coverage reported);
  plus a constant offset k (whole cents, -3..+3) fitted with D on the FIRST half of the block (by time) and scored on
  the SECOND half. Subpopulations: new-own-top adds (the add's price is above its previous own top on the token).
Within one tick = |price - anchor| <= 0.01 (anchors in [0.04, 0.96]) else 0.001. Event bootstrap (500) of FT - J.
Pre-registered signature (panel): true iff FT beats J by >= 0.10 on adds and on top changes; false iff FT <= J + 0.03
for every D. Output: results/fresh_touch.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
C = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
DS = [0.25, 0.5, 1, 2, 5, 15, 60]
KS = [-0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03]


def tickhit(p, a):
    p, a = np.asarray(p, float), np.asarray(a, float)
    t = np.where((a >= 0.04) & (a <= 0.96), 0.01, 0.001)
    return np.isfinite(a) & (np.abs(p - a) <= t + 1e-9)


def main():
    E = pd.read_parquet(C / "level_events_dev.parquet")
    LA = pd.read_parquet(C / "linked_adds_dev.parquet", columns=["a", "s", "side", "p", "d", "z", "F_mkt", "in_burst", "slug"])
    LA["own"] = LA.F_mkt & (LA.in_burst | (LA.d.round(2) != 100.0))
    LA = LA.drop_duplicates(["a", "s", "side", "p", "d", "z"])
    E = E.merge(LA[["a", "s", "side", "p", "d", "z", "own", "slug"]], on=["a", "s", "side", "p", "d", "z"], how="left")
    E["own"] = E.own.fillna(False).astype(bool)
    E = E[E.side == "BUY"].sort_values(["s"], kind="stable").reset_index(drop=True)
    slug_of = E.dropna(subset=["slug"]).groupby("a").slug.first().to_dict()
    # state per asset: price -> [size, own_size, last_nonown_ts, own_add_sizes(list)]
    book = {}
    rows = []
    own_top = {}
    for r in E.itertuples(index=False):
        a = r.a
        bk = book.setdefault(a, {})
        lv = bk.get(r.p)
        if lv is None:
            lv = [0.0, 0.0, -1e18, []]
            bk[r.p] = lv
        if r.kind == "add" and r.own:
            t = r.s - 24
            # anchors from the state before this add
            live_lv = [(p, v) for p, v in bk.items() if v[0] - v[1] > 0.5]
            J = max((p for p, _ in live_lv), default=np.nan)
            ft = {}
            for D in DS:
                lo, hi = t - D * 1000, t - 20
                cand = [p for p, v in live_lv if lo <= v[2] <= hi]
                ft[D] = (max(cand) if cand else np.nan)
            ot = own_top.get(a)
            rows.append({"a": a, "slug": slug_of.get(a), "s": r.s, "p": r.p, "J": J, **{f"FT{D}": ft[D] for D in DS},
                         "new_top": bool(ot is None or r.p > ot + 1e-9)})
            lv[0] += r.d
            lv[1] += r.d
            lv[3].append(round(r.d, 2))
        elif r.kind == "add":
            lv[0] += r.d
            lv[2] = r.s
        else:  # decrease (cancel / cons)
            dd = -r.d
            if lv[1] > 0.5 and round(dd, 2) in lv[3] and dd <= lv[1] + 0.5:
                lv[1] -= dd
                lv[3].remove(round(dd, 2))
            else:
                lv[2] = r.s
            lv[0] = max(0.0, lv[0] - dd)
            if lv[1] > lv[0]:
                lv[1] = lv[0]
        # own top on the asset
        ops = [p for p, v in bk.items() if v[1] > 0.5]
        own_top[a] = max(ops) if ops else None
    R = pd.DataFrame(rows)
    R = R[R.p.between(0.04, 0.96)]
    tmid = R.s.median()
    fit, sco = R[R.s < tmid], R[R.s >= tmid]
    out = {"adds": int(len(R)), "assets": int(R.a.nunique()), "events": int(R.slug.nunique()),
           "split_ms": float(tmid), "by_D": {}}
    for nm, sub in (("first_half", fit), ("second_half", sco), ("all", R)):
        J = sub.J.to_numpy(float)
        o = {"n": int(len(sub)), "touch": round(float(tickhit(sub.p, J).mean()), 3)}
        for D in DS:
            f = sub[f"FT{D}"].to_numpy(float)
            cov = np.isfinite(f)
            fb = np.where(cov, f, J)
            o[f"FT{D}"] = {"within_tick": round(float(tickhit(sub.p, fb).mean()), 3), "coverage": round(float(cov.mean()), 3),
                           "within_tick_on_covered": round(float(tickhit(sub.p[cov], f[cov]).mean()), 3) if cov.any() else None,
                           "touch_on_covered": round(float(tickhit(sub.p[cov], J[cov]).mean()), 3) if cov.any() else None}
        o["new_top_touch"] = round(float(tickhit(sub.p[sub.new_top], J[sub.new_top.to_numpy()]).mean()), 3) if sub.new_top.any() else None
        out["by_D"][nm] = o
    # fit D and k on the first half; score the second half
    best = None
    for D in DS:
        for k in KS:
            f = fit[f"FT{D}"].to_numpy(float)
            fb = np.where(np.isfinite(f), f + k, fit.J.to_numpy(float) + k)
            sc = float(tickhit(fit.p, fb).mean())
            if best is None or sc > best[0]:
                best = (sc, D, k)
    bj = max(((float(tickhit(fit.p, fit.J.to_numpy(float) + k).mean()), k) for k in KS))
    D, k = best[1], best[2]
    f2 = sco[f"FT{D}"].to_numpy(float)
    fb2 = np.where(np.isfinite(f2), f2 + k, sco.J.to_numpy(float) + k)
    hitF = tickhit(sco.p, fb2)
    hitJ = tickhit(sco.p, sco.J.to_numpy(float) + bj[1])
    hitJ0 = tickhit(sco.p, sco.J.to_numpy(float))
    nt = sco.new_top.to_numpy()
    rng = np.random.default_rng(11)
    ev = sco.slug.fillna("?").to_numpy()
    ue = np.unique(ev)
    diffs = []
    for _ in range(500):
        pick = rng.choice(ue, len(ue))
        m = np.concatenate([np.where(ev == e)[0] for e in pick])
        diffs.append(hitF[m].mean() - hitJ[m].mean())
    out["fitted"] = {"D": D, "k": k, "fit_score": round(best[0], 3), "touch_k": bj[1], "touch_fit_score": round(bj[0], 3),
                     "second_half": {"FT_fitted": round(float(hitF.mean()), 3), "touch_fitted_k": round(float(hitJ.mean()), 3),
                                     "touch_raw": round(float(hitJ0.mean()), 3),
                                     "gain_ci95": [round(float(np.percentile(diffs, 2.5)), 3), round(float(np.percentile(diffs, 97.5)), 3)],
                                     "new_top": {"n": int(nt.sum()), "FT": round(float(hitF[nt].mean()), 3) if nt.any() else None,
                                                 "touch": round(float(hitJ[nt].mean()), 3) if nt.any() else None}}}
    (RES / "fresh_touch.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
