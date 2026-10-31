"""Iteration 5, assumptions panel iter4 P5 (X62): split the taker leg by size class (caps 1000 / 2000 vs odd sizes).

Per wallet taker order (orders.parquet, 16-22 Oct, in play): premium = limit - first matched level (in the bought
token's terms, from its own tx in calldata_all); move10 = public last print of the bought token at sign + 10 s minus at
sign - 1 s (txs with a wallet order excluded); markouts at +10 / +60 s vs its average fill price; settlement edge
(payout - fill price) per share. Spearman(premium, move10) per class and split (H36), and the daily cap share with a
two-segment change-point (least squares) over the days.
Output: results/taker_size_class.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0, H = 1792540800, 1792713600


def main():
    o = pd.read_parquet(OUT / "orders.parquet")
    t = o[(o.role == "taker") & (o.sign_ms > 1.7e12)].copy()
    t["cls"] = np.where(t.shares.round(0).isin([1000, 2000]), "cap", "odd")
    ca = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "side", "token_id", "price", "fill", "sign_ms", "salt", "oi", "cid"])
    ca["salt"] = ca.salt.astype(str)
    t["salt"] = t.salt.astype(str)
    tkrow = ca[(ca.idx == -1) & (ca.maker == WALLET)][["tx", "salt", "fill"]]
    t = t.merge(tkrow, on="salt", how="left")
    mk = ca[ca.idx >= 0]
    first = {}
    for tx, g in mk[mk.tx.isin(set(t.tx.dropna()))].groupby("tx"):
        first[tx] = g
    pm = pd.read_parquet(OUT / "per_market.parquet", columns=["cid", "win"])
    win = dict(zip(pm.cid, pm.win))
    wtx = set(ca.tx)
    rows = []
    tapes = {}
    for r in t.itertuples():
        g = first.get(r.tx)
        if g is None:
            continue
        x = int(r.oi)
        lv = np.where((g.side.to_numpy() == 1) & (g.oi.to_numpy() == x), g.price.to_numpy(float),
                      np.where((g.side.to_numpy() == 0) & (g.oi.to_numpy() != x), 1 - g.price.to_numpy(float), np.nan))
        lv = lv[np.isfinite(lv)]
        if len(lv) == 0:
            continue
        fsh = g.fill.to_numpy(float)
        avgp = float(np.nansum(np.where(np.isfinite(lv), lv, 0) * fsh[:len(lv)]) / max(fsh[:len(lv)].sum(), 1e-9)) if len(fsh) == len(lv) else float(np.mean(lv))
        if r.cid not in tapes:
            p = OUT / "tapes" / f"{r.cid}_tkw.parquet"
            if p.exists():
                d = pd.read_parquet(p, columns=["timestamp", "price", "outcomeIndex", "transactionHash"])
                d = d[~d.transactionHash.isin(wtx)].sort_values("timestamp")
                tapes[r.cid] = (d.timestamp.to_numpy(float), np.where(d.outcomeIndex.to_numpy(int) == 0, d.price.to_numpy(float), 1 - d.price.to_numpy(float)))
            else:
                tapes[r.cid] = None
        tp = tapes[r.cid]
        if tp is None:
            continue
        ts, p0 = tp

        def px(tt):
            j = int(np.searchsorted(ts, tt, side="right")) - 1
            return np.nan if j < 0 else (p0[j] if x == 0 else 1 - p0[j])

        s = r.sign_ms / 1000.0
        if s < r.gs_ts:
            continue
        w = win.get(r.cid)
        rows.append({"cid": r.cid, "gs": r.gs_ts, "day": pd.Timestamp(r.gs_ts, unit="s").strftime("%m-%d"), "cls": r.cls,
                     "shares": r.shares, "filled": r.filled, "fill_frac": r.fill_frac, "premium": round(float(r.price - lv.min()), 4),
                     "move10": px(s + 10) - px(s - 1), "mk10": px(s + 10) - avgp, "mk60": px(s + 60) - avgp,
                     "settle": ((1.0 if w == x else 0.0) - avgp) if w is not None else np.nan, "usd": float(r.filled) * avgp})
    D = pd.DataFrame(rows)
    D["split"] = np.where(D.gs < VAL0, "BUILD", "VALIDATE")
    res = {}
    for (sp, c), g in D.groupby(["split", "cls"]):
        ok = g.premium.notna() & g.move10.notna()
        rho = stats.spearmanr(g.premium[ok], g.move10[ok])[0] if ok.sum() > 10 else None
        wsum = g.filled.sum()
        res[f"{sp}_{c}"] = {"n": int(len(g)), "fill_frac_median": round(float(g.fill_frac.median()), 3),
                            "spearman_premium_move10": round(float(rho), 3) if rho is not None else None,
                            "premium_mean_c": round(float(100 * g.premium.mean()), 2),
                            "move10_mean_c": round(float(100 * g.move10.mean()), 2),
                            "markout10_c_shw": round(float(100 * np.nansum(g.mk10 * g.filled) / max(g.filled[g.mk10.notna()].sum(), 1e-9)), 2),
                            "markout60_c_shw": round(float(100 * np.nansum(g.mk60 * g.filled) / max(g.filled[g.mk60.notna()].sum(), 1e-9)), 2),
                            "settle_edge_pct_usd": round(float(100 * np.nansum(g.settle * g.filled) / max(g.usd.sum(), 1e-9)), 2),
                            "move10_up_share": round(float((g.move10 > 0.005).mean()), 3)}
    daily = D.groupby("day").apply(lambda g: (g.cls == "cap").mean()).round(3).to_dict()
    # two-segment change point on the daily cap share
    vals = np.array(list(daily.values()))
    best = None
    for k in range(1, len(vals)):
        sse = ((vals[:k] - vals[:k].mean()) ** 2).sum() + ((vals[k:] - vals[k:].mean()) ** 2).sum()
        if best is None or sse < best[0]:
            best = (sse, k)
    res["daily_cap_share"] = daily
    res["cap_share_changepoint_after_day"] = list(daily)[best[1] - 1] if best else None
    (RES / "taker_size_class.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
