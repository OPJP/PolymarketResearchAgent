"""Shared loaders for rebate-farmer (development data only, < H)."""
import glob, os, re
import numpy as np, pandas as pd

ROOT = "/home/user/PolymarketResearchAgent"
CACHE = f"{ROOT}/.cache/re/rebate-farmer"
H = 1792713600
VAL0 = 1792108800  # VALIDATE = [VAL0, H)
BUILD0 = 1788220800
DUR = {"5m": 300, "15m": 900, "4h": 14400, "1h": 3600}


def load_activity(a, b):
    """TRADE rows of the wallet with ts in [a, b) (b <= H enforced)."""
    assert b <= H
    fs = sorted(glob.glob(f"{CACHE}/activity/*.parquet"))
    fs = [f for f in fs if a - 86400 < int(os.path.basename(f).split(".")[0]) < b]
    df = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    df = df[(df.timestamp >= a) & (df.timestamp < b)]
    return df


def add_family(t):
    t = t.copy()
    s = t.slug.fillna("")
    m = s.str.extract(r"^([a-z]+)-updown-(5m|15m|4h)-(\d{9,})$")
    t["asset"] = m[0]
    t["dur"] = m[1]
    t["ws"] = pd.to_numeric(m[2], errors="coerce")
    # hourly: '<name>-up-or-down-<month>-<day>-<year>-<h>(am|pm)-et'
    h = s.str.extract(r"^([a-z]+)-up-or-down-([a-z]+)-(\d+)-(\d{4})-(\d+)(am|pm)-et$")
    ok = h[0].notna()
    if ok.any():
        name2asset = {"bitcoin": "btc", "ethereum": "eth", "solana": "sol", "xrp": "xrp", "dogecoin": "doge", "bnb": "bnb", "hyperliquid": "hype"}
        hr = h[4].astype(float) % 12 + np.where(h[5] == "pm", 12, 0)
        dates = pd.to_datetime(h[1] + " " + h[2] + " " + h[3], format="%B %d %Y", errors="coerce")
        # ET = UTC-4 (EDT) through 2026-11-01
        wsh = (dates - pd.Timestamp("1970-01-01")).dt.total_seconds() + hr * 3600 + 4 * 3600
        t.loc[ok, "asset"] = h.loc[ok, 0].map(name2asset)
        t.loc[ok, "dur"] = "1h"
        t.loc[ok, "ws"] = wsh[ok]
    t["fam"] = t.asset.fillna("other") + "-" + t.dur.fillna("other")
    t["we"] = t.ws + t.dur.map(DUR)
    return t
