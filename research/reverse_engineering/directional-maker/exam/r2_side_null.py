"""Examiner round 2: rotation null (2,000 draws) for the R8c side accuracy on lot f1.

In each draw every BTC 5m window takes the reference path (Chainlink report, priceToBeat and 300-s Binance vol) of the
window k_b places later in the same 2-h block (k_b != 0 per block); each fill keeps its own market mid at b - 3, its
offset in the window and its decided-window branch (market-only). The statistic is the per-fill accuracy of R8c.
p = (1 + #null >= obs) / (n + 1), one-sided. Also reported per half."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import norm

from r2_common import EXC, RES

from features2 import Spot  # noqa: E402
from r2_metrics import chainlink_series, ptb_of  # noqa: E402

EV = EXC / "ev"
CUT = json.loads((RES / "exam_r2_step0.json").read_text())["cut_ts"]


def main():
    S = pd.read_parquet(EXC / "side_fills.parquet")
    w = pd.read_parquet(EV / "w5.parquet").sort_values("start_ts").reset_index(drop=True)
    sp_d = pd.read_parquet(EV / "spot_btc.parquet")
    sp = Spot(sp_d["sec"].to_numpy(), sp_d["px"].to_numpy())
    cl, _ = chainlink_series()
    ptb = ptb_of(w)
    w["blk"] = (w.start_ts // 7200).astype(int)
    st_of = dict(zip(w.cid, w.start_ts))
    y = S.is_up.to_numpy() == 1
    dec = (S.mid - 0.5).abs().to_numpy() > 0.4
    cheap = S.mid.to_numpy() < 0.5
    off = (S.ts - S.st).to_numpy()
    obs = float(np.mean(S.r8c.to_numpy() == y))

    def posture(cid_partner, idx):
        s2 = np.array([st_of[c] for c in cid_partner])
        b2 = s2 + off[idx]
        clv = np.array([cl.get(int(t - 4), np.nan) for t in b2])
        K = np.array([ptb.get(int(s), np.nan) for s in s2])
        sig = np.array([float(sp.sigma(np.array([t - 2]), look=300)[0]) for t in b2]) * 1.4
        tau = np.maximum(s2 + 300 - (b2 - 2.285), 1.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            f = norm.cdf(np.log(clv / K) / (sig * np.sqrt(tau)))
        return np.where(np.isfinite(f), f > S.mid.to_numpy()[idx], cheap[idx])
    # precompute every (fill, partner) decision
    blocks = {b: g.cid.tolist() for b, g in w.groupby("blk")}
    pos_in = {c: (b, i) for b, cs in blocks.items() for i, c in enumerate(cs)}
    fills_of = S.groupby("cid").indices
    pre = {}
    for b, cs in blocks.items():
        n = len(cs)
        for i, c in enumerate(cs):
            idx = fills_of.get(c)
            if idx is None:
                continue
            for k in range(1, n):
                c2 = cs[(i + k) % n]
                pre[(c, k)] = (idx, posture([c2] * len(idx), idx))
    rng = np.random.default_rng(77)
    half = (S.st.to_numpy() < CUT)
    null, null_e, null_l = [], [], []
    for _ in range(2000):
        pred = np.where(dec, cheap, False).astype(bool)
        for b, cs in blocks.items():
            kb = int(rng.integers(1, len(cs)))
            for c in cs:
                v = pre.get((c, kb))
                if v is not None:
                    pred[v[0]] = np.where(dec[v[0]], cheap[v[0]], v[1])
        hit = pred == y
        null.append(hit.mean()); null_e.append(hit[half].mean()); null_l.append(hit[~half].mean())
    null, null_e, null_l = map(np.array, (null, null_e, null_l))
    hit0 = S.r8c.to_numpy() == y
    out = {"n": int(len(S)), "obs": obs, "null_mean": float(null.mean()), "null_sd": float(null.std(ddof=1)), "null_max": float(null.max()),
           "p": float((1 + np.sum(null >= obs)) / 2001),
           "early": {"obs": float(hit0[half].mean()), "null_mean": float(null_e.mean()), "p": float((1 + np.sum(null_e >= hit0[half].mean())) / 2001)},
           "late": {"obs": float(hit0[~half].mean()), "null_mean": float(null_l.mean()), "p": float((1 + np.sum(null_l >= hit0[~half].mean())) / 2001)},
           "n_draws": 2000}
    (RES / "exam_r2_side_null.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
