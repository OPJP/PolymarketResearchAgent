"""Iteration 8, X114 (assumptions panel iter7 P3): is the shared push feed multi-sport? In CS2 the feed's subscribers
sign in a fixed order (P4e 0, 0x2005d16a +25 ms, the wallet +50, 0xf1ee4842 ~+150-209, the 0x8a80528d / 0xddb6e624
process ~+203, P93 ~+400). Here: same-token BUY taker co-signs of 0x2005d16a and the 0x8a80528d / 0xddb6e624 process in
NON-esports markets (football, NBA, tennis) of 16-22 Oct (development; public activity through the polyrea adapter,
calldata through eth_getTransactionByHash). Signature of one multi-sport source: co-signs at a fixed lag (~+180 ms,
IQR tens of ms) with a 30-s shift null near 0. Output: results/multisport_fanout.json; decoded orders in
.cache/re/tommy-cs2-maker/multisport/ (decoded fields only).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from fetch_calldata import rows_of  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker/multisport"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
H = 1792713600
START = 1792108800
R2 = "0x2005d16a84ceefa912d4e380cd32e7ff827875ea"
PAIR = ["0x8a80528dce46711a54aa3455c2cc81dea51e11c5", "0xddb6e6246546230503f153506ac1e9914978b9b3"]
F1 = "0xf1ee4842fa0c7283632185e42577027452d4519c"
ESPORT = ("cs2", "dota2", "lol", "val", "codmw", "r6")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pm = PolymarketData()
    acts = {}
    for w in [R2] + PAIR + [F1]:
        rows, _, _ = pm.activity(w, start=START, end=H - 1)
        df = pd.DataFrame(rows)
        df = df[df["type"] == "TRADE"].copy()
        df["pre"] = df["eventSlug"].astype(str).str.split("-").str[0]
        acts[w] = df[~df["pre"].isin(ESPORT)]
        print(w[:10], len(df), "non-esports", len(acts[w]), flush=True)
    m_r2 = set(acts[R2]["conditionId"])
    m_pair = set(acts[PAIR[0]]["conditionId"]) | set(acts[PAIR[1]]["conditionId"])
    m_f1 = set(acts[F1]["conditionId"])
    both = m_r2 & (m_pair | m_f1)
    print("overlap markets", len(both), flush=True)
    txs = set()
    for w, df in acts.items():
        txs |= set(df.loc[df["conditionId"].isin(both), "transactionHash"])
    txs = sorted(txs)
    done = set()
    parts = sorted(OUT.glob("part_*.parquet"))
    for p in parts:
        done |= set(pd.read_parquet(p, columns=["tx"]).tx)
    todo = [t for t in txs if t not in done]
    print("txs", len(txs), "todo", len(todo), flush=True)
    cli = httpx.Client(timeout=40, headers={"User-Agent": "polyrea-research"})
    buf, k = [], len(parts)
    for i in range(0, len(todo), 40):
        part = todo[i:i + 40]
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(part)]
        res = None
        for attempt in range(8):
            try:
                r = cli.post("https://polygon-bor-rpc.publicnode.com", json=body)
                if r.status_code == 429:
                    time.sleep(3 + 3 * attempt)
                    continue
                res = r.json()
                if isinstance(res, list):
                    break
            except Exception:  # noqa: BLE001
                time.sleep(3 + 3 * attempt)
        for x in res or []:
            t = x.get("result") if isinstance(x, dict) else None
            if t:
                buf += rows_of(t)
        if len(buf) > 20000 or i + 40 >= len(todo):
            if buf:
                pd.DataFrame(buf).astype({"salt": str, "token_id": str}).to_parquet(OUT / f"part_{k}.parquet", index=False)
                k += 1
                buf = []
        time.sleep(0.25)
    D = pd.concat([pd.read_parquet(p) for p in sorted(OUT.glob("part_*.parquet"))]).drop_duplicates(["tx", "idx"])
    D["maker"] = D.maker.str.lower()
    T = D[(D.idx == -1) & (D.side == 0) & (D.sign_ms > 1.7e12) & (D.sign_ms < 1.8e12)].copy()
    slug = {}
    for df in acts.values():
        slug.update(dict(zip(df["asset"].astype(str), df["eventSlug"].astype(str))))
    T["event"] = T.token_id.astype(str).map(slug)
    T["pre"] = T.event.astype(str).str.split("-").str[0]
    res = {"overlap_markets": len(both), "decoded_txs": int(D.tx.nunique()), "taker_buys": T.maker.value_counts().head(6).to_dict()}
    rng = np.random.default_rng(4)

    def cosign(lead, foll, lo, hi):
        a = T[T.maker == lead]
        b = {kk: v.sign_ms.to_numpy(float) for kk, v in T[T.maker.isin(foll)].groupby("token_id")}
        lags, pre, ev = [], [], []
        for r in a.itertuples():
            x = b.get(r.token_id)
            if x is None:
                continue
            d = x - r.sign_ms
            d = d[(d >= lo) & (d <= hi)]
            if len(d):
                lags.append(float(d[np.argmin(np.abs(d))]))
                pre.append(r.pre)
                ev.append(r.event)
        nul = []
        for _ in range(20):
            c = 0
            for r in a.itertuples():
                x = b.get(r.token_id)
                if x is None:
                    continue
                d = x - (r.sign_ms + rng.choice([-1, 1]) * 30000)
                c += bool(((d >= lo) & (d <= hi)).any())
            nul.append(c)
        L = np.array(lags)
        o = {"lead_takes": int(len(a)), "pairs": int(len(L)), "shift30s_null_mean": round(float(np.mean(nul)), 2),
             "median_ms": round(float(np.median(L)), 1) if len(L) else None,
             "iqr_ms": round(float(np.subtract(*np.percentile(L, [75, 25]))), 1) if len(L) else None,
             "events": int(len(set(ev)))}
        if len(L):
            dfp = pd.DataFrame({"lag": L, "pre": pre})
            o["by_sport"] = dfp.groupby("pre").lag.agg(["count", "median"]).round(1).to_dict("index")
            o["hist_100ms"] = np.histogram(L, bins=np.arange(lo, hi + 1, 100))[0].tolist()
        return o
    res["r2_then_pair"] = cosign(R2, PAIR, -500, 500)
    res["r2_then_f1ee"] = cosign(R2, [F1], -500, 500)
    res["pair0_then_pair1"] = cosign(PAIR[0], [PAIR[1]], -300, 300)
    res["f1ee_then_pair"] = cosign(F1, PAIR, -500, 500)
    print(json.dumps(res, indent=1, default=str))
    json.dump(res, open(RES / "multisport_fanout.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
