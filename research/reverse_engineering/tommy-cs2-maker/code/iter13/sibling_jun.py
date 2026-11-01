"""X185 (iteration 13): the earlier account in June (0x7d67f01d, 06-19..06-30 CS2, BUY and SELL, 5-7-share sizes): maker / taker
split, sides, whole cents, band and the price relation to the last print, as sibling_price.py. Based on the September
script: the same maker process in September (0x7d67f01d, 09-21..09-30, BUY-only, 100 shares) and
whether its takes then sat on the push feed (lag behind P4e's taker orders on the same token, P4e calldata of its
09-26..09-30 transactions on the sibling's September markets). Same metrics as sibling_price.py.
Output: results/sibling_sep.json"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from sibling_price import anchor_metric, describe, tape  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
A = "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14"
P4E = "0x4ebc2722adc772bde8680792d0a6fdf15499a33d"
COLS = ["tx", "idx", "maker", "token_id", "price", "shares", "sign_ms", "salt", "side"]


def load(pat):
    fs = glob.glob(str(OUT / pat))
    if not fs:
        return pd.DataFrame(columns=COLS)
    d = pd.concat([pd.read_parquet(f, columns=COLS) for f in fs])
    d["maker"] = d.maker.str.lower()
    d["token_id"] = d.token_id.astype(str)
    return d[(d.sign_ms > 1.7e12) & (d.sign_ms < 1.8e12)]


def lag_hist(a: pd.DataFrame, ref: pd.DataFrame) -> dict:
    rt = {t: np.sort(g.sign_ms.to_numpy(np.int64)) for t, g in ref.groupby("token_id")}
    lags = []
    for row in a.itertuples():
        s = rt.get(row.token_id)
        if s is None:
            continue
        j = np.searchsorted(s, row.sign_ms)
        cand = []
        if j > 0:
            cand.append(row.sign_ms - s[j - 1])
        if j < len(s):
            cand.append(row.sign_ms - s[j])
        c = min(cand, key=abs)
        if abs(c) <= 2000:
            lags.append(int(c))
    lags = np.array(lags)
    bins = [-2000, -500, -100, -20, 0, 20, 40, 60, 80, 100, 200, 500, 2001]
    return {"sibling_takers": int(len(a)), "on_ref_tokens": int(a.token_id.isin(rt).sum()), "pairs_within_2s": int(len(lags)),
            "bins": bins, "hist": np.histogram(lags, bins=bins)[0].tolist() if len(lags) else [],
            "median_lag_ms_within_500": float(np.median(lags[np.abs(lags) <= 500])) if (np.abs(lags) <= 500).any() else None,
            "share_in_0_100ms": round(float(np.mean((lags >= 0) & (lags < 100))), 3) if len(lags) else None}


def main():
    pm = PolymarketData()
    ca = load("sib7d67_jun/calldata/part_*.parquet")
    act = pd.read_parquet(OUT / "sib7d67_jun/activity_jun.parquet")
    own = set(act.transactionHash)
    mk, _ = pm.markets_by_condition(sorted(act.conditionId.unique()))
    tok2, gs = {}, {}
    for cid, x in mk.items():
        toks = json.loads(x["clobTokenIds"]) if isinstance(x.get("clobTokenIds"), str) else x.get("clobTokenIds")
        for i, t in enumerate(toks):
            tok2[str(t)] = (cid, i)
        g = x.get("gameStartTime") or x.get("startDate")
        try:
            gs[cid] = pd.Timestamp(str(g) + ":00" if str(g).endswith("+00") else g).timestamp()
        except Exception:  # noqa: BLE001
            gs[cid] = None
    ao = ca[(ca.maker == A) & (ca.idx != -1) & ca.token_id.isin(tok2)].drop_duplicates(["salt", "sign_ms"]).copy()
    ao["cid"] = ao.token_id.map(lambda t: tok2[t][0])
    at = ca[(ca.maker == A) & (ca.idx == -1)].drop_duplicates(["salt", "sign_ms"])
    tapes = {}
    for cid in ao.cid.unique():
        if gs.get(cid):
            try:
                tapes[cid] = tape(pm, cid, gs[cid])
            except Exception as e:  # noqa: BLE001
                print("tape fail", cid[:10], type(e).__name__, flush=True)
    p4 = load("p4e_jun_none/calldata/part_*.parquet")
    p4t = p4[(p4.maker == P4E) & (p4.idx == -1)].drop_duplicates(["salt", "sign_ms"])
    out = {"describe": describe(ao), "price": anchor_metric(ao, tapes, own, tok2), "taker_orders": int(len(at)),
           "taker_sizes": at.shares.round(0).value_counts().head(5).to_dict(), "p4e_taker_orders": int(len(p4t)),
           "maker_sides": ca[(ca.maker == A) & (ca.idx != -1)].drop_duplicates(["salt", "sign_ms"]).side.value_counts().to_dict() if "side" in ca else None, "tapes": len(tapes)}
    (RES / "sibling_jun.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
