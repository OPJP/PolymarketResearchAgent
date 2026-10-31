"""Iteration 8: the per-fill posture side on the strict publish clock (development block 10-31 17:29-18:00 UTC, BTC 15m;
BTC 5m was off). Same rule as final_rule.side_posture_match_clock, but the Chainlink value is the latest dy_rtds report
whose server publish ms P <= T - lag (lag 0 / 50 / 150 ms), against the stamp convention floor((T - 1432)/1000).
    python code8/side_pubclock.py 1793467740 1793469600
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE.parent / "code5"))
import final_rule as F  # noqa: E402
from rawread import iter_dm  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402


def main(a, b):
    pm = PolymarketData()
    w = pd.concat([F._windows(a - 300, b + 300), F._windows15(a - 900, b + 900)], ignore_index=True)
    w["up_token"], w["down_token"] = w.up_token.astype(str), w.down_token.astype(str)
    ct = F._cluster_trades(a - 900, b, pm, False)
    tk = pd.concat([F._tapes(w[w.end_ts - w.start_ts == 300], pm, b, False), F._tapes15(w[w.end_ts - w.start_ts == 900], pm, b, False)], ignore_index=True)
    toks = set(w.up_token) | set(w.down_token)
    buys = ct[(ct.side == "BUY") & ct.token_id.isin(toks) & (ct.ts >= a) & (ct.ts < b)].copy()
    own = tk[tk.wallet.isin(set(F.CLUSTER))]
    pairs = set(zip(own.tx, own.wallet.astype(str)))
    buys["role"] = ["taker" if (x, y) in pairs else "maker" for x, y in zip(buys.tx, buys.wallet)]
    mk = buys[buys.role == "maker"].copy()
    txh = F._cluster_tx_hashes(a - 900, b, pm, False)
    mk["txh"] = mk.tx.map(txh)
    ups = set(w.up_token)
    tok_info = {**{t: (s, e, 1) for t, s, e in zip(w.up_token, w.start_ts, w.end_ts)}, **{t: (s, e, 0) for t, s, e in zip(w.down_token, w.start_ts, w.end_ts)}}
    up_of = {**dict(zip(w.up_token, w.up_token)), **dict(zip(w.down_token, w.up_token))}
    match_ms, books = {}, {}
    for r in F._iter_live_xq(a - 120, b + 120, ups):
        if r.get("k") == "x":
            h = str(r.get("h", "")).lower()
            if h and h not in match_ms:
                match_ms[h] = int(r.get("s") or r.get("t"))
        elif r.get("k") == "q" and str(r.get("a")) in ups:
            bq, oq = r.get("b") or [], r.get("o") or []
            if bq and oq:
                books.setdefault(str(r["a"]), []).append((int(r.get("s") or r["t"]), (max(float(x[0]) for x in bq) + min(float(x[0]) for x in oq)) / 2))
    bk = {t: (np.array([x[0] for x in v]), np.array([x[1] for x in v])) for t, v in books.items()}
    Pm = {}
    for r in iter_dm("dy_rtds", a - 60, b + 5):
        if r.get("k") == "u" and r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P") and r.get("ts"):
            Pm.setdefault(int(r["ts"]) // 1000, (int(r["P"]), float(r["v"])))
    ks = np.array(sorted(Pm))
    pubs = np.array([Pm[k][0] for k in ks], dtype=np.int64)
    vals = np.array([Pm[k][1] for k in ks])
    o = np.argsort(pubs)
    pubs_s, vals_s = pubs[o], vals[o]
    stamp_val = dict(zip(ks, vals))
    ptb = F._ptb_any(w)
    secs, px = zip(*F._binance_rest_seconds(a - 400, b + 10))
    secs, px = np.array(secs, dtype=np.int64), np.array(px)
    r1 = np.r_[0.0, np.diff(np.log(px))]
    rows = []
    for r in mk.itertuples(index=False):
        T = match_ms.get(str(r.txh).lower())
        inf = tok_info.get(str(r.token_id))
        if T is None or inf is None:
            continue
        u = up_of[str(r.token_id)]
        if u not in bk:
            continue
        i = np.searchsorted(bk[u][0], T, side="left") - 1
        if i < 0:
            continue
        K = ptb.get(("15m" if inf[1] - inf[0] == 900 else "5m", inf[0]))
        j = np.searchsorted(secs, T // 1000)
        if K is None or j < 300:
            continue
        sig = np.std(r1[j - 300:j]) * 1.4
        tau = max(inf[1] - T / 1000, 1.0)
        mid = bk[u][1][i]
        row = {"up": inf[2], "fam": "15m" if inf[1] - inf[0] == 900 else "5m", "wallet": r.wallet}
        for lag in (0, 50, 150):
            k = np.searchsorted(pubs_s, T - lag, side="right") - 1
            row[f"pub{lag}"] = (norm.cdf(np.log(vals_s[k] / K) / (sig * np.sqrt(tau))) - mid) if k >= 0 else np.nan
        sv = stamp_val.get((T - 1432) // 1000)
        row["stamp1432"] = (norm.cdf(np.log(sv / K) / (sig * np.sqrt(tau))) - mid) if sv else np.nan
        rows.append(row)
    D = pd.DataFrame(rows)
    out = {"fills": int(len(D)), "per_family_n": D.fam.value_counts().to_dict()}
    for c in ("pub0", "pub50", "pub150", "stamp1432"):
        v = D[D[c].notna()]
        out[c] = round(float(((v[c] > 0) == (v.up == 1)).mean()), 3) if len(v) else None
    (HERE.parent / "results" / f"iter8_side_pubclock_{a}_{b}.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
