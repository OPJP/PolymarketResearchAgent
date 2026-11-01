"""Iteration 14, X127 (remaining venues): Deribit BTC-PERPETUAL (London LD4) and Coinbase BTC-USD (us-east) trades on their own exchange
clocks, from the cached hourly trade files of 12 VALIDATE hours on 10-17..22 (venues/deribit, venues/coinbase; fetched in iteration 4).
Units: operator first legs (dcfit14_pred rank 0) with m0 inside those hours. (1) Univariate profile: sign of the last-price change over
[m0 - c - 250, m0 - c), c = 400 .. 100 ms (agreement on covered, coverage). (2) The late band test: among first legs, does the venue's
price change in [m0 - 230, m0 - 150) (after the Binance spot knee, before the arrival) agree with the side, and does it add to the
Binance spot sign at the knee (the dc14 frame's own-anchor spot microprice 250-ms return)? A London venue read directly would be
usable up to ~m0 - 152; a lagging relay of Binance adds nothing beyond the Binance knee. Usage: python knee14b.py FRAME_DIR"""
import os, sys, json, glob
import numpy as np, pandas as pd

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
CS = list(range(400, 90, -10))


def at(T, X, t):
    i = np.searchsorted(T, t, "left") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def main():
    D = sys.argv[1]
    P = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["cid", "up", "m0", "rank", "day"])
    F = pd.read_parquet(f"{D}/dcclock14_frame.parquet", columns=["m", "rank", "own_bs_mic_250"])
    P = P[P["rank"] == 0].reset_index(drop=True)
    F = F[F["rank"] == 0].drop_duplicates("m").set_index("m").own_bs_mic_250
    P["bs250"] = F.reindex(P.m0.to_numpy()).to_numpy()
    y = np.where(P.up.to_numpy() == 1, 1, -1)
    res = {}
    for v in ("deribit", "coinbase"):
        fs = sorted(glob.glob(f"{C}/venues/{v}/*.parquet"))
        hrs = [int(os.path.basename(f)[:-8]) for f in fs]
        T = pd.concat([pd.read_parquet(f, columns=["T", "p"]) for f in fs]).sort_values("T", kind="stable")
        Tt, pt = T["T"].to_numpy(np.int64), T.p.to_numpy(float)
        sel = np.zeros(len(P), bool)
        for h in hrs:
            sel |= (P.m0.to_numpy() >= h * 1000 + 5000) & (P.m0.to_numpy() < (h + 3600) * 1000)
        m0 = P.m0.to_numpy(np.int64)[sel]; yy = y[sel]
        prof = {}
        for c in CS:
            s = at(Tt, pt, m0 - c) - at(Tt, pt, m0 - c - 250); nz = np.isfinite(s) & (s != 0)
            prof[c] = [round(float((np.sign(s[nz]) == yy[nz]).mean()), 4) if nz.any() else None, round(float(nz.mean()), 4)]
        late = at(Tt, pt, m0 - 150) - at(Tt, pt, m0 - 230); nzl = np.isfinite(late) & (late != 0)
        bs = P.bs250.to_numpy()[sel]; bsign = np.sign(np.nan_to_num(bs))
        comb = np.where(nzl, np.sign(np.nan_to_num(late)), bsign)  # the venue's late move takes precedence where it moved
        o = {"first_legs": int(sel.sum()), "hours": len(hrs), "profile_agree_on_covered_and_coverage": prof,
             "late_band_230_150": {"coverage": round(float(nzl.mean()), 4), "agree_on_covered": round(float((np.sign(late[nzl]) == yy[nzl]).mean()), 4) if nzl.any() else None},
             "binance_spot_knee_sign_full": round(float(np.where(bsign != 0, bsign == yy, 0.5).mean()), 4),
             "binance_then_late_venue_override_full": round(float(np.where(comb != 0, comb == yy, 0.5).mean()), 4)}
        dis = nzl & (bsign != 0) & (np.sign(np.nan_to_num(late)) != bsign)
        o["where_late_venue_disagrees_with_binance"] = {"n": int(dis.sum()), "venue_right": round(float((np.sign(late[dis]) == yy[dis]).mean()), 4) if dis.any() else None}
        res[v] = o
        print(v, json.dumps({k: o[k] for k in o if k != "profile_agree_on_covered_and_coverage"}), {c: prof[c] for c in (400, 320, 260, 230, 200, 150, 100)})
    json.dump(res, open(f"{R}/knee14b.json", "w"), indent=1)


if __name__ == "__main__":
    main()
