"""Iteration 6, Q1 step 3 (X35): does the futures fair decide WHEN the cluster joins the touch?
Confirmed posting adds (code6/q1_confirmed.py) vs other makers' at-touch adds (any size; exact 500/100) in BTC 5m:
* futures bookTicker mid move over the previous 250 ms / 1 s / 3 s, signed toward the post's token;
* edge = digital fair of the token (futures mid vs the futures TWAP of [start-60, start), realised 1-s vol of the last
  300 s x 1.4, time left) minus the post price.
Development live block only (own recorder dm_bnf, server ms). python code6/q1_fair.py <start_ts> <end_ts>"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
from rawread import iter_dm  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"


def main(a, b):
    F = pd.read_parquet(C / "it6" / f"confirmed_{a}_{b}.parquet")
    F = F[F.horizon == "5m"]
    ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet")
    ev = ev[ev.w.str.contains("btc-updown-5m") & (ev.d > 0)]
    att = np.where(ev.side == 1, np.abs(ev.p - ev.bb) < 1e-6, np.abs(ev.p - ev.ba) < 1e-6)
    ev = ev[att]
    keys = set(zip(F.add_s, F.slug, F.side))
    ev = ev[[k not in keys for k in zip(ev.s, ev.w, ev.side)]]
    n_all = ev.sample(min(6000, len(ev)), random_state=3)
    n_5 = ev[ev.d.isin([500.0, 100.0])]
    n_5 = n_5.sample(min(4000, len(n_5)), random_state=4)
    fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", a - 400, b) if r["r"][0] == "b" and r["r"][2]]
    fu = pd.DataFrame(fut, columns=["s", "m"]).sort_values("s").drop_duplicates("s", keep="last")
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))

    def mid_at(t):
        i = np.searchsorted(fs, t, side="right") - 1
        return fm[i] if i >= 0 else np.nan

    def feats(t, w, side, p):
        st = int(w.split("-")[-1])
        sgn = 1 if side == 1 else -1  # side 1: bid on Up = BUY Up; side 0: ask on Up = BUY Down
        o = {}
        m0 = mid_at(t)
        for L in (250, 1000, 3000):
            o[f"mv{L}"] = sgn * (m0 - mid_at(t - L))
        k0 = np.searchsorted(sec, st - 60)
        k1 = np.searchsorted(sec, st)
        K = ms_sec[k0:k1].mean() if k1 > k0 else np.nan
        j = np.searchsorted(sec, t // 1000)
        sig = np.std(r1[max(j - 300, 0):j]) * 1.4 if j > 30 else np.nan
        tau = max(st + 300 - t / 1000, 1.0)
        fair_up = norm.cdf(np.log(m0 / K) / (sig * np.sqrt(tau))) if (K == K and sig and sig == sig) else np.nan
        tok_px = p if side == 1 else 1 - p
        fair_tok = fair_up if side == 1 else 1 - fair_up
        o["edge"] = fair_tok - tok_px
        o["tok_px"] = tok_px
        o["rel"] = t / 1000 - st
        return o

    def table(D, tcol, wcol, scol, pcol):
        return pd.DataFrame([feats(int(r[0]), r[1], int(r[2]), float(r[3])) for r in D[[tcol, wcol, scol, pcol]].itertuples(index=False)])
    A = table(F, "add_s", "slug", "side", "p")
    B = table(n_all, "s", "w", "side", "p")
    B5 = table(n_5, "s", "w", "side", "p")

    def summ(D):
        o = {"n": int(len(D))}
        for L in (250, 1000, 3000):
            v = D[f"mv{L}"].dropna()
            mv = v[v != 0]
            o[f"P_moved_{L}ms"] = round(float((v != 0).mean()), 3)
            o[f"P_toward_given_moved_{L}ms"] = round(float((mv > 0).mean()), 3) if len(mv) else None
            o[f"mean_signed_move_usd_{L}ms"] = round(float(v.mean()), 2)
        e = D.edge.dropna()
        o["edge_q"] = e.quantile([.1, .25, .5, .75, .9]).round(3).to_dict()
        o["edge_mean"] = round(float(e.mean()), 4)
        o["P_edge_gt_0.02"] = round(float((e > 0.02).mean()), 3)
        return o
    from sklearn.metrics import roc_auc_score
    lab = np.r_[np.ones(len(A)), np.zeros(len(B5))]
    out = {"period": [a, b], "confirmed_5m": summ(A), "null_at_touch_any_size": summ(B), "null_at_touch_500_100": summ(B5)}
    for col in ("edge", "mv1000", "mv3000", "mv250"):
        s = np.r_[A[col].to_numpy(), B5[col].to_numpy()]
        ok = np.isfinite(s)
        out[f"auc_confirmed_vs_500_100_null_{col}"] = round(float(roc_auc_score(lab[ok], s[ok])), 3)
    (HERE.parent / "results" / f"iter6_q1_fair_{a}_{b}.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
