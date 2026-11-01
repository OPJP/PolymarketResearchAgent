"""X176: did the earlier account take on the push feed before 10-16? Signing lag of 0x7d67f01d's taker orders
(10-08..10-15, sampled calldata) behind P4e's taker orders on the same token (pre-switch subscriber calldata,
feed_pre/calldata, plus any P4e orders inside the sampled transactions); same for 0x2005d16a as a second reference.
Output: results/sibling_feed_lag.json"""
import glob, json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"; RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
A = "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14"; P4E = "0x4ebc2722adc772bde8680792d0a6fdf15499a33d"
G2 = "0x2005d16a84ceefa912d4e380cd32e7ff827875ea"
cols = ["tx", "idx", "maker", "token_id", "price", "shares", "sign_ms", "salt"]
fp = pd.concat([pd.read_parquet(f, columns=cols) for f in glob.glob(str(OUT / "feed_pre/calldata/*.parquet"))])
sa = pd.concat([pd.read_parquet(f, columns=cols) for f in glob.glob(str(OUT / "sib7d67/calldata/*.parquet"))])
d = pd.concat([fp, sa]); d["maker"] = d.maker.str.lower(); d["token_id"] = d.token_id.astype(str)
d = d[(d.sign_ms > 1.7e12) & (d.sign_ms < 1.8e12)]
tk = d[d.idx == -1].drop_duplicates(["maker", "salt", "sign_ms"])
out = {}
for ref_name, ref in (("P4e", P4E), ("0x2005d16a", G2)):
    r = tk[tk.maker == ref]
    rt = {t: np.sort(g.sign_ms.to_numpy(np.int64)) for t, g in r.groupby("token_id")}
    a = tk[tk.maker == A]
    lags = []
    for row in a.itertuples():
        s = rt.get(row.token_id)
        if s is None: continue
        j = np.searchsorted(s, row.sign_ms)
        cand = []
        if j > 0: cand.append(row.sign_ms - s[j - 1])
        if j < len(s): cand.append(row.sign_ms - s[j])
        c = min(cand, key=abs)
        if abs(c) <= 2000: lags.append(int(c))
    lags = np.array(lags)
    bins = [-2000, -500, -100, -20, 0, 20, 40, 60, 80, 100, 200, 500, 2001]
    h = np.histogram(lags, bins=bins)[0].tolist() if len(lags) else []
    out[ref_name] = {"ref_taker_orders": int(len(r)), "sibling_taker_orders": int(len(a)),
                     "sibling_orders_on_ref_tokens": int(a.token_id.isin(rt).sum()),
                     "pairs_within_2s": int(len(lags)), "hist_bins_ms": bins, "hist": h,
                     "median_lag_ms_within_500": float(np.median(lags[np.abs(lags) <= 500])) if (np.abs(lags) <= 500).any() else None,
                     "share_in_20_100ms": round(float(np.mean((lags >= 20) & (lags < 100))), 3) if len(lags) else None}
(RES / "sibling_feed_lag.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
