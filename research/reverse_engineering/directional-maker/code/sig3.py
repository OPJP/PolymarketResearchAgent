"""Iteration 3, family N1 (print signature): how well do the 0.01 price grid and the order-size signature
separate the taker prints that fill the cluster from other in-window taker prints? Descriptive, per split.

python code/sig3.py   (reads taker5m_day_*.parquet, windows_5m.parquet, activity; nothing at or after H)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from panel2 import OUT, WALLETS, H, cluster_trades  # noqa: E402

VAL0 = 1792108800
SIG_SIZES = (500.0, 250.0, 125.0, 498.0, 502.0, 1000.0, 333.0)


def on_grid(x, tol=2e-4):
    x = np.asarray(x, dtype=float)
    return np.abs(x * 100 - np.round(x * 100)) < tol * 100


def main():
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[w["end_ts"] <= H]
    ct = cluster_trades()
    cw = set(WALLETS.values())
    mk_tx = set(ct["tx"])
    rows = []
    for f in sorted(OUT.glob("taker5m_day_*.parquet")):
        d = int(f.stem.split("_")[-1])
        tk = pd.read_parquet(f, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])
        tk = tk[~tk["wallet"].isin(cw)].merge(w[["cid", "start_ts", "end_ts", "up_token"]], on="cid")
        tk = tk[(tk["ts"] >= tk["start_ts"]) & (tk["ts"] < tk["end_ts"])]
        y = tk["tx"].isin(mk_tx).to_numpy()
        is_up = tk["asset"].to_numpy() == tk["up_token"].to_numpy()
        buy = tk["side"].astype(str).to_numpy() == "BUY"
        px = tk["price"].to_numpy().astype(float)
        up_px = np.where(is_up, px, 1 - px)
        hit_up = (is_up & ~buy) | (~is_up & buy)
        q = np.where(hit_up, up_px, 1 - up_px)
        sz = tk["size"].to_numpy().astype(float)
        g = on_grid(q)
        sig = np.isin(np.round(sz, 2), SIG_SIZES)
        r5 = on_grid(sz / 500.0 * 5.0 / 5.0 * 0.01 * 100, 1e-6)  # placeholder (unused)
        rnd = np.abs(sz - np.round(sz)) < 1e-6
        mult5 = rnd & (np.round(sz) % 5 == 0)
        rows.append(pd.DataFrame({"d": d, "y": y, "grid": g, "sig": sig, "int": rnd, "m5": mult5, "taker_buy": buy}))
    a = pd.concat(rows, ignore_index=True)
    out = {}
    for name, part in (("build", a[a["d"] < VAL0]), ("validate", a[a["d"] >= VAL0])):
        r = {"n": int(len(part)), "pos": int(part["y"].sum()), "base": float(part["y"].mean())}
        for c in ("grid", "sig", "int", "m5", "taker_buy"):
            pp = part[part[c]]
            r[c] = {"share_of_pos": float(part.loc[part["y"], c].mean()), "share_of_neg": float(part.loc[~part["y"], c].mean()),
                    "p_y_given": float(pp["y"].mean()) if len(pp) else None,
                    "lift": float(pp["y"].mean() / part["y"].mean()) if len(pp) else None}
        out[name] = r
    print(json.dumps(out, indent=1))
    (HERE.parent / "results_iter3_signature.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
