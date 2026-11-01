"""Iteration 12, PR12-D (X114 information I11-1, first pass; also X127 / X123 change points on the whole history):
the favourite share of the cluster's BTC 5m BUY fills per 6-h block from the first trade to 2026-10-30.

Inputs: whole-history activity (it12/hist, first trade .. 10-08), activity_<w>.parquet (10-08..22), exam/activity_<w>
(the released lot 10-23..30; VALIDATE days enter only as block aggregates). Taker buys are included (activity has no
maker flag; ~10-15% of BUY rows). Realised vol per block from Binance 1-m klines (daily archive, checksum verified).
Models (fitted on blocks before 2026-09-30, scored on 10-01..30): (a) UTC weekday dummies, (b) log RV, (a+b),
(d) piecewise-constant mean with optimal-partition change points (BIC-type penalty) carried forward.
Also writes the compact BTC-crypto activity table it12/hist_btc.parquet and deletes the raw chunks (they stay in the
shared HTTP cache: fetch_history.py rebuilds them from it).
    python code12/hist_state.py
"""
import glob
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import shared_client  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
NAMES = ("almach", "bosona", "momoney")
FIT_END = 1790726400  # 2026-09-30 00:00 UTC
OOS = (1790812800, 1793404800)  # 10-01 .. 10-31
K1M = "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-{day}.zip"


def load_rows():
    comp = C / "it12" / "hist_btc.parquet"
    cols = ["timestamp", "type", "side", "outcomeIndex", "price", "size", "usdcSize", "slug", "transactionHash"]
    parts = []
    raw = sorted(glob.glob(str(C / "it12" / "hist" / "act_*.parquet")))
    if comp.exists() and not raw:
        H = pd.read_parquet(comp)
    else:
        for f in raw:
            w = Path(f).stem.split("_")[1]
            d = pd.read_parquet(f, columns=[c for c in cols if c in pd.read_parquet(f).columns])
            if d.empty:
                continue
            d = d[d.slug.fillna("").str.contains("updown|up-or-down", regex=True)]
            d["w"] = w
            parts.append(d)
        H = pd.concat(parts, ignore_index=True)
        H["tx8"] = H.transactionHash.str[2:18]
        H = H.drop(columns=["transactionHash"])
        H.to_parquet(comp, index=False)
        for f in raw:
            Path(f).unlink()
    rec = [H]
    for w in NAMES:
        for f in (C / f"activity_{w}.parquet", C / "exam" / f"activity_{w}.parquet"):
            d = pd.read_parquet(f, columns=["timestamp", "type", "side", "outcomeIndex", "price", "size", "usdcSize", "slug", "transactionHash"])
            d = d[d.slug.fillna("").str.contains("updown|up-or-down", regex=True)].copy()
            d["w"] = w
            d["tx8"] = d.transactionHash.str[2:18]
            rec.append(d.drop(columns=["transactionHash"]))
    A = pd.concat(rec, ignore_index=True).drop_duplicates(["w", "tx8", "timestamp", "price", "size", "outcomeIndex", "type"])
    A = A[A.timestamp < OOS[1]]
    return A


