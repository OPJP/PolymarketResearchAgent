"""DIAGNOSTIC ONLY (never a rule feature): how far is the Binance TWAP-60 strike
from the Chainlink strike that settles the window (Gamma priceToBeat), and how
does the basis evolve? BUILD windows only. Also saves, per window, the
Chainlink final/strike with Gamma closedTime so a point-in-time basis can be
built from windows that resolved strictly before a decision time.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from features import Spot  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.workflows.updown_study import fetch_windows, window_slugs  # noqa: E402

OUT = ROOT / ".cache/re/directional-maker"
H = 1792713600


def main(lo, hi):
    slugs = window_slugs("btc", "5m", lo, min(hi, H))
    ms = fetch_windows(slugs)
    rows = []
    for cid, m in ms.items():
        ev = (m.get("events") or [{}])[0]
        md = ev.get("eventMetadata") or {}
        st = int(pd.Timestamp(m["eventStartTime"]).timestamp())
        rows.append({"cid": cid, "start_ts": st, "ptb": md.get("priceToBeat"), "final": md.get("finalPrice"),
                     "closed_ts": int(pd.Timestamp(m["closedTime"]).timestamp()) if m.get("closedTime") else None,
                     "uma_ts": m.get("umaEndDate")})
    d = pd.DataFrame(rows).sort_values("start_ts")
    d = d[d["start_ts"] + 300 <= H]
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    d["bn_strike"] = sp.mean(d["start_ts"] - 60, d["start_ts"])
    d["bn_final"] = sp.mean(d["start_ts"] + 240, d["start_ts"] + 300)
    d["basis_strike"] = d["ptb"] - d["bn_strike"]
    d["basis_final"] = d["final"] - d["bn_final"]
    d["resolve_lag"] = d["closed_ts"] - (d["start_ts"] + 300)
    print("windows", len(d), "with ptb", d["ptb"].notna().sum(), "with final", d["final"].notna().sum())
    print("basis strike (ptb - binance twap) q", np.round(np.nanquantile(d["basis_strike"], [0.05, 0.25, 0.5, 0.75, 0.95]), 2))
    print("basis final q", np.round(np.nanquantile(d["basis_final"], [0.05, 0.25, 0.5, 0.75, 0.95]), 2))
    print("resolve lag (closedTime - end) q", np.nanquantile(d["resolve_lag"], [0.05, 0.5, 0.95]))
    # persistence of the basis: corr with basis of window 3 back (15 min)
    b = d.set_index("start_ts")["basis_strike"]
    for k in (1, 3, 6, 12):
        print(f"basis autocorr lag {k} windows", round(b.autocorr(k), 3))
    # ptb(W) vs final(W-1): same quantity?
    d["prev_final"] = d["final"].shift(1)
    print("ptb - prev final q", np.round(np.nanquantile(d["ptb"] - d["prev_final"], [0.05, 0.5, 0.95]), 3))
    # outcome agreement: binance proxy vs chainlink
    up_cl = d["final"] >= d["ptb"]
    up_bn = d["bn_final"] >= d["bn_strike"]
    print("binance-proxy outcome agrees with chainlink", round((up_cl == up_bn).mean(), 4))
    d.to_parquet(OUT / f"chainlink_ref_{lo}_{hi}.parquet", index=False)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
