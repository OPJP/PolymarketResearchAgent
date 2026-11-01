"""Examiner round 2: on-chain checks on seeded samples of the lot's BTC 5m cluster BUY trades (my own RPC code).

(a) role: for 120 BUY trades (seed 31) the receipt's V2 OrderFilled events decide maker vs taker (an OrderFilled whose
    maker topic is the wallet and whose taker topic is not an exchange contract = a maker fill; taker = the exchange =
    the wallet's own taker order) and the shares; compared with the tape-inferred role used by the rule and by me.
(b) the in-block price anchor (R7) recomputed independently for 150 maker fills (seed 32): block number and transaction
    index of the fill and of every clean taker print of the same window stamped in the same second
    (eth_getTransactionByHash); anchor = the last clean transaction earlier in the block (its taker's worst price), else
    the last clean print stamped before the block second; prediction = anchor - 0.01.
"""
from __future__ import annotations

import json
import time

import httpx
import numpy as np
import pandas as pd

from r2_common import CLUSTER, EXC, RES

from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from polyrea.analysis.updown import snap_price  # noqa: E402

EV = EXC / "ev"
RPCS = ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"]
TOPIC_V2 = "0xd543adfd945773f1a62f74f0ee55a5e3b9b1a28262980ba90b1a89f2ea84d8ee"
EXCH = {"0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"}


def rpc(cl, body):
    for a in range(8):
        try:
            r = cl.post(RPCS[a % 2], json=body)
            if r.status_code == 429:
                time.sleep(2 + a); continue
            r.raise_for_status()
            j = r.json()
            if isinstance(j, list) and all(isinstance(x, dict) and x.get("result") is not None for x in j):
                return j
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1 + a)
    return None


def main():
    t0 = time.time()
    S = pd.read_parquet(EXC / "side_fills.parquet")  # examiner maker fills (BTC 5m) with tape-inferred role = maker
    w = pd.read_parquet(EV / "w5.parquet")
    B = pd.read_parquet(EXC / "btc5m_buys.parquet")  # r2_metrics: role from the full taker tape
    B["role_tape"] = B["role"]
    inv = {v: k for k, v in CLUSTER.items()}
    out = {}
    rng = np.random.default_rng(31)
    samp = B.iloc[rng.choice(len(B), size=min(120, len(B)), replace=False)]
    agree, found, sh_ok = 0, 0, 0
    with httpx.Client(timeout=40) as cl:
        hs = list(dict.fromkeys(samp.tx))
        rec = {}
        for i in range(0, len(hs), 20):
            part = hs[i:i + 20]
            j = rpc(cl, [{"jsonrpc": "2.0", "id": k, "method": "eth_getTransactionReceipt", "params": [h]} for k, h in enumerate(part)])
            for x in j or []:
                rec[part[x["id"]]] = x["result"]
            time.sleep(0.3)
        for r in samp.itertuples(index=False):
            rc = rec.get(r.tx)
            if not rc:
                continue
            addr = inv[r.wallet][2:]
            role, shares = None, 0.0
            for lg in rc.get("logs", []):
                tp = lg.get("topics", [])
                if len(tp) < 4 or tp[0].lower() != TOPIC_V2:
                    continue
                if tp[2][-40:].lower() != addr:
                    continue
                d = lg["data"][2:]
                side = int(d[0:64], 16)
                tok = str(int(d[64:128], 16))
                if tok != r.asset or side != 0:
                    continue
                taker = "0x" + tp[3][-40:].lower()
                role = "taker" if taker in EXCH else "maker"
                shares += int(d[192:256], 16) / 1e6  # takerAmountFilled of a BUY = shares received
            if role is None:
                continue
            found += 1
            agree += int(role == r.role_tape)
            sh_ok += int(abs(shares - r.size) <= max(0.005 * r.size, 0.011))
        out["role_check"] = {"sampled": int(len(samp)), "receipts_decoded": found, "role_agree": agree, "shares_agree": sh_ok,
                             "tape_taker_share": float((B.role_tape == "taker").mean())}
        print(out["role_check"], round(time.time() - t0, 1), flush=True)
        # (b) in-block anchor on the 06-12 block (no live recording)
        pm = PolymarketData()
        S6 = S[(S.ts >= 1793426400) & (S.ts < 1793448000)]
        rng = np.random.default_rng(32)
        sm = S6.iloc[rng.choice(len(S6), size=min(150, len(S6)), replace=False)] if len(S6) else S6
        A = pd.read_parquet(EXC / "activity_f1_all.parquet")
        ctx = set(A.tx.str.lower())
        wi = w.set_index("cid")
        tapes = {}
        for c in sm.cid.unique():
            rs, _, _ = pm.market_trades(c, start=int(wi.at[c, "start_ts"]) - 120, end=int(wi.at[c, "end_ts"]) - 1, taker_only=True)
            d = pd.DataFrame([(int(x["timestamp"]), str(x.get("asset")), x.get("side"), snap_price(float(x.get("price", 0))),
                               str(x.get("transactionHash") or "").lower()) for x in rs], columns=["ts", "asset", "side", "price", "tx"])
            d = d[~d.tx.isin(ctx)]
            d["up_px"] = np.where(d.asset == str(wi.at[c, "up_token"]), d.price, 1 - d.price)
            d["push_up"] = (d.side == "BUY") == (d.asset == str(wi.at[c, "up_token"]))
            tapes[c] = d.sort_values("ts", kind="stable")
        need = set(sm.tx)
        for r in sm.itertuples(index=False):
            d = tapes[r.cid]
            need |= set(d.loc[d.ts == r.ts, "tx"])
        need = sorted(need)
        pos = {}
        for i in range(0, len(need), 20):
            part = need[i:i + 20]
            j = rpc(cl, [{"jsonrpc": "2.0", "id": k, "method": "eth_getTransactionByHash", "params": [h]} for k, h in enumerate(part)])
            for x in j or []:
                pos[part[x["id"]]] = (int(x["result"]["blockNumber"], 16), int(x["result"]["transactionIndex"], 16))
            time.sleep(0.3)
        ok_in, ok_blk, n, src_in = 0, 0, 0, 0
        for r in sm.itertuples(index=False):
            d = tapes[r.cid]
            before = d[d.ts < r.ts]
            a_blk = before.up_px.iloc[-1] if len(before) else np.nan
            a = a_blk
            fp = pos.get(r.tx)
            same = d[d.ts == r.ts]
            if fp is not None and len(same):
                cand = [(pos.get(h), h) for h in same.tx.unique()]
                cand = [(p_[1], h) for p_, h in cand if p_ is not None and p_[0] == fp[0] and p_[1] < fp[1]]
                if cand:
                    h = max(cand)[1]
                    tr = same[same.tx == h]
                    a = tr.up_px.max() if bool(tr.push_up.iloc[0]) else tr.up_px.min()
                    src_in += 1
            if not np.isfinite(a):
                continue
            n += 1
            m = lambda x: round((x if r.is_up == 1 else 1 - x) - 0.01, 2)
            ok_in += int(abs(r.price - m(a)) <= 0.0105)
            ok_blk += int(abs(r.price - m(a_blk)) <= 0.0105) if np.isfinite(a_blk) else 0
        out["inblock_check_0612"] = {"fills": n, "inblock_anchor_share": src_in / max(n, 1), "within_tick_inblock": ok_in / max(n, 1),
                                      "within_tick_block_clock": ok_blk / max(n, 1), "rpc_positions": len(pos)}
    out["secs"] = round(time.time() - t0, 1)
    (RES / "exam_r2_onchain.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
