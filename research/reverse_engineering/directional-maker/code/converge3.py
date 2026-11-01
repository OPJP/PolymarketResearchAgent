"""Iteration 3, family N7 (mechanism, descriptive): after a cluster maker BUY fill on side s at price q, does the
market (last clean print on s) move toward the cluster while Binance does not (the market catching up with a
spot-based fair value), or does Binance move (information about spot)? Control: other makers' fills = clean
bid-hit prints on s (taker sells s or buys the complement), at their implied maker price.
Uses future prints/spot only to DESCRIBE what happens after a fill (never as a feature). Nothing at or after H.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up  # noqa: E402
from panel2 import OUT, WALLETS, H, cluster_trades  # noqa: E402

VAL0 = 1792108800
K = (5, 15, 30, 60)


def main():
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[w["end_ts"] <= H].set_index("cid")
    fills = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
    mk = fills[(fills["role"] == "maker") & (fills["side"] == "BUY")].copy()
    ct = cluster_trades()
    ctx, cw = set(ct["tx"]), set(WALLETS.values())
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    spd = spd[spd["sec"] < H]
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    rng = np.random.default_rng(3)
    out = []
    for f in sorted(OUT.glob("taker5m_day_*.parquet")):
        d = int(f.stem.split("_")[-1])
        tk = pd.read_parquet(f, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])
        tk = tk[~(tk["tx"].isin(ctx) | tk["wallet"].isin(cw)) & (tk["ts"] < H)]
        tk = tk[tk["cid"].isin(w.index)]
        md = mk[mk["day"] == d]
        for cid, g in tk.groupby("cid", sort=False):
            win = w.loc[cid]
            o = np.argsort(g["ts"].to_numpy(), kind="stable")
            ts = g["ts"].to_numpy()[o].astype(np.int64)
            is_up = (g["asset"].to_numpy() == win["up_token"])[o]
            buy = (g["side"].astype(str).to_numpy() == "BUY")[o]
            px = g["price"].to_numpy().astype(float)[o]
            up_px = np.where(is_up, px, 1 - px)
            hit_up = (is_up & ~buy) | (~is_up & buy)
            ev = []
            m = md[md["cid"] == cid]
            for r in m.itertuples(index=False):
                ev.append((int(r.ts), r.token_id == win["up_token"], float(r.price), 1))
            inw = np.flatnonzero((ts >= win["start_ts"]) & (ts < win["end_ts"] - 60))
            if len(inw):
                pick = inw[rng.random(len(inw)) < 0.05]
                for i in pick:
                    ev.append((int(ts[i]), bool(hit_up[i]), float(up_px[i] if hit_up[i] else 1 - up_px[i]), 0))
            if not ev:
                continue
            e = pd.DataFrame(ev, columns=["t", "up", "q", "cl"])
            e = e[(e["t"] >= win["start_ts"]) & (e["t"] < win["end_ts"] - 60)]
            if not len(e):
                continue
            sg = np.where(e["up"], 1.0, -1.0)
            fu0, _ = fair_up(sp, np.full(len(e), win["start_ts"]), np.full(len(e), win["end_ts"]), e["t"].to_numpy())
            row = {"day": d, "cl": e["cl"].to_numpy(), "q": e["q"].to_numpy(), "f0": np.where(e["up"], fu0, 1 - fu0),
                   "won": np.where(e["up"], win["up_payout"], 1 - win["up_payout"])}
            j0 = np.searchsorted(ts, e["t"].to_numpy(), side="left") - 1
            lu0 = np.where(j0 >= 0, up_px[np.clip(j0, 0, None)], np.nan)
            row["m0"] = np.where(e["up"], lu0, 1 - lu0)
            for k in K:
                tt = e["t"].to_numpy() + k
                fuk, _ = fair_up(sp, np.full(len(e), win["start_ts"]), np.full(len(e), win["end_ts"]), tt + 1)
                row[f"f{k}"] = np.where(e["up"], fuk, 1 - fuk)
                j = np.searchsorted(ts, tt, side="right") - 1
                lu = np.where(j >= 0, up_px[np.clip(j, 0, None)], np.nan)
                row[f"m{k}"] = np.where(e["up"], lu, 1 - lu)
            out.append(pd.DataFrame(row))
    a = pd.concat(out, ignore_index=True)
    res = {}
    for split, part in (("build", a[a["day"] < VAL0]), ("validate", a[a["day"] >= VAL0])):
        r = {}
        for cl, nm in ((1, "cluster"), (0, "other_makers")):
            x = part[part["cl"] == cl]
            rr = {"n": int(len(x)), "fair_minus_q_at_fill": float((x["f0"] - x["q"]).mean()), "won_minus_q": float((x["won"] - x["q"]).mean()),
                  "prefill_market_minus_q": float(np.nanmean(x["m0"] - x["q"])), "fair_minus_prefill_market": float(np.nanmean(x["f0"] - x["m0"]))}
            for k in K:
                rr[f"market_move_{k}s"] = float((x[f"m{k}"] - x["q"]).mean())
                rr[f"market_vs_prefill_{k}s"] = float(np.nanmean(x[f"m{k}"] - x["m0"]))
                rr[f"fair_move_{k}s"] = float((x[f"f{k}"] - x["f0"]).mean())
            r[nm] = {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in rr.items()}
        res[split] = r
    print(json.dumps(res, indent=1))
    (HERE.parent / "results_iter3_converge.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
