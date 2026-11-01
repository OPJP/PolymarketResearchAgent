"""Iteration 9 (X83 / X84 groundwork): does the posture side rule describe the cluster's BTC hourly fills (Binance-settled:
Up iff the 1-h candle closes >= its open) on the block clock? Every cluster BUY fill (activity; all roles) in the 334
hourly markets of 10-16..10-30 (fam/ tapes): Up iff Phi(ln(S/K)/(k sigma sqrt(tau))) > mid_up, S = Binance spot second
b-3, K = Binance spot at the hour start (candle open), mid_up = last clean print at ts <= b-3, sigma = v300 x 1.4
(frozen) or v3600 (slow). BUILD 10-16..22 and STUDY 10-23..26 per split; VALIDATE 10-27..30 aggregate only."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"
SPL = {"build": (1792108800, 1792713600), "study": (1792713600, 1793059200), "validate": (1793059200, 1793404800)}


def main():
    a = pd.read_parquet(C / "spot_btc_1s.parquet")
    b = pd.read_parquet(C / "exam" / "spot_btc_1s.parquet")
    s = pd.concat([a, b]).drop_duplicates("sec").sort_values("sec")
    base = int(s.sec.iloc[0])
    px = np.full(int(s.sec.iloc[-1]) - base + 1, np.nan)
    px[s.sec.to_numpy() - base] = s.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    rr = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(rr * rr)]
    mk = pd.read_parquet(C / "fam" / "btc_hourly_markets.parquet")
    T = pd.read_parquet(C / "fam" / "btc_hourly_tapes.parquet")
    parts = []
    for n in ("bosona", "almach", "momoney"):
        for p in (C / f"activity_{n}.parquet", C / "exam" / f"activity_{n}.parquet"):
            parts.append(pd.read_parquet(p, columns=["timestamp", "type", "conditionId", "asset", "side", "outcome", "price", "size", "transactionHash"]))
    act = pd.concat(parts).drop_duplicates()
    act = act[act.type == "TRADE"]
    cl_tx = set(act.transactionHash.str.lower())
    T = T[~T.tx.str.lower().isin(cl_tx)].sort_values("ts")
    fills = act[(act.side == "BUY") & act.conditionId.isin(set(mk.conditionId))].copy()
    info = mk.set_index("conditionId")
    rows = []
    for cid, g in fills.groupby("conditionId"):
        st, en = int(info.loc[cid, "st"]), int(info.loc[cid, "en"])
        tp = T[T.cid == cid]
        if not len(tp):
            continue
        up_tok = None
        for o, a_ in zip(g.outcome, g.asset):
            if str(o).lower() == "up":
                up_tok = str(a_)
                break
        if up_tok is None:
            continue
        pts = tp.ts.to_numpy()
        pup = np.where(tp.asset.astype(str).to_numpy() == up_tok, tp.price.to_numpy(float), 1 - tp.price.to_numpy(float))
        K = px[st - 1 - base]
        for r in g.itertuples(index=False):
            bs = int(r.timestamp)
            j = np.searchsorted(pts, bs - 3, side="right") - 1
            if j < 0 or bs < st or bs >= en:
                continue
            i = bs - 3 - base
            tau = max(en - (bs - 2), 1.0)
            x = np.log(px[i] / K)
            v300 = np.sqrt((cs[i + 1] - cs[i + 1 - 300]) / 300)
            v3600 = np.sqrt((cs[i + 1] - cs[i + 1 - 3600]) / 3600)
            rows.append(dict(b=bs, is_up=int(str(r.outcome).lower() == "up"), mid=float(pup[j]), x=x, tau=tau, v300=v300, v3600=v3600,
                             usd=float(r.price) * float(r.size)))
    D = pd.DataFrame(rows)
    out = {}
    for sp_, (lo, hi) in SPL.items():
        g = D[(D.b >= lo) & (D.b < hi)]
        if not len(g):
            continue
        y = g.is_up.to_numpy() == 1
        m = g["mid"].to_numpy()
        st_ = np.sqrt(g.tau.to_numpy())
        regA = np.sign(g.x.to_numpy()) == np.sign(m - 0.5)
        frz = (norm.cdf(g.x.to_numpy() / (1.4 * g.v300.to_numpy() * st_)) > m) == y
        slw = (norm.cdf(g.x.to_numpy() / (g.v3600.to_numpy() * st_)) > m) == y
        out[sp_] = {"fills": int(len(g)), "markets": int(g.b.floordiv(3600).nunique()), "frozen": round(float(frz.mean()), 3),
                    "slow": round(float(slw.mean()), 3), "regionD_share": round(float((~regA).mean()), 3),
                    "regionD_acc": round(float(((g.x.to_numpy() > 0) == y)[~regA].mean()), 3) if (~regA).any() else None,
                    "cheaper": round(float(np.mean((m < 0.5) == y)), 3), "always_up": round(float(y.mean()), 3)}
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter9_hourly_side.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
