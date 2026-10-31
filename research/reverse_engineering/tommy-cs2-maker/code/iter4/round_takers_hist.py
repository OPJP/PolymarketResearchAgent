"""Iteration 4, X47a (assumptions iter3 P1a): does any taker in the ROUND markets of the same event sign before the
wallet's taker orders? Historical, VALIDATE events (gs 10-21..22; development data before H).

Round markets = every market of the wallet's traded VALIDATE events whose sportsMarketType is not moneyline /
child_moneyline (round handicap, round totals, map handicap, total maps), from universe.parquet. Their taker tapes
(data-api, taker_only) in [gs - 10 min, gs + 4.5 h]. Transactions whose block time lies in [t - 1 s, t + 8 s] of a
wallet take t (signing) or of a control time (t - 120 s, t + 120 s, t + 240 s) are decoded (publicnode,
eth_getTransactionByHash, batches of 40, decoded in memory) for the round-market taker's signing ms.
Reported: the share of wallet takes (and of control times) with a round-market taker signing in [-1000, 0) ms and
[-200, 0) ms, and in (0, +500] ms; who signs; and the median lead. Output: results/round_takers_hist.json
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
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from calldata import decode_match_orders  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
RPC = "https://polygon-bor-rpc.publicnode.com"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0, H = 1792540800, 1792713600
CTRL = (-120.0, 120.0, 240.0)


def main():
    u = pd.read_parquet(OUT / "universe.parquet", columns=["event_slug", "cid", "smt", "gs_ts"])
    o = pd.read_parquet(OUT / "orders.parquet", columns=["role", "sign_ms", "event", "gs_ts", "cid"])
    tk = o[(o.role == "taker") & (o.gs_ts >= VAL0) & (o.gs_ts < H) & (o.sign_ms > 1.7e12)].copy()
    evs = set(tk.event)
    rm = u[u.event_slug.isin(evs) & ~u.smt.isin(["moneyline", "child_moneyline"]) & (u.gs_ts < H)]
    print("events", len(evs), "round markets", len(rm), flush=True)
    pm = PolymarketData()
    near = []
    for r in rm.itertuples():
        rows, _, _ = pm.market_trades(r.cid, start=int(r.gs_ts) - 600, end=min(int(r.gs_ts) + 16200, H - 1), taker_only=True, max_rows=50_000)
        if not rows:
            continue
        d = pd.DataFrame(rows)
        bt = d.timestamp.astype(float).to_numpy()
        t_ev = tk[tk.event == r.event_slug].sign_ms.to_numpy(float) / 1000
        for lab, sh in [("take", 0.0)] + [(f"ctrl{int(c)}", c) for c in CTRL]:
            tt = np.sort(t_ev + sh)
            k = np.searchsorted(tt, bt - 8, side="left")
            hit = (k < len(tt)) & (tt[np.minimum(k, len(tt) - 1)] <= bt + 1)
            for h in d.transactionHash[hit]:
                near.append((h, r.cid, r.event_slug, r.smt))
    nd = pd.DataFrame(near, columns=["tx", "cid", "event", "smt"]).drop_duplicates("tx")
    print("txs to decode", len(nd), flush=True)
    cli = httpx.Client(timeout=40, headers={"User-Agent": "polyrea-research"})
    sg = {}
    txl = nd.tx.tolist()
    for i in range(0, len(txl), 40):
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(txl[i:i + 40])]
        res = None
        for attempt in range(6):
            try:
                rr = cli.post(RPC, json=body)
                if rr.status_code == 429:
                    time.sleep(3 * (attempt + 1))
                    continue
                res = rr.json()
                break
            except Exception:  # noqa: BLE001
                time.sleep(2)
        for x in res or []:
            t = x.get("result") or {}
            dd = decode_match_orders(t.get("input", ""))
            if dd:
                sg[t["hash"]] = (dd["taker"]["sign_ms"], dd["taker"]["maker"].lower())
        time.sleep(0.15)
    nd["sign_ms"] = nd.tx.map(lambda h: sg.get(h, (np.nan, None))[0])
    nd["who"] = nd.tx.map(lambda h: sg.get(h, (np.nan, None))[1])
    nd = nd[(nd.sign_ms > 1.7e12) & (nd.sign_ms < 1.8e12) & (nd.who != WALLET)]
    out = {"events": len(evs), "round_markets": int(len(rm)), "decoded_round_txs": int(len(nd)), "by_time": {}}
    for lab, sh in [("take", 0.0)] + [(f"ctrl{int(c)}", c) for c in CTRL]:
        rows = []
        for ev, g in tk.groupby("event"):
            s = np.sort(nd[nd.event == ev].sign_ms.to_numpy(float))
            for t in g.sign_ms.to_numpy(float) + sh * 1000:
                lead = t - s
                rows.append({"pre1000": bool(((lead > 0) & (lead <= 1000)).any()), "pre200": bool(((lead > 0) & (lead <= 200)).any()),
                             "post500": bool(((lead < 0) & (lead >= -500)).any()),
                             "lead_ms": float(lead[(lead > 0) & (lead <= 1000)].min()) if ((lead > 0) & (lead <= 1000)).any() else np.nan})
        x = pd.DataFrame(rows)
        out["by_time"][lab] = {"n": int(len(x)), "share_round_taker_signed_in_prior_1000ms": round(float(x.pre1000.mean()), 4),
                               "share_prior_200ms": round(float(x.pre200.mean()), 4), "share_next_500ms": round(float(x.post500.mean()), 4),
                               "median_lead_ms": round(float(x.lead_ms.median()), 1) if x.lead_ms.notna().any() else None}
    # who signs just before the wallet's takes
    pre = []
    for ev, g in tk.groupby("event"):
        e = nd[nd.event == ev]
        for t in g.sign_ms.to_numpy(float):
            m = e[(t - e.sign_ms > 0) & (t - e.sign_ms <= 1000)]
            pre += m.who.tolist()
    out["prior_1000ms_signers_top"] = pd.Series(pre).value_counts().head(10).to_dict() if pre else {}
    json.dump(out, open(RES / "round_takers_hist.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
