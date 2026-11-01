"""X156 step 3 (assumptions panel iter-10 P4): build fingerprints of the frozen constants on the post-H development blocks
(10-31 00-06 and 12-18 UTC) against 16-22 Oct, before any future-block exam.

From calldata_dev (decoded matchOrders of the wallet's dev-block markets; sign_ms kept only in [block start - 1 h,
block time]) and activity_devblocks (MERGE rows): (1) the client band [0.05, 0.95]; (2) maker size ladder by title
(CS2 100 shares, Dota 2 10 shares); (3) whole-cent prices; (4) the merge loop law (next pass start = previous pass start
+ 300.22 s + 7.28 s x merges; passes = merges <= 30 s apart); (5) its maker-order lag behind P4e's takes on the same event
(P4e = 0x4ebc2722..., matched by prefix in the dev-block calldata) within 150 ms; (6) taker size median and cap share.
Reference values (16-22 Oct): band 0 of 25,878 outside; CS2 100-share 88-92%, Dota 10-share 100%; merge residual SD
1.33 s, 99.2% phase-continuous; P4e lag median +51 ms. Output: results/fingerprints_dev.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
C = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def main():
    cd = pd.read_parquet(C / "calldata_dev.parquet")
    dm = pd.read_parquet(C / "dev_markets.parquet")
    tokmap = {}
    for r in dm.itertuples():
        tokmap[str(r.tok0)] = (r.slug, r.event, 0)
        tokmap[str(r.tok1)] = (r.slug, r.event, 1)
    cd["tok"] = cd.token_id.astype(str)
    cd = cd[cd.tok.isin(tokmap)].copy()
    cd["slug"] = cd.tok.map(lambda t: tokmap[t][0])
    cd["event"] = cd.tok.map(lambda t: tokmap[t][1])
    cd["title"] = np.where(cd.slug.str.startswith("dota2"), "dota2", "cs2")
    ok_sign = (cd.sign_ms > 1.79345e12) & (cd.sign_ms < 1.79348e12)  # 10-31 00:00 .. ~08:20 + 12-18 window bound below
    cd = cd[(cd.sign_ms > 1.7934048e12) & (cd.sign_ms < 1.7934696e12)]  # 10-31 00:00 .. 18:00 UTC (development blocks)
    w = cd[cd.maker.str.lower() == W].drop_duplicates("salt")
    mk, tk = w[w.idx >= 0], w[w.idx == -1]
    out = {"orders": int(len(w)), "maker": int(len(mk)), "taker": int(len(tk))}
    out["band_outside_0.05_0.95"] = int(((w.price < 0.05 - 1e-9) | (w.price > 0.95 + 1e-9)).sum())
    out["whole_cent_share_maker"] = round(float((np.abs(mk.price * 100 - np.round(mk.price * 100)) < 1e-6).mean()), 3)
    out["maker_size"] = {t: {"n": int((mk.title == t).sum()), "share_100": round(float((mk[mk.title == t].shares.round(2) == 100).mean()), 3),
                             "share_10": round(float((mk[mk.title == t].shares.round(2) == 10).mean()), 3),
                             "median": float(mk[mk.title == t].shares.median()) if (mk.title == t).any() else None}
                         for t in ("cs2", "dota2")}
    out["taker_size"] = {t: {"n": int((tk.title == t).sum()), "median": float(tk[tk.title == t].shares.median()) if (tk.title == t).any() else None,
                             "share_cap_1000_2000": round(float(tk[tk.title == t].shares.round(0).isin([1000, 2000]).mean()), 3) if (tk.title == t).any() else None}
                         for t in ("cs2", "dota2")}
    # P4e lag: wallet maker orders signed 0-150 ms after a P4e take on the same event
    p4 = cd[(cd.idx == -1) & cd.maker.str.lower().str.startswith("0x4ebc2722")].drop_duplicates("salt")
    lags = []
    for ev, g in p4.groupby("event"):
        wm = mk[mk.event == ev].sign_ms.to_numpy(float)
        wm.sort()
        for s in g.sign_ms.to_numpy(float):
            j = np.searchsorted(wm, s, side="right")
            if j < len(wm) and wm[j] - s <= 150:
                lags.append(wm[j] - s)
    out["p4e_takes"] = int(len(p4))
    out["wallet_maker_within_150ms_of_p4e"] = {"n": len(lags), "median_ms": round(float(np.median(lags)), 1) if lags else None,
                                               "p25_p75": [round(float(np.percentile(lags, 25)), 1), round(float(np.percentile(lags, 75)), 1)] if lags else None}
    # merge loop law
    a = pd.read_parquet(C / "activity_devblocks.parquet")
    mg = np.sort(a[a.type == "MERGE"].timestamp.to_numpy(float))
    passes = []
    for t in mg:
        if passes and t - passes[-1][-1] <= 30:
            passes[-1].append(t)
        else:
            passes.append([t])
    res = []
    for p0, p1 in zip(passes[:-1], passes[1:]):
        pred = p0[0] + 300.22 + 7.28 * len(p0)
        res.append(p1[0] - pred)
    res = np.array(res)
    out["merge_loop"] = {"merges": int(len(mg)), "passes": len(passes),
                         "residual_s_median": round(float(np.median(res)), 2) if len(res) else None,
                         "share_abs_residual_le_10s": round(float((np.abs(res) <= 10).mean()), 3) if len(res) else None,
                         "residuals_s": [round(float(x), 1) for x in res[:40]],
                         "window_utc": [str(pd.to_datetime(mg.min(), unit="s")), str(pd.to_datetime(mg.max(), unit="s"))] if len(mg) else None}
    (RES / "fingerprints_dev.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
