"""iteration 17, T12 = X195 natural experiment (pre-registered in NOTES.md 11:22 UTC): the cluster's BTC 5m BUY fill
return per $ in the 7 days before vs after the taker-hold changes (08-17 11:00 UTC 250 -> 50 ms; 09-04 14:00 UTC 50 -> 150 ms)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from polyrea.workflows.updown_study import fetch_windows  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
CHG = {"0817_250to50": 1786964400, "0904_50to150": 1788530400}
WK = 7 * 86400


def main():
    h = pd.read_parquet(C / "it12" / "hist_btc.parquet", columns=["timestamp", "side", "outcomeIndex", "price", "size", "usdcSize", "slug"])
    h = h[h.slug.astype(str).str.startswith("btc-updown-5m-") & (h.side == "BUY")].copy()
    h["st"] = h.slug.str.rsplit("-", n=1).str[1].astype(int)
    lo, hi = min(CHG.values()) - WK, max(CHG.values()) + WK
    h = h[(h.st >= lo) & (h.st < hi)]
    slugs = sorted(set(h.slug))
    print("slugs", len(slugs), flush=True)
    raw = fetch_windows(slugs)
    win = {}
    for m in raw.values():
        try:
            op = json.loads(m["outcomePrices"]) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices")
            outs = json.loads(m["outcomes"]) if isinstance(m.get("outcomes"), str) else m.get("outcomes")
            win[m["slug"]] = [float(x) for x in op]
        except Exception:  # noqa: BLE001
            continue
    h["pay"] = [win.get(s, [np.nan, np.nan])[int(i)] if s in win and int(i) in (0, 1) else np.nan for s, i in zip(h.slug, h.outcomeIndex)]
    h = h[np.isfinite(h.pay) & (h.pay.isin([0.0, 1.0]))]
    h["pnl"] = h.pay * h["size"] - h.usdcSize
    h["day"] = (h.st // 86400).astype(int)
    out = {"n_fills": int(len(h)), "windows_resolved": len(win)}
    rng = np.random.default_rng(0)
    for nm, t in CHG.items():
        rows = {}
        for side, m in (("before", (h.st >= t - WK) & (h.st < t)), ("after", (h.st >= t) & (h.st < t + WK))):
            x = h[m]
            rows[side] = {"fills": int(len(x)), "usd": round(float(x.usdcSize.sum()), 0), "ret_per_usd": round(float(x.pnl.sum() / x.usdcSize.sum()), 4) if len(x) else None,
                          "cheap_share": round(float((x.price < 0.5).mean()), 3) if len(x) else None,
                          "daily_ret": {str(d): round(float(g.pnl.sum() / g.usdcSize.sum()), 4) for d, g in x.groupby("day")}}
        b = h[(h.st >= t - WK) & (h.st < t)]
        a = h[(h.st >= t) & (h.st < t + WK)]
        gb = b.groupby("day").agg(p=("pnl", "sum"), u=("usdcSize", "sum"))
        ga = a.groupby("day").agg(p=("pnl", "sum"), u=("usdcSize", "sum"))
        diffs = []
        for _ in range(2000):
            sb = gb.sample(len(gb), replace=True, random_state=int(rng.integers(1e9)))
            sa = ga.sample(len(ga), replace=True, random_state=int(rng.integers(1e9)))
            diffs.append(sa.p.sum() / sa.u.sum() - sb.p.sum() / sb.u.sum())
        rows["diff_after_minus_before"] = round(rows["after"]["ret_per_usd"] - rows["before"]["ret_per_usd"], 4)
        rows["diff_ci90"] = [round(float(np.quantile(diffs, 0.05)), 4), round(float(np.quantile(diffs, 0.95)), 4)]
        out[nm] = rows
    pred = (out["0817_250to50"]["diff_after_minus_before"] < 0) and (out["0904_50to150"]["diff_after_minus_before"] > 0)
    out["reading_met"] = bool(pred and abs(out["0904_50to150"]["diff_after_minus_before"]) >= 0.02 and out["0904_50to150"]["diff_ci90"][0] > 0)
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "before" and kk != "after"} | {"before": {k2: v2 for k2, v2 in v["before"].items() if k2 != "daily_ret"}, "after": {k2: v2 for k2, v2 in v["after"].items() if k2 != "daily_ret"}}) for k, v in out.items()}, indent=1))
    (HERE.parent / "results" / "iter17_hold_natexp.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
