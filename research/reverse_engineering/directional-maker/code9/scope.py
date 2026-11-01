"""Iteration 9 (assumptions B1 = X83): coverage of nested universes per 6-hour block and block type, and the module
on/off calendar. Development data only: BUILD 10-08..22, the released lot 10-23..30 (aggregates per block), the
development blocks 10-31 00-06 and 12-18. Universes (cumulative):
  U1 BTC 5m + 15m (R6), U2 + BTC 4h, U3 + BTC hourly/daily (Binance-settled), U4 + ETH (all horizons),
  U5 every crypto Up/Down family.
Calendar gate (assumptions panel, frozen there): off from Friday, Saturday or Sunday 18:00 ET to 09:00 ET the next day.
Writes results/iter9_scope.json."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"
RES = HERE.parent / "results"


def fam(slug: str) -> str:
    s = str(slug)
    for a in ("btc", "eth", "sol", "xrp", "bnb", "doge"):
        for h in ("5m", "15m", "4h"):
            if s.startswith(f"{a}-updown-{h}-"):
                return f"{a}_{h}"
    long = {"bitcoin": "btc", "ethereum": "eth", "solana": "sol", "xrp": "xrp", "bnb": "bnb", "dogecoin": "doge"}
    for k, a in long.items():
        if s.startswith(f"{k}-up-or-down-on-"):
            return f"{a}_daily"
        if s.startswith(f"{k}-up-or-down-"):
            return f"{a}_hourly"
    return "other"


UNIV = {"U1": {"btc_5m", "btc_15m"}}
UNIV["U2"] = UNIV["U1"] | {"btc_4h"}
UNIV["U3"] = UNIV["U2"] | {"btc_hourly", "btc_daily"}
UNIV["U4"] = UNIV["U3"] | {"eth_5m", "eth_15m", "eth_4h", "eth_hourly", "eth_daily"}


def load():
    parts = []
    for n in ("bosona", "almach", "momoney"):
        for p in (C / f"activity_{n}.parquet", C / "exam" / f"activity_{n}.parquet"):
            d = pd.read_parquet(p, columns=["timestamp", "type", "slug", "usdcSize", "transactionHash", "asset", "size", "price"])
            d["wallet"] = n
            parts.append(d)
    a = pd.read_parquet(C / "live_activity_1793404800_1793426400.parquet")
    names = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
             "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
    if "wallet" not in a.columns:
        a["wallet"] = a.get("w", "x")
    a["wallet"] = a["wallet"].map(lambda v: names.get(str(v).lower(), str(v)))
    parts.append(a[["timestamp", "type", "slug", "usdcSize", "transactionHash", "asset", "size", "price", "wallet"]])
    b = pd.read_parquet(C / "it9" / "act_1793448000_1793469600.parquet")
    b["wallet"] = b.wallet.map(lambda v: names.get(str(v).lower(), str(v)))
    parts.append(b[["timestamp", "type", "slug", "usdcSize", "transactionHash", "asset", "size", "price", "wallet"]])
    D = pd.concat(parts, ignore_index=True)
    D = D[D.type == "TRADE"].drop_duplicates(subset=["wallet", "transactionHash", "asset", "size", "price", "timestamp"])
    D["fam"] = D.slug.map(fam)
    return D


def main():
    D = load()
    D["blk"] = (D.timestamp // 21600) * 21600
    t = pd.to_datetime(D.blk, unit="s")
    D["dow"] = t.dt.dayofweek
    D["bh"] = t.dt.hour
    out = {"rows": int(len(D)), "families_dollars": D.groupby("fam").usdcSize.sum().sort_values(ascending=False).round(0).head(20).to_dict()}
    rows = []
    for blk, g in D.groupby("blk"):
        tot_n, tot_d = len(g), g.usdcSize.sum()
        if tot_n < 30:
            continue
        r = {"blk": int(blk), "dow": int(g.dow.iloc[0]), "bh": int(g.bh.iloc[0]), "n": tot_n, "usd": float(tot_d)}
        for u, fs in UNIV.items():
            k = g.fam.isin(fs)
            r[f"{u}_n"] = float(k.mean())
            r[f"{u}_usd"] = float(g.usdcSize[k].sum() / tot_d)
        k = g.fam != "other"
        r["U5_n"], r["U5_usd"] = float(k.mean()), float(g.usdcSize[k].sum() / tot_d)
        rows.append(r)
    B = pd.DataFrame(rows)
    B["type"] = np.where(B.dow >= 5, "weekend", "weekday") + "_" + B.bh.map({0: "00", 6: "06", 12: "12", 18: "18"})
    B["version"] = np.where(B.blk >= 1792108800, "since10-16", "before10-16")
    summ = {}
    for u in ("U1", "U2", "U3", "U4", "U5"):
        both = np.minimum(B[f"{u}_n"], B[f"{u}_usd"])
        summ[u] = {"blocks": int(len(B)), "share_blocks_ge_0.80_both": float((both >= 0.8).mean()),
                   "since10-16_share_ge_0.80": float((both[B.version == "since10-16"] >= 0.8).mean()),
                   "min_by_type_since10-16": {ty: round(float(both[(B.type == ty) & (B.version == "since10-16")].min()), 3) for ty in sorted(B.type.unique())},
                   "median_by_type_since10-16": {ty: round(float(both[(B.type == ty) & (B.version == "since10-16")].median()), 3) for ty in sorted(B.type.unique())}}
    out["universes"] = summ
    print(pd.DataFrame({u: summ[u]["min_by_type_since10-16"] for u in summ}).to_string())
    print({u: (summ[u]["share_blocks_ge_0.80_both"], summ[u]["since10-16_share_ge_0.80"]) for u in summ})
    # module on/off for BTC 5m and 15m windows: the calendar gate at window level since 10-16
    gate = {}
    for f_, L in (("btc_5m", 300), ("btc_15m", 900)):
        g = D[D.fam == f_]
        st = g.slug.str.rsplit("-", n=1).str[1].astype(np.int64)
        act = set(st.unique())
        a0, a1 = 1792108800, 1793469600
        ws = np.arange(a0, a1, L)
        dev = ((ws < 1793426400) | ((ws >= 1793448000) & (ws < 1793469600)))
        ws = ws[dev]
        y = np.array([w in act for w in ws])
        et = pd.to_datetime(ws - 4 * 3600, unit="s")
        h, d = et.hour.to_numpy(), et.dayofweek.to_numpy()
        off = ((np.isin(d, [4, 5, 6])) & (h >= 18)) | ((np.isin(d, [5, 6, 0])) & (h < 9))
        rec = {"windows": int(len(ws)), "active_share": float(y.mean()), "active_when_gate_off": float(y[off].mean()),
               "active_otherwise": float(y[~off].mean()), "auc_gate": float(roc_auc_score(y, ~off))}
        # off-runs >= 1 h
        runs, cur = [], None
        for w, a_ in zip(ws, y):
            if not a_:
                cur = w if cur is None else cur
            else:
                if cur is not None and w - cur >= 3600:
                    runs.append((int(cur), int(w)))
                cur = None
        rec["off_runs_ge_1h"] = [(pd.to_datetime(a, unit="s").strftime("%a %m-%d %H:%M"), round((b - a) / 3600, 1)) for a, b in runs]
        gate[f_] = rec
    out["gate"] = gate
    print(json.dumps(gate, indent=1))
    # do BTC 5m and 15m switch together? share of 5m-off hours (dev, since 10-16) where 15m is also off
    out["blocks"] = B.round(4).to_dict("records")
    (RES / "iter9_scope.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
