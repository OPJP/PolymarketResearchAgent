"""Iteration 10 (M2 = X93): the ladder as a time-left phase machine. Live 10-31 12:00-18:00 (development) match-clock
fills (it9/side_D: 2,244 BTC 5m/15m fills with the match ms, the book mid, the Chainlink report and the Gamma strike).
Phases by time left tau (BTC 5m): >= 120 s, 60-120 s, 30-60 s, < 30 s; BTC 15m: >= 120 s, < 120 s.
Candidate fairs, pre-registered before scoring (23:00 UTC): (f) frozen 1.4 x v300; (s) slow v3600 x 1; (l) TWAP lock-in
digital: the settlement is the 60-s TWAP, so for tau > 60 the variance is sigma^2 (tau - 40) (frozen sigma), for tau <= 60
the observed part of the TWAP is fixed: mean = (sum of observed reports + (60 - observed) x CL) / 60, sd = sigma tau^1.5
/ (sqrt(3) x 60). Rule: per phase, the candidate with the best accuracy on 12-15 UTC; scored on 15-18 UTC (aggregate),
per wallet and pooled, against the frozen rule."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import cl_source  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
NAME = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
        "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}


def main():
    d = pd.read_parquet(C / "it9/side_D_1793448000_1793469600.parquet").dropna(subset=["cl", "K"]).copy()
    sp = pd.read_parquet(C / f"it9/spot1s_rest_{1793448000 - 7200}_{1793469600}.parquet").sort_values("sec").set_index("sec").px
    lr = np.log(sp).diff()
    v300 = np.sqrt((lr ** 2).rolling(300).mean())
    v3600 = np.sqrt((lr ** 2).rolling(3600, min_periods=1800).mean())
    tsec = (d["T"] // 1000).astype(np.int64)
    d["v300"] = (tsec - 1).map(v300).to_numpy()
    d["v3600"] = (tsec - 1).map(v3600).to_numpy()
    d["tau"] = np.maximum(d.en - d["T"] / 1000.0, 1.0)
    d["fam"] = np.where(d.en - d.st == 900, "15m", "5m")
    stamp = ((d["T"] - 1432) // 1000).astype(np.int64)
    # observed TWAP part for tau <= 60: reports stamped in [en - 61, stamp] (settlement averages [end-61, end-2])
    need = set()
    for s_, e_, t_ in zip(stamp, d.en, d.tau):
        if t_ <= 62:
            need.update(range(int(e_) - 61, int(s_) + 1))
    clv = cl_source.cl_values(sorted(need), fetch=False) if need else pd.Series(dtype=float)
    x_f, x_l = [], []
    for r, s_ in zip(d.itertuples(index=False), stamp):
        sig = 1.4 * r.v300
        if r.tau > 60:
            x_l.append(np.log(r.cl / r.K) / (sig * np.sqrt(r.tau - 40)))
        else:
            obs = [clv.get(k, np.nan) for k in range(int(r.en) - 61, int(s_) + 1)]
            obs = [o for o in obs if np.isfinite(o)]
            n_obs = len(obs)
            mean = (sum(obs) + (60 - n_obs) * r.cl) / 60.0 if n_obs <= 60 else np.mean(obs)
            sd = sig * max(r.tau, 1.0) ** 1.5 / (np.sqrt(3) * 60.0)
            x_l.append(np.log(mean / r.K) / max(sd, 1e-9))
    d["f_f"] = norm.cdf(np.log(d.cl / d.K) / (1.4 * d.v300 * np.sqrt(d.tau)))
    d["f_s"] = norm.cdf(np.log(d.cl / d.K) / (d.v3600 * np.sqrt(d.tau)))
    d["f_l"] = norm.cdf(np.array(x_l))
    y = d.is_up.to_numpy() == 1

    def phase(r_tau, fam):
        if fam == "15m":
            return "15m_ge120" if r_tau >= 120 else "15m_lt120"
        return "5m_ge120" if r_tau >= 120 else ("5m_60_120" if r_tau >= 60 else ("5m_30_60" if r_tau >= 30 else "5m_lt30"))

    d["ph"] = [phase(t_, f_) for t_, f_ in zip(d.tau, d.fam)]
    d["half"] = np.where(d["T"] < 1793458800 * 1000, "fit_12_15", "test_15_18")
    out = {"n": int(len(d))}
    tab = {}
    for (ph, hf), g in d.groupby(["ph", "half"]):
        yy = g.is_up.to_numpy() == 1
        tab.setdefault(ph, {})[hf] = {"n": int(len(g)), **{c: float(np.mean((g[f"f_{c}"].to_numpy() > g.mid_up.to_numpy()) == yy)) for c in ("f", "s", "l")}}
    out["by_phase"] = tab
    choice = {ph: max(("f", "s", "l"), key=lambda c: v.get("fit_12_15", {}).get(c, -1)) for ph, v in tab.items()}
    out["chosen_on_12_15"] = choice
    d["pred"] = [(getattr(r, f"f_{choice[r.ph]}") > r.mid_up) for r in d.itertuples(index=False)]
    d["pred_f"] = d.f_f > d.mid_up
    te = d[d.half == "test_15_18"]
    yt = te.is_up.to_numpy() == 1
    out["test_15_18"] = {"phase_rule": float(np.mean(te.pred.to_numpy() == yt)), "frozen": float(np.mean(te.pred_f.to_numpy() == yt)), "n": int(len(te)),
                         "per_wallet_phase_rule": {NAME[w]: float(np.mean((g.pred.to_numpy()) == (g.is_up.to_numpy() == 1))) for w, g in te.groupby("wallet")},
                         "per_wallet_frozen": {NAME[w]: float(np.mean((g.pred_f.to_numpy()) == (g.is_up.to_numpy() == 1))) for w, g in te.groupby("wallet")}}
    out["per_wallet_phase_accuracy_frozen_all"] = {NAME[w]: {ph: [int(len(gg)), float(np.mean((gg.pred_f.to_numpy()) == (gg.is_up.to_numpy() == 1)))] for ph, gg in g.groupby("ph")} for w, g in d.groupby("wallet")}
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_m2_phase.json", "w"), indent=1)


if __name__ == "__main__":
    main()
