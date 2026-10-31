"""Live lab (development blocks after T0 only): CS2 markets whose scheduled game start lies in a development
block, the wallet's fills there (public tape of those markets only), their signing times (calldata), the
recorded books (clob_wallets) and the sports websocket's round scores (sports feed), for a first look at
timing vs round events (X2, X3/A5a) and quote placement vs the touch.

Sealed discipline: Gamma is read through a projection (listing fields only); only markets whose gameStartTime is
inside a development interval of tools/sealed.py (and after T0) are kept; tapes are requested per kept market;
live records come through iter_live (development blocks only).
Output: .cache/re/tommy-cs2-maker/live/<stamp>_*.parquet and a printed summary.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import live  # noqa: E402
import sealed  # noqa: E402
from polyrea.adapters.http import shared_client  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from fetch_calldata import rows_of  # noqa: E402

KEY = "tommy-cs2-maker"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
T0 = 1793404800
OUT = ROOT / ".cache/re/tommy-cs2-maker/live"


def dev_markets(now: float) -> pd.DataFrame:
    h = shared_client()
    rows, off = [], 0
    while True:
        params = {"series_id": "10310", "start_date_min": "2026-10-28T00:00:00Z", "limit": 100, "offset": off}
        d, _ = h.get_json("https://gamma-api.polymarket.com/events", params, adapter="gamma.events", max_age=600)
        if not d:
            break
        for e in d:
            meta = e.get("eventMetadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:  # noqa: BLE001
                    meta = {}
            for m in e.get("markets") or []:
                if m.get("sportsMarketType") not in ("moneyline", "child_moneyline"):
                    continue
                rows.append({"event": e.get("slug"), "title": e.get("title"), "league": meta.get("league"),
                             "pandascore": meta.get("pandascoreMatchId"), "cid": m.get("conditionId"),
                             "smt": m.get("sportsMarketType"), "question": m.get("question"),
                             "game_start": m.get("gameStartTime"), "tokens": m.get("clobTokenIds"),
                             "gameId": m.get("gameId"), "outcomes": m.get("outcomes")})
        if len(d) < 100:
            break
        off += 100
    df = pd.DataFrame(rows).drop_duplicates("cid")
    gs = pd.to_datetime(df["game_start"].astype(str).str.replace(r"\+00$", "+00:00", regex=True), utc=True, errors="coerce")
    df["gs_ts"] = (gs - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()
    iv = sealed.intervals(KEY, T0, now, sealed=False)
    keep = np.zeros(len(df), bool)
    for a, b in iv:
        keep |= (df["gs_ts"] >= a).to_numpy() & (df["gs_ts"] < b).to_numpy()
    df = df[keep & (df["gs_ts"] < now)].copy()
    df["blk_end"] = [next(b for a, b in iv if a <= g < b) for g in df["gs_ts"]]
    return df


def main() -> None:
    now = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    mk = dev_markets(now)
    print("dev-unit CS2 markets", len(mk), mk.groupby("event").size().to_dict(), flush=True)
    pm = PolymarketData()
    tapes = []
    for r in mk.itertuples():
        end = int(min(now, r.blk_end) - 1)
        rows, _, cov = pm.market_trades(r.cid, start=int(r.gs_ts) - 3600, end=end, taker_only=False, max_rows=100_000)
        d = pd.DataFrame(rows)
        if len(d):
            d["cid"] = r.cid
            tapes.append(d)
    tp = pd.concat(tapes, ignore_index=True) if tapes else pd.DataFrame()
    print("tape rows", len(tp), "wallet rows", int((tp.get("proxyWallet", pd.Series(dtype=str)) == W).sum()) if len(tp) else 0, flush=True)
    stamp = time.strftime("%Y%m%dT%H%M", time.gmtime(now))
    mk.to_parquet(OUT / f"{stamp}_markets.parquet", index=False)
    if len(tp):
        tp.to_parquet(OUT / f"{stamp}_tape.parquet", index=False)
        wtx = sorted(set(tp.loc[tp["proxyWallet"] == W, "transactionHash"]))
        cli = httpx.Client(timeout=40)
        recs = []
        for i in range(0, len(wtx), 40):
            body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [hsh]} for j, hsh in enumerate(wtx[i:i + 40])]
            res = cli.post("https://polygon-bor-rpc.publicnode.com", json=body).json()
            for x in res:
                if x.get("result"):
                    recs.extend(rows_of(x["result"]))
            time.sleep(0.2)
        if recs:
            pd.DataFrame(recs).to_parquet(OUT / f"{stamp}_calldata.parquet", index=False)
        print("wallet tx", len(wtx), "calldata rows", len(recs), flush=True)
    # sports feed and books for these markets
    toks = set()
    for t in mk["tokens"]:
        t = json.loads(t) if isinstance(t, str) else t
        toks.add(str(t[0]))
    sp, bk = [], []
    t_lo = float(mk["gs_ts"].min()) - 600 if len(mk) else now
    try:
        for r in live.iter_live("sports", t_lo, now):
            try:
                m = json.loads(r["m"])
            except Exception:  # noqa: BLE001
                continue
            if m.get("leagueAbbreviation") == "cs2":
                sp.append({"t": r["t"], "gameId": m.get("gameId"), "home": m.get("homeTeam"), "away": m.get("awayTeam"),
                           "score": m.get("score"), "period": m.get("period"), "status": m.get("status")})
    except Exception as e:  # noqa: BLE001  (current hour file still being written)
        print("sports reader stopped:", type(e).__name__, flush=True)
    try:
        for r in live.iter_live("clob_wallets", t_lo, now):
            if r.get("a") in toks:
                bk.append({"t": r["t"], "s": r.get("s"), "k": r.get("k"), "a": r.get("a"), "b": json.dumps(r.get("b")),
                           "o": json.dumps(r.get("o")), "p": r.get("p"), "z": r.get("z"), "d": r.get("d"), "h": r.get("h")})
    except Exception as e:  # noqa: BLE001
        print("book reader stopped:", type(e).__name__, flush=True)
    pd.DataFrame(sp).to_parquet(OUT / f"{stamp}_sports.parquet", index=False)
    pd.DataFrame(bk).to_parquet(OUT / f"{stamp}_books.parquet", index=False)
    print("sports recs", len(sp), "book recs", len(bk), "stamp", stamp, flush=True)


if __name__ == "__main__":
    main()
