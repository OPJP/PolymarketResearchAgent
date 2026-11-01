"""X194 (mechanics panel iter-13 P1), first pass: the operator's in-play SPORTS quoting on 0x52661b8e
('TommyLeePeeecan'), September 2026 (development, before H). Steps 1-2 (design fingerprint) and a first step-4 check
(its maker prices against the last public print). Calldata decoded with code/fetch_calldata.py into
.cache/re/tommy-cs2-maker/sib5266_sport/calldata (1,326 txs of 1,334 sport trades in 421 events).

Fingerprint: maker / taker share, BUY share, whole cents, band [0.05, 0.95], sizes, orders per 50-ms burst and slot
offsets below the burst top, salts magnitude. Price: for a sample of its markets (most maker orders first, MLB and
football), the taker tape from data-api (taker_only rows, sibling transactions excluded), last print stamped before
signing, within one tick, median offset, by print age; in-play share (orders after the scheduled start).
Output: results/sports_twin.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker/sib5266_sport"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
SIB = "0x52661b8e13158f23d94a9e8302ab0295704c22ac"
NM = 40


def main():
    a = pd.read_parquet(OUT / "activity_sep_sport.parquet")
    c = pd.concat([pd.read_parquet(p) for p in sorted((OUT / "calldata").glob("*.parquet"))], ignore_index=True)
    c = c[c.idx > -9]
    c["maker"] = c.maker.str.lower()
    tx_role = c.groupby("tx").apply(lambda g: "maker" if ((g.idx >= 0) & (g.maker == SIB)).any() else ("taker" if ((g.idx == -1) & (g.maker == SIB)).any() else "none"), include_groups=False)
    own = c[(c.maker == SIB)].copy()
    own["role"] = np.where(own.idx >= 0, "maker", "taker")
    own = own.drop_duplicates(["salt", "sign_ms", "role"])
    tok2cid = dict(zip(a.drop_duplicates("cid").cid, a.drop_duplicates("cid").cid))
    # map token -> (cid, oi) from activity
    tm = a.drop_duplicates(["cid", "oi"])
    act_tok = {}
    for r in a.itertuples():
        pass
    out = {"sport_trades": int(len(a)), "txs": int(a.tx.nunique()), "decoded_txs": int(c.tx.nunique()), "events": int(a.ev.nunique()),
           "markets": int(a.cid.nunique()), "by_prefix": a.pre.value_counts().head(12).to_dict(),
           "tx_role": tx_role.value_counts().to_dict()}
    mk = own[own.role == "maker"].copy()
    tk = own[own.role == "taker"].copy()
    out["orders"] = {"maker": int(len(mk)), "taker": int(len(tk))}
    for nm, d in (("maker", mk), ("taker", tk)):
        if len(d) == 0:
            continue
        p = d.price.astype(float)
        out[f"{nm}_fingerprint"] = {"buy_share": round(float((d.side == 0).mean()), 3),
                                    "whole_cents": round(float((np.abs(p * 100 - np.round(p * 100)) < 1e-6).mean()), 3),
                                    "in_band_0.05_0.95": round(float(((p >= 0.05 - 1e-9) & (p <= 0.95 + 1e-9)).mean()), 3),
                                    "size_top": {str(k): int(v) for k, v in d.shares.round(1).value_counts().head(8).items()},
                                    "sig_types": {str(k): int(v) for k, v in d.sig_type.value_counts().items()},
                                    "salt_median": float(pd.to_numeric(d.salt, errors="coerce").median())}
    # bursts of maker orders per token
    mk = mk.sort_values(["token_id", "sign_ms"])
    mk["burst"] = (mk.groupby("token_id").sign_ms.diff().fillna(1e12) > 50).cumsum()
    bs = mk.groupby("burst").size()
    mk["top"] = mk.groupby("burst").price.transform("max")
    mk["slot"] = np.round((mk.top - mk.price) * 100).astype(int)
    out["maker_bursts"] = {"bursts": int(len(bs)), "orders_per_burst": {str(k): int(v) for k, v in bs.value_counts().sort_index().head(8).items()},
                           "slot_below_top": {str(k): int(v) for k, v in mk.slot.value_counts().sort_index().head(8).items()}}
    # price vs last print on a sample of markets
    tokinfo = c.drop_duplicates("token_id")[["token_id", "condition_id"]]
    cid_of_tok = dict(zip(tokinfo.token_id.astype(str), tokinfo.condition_id))
    mk["cid"] = mk.token_id.astype(str).map(cid_of_tok)
    pre_of = dict(zip(a.cid, a.pre))
    mk["pre"] = mk.cid.map(pre_of)
    sample = mk.groupby("cid").size().sort_values(ascending=False)
    sample = list(sample.index[:NM])
    pm = PolymarketData()
    sib_tx = set(c.tx)
    rows = []
    for cid in sample:
        g = mk[mk.cid == cid]
        t0, t1 = int(g.sign_ms.min() / 1000) - 3 * 3600, int(g.sign_ms.max() / 1000) + 600
        try:
            tr, *_ = pm.market_trades(cid, t0, t1, taker_only=True, max_rows=60000)
        except Exception as e:  # noqa: BLE001
            print("tape fail", cid, repr(e)[:100])
            continue
        if not tr:
            continue
        d = pd.DataFrame(tr)
        d = d[~d.transactionHash.isin(sib_tx)].sort_values("timestamp")
        if len(d) < 5:
            continue
        ts = d.timestamp.to_numpy(float)
        asset = d.asset.astype(str).to_numpy()
        price = d.price.astype(float).to_numpy()
        oi = d.outcomeIndex.astype(int).to_numpy()
        p0 = np.where(oi == 0, price, 1 - price)
        for r in g.itertuples():
            t = r.sign_ms / 1000
            j = np.searchsorted(ts, t, side="left") - 1
            if j < 0:
                continue
            # token of the order: outcome index from the tape's asset ids
            same = asset == str(r.token_id)
            if same.any():
                oi_r = int(oi[same][0])
            else:
                continue
            lp = p0[j] if oi_r == 0 else 1 - p0[j]
            rows.append({"cid": cid, "pre": r.pre, "p": float(r.price), "lp": round(float(lp), 2), "age": t - ts[j],
                         "top": float(r.top), "slot": int(r.slot)})
    x = pd.DataFrame(rows)
    if len(x):
        x["off"] = np.round((x.p - x.lp) * 100)
        x["hit"] = np.abs(x.p - x.lp) <= 0.0101
        x["hit_top"] = np.abs(x.top - x.lp) <= 0.0101
        x["grp"] = np.where(x.pre == "mlb", "mlb", "football")
        out["price_vs_last_print"] = {"orders": int(len(x)), "markets": int(x.cid.nunique()),
                                      "within_tick": round(float(x.hit.mean()), 3),
                                      "exact": round(float((x.off == 0).mean()), 3),
                                      "median_offset_c": float(x.off.median()),
                                      "burst_top_within_tick": round(float(x.hit_top.mean()), 3),
                                      "by_group": {k: {"orders": int(len(g)), "within_tick": round(float(g.hit.mean()), 3), "median_offset_c": float(g.off.median()),
                                                       "top_within_tick": round(float(g.hit_top.mean()), 3)} for k, g in x.groupby("grp")},
                                      "by_print_age": {str(k): round(float(g.hit.mean()), 3) for k, g in x.groupby(pd.cut(x.age, [-1, 10, 60, 600, 1e9]), observed=True)},
                                      "offset_hist": {str(int(k)): int(v) for k, v in x.off.value_counts().sort_index().items() if abs(k) <= 6}}
    (RES / "sports_twin.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
