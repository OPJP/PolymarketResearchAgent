"""Backtest quote-pulling filters (H-A own-tape calm, H-B sibling-tape calm) on the slow
public-data maker grid. Parameters (delta, J, pause P, range cap R) chosen on FIT only by
per-market HAC t of strict-fill PnL; TEST evaluated once at latencies 1, 2, 5 s under strict and
at-touch fills. Maker rebate estimate (rebateRate * taker fee on our fills) reported separately.
"""
import json, itertools, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from common import S, load
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue

_, _, meta = load()
fees = {c: (json.loads(v) if isinstance(v, str) else v) or {} for c, v in meta["feeSchedule"].items()}
DELTAS = (0.005, 0.01, 0.02)


def pnl_frame(G, d, model):
    tag = int(d * 1000)
    parts = []
    for o in (0, 1):
        q = G[f"q_d{tag}_o{o}"].to_numpy(); sh = G[f"{model}_d{tag}_o{o}"].to_numpy(); pay = G[f"pay_o{o}"].to_numpy()
        rate = G.condition_id.map(lambda c: float(fees.get(c, {}).get("rate", 0) or 0)).to_numpy()
        rr = G.condition_id.map(lambda c: float(fees.get(c, {}).get("rebateRate", 0) or 0)).to_numpy()
        parts.append(pd.DataFrame({"condition_id": G.condition_id.to_numpy(), "usd": sh * q, "pnl": sh * (pay - q), "rebate": sh * rate * q * (1 - q) * rr}))
    return pd.concat(parts)


def score(G, mask, d, model):
    f = pnl_frame(G[mask], d, model)
    per = f.groupby("condition_id")[["usd", "pnl", "rebate"]].sum()
    per = per[per.usd > 0]
    if len(per) < 5:
        return None
    t = hac_t_test(per.pnl.to_numpy())
    t2 = hac_t_test((per.pnl + per.rebate).to_numpy())
    return {"markets": int(len(per)), "usd": float(per.usd.sum()), "pnl": float(per.pnl.sum()), "ret": float(per.pnl.sum() / per.usd.sum()),
            "rebate": float(per.rebate.sum()), "ret_with_rebate": float((per.pnl.sum() + per.rebate.sum()) / per.usd.sum()),
            "t": t.statistic, "p": t.p_value, "p_with_rebate": t2.p_value,
            "boot_p": stationary_bootstrap_pvalue(per.pnl.to_numpy(), n_boot=2000).p_value}


def masks(G, fam):
    yield {"J": 0, "P": 0, "R": None}, np.ones(len(G), bool)
    for J, P in itertools.product((3, 5, 10), (10, 30, 60, 120, 300)):
        for R in (0.02, 0.05, 1.0):
            m = (G[f"{fam}sj{J}"].to_numpy() >= P) & ((G.rng30.fillna(0).to_numpy() <= R) if fam == "" else True)
            yield ({"J": J, "P": P, "R": R if fam == "" else None}), m
        if fam != "":
            continue


out = {}
G1 = pd.read_pickle(S / "grid_lat1.pkl")
for fam, name in (("", "H-A own-tape calm"), ("sib_", "H-B sibling-tape calm")):
    Gf = G1[G1.period == "fit"]
    best, best_t, scan = None, -1e9, []
    seen = set()
    for (params, m) in masks(Gf, fam):
        key = json.dumps(params, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        for d in DELTAS:
            r = score(Gf, m, d, "strict")
            if r is None:
                continue
            scan.append({**params, "delta": d, "t": r["t"], "ret": r["ret"], "markets": r["markets"]})
            if r["t"] > best_t:
                best_t, best = r["t"], (params, d)
    params, d = best
    res = {"fit_best": {**params, "delta": d, "fit_t": best_t}, "fit_scan_top5": sorted(scan, key=lambda x: -x["t"])[:5],
           "fit_scan_n": len(scan), "test": {}}
    for lat in (1, 2, 5):
        G = pd.read_pickle(S / f"grid_lat{lat}.pkl")
        Gt = G[G.period == "test"]
        if fam == "":
            m = np.ones(len(Gt), bool) if params["J"] == 0 else (Gt[f"sj{params['J']}"].to_numpy() >= params["P"]) & (Gt.rng30.fillna(0).to_numpy() <= params["R"])
        else:
            m = np.ones(len(Gt), bool) if params["J"] == 0 else Gt[f"sib_sj{params['J']}"].to_numpy() >= params["P"]
        res["test"][str(lat)] = {"strict": score(Gt, m, d, "strict"), "at_touch": score(Gt, m, d, "touch"),
                                 "unfiltered_strict": score(Gt, np.ones(len(Gt), bool), d, "strict"),
                                 "unfiltered_at_touch": score(Gt, np.ones(len(Gt), bool), d, "touch")}
    out[name] = res
    print(name, json.dumps(res, indent=1))
json.dump(out, open(S / "backtest_filters.json", "w"), indent=1)
