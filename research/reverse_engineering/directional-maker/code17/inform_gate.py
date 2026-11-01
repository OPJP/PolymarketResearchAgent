"""iteration 17, T7 = X206 (assumptions panel P2; pre-registered in NOTES.md 11:12 UTC): does the side regime follow the
reference's recent informativeness? H_N(t) = share of the last N resolved BTC 5m windows (end + 60 <= t, |F - m| >= 0.05 at
rel 150 s) whose outcome followed the Binance fair; dependent = per 2-h block margin acc(posture) - acc(cheaper) of the
cluster's non-decided BTC 5m fills. BUILD 10-09..22 (fills_price2), lot 10-23..30 (typed_fills; VALIDATE aggregate only)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import side_sm  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
B0, B1 = 1791504000, 1792713600


def windows():
    fr = []
    for pat, lo, hi in (("panel2_day_*.parquet", B0, B1), ("exam/panel_day_*.parquet", B1, 1793404800)):
        for f in sorted(C.glob(pat)):
            d = int(f.stem.split("_")[-1])
            if lo <= d < hi:
                x = pd.read_parquet(f, columns=["cid", "start_ts", "rel", "side_up", "fair_s", "last_s", "won_s"])
                fr.append(x[(x.side_up == 1) & (x.rel == 150)])
    w = pd.concat(fr, ignore_index=True).drop_duplicates("cid").sort_values("start_ts")
    w["end"] = w.start_ts + 300
    w["inf"] = (np.abs(w.fair_s - w.last_s) >= 0.05) & np.isfinite(w.fair_s) & np.isfinite(w.last_s) & np.isfinite(w.won_s)
    w["agree"] = ((w.fair_s > w.last_s).astype(int) == w.won_s.astype(int)).astype(float)
    return w


def H(w, t, N):
    """causal: windows with end + 60 <= t, informative ones only, last N of them."""
    ww = w[w["inf"]]
    ends = ww.end.to_numpy() + 60
    ag = ww.agree.to_numpy()
    cs = np.r_[0.0, np.cumsum(ag)]
    j = np.searchsorted(ends, t, side="right")
    i = np.maximum(j - N, 0)
    n = j - i
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n >= max(6, N // 3), (cs[j] - cs[i]) / np.maximum(n, 1), np.nan)


def build_fills():
    f = pd.read_parquet(C / "fills_price2.parquet", columns=["ts", "is_up", "fair_s", "bu", "bd", "last_s", "start_ts"])
    f = f[(f.ts >= B0) & (f.ts < B1)].copy()
    lu = np.where(f.is_up, f.last_s, 1 - f.last_s)
    mid_up = np.where(np.isfinite(f.bu) & np.isfinite(f.bd), (f.bu + f.bd) / 2, lu)
    f["mid_up"] = mid_up
    f["post_up"] = np.where(f.is_up, f.fair_s > (np.where(f.is_up, mid_up, 1 - mid_up)), ~(f.fair_s > (1 - mid_up)))
    f["y"] = f.is_up.astype(bool)
    f["en"] = f.start_ts + 300
    f["st"] = f.start_ts
    return f[np.isfinite(f.mid_up) & np.isfinite(f.fair_s)]


def lot_fills():
    V = pd.read_parquet(C / "it12" / "typed_fills.parquet", columns=["st", "en", "is_up", "mid_up", "f_cl", "f_bn", "sp", "b"])
    V = V[(V.en - V.st) == 300].copy()
    mid = V.mid_up.to_numpy()
    V["post_up"] = np.where(np.isfinite(V.f_cl) & np.isfinite(mid), V.f_cl > mid, V.f_bn > mid)
    V["y"] = V.is_up == 1
    V["ts"] = V.b
    return V[np.isfinite(V.mid_up)]


def score(F, w, N, thr=None):
    F = F.copy()
    F["H"] = H(w, F.ts.to_numpy(float), N)
    dec = np.abs(F.mid_up - 0.5) > 0.4
    cheap_up = F.mid_up < 0.5
    F["post_ok"] = (F.post_up == F.y).astype(float)
    F["cheap_ok"] = (cheap_up == F.y).astype(float)
    nd = F[~dec].copy()
    nd["blk"] = (nd.ts // 7200).astype(int)
    g = nd.groupby("blk").agg(n=("post_ok", "size"), post=("post_ok", "mean"), cheap=("cheap_ok", "mean"))
    hb = H(w, (g.index.to_numpy() * 7200).astype(float), N)
    g["H"] = hb
    g = g[(g.n >= 30) & np.isfinite(g.H)]
    g["margin"] = g.post - g.cheap
    rho, p = spearmanr(g.H, g.margin) if len(g) > 5 else (np.nan, np.nan)
    out = {"blocks": int(len(g)), "spearman": round(float(rho), 3), "p": float(p), "H_median": float(np.nanmedian(nd.H))}
    if thr is not None:
        op = side_sm.nyse_open_window(F.st.to_numpy(), F.en.to_numpy())
        r8 = np.where(dec, cheap_up, F.post_up)
        r8c = np.where(op, cheap_up, r8)
        gate = np.where(dec, cheap_up, np.where(np.isfinite(F.H) & (F.H < thr), cheap_up, F.post_up))
        gate = np.where(op, cheap_up, gate)
        y = F.y.to_numpy()
        out.update({"n_fills": int(len(F)), "r8c": round(float((r8c == y).mean()), 4), "gated": round(float((gate == y).mean()), 4),
                    "share_gated_to_cheaper": round(float((~dec & np.isfinite(F.H) & (F.H < thr)).mean()), 3)})
    return out


def main():
    w = windows()
    Fb = build_fills()
    res = {"n_windows": int(len(w)), "n_informative": int(w["inf"].sum())}
    for N in (12, 36, 96):
        res[f"BUILD_N{N}"] = score(Fb, w, N)
    thr = res["BUILD_N36"]["H_median"]
    res["threshold_H36"] = thr
    ok = res["BUILD_N36"]["spearman"] >= 0.30 and res["BUILD_N36"]["p"] < 0.01
    res["build_reading_met"] = bool(ok)
    if ok:
        L = lot_fills()
        for sp in ("study", "validate"):
            res[f"{sp}_N36"] = score(L[L.sp == sp], w, 36, thr)
        res["adopt"] = bool(res["validate_N36"]["gated"] - res["validate_N36"]["r8c"] >= 0.01 and
                            res["study_N36"]["gated"] - res["study_N36"]["r8c"] >= -0.01)
    print(json.dumps(res, indent=1))
    (HERE.parent / "results" / "iter17_inform_gate.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
