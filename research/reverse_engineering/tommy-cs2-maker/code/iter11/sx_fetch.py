"""X145 (information panel iter-10 P2): SX Bet in-play fills on chain (SX Rollup), development period 10-16..H only.

Verified 2026-11-01 05:30 UTC (NOTES iteration 11):
  - explorer API https://explorerl2.sx.technology/api (Etherscan-style logs, key-free) and /api/v2 (Blockscout);
  - SX Bet exchange proxy 0x890482680C3a0116aBB003B17e7D694D13a6c1eB (EIP-1967, implementation 0x4336940c...
    initialized 2026-10-13, unverified), fill txs call selector 0x468e5f52;
  - its per-fill-tx summary log topic0 0x9267299c... = [marketHash, ?, taker] + [amount]; per-maker-order log
    0x8c0f5113... = [maker, ?, ?] + [fill amount, orderHash?, batch id];
  - the fill calldata holds every maker order with (marketHash, baseToken, totalBetSize, percentageOdds (1e20 = 100%),
    salt, isMakerBettingOutcomeOne), its maker and its fill amount (positions relative to the marketHash word);
  - api.sx.bet/markets/find?marketHashes=<<=30 hashes> answers key-free for finished markets (teams, type, gameTime,
    league, sport, outcome).
Steps: (1) all summary logs in blocks [B0, B1] (10-16 00:00 .. H - 1 s; every record asserted < H by block time);
(2) map distinct market hashes; (3) for esports / CS2 / Dota markets, fetch each fill tx's input and decode the maker
orders. Outputs (parquet) in .cache/re/tommy-cs2-maker/sx/.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker/sx"
OUT.mkdir(parents=True, exist_ok=True)
H = 1792713600
B0, B1 = 10543166, 10686804
EXCH = "0x890482680C3a0116aBB003B17e7D694D13a6c1eB"
T_SUM = "0x9267299c72f9365d807c6b2d2e669e6d91d690042ed52a1da054bda6b1ddc104"
API = "https://explorerl2.sx.technology/api"
V2 = "https://explorerl2.sx.technology/api/v2"
cli = httpx.Client(timeout=60, headers={"User-Agent": "polyrea-research"})
LOG = open(OUT / "sx_fetch_log.txt", "a", encoding="utf-8")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, file=LOG, flush=True)


def get(url, params=None, tries=6):
    for k in range(tries):
        try:
            r = cli.get(url, params=params)
            if r.status_code == 200:
                time.sleep(0.35)
                return r
            log("http", r.status_code, url[-60:])
        except Exception as e:  # noqa: BLE001
            log("err", repr(e)[:120])
        time.sleep(2 + 3 * k)
    return None


def step1():
    p = OUT / "sx_fill_summaries.parquet"
    if p.exists():
        return pd.read_parquet(p)
    rows, a = [], B0
    step = 5000
    while a <= B1:
        b = min(B1, a + step - 1)
        r = get(API, {"module": "logs", "action": "getLogs", "fromBlock": a, "toBlock": b, "address": EXCH, "topic0": T_SUM})
        res = (r.json().get("result") if r is not None else None) or []
        if not isinstance(res, list):
            res = []
        if len(res) >= 1000 and step > 50:
            step //= 2
            continue
        for x in res:
            ts = int(x["timeStamp"], 16)
            if ts >= H:
                continue
            tp = x["topics"]
            rows.append({"blk": int(x["blockNumber"], 16), "ts": ts, "tx": x["transactionHash"],
                         "li": int(x["logIndex"], 16) if x.get("logIndex") else -1, "mh": tp[1], "t2": tp[2],
                         "taker": "0x" + tp[3][-40:], "amt": int(x["data"][2:66], 16) / 1e6})
        log("logs", a, b, len(res), "total", len(rows))
        a = b + 1
        if len(res) < 400 and step < 20000:
            step = int(step * 1.5)
    df = pd.DataFrame(rows)
    df.to_parquet(p)
    return df


def step2(df):
    p = OUT / "sx_markets.parquet"
    if p.exists():
        return pd.read_parquet(p)
    hs = sorted(df.mh.unique())
    rows = []
    for i in range(0, len(hs), 30):
        r = get("https://api.sx.bet/markets/find", {"marketHashes": ",".join(hs[i:i + 30])})
        d = (r.json().get("data") if r is not None else None) or []
        for m in d:
            rows.append({k: m.get(k) for k in ("marketHash", "status", "outcomeOneName", "outcomeTwoName", "teamOneName",
                                                 "teamTwoName", "type", "gameTime", "line", "sportXeventId", "liveEnabled",
                                                 "sportLabel", "sportId", "leagueId", "leagueLabel", "group1", "outcome",
                                                 "reportedDate", "chainVersion", "mainLine")})
        if i % 600 == 0:
            log("markets", i, len(hs), len(rows))
    mk = pd.DataFrame(rows)
    # sealed-data rule: keep only markets of games that started before H (post-hoc fields of later games are never stored)
    mk = mk[mk.gameTime.notna() & (mk.gameTime.astype(float) < H)]
    mk.to_parquet(p)
    return mk


def words(h):
    h = h[10:] if h.startswith("0x") else h[8:]
    return [h[64 * i:64 * (i + 1)] for i in range(len(h) // 64)]


def decode(inp, mhs):
    w = words(inp)
    out = []
    for j, x in enumerate(w):
        if ("0x" + x) not in mhs or j < 8 or j + 5 >= len(w):
            continue
        base = w[j + 1]
        if not (base[:24] == "0" * 24 and int(base, 16) != 0):
            continue
        po = int(w[j + 3], 16)
        flag = int(w[j + 5], 16)
        if not (0 < po < 10 ** 20) or flag not in (0, 1):
            continue
        out.append({"mh": "0x" + x, "maker": "0x" + w[j - 8][-40:], "fill": int(w[j - 7], 16) / 1e6,
                    "total": int(w[j + 2], 16) / 1e6, "po": po / 1e20, "one": flag, "pos": j})
    return out


def step3(df, mk):
    p = OUT / "sx_maker_orders.parquet"
    es = mk[mk.sportLabel.astype(str).str.contains("sport", case=False) | mk.leagueLabel.astype(str).str.contains(
        "CS|Counter|Dota|ESL|IEM|BLAST|PGL", case=True)]
    keep = set(es.marketHash)
    txs = df[df.mh.isin(keep)].drop_duplicates("tx")
    log("esports markets", len(keep), "fill txs", len(txs))
    done = {}
    if p.exists():
        old = pd.read_parquet(p)
        done = set(old.tx)
        rows = old.to_dict("records")
    else:
        rows = []
    n = 0
    for r0 in txs.itertuples():
        if r0.tx in done:
            continue
        r = get(f"{V2}/transactions/{r0.tx}")
        if r is None:
            continue
        d = r.json()
        inp = d.get("raw_input") or ""
        for e in decode(inp, keep):
            e.update({"tx": r0.tx, "ts": int(r0.ts), "blk": int(r0.blk), "taker": r0.taker, "sel": inp[:10],
                      "frm": (d.get("from") or {}).get("hash")})
            rows.append(e)
        n += 1
        if n % 100 == 0:
            pd.DataFrame(rows).to_parquet(p)
            log("txs", n, len(txs), "rows", len(rows))
    pd.DataFrame(rows).to_parquet(p)
    log("done step3", n, len(rows))


if __name__ == "__main__":
    df = step1()
    log("summaries", len(df), "markets", df.mh.nunique())
    mk = step2(df)
    log("markets mapped", len(mk), mk.sportLabel.value_counts().head(12).to_dict())
    if len(sys.argv) > 1 and sys.argv[1] == "noinput":
        sys.exit(0)
    step3(df, mk)