def rv_blocks(b0, b1):
    http = shared_client()
    out = {}
    for day0 in range(b0 // 86400 * 86400, b1, 86400):
        day = pd.to_datetime(day0, unit="s").strftime("%Y-%m-%d")
        url = K1M.format(day=day)
        try:
            body, _ = http.get_bytes(url, adapter="binance.archive", max_age=None)
            chk, _ = http.get_bytes(url + ".CHECKSUM", adapter="binance.archive", max_age=None)
        except Exception:  # noqa: BLE001
            continue
        if hashlib.sha256(body).hexdigest() != chk.decode().split()[0]:
            continue
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            k = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), header=None, usecols=[0, 4])
        t = k[0].to_numpy()
        t = np.where(t > 10 ** 14, t // 1_000_000, t // 1000)
        px = k[4].to_numpy(float)
        r = np.diff(np.log(px), prepend=np.log(px[0]))
        blk = (t // 21600) * 21600
        for b in np.unique(blk):
            m = blk == b
            out[int(b)] = float(np.sqrt(np.sum(r[m] ** 2) / max(m.sum() * 60, 1)))  # per-sqrt-second vol
    return out


def optimal_partition(y, w, pen):
    """Piecewise-constant weighted mean, exact optimal partition (O(n^2))."""
    n = len(y)
    cw = np.concatenate([[0], np.cumsum(w)])
    cy = np.concatenate([[0], np.cumsum(w * y)])
    cyy = np.concatenate([[0], np.cumsum(w * y * y)])
    F = np.full(n + 1, np.inf)
    F[0] = -pen
    last = np.zeros(n + 1, dtype=int)
    for t in range(1, n + 1):
        s = np.arange(0, t)
        W_ = cw[t] - cw[s]
        cost = (cyy[t] - cyy[s]) - (cy[t] - cy[s]) ** 2 / np.maximum(W_, 1e-12)
        tot = F[s] + cost + pen
        j = int(np.argmin(tot))
        F[t] = tot[j]
        last[t] = j
    cps = []
    t = n
    while t > 0:
        cps.append(last[t])
        t = last[t]
    return sorted(set(cps) - {0})


def main():
    A = load_rows()
    B5 = A[(A.type == "TRADE") & (A.side == "BUY") & A.slug.str.startswith("btc-updown-5m-")].copy()
    B5["blk"] = (B5.timestamp // 21600) * 21600
    B5["fav"] = (B5.price > 0.5).astype(float)
    g = B5.groupby("blk")
    Bk = pd.DataFrame({"n": g.size(), "F": g.fav.mean(), "F_size": g.apply(lambda x: float((x.fav * x["size"]).sum() / x["size"].sum()))})
    for w in NAMES:
        gw = B5[B5.w == w].groupby("blk").fav.mean()
        Bk[f"F_{w}"] = gw
    Bk = Bk[Bk.n >= 30]
    rv = rv_blocks(int(Bk.index.min()), int(Bk.index.max()) + 21600)
    Bk["rv"] = Bk.index.map(rv)
    Bk = Bk.dropna(subset=["rv"])
    t = pd.to_datetime(Bk.index.to_numpy(), unit="s")
    Bk["dow"] = t.dayofweek
    Bk["hb"] = t.hour // 6
    Bk["lrv"] = np.log(Bk.rv)
    fit = Bk.index < FIT_END
    oos = (Bk.index >= OOS[0]) & (Bk.index < OOS[1])
    res = {"first_block": str(pd.to_datetime(Bk.index.min(), unit="s")), "n_blocks": int(len(Bk)), "n_fit": int(fit.sum()), "n_oos": int(oos.sum()),
           "fills": int(Bk.n.sum())}

    def design(df, kind):
        X = [np.ones(len(df))]
        if "a" in kind:
            for d in range(1, 7):
                X.append((df.dow == d).astype(float).to_numpy())
        if "b" in kind:
            X.append(df.lrv.to_numpy())
        if "h" in kind:
            for h in range(1, 4):
                X.append((df.hb == h).astype(float).to_numpy())
        return np.column_stack(X)

    y = Bk.F.to_numpy()
    wts = np.sqrt(Bk.n.to_numpy())
    models = {}
    for kind in ("const", "a", "b", "ab", "abh"):
        Xf, Xo = design(Bk[fit], kind), design(Bk[oos], kind)
        beta, *_ = np.linalg.lstsq(Xf * wts[fit][:, None], y[fit] * wts[fit], rcond=None)
        po = Xo @ beta
        ss_res = float(np.sum((y[oos] - po) ** 2))
        ss_tot = float(np.sum((y[oos] - y[oos].mean()) ** 2))
        pf = Xf @ beta
        models[kind] = {"oos_r2": round(1 - ss_res / ss_tot, 4), "fit_r2": round(1 - float(np.sum((y[fit] - pf) ** 2) / np.sum((y[fit] - y[fit].mean()) ** 2)), 4),
                        "beta": [round(float(b), 4) for b in beta]}
    res["models"] = models
    # change points on the whole series (blocks in time order), penalty = 3 x var x log(n)
    order = np.argsort(Bk.index.to_numpy())
    yy, ww = y[order], Bk.n.to_numpy()[order].astype(float)
    ww = ww / ww.mean()
    var = float(np.var(yy))
    for pen_k in (2.0, 4.0):
        cps = optimal_partition(yy[fit[order]], ww[fit[order]], pen_k * var * np.log(fit.sum()))
        res[f"cp_fit_pen{pen_k}"] = [str(pd.to_datetime(Bk.index.to_numpy()[order][fit[order]][c], unit="s")) for c in cps]
        # carried-forward last level as the OOS forecast
        last_lvl = float(np.average(yy[fit[order]][cps[-1]:] if cps else yy[fit[order]], weights=ww[fit[order]][cps[-1]:] if cps else ww[fit[order]]))
        ss_res = float(np.sum((y[oos] - last_lvl) ** 2))
        ss_tot = float(np.sum((y[oos] - y[oos].mean()) ** 2))
        res[f"d_pen{pen_k}_oos_r2"] = round(1 - ss_res / ss_tot, 4)
    cps_all = optimal_partition(yy, ww, 4.0 * var * np.log(len(yy)))
    res["cp_all_pen4"] = [str(pd.to_datetime(Bk.index.to_numpy()[order][c], unit="s")) for c in cps_all]
    seg_ss = 0.0
    bounds = [0] + cps_all + [len(yy)]
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg_ss += float(np.sum(ww[a:b] * (yy[a:b] - np.average(yy[a:b], weights=ww[a:b])) ** 2))
    res["cp_all_share_of_var_explained"] = round(1 - seg_ss / float(np.sum(ww * (yy - np.average(yy, weights=ww)) ** 2)), 4)
    # weekday profile by period and the Monday step net of RV (model ab coefficients)
    prof = {}
    per = {"may_jul": (0, 1785542400), "aug_sep": (1785542400, 1790812800), "oct": (1790812800, OOS[1])}
    for nm, (a, b) in per.items():
        m = (Bk.index >= a) & (Bk.index < b)
        prof[nm] = {int(d): round(float(np.average(Bk.F[m & (Bk.dow == d)], weights=Bk.n[m & (Bk.dow == d)])), 3) for d in range(7) if (m & (Bk.dow == d)).sum() > 0}
        prof[nm]["corr_F_lrv"] = round(float(np.corrcoef(Bk.F[m], Bk.lrv[m])[0, 1]), 3) if m.sum() > 5 else None
    res["weekday_profile_0Mon"] = prof
    # per-wallet synchrony: correlation of the wallets' block F
    res["wallet_corr"] = Bk[[f"F_{w}" for w in NAMES]].corr().round(3).to_dict()
    # daily series for the record (VALIDATE days as daily aggregates)
    day = B5.groupby(B5.timestamp // 86400 * 86400).fav.mean()
    res["daily_F"] = {str(pd.to_datetime(d, unit="s").date()): round(float(v), 3) for d, v in day.items()}
    Bk.to_parquet(C / "it12" / "hist_blocks.parquet")
    (HERE.parent / "results" / "iter12_hist_state.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "daily_F"}, indent=1))


if __name__ == "__main__":
    main()
