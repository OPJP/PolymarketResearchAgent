"""X144 step 2, Polymarket half (information panel iter-10 P1): the wallet's PRE-GAME levels against Polymarket's own
book, 16-22 Oct (development). Pre-game has no game state, so a level that departs from the public price there is a
private prior (own ratings or an external line); a level on the public price says its prior is Polymarket's.

Rows: its filled maker orders signed before the market's scheduled game start (gs_ts) and, as the in-play reference,
those signed 10-60 min after it. Anchors (point-in-time, non-wallet public prints only, tapes/<cid>_tkw):
the last public print on the token before signing (rounded to the cent), the median of the last 5 prints, and the
complement form 1 - last print of the other token. Reports within one tick (1c inside [0.04, 0.96]), the offset
distribution (p10 / p50 / p90, cents), the age of the last print, by market type, BUILD and VALIDATE.
Output: results/pregame_levels.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
C = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0, H = 1792540800, 1792713600


def hit(p, a):
    p, a = np.asarray(p, float), np.asarray(a, float)
    t = np.where((a >= 0.04) & (a <= 0.96), 0.01, 0.001)
    return np.isfinite(a) & (np.abs(p - a) <= t + 1e-9)


def main():
    o = pd.read_parquet(C / "orders.parquet")
    o = o[(o.role == "maker") & (o.gs_ts < H)].copy()
    o["dt"] = o.sign_ts - o.gs_ts
    o = o[(o.dt < 0) | ((o.dt >= 600) & (o.dt < 3600))].copy()
    o["phase"] = np.where(o.dt < 0, "pre", "inplay_10_60min")
    rows = []
    for cid, g in o.groupby("cid"):
        p = C / f"tapes/{cid}_tkw.parquet"
        if not p.exists():
            continue
        t = pd.read_parquet(p, columns=["timestamp", "price", "outcomeIndex", "proxyWallet", "transactionHash"])
        t = t[t.proxyWallet.str.lower() != W].sort_values("timestamp")
        ts = t.timestamp.to_numpy(float)
        p0 = np.where(t.outcomeIndex.to_numpy() == 0, t.price.to_numpy(float), 1 - t.price.to_numpy(float))
        for r in g.itertuples():
            j = np.searchsorted(ts, r.sign_ts, side="right") - 1
            if j < 0:
                rows.append({"cid": cid, "smt": r.smt, "phase": r.phase, "gs": r.gs_ts, "p": r.price, "last": np.nan,
                             "med5": np.nan, "age": np.nan, "dt": r.dt})
                continue
            v = p0[j] if r.oi == 0 else 1 - p0[j]
            lo = max(0, j - 4)
            m5 = np.median(p0[lo:j + 1]) if r.oi == 0 else 1 - np.median(p0[lo:j + 1])
            rows.append({"cid": cid, "smt": r.smt, "phase": r.phase, "gs": r.gs_ts, "p": r.price, "last": np.round(v, 2),
                         "med5": np.round(m5, 2), "age": r.sign_ts - ts[j], "dt": r.dt})
    R = pd.DataFrame(rows)
    out = {}
    for sp, sel in (("BUILD", R.gs < VAL0), ("VALIDATE", R.gs >= VAL0)):
        for ph in ("pre", "inplay_10_60min"):
            S = R[sel & (R.phase == ph)]
            k = S["last"].notna()
            off = (S.p - S["last"])[k] * 100
            out[f"{sp}_{ph}"] = {"orders": int(len(S)), "markets": int(S.cid.nunique()), "with_print": int(k.sum()),
                                 "within_tick_last": round(float(hit(S.p[k], S["last"][k]).mean()), 3) if k.any() else None,
                                 "within_tick_med5": round(float(hit(S.p[k], S["med5"][k]).mean()), 3) if k.any() else None,
                                 "offset_c_p10_p50_p90": [round(float(np.percentile(off, q)), 1) for q in (10, 50, 90)] if k.any() else None,
                                 "last_print_age_s_p50": round(float(S.age[k].median()), 1) if k.any() else None,
                                 "by_type": {smt: round(float(hit(S.p[k & (S.smt == smt)], S["last"][k & (S.smt == smt)]).mean()), 3)
                                             for smt in S.smt.unique() if (k & (S.smt == smt)).sum() >= 20}}
    (RES / "pregame_levels.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
