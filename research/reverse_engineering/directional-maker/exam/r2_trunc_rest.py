"""Examiner round 2: parts (3) price and (4) selection of the truncation test (r2_trunc.py crashed on a float32 setitem in
part 3 after parts (1) and (2) had finished and been logged). Same definitions as r2_trunc.py, seed 20261102 for the
samples; parts (1)-(2) are copied from the run's log (.cache/exam/directional-maker/trunc.log)."""
from __future__ import annotations

import ast
import json

import numpy as np
import pandas as pd

from r2_common import CLUSTER, EXC, RES

from features2 import Spot, fair_up  # noqa: E402

EV = EXC / "ev"


def same(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return (a == b) | (np.isnan(a) & np.isnan(b))


def main():
    res = {}
    for line in (EXC / "trunc.log").read_text(errors="ignore").splitlines():
        if line.startswith("presence {"):
            res["presence"] = ast.literal_eval(line[len("presence "):line.rindex("}") + 1])
        if line.startswith("side {"):
            res["side_r8c"] = ast.literal_eval(line[len("side "):line.rindex("}") + 1])
    rng = np.random.default_rng(20261102)
    w = pd.read_parquet(EV / "w5.parquet")
    w["up_token"], w["down_token"] = w["up_token"].astype(str), w["down_token"].astype(str)
    clean = pd.read_parquet(EV / "clean5.parquet")
    mk = pd.read_parquet(EV / "mk5.parquet")
    spd = pd.read_parquet(EV / "spot_btc.parquet")
    sec_all, px_all = spd["sec"].to_numpy(), spd["px"].to_numpy()
    upset = set(w.up_token)
    tok2cid = {**dict(zip(w.up_token, w.cid)), **dict(zip(w.down_token, w.cid))}
    c2 = clean.merge(w[["cid", "up_token"]], on="cid")
    c2["up_px"] = np.where(c2["asset"].astype(str) == c2["up_token"], c2["price"], 1 - c2["price"]).astype(float)
    by = {c: g.sort_values("ts", kind="stable") for c, g in c2.groupby("cid")}
    pick = rng.choice(len(mk), size=min(300, len(mk)), replace=False)
    pr = {"n": 0, "trunc_mismatch": 0, "corrupt_mismatch": 0, "control_mismatch": 0}
    for k in pick:
        r = mk.iloc[k]
        g = by.get(tok2cid.get(str(r.token_id)))
        if g is None:
            continue
        b = int(r.ts)

        def pred(gg, cut=b):
            ts_, pu = gg["ts"].to_numpy(), gg["up_px"].to_numpy()
            i = np.searchsorted(ts_, cut, side="left") - 1
            return None if i < 0 else round((pu[i] if str(r.token_id) in upset else 1 - pu[i]) - 0.01, 2)
        f = pred(g)
        if f is None:
            continue
        pr["n"] += 1
        pr["trunc_mismatch"] += int(pred(g[g["ts"] < b]) != f)
        gc = g.copy()
        m = (gc["ts"] >= b).to_numpy()
        gc.loc[m, "up_px"] = rng.uniform(0.01, 0.99, int(m.sum()))
        pr["corrupt_mismatch"] += int(pred(gc) != f)
        pr["control_mismatch"] += int(pred(g[g["ts"] < b - 1], b - 1) != f)
    res["price_block_clock"] = pr
    sel = {"n": 0, "dq_last_mismatch": 0, "fair_p_mismatch": 0, "fair_p_mismatch_first_2s": 0}
    te = pd.concat([pd.read_parquet(f) for f in sorted(EV.glob("sel_te_*.parquet"))], ignore_index=True)
    mk_tx = set(pd.read_pickle(EV / "sel_mk_tx.pkl"))
    tk = pd.concat([pd.read_parquet(f) for f in EV.glob("sel_tk_*.parquet")], ignore_index=True)
    tk = tk[~tk["wallet"].str.lower().isin(set(CLUSTER))]
    tk = tk.merge(w[["cid", "up_token"]], on="cid")
    tk["up_px"] = np.where(tk["asset"].astype(str) == tk["up_token"], tk["price"], 1 - tk["price"])
    tk["cleanp"] = ~tk["tx"].isin(mk_tx)
    byt = {c: g.sort_values("ts", kind="stable") for c, g in tk.groupby("cid")}
    for k in rng.choice(len(te), size=min(300, len(te)), replace=False):
        r = te.iloc[k]
        g = byt.get(r["cid"])
        if g is None:
            continue
        g = g[(g["ts"] < r["ts"]) & g["cleanp"]]
        lu = g["up_px"].to_numpy()[-1] if len(g) else np.nan
        ls = lu if r["side_up"] == 1 else 1 - lu
        dq = np.float32(r["q"] - ls)
        ks = sec_all < int(r["ts"]) - 2
        f, _ = fair_up(Spot(sec_all[ks], px_all[ks]), np.array([r["start_ts"]]), np.array([r["end_ts"]]), np.array([r["ts"] - 2]))
        fp = np.float32(f[0] if r["side_up"] == 1 else 1 - f[0])
        sel["n"] += 1
        sel["dq_last_mismatch"] += int(not same([dq], [r["dq_last"]])[0])
        bad = not (abs(float(fp) - float(r["fair_p"])) < 1e-5 or (np.isnan(fp) and np.isnan(r["fair_p"])))
        sel["fair_p_mismatch"] += int(bad)
        sel["fair_p_mismatch_first_2s"] += int(bad and (r["ts"] - r["start_ts"]) < 2)
    res["selection_print_features"] = sel
    (RES / "exam_r2_truncation.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
