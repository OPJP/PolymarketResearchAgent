"""X196 (mechanics panel iter-13 P3), first pass: the operator's two-sided esports quoting of July-August on
0x52661b8e ('TommyLeePeeecan'; BUY ~ SELL) as an uncensored view of its value, before the push-feed era.
Sample: its CS2 trades of 07-01..07-13 and Dota trades of 08-01..08-13 (activity, development), calldata decoded with
code/fetch_calldata.py (sib5266_jul). For its maker orders: within one tick of the last clean print (sibling
transactions excluded) stamped before signing and the median offset; two-sided pairs = a BUY and a SELL maker order on
the same token signed within 2 s: their mid against the last print (|mid - print| <= 0.5c share) and against later
prints (print(t + L) for L = 0, 5, 10, 20, 30, 60 s: the lead profile). Output: results/july_twosided.json
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker/sib5266_jul"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
SIB = "0x52661b8e13158f23d94a9e8302ab0295704c22ac"
H = 1792713600
NM = 30


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pm = PolymarketData()
    rows, *_ = pm.activity(SIB, 1781000000, H - 1)
    d = pd.DataFrame(rows)
    d = d[d["type"] == "TRADE"].copy()
    d["pre"] = d.eventSlug.fillna("").str.split("-").str[0]
    t = pd.to_datetime(d.timestamp, unit="s")
    sel = ((d.pre == "cs2") & (t >= "2026-07-01") & (t < "2026-07-14")) | ((d.pre == "dota2") & (t >= "2026-08-01") & (t < "2026-08-14"))
    d = d[sel]
    tx = d.drop_duplicates("transactionHash")[["transactionHash", "timestamp"]].rename(columns={"transactionHash": "tx", "timestamp": "bts"})
    tx = tx.sample(n=min(len(tx), 1800), random_state=0)
    tx.to_parquet(OUT / "txs.parquet", index=False)
    if not (OUT / "calldata").exists() or not list((OUT / "calldata").glob("*.parquet")):
        subprocess.run([sys.executable, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/fetch_calldata.py"), str(OUT / "txs.parquet"), "40", "sib5266_jul/calldata"], check=False)
    c = pd.concat([pd.read_parquet(p) for p in sorted((OUT / "calldata").glob("*.parquet"))], ignore_index=True)
    c = c[c.idx > -9]
    c["maker"] = c.maker.str.lower()
    own = c[(c.maker == SIB) & (c.idx >= 0)].drop_duplicates(["salt", "sign_ms"]).copy()
    tk = c[(c.maker == SIB) & (c.idx == -1)].drop_duplicates(["salt", "sign_ms"])
    out = {"trades_in_window": int(len(d)), "txs_sampled": int(len(tx)), "maker_orders": int(len(own)), "taker_orders": int(len(tk)),
           "maker_buy_share": round(float((own.side == 0).mean()), 3) if len(own) else None,
           "maker_whole_cents": round(float((np.abs(own.price * 100 - np.round(own.price * 100)) < 1e-6).mean()), 3) if len(own) else None,
           "maker_sizes": {str(k): int(v) for k, v in own.shares.round(0).value_counts().head(6).items()}}
    cid_of = dict(zip(d.asset.astype(str), d.conditionId))
    oi_of = dict(zip(d.asset.astype(str), d.outcomeIndex.astype(int)))
    own["cid"] = own.token_id.astype(str).map(cid_of)
    own["oi"] = own.token_id.astype(str).map(oi_of)
    own = own[own.cid.notna()]
    sib_tx = set(c.tx)
    mk = own.groupby("cid").size().sort_values(ascending=False)
    rows_o, rows_p = [], []
    for cid in list(mk.index[:NM]):
        g = own[own.cid == cid].sort_values("sign_ms")
        t0, t1 = int(g.sign_ms.min() / 1000) - 3 * 3600, int(g.sign_ms.max() / 1000) + 3600
        try:
            tr, *_ = pm.market_trades(cid, t0, t1, taker_only=True, max_rows=60000)
        except Exception as e:  # noqa: BLE001
            print("tape fail", repr(e)[:80])
            continue
        if not tr:
            continue
        x = pd.DataFrame(tr)
        x = x[~x.transactionHash.isin(sib_tx)].sort_values("timestamp")
        if len(x) < 10:
            continue
        ts = x.timestamp.to_numpy(float)
        p0 = np.where(x.outcomeIndex.astype(int).to_numpy() == 0, x.price.astype(float).to_numpy(), 1 - x.price.astype(float).to_numpy())

        def pr_at(tq, oi):
            j = np.searchsorted(ts, tq, side="left") - 1
            if j < 0:
                return np.nan
            v = p0[j]
            return v if oi == 0 else 1 - v
        for r in g.itertuples():
            tq = r.sign_ms / 1000
            lp = pr_at(tq, r.oi)
            if np.isfinite(lp):
                rows_o.append({"cid": cid, "side": int(r.side), "p": float(r.price), "lp": round(float(lp), 2)})
        b = g[g.side == 0]
        s = g[g.side == 1]
        st = s.sign_ms.to_numpy()
        for r in b.itertuples():
            j = np.searchsorted(st, r.sign_ms)
            best = None
            for jj in (j - 1, j):
                if 0 <= jj < len(st) and abs(st[jj] - r.sign_ms) <= 2000 and s.token_id.iloc[jj] == r.token_id:
                    best = jj
            if best is None:
                continue
            mid = (r.price + s.price.iloc[best]) / 2
            tq = max(r.sign_ms, st[best]) / 1000
            rec = {"cid": cid, "mid": float(mid), "spread": float(s.price.iloc[best] - r.price)}
            for L in (0, 5, 10, 20, 30, 60, 120):
                rec[f"p{L}"] = pr_at(tq + L, r.oi)
            rows_p.append(rec)
    O = pd.DataFrame(rows_o)
    if len(O):
        O["off"] = np.round((O.p - O.lp) * 100)
        out["maker_vs_last_print"] = {"orders": int(len(O)), "markets": int(O.cid.nunique()),
                                      "within_tick": round(float((np.abs(O.p - O.lp) <= 0.0101).mean()), 3),
                                      "median_offset_buy_c": float(O[O.side == 0].off.median()) if (O.side == 0).any() else None,
                                      "median_offset_sell_c": float(O[O.side == 1].off.median()) if (O.side == 1).any() else None}
    P = pd.DataFrame(rows_p)
    if len(P):
        out["two_sided_pairs"] = {"pairs": int(len(P)), "markets": int(P.cid.nunique()), "spread_median_c": round(float(P.spread.median() * 100), 2)}
        for L in (0, 5, 10, 20, 30, 60, 120):
            dd = (P.mid - P[f"p{L}"]).dropna()
            out["two_sided_pairs"][f"L{L}"] = {"n": int(len(dd)), "abs_le_half_c": round(float((dd.abs() <= 0.0051).mean()), 3),
                                               "within_1c": round(float((dd.abs() <= 0.0101).mean()), 3), "mae_c": round(float(dd.abs().mean() * 100), 2)}
    (RES / "july_twosided.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
