"""iteration 18, T7 = X223 (information panel I17-4, historical part; pre-registered in NOTES.md 12:51 UTC 11-01): does the
October open-window behaviour read the US equity open? Per weekday BTC 5m window starting at 13:30 UTC (NYSE open under
DST), 10-02..10-26 case by case (VALIDATE 10-27..30 only pooled): the cluster's BUY trades in the window (activity; cheap =
price < 0.5), BTC's first-minute move 13:30:00 -> 13:31:00 (Binance 1-m klines REST), the equities' first-minute return
(open -> close of the 13:30 1-m bar of SPY, QQQ, IBIT). agree = sign(SPY + QQQ first-minute return) == sign(BTC move)."""
import json
import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
CL = ("bosona", "almach", "momoney")


def trades():
    fr = []
    for w in CL:
        for f in (C / f"activity_{w}.parquet", C / "exam" / f"activity_{w}.parquet"):
            a = pd.read_parquet(f, columns=["timestamp", "type", "side", "price", "size", "slug", "transactionHash"])
            fr.append(a[(a.type == "TRADE") & (a.side == "BUY") & a.slug.str.startswith("btc-updown-5m-")])
    h = pd.read_parquet(C / "it12" / "hist_btc.parquet", columns=["timestamp", "type", "side", "price", "size", "slug"])
    h = h[(h.type == "TRADE") & (h.side == "BUY") & h.slug.astype(str).str.startswith("btc-updown-5m-")]
    fr.append(h)
    A = pd.concat(fr, ignore_index=True)
    A["st"] = A.slug.astype(str).str.rsplit("-", n=1).str[1].astype(int)
    if "transactionHash" in A:
        A = A.drop_duplicates(["timestamp", "price", "size", "slug", "transactionHash"])
    return A


def main():
    A = trades()
    Y = pd.concat([pd.read_parquet(C / "it18" / "yahoo_1m_early.parquet"), pd.read_parquet(C / "it18" / "yahoo_1m.parquet")]).drop_duplicates(["sym", "ts"])
    days = [d for d in range(1790899200, 1793404800, 86400) if pd.Timestamp(d, unit="s").weekday() < 5]
    rows = []
    with httpx.Client(timeout=20) as cl:
        for d in days:
            t0 = d + 13 * 3600 + 1800
            r = cl.get("https://api.binance.com/api/v3/klines", params={"symbol": "BTCUSDT", "interval": "1m", "startTime": t0 * 1000, "limit": 1})
            k = r.json()[0] if r.status_code == 200 and r.json() else None
            btc = np.log(float(k[4]) / float(k[1])) if k else np.nan
            eq = {}
            for s in ("SPY", "QQQ", "IBIT"):
                b = Y[(Y.sym == s) & (Y.ts == t0)]
                eq[s] = float(np.log(b.c.iloc[0] / b.o.iloc[0])) if len(b) and b.o.iloc[0] and b.c.iloc[0] else np.nan
            f = A[A.st == t0]
            rows.append({"day": pd.Timestamp(d, unit="s").strftime("%m-%d"), "fold": "validate" if d >= 1793059200 else ("study" if d >= 1792713600 else "dev"),
                         "n": int(len(f)), "cheap": float((f.price < 0.5).mean()) if len(f) else np.nan, "btc_1m": btc, **{f"r_{s}": v for s, v in eq.items()}})
    D = pd.DataFrame(rows)
    D["eqr"] = D.r_SPY.fillna(0) + D.r_QQQ.fillna(0)
    D["agree"] = np.sign(D["eqr"]) == np.sign(D.btc_1m)
    dev = D[(D.fold != "validate") & (D.n >= 5) & np.isfinite(D.cheap) & D.r_SPY.notna()]
    out = {"windows_dev_study": dev[["day", "fold", "n", "cheap", "btc_1m", "r_SPY", "r_QQQ", "r_IBIT", "agree"]].round(5).to_dict("records")}
    ga, gd = dev[dev.agree].cheap, dev[~dev.agree].cheap
    out["dev_study"] = {"n_agree": int(len(ga)), "n_diverge": int(len(gd)), "cheap_agree": round(float(ga.mean()), 3) if len(ga) else None,
                        "cheap_diverge": round(float(gd.mean()), 3) if len(gd) else None,
                        "mannwhitney_p": float(mannwhitneyu(ga, gd).pvalue) if len(ga) and len(gd) else None,
                        "fills_agree": round(float(dev[dev.agree].n.mean()), 1) if len(ga) else None,
                        "fills_diverge": round(float(dev[~dev.agree].n.mean()), 1) if len(gd) else None,
                        "spearman_absbtc_cheap": [round(float(x), 3) for x in spearmanr(dev.btc_1m.abs(), dev.cheap)],
                        "spearman_abseq_cheap": [round(float(x), 3) for x in spearmanr(dev["eqr"].abs(), dev.cheap)]}
    v = D[(D.fold == "validate") & (D.n >= 5)]
    out["validate_pooled"] = {"windows": int(len(v)), "cheap_mean": round(float(v.cheap.mean()), 3) if len(v) else None}
    d = out["dev_study"]
    out["reading_met"] = bool(d["cheap_agree"] is not None and d["cheap_diverge"] is not None and abs(d["cheap_agree"] - d["cheap_diverge"]) >= 0.3
                              and d["mannwhitney_p"] is not None and d["mannwhitney_p"] < 0.05)
    (HERE.parent / "results" / "iter18_equity_open.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
