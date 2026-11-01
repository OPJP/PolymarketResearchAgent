"""iteration 18, T3 = X220 (information panel I17-1; frozen as the panel specified, on 11-01 07:00-09:15, which the panel
had looked at): event law E for the side of the cluster's at-touch 500/1000 posts (non-extreme 0.10-0.90):
  (1) a public Chainlink BTC publish P_i in (t - 150 ms, t] with |u_i| >= $1 -> sign(u_i) (u_i = the report change minus
      a futures-only prediction: four 0.5-s increments of the Binance USD-M mid known by stamp + 300 ms, OLS fitted on
      11-01 07:00-08:00);
  (2) else a futures-mid jump (k 3 sigma over 0.5 s, 100-ms grid, refractory 0.5 s; the T13 detector) ending in
      (t - 450, t - 50] ms -> its sign;
  (3) else the posture (Chainlink stamped <= t - 1.25 s, Gamma strike, 1.4 x futures sigma300, vs the Up mid before the add).
Scored per post against the posture, the cheaper token, W500 'rose else posture' and the last-hit token, overall and by
|F - mid| band; signed event study of the posts around publishes with |u| >= 1 ((-300, 0] and (0, 150] ms) with a
binomial p and a swap null (u moved to the publish 1-3 before / after). Blocks: freeze 11-01 07:00-09:15 (in sample),
confirmation 11-01 09:15-12:00 and 10-31 17:29-18:00 (noise regime). Development blocks only (iter_live)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code14"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from lagged_quote import fut_mid, at, live  # noqa: E402
import indicators as ind  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
FIT = (1793516400, 1793520000)
BLOCKS = {"freeze_1101_0700_0915": (1793516400, 1793524500, "it14_qu_rebuilt_1793516400_1793524500.parquet"),
          "confirm_1101_0915_1200": (1793524500, 1793534400, "it14_qu_rebuilt_1793524500_1793534400.parquet"),
          "confirm_1031_1729_1800": (1793467740, 1793469600, "it14_qu_rebuilt_1793455200_1793469600.parquet")}
LAGS = (300, -200, -700, -1200)


def publishes(a, b):
    cl, P = {}, {}
    for r in live.iter_live("dy_rtds", a - 10, b + 5):
        if r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P"):
            s = int(r["ts"]) // 1000
            if s not in cl:
                cl[s] = float(r["v"])
                P[s] = int(r["P"])
    secs = sorted(s for s in cl if (s - 1) in cl and a <= s < b)
    return secs, cl, P


def design(E, M, secs):
    X = np.array([[at(E, M, np.array([s * 1000 + g]))[0] - at(E, M, np.array([s * 1000 + g - 500]))[0] for g in LAGS] for s in secs])
    return X


def main():
    E0, M0 = fut_mid(FIT[0] - 120, FIT[1] + 60)
    secs, cl, P = publishes(*FIT)
    X = design(E0, M0, secs)
    y = np.array([cl[s] - cl[s - 1] for s in secs])
    ok = np.all(np.isfinite(X), axis=1)
    beta, *_ = np.linalg.lstsq(np.c_[np.ones(ok.sum()), X[ok]], y[ok], rcond=None)
    res = {"beta": [round(float(b), 4) for b in beta], "fit_n": int(ok.sum())}
    for name, (a, b, qf) in BLOCKS.items():
        f = C / qf
        if not f.exists():
            res[name] = {"error": "missing " + qf}
            continue
        q = pd.read_parquet(f)
        q = q[(q.s >= a * 1000) & (q.s < b * 1000) & (q.p >= 0.10) & (q.p <= 0.90) & q.dz.isin([500.0, 1000.0])].copy()
        q = q.sort_values("s").reset_index(drop=True)
        E, M = fut_mid(a - 120, b + 60)
        sc, clb, Pb = publishes(a, b)
        Xb = design(E, M, sc)
        yb = np.array([clb[s] - clb[s - 1] for s in sc])
        okb = np.all(np.isfinite(Xb), axis=1)
        pred = np.where(okb, np.c_[np.ones(len(Xb)), np.nan_to_num(Xb)] @ beta, np.nan)
        u = yb - pred
        pub = pd.DataFrame({"P": [Pb[s] for s in sc], "u": u}).sort_values("P").reset_index(drop=True)
        Pm = pub.P.to_numpy(np.int64)
        um = pub.u.to_numpy(float)
        # futures jumps (T13 detector)
        tg = ind.grid(a - 60, b + 30, 0.1)
        mid = ind.asof(tg, np.asarray(E, float) / 1000.0, np.asarray(M, float))
        jt, js = ind.jumps(tg, mid, horizon=5, k=3.0, refractory_s=0.5)
        jt = np.asarray(jt, float)
        js = np.asarray(js, float)
        t = q.s.to_numpy(np.int64)
        yv = (q.sd == 1).to_numpy(float)
        F = q.F.to_numpy(float)
        mp = q.mid_prev.to_numpy(float)
        post = np.where(np.isfinite(F) & np.isfinite(mp), (F > mp).astype(float), np.nan)
        cheap = np.where(np.isfinite(mp), (mp < 0.5).astype(float), np.nan)
        hit = q.hit.to_numpy(float)
        f50 = at(E, M, t - 50)
        dF = f50 - at(E, M, t - 500)
        rose = np.where(np.abs(dF) >= 2.0, (dF > 0).astype(float), post)
        law = post.copy()
        src = np.full(len(t), "posture", dtype=object)
        for k, tk in enumerate(t):
            j = np.searchsorted(Pm, tk, side="right") - 1
            used = False
            while j >= 0 and Pm[j] > tk - 150:
                if np.isfinite(um[j]) and abs(um[j]) >= 1.0:
                    law[k] = float(um[j] > 0)
                    src[k] = "publish_u"
                    used = True
                    break
                j -= 1
            if used:
                continue
            i = np.searchsorted(jt, (tk - 50) / 1000.0, side="right") - 1
            if i >= 0 and jt[i] > (tk - 450) / 1000.0:
                law[k] = float(js[i] > 0)
                src[k] = "futures_jump"
        law2 = np.where(src == "publish_u", law, rose)  # T3b: E2 = publish u, else W500 rose, else posture
        edge = np.abs(F - mp)
        bands = {"lt0.05": edge < 0.05, "0.05-0.1": (edge >= 0.05) & (edge < 0.1), "ge0.1": edge >= 0.1, "all": np.isfinite(edge)}

        def acc(pr, m):
            mm = m & np.isfinite(pr) & np.isfinite(post)
            return [round(float((pr[mm] == yv[mm]).mean()), 4) if mm.any() else None, int(mm.sum())]
        rec = {"posts": int(len(q)), "with_posture": int(np.isfinite(post).sum()), "publishes": int(len(pub)),
               "u_sd": round(float(np.nanstd(um)), 3), "jumps": int(len(jt)),
               "source_share": {s_: round(float((src == s_).mean()), 3) for s_ in ("publish_u", "futures_jump", "posture")}}
        for bn, bm in bands.items():
            rec[bn] = {"law_E": acc(law, bm), "law_E2": acc(law2, bm), "posture": acc(post, bm), "cheaper": acc(cheap, bm), "W500_rose_else_posture": acc(rose, bm),
                       "last_hit_token": acc(hit, bm)}
        rec["by_source"] = {s_: {"law_E": acc(law, src == s_), "posture": acc(post, src == s_)} for s_ in ("publish_u", "futures_jump", "posture")}
        # signed event study around publishes with |u| >= 1
        us = np.where(q.sd == 1, 1, -1)

        def agree(lo, hi, shift=0):
            ag = tot = 0
            for i, (Pi, ui) in enumerate(zip(Pm, um)):
                j = i + shift
                if j < 0 or j >= len(um) or not np.isfinite(um[j]) or abs(um[j]) < 1.0:
                    continue
                if not np.isfinite(ui) or abs(ui) < 1.0:
                    continue
                aa = np.searchsorted(t, Pi + lo, side="right")
                bb = np.searchsorted(t, Pi + hi, side="right")
                ag += int((np.sign(um[j]) == us[aa:bb]).sum())
                tot += bb - aa
            return ag, tot
        es = {}
        for lo, hi in ((-600, -300), (-300, 0), (0, 150), (150, 300), (300, 600)):
            ag, tot = agree(lo, hi)
            es[f"({lo},{hi}]"] = {"n": tot, "agree": round(ag / tot, 3) if tot else None,
                                  "p_one_sided": float(binomtest(ag, tot, 0.5, alternative="greater").pvalue) if tot else None}
        nulls = []
        for sh in (-3, -2, -1, 1, 2, 3):
            ag, tot = agree(0, 150, sh)
            nulls.append(round(ag / tot, 3) if tot else None)
        es["(0,150]_swap_null_u_shift_-3..3"] = nulls
        rec["event_study_u_ge_1"] = es
        n0 = es["(0,150]"]["n"]
        rec["signature_block"] = bool(n0 >= 40 and (es["(0,150]"]["agree"] or 0) >= 0.65 and (es["(-300,0]"]["agree"] or 1) <= 0.55)
        lt = rec["lt0.05"]
        ge = rec["ge0.1"]
        rec["law_beats_posture_small_edge_by_0.05"] = bool(lt["law_E"][0] is not None and lt["law_E"][0] - lt["posture"][0] >= 0.05)
        rec["law_not_worse_ge0.1"] = bool(ge["law_E"][0] is not None and ge["law_E"][0] >= ge["posture"][0])
        rec["E2_beats_posture_small_edge_by_0.05"] = bool(lt["law_E2"][0] is not None and lt["law_E2"][0] - lt["posture"][0] >= 0.05)
        rec["E2_not_worse_ge0.1"] = bool(ge["law_E2"][0] is not None and ge["law_E2"][0] >= ge["posture"][0])
        res[name] = rec
    (HERE.parent / "results" / "iter18_event_law.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
