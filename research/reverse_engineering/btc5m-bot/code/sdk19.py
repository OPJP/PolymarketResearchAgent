"""Iteration 19, X197 (information panel iter18 P3 step 1): do the operator's whole-cluster restarts follow pushes to Polymarket's public
TypeScript SDK (Polymarket/ts-sdk main)?

PRE-REGISTRATION 21 (written 11-01 ~13:55 UTC, before the run). FRESH events only: whole-cluster gaps (no on-chain fill of DS / GF / XM)
of 10-20 minutes on the development days before H (the panel used the 12 gaps of >= 20 minutes; those 24 boundaries are reported
separately and not counted). Publication series: ts-sdk main commit committer times (p18i/commits_oct.json, the panel's public fetch),
merged within 2 minutes. Statistic: the number of fresh gap boundaries (last fill before, first fill after) within +0..10 minutes AFTER a
push. Null: whole-day shifts of the push series by +/-1..11 days (keeps time of day), 4,000 draws; bar p <= 0.01. Control series: the
same pushes shifted by +60 minutes (no causal link expected).
Usage: python sdk19.py SCRATCH_DIR"""
import sys, json, os
import numpy as np, pandas as pd

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
H = 1792713600


def main():
    S = sys.argv[1]
    f = pd.read_parquet(_ROOT + "/.cache/re/btc5m-bot/fills.parquet", columns=["ts", "wallet"])
    t = np.unique(np.sort(f.ts.to_numpy().astype(np.int64))); t = t[t < H]
    d = json.load(open(f"{S}/p18i/commits_oct.json", encoding="utf-8"))
    ct = np.array(sorted(pd.Timestamp(c["commit"]["committer"]["date"]).tz_convert(None).value // 10 ** 9 for c in d), np.int64)
    pushes = [ct[0]]
    for x in ct[1:]:
        if x - pushes[-1] > 120:
            pushes.append(x)
    pushes = np.array(pushes, np.int64)
    gaps = np.diff(t); i = np.where(gaps >= 600)[0]
    G = pd.DataFrame({"a": t[i], "b": t[i + 1], "len": gaps[i]})
    fresh = G[G.len < 1200]; old = G[G.len >= 1200]
    lo_span, hi_span = max(t.min(), pushes.min() - 86400 * 12), min(t.max(), pushes.max() + 86400 * 12)
    def bounds(g):
        return np.concatenate([g.a.to_numpy(), g.b.to_numpy()])
    def count(bd, ps, w=600):
        j = np.searchsorted(ps, bd, "right") - 1
        ok = j >= 0
        dt = np.where(ok, bd - ps[np.clip(j, 0, len(ps) - 1)], 10 ** 9)
        return int(((dt >= 0) & (dt <= w)).sum())
    res = {"prereg": "21", "pushes": int(len(pushes)), "push_span": [str(pd.to_datetime(pushes.min(), unit="s")), str(pd.to_datetime(pushes.max(), unit="s"))],
           "fill_span": [str(pd.to_datetime(t.min(), unit="s")), str(pd.to_datetime(t.max(), unit="s"))], "gaps_10_20min": int(len(fresh)), "gaps_ge_20min": int(len(old))}
    rng = np.random.default_rng(21)
    for nm, g in (("fresh_10_20min", fresh), ("panel_ge_20min", old)):
        bd = bounds(g)
        # only boundaries inside the push series' span (+/- 1 day)
        bd = bd[(bd >= pushes.min() - 86400) & (bd <= pushes.max() + 86400)]
        obs = count(bd, pushes)
        null = []
        for _ in range(4000):
            sh = np.sort(pushes + rng.integers(1, 12) * 86400 * rng.choice([-1, 1]))
            null.append(count(bd, sh))
        null = np.array(null)
        ctl = count(bd, np.sort(pushes + 3600))
        res[nm] = {"boundaries_in_span": int(len(bd)), "within_0_10min_after_push": obs, "null_mean": round(float(null.mean()), 3),
                   "p_one_sided": round(float(((null >= obs).sum() + 1) / (len(null) + 1)), 4), "control_shift_plus_60min": ctl,
                   "examples": [str(pd.to_datetime(x, unit="s")) for x in bd if count(np.array([x]), pushes) > 0][:8]}
    res["confirms_at_0.01"] = bool(res["fresh_10_20min"]["p_one_sided"] <= 0.01)
    print(json.dumps(res, indent=1))
    json.dump(res, open(f"{R}/sdk19.json", "w"), indent=1)


if __name__ == "__main__":
    main()
