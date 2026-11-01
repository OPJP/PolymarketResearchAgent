"""Maker quote placement vs a touch rebuilt from the full matched-order record (mechanics panel X: child-order quote
function; B3). For every wallet maker BUY order (signing time s, token T, price q):
  - bid_T(s): best price among OTHER makers' BUY orders on T that were signed before s and filled after s (block time),
    i.e. known to be resting at s (a lower bound on the true best bid: cancelled orders are invisible);
  - ask_T(s): best (lowest) of OTHER makers' SELL orders on T and 1 - BUY orders on the complement resting at s;
  - last public print on T before s (wallet txs excluded);
  - own last fill on T and on the complement, on the match clock (taker sign + 1 s), before s.
Burst = wallet orders on the same (market, token) signed within 300 ms; level 0 = highest price.
Scores: exact (tick 0.001 = whole cent here) and within 1c, BUILD vs VALIDATE, for anchors + offset fitted on BUILD.
Development data 16-22 Oct only."""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import H, OUT, RES, SPLIT, WALLET, TAPES  # noqa: E402


def main():
    o = pd.read_parquet(OUT / "orders.parquet")
    o = o[(o.sign_ms > 1.7e12) & (o.sign_ms < 1.8e12)].copy()
    mk = o[o.role == "maker"].copy()
    # matched-order record: all maker orders (idx >= 0) with fill tx block time; need block times for calldata_pub
    cols = ["tx", "idx", "maker", "side", "token_id", "price", "sign_ms", "block", "condition_id"]
    pub = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(OUT / "calldata_pub/*.parquet")))])
    al = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["bts"])
    # block -> ts map from wallet txs (bts) + linear interpolation (Polygon ~2 s blocks)
    bmap = al[["block", "bts"]].drop_duplicates("block").sort_values("block")
    bb, bt = bmap.block.to_numpy(), bmap.bts.to_numpy().astype(float)
    pub["bts"] = np.interp(pub.block.to_numpy(), bb, bt)
    rec = pd.concat([pub, al]).drop_duplicates(["tx", "idx"])
    rec = rec[(rec.idx >= 0) & (rec.maker != WALLET) & (rec.sign_ms > 1.7e12) & (rec.sign_ms < 1.8e12)]
    # first fill time per order (by maker+token+price+sign_ms identity)
    rec = rec.groupby(["maker", "token_id", "side", "price", "sign_ms"], as_index=False).agg(fill_ts=("bts", "min"), cid=("condition_id", "first"))
    # token -> complement
    tm = {}
    for cid, g in o.groupby("cid"):
        toks = g.drop_duplicates("oi").set_index("oi").token_id.to_dict()
        if 0 in toks and 1 in toks:
            tm[toks[0]] = toks[1]; tm[toks[1]] = toks[0]
    # own fills on the match clock
    w = al[(al.maker == WALLET)].copy()
    tk = al[al.idx == -1][["tx", "sign_ms"]].rename(columns={"sign_ms": "tsign"})
    w = w.merge(tk, on="tx", how="left")
    w["match_ms"] = np.where((w.tsign > 1.7e12) & (w.tsign < 1.8e12), w.tsign + 1000, w.bts * 1000.0)
    w = w[w.side == 0][["token_id", "price", "match_ms"]].sort_values("match_ms")
    out = []
    for cid, g in mk.groupby("cid"):
        g = g.sort_values("sign_ms")
        r = rec[rec.cid == cid]
        toks = g.token_id.unique().tolist()
        allt = set(toks) | {tm.get(t) for t in toks if tm.get(t)}
        tp = TAPES / f"{cid}_tkw.parquet"
        tape = None
        if tp.exists():
            tape = pd.read_parquet(tp, columns=["timestamp", "price", "outcomeIndex", "transactionHash"])
            tape = tape[~tape.transactionHash.isin(set(al.tx))].sort_values("timestamp")
        for t in allt:
            if t is None:
                continue
            gt = g[g.token_id == t]
            if len(gt) == 0:
                continue
            comp = tm.get(t)
            bids = r[(r.token_id == t) & (r.side == 0)]
            asks_s = r[(r.token_id == t) & (r.side == 1)]
            asks_c = r[(r.token_id == comp) & (r.side == 0)] if comp else r.iloc[0:0]
            oi = int(gt.oi.iloc[0])
            ownT = w[w.token_id == t]; ownC = w[w.token_id == comp] if comp else w.iloc[0:0]
            if tape is not None and len(tape):
                p0 = np.where(tape.outcomeIndex.astype(int) == oi, tape.price.astype(float), 1 - tape.price.astype(float))
                tts = tape.timestamp.to_numpy()
            for s, q, sh in zip(gt.sign_ms.to_numpy(), gt.price.to_numpy(), gt.shares.to_numpy()):
                ss = s / 1000.0
                rb = bids[(bids.sign_ms < s) & (bids.fill_ts > ss)]
                ra1 = asks_s[(asks_s.sign_ms < s) & (asks_s.fill_ts > ss)]
                ra2 = asks_c[(asks_c.sign_ms < s) & (asks_c.fill_ts > ss)]
                bid = rb.price.max() if len(rb) else np.nan
                ask = min(ra1.price.min() if len(ra1) else np.inf, (1 - ra2.price.max()) if len(ra2) else np.inf)
                last = np.nan
                if tape is not None and len(tape):
                    j = np.searchsorted(tts, ss, side="right") - 1
                    last = p0[j] if j >= 0 else np.nan
                jT = np.searchsorted(ownT.match_ms.to_numpy(), s, side="right") - 1
                jC = np.searchsorted(ownC.match_ms.to_numpy(), s, side="right") - 1
                out.append({"cid": cid, "token": t, "s": s, "q": q, "shares": sh, "bid": bid, "ask": ask if np.isfinite(ask) else np.nan,
                            "last": last, "ownT_p": ownT.price.to_numpy()[jT] if jT >= 0 else np.nan,
                            "ownT_age": (s - ownT.match_ms.to_numpy()[jT]) / 1000 if jT >= 0 else np.nan,
                            "ownC_p": ownC.price.to_numpy()[jC] if jC >= 0 else np.nan,
                            "ownC_age": (s - ownC.match_ms.to_numpy()[jC]) / 1000 if jC >= 0 else np.nan, "gs": int(gt.gs_ts.iloc[0])})
    x = pd.DataFrame(out).sort_values(["cid", "token", "s"])
    # bursts
    x["burst"] = ((x.groupby(["cid", "token"]).s.diff() > 300) | x.groupby(["cid", "token"]).s.diff().isna()).cumsum()
    x["level"] = x.groupby("burst").q.rank(ascending=False, method="first") - 1
    x["top"] = x.groupby("burst").q.transform("max")
    x.to_parquet(OUT / "price_touch.parquet", index=False)
    x["split"] = np.where(x.gs >= SPLIT, "VALIDATE", "BUILD")
    res = {"orders": len(x), "bursts": int(x.burst.nunique()), "bid_known_share": round(float(x.bid.notna().mean()), 3),
           "ask_known_share": round(float(x.ask.notna().mean()), 3)}
    anchors = {"bid": x.bid, "ask_minus": x.ask, "last": x.last.round(2), "ownT": x.ownT_p, "ownC": 1 - x.ownC_p,
               "mid": ((x.bid + x.ask) / 2).round(2)}
    for name, a in anchors.items():
        d = (x.q - a).round(3)
        b = d[x.split == "BUILD"].dropna()
        if len(b) == 0:
            continue
        off = float(b.mode().iloc[0])
        r = {}
        for sp in ("BUILD", "VALIDATE"):
            dd = d[x.split == sp]
            r[sp] = {"coverage": round(float(dd.notna().mean()), 3), "exact_given": round(float((dd.dropna() - off).abs().lt(0.0005).mean()), 3),
                     "within1c_given": round(float((dd.dropna() - off).abs().le(0.0105).mean()), 3),
                     "exact_all": round(float(((dd - off).abs() < 0.0005).sum() / len(dd)), 3)}
        res[name] = {"offset_mode_build": off, "dist_build": b.value_counts(normalize=True).head(6).round(3).to_dict(), **r}
    # burst-top vs bid (join / improve) on tops only
    tops = x[x.level == 0]
    res["top_minus_bid_dist"] = (tops.q - tops.bid).round(3).value_counts(normalize=True).head(8).round(3).to_dict()
    res["top_minus_ask_dist"] = (tops.q - tops.ask).round(3).value_counts(normalize=True).head(8).round(3).to_dict()
    json.dump(res, open(RES / "results/price_touch.json", "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
