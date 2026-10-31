"""Taker presence on the live book (pre-registered unit for live rules): (market, team, 0.5-s bin) over the recorded
in-play span; label = the wallet signs a taker BUY of that team in the bin. Score S_col = depth-collapse strength on the
team's ask side known at the bin start: 1 - D(t)/max D over [t-1.5, t-0.4] s (0 if no public trade-free collapse).
Baseline B_act: public prints (count, size) on the market in the previous 2 s and 10 s, price level (logistic).
Combined: logistic(B_act + S_col). AUCs on the development block 10-31 12-18 UTC (live BUILD only; descriptive)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from dev_books import BLOCK0, OUT, RES, WALLET  # noqa: E402
from common import auc  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import live  # noqa: E402

BIN = 500


def main():
    end = min(time.time() - 60, BLOCK0 + 6 * 3600)
    a = pd.read_parquet(OUT / "activity_devblocks.parquet")
    mk, _ = PolymarketData().markets_by_condition(sorted(a.conditionId.unique()))
    tok = {}
    for cid, x in mk.items():
        t = x["clobTokenIds"]
        t = json.loads(t) if isinstance(t, str) else t
        tok[str(t[0])] = (cid, 0, str(t[0]))
        tok[str(t[1])] = (cid, 1, str(t[0]))
    tok0 = {v[2] for v in tok.values()}
    recs, trades = [], []
    h = BLOCK0
    while h < end:
        try:
            for r in live.iter_live("clob_wallets", h, min(h + 3600, end)):
                if r.get("a") in tok0:
                    if r.get("k") in ("q", "f"):
                        b = [(float(p), float(z)) for p, z in (r.get("b") or [])]
                        o = [(float(p), float(z)) for p, z in (r.get("o") or [])]
                        bb = max((p for p, z in b), default=np.nan)
                        ba = min((p for p, z in o), default=np.nan)
                        recs.append((r["t"], r["a"], bb, ba, sum(z for p, z in b if p >= bb - 0.03 - 1e-9), sum(z for p, z in o if p <= ba + 0.03 + 1e-9)))
                    elif r.get("k") == "x":
                        trades.append((r["t"], r["a"], float(r.get("z") or 0)))
        except Exception as e:  # noqa: BLE001
            print("hour stopped", type(e).__name__)
        h += 3600
    bk = pd.DataFrame(recs, columns=["t", "a", "bb", "ba", "Db", "Do"]).sort_values("t")
    tr = pd.DataFrame(trades, columns=["t", "a", "z"]).sort_values("t")
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    d = d[(d.idx == -1) & (d.maker == WALLET) & (d.sign_ms > 1.79e12) & d.token_id.astype(str).isin(tok)].copy()
    d["a"] = d.token_id.astype(str).map(lambda t: tok[t][2])
    d["team"] = [(tok[str(t)][1] if s == 0 else 1 - tok[str(t)][1]) for t, s in zip(d.token_id, d.side)]
    rows = []
    for a_, b in bk.groupby("a"):
        tt = b.t.to_numpy()
        if len(tt) < 50:
            continue
        trt = tr[tr.a == a_].t.to_numpy()
        trz = tr[tr.a == a_].z.to_numpy()
        bins = np.arange(tt[0] + 2000, tt[-1], BIN)
        j = np.searchsorted(tt, bins, side="right") - 1
        lo = np.searchsorted(tt, bins - 1500)
        hi = np.searchsorted(tt, bins - 400, side="right")
        n2 = np.searchsorted(trt, bins) - np.searchsorted(trt, bins - 2000)
        n10 = np.searchsorted(trt, bins) - np.searchsorted(trt, bins - 10000)
        cz = np.concatenate([[0], np.cumsum(trz)])
        z10 = cz[np.searchsorted(trt, bins)] - cz[np.searchsorted(trt, bins - 10000)]
        notr = (np.searchsorted(trt, bins) - np.searchsorted(trt, bins - 1500)) == 0
        for col, team in (("Do", 0), ("Db", 1)):
            D = b[col].to_numpy()
            ref = np.array([D[l:hh].max() if hh > l else np.nan for l, hh in zip(lo, hi)])
            cur = D[j]
            s_col = np.where((ref >= 200) & notr, np.clip(1 - cur / ref, 0, 1), 0.0)
            px = b.ba.to_numpy()[j] if team == 0 else 1 - b.bb.to_numpy()[j]
            ws = d[(d.a == a_) & (d.team == team)].sign_ms.to_numpy()
            y = np.zeros(len(bins), bool)
            k = np.searchsorted(bins, ws, side="right") - 1
            y[k[(k >= 0) & (k < len(bins))]] = True
            rows.append(pd.DataFrame({"a": a_, "team": team, "y": y, "s_col": np.nan_to_num(s_col), "n2": n2, "n10": n10, "z10": z10, "px": px}))
    x = pd.concat(rows, ignore_index=True)
    x = x[np.isfinite(x.px)]
    x.to_parquet(OUT / "collapse_bins.parquet", index=False)
    from sklearn.linear_model import LogisticRegression
    Xb = np.column_stack([np.log1p(x.n2), np.log1p(x.n10), np.log1p(x.z10), x.px, x.px ** 2])
    Xc = np.column_stack([Xb, x.s_col, x.s_col ** 2])
    res = {"bins": len(x), "positives": int(x.y.sum()), "auc_S_col": round(auc(x.s_col, x.y), 4)}
    for name, X in (("B_act", Xb), ("B_act_plus_S_col", Xc)):
        m = LogisticRegression(max_iter=3000).fit(X, x.y)  # in-sample (live BUILD, descriptive)
        res[f"auc_{name}_insample"] = round(auc(m.predict_proba(X)[:, 1], x.y), 4)
    json.dump(res, open(RES / "results/collapse_presence.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
