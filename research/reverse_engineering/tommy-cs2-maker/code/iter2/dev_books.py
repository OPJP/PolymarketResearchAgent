"""Quote placement against the recorded CLOB book (clob_wallets, development block 10-31 12-18 UTC only, units that
started in it). For every wallet order decoded from calldata_dev (signing ms): the last book snapshot of the market
received before the signing time (token-0 book; token-1 = 1 - price, sides swapped), best bid / ask, and the order's
price relative to them. Also: the book level at the order's price in the first snapshot 0.3-3 s after signing vs the
last before (did ~shares appear at that level, i.e. the order rested). Output: results/dev_books.json."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import live  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
BLOCK0 = 1793448000  # 2026-10-31 12:00 UTC (development block)


def read_books(tok0: set, start: float, end: float):
    recs = []
    h = int(start // 3600 * 3600)
    while h < end:
        try:
            for r in live.iter_live("clob_wallets", max(h, start), min(h + 3600, end)):
                if r.get("a") in tok0 and r.get("k") in ("q", "f"):
                    b = r.get("b") or []
                    o = r.get("o") or []
                    recs.append((r["t"], r["a"], r["k"], [(float(p), float(z)) for p, z in b], [(float(p), float(z)) for p, z in o]))
        except Exception as e:  # noqa: BLE001  (zlib.error on a corrupt / open member: keep what was read)
            print("hour", time.strftime("%H", time.gmtime(h)), "stopped:", type(e).__name__, flush=True)
        h += 3600
    return recs


def main():
    end = min(time.time() - 60, BLOCK0 + 6 * 3600)
    a = pd.read_parquet(OUT / "activity_devblocks.parquet")
    cids = sorted(a.conditionId.unique())
    pm = PolymarketData()
    mk, _ = pm.markets_by_condition(cids)
    tok = {}
    for cid, x in mk.items():
        t = x["clobTokenIds"]
        t = json.loads(t) if isinstance(t, str) else t
        tok[str(t[0])] = (cid, 0)
        tok[str(t[1])] = (cid, 1)
    tok0 = {t for t, (c, i) in tok.items() if i == 0}
    recs = read_books(tok0, BLOCK0, end)
    print("book records", len(recs), flush=True)
    bk = pd.DataFrame(recs, columns=["t", "a", "k", "b", "o"]).sort_values("t")
    bk["bb"] = bk.b.map(lambda L: max((p for p, z in L), default=np.nan))
    bk["ba"] = bk.o.map(lambda L: min((p for p, z in L), default=np.nan))
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    d = d[(d.sign_ms > 1.79e12) & (d.sign_ms < 1.8e12)]
    w = d[d.maker == WALLET].drop_duplicates(["maker", "token_id", "price", "sign_ms", "side"]).copy()
    w["role"] = np.where(w.idx == -1, "taker", "maker")
    w["cid"] = w.token_id.map(lambda t: tok.get(str(t), (None, -1))[0])
    w["oi"] = w.token_id.map(lambda t: tok.get(str(t), (None, -1))[1])
    w = w[w.cid.notna()]
    c0 = {c: t for t, (c, i) in tok.items() if i == 0}
    rows = []
    for (cid, oi, role, side), g in w.groupby(["cid", "oi", "role", "side"]):
        b = bk[bk.a == c0[cid]]
        if len(b) == 0:
            continue
        tt = b.t.to_numpy()
        for s, q, sh in zip(g.sign_ms, g.price, g.shares):
            j = np.searchsorted(tt, s, side="left") - 1
            if j < 0:
                continue
            age = (s - tt[j]) / 1000
            bb0, ba0 = b.bb.iloc[j], b.ba.iloc[j]
            bid, ask = (bb0, ba0) if oi == 0 else (1 - ba0, 1 - bb0)
            # level size before / after at the order price, in token-0 terms
            p0, sd = (q, "b") if oi == 0 else (round(1 - q, 3), "o")
            def lvl(L):
                return sum(z for p, z in L if abs(p - p0) < 1e-6)
            before = lvl(b[sd].iloc[j])
            k = np.searchsorted(tt, s + 300, side="left")
            after = lvl(b[sd].iloc[k]) if k < len(b) and tt[k] < s + 3000 else np.nan
            rows.append({"cid": cid, "oi": oi, "role": role, "side": side, "q": q, "shares": sh, "bid": bid, "ask": ask, "book_age_s": age,
                         "q_minus_bid": round(q - bid, 3), "q_minus_ask": round(q - ask, 3), "lvl_before": before, "lvl_after": after})
    x = pd.DataFrame(rows)
    x.to_parquet(OUT / "dev_books_orders.parquet", index=False)
    res = {"book_records": len(recs), "wallet_orders": int(len(w)), "with_book": len(x), "by_role": x.role.value_counts().to_dict() if len(x) else {}}
    for role, s in x.groupby("role"):
        s = s[s.book_age_s < 30]
        res[role] = {"n": len(s), "q_minus_bid": s.q_minus_bid.value_counts(normalize=True).head(8).round(3).to_dict(),
                     "q_minus_ask": s.q_minus_ask.value_counts(normalize=True).head(8).round(3).to_dict(),
                     "at_or_above_bid_share": round(float((s.q_minus_bid >= -0.0005).mean()), 3),
                     "spread_q": (s.ask - s.bid).round(3).quantile([.1, .5, .9]).tolist(),
                     "shares_dist": s.shares.round(0).value_counts(normalize=True).head(5).round(3).to_dict(),
                     "level_grew_by_shares": round(float(((s.lvl_after - s.lvl_before - s.shares).abs() < 1).mean()), 3),
                     "book_age_q": s.book_age_s.quantile([.5, .9]).round(2).tolist()}
    json.dump(res, open(RES / "results/dev_books.json", "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
