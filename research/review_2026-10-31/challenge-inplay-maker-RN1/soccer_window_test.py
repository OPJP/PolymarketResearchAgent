"""H-C targeted match statistic: after an ESPN soccer goal / red card known at wallclock + D, RN1 is
absent from the touch for W seconds while other makers keep getting filled.
Statistic = share of OTHER makers' touch events in [0, W) after a known key event minus RN1's share.
D, W fitted on FIT games; TEST statistic vs 2000 shifts of each game's key-event timeline by
+-5..40 min (wrapped inside the 2.5 h game window). Also: RN1 / others touch-event shares around the
first public tape jump that follows each goal (tape-relative timing, -30..+120 s)."""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from common import S, W, implied_p0
from grid_maker import jump_times

exec(open(S / "soccer_test.py").read().split("# (c) match test")[0])  # reuse loading + touch events E, KEY, GOALS, kicks, period


def stat(df, D, Wn, shift=None):
    s = add_since(df, D, shift)
    inw = (s >= 0) & (s < Wn)
    r = df.rn1.to_numpy()
    return float(inw[~r].mean() - inw[r].mean()), float(inw[r].mean()), float(inw[~r].mean()), int(inw[r].sum())

F = E[E.period == "fit"].reset_index(drop=True); T = E[E.period == "test"].reset_index(drop=True)
scan = [{"D": D, "W": Wn, "fit_stat": stat(F, D, Wn)[0]} for D in (0, 2, 5, 10, 20, 30) for Wn in (10, 30, 60, 120, 300)]
best = max(scan, key=lambda r: r["fit_stat"])
obs, rs, os_, rn = stat(T, best["D"], best["W"])
rng = np.random.default_rng(5)
tg = T.event_slug.unique()
null = np.array([stat(T, best["D"], best["W"], {e: int(rng.integers(300, 2400) * rng.choice([-1, 1])) for e in tg})[0] for _ in range(2000)])
res = {"fit_best": best, "test_stat_others_minus_rn1_share": obs, "test_rn1_share_in_window": rs, "test_others_share_in_window": os_, "test_rn1_events_in_window": rn,
       "test_rn1_events": int(T.rn1.sum()), "test_other_events": int((~T.rn1).sum()), "null_mean": float(null.mean()), "null_p99": float(np.quantile(null, 0.99)),
       "perm_p": float((1 + (null >= obs).sum()) / (1 + len(null)))}

# timing relative to the first public tape jump after each goal (all games)
rel = []
for e in kicks:
    g = tk[tk.event_slug == e]
    jt = []
    for cid, x in g.groupby("condition_id"):
        x = x.sort_values("ts"); ts = x.ts.to_numpy().astype(np.int64)
        if len(ts) > 2:
            jt.append(jump_times(ts, implied_p0(x), 0.05, 30))
    jt = np.sort(np.concatenate(jt)) if jt else np.array([])
    ee = E[E.event_slug == e]
    for gt in GOALS[e]:
        cand = jt[(jt >= gt - 120) & (jt <= gt + 300)]
        if not len(cand):
            continue
        j0 = cand[0]
        x = ee[(ee.ts >= j0 - 60) & (ee.ts <= j0 + 180)]
        rel.append(pd.DataFrame({"dt": x.ts - j0, "rn1": x.rn1, "ret": x.ret, "cap": x.cap, "q": x.q}))
R = pd.concat(rel)
bins = [-61, -10, -3, 0, 3, 10, 30, 60, 120, 181]
R["b"] = pd.cut(R.dt, bins)
tab = R.groupby("b", observed=False).apply(lambda x: pd.Series({"others_events": int((~x.rn1).sum()), "rn1_events": int(x.rn1.sum()),
                                                               "rn1_share_of_touch_events": float(x.rn1.mean()) if len(x) else np.nan,
                                                               "others_ret_cap50": float((x[~x.rn1].cap * x[~x.rn1].ret).sum() / max(1e-9, (x[~x.rn1].cap * x[~x.rn1].q).sum()))}))
res["around_first_tape_jump_after_goal"] = {str(k): v for k, v in tab.to_dict(orient="index").items()}
res["baseline_rn1_share_all_touch_events"] = float(E.rn1.mean())
print(json.dumps(res, indent=1))
json.dump(res, open(S / "soccer_window_test.json", "w"), indent=1)
