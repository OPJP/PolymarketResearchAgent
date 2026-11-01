"""X228 step 2 (assumptions panel iter-15 P2), quick form: the operator's GRID arm (0x10d79cc7, attributed by the shadow
fingerprint in shadow_persistence.json) as a public-information control. 0x10d79cc7 has no trade in the decoded GRID units of the
development blocks, so the unit is 16-22 Oct (before H): its orders decoded for shadow_persistence.py (the shadows'
markets, +-1 h of a shadow trade) and the data-api taker tape of those markets (fetched, before H). Per maker order and per burst top
(50-ms chains on a token): distance to the last clean print at signing (wallet- and operator-free taker rows, block time),
share within one tick (1c) of print + k for k in -4..+1 c, and the same for the wallet's own orders on 16-22 Oct
(order unit, 0.305 wallet-free). Output: results/grid_arm_anchor.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
L = "0x10d79cc72df76ea3d6bdc2d54f41dbcbbb18bbf6"
OPS = {"0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2", "0xd2bb94594762beda042e596598800d83f781bd8e", "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14",
       L, "0x52661b8e13158f23d94a9e8302ab0295704c22ac", "0x671190333b064b0899b4ac1aec86744b1f82885b"}
import sys
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
H = 1792713600
c = pd.read_parquet(OUT / "iter16/shadow_calldata.parquet")
c = c[(c.maker.str.lower() == L) & (c.idx >= 0) & (c.sign_ms > 1.7e12) & (c.sign_ms < H * 1000)].drop_duplicates(["salt", "sign_ms"])
act = pd.read_parquet(OUT / "iter16/shadow_activity.parquet")
tok2cid = dict(zip(act.asset.astype(str), act.cid))
c["cid"] = c.token_id.astype(str).map(tok2cid)
c = c[c.cid.notna()]
tp = OUT / "iter16/grid_arm_tapes.parquet"
if tp.exists():
    t = pd.read_parquet(tp)
else:
    pm = PolymarketData()
    rr = []
    for cid, g in c.groupby("cid"):
        a = int(g.sign_ms.min() / 1000) - 3600
        b = min(int(g.sign_ms.max() / 1000) + 600, H - 1)
        rws, _, _ = pm.market_trades(cid, start=a, end=b, taker_only=True)
        for x in rws:
            x = dict(x)
            x.update(cid=cid, is_taker_row=True, event=act.loc[act.cid == cid, "event"].iloc[0])
            rr.append(x)
    t = pd.DataFrame(rr)
    t["proxyWallet"] = t.proxyWallet.str.lower()
    t = t[["proxyWallet", "asset", "outcomeIndex", "price", "timestamp", "transactionHash", "cid", "event", "is_taker_row"]]
    t = t[t.timestamp < H]
    t.to_parquet(tp, index=False)
optx = set(act.tx) | set(t.loc[t.proxyWallet.isin(OPS), "transactionHash"])
rows = []
for asset, g in c.groupby(c.token_id.astype(str)):
    tt = t[t.asset.astype(str).isin([asset])]
    if not len(tt):
        continue
    cid = tt.cid.iloc[0]
    pt = t[(t.cid == cid) & (t.is_taker_row == True) & ~t.transactionHash.isin(optx)].sort_values("timestamp")  # noqa: E712
    if len(pt) < 5:
        continue
    oi = int(tt.outcomeIndex.iloc[0])
    p_tok = np.where(pt.outcomeIndex.astype(int) == oi, pt.price.astype(float), 1 - pt.price.astype(float))
    ts = pt.timestamp.to_numpy(float)
    g = g.sort_values("sign_ms")
    s, p = g.sign_ms.to_numpy(float), g.price.to_numpy(float)
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] - s[i] <= 50:
            j += 1
        k = np.searchsorted(ts, s[i] / 1000.0, side="left") - 1
        if k >= 0:
            lp = round(float(p_tok[k]), 2)
            for q in range(i, j + 1):
                rows.append({"event": tt.event.iloc[0], "top": q == i + int(np.argmax(p[i:j + 1])), "p": p[q], "lp": lp, "n": j - i + 1,
                             "shares": float(g.shares.iloc[q])})
        i = j + 1
R = pd.DataFrame(rows)
R = R[(R.lp >= 0.04) & (R.lp <= 0.96)]
out = {"orders": int(len(R)), "events": R.event.value_counts().to_dict(), "sizes_top": R.shares.round(0).value_counts().head(5).to_dict(),
       "burst_size_counts": R[R.top].n.value_counts().sort_index().head(8).to_dict()}
for nm, X in (("all_orders", R), ("burst_tops", R[R.top])):
    out[nm] = {"n": int(len(X)), "median_offset_c": round(float(((X.p - X.lp) * 100).median()), 2),
               "within_1c_of_print_plus_k": {str(k): round(float((np.abs(X.p - (X.lp + k / 100)) <= 0.01 + 1e-9).mean()), 3) for k in range(-4, 2)}}
(RES / "grid_arm_anchor.json").write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str))
