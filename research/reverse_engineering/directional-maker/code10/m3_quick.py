"""Iteration 10 (M3 = X94, light form): do mo-money's off-posture 500 rungs sit closer to the touch than the other wallets'?
Unit: the iteration-6 confirmed filled exact-500 orders of 10-31 14:04-16:13 (raw-book add ms, price, at-touch flag at the
add, improve flag, previous touch). Posture at the add as in code9/posture_at_add.py (frozen sigma). Per wallet x posture
side: share posted at the touch, share that improved the touch, (price - Up-equivalent mid) in ticks. Filled orders are
selected on being filled, so this is descriptive only (the survival test needs unfilled adds)."""
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

C = ROOT / ".cache/re/directional-maker"
a, b = 1793455600, 1793463203


def main():
    Q = pd.read_parquet(C / "it6" / f"confirmed_{a}_{b}.parquet")
    Q = Q[Q.found & np.isclose(Q.S, 500)].drop_duplicates(["wallet", "ms", "add_s"]).copy()
    tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
    fu, cl, tw = load_ref(a, b)
    sp = pd.read_parquet(C / "it9" / "spot1s_rest_1793440800_1793469600.parquet").sort_values("sec")
    b0 = int(sp.sec.iloc[0])
    px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan)
    px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    rr = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(rr * rr)]
    tg = {w: g.sort_values("s") for w, g in tch.groupby("w")}
    rows = []
    for r in Q.itertuples(index=False):
        st = int(r.slug.rsplit("-", 1)[1])
        L = 900 if "-15m-" in r.slug else 300
        K = tw.get(st)
        g = tg.get(r.slug)
        t = int(r.add_s)
        c = cl.get((t - 1432) // 1000)
        if K is None or g is None or c is None:
            continue
        ts_, bb_, ba_ = g.s.to_numpy(), g.bb.to_numpy(), g.ba.to_numpy()
        i = np.searchsorted(ts_, t, side="left") - 1
        if i < 0:
            continue
        k = t // 1000 - 1 - b0
        sg = 1.4 * np.sqrt((cs[k + 1] - cs[k + 1 - 300]) / 300)
        tau = max(st + L - t / 1000, 1.0)
        fair = norm.cdf(np.log(c / K) / (sg * np.sqrt(tau)))
        mid = (bb_[i] + ba_[i]) / 2
        up = int(r.side == 1)
        on = int((fair > mid) == bool(up))
        mid_tok = mid if up else 1 - mid
        rows.append((r.wallet, on, bool(r.at_touch), bool(r.improve), (r.p - mid_tok) / 0.01, abs(fair - mid)))
    D = pd.DataFrame(rows, columns=["wallet", "on_posture", "at_touch", "improve", "px_minus_mid_ticks", "gap"])
    out = {"n": int(len(D))}
    for (w, on), g in D.groupby(["wallet", "on_posture"]):
        out[f"{w}|{'on' if on else 'off'}"] = {"n": int(len(g)), "at_touch": round(float(g.at_touch.mean()), 3), "improve": round(float(g.improve.mean()), 3),
                                               "px_minus_mid_ticks_median": round(float(g.px_minus_mid_ticks.median()), 2), "gap_median": round(float(g.gap.median()), 3)}
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_m3_quick.json", "w"), indent=1)


if __name__ == "__main__":
    main()
