"""Iteration 8: window-level side (the examiner's 'one-sided windows' unit) with the posture rule. Development live block
10-31 14:06-16:30 UTC, BTC 5m and 15m. One-sided window = >= 70% of the cluster's maker BUY shares on one outcome.
Predicted dominant side: (a) public, unconditioned: sign of the mean over the window's seconds of e_up = Chainlink fair of
Up (report stamped floor((t - 1432)/1000), true strike, 1.4 x 300-s futures vol) - Up mid; (b) conditioned on its acting
times only: sign of the share-weighted mean e_up at its fills' match ms (uses when it was filled, not which side).
Baselines: always-Up, the cheaper side at the window's mid-life, the sign of the mean futures edge.
    python code8/window_side.py 1793455600 1793464202
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
sys.path.insert(0, str(HERE.parent / "code6"))
from pres_live import load_ref  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
D_CL = 1432


def main(a, b):
    F = pd.read_parquet(C / "it6" / f"fill_side_{a}_{b}.parquet")
    tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
    fu, cl, tw = load_ref(a, b)
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))
    cls = np.array(sorted(cl))
    clv = np.array([cl[k] for k in cls])
    rows = []
    for (fam, st), g in F.groupby(["fam", "st"]):
        L = 900 if fam == "15m" else 300
        slug = f"btc-updown-{fam}-{st}"
        K = tw.get(st)
        tg = tch[tch.w == slug].sort_values("s")
        if K is None or not len(tg):
            continue
        K_f = ms_sec[np.searchsorted(sec, st - 60):np.searchsorted(sec, st)].mean()
        ts_, bb_, ba_ = tg.s.to_numpy(), tg.bb.to_numpy(), tg.ba.to_numpy()
        e, ef, mids = [], [], []
        for t in range(st + 5, st + L - 30):
            T = t * 1000
            i = np.searchsorted(ts_, T, side="right") - 1
            k = np.searchsorted(cls, (T - D_CL) // 1000, side="right") - 1
            if i < 0 or k < 0 or t < a or t >= b:
                continue
            jj = np.searchsorted(sec, t)
            sig = np.std(r1[max(jj - 300, 0):jj]) * 1.4
            if not sig > 0:
                continue
            tau = st + L - t
            mid = (bb_[i] + ba_[i]) / 2
            e.append(norm.cdf(np.log(clv[k] / K) / (sig * np.sqrt(tau))) - mid)
            fmid = fm[max(np.searchsorted(fs, T, side="right") - 1, 0)]
            ef.append(norm.cdf(np.log(fmid / K_f) / (sig * np.sqrt(tau))) - mid)
            mids.append(mid)
        if len(e) < 30:
            continue
        up_share = float(g.shares[g.up == 1].sum() / g.shares.sum())
        wcl = float(np.average(g.e_cl, weights=g.shares))
        rows.append(dict(fam=fam, st=st, up_share=up_share, n_fills=len(g), e_mean=float(np.mean(e)), ef_mean=float(np.mean(ef)),
                         mid_mid=float(mids[len(mids) // 2]), e_at_fills=wcl))
    W = pd.DataFrame(rows)
    one = W[(W.up_share >= 0.7) | (W.up_share <= 0.3)].copy()
    y = one.up_share >= 0.7
    out = {"windows": int(len(W)), "one_sided_windows": int(len(one)), "one_sided_share": round(float(len(one) / max(len(W), 1)), 3)}
    for nm, pred in (("public_mean_chainlink_edge", one.e_mean > 0), ("at_fill_times_chainlink_edge", one.e_at_fills > 0),
                     ("mean_futures_edge", one.ef_mean > 0), ("cheaper_side_mid_life", one.mid_mid < 0.5), ("always_up", pd.Series(True, index=one.index))):
        out[nm] = round(float((pred.to_numpy() == y.to_numpy()).mean()), 3)
    out["per_family_public"] = {f: [round(float(((g.e_mean > 0) == (g.up_share >= 0.7)).mean()), 3), int(len(g))] for f, g in one.groupby("fam")}
    (HERE.parent / "results" / f"iter8_window_side_{a}_{b}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
