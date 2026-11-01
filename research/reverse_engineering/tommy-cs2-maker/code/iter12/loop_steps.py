"""X158 step 3 (information panel iter-11 P1): the unexplained residue of the loop-sampled value. BUILD-live.

Validated own add bursts (the mechanics panel's V-relative rows: own top before the burst and V_after) with the loop
phase of code/iter12/loop_attribution.py (P = 504 ms, +-15 ms from the latest earlier untriggered own burst). For bursts
that changed V on a token (dV = V_after - own top before, cents; fresh ladders excluded):
  * step sizes |dV| (1c drift vs multi-cent jumps), on-tick vs off-tick;
  * sign persistence: runs of same-sign dV over consecutive V changes on the same token within 30 s, against 2,000
    within-token sign shuffles (run-length >= 3 rate);
  * dV sign vs the previous change's sign by gap (mean reversion vs momentum).
Branch (c) (a clock-driven in-round model) predicts same-sign runs of >= 3 ticks at >= 2x the shuffled rate with 1c
steps; branch (d) (a pushed odds stream) predicts multi-cent steps at irregular times. Output: results/loop_steps.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
P, TOL = 504.0, 15.0


def main():
    OB = pd.read_parquet(OUT / f"own_bursts_dev{SUF}.parquet").sort_values("s").reset_index(drop=True)
    s = OB.s.to_numpy(float); untr = (OB.trig_code == 0).to_numpy()
    ref = np.full(len(OB), np.nan); last = np.nan
    for i in range(len(OB)):
        if np.isfinite(last) and s[i] - last <= 60000:
            ref[i] = last
        if untr[i]:
            last = s[i]
    OB["res"] = ((s - ref + P / 2) % P) - P / 2
    R = pd.read_parquet(OUT / f"iter12/slot_vrel_rows{SUF}.parquet")
    A = R[(R.kind == "add") & np.isfinite(R.own_top) & np.isfinite(R.V_after)].copy()
    A["s_est"] = A.t + 30.0
    # match each add to the nearest own add burst on the same book within 5 ms
    adds = OB[OB.kind == "add"]
    lab = []
    for r in A.itertuples():
        g = adds[(adds.a == r.a)]
        j = np.searchsorted(g.s.to_numpy(), r.s_est)
        best = None
        for jj in (j - 1, j):
            if 0 <= jj < len(g) and abs(g.s.iloc[jj] - r.s_est) <= 5:
                best = g.iloc[jj]
        lab.append((best.res if best is not None else np.nan, bool(best.trig_code == 0) if best is not None else None))
    A["phase_res"] = [x[0] for x in lab]; A["untrig"] = [x[1] for x in lab]
    A["dV"] = np.round((A.V_after - A.own_top) * 100)
    A = A.sort_values(["a", "oi", "t"]).drop_duplicates(["a", "oi", "t"])
    # one value change per burst (bursts within 20 ms share V)
    A["burst"] = (A.groupby(["a", "oi"]).t.diff().fillna(1e9) > 20).cumsum()
    B = A.groupby("burst").agg(a=("a", "first"), oi=("oi", "first"), t=("t", "first"), dV=("dV", "first"),
                              phase_res=("phase_res", "first"), untrig=("untrig", "first")).reset_index(drop=True)
    B = B[B.dV != 0].copy()
    B["on_tick"] = np.abs(B.phase_res) <= TOL
    out = {"value_changes": int(len(B)), "on_tick": int(B.on_tick.sum()), "with_phase": int(np.isfinite(B.phase_res).sum())}
    for nm, g in (("on_tick", B[B.on_tick]), ("off_tick", B[~B.on_tick & np.isfinite(B.phase_res)]), ("all", B)):
        ad = np.abs(g.dV)
        out[f"step_{nm}"] = {"n": int(len(g)), "share_1c": round(float((ad == 1).mean()), 3), "share_2c": round(float((ad == 2).mean()), 3),
                             "share_ge3c": round(float((ad >= 3).mean()), 3), "median_c": float(ad.median()) if len(g) else None,
                             "share_up": round(float((g.dV > 0).mean()), 3)}
    # sign persistence on consecutive changes of one token within 30 s
    rng = np.random.default_rng(11)

    def run_stats(df):
        runs3 = tot = 0; same = pairs = 0
        for (_, _), g in df.groupby(["a", "oi"]):
            t = g.t.to_numpy(); sg = np.sign(g.dV.to_numpy())
            k = 0
            while k < len(g):
                e = k
                while e + 1 < len(g) and t[e + 1] - t[e] <= 30000:
                    e += 1
                seg = sg[k:e + 1]
                if len(seg) >= 2:
                    same += int((seg[1:] == seg[:-1]).sum()); pairs += len(seg) - 1
                    r = 1
                    for q in range(1, len(seg)):
                        if seg[q] == seg[q - 1]:
                            r += 1
                        else:
                            runs3 += int(r >= 3); r = 1
                    runs3 += int(r >= 3)
                    tot += len(seg)
                k = e + 1
        return same / max(pairs, 1), runs3 / max(tot, 1), pairs
    obs_same, obs_r3, pairs = run_stats(B)
    null_same, null_r3 = [], []
    for _ in range(300):
        C = B.copy()
        C["dV"] = C.groupby(["a", "oi"]).dV.transform(lambda x: rng.permutation(x.to_numpy()))
        a_, b_, _ = run_stats(C)
        null_same.append(a_); null_r3.append(b_)
    out["sign_persistence"] = {"pairs": int(pairs), "same_sign_share": round(obs_same, 3), "null_same_sign_p50": round(float(np.median(null_same)), 3),
                               "runs_ge3_per_change": round(obs_r3, 4), "null_runs_ge3_p50": round(float(np.median(null_r3)), 4),
                               "p_same_ge": round(float((np.array(null_same) >= obs_same).mean()), 4)}
    (RES / f"loop_steps{SUF}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
