"""X142 (panel iter12 assumptions P3): data for the settlement-switch natural experiment (spot -> TWAP-30 on 08-07, -> TWAP-60 on 08-14). Same design as code13/fetch_stable.py, other dates.

Pre-registered sample (written 2026-11-01 04:10 UTC, before any of these tapes were read): every BTC 5m window that
starts in the UTC hours 02, 08, 14, 20 of 2026-07-31 .. 2026-08-20 (one week each of spot, TWAP-30 and TWAP-60
settlement). Gamma metadata in batches of 20 slugs, then the taker-only data-api tape
[start - 300, end + 60) per window, fetched in balanced passes (pass k = the k-th window of every (day, hour) cell) so a
partial fetch stays balanced. Development data only (all before H = 2026-10-23).

Output: .cache/re/directional-maker/it13/switch/windows.parquet and t_<start>.parquet
(ts, wallet, side, asset, price, size, tx16).

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code13/fetch_stable.py
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from polyrea.workflows.updown_study import fetch_windows  # noqa: E402

D0 = 1785456000   # 2026-07-31 00:00 UTC
D1 = 1787270400   # 2026-08-21 00:00 UTC
H = 1792713600
HOURS = (2, 8, 14, 20)
OUT = ROOT / ".cache/re/directional-maker/it13/switch"
STATUS = ROOT / ".cache/re/directional-maker/fetch_switch_status.json"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    starts = [t for t in range(D0, D1, 300) if ((t % 86400) // 3600) in HOURS and t + 300 <= H]
    wf = OUT / "windows.parquet"
    if wf.exists():
        W = pd.read_parquet(wf)
    else:
        slugs = [f"btc-updown-5m-{t}" for t in starts]
        raw = fetch_windows(slugs)
        rows = []
        for m in raw.values():
            try:
                st = int(str(m.get("slug")).rsplit("-", 1)[1])
                toks = json.loads(m.get("clobTokenIds") or "[]")
                outs = json.loads(m.get("outcomes") or "[]")
            except (ValueError, IndexError):
                continue
            if len(toks) != 2:
                continue
            up = 0 if (outs and str(outs[0]).lower() == "up") else 1
            ptb = None; rsrc = m.get("resolutionSource"); cmc = m.get("cryptoMarketConfig")
            for e in m.get("events") or []:
                ptb = (e.get("eventMetadata") or {}).get("priceToBeat", ptb)
            rows.append(dict(cid=m["conditionId"], slug=m["slug"], start_ts=st, end_ts=st + 300, up_token=str(toks[up]),
                             down_token=str(toks[1 - up]), ptb=ptb, rsrc=str(rsrc), cmc=json.dumps(cmc) if not isinstance(cmc, str) else cmc))
        W = pd.DataFrame(rows).sort_values("start_ts").reset_index(drop=True)
        W.to_parquet(wf, index=False)
    W["day"] = W.start_ts // 86400
    W["hour"] = (W.start_ts % 86400) // 3600
    W["k"] = ((W.start_ts % 3600) // 300).astype(int)
    W = W.sort_values(["k", "day", "hour"]).reset_index(drop=True)
    pm = PolymarketData()
    st = {"n": len(W), "done": 0, "rows": 0, "t0": time.time()}

    def one(r):
        f = OUT / f"t_{int(r.start_ts)}.parquet"
        if f.exists():
            return 0
        rows, _, cov = pm.market_trades(r.cid, int(r.start_ts) - 300, int(r.end_ts) + 60, taker_only=True)
        d = pd.DataFrame(rows)
        if d.empty:
            d = pd.DataFrame({"ts": pd.Series(dtype="int64")})
        else:
            d = pd.DataFrame({"ts": pd.to_numeric(d["timestamp"], errors="coerce").astype("int64"),
                              "wallet": d["proxyWallet"].astype(str).str.lower(), "side": d["side"].astype(str),
                              "asset": d["asset"].astype(str), "price": pd.to_numeric(d["price"], errors="coerce").astype("float32"),
                              "size": pd.to_numeric(d["size"], errors="coerce").astype("float32"),
                              "tx16": d["transactionHash"].astype(str).str.lower().str[2:18]})
        d["cov"] = cov.status
        d.to_parquet(f, index=False)
        return len(d)

    with ThreadPoolExecutor(max_workers=3) as ex:
        for n in ex.map(one, W.itertuples(index=False)):
            st["done"] += 1
            st["rows"] += n
            if st["done"] % 20 == 0:
                st["t"] = time.time()
                STATUS.write_text(json.dumps(st))
    st["t"] = time.time()
    st["finished"] = True
    STATUS.write_text(json.dumps(st))


if __name__ == "__main__":
    main()
