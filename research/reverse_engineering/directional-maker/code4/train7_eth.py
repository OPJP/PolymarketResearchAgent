"""Iteration 4, family A4 (cross-asset): ETH (and SOL) Binance 1-s returns, signed by side, and their lead over BTC,
added to R3; BUILD4 fit, VALIDATE4 aggregate. Point-in-time: second k used from k+1 (Spot.last)."""
import json, sys
from pathlib import Path
import lightgbm as lgb
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[3]))
import train2 as T  # noqa
from features2 import Spot  # noqa
from train4 import load  # noqa
from train6 import add_clock, CLOCK  # noqa
from polyrea.adapters.spot import binance_seconds  # noqa
C = HERE.parents[3] / ".cache/re/directional-maker"


def spot(asset):
    f = C / f"spot_{asset}_1s_iter4.parquet"
    if not f.exists():
        rows, _ = binance_seconds(asset, 1791417600, 1793404800)
        a = np.asarray(rows)
        pd.DataFrame({"sec": a[:, 0].astype(np.int64), "px": a[:, 1]}).to_parquet(f)
    d = pd.read_parquet(f)
    return Spot(d.sec.to_numpy(), d.px.to_numpy())


def add_x(p, sp, tag):
    t = (p.start_ts + p.rel).to_numpy().astype(np.int64)
    sg = np.where(p.side_up.to_numpy() == 1, 1.0, -1.0)
    st = sp.last(t)
    p = p.copy()
    for k in (1, 3, 5, 10, 30):
        p[f"{tag}r{k}"] = (np.log(st / sp.last(t - k)) * 1e4 * sg).astype(np.float32)
    for k in (1, 3, 5):
        p[f"{tag}lead{k}"] = p[f"{tag}r{k}"] - p[f"r{k}"]
    return p


if __name__ == "__main__":
    b, v = load()
    b, v = add_clock(b), add_clock(v)
    X = []
    for a in ("eth", "sol"):
        sp = spot(a)
        b, v = add_x(b, sp, a), add_x(v, sp, a)
        X += [f"{a}r{k}" for k in (1, 3, 5, 10, 30)] + [f"{a}lead{k}" for k in (1, 3, 5)]
    act = v.groupby("cid")["y"].transform("max") > 0
    res = {}
    for nm, feats in (("R3", T.SETS["all_path_xwin"] + CLOCK), ("R3+eth_sol", T.SETS["all_path_xwin"] + CLOCK + X)):
        m = lgb.train(T.PARAMS, lgb.Dataset(b[feats], b["y"]), T.ROUNDS)
        v["p"] = m.predict(v[feats])
        res[nm] = {"auc": round(T.auc(v.y, v.p), 4), "within_active": round(T.auc(v.y[act], v.p[act]), 4), "side": round(T.side_metrics(v, "p")["acc"], 4)}
        print(nm, res[nm], flush=True)
    (HERE.parent / "results" / "iter4_train7_eth_sol.json").write_text(json.dumps(res, indent=1))
