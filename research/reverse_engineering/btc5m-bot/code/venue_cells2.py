"""Iteration 3 (c): three more reference series (Binance spot aggTrades S, Bybit spot Y, OKX spot K) and a six-series
composite (Binance futures, OKX swap, Bybit perp, Binance spot, Bybit spot, OKX spot): mean move, largest move, number
of series that moved toward / against the outcome, and the largest move since the last Polymarket print.
PIT: trades with T < (s - 1) * 1000 ms. Oriented toward the cell's outcome. NaN outside a series' archive coverage.
Writes .cache/re/btc5m-bot/cells_ven2/<day0>.parquet. Usage: python venue_cells2.py"""
import os, sys, glob
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import numpy as np, pandas as pd
from ofi import Agg
from venue_cells import venue_frame, feats_for, VWIN
C = _ROOT + "/.cache/re/btc5m-bot"
SPOT_VENUES = (("S", "bnspot"), ("Y", "bybitspot"), ("K", "okxspot"))
ALL6 = ("F", "O", "B", "S", "Y", "K")
VEN2_FEATS = [f"{p}_{k}" for p, _ in SPOT_VENUES for k in [f"pm{w}" for w in VWIN] + ["ofin1000", "ofin3000", "age_tr", "ntr1000"]] + \
             [f"C6_pm{w}" for w in (1000, 2000, 3000)] + [f"C6_mx{w}" for w in (1000, 2000, 3000)] + \
             [f"C6_nup{w}" for w in (2000, 3000)] + [f"C6_ndn{w}" for w in (2000, 3000)] + ["C6_since_mx", "C6_since_mean"]


def lp_before(agg: Agg, t_ms):
    i = np.searchsorted(agg.T, np.asarray(t_ms, np.int64), side="left") - 1
    return np.where(i >= 0, agg.lp[np.clip(i, 0, None)], np.nan)


def ven2_feats(c: pd.DataFrame, aggs: dict, pm_other: dict) -> pd.DataFrame:
    """c: start_ts, rel, is_up, age_last; aggs: {'S','Y','K','F','O','B': Agg|None}; pm_other: {(prefix, w): oriented move
    array} for F, O, B (already computed by fut_cells / venue_cells)."""
    s = c.start_ts.to_numpy(np.int64) + c.rel.to_numpy(np.int64)
    sg = np.where(c.is_up.to_numpy(), 1.0, -1.0)
    t_end = (s - 1) * 1000
    out = {}
    for p, _ in SPOT_VENUES:
        a = aggs.get(p)
        if a is None:
            for k in [f"{p}_{x}" for x in [f"pm{w}" for w in VWIN] + ["ofin1000", "ofin3000", "age_tr", "ntr1000"]]:
                out[k] = np.full(len(c), np.nan, np.float32)
        else:
            out.update(feats_for(a, t_end, sg, p))
    mv = lambda p, w: (pm_other[(p, w)] if p in ("F", "O", "B") else out[f"{p}_pm{w}"]).astype(float)
    for w in (1000, 2000, 3000):
        st = np.stack([mv(p, w) for p in ALL6], axis=1)
        out[f"C6_pm{w}"] = np.nanmean(st, axis=1).astype(np.float32)
        ab = np.where(np.isfinite(st), np.abs(st), -1.0); j = ab.argmax(1)
        out[f"C6_mx{w}"] = st[np.arange(len(st)), j].astype(np.float32)
        if w >= 2000:
            out[f"C6_nup{w}"] = np.nansum(st >= 0.3, axis=1).astype(np.float32); out[f"C6_ndn{w}"] = np.nansum(st <= -0.3, axis=1).astype(np.float32)
    # move of every series since the last Polymarket print (the quote the bot would hit was set around then)
    age = c.age_last.to_numpy(float)
    t_last = np.where(np.isfinite(age), (s - np.nan_to_num(age, nan=0.0) - 1) * 1000, 0).astype(np.int64)
    sinces = []
    for p in ALL6:
        a = aggs.get(p)
        if a is None:
            sinces.append(np.full(len(c), np.nan)); continue
        cov = (t_end - 15000 >= a.T[0]) & (t_end <= a.T[-1]) & np.isfinite(age)
        sinces.append(np.where(cov, sg * (lp_before(a, t_end) - lp_before(a, t_last)) * 1e4, np.nan))
    st = np.stack(sinces, axis=1)
    ab = np.where(np.isfinite(st), np.abs(st), -1.0); j = ab.argmax(1)
    out["C6_since_mx"] = np.where(ab.max(1) >= 0, st[np.arange(len(st)), j], np.nan).astype(np.float32)
    out["C6_since_mean"] = np.nanmean(st, axis=1).astype(np.float32)
    return pd.DataFrame(out)


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    os.makedirs(f"{C}/cells_ven2", exist_ok=True)
    for fp_ in sorted(glob.glob(f"{C}/cells/*.parquet")):
        d0 = int(os.path.basename(fp_)[:-8])
        out = f"{C}/cells_ven2/{d0}.parquet"
        if os.path.exists(out) or not os.path.exists(f"{C}/cells_ven/{d0}.parquet"):
            continue
        c = pd.read_parquet(fp_, columns=["start_ts", "rel", "is_up", "age_last"])
        F = pd.read_parquet(f"{C}/cells_fut/{d0}.parquet", columns=[f"F_pm{w}" for w in (1000, 2000, 3000)])
        Vn = pd.read_parquet(f"{C}/cells_ven/{d0}.parquet", columns=[f"{p}_pm{w}" for p in ("O", "B") for w in (1000, 2000, 3000)])
        pm_other = {("F", w): F[f"F_pm{w}"].to_numpy() for w in (1000, 2000, 3000)}
        pm_other.update({(p, w): Vn[f"{p}_pm{w}"].to_numpy() for p in ("O", "B") for w in (1000, 2000, 3000)})
        aggs = {}
        for p, v in SPOT_VENUES + (("O", "okx"), ("B", "bybit")):
            vf = venue_frame(v, d0, f"{C}/venues")
            aggs[p] = Agg(vf) if vf is not None else None
        fparts = [pd.read_parquet(f"{C}/fut/{d}.parquet") for d in (d0 - 86400, d0) if os.path.exists(f"{C}/fut/{d}.parquet")]
        aggs["F"] = Agg(pd.concat(fparts, ignore_index=True))
        V2 = ven2_feats(c, aggs, pm_other); del aggs
        V2.to_parquet(out, index=False)
        print(d0, len(V2), "nan S", round(float(np.isnan(V2.S_pm1000).mean()), 3), "nan Y", round(float(np.isnan(V2.Y_pm1000).mean()), 3),
              "nan K", round(float(np.isnan(V2.K_pm1000).mean()), 3), flush=True)
