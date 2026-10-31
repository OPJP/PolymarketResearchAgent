"""Which book collapses does the wallet act on? (dev block 10-31 12-18 UTC). For every collapse event (frac 0.5,
min_ref 200; see collapse_trigger.py): lag from the event to a wallet / pack taker order on that team, and event features
known at the event time: reference depth, remaining depth, best ask of the team before / at the event (price jump of the
touch), the team's price level, time since the previous collapse in the market. Compares the events the wallet acted on
with the rest (descriptive; small sample)."""
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
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from dev_books import BLOCK0, OUT, RES, WALLET  # noqa: E402
from dev_book_trigger import PACK  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import live  # noqa: E402


def main(frac=0.5, min_ref=200):
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
                        Db = sum(z for p, z in b if p >= bb - 0.03 - 1e-9)
                        Do = sum(z for p, z in o if p <= ba + 0.03 + 1e-9)
                        recs.append((r["t"], r["a"], bb, ba, Db, Do))
                    elif r.get("k") == "x":
                        trades.append((r["t"], r["a"]))
        except Exception as e:  # noqa: BLE001
            print("hour stopped", type(e).__name__)
        h += 3600
    bk = pd.DataFrame(recs, columns=["t", "a", "bb", "ba", "Db", "Do"]).sort_values("t")
    tr = pd.DataFrame(trades, columns=["t", "a"]).sort_values("t")
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    d = d[(d.idx == -1) & (d.sign_ms > 1.79e12) & (d.sign_ms < 1.8e12) & d.token_id.astype(str).isin(tok)].copy()
    d["a"] = d.token_id.astype(str).map(lambda t: tok[t][2])
    d["team"] = [(tok[str(t)][1] if s == 0 else 1 - tok[str(t)][1]) for t, s in zip(d.token_id, d.side)]
    d["grp"] = np.where(d.maker == WALLET, "W", np.where(d.maker.isin(PACK), "pack", "other"))
    rows = []
    for a_, b in bk.groupby("a"):
        tt = b.t.to_numpy()
        trt = tr[tr.a == a_].t.to_numpy()
        for col, team in (("Do", 0), ("Db", 1)):
            D = b[col].to_numpy()
            last = -1e18
            for i in range(len(tt)):
                lo, hi = np.searchsorted(tt, tt[i] - 1500), np.searchsorted(tt, tt[i] - 400, side="right")
                if hi <= lo:
                    continue
                ref = D[lo:hi].max()
                if ref < min_ref or D[i] > frac * ref:
                    continue
                k = np.searchsorted(trt, tt[i] - 1500)
                if k < len(trt) and trt[k] <= tt[i]:
                    continue
                if tt[i] - last < 3000:
                    continue
                gap_prev = (tt[i] - last) / 1000 if last > 0 else np.nan
                last = tt[i]
                j = lo  # snapshot at the start of the reference window
                # team price: ask of the team (token-0 ask for team 0; 1 - token-0 bid for team 1)
                ask_before = b.ba.iloc[j] if team == 0 else 1 - b.bb.iloc[j]
                ask_now = b.ba.iloc[i] if team == 0 else 1 - b.bb.iloc[i]
                rows.append({"a": a_, "team": team, "t": tt[i], "ref": ref, "rem": D[i], "ask_before": ask_before, "ask_now": ask_now,
                             "gap_prev_s": gap_prev})
    ev = pd.DataFrame(rows)
    for g in ("W", "pack"):
        o = d[d.grp == g]
        lag, acted = [], []
        for a_, team, t in zip(ev.a, ev.team, ev.t):
            s = o[(o.a == a_) & (o.team == team)].sign_ms.to_numpy()
            s = s[(s >= t) & (s <= t + 2000)]
            acted.append(len(s) > 0)
            lag.append((s.min() - t) / 1000 if len(s) else np.nan)
        ev[f"acted_{g}"] = acted
        ev[f"lag_{g}"] = lag
    ev["jump"] = (ev.ask_now - ev.ask_before).round(3)
    res = {"events": len(ev), "acted_W": int(ev.acted_W.sum()), "acted_pack": int(ev.acted_pack.sum()),
           "lag_W_q": ev.lag_W.dropna().quantile([.1, .25, .5, .75, .9]).round(3).tolist(),
           "lag_pack_q": ev.lag_pack.dropna().quantile([.1, .25, .5, .75, .9]).round(3).tolist(),
           "acted_W_by_both": int((ev.acted_W & ev.acted_pack).sum())}
    for k, s in ev.groupby("acted_W"):
        res[f"features_acted_W_{k}"] = {"ref_med": round(float(s.ref.median()), 0), "rem_frac_med": round(float((s.rem / s.ref).median()), 3),
                                         "ask_now_med": round(float(s.ask_now.median()), 3), "jump_dist": s.jump.value_counts(normalize=True).head(5).round(3).to_dict(),
                                         "gap_prev_med": round(float(s.gap_prev_s.median()), 1), "pack_acted_share": round(float(s.acted_pack.mean()), 3)}
    ev.to_parquet(OUT / "collapse_events_dev.parquet", index=False)
    json.dump(res, open(RES / "results/collapse_detail.json", "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
