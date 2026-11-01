"""btc5m-bot frozen rule (iteration 8; iteration 10 adds pre-registered point-in-time clean live versions; iteration 12
adds the exposure-tracker replica for the PnL condition; iteration 14 re-anchors the decision clock).

Iteration 14 (PRE-REGISTRATION 5, NOTES.md iteration 14): 'side_decision_clock' now comes from code/dc_exam14.py: the decision
anchor is X = m - 260 ms on EXCHANGE time (150-ms taker delay + 105-ms Binance-to-London + 5 ms), the capture's Binance spot book
cut at X + 131 ms (collector receive clock) and its spot trades at X; frozen model_it14_dcside_spot.txt (fitted on 10-17..19;
VALIDATE 10-20..22 scored once: 83.7% per taker order, 82.4% per decision). It is target_metrics.side_accuracy from iteration 14
on (the block-clock side model stays as side_accuracy_block_clock). NEW reported component 'presence_decision_clock'
(code/dc_hazard14.py, VALIDATE-only, not a pre-registered target metric): a 50-ms decision hazard on the same clock (label = a
cluster first leg matched 205-255 ms after the bin end; model_it14_hazard_full.txt vs its Polymarket-only baseline
model_it14_hazard_pm_only.txt; VALIDATE 10-20..22 0.889 vs 0.759). Presence (block seconds), price and the PnL tracker are
unchanged; the block-second presence gain over a capture-aware market baseline is only +0.024 (results/pres14.json).

Iteration 13: the scored rule and target_metrics are unchanged (the pre-registered two-stream tracker was not adopted). NEW
reported component 'side_decision_clock' (pre-registration 4, X113 step 6; code/dc_exam13.py): per cluster taker order, the
matching-engine ms from the public CC0 capture Fahri-5/updown-5m-polymarket-raw (revision pinned in dc_exam13.REV), the
decision instant a = m - 180 ms, Binance spot book microprice / mid returns over [a - K, a) from the same capture, and the frozen
model_it13_dcside_spot.txt (fitted on 10-17..19; VALIDATE 10-20..22: 74.2% per order, XM one-sided windows 81.4%). Development
runs never open a capture day file that starts at or after H; the examiner's ALLOW_SEALED = True reaches those days.

Iteration 12 (PIVOT: condition 5 as an exposure-path target; NOTES.md iteration 12, pre-registered 00:20 and 00:36 UTC
11-01, before scoring): the executable rule for the PnL condition is now an EXPOSURE TRACKER. Per window, target net
N*(s) = sum_{t <= s} flow(t), flow = 0.5 x the frozen it4b per-second netflow model (MODEL_NETFLOW, BUILD-fitted) + 0.5 x
the new nf12b net-flow model (MODEL_NF12B: cell features of both outcomes + slow spot-path features, BUILD-fitted, PIT);
the rule's own realized net R (the rule's own state); every free second s, if |N* - R| >= TRK_LOT it BUYS the deficit
(multiples of TRK_LOT) of Up (> 0) or Down (< 0) at the outcome's last implied ask + TRK_SLACK; strict fills only against
other traders' taker BUY prints on that outcome (cluster takers and transactions holding a cluster maker fill excluded)
with block ts in [s+1, s+3] (convention (a), latency >= 2 s; (b) = [s, s+2] reported apart), at the print price; the
unfilled part stays in the deficit. target_metrics.pnl_corr_* now come from it (VALIDATE: 0.4758 / 0.4404 offline,
track12_avg.json); the iteration-4 30-share replica is kept as pnl_corr_*_frozen30. Nothing else changed.

Iteration 11: no change to the rule, its constants or its data loading (measurements only; see NOTES.md iteration 11 and
FINAL_RULE.md item 11). evaluate(start_ts, end_ts, intervals=None) is unchanged.

Iteration 10 additions (live / future-block components only; the historical rule and every frozen live component are unchanged):
  - Polymarket holds marketable orders on BTC 5m for a TAKER DELAY of 150 ms (measured: fresh-signed sign-to-match floor
    186-190 ms vs 35-73 ms on markets without a delay), so the bot's order arrives at a = m - TAKER_DELAY_MS and its last input
    is a - POST_LATENCY_MS = m - 180 ms. PRE-REGISTERED 10-31 ~21:40 UTC, first clean test 11-01 06-12 UTC:
    side_live_decision_pit (vote over LIVE_VOTE_WIN_MS_PIT = [m - 650, m - 180)), price_live_book_pit (o's ask at
    m - PRE_MATCH_MS_PIT = m - 180) and presence_live_decision.pit_label (the frozen hazard scored against a match in
    [t + 180, t + 680)); target keys *_pit. They are reported next to the frozen versions and replace nothing.

Iteration 8 additions (live / future-block components only; the historical rule is unchanged; nothing fitted on VALIDATE):
  - LIVE_VOTE_FEEDS read both the rec_exam7 feed names and their continuation by rec_exam8 (btc5m_xclob8 / btc5m_xven8,
    11-02 05:59 -> 11-03 18:00 UTC, weekday sealed blocks); identical records, identical rule.
  - side_live_decision.full_coverage: PRE-REGISTERED 10-31 18:16 UTC fallbacks for decisions without a vote (Polymarket ask
    rose over [m-600, m-100) -> ask fell over [m-3000, m-100) -> underdog); target key side_accuracy_live_decision_full_coverage.
  - side_live_decision_ext: pre-registered secondary vote = the six series plus Bybit linear L1 from btc5m_xfam (rec_fam8.py).
  - presence_live_decision (_live_hazard): decision-level hazard of a cluster taker match on o in [t+100, t+600) ms on a
    100-ms grid, frozen coefficients HAZ_FULL_COEF (Polymarket activity + venue tick + touch-change gate) and HAZ_BASE_COEF
    (Polymarket-activity baseline), fitted on development interval 10-31 16:04:30-16:33 UTC; target keys
    presence_live_decision_auc / presence_live_decision_baseline.

Iteration 6 header:

Iteration 6 additions (frozen; nothing fitted on VALIDATE):
  - price.calldata_touch: for every sampled cluster TAKER order, the limit vs the best effective ask of the maker orders the
    same match consumed (SELL of the token at p = ask p; BUY of the complement at q = ask 1 - q). Rule price = the touch
    (the trivial touch anchor, stated as such; measured on the match itself, not a PIT forecast). Used as
    target_metrics.price_within_tick where no live book covers the period (h1/h2). VALIDATE sample: 95.1% within a tick.
  - side_condition_by_wallet: share of one-sided windows per wallet (the side condition is judged per wallet).

Iteration 5 additions (all frozen constants below; nothing fitted on VALIDATE):
  - evaluate(start_ts, end_ts, intervals=None): only windows that start in one of the [a, b) intervals count.
  - Order generation (decoded from V2 calldata): orders are PRE-SIGNED ladders signed at rel -89.5 / +42.4 / +173.3 s;
    `order_generation_b1` checks the share of a seeded calldata sample of the period's filled cluster orders signed in
    those bursts (LADDER_BATCHES).
  - Price: where the shared live recorder covers the period (tools/live.py iter_live with ALLOW_SEALED), the rule price
    is the recorded best ask of the bought outcome PRE_MATCH_MS before the recorded match of the same tx (`price.live_book`).
  - Presence baselines: a PURE market-activity baseline (model_it5_dp_k0_pure.txt; no reference feed) replaces the
    iteration 2-4 baseline that contained Binance fair-value gaps; decision-aligned presence (label at block second s+1)
    with its own pure baseline and a 2-hour block bootstrap of the gain.
  - Side: model_it5_side_book.txt (it4b features + lagged segments + Bybit perp top-of-book, USE_BOOK).
  - `target_metrics`: the brief's named keys.

Previous header (iteration 4):

Point-in-time behaviour-cloning rule for the three-wallet BTC 5-minute Up/Down bot
(GF 0x0ca4e9d2..., XM 0x3048d653..., DS 0xc53375ff...). Every cell (window, outcome, second s of the window) is
scored with frozen LightGBM models trained on BUILD only (windows 2026-10-09 .. 2026-10-16 00:00 UTC; model files
model_it4*_*.txt next to this script). Inputs, all public and available before second s:
  - Binance BTCUSDT spot 1-s closes of seconds <= s-2 (cells.py),
  - Binance USD-M futures BTCUSDT aggTrades with T < (s-1)*1000 ms (fut_cells.py, new in iteration 3),
  - OKX BTC-USDT-SWAP and Bybit BTCUSDT perpetual trades with T < (s-1)*1000 ms (venue_cells.py, new in iteration 3,
    used when USE_VENUES is True), Binance spot aggTrades, Bybit spot, OKX spot (venue_cells2.py, SIX_SERIES),
  - cross-asset: Binance USD-M ETHUSDT (and with ALT_SET "four" SOLUSDT, XRPUSDT, DOGEUSDT) perpetual aggTrades with
    T < (s-1)*1000 ms (alt_cells.py, new in iteration 4, used when USE_ALTS is True),
  - other traders' data-api taker prints with block ts <= s-1 (cluster prints and prints that traded against a
    cluster maker order removed) (tape_feats.py),
  - listing metadata (window start/end, token ids).
No own-state features in the primary score; nothing fitted on VALIDATE or the holdout.

Outputs per cell: presence score p (any cluster BUY fill in that cell), flag p >= P_THRESH; per second: side = the
dedicated side model's choice (Up if ps >= 0.5); print-level selection score = 2*1[full size] + 1[partial size] + p
(flag: full size OR (partial size AND p >= P_THRESH)); outcome proxy (primary, iteration 4): buy the predicted cluster
shares of each outcome in every cell (model_*_shares) at the last implied ask; secondary: the predicted signed net
share flow (model_*_netflow) and soft_side.

evaluate(start_ts, end_ts) fetches what it needs for that period (Gamma metadata, Binance spot 1-s archive, Binance
futures / OKX / Bybit daily trade archives, data-api taker tapes, on-chain OrderFilled logs of the cluster), applies
the frozen rule and returns the brief's metrics (presence with the co-occurrence baseline, side, price, selection,
outcome).
"""
from __future__ import annotations
import os as _os; _ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))  # repo root

import calendar
import gzip
import hashlib
import io
import os
import shutil
import sys
import tempfile
import time
import zipfile

CODE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CODE)
sys.path.insert(0, _ROOT + "")

import httpx
import numpy as np
import pandas as pd
import lightgbm as lgb
from scipy import stats
from sklearn.metrics import roc_auc_score

from polyrea.adapters.polymarket import PolymarketData
from polyrea.adapters.spot import binance_seconds
from polyrea.analysis.updown import windows_from_markets
from polyrea.workflows.updown_study import fetch_windows, window_slugs

import cells as cellsmod
import rpc
import spot as spotmod
import tape_feats as tf
from build_cells_day import add_inv, add_extra, OWN, EXTRA
from fetch_tapes2 import fetch_one as _fetch_tape
from ofi import Agg
from fut_cells import FUT_FEATS, fut_feats
from venue_cells import VEN_FEATS, ven_feats
from venue_cells2 import VEN2_FEATS, ven2_feats
from alt_cells import alt_feats, ALTS, ALTS4, ALT_FEATS, ALT4_FEATS, BETA as ALT_BETA, lag_feats, LAG_FEATS
from book_feats import BK as BOOK_FEATS, book_arrays, book_feats, stream_day

# ----------------------------------------------------------------------------- frozen constants
WALLETS = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
H = 1792713600  # holdout start; development runs (end_ts <= H) never download an archive that extends past H
USE_VENUES = True   # iteration 3: OKX + Bybit perpetual features in the primary score and the side model
SIX_SERIES = True   # iteration 3: + Binance spot aggTrades, Bybit spot, OKX spot and the six-series composite (requires USE_VENUES)
USE_ALTS = True     # iteration 4: cross-asset features (alt perpetuals), requires USE_VENUES and SIX_SERIES
ALT_SET = "four"    # "eth" = ETHUSDT only (model_it4_*), "four" = ETH, SOL, XRP, DOGE + composites (model_it4b_*)
_ALTS = ALTS4 if ALT_SET == "four" else ALTS
_ALT_FEATS = list(ALT4_FEATS if ALT_SET == "four" else ALT_FEATS) if USE_ALTS else []
ALT_SYMBOLS = {"ethfut": "ETHUSDT", "solfut": "SOLUSDT", "xrpfut": "XRPUSDT", "dogefut": "DOGEUSDT"}
SPOT_FEATURES = list(cellsmod.FEATS)
TAPE_FEATURES = list(tf.TAPE_FEATS)
FEATURES = SPOT_FEATURES + TAPE_FEATURES + list(EXTRA) + list(FUT_FEATS) + (list(VEN_FEATS) if USE_VENUES else []) + (list(VEN2_FEATS) if USE_VENUES and SIX_SERIES else []) + _ALT_FEATS
MARKET_FEATURES = ["rel", "tau"] + TAPE_FEATURES + list(EXTRA)    # co-occurrence baseline: market activity only (no reference feed)
OWN_FEATURES = FEATURES + list(OWN)                               # secondary: + cluster inventory (own state)
DSIDE = ["ask_o", "bid_o", "age_ask", "age_bid", "n1", "n2", "n5", "n30", "vol30", "dm5", "dm10", "dm30", "F_gap_ask", "F_gap_m", "gap_ask", "gap_m"]
SIDE_FEATURES = FEATURES + ["D_" + k for k in DSIDE]             # side model: Up-cell features + Down-cell non-mirror features
_TAG = ((("it4b" if ALT_SET == "four" else "it4") if USE_ALTS else "it3s") if SIX_SERIES else "it3v") if USE_VENUES else None
_M = f"model_{_TAG}_all" if USE_VENUES else "model_it3_spot_tape_fut"
MODEL_Y = f"{CODE}/{_M}_y.txt"          # label: any cluster BUY fill on (window, outcome, second)
MODEL_T = f"{CODE}/{_M}_yT.txt"         # label: cluster taker fill
MODEL_M = f"{CODE}/{_M}_yM.txt"         # label: cluster maker fill
MODEL_OWN = f"{CODE}/{f'model_{_TAG}_all_own' if USE_VENUES else 'model_it3_spot_tape_fut_own'}_y.txt"  # + own state (secondary)
MODEL_SIDE = f"{CODE}/{f'model_{_TAG}_side' if USE_VENUES else 'model_it3_side'}.txt"                  # side given a one-sided second
SIDE_LAG = USE_ALTS and ALT_SET == "four"  # iteration 4: side model with explicit [s-3, s-2) / [s-4, s-3) segments (chosen on VALIDATE: 75.5% vs 75.3%)
if SIDE_LAG:
    MODEL_SIDE = f"{CODE}/model_{_TAG}_side_lag.txt"
USE_BOOK = True     # iteration 5: Bybit BTCUSDT perpetual top-of-book features (public orderbook.200 archive) in the side model
ALLOW_SEALED = False  # only the examiner's driver sets this to True (live recordings of sealed blocks)
DECISION_LAG_S = 2.0  # iteration 5 (live lab): the bot's order matches ~2.0 s (median) before its block timestamp
PRE_MATCH_MS = 50.0  # iteration 5 (live lab): rule price = recorded best ask 50 ms before the recorded match (the book record at the match already shows the post-trade book)
# iteration 10 (X73, panel iter9 information P1): Polymarket's crypto TAKER DELAY. A marketable order on a BTC 5m market (CLOB
# market record itode = true) is held D ms before it is matched or placed on the book. Measured on 10-31 (delay10.py / ctl10.py):
# fresh-signed taker orders of other wallets reach the match >= 186-190 ms after signing on BTC 5m (q1 per hour 187-190 ms) vs
# 35-73 ms on control markets without a delay (and ~1,035 ms on sports in-play markets). So the bot's decision (its last input)
# is at a - delta = m - D - delta, not m - 50..150. PRE-REGISTERED 10-31 ~21:40 UTC, before any 11-01 data exists (first clean
# test: 11-01 06-12 UTC development block), reported NEXT TO the frozen versions (which stay unchanged):
TAKER_DELAY_MS = 150.0       # D (changelog: 150 ms since 2026-09-04 14:00 UTC)
POST_LATENCY_MS = 30.0       # delta: signing / posting before the arrival (fresh-signed floor 186-190 ms = D + ~35 ms)
PRE_MATCH_MS_PIT = TAKER_DELAY_MS + POST_LATENCY_MS            # price_live_book_pit: o's ask at a - delta = m - 180 ms
LIVE_VOTE_WIN_MS_PIT = (500 + TAKER_DELAY_MS, TAKER_DELAY_MS + POST_LATENCY_MS)  # side_live_decision_pit: vote over [a - 500, a - delta)
HAZ_LABEL_MS_PIT = (TAKER_DELAY_MS + POST_LATENCY_MS, TAKER_DELAY_MS + POST_LATENCY_MS + 500)  # presence_live_decision pit label
LADDER_BATCHES = ((-89.5, 1.5), (42.4, 3.0), (173.3, 3.0))  # iteration 5 (B1): ladder signing times (rel to window start, s) and half-widths
B1_SAMPLE_TXS = 1500  # calldata sample per evaluate() run (batched eth_getTransactionByHash)
MODEL_DP_FULL = f"{CODE}/model_it5_dp_k1_full.txt"   # iteration 5 (D1): decision-aligned presence, it4b features, label = fill at s+1
MODEL_DP_PURE = f"{CODE}/model_it5_dp_k1_pure.txt"   # its pure market-activity baseline (no reference feed)
MODEL_DP0_PURE = f"{CODE}/model_it5_dp_k0_pure.txt"  # pure market-activity baseline for the block-second label
MODEL_BLK_FULL = f"{CODE}/model_it5_blk_full.txt"  # iteration 5: presence on BLOCK seconds (it4b features), trained on BUILD block seconds
MODEL_BLK_PURE = f"{CODE}/model_it5_blk_pure.txt"  # its pure market-activity baseline
BLOCK_SEC = 1.5  # Polygon block interval (s); the chain clock is fitted per UTC hour from (block number, block timestamp) pairs
BLOCK_LOCK_SHARE = 0.98  # an hour is "locked" when one phase explains >= this share of its pairs (else all its seconds are kept)
MODEL_SIDE_BOOK = f"{CODE}/model_it5_side_book.txt"  # side model it4b-lag features + BK_* (trained on BUILD only)
MODEL_MKT = f"{CODE}/model_it2_market_only_y.txt"                  # co-occurrence baseline (market activity only)
MODEL_NETFLOW = f"{CODE}/model_{_TAG}_netflow.txt"                # iteration 4: signed net share flow per second (outcome proxy)
MODEL_SHARES = f"{CODE}/model_{_TAG}_shares.txt"                  # iteration 4: expected cluster shares per cell (primary outcome proxy)
MODEL_IT2 = f"{CODE}/model_it2_spot_tape_y.txt"                    # iteration-2 rule (spot + tape), for comparison
IT2_FEATURES = SPOT_FEATURES + TAPE_FEATURES + list(EXTRA)
ORDER_SIZES = (30.0, 50.0, 60.0)  # the bot's fixed order sizes (shares), decoded on BUILD (iteration 1)
FULL_SIZES = (30.0, 50.0, 60.0, 100.0)            # iteration 3: full order sizes seen on BUILD (100 = 3.3% of BUILD cluster taker prints)
PARTIAL_SIZES = (5.0, 10.0, 15.0, 20.0, 25.0)      # iteration 3: partial taker fills of those orders (maker sizes are multiples of 5)
SEL_THRESH = 1.30  # print-level selection flag: size rule AND cell score >= P_THRESH (fixed before VALIDATE was scored)
P_THRESH = 0.30         # flag a cell when the presence score >= this (fixed in iteration 1, not tuned on VALIDATE)
ORDER_SHARES = 30.0      # rule order size for the PnL proxy
FEE_RATE = 0.07
EXCHANGES = rpc.V2_EXCHANGES
EVAL_DIR = _ROOT + "/.cache/re/btc5m-bot/eval"
DEV_CACHE = _ROOT + "/.cache/re/btc5m-bot"
FUT_URL = "https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{d}.zip"
OKX_URL = "https://static.okx.com/cdn/okex/traderecords/trades/daily/{c}/BTC-USDT-SWAP-trades-{d}.zip"
BYBIT_URL = "https://public.bybit.com/trading/BTCUSDT/BTCUSDT{d}.csv.gz"
BYBITSPOT_URL = "https://public.bybit.com/spot/BTCUSDT/BTCUSDT_{d}.csv.gz"
OKXSPOT_URL = "https://static.okx.com/cdn/okex/traderecords/trades/daily/{c}/BTC-USDT-trades-{d}.zip"
BNSPOT_URL = "https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{d}.zip"
ALT_URL = "https://data.binance.vision/data/futures/um/daily/aggTrades/{s}/{s}-aggTrades-{d}.zip"
# iteration 12: exposure tracker (pre-registered in NOTES.md iteration 12; frozen constants)
MODEL_NF12B = f"{CODE}/model_it12_nf12b.txt"   # per-second cluster net-flow model with slow spot-path features (BUILD-fitted)
TRK_LOT = 10.0          # shares; the tracker trades only when |target - realized| >= TRK_LOT, in multiples of TRK_LOT
TRK_SLACK = 0.02        # limit = last implied ask + 2 c
TRK_CAPTURE = 1.0       # share of an observed print the rule may take (frozen strict-fill convention, an upper bound)
TRK_CONV = {"a": (1, 3, 4), "b": (0, 2, 3)}  # prints in [s+lo, s+hi]; next decision at s+step. (a) = latency >= 2 s (primary)
TRK_W_IT4B, TRK_W_NF12B = 0.5, 0.5          # target flow weights (pre-registration 2: avg replaces it4b alone; it won on both)


# ----------------------------------------------------------------------------- data loading
def _find_block(ts: int) -> int:
    """First block with timestamp >= ts (binary search over cached eth_getBlockByNumber)."""
    head = int(rpc.call("eth_blockNumber", [], max_age=60), 16)
    est = head - int((rpc.block_ts(head) - ts) / 1.5)
    lo, hi = max(1, est - 200_000), min(head, est + 200_000)
    while rpc.block_ts(lo) >= ts:
        lo = max(1, lo - 400_000)
    while rpc.block_ts(hi) < ts:
        hi = min(head, hi + 400_000)
        if hi == head:
            break
    while lo < hi:
        mid = (lo + hi) // 2
        if rpc.block_ts(mid) < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _decode(log):
    t = log["topics"]; d = log["data"][2:]
    w = [int(d[i:i + 64], 16) for i in range(0, min(len(d), 64 * 5), 64)]
    return {"block": int(log["blockNumber"], 16), "ts": int(log["blockTimestamp"], 16) if "blockTimestamp" in log else -1,
            "tx": log["transactionHash"], "li": int(log["logIndex"], 16), "oh": t[1], "owner": "0x" + t[2][-40:], "cp": "0x" + t[3][-40:],
            "side": w[0], "token": str(w[1]), "mamt": float(w[2]), "tamt": float(w[3]), "fee": float(w[4])}


LOGS_CHUNK = 100  # iteration 10 (data loading only): drpc's free plan refuses eth_getLogs above ~100-199 blocks since 10-31


def _get_logs_chunked(ex, a, b, topics):
    """Iteration 10 robustness fix (data loading, not the rule): drpc's free plan now refuses eth_getLogs ranges above ~100-199
    blocks (HTTP 400 'ranges over 10000 blocks are not supported on free plan', 10-31 21:50 UTC) and publicnode refuses archive
    ranges. Try the whole range first (responses cached by earlier runs stay valid), else LOGS_CHUNK-block chunks (2 threads,
    retries with back-off)."""
    try:
        return rpc.get_logs(ex, a, b, topics)
    except Exception:
        pass
    from concurrent.futures import ThreadPoolExecutor
    chunks = [(x, min(x + LOGS_CHUNK - 1, b)) for x in range(a, b + 1, LOGS_CHUNK)]

    def one(c):
        for k in range(5):
            try:
                return rpc.get_logs(ex, c[0], c[1], topics)
            except Exception:
                time.sleep(1 + 2 * k)
        raise RuntimeError(f"eth_getLogs failed for blocks {c[0]}-{c[1]} on {ex}")
    out = []
    with ThreadPoolExecutor(2) as pool:
        for r in pool.map(one, chunks):
            out += r
    return out


def cluster_fills(start_ts: int, end_ts: int, windows: pd.DataFrame) -> pd.DataFrame:
    """Every OrderFilled of the cluster's own orders (maker and taker role) in [start_ts, end_ts)."""
    b0, b1 = _find_block(start_ts), _find_block(end_ts)
    pads = [rpc.pad(x) for x in WALLETS]
    rows = []
    for a in range(b0, b1, 3000):
        b = min(a + 2999, b1 - 1)
        for ex in EXCHANGES:
            rows += [_decode(l) for l in _get_logs_chunked(ex, a, b, [rpc.TOPIC_V2, None, pads])]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    miss = df.ts < 0
    if miss.any():
        for blk in df.loc[miss, "block"].unique():
            df.loc[df.block == blk, "ts"] = rpc.block_ts(int(blk))
    df = df.drop_duplicates(["tx", "li"])
    df = df[(df.ts >= start_ts) & (df.ts < end_ts)]
    df["wallet"] = df.owner.map(WALLETS)
    df["role"] = np.where(df.cp.isin([e.lower() for e in EXCHANGES]), "T", "M")
    buy = df.side == 0
    df["usdc"] = np.where(buy, df.mamt, df.tamt) / 1e6
    df["shares"] = np.where(buy, df.tamt, df.mamt) / 1e6
    df["price"] = df.usdc / df.shares
    df["fee_usd"] = df.fee / 1e6
    up = windows[["cid", "start_ts", "end_ts", "up_token", "up_payout"]].rename(columns={"up_token": "token"}).assign(is_up=True)
    dn = windows[["cid", "start_ts", "end_ts", "down_token", "up_payout"]].rename(columns={"down_token": "token"}).assign(is_up=False)
    df = df.merge(pd.concat([up, dn]), on="token", how="inner")
    df["is_up"] = df.is_up.astype(bool)
    df["rel"] = df.ts - df.start_ts
    return df[df.side == 0].sort_values(["block", "li"]).reset_index(drop=True)


def load_windows(start_ts: int, end_ts: int) -> pd.DataFrame:
    markets = fetch_windows(window_slugs("btc", "5m", start_ts, end_ts))
    ws = windows_from_markets(markets)
    w = pd.DataFrame([{"cid": x.condition_id, "start_ts": x.start_ts, "end_ts": x.end_ts, "up_token": x.up_token, "down_token": x.down_token,
                       "fee_rate": x.fee_rate, "up_payout": x.up_payout} for x in ws])
    return w[(w.start_ts >= start_ts) & (w.end_ts <= end_ts)].reset_index(drop=True)


def load_tapes(windows: pd.DataFrame, end_ts: int) -> str:
    """Taker tapes for every window, same range and columns as in training (fetch_tapes2.fetch_one: [start-600, end+5])."""
    d = f"{EVAL_DIR}/tapes"
    os.makedirs(d, exist_ok=True)
    pm = PolymarketData()
    for r in windows.itertuples():
        _fetch_tape(pm, r.cid, r.start_ts, r.end_ts, int(end_ts), d)
    return d


def load_spot(start_ts: int, end_ts: int):
    sp, _ = binance_seconds("btc", start_ts - 7200, end_ts)
    s = pd.DataFrame(sp, columns=["sec", "close"])
    s["sec"] = s.sec.astype(np.int64)
    return spotmod.Spot(frame=s), s


def _day_str(day0: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(day0))


def _download(url: str, tmpdir: str) -> str:
    raw = f"{tmpdir}/raw.bin"
    with httpx.stream("GET", url, timeout=180, follow_redirects=True) as r:
        r.raise_for_status()
        with open(raw, "wb") as fh:
            for chunk in r.iter_bytes(1 << 20):
                fh.write(chunk)
    return raw


def _archive(venue: str, day0: int, end_ts: int):
    """Path of the reduced trade parquet (T ms, p, q, m) of one daily archive, or None if unavailable.
    Binance futures and Bybit files are UTC days; OKX files are UTC+8 days (file D covers [D-8h, D+16h) UTC)."""
    cover_end = day0 + 86400 - (8 * 3600 if venue in ("okx", "okxspot") else 0)
    if end_ts <= H and cover_end > H:
        return None  # development run: never load data from the holdout period
    sub = {"fut": "fut", "okx": "venues/okx", "bybit": "venues/bybit", "bnspot": "venues/bnspot", "bybitspot": "venues/bybitspot", "okxspot": "venues/okxspot",
           **{k: f"venues/{k}" for k in ALT_SYMBOLS}}[venue]
    for base in (DEV_CACHE, EVAL_DIR):
        p = f"{base}/{sub}/{day0}.parquet"
        if os.path.exists(p):
            return p
    out_dir = f"{EVAL_DIR}/{sub}"; os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="dl_", dir=EVAL_DIR)
    d = _day_str(day0)
    try:
        if venue in ("fut", "bnspot") or venue in ALT_SYMBOLS:
            url = ALT_URL.format(s=ALT_SYMBOLS[venue], d=d) if venue in ALT_SYMBOLS else (FUT_URL if venue == "fut" else BNSPOT_URL).format(d=d)
            raw = _download(url, tmp)
            chk = httpx.get(url + ".CHECKSUM", timeout=30).text.split()[0]
            assert hashlib.sha256(open(raw, "rb").read()).hexdigest() == chk, "checksum mismatch"
            with zipfile.ZipFile(raw) as zz:
                txt = zz.read(zz.namelist()[0])
            df = pd.read_csv(io.BytesIO(txt), header=None)
            if not str(df.iloc[0, 0]).isdigit():
                df = df.iloc[1:]
            df = df.iloc[:, [1, 2, 5, 6]]; df.columns = ["p", "q", "T", "m"]
            T = df["T"].astype(np.int64).to_numpy(); T = np.where(T > 10**14, T // 1000, T)  # spot archives may be in microseconds
            out = pd.DataFrame({"T": T, "p": df.p.astype(float).to_numpy(), "q": df.q.astype(np.float32).to_numpy(),
                                "m": df.m.astype(str).str.lower().isin(["true", "1"]).to_numpy()})
        elif venue in ("okx", "okxspot"):
            raw = _download((OKX_URL if venue == "okx" else OKXSPOT_URL).format(d=d, c=d.replace("-", "")), tmp)
            with zipfile.ZipFile(raw) as zz:
                txt = zz.read(zz.namelist()[0])
            df = pd.read_csv(io.BytesIO(txt), encoding_errors="replace")
            cols = {c.lower().strip(): c for c in df.columns}
            tcol = next(cols[k] for k in cols if "time" in k); qcol = next(cols[k] for k in cols if k in ("size", "qty", "sz"))
            out = pd.DataFrame({"T": pd.to_numeric(df[tcol]).astype(np.int64), "p": pd.to_numeric(df[cols["price"]]).astype(float),
                                "q": pd.to_numeric(df[qcol]).astype(np.float32), "m": df[cols["side"]].astype(str).str.lower().str.startswith("s")})
        else:
            raw = _download((BYBIT_URL if venue == "bybit" else BYBITSPOT_URL).format(d=d), tmp)
            with gzip.open(raw) as g:
                df = pd.read_csv(g)
            cols = {c.lower().strip(): c for c in df.columns}
            ts = pd.to_numeric(df[cols["timestamp"]]).to_numpy(float)
            ts = np.where(ts > 1e11, ts / 1000.0, ts)  # bybit spot files are in ms, perp files in seconds
            qc = cols.get("size", cols.get("volume"))
            out = pd.DataFrame({"T": np.round(ts * 1000).astype(np.int64), "p": pd.to_numeric(df[cols["price"]]).astype(float).to_numpy(),
                                "q": pd.to_numeric(df[qc]).astype(np.float32).to_numpy(), "m": df[cols["side"]].astype(str).str.lower().str.startswith("s").to_numpy()})
    except (httpx.HTTPError, AssertionError, KeyError, StopIteration, ValueError, zipfile.BadZipFile, OSError) as e:
        print(f"archive {venue} {d} unavailable: {type(e).__name__}", flush=True)
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out = out.sort_values("T", kind="stable").reset_index(drop=True)
    p = f"{out_dir}/{day0}.parquet"; out.to_parquet(p, index=False)
    return p


def _agg(venue: str, days, end_ts: int):
    parts = [pd.read_parquet(p) for p in (_archive(venue, d, end_ts) for d in days) if p]
    if not parts:
        return None
    return Agg(pd.concat(parts, ignore_index=True).drop_duplicates())


def _book_path(day0: int, end_ts: int, download: bool = True):
    """Reduced 100-ms Bybit perpetual top-of-book parquet for one UTC day (streamed from the public orderbook.200 archive),
    or None. Development runs (end_ts <= H) never load a day that extends past H."""
    if end_ts <= H and day0 + 86400 > H:
        return None
    for base in (DEV_CACHE, EVAL_DIR):
        p = f"{base}/bybit_ob/linear_{day0}.parquet"
        if os.path.exists(p):
            return p
    if not download:
        return None
    p = f"{EVAL_DIR}/bybit_ob/linear_{day0}.parquet"
    try:
        ok = stream_day(day0, p, H if end_ts <= H else 0)
    except Exception as e:  # network / archive errors: the side model then sees NaN book features
        print(f"bybit book {_day_str(day0)} unavailable: {type(e).__name__}", flush=True)
        return None
    return p if ok else None


def _add_book(X: pd.DataFrame, sec: np.ndarray, end_ts: int) -> pd.DataFrame:
    """BK_* features for block seconds sec (point in time: book buckets with T < (s-1)*1000 ms)."""
    day = (sec // 86400) * 86400
    cols = {k: np.full(len(X), np.nan, np.float32) for k in BOOK_FEATS}
    for d0 in np.unique(day):
        d0 = int(d0); idx = np.where(day == d0)[0]
        A = book_arrays(d0, {d0 - 86400: _book_path(d0 - 86400, end_ts, download=False), d0: _book_path(d0, end_ts)})
        f = book_feats(sec[idx], A)
        for k in BOOK_FEATS:
            cols[k][idx] = f[k]
        del A
    for k in BOOK_FEATS:
        X[k] = cols[k]
    return X


def add_reference_feats(cells: pd.DataFrame, spot_frame: pd.DataFrame, end_ts: int) -> pd.DataFrame:
    """Binance futures (+ OKX, Bybit) PIT features, computed per UTC day of the window start (as in training)."""
    day = (cells.start_ts.to_numpy(np.int64) // 86400) * 86400
    F_all = pd.DataFrame(index=cells.index, columns=[k for k in FEATURES if k in set(FUT_FEATS) | set(VEN_FEATS) | set(VEN2_FEATS) | set(_ALT_FEATS)], dtype=np.float32)
    for d0 in np.unique(day):
        idx = np.where(day == d0)[0]
        c = cells.iloc[idx]
        fa = _agg("fut", (d0 - 86400, d0, d0 + 86400), end_ts)
        if fa is None:
            continue
        F = fut_feats(c, fa, spot_frame)
        F.index = cells.index[idx]
        F_all.loc[F.index, FUT_FEATS] = F[FUT_FEATS].to_numpy()
        if USE_VENUES:
            days = (d0 - 86400, d0, d0 + 86400)
            aggs = {"O": _agg("okx", days, end_ts), "B": _agg("bybit", days, end_ts)}
            Vf = ven_feats(c, aggs, {w: F[f"F_pm{w}"].to_numpy() for w in (1000, 2000, 3000, 5000)})
            Vf.index = cells.index[idx]
            F_all.loc[Vf.index, VEN_FEATS] = Vf[VEN_FEATS].to_numpy()
            if SIX_SERIES:
                aggs.update({"S": _agg("bnspot", days, end_ts), "Y": _agg("bybitspot", days, end_ts), "K": _agg("okxspot", days, end_ts), "F": fa})
                pm_other = {("F", w): F[f"F_pm{w}"].to_numpy() for w in (1000, 2000, 3000)}
                pm_other.update({(p, w): Vf[f"{p}_pm{w}"].to_numpy() for p in ("O", "B") for w in (1000, 2000, 3000)})
                V2 = ven2_feats(c, aggs, pm_other)
                V2.index = cells.index[idx]
                F_all.loc[V2.index, VEN2_FEATS] = V2[VEN2_FEATS].to_numpy()
                if USE_ALTS:
                    alt_aggs = {p: _agg(sub, days, end_ts) for p, sub in _ALTS}
                    A = alt_feats(c, alt_aggs, {w: V2[f"C6_pm{w}"].to_numpy() for w in (1000, 2000, 3000)}, beta=ALT_BETA, alts=_ALTS)
                    A.index = cells.index[idx]
                    F_all.loc[A.index, _ALT_FEATS] = A[_ALT_FEATS].to_numpy()
                    del alt_aggs
            del aggs
        del fa
    cells = pd.concat([cells.drop(columns=[k for k in F_all.columns if k in cells.columns]), F_all.astype(np.float32)], axis=1)
    return cells


# ----------------------------------------------------------------------------- metrics helpers
def _auc(y, p):
    y = np.asarray(y); p = np.asarray(p)
    ok = np.isfinite(p)
    if y[ok].min() == y[ok].max():
        return None
    return round(float(roc_auc_score(y[ok], p[ok])), 4)


def _recall_lift(y, flag):
    y = np.asarray(y).astype(bool); flag = np.asarray(flag).astype(bool)
    base = y.mean(); rec = flag[y].mean() if y.any() else np.nan
    prec = y[flag].mean() if flag.any() else np.nan
    lift = prec / base if base > 0 else np.nan
    k, n = int(y[flag].sum()), int(flag.sum())  # one-sided binomial test of precision vs base rate
    pval = float(stats.binomtest(k, n, base, alternative="greater").pvalue) if n > 0 else None
    return {"recall": round(float(rec), 4), "precision": round(float(prec), 4), "lift": round(float(lift), 3), "flag_share": round(float(flag.mean()), 4), "p_value": pval}


def _mcnemar(a_ok, b_ok):
    b = int((a_ok & ~b_ok).sum()); c = int((~a_ok & b_ok).sum())
    return float(stats.binomtest(b, b + c, 0.5, alternative="greater").pvalue) if b + c > 0 else None


def _predict(model_file: str, df: pd.DataFrame, cols, chunk: int = 200_000) -> np.ndarray:
    """LightGBM predictions in row chunks (keeps memory low on long periods)."""
    m = lgb.Booster(model_file=model_file)
    out = np.empty(len(df))
    for i in range(0, len(df), chunk):
        out[i:i + chunk] = m.predict(df.iloc[i:i + chunk][list(cols)])
    return out


def _pairs(cells: pd.DataFrame):
    """Up and Down rows of every (cid, rel), aligned."""
    up = cells[cells.is_up].sort_values(["cid", "rel"]).reset_index(drop=True)
    dn = cells[~cells.is_up].sort_values(["cid", "rel"]).reset_index(drop=True)
    assert (up.cid.to_numpy() == dn.cid.to_numpy()).all() and (up.rel.to_numpy() == dn.rel.to_numpy()).all()
    return up, dn


def _strict_backtest(up: pd.DataFrame, dn: pd.DataFrame, ps: np.ndarray, win: pd.DataFrame, fills: pd.DataFrame) -> dict:
    """Iteration 4: strict-fill backtest (observed liquidity, as polyrea.analysis.updown.backtest). At second s, if the
    presence score of the side model's outcome o is >= P_THRESH, send a 30-share BUY limit at the last implied ask of o
    (seen at s-1); fill only against OTHER traders' taker BUY prints on o with block ts in [s+1, s+3] (latency >= 2 s after
    the information horizon) at price <= limit, at the print price, for min(print size, remaining shares) (capture 1.0:
    an upper bound). One open order per (window, outcome). Taker fee FEE_RATE p (1-p)."""
    rows = []
    wi = win.set_index("cid")
    sel = pd.DataFrame({"cid": up.cid.to_numpy(), "rel": up.rel.to_numpy(), "side_up": ps >= 0.5,
                        "p": np.where(ps >= 0.5, up.p.to_numpy(), dn.p.to_numpy()), "lim": np.where(ps >= 0.5, up.ask_o.to_numpy(), dn.ask_o.to_numpy())})
    sel = sel[(sel.p >= P_THRESH) & np.isfinite(sel.lim) & (sel.lim > 0.05) & (sel.lim < 0.95)]
    for cid, g in sel.groupby("cid", sort=False):
        tp = f"{tf.TAPE_DIR}/{cid}.parquet"
        if not os.path.exists(tp) or cid not in wi.index:
            continue
        d = pd.read_parquet(tp)
        if not len(d) or "side" not in d:
            continue
        st0 = int(wi.at[cid, "start_ts"]); pay_up = float(wi.at[cid, "up_payout"])
        d = d[(d.side == "BUY") & ~d.proxyWallet.str.lower().isin(WALLETS)]
        d = d.assign(rel=d.timestamp - st0, up=(d.outcome == "Up"))
        for o in (True, False):
            dd = d[d.up == o].sort_values("rel", kind="stable")
            Rr = dd.rel.to_numpy(np.int64); Pp = dd.price.to_numpy(float); Zz = dd["size"].to_numpy(float)
            gg = g[g.side_up == o].sort_values("rel")
            pay = pay_up if o else 1 - pay_up
            busy = -1
            for s0, lim in zip(gg.rel.to_numpy(np.int64), gg.lim.to_numpy(float)):
                if s0 <= busy:
                    continue
                busy = s0 + 3
                left = ORDER_SHARES
                for k in range(np.searchsorted(Rr, s0 + 1, "left"), np.searchsorted(Rr, s0 + 3, "right")):
                    if Pp[k] <= lim + 1e-9:
                        sh = min(left, Zz[k]); left -= sh
                        rows.append((cid, Pp[k], sh, sh * (pay - Pp[k]) - FEE_RATE * Pp[k] * (1 - Pp[k]) * sh))
                        if left <= 0:
                            break
    if not rows:
        return {"rule_fills": 0}
    T = pd.DataFrame(rows, columns=["cid", "price", "shares", "pnl"])
    usd = float((T.price * T.shares).sum()); fee = float((FEE_RATE * T.price * (1 - T.price) * T.shares).sum())
    fw = fills.assign(pay=np.where(fills.is_up, fills.up_payout, 1 - fills.up_payout))
    fw["pnl"] = fw.shares * (fw.pay - fw.price) - fw.fee_usd
    both = T.groupby("cid").pnl.sum().rename("rule").to_frame().join(fw.groupby("cid").pnl.sum().rename("wallet"), how="outer").reindex(win.cid).fillna(0.0)
    return {"rule_fills": int(len(T)), "rule_usd": round(usd, 1), "rule_pnl_before_rebates": round(float(T.pnl.sum()), 1),
            "rule_return_before_rebates": round(float(T.pnl.sum()) / usd, 4), "rule_return_with_50pct_fee_rebate": round((float(T.pnl.sum()) + 0.5 * fee) / usd, 4),
            "per_window_pnl_corr_pearson": round(float(both.rule.corr(both.wallet)), 4), "per_window_pnl_corr_spearman": round(float(both.rule.corr(both.wallet, method="spearman")), 4),
            "note": "strict fills on observed liquidity, latency >= 2 s after the information horizon, capture 1.0 (upper bound), taker only"}


def _nf12b_flow(cells: pd.DataFrame, sp, up: pd.DataFrame) -> np.ndarray:
    """Iteration 12: nf12b per-second net-flow prediction (Up +), aligned with the rows of `up`. PIT as cells.py (spot
    closes <= s-2, other traders' prints <= s-1); slow features from the rule's own Binance 1-s spot index (forward-filled,
    as in training); no own state."""
    import nf12 as nf12mod
    need = ["cid", "start_ts", "is_up"] + nf12mod.SPOT + nf12mod.TAPE
    d = cells[[c for c in need if c in cells.columns]].copy()
    for c in need:
        if c not in d.columns:
            d[c] = np.nan
    px = pd.Series(np.asarray(sp.px, float)).ffill().bfill().to_numpy(float)
    X = nf12mod.pair_frame(d, px, int(sp.s0), pd.Series(dtype=float))
    m = lgb.Booster(model_file=MODEL_NF12B)
    p = m.predict(X[m.feature_name()], num_threads=4)
    s = pd.Series(p, index=pd.MultiIndex.from_arrays([X.cid.to_numpy(), X.rel.to_numpy().astype(np.int64)]))
    return s.reindex(pd.MultiIndex.from_arrays([up.cid.to_numpy(), up.rel.to_numpy().astype(np.int64)])).fillna(0.0).to_numpy(float)


def _strict_tracker(up: pd.DataFrame, dn: pd.DataFrame, flow: np.ndarray, win: pd.DataFrame, fills: pd.DataFrame, conv: str = "a") -> dict:
    """Iteration 12: EXPOSURE TRACKER (pre-registered). Per window the target net N*(s) = cumsum(flow) (Up +); the rule's
    own realized net R; at each free second s, deficit d = N* - R; if |d| >= TRK_LOT, BUY floor(|d| / TRK_LOT) x TRK_LOT
    shares of Up (d > 0) or Down (d < 0) at limit = that outcome's last implied ask (cell ask_o, info <= s-1) + TRK_SLACK,
    only when the ask is in (0.05, 0.95); strict fills only against OTHER traders' taker BUY prints on that outcome with
    block ts in [s+lo, s+hi] at <= limit, at the print price, for min(TRK_CAPTURE x print, remaining), excluding prints of
    cluster takers and prints in transactions that contain a cluster maker fill; taker fee FEE_RATE p (1 - p); one open
    order per window, next decision at s + step; the unfilled part stays in the deficit; positions held to resolution."""
    lo, hi, step = TRK_CONV[conv]
    mk_tx = set(fills.loc[fills.role == "M", "tx"].astype(str).str.lower()) if len(fills) and "tx" in fills else set()
    wl = set(WALLETS)
    wi = win.set_index("cid")
    df = pd.DataFrame({"cid": up.cid.to_numpy(), "rel": up.rel.to_numpy().astype(np.int64), "nf": np.nan_to_num(np.asarray(flow, float)),
                       "au": up.ask_o.to_numpy(float), "ad": dn.ask_o.to_numpy(float)})
    rows, fin = [], {}
    for cid, g in df.groupby("cid", sort=False):
        tp = f"{tf.TAPE_DIR}/{cid}.parquet"
        if not os.path.exists(tp) or cid not in wi.index:
            continue
        d = pd.read_parquet(tp)
        if not len(d) or "side" not in d:
            continue
        st0 = int(wi.at[cid, "start_ts"]); pay_up = float(wi.at[cid, "up_payout"])
        d = d[(d.side == "BUY")]
        keep = np.array([str(w).lower() not in wl for w in d.proxyWallet], bool)
        if "transactionHash" in d:
            keep &= np.array([str(h).lower() not in mk_tx for h in d.transactionHash], bool)
        d = d[keep]
        d = d.assign(rel=d.timestamp - st0, up=(d.outcome == "Up"))
        P = {}
        for o in (True, False):
            dd = d[d.up == o].sort_values("rel", kind="stable")
            P[o] = (dd.rel.to_numpy(np.int64), dd.price.to_numpy(float), dd["size"].to_numpy(float))
        g = g.sort_values("rel")
        tgt = np.cumsum(g.nf.to_numpy(float)); rel = g.rel.to_numpy(np.int64); au = g.au.to_numpy(float); ad = g.ad.to_numpy(float)
        Rn, nxt = 0.0, 0
        for i in range(len(rel)):
            s = rel[i]
            if s < nxt:
                continue
            dd_ = tgt[i] - Rn
            if abs(dd_) < TRK_LOT:
                continue
            o = dd_ > 0
            a = au[i] if o else ad[i]
            if not (np.isfinite(a) and 0.05 < a < 0.95):
                continue
            lim = min(a + TRK_SLACK, 0.99)
            left = np.floor(abs(dd_) / TRK_LOT) * TRK_LOT
            Rr, Pp, Zz = P[o]
            pay = pay_up if o else 1 - pay_up
            for k in range(np.searchsorted(Rr, s + lo, "left"), np.searchsorted(Rr, s + hi, "right")):
                if Pp[k] <= lim + 1e-9:
                    sh = min(left, TRK_CAPTURE * Zz[k]); left -= sh
                    if sh > 0:
                        rows.append((cid, Pp[k], sh, sh * (pay - Pp[k]) - FEE_RATE * Pp[k] * (1 - Pp[k]) * sh))
                        Rn += sh if o else -sh
                    if left <= 1e-9:
                        break
            nxt = s + step
        fin[cid] = (Rn, float(tgt[-1]) if len(tgt) else 0.0)
    if not rows:
        return {"rule_fills": 0}
    T = pd.DataFrame(rows, columns=["cid", "price", "shares", "pnl"])
    usd = float((T.price * T.shares).sum()); fee = float((FEE_RATE * T.price * (1 - T.price) * T.shares).sum())
    fw = fills.assign(pay=np.where(fills.is_up, fills.up_payout, 1 - fills.up_payout))
    fw["pnl"] = fw.shares * (fw.pay - fw.price) - fw.fee_usd
    rp = T.groupby("cid").pnl.sum().reindex(win.cid).fillna(0.0)
    wp = fw.groupby("cid").pnl.sum().reindex(win.cid).fillna(0.0)
    rn = pd.Series({k: v[0] for k, v in fin.items()}).reindex(win.cid).fillna(0.0)
    tg = pd.Series({k: v[1] for k, v in fin.items()}).reindex(win.cid).fillna(0.0)
    wn = (fw.shares * np.where(fw.is_up, 1.0, -1.0)).groupby(fw.cid).sum().reindex(win.cid).fillna(0.0)
    out = {"convention": conv, "rule_fills": int(len(T)), "rule_usd": round(usd, 1), "rule_pnl_before_rebates": round(float(T.pnl.sum()), 1),
           "rule_return_before_rebates": round(float(T.pnl.sum()) / usd, 4), "rule_return_with_50pct_fee_rebate": round((float(T.pnl.sum()) + 0.5 * fee) / usd, 4),
           "per_window_pnl_corr_pearson": round(float(rp.corr(wp)), 4), "per_window_pnl_corr_spearman": round(float(rp.corr(wp, method="spearman")), 4),
           "corr_realized_net_target_net": round(float(rn.corr(tg)), 4), "corr_realized_net_wallet_net": round(float(rn.corr(wn)), 4), "by_wallet": {}}
    for w in ("GF", "XM", "DS"):
        ww = fw[fw.wallet == w].groupby("cid").pnl.sum().reindex(win.cid).fillna(0.0)
        out["by_wallet"][w] = {"pearson": round(float(rp.corr(ww)), 4), "spearman": round(float(rp.corr(ww, method="spearman")), 4)}
    st = win.set_index("cid").start_ts.reindex(win.cid).to_numpy()
    half = st < (np.nanmin(st) + np.nanmax(st)) / 2
    out["halves_pearson"] = [round(float(np.corrcoef(rp.to_numpy()[m], wp.to_numpy()[m])[0, 1]), 4) if m.sum() > 2 else None for m in (half, ~half)]
    out["pnl_block_bootstrap_2h"] = None
    try:
        b = st // 7200; ub = np.unique(b); rng = np.random.default_rng(12); bi = {x: np.where(b == x)[0] for x in ub}
        x, y = rp.to_numpy(), wp.to_numpy(); bs = []
        for _ in range(1000):
            ii = np.concatenate([bi[u] for u in rng.choice(ub, len(ub))])
            bs.append(np.corrcoef(x[ii], y[ii])[0, 1])
        out["pnl_block_bootstrap_2h"] = {"pearson_ci95": [round(float(np.nanquantile(bs, 0.025)), 4), round(float(np.nanquantile(bs, 0.975)), 4)]}
    except Exception:
        pass
    out["note"] = ("exposure tracker (iteration 12, pre-registered): strict fills on observed liquidity, capture 1.0 (upper bound), taker only; "
                   "(a) = latency >= 2 s after the information horizon")
    return out


def _block_keep(t: np.ndarray, pairs: pd.DataFrame) -> np.ndarray:
    """True for the seconds t that hold a Polygon block. The chain clock ts = floor(phi + 1.5 (block - b_ref)) is fitted per
    UTC hour from (block number, block timestamp) pairs (here: the blocks of the period's cluster fills, used only as a
    source of chain timestamps); seconds of hours that are not locked are all kept."""
    t = np.asarray(t, np.int64); keep = np.ones(len(t), bool)
    if pairs is None or pairs.empty:
        return keep
    b = pairs.drop_duplicates("block")[["block", "ts"]].sort_values("block")
    hrs = t // 3600
    for h, g in b.groupby(b.ts // 3600):
        bl = g.block.to_numpy(np.int64); ts = g.ts.to_numpy(np.int64)
        if len(bl) < 50:
            continue
        x = BLOCK_SEC * (bl - bl[0]); best, bphi = -1, None
        for phi in np.arange(ts[0] - 1.5, ts[0] + 1.5, 0.01):
            k = int((np.floor(phi + x) == ts).sum())
            if k > best:
                best, bphi = k, phi
        if best / len(bl) < BLOCK_LOCK_SHARE:
            continue
        allb = np.arange(bl.min() - 5, bl.max() + 6)
        secs = np.unique(np.floor(bphi + BLOCK_SEC * (allb - bl[0])).astype(np.int64))
        idx = np.where(hrs == h)[0]
        keep[idx] = np.isin(t[idx], secs)
    return keep


def _shift(y: np.ndarray, k: int) -> np.ndarray:
    """Label of block second s + k on the row of second s (cells come in 300-row window-outcome blocks)."""
    y = np.asarray(y)
    if k == 0:
        return y.copy()
    out = np.zeros_like(y)
    out[:-k] = y[k:]
    return np.where((np.arange(len(y)) % 300) + k < 300, out, 0)


def _predict_named(model_file: str, df: pd.DataFrame, chunk: int = 200_000) -> np.ndarray:
    m = lgb.Booster(model_file=model_file)
    cols = m.feature_name()
    return np.concatenate([m.predict(df.iloc[i:i + chunk][cols].astype(np.float32)) for i in range(0, len(df), chunk)]) if len(df) else np.array([])


def _block_boot_gain(y, a, b, blocks, n_boot: int = 2000, seed: int = 3) -> dict | None:
    """95% block-bootstrap interval of AUC(a) - AUC(b) over 2-hour blocks (resampling whole blocks)."""
    y = np.asarray(y).astype(float); a = np.asarray(a); b = np.asarray(b); blocks = np.asarray(blocks)
    ub, inv = np.unique(blocks, return_inverse=True)
    if len(ub) < 4 or y.sum() == 0:
        return None

    def prep(s):  # tie groups in score order, computed once
        o = np.argsort(s, kind="mergesort"); ss = s[o]
        grp = np.empty(len(s), np.int64); grp[o] = np.r_[0, np.cumsum(ss[1:] != ss[:-1])]
        return grp, int(grp.max()) + 1

    def wauc(grp, ng, w):  # weighted AUC (whole-block resampling = integer block weights), ties count 1/2
        gp = np.bincount(grp, y * w, ng); gn = np.bincount(grp, (1 - y) * w, ng)
        below = np.cumsum(gn) - gn
        return float((gp * (below + 0.5 * gn)).sum() / (gp.sum() * gn.sum()))

    ga, na = prep(a); gb, nb = prep(b)
    rng = np.random.default_rng(seed); g = []
    for _ in range(n_boot):
        cnt = np.bincount(rng.integers(0, len(ub), len(ub)), minlength=len(ub)).astype(float)
        w = cnt[inv]
        if (y * w).sum() > 0 and ((1 - y) * w).sum() > 0:
            g.append(wauc(ga, na, w) - wauc(gb, nb, w))
    g = np.array(g)
    return {"lo95": round(float(np.quantile(g, 0.025)), 4), "hi95": round(float(np.quantile(g, 0.975)), 4),
            "one_sided_p_gain_le_0": round(float((g <= 0).mean()), 5), "n_boot": int(len(g)), "blocks": int(len(ub))}


def _live_touch(fills: pd.DataFrame, win: pd.DataFrame, start_ts: int, end_ts: int, pre_ms: float | None = None) -> dict | None:
    """Iteration 5 (price component, decoded from calldata + live lab): the bot submits a PRE-SIGNED ladder order whose
    limit is the current best ask of the outcome it buys. Where the shared live recorder has the Polymarket book for
    the period (tools/live.py clob_crypto, through iter_live with ALLOW_SEALED), the rule's price for each cluster fill is
    the recorded best ask of the bought outcome at the decision time (a) = the recorded server time of the matched trade
    (same tx hash) and (b) = block time - DECISION_LAG_S (frozen). Returns None without recordings."""
    import zlib
    sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
    try:
        import live as _live
    except Exception:
        return None
    up_tok = set(win.up_token); tok_up = {r.down_token: r.up_token for r in win.itertuples()}
    books = {}; mt = {}
    hh = int((start_ts - 120) // 3600) * 3600
    while hh < end_ts + 60:  # hour by hour: a broken gzip member in one hourly file must not abort the others
        try:
            for r in _live.iter_live("clob_crypto", max(start_ts - 120, hh), min(end_ts + 60, hh + 3600), allow_sealed=ALLOW_SEALED):
                k = r.get("k")
                if k in ("q", "f") and r["a"] in up_tok:
                    bb = max((p for p, z in r["b"]), default=np.nan); ba = min((p for p, z in r["o"]), default=np.nan)
                    books.setdefault(r["a"], []).append((r["s"], bb, ba))
                elif k == "x" and r.get("h"):
                    h = r["h"].lower()
                    mt[h] = min(mt.get(h, 1e18), r["s"])
        except (zlib.error, EOFError, OSError):
            pass
        hh += 3600
    if not books:
        return None
    books = {t: np.array(sorted(v), dtype=float) for t, v in books.items()}
    f = fills[(fills.role == "T")].drop_duplicates(["tx", "wallet"]).copy()
    f["up_token"] = np.where(f.is_up, f.token, f.token.map(tok_up))

    def touch(u, s_ms, is_up):
        a = books.get(u)
        if a is None:
            return np.nan
        i = np.searchsorted(a[:, 0], s_ms, side="left") - 1
        if i < 0 or s_ms - a[i, 0] > 30_000:
            return np.nan
        return a[i, 2] if is_up else 1.0 - a[i, 1]

    f["match_ms"] = f.tx.str.lower().map(mt)
    pm_ = PRE_MATCH_MS if pre_ms is None else float(pre_ms)
    f["ask_match"] = [touch(u, s - pm_, up) if np.isfinite(s) else np.nan for u, s, up in zip(f.up_token, f.match_ms.astype(float), f.is_up)]
    f["ask_lag"] = [touch(u, (t - DECISION_LAG_S) * 1000.0, up) for u, t, up in zip(f.up_token, f.ts.astype(float), f.is_up)]
    # the limit price of a taker order = its fill price when it does not sweep (it never sweeps: decoded on BUILD)
    out = {"n_taker_orders": int(len(f)), "share_with_book": round(float(np.isfinite(f.ask_lag).mean()), 4) if len(f) else None,
           "share_with_match_time": round(float(np.isfinite(f.match_ms.astype(float)).mean()), 4) if len(f) else None}
    for nm in ("ask_match", "ask_lag"):
        g = f[np.isfinite(f[nm])]
        out[f"within_1tick_{nm}"] = round(float((np.abs(g.price - g[nm]) <= 0.0101).mean()), 4) if len(g) else None
        out[f"exact_{nm}"] = round(float((np.abs(g.price - g[nm]) <= 0.0001).mean()), 4) if len(g) else None
        out[f"within_1tick_{nm}_by_wallet"] = {w: round(float((np.abs(x.price - x[nm]) <= 0.0101).mean()), 4) for w, x in g.groupby("wallet")} if len(g) else None
    return out


LIVE_VOTE_FEEDS = (("btc5m_xclob", "btc5m_xclob8"), ("btc5m_xven", "btc5m_xven8"))
# iteration 7: exam-input recorder (code/rec_exam7.py, every block, until 11-02 06:00 UTC); iteration 8: the same recorder
# continued as code/rec_exam8.py (feed names with suffix 8, 11-02 05:59 -> 11-03 18:00 UTC, weekday sealed blocks). The rule is
# unchanged: the two name sets carry identical records.
LIVE_VOTE_FEEDS_EXT = (("btc5m_xclob", "btc5m_xclob8"), ("btc5m_xven", "btc5m_xven8", "btc5m_xfam"))
LIVE_VOTE_VENUES_EXT = ("bf", "bs", "ok", "by")
# iteration 8 (pre-registered SECONDARY, 10-31 18:08 UTC, before any exam-feed evaluation of it): the frozen vote plus Bybit linear
# BTC/ETH L1 from code/rec_fam8.py (btc5m_xfam, every block from 10-31 17:45 UTC to 11-03 18:00 UTC). Bybit was one of the ten
# lab series validated on four development intervals; Hyperliquid (a follower) stays out. Reported as side_live_decision_ext.
LIVE_VOTE_WIN_MS = (600, 100)   # iteration 6 (frozen): reaction window [m - 600, m - 100) ms before the matching-engine ms m
LIVE_TICK_BP = 0.002            # iteration 6 (frozen): a series votes when its microprice moved by more than this (bp)
ETH_SCALE = 1.235               # iteration 6 (frozen): ETH moves in BTC units


def _live_vote(fills: pd.DataFrame, win: pd.DataFrame, start_ts: int, end_ts: int, feeds=LIVE_VOTE_FEEDS, venues=("bf", "bs", "ok"), win_ms=None) -> dict | None:
    """Iteration 7 (side and timing components, decision level; decoded live in iteration 6, replicated in iterations 6-7):
    the bot submits its pre-signed order for outcome o 100-600 ms after a tick-level MICROPRICE move of the BTC/ETH perps
    and spot toward o. For every cluster taker fill whose tx hash is in the exam-input recording (btc5m_xclob trade records,
    matching-engine ms), the rule's side = sign of the vote of the six sized top-of-book series of btc5m_xven (Binance
    USD-M and spot bookTicker, OKX bbo-tbt; BTC and ETH) over [m - 600, m - 100) ms; abstains when no series moved.
    Placebo = the same side labels at m +- U(5, 60) s. Returns None where the period has no exam-input recording."""
    import zlib
    sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
    try:
        import live as _live
    except Exception:
        return None

    def recs(feed, a, b):
        for fd in ((feed,) if isinstance(feed, str) else tuple(feed)):
            hh = int(a // 3600) * 3600
            while hh < b:
                try:
                    for r in _live.iter_live(fd, max(a, hh), min(b, hh + 3600), allow_sealed=ALLOW_SEALED):
                        yield r
                except (zlib.error, EOFError, OSError, FileNotFoundError):
                    pass
                hh += 3600

    if not len(fills):
        return None
    lo, hi = int(start_ts) - 60, int(end_ts) + 400
    mt = {}
    tok2st, touch = {}, []
    for r in recs(feeds[0], lo, hi):
        k_ = r.get("k")
        if k_ == "x" and r.get("h"):
            h = r["h"].lower(); mt[h] = min(mt.get(h, 1e18), r["s"])
        elif k_ == "S":
            tok2st[str(r["u"])] = int(r["m"]); tok2st[str(r["d"])] = int(r["m"])
        elif k_ == "p" and r.get("bb") is not None and r.get("ba") is not None:
            touch.append((int(r["s"]), int(r["m"]), float(r["bb"]), float(r["ba"])))
    rows = {}
    for r in recs(feeds[1], lo, hi):
        v = r.get("v")
        if v in venues and r.get("b") and r.get("a"):
            rows.setdefault((v, r["y"]), []).append((r.get("E") or 0, r["t"], r["b"], r.get("B") or 0, r["a"], r.get("A") or 0))
    if not mt or not rows:
        return None
    f = fills[fills.role == "T"].drop_duplicates(["tx", "wallet", "token"]).copy()
    f["m"] = f.tx.str.lower().map(mt)
    f = f[f.m.notna()].sort_values("m")
    if not len(f):
        return {"n_taker_matches": 0}
    m = f.m.to_numpy(np.int64); up = f.is_up.to_numpy(bool)
    rng = np.random.default_rng(11)
    pl = m + (rng.choice([-1, 1], len(m)) * rng.uniform(5000, 60000, len(m))).astype(np.int64)
    off = None
    if ("bf", "BTC") in rows:
        x = np.array(rows[("bf", "BTC")], float); off = float(np.median(x[:, 1] - x[:, 0]))
    Q, Qp, cov = [], [], np.zeros(len(m), bool)
    for key, lst in sorted(rows.items()):
        x = np.array(lst, float)
        T = x[:, 0] if key[0] != "bs" else x[:, 1] - (off or 0)
        o = np.argsort(T, kind="stable"); x = x[o]; T = T[o].astype(np.int64)
        mic = (x[:, 2] * x[:, 5] + x[:, 4] * x[:, 3]) / np.maximum(x[:, 3] + x[:, 5], 1e-12)
        sc = ETH_SCALE if key[1] == "ETH" else 1.0

        W_ = LIVE_VOTE_WIN_MS if win_ms is None else win_ms

        def mv(tt):
            i0 = np.searchsorted(T, tt - W_[0], "right") - 1; i1 = np.searchsorted(T, tt - W_[1], "right") - 1
            r = (mic[np.clip(i1, 0, len(mic) - 1)] / mic[np.clip(i0, 0, len(mic) - 1)] - 1) * 1e4 / sc
            r[(i0 < 0) | (tt < T[0] + 3000) | (tt > T[-1] - 500)] = np.nan
            return r
        qa, qb = mv(m), mv(pl)
        Q.append(qa); Qp.append(qb); cov |= np.isfinite(qa)
    Q = np.vstack(Q); Qp = np.vstack(Qp)
    vote = np.nansum(np.sign(Q) * (np.abs(Q) > LIVE_TICK_BP), axis=0); votep = np.nansum(np.sign(Qp) * (np.abs(Qp) > LIVE_TICK_BP), axis=0)
    k = cov & (vote != 0); kp = cov & (votep != 0)
    ok = (vote > 0) == up
    out = {"n_taker_matches": int(len(m)), "series": [f"{a}_{b}" for a, b in sorted(rows)], "covered": int(cov.sum()),
           "cover": round(float(k.sum() / max(cov.sum(), 1)), 4), "agree_on_voted": round(float(ok[k].mean()), 4) if k.any() else None,
           "accuracy_all_covered_abstain_half": round(float((ok[k].sum() + 0.5 * (cov & ~k).sum()) / max(cov.sum(), 1)), 4) if cov.any() else None,
           "placebo_cover": round(float(kp.sum() / max(cov.sum(), 1)), 4), "placebo_agree": round(float(((votep[kp] > 0) == up[kp]).mean()), 4) if kp.any() else None,
           "by_wallet": {}}
    wal = f.wallet.to_numpy()
    for w in ("DS", "GF", "XM"):
        s = k & (wal == w)
        if s.any():
            out["by_wallet"][w] = {"n_voted": int(s.sum()), "agree": round(float(ok[s].mean()), 4)}
    # iteration 8, PRE-REGISTERED 10-31 18:16 UTC (chosen on development intervals A-C = 10-31 14:55-17:55: fallback8.py and
    # this function's B / C output; its first clean test is the next development block, 11-01 06-12 UTC): FULL-COVERAGE side
    # = the vote where any series voted; else the outcome whose Polymarket ask ROSE over [m - 600, m - 100) (others lifting:
    # momentum; B 51.6%, C 64.2%); else the outcome whose ask FELL over [m - 3000, m - 100) (value; B 64.7%, C 57.6%); else
    # the UNDERDOG (ask < 0.5) at m - 100 (the favourite scored 41.7% / 29.4% on B / C, n = 12 / 17).
    if touch:
        tc = pd.DataFrame(touch, columns=["s", "w", "bb", "ba"]).sort_values("s", kind="stable")
        st_m = f.token.astype(str).map(tok2st).to_numpy()
        pred = np.where(cov & (vote > 0), 1.0, np.where(cov & (vote < 0), -1.0, 0.0))
        src = np.where(pred != 0, 0, -1)
        dU6 = np.full(len(m), np.nan); dD6 = np.full(len(m), np.nan); dU30 = np.full(len(m), np.nan); dD30 = np.full(len(m), np.nan)
        aU = np.full(len(m), np.nan)
        for w0, g0 in tc.groupby("w"):
            sel = np.where(st_m == w0)[0]
            if not len(sel):
                continue
            rs = g0.s.to_numpy(np.int64); bbv = g0.bb.to_numpy(float); bav = g0.ba.to_numpy(float)

            def at(xv, tt):
                i = np.searchsorted(rs, tt, "right") - 1
                o_ = xv[np.clip(i, 0, None)].astype(float); o_[i < 0] = np.nan
                return o_
            mm = m[sel]
            aU[sel] = at(bav, mm - 100)
            dU6[sel] = at(bav, mm - 100) - at(bav, mm - 600); dD6[sel] = -(at(bbv, mm - 100) - at(bbv, mm - 600))
            dU30[sel] = at(bav, mm - 100) - at(bav, mm - 3000); dD30[sel] = -(at(bbv, mm - 100) - at(bbv, mm - 3000))
        rose = np.where((dU6 > 0.005) & ~(dD6 > 0.005), 1.0, np.where((dD6 > 0.005) & ~(dU6 > 0.005), -1.0, 0.0))
        kk = (pred == 0) & (rose != 0); pred[kk] = rose[kk]; src[kk] = 1
        fell = np.where((dU30 < -0.005) & ~(dD30 < -0.005), 1.0, np.where((dD30 < -0.005) & ~(dU30 < -0.005), -1.0, 0.0))
        kk = (pred == 0) & (fell != 0); pred[kk] = fell[kk]; src[kk] = 2
        kk = (pred == 0) & np.isfinite(aU); pred[kk] = np.where(aU[kk] < 0.5, 1.0, -1.0); src[kk] = 3
        okf = (pred > 0) == up
        cv = pred != 0
        out["full_coverage"] = {"covered": round(float(cv.mean()), 4), "accuracy": round(float(okf[cv].mean()), 4) if cv.any() else None,
                                "by_source": {nm: [round(float(okf[src == i].mean()), 4) if (src == i).any() else None, int((src == i).sum())]
                                              for i, nm in enumerate(("vote", "pm_ask_rose_600", "pm_ask_fell_3000", "underdog"))},
                                "by_wallet": {w: round(float(okf[cv & (wal == w)].mean()), 4) for w in ("DS", "GF", "XM") if (cv & (wal == w)).any()}}
    return out


# iteration 8 (X56 = panel-assumptions iter7 P3, decision-level presence on the exam-input recording): logistic hazard of a
# cluster taker match on outcome o in [t + 100, t + 600) ms on a 100-ms grid of window time (rel 5..285 s). Features at t:
# act = other traders' Polymarket trades on the window in [t - 1000, t) (btc5m_xclob trades minus cluster txs); tick = sum of
# the six exam-feed microprice moves toward o over [t - 500, t) (bp, ETH / 1.235); rp = sign of the change of o's ask over
# [t - 500, t) (Up ask = ba, Down ask = 1 - bb of the Up book; btc5m_xclob touch records); age = ms since o's ask last changed;
# |ask - 0.5|. FULL = activity + tick + gate; BASE = the Polymarket-activity model (trades, touch changes, age, price level;
# no venue feed). Coefficients FROZEN from a fit on development interval 10-31 16:04:30-16:33 UTC (code/fit_hazard8.py).
# [intercept, coefficients in _haz_design order]; fit_hazard8.py fit on 24,705 grid points (1,072 positives), 10-31 18:08 UTC
HAZ_FULL_COEF = [-1.528663, 0.034989, 0.10605, 0.121965, -0.216997, -0.047516, -0.513175, -0.498611, -0.334245, -0.118567, 0.087896,
                 -0.382857, 0.535861, -3.964875]
HAZ_BASE_COEF = [-1.541862, 0.036447, 0.082306, -0.548028, -0.475293, -0.36622, -0.318605, -3.868469]
# iteration 9 (X72, pre-registered secondary, reported inside presence_live_decision as edge_rule_V8; never counted toward the
# target): the fee-aware delta-scaled edge rule. k chosen on 10-31 14:55-16:04 (lab feeds) among 1 / 1.5 / 2 / 3 / 5 / 8 by
# step ratio x recall (code/fee9b.py); on 16:33-17:55 it flagged 2.7% of grid points at precision 19.7% / recall 13.0% (decision
# label, lab feeds) vs 18.1% / 11.9% for the fitted hazard at the same volume.
EDGE_K = 8.0
EDGE_SIGMA_BP = 0.67        # bp per sqrt(s) (Deribit DVOL ~38%, iteration 8)
EDGE_FEE_NET = 0.035        # taker fee 0.07 p (1 - p) net of the 50% rebate
EDGE_MOVE_WIN_MS = (600, 100)


def _haz_design(tick, rp, age, act, ask):
    la = np.log1p(np.nan_to_num(age, nan=1e5) / 100.0)
    base = np.c_[act, np.log1p(act), rp == 0, rp > 0, rp < 0, la, np.abs(ask - 0.5)].astype(float)
    full = np.c_[act, np.log1p(act), tick, np.abs(tick), np.clip(tick, 0, None), rp == 0, rp > 0, rp < 0,
                 np.clip(tick, 0, None) * (rp == 0), np.clip(tick, 0, None) * (rp > 0), la, la * (tick > 0.02), np.abs(ask - 0.5)].astype(float)
    return full, base


def _live_hazard_data(fills: pd.DataFrame, start_ts: int, end_ts: int, intervals=None):
    """Design of the decision-level hazard from the exam-input feeds; returns (y, full, base, unit) or None (iteration 9: the
    edge-rule values of the same grid points are left in _live_hazard_data.edge_V)."""
    import zlib
    _live_hazard_data.edge_V = None
    _live_hazard_data.y_pit = None
    sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
    try:
        import live as _live
    except Exception:
        return None

    def recs(feeds, a, b):
        for fd in feeds:
            hh = int(a // 3600) * 3600
            while hh < b:
                try:
                    for r in _live.iter_live(fd, max(a, hh), min(b, hh + 3600), allow_sealed=ALLOW_SEALED):
                        yield r
                except (zlib.error, EOFError, OSError, FileNotFoundError):
                    pass
                hh += 3600

    lo, hi = int(start_ts) - 300, int(end_ts) + 400
    toks, trades, touch = {}, [], []
    for r in recs(LIVE_VOTE_FEEDS[0], lo, hi):
        k = r.get("k")
        if k == "S":
            toks[int(r["m"])] = (r["u"], r["d"])
        elif k == "x" and r.get("h"):
            trades.append((int(r["s"]), int(r["m"]), r["h"].lower()))
        elif k == "p" and r.get("bb") is not None and r.get("ba") is not None:
            touch.append((int(r["s"]), int(r["m"]), float(r["bb"]), float(r["ba"])))
    rows = {}
    for r in recs(LIVE_VOTE_FEEDS[1], lo, hi):
        v = r.get("v")
        if v in ("bf", "bs", "ok") and r.get("b") and r.get("a"):
            rows.setdefault((v, r["y"]), []).append((r.get("E") or 0, r["t"], r["b"], r.get("B") or 0, r["a"], r.get("A") or 0))
    if not toks or not trades or not touch or not rows:
        return None
    off = None
    if ("bf", "BTC") in rows:
        x = np.array(rows[("bf", "BTC")], float); off = float(np.median(x[:, 1] - x[:, 0]))
    S = {}
    for key, lst in sorted(rows.items()):
        x = np.array(lst, float)
        T = x[:, 0] if key[0] != "bs" else x[:, 1] - (off or 0)
        o = np.argsort(T, kind="stable"); x = x[o]; T = T[o].astype(np.int64)
        S[key] = (T, (x[:, 2] * x[:, 5] + x[:, 4] * x[:, 3]) / np.maximum(x[:, 3] + x[:, 5], 1e-12), ETH_SCALE if key[1] == "ETH" else 1.0)

    def mv(key, t0, t1):
        T, p, sc = S[key]
        i0 = np.searchsorted(T, t0, "right") - 1; i1 = np.searchsorted(T, t1, "right") - 1
        r = (p[np.clip(i1, 0, None)] / p[np.clip(i0, 0, None)] - 1) * 1e4 / sc
        r[(i0 < 0) | (t0 < T[0] + 3000) | (t1 > T[-1] - 200)] = np.nan
        return r

    tr = pd.DataFrame(trades, columns=["s", "m", "h"]).drop_duplicates()
    tc = pd.DataFrame(touch, columns=["s", "m", "bb", "ba"]).sort_values("s", kind="stable")
    cl = fills[fills.role == "T"].drop_duplicates(["tx", "wallet", "token"]).copy()
    cl["h"] = cl.tx.str.lower()
    mt = tr.groupby("h").s.min()
    cl["mm"] = cl.h.map(mt)
    cl = cl[cl.mm.notna()]
    tok2st = {}
    for st0, (u0, d0) in toks.items():
        tok2st[str(u0)] = st0; tok2st[str(d0)] = st0
    cl["st"] = cl.token.astype(str).map(tok2st)
    cl_tx = set(fills.tx.str.lower())
    oth = tr[~tr.h.isin(cl_tx)]
    Y, F, B, U, V, Y2 = [], [], [], [], [], []
    for st, (upt, dnt) in sorted(toks.items()):
        if st < start_ts or st >= end_ts:
            continue
        if intervals is not None and not any(a <= st < b for a, b in intervals):
            continue
        g = np.arange((st + 5) * 1000, (st + 285) * 1000, 100, dtype=np.int64)
        g = g[(g >= int(start_ts) * 1000 + 5000) & (g < int(end_ts) * 1000)]
        if not len(g):
            continue
        tw = tc[tc.m == st]
        if len(tw) < 2:
            continue
        rs = tw.s.to_numpy(np.int64); bb = tw.bb.to_numpy(float); ba = tw.ba.to_numpy(float)

        def at(xv, tt):
            i = np.searchsorted(rs, tt, "right") - 1
            o = xv[np.clip(i, 0, None)].astype(float); o[i < 0] = np.nan
            return o
        comp = np.zeros(len(g)); okc = np.zeros(len(g), bool)
        for key in S:
            r = mv(key, g - 500, g); okc |= np.isfinite(r); comp += np.nan_to_num(r)
        # iteration 9 (pre-registered secondary, X72): mean BTC microprice move over the vote window, for the edge rule
        mvb = np.zeros(len(g)); nb_ = np.zeros(len(g))
        for key in S:
            if key[1] == "BTC":
                r = mv(key, g - EDGE_MOVE_WIN_MS[0], g - EDGE_MOVE_WIN_MS[1]); mvb += np.nan_to_num(r); nb_ += np.isfinite(r)
        mvb = np.where(nb_ > 0, mvb / np.maximum(nb_, 1), np.nan)
        midU = (at(bb, g) + at(ba, g)) / 2
        tau = np.clip(st + 300 - g / 1000.0, 5, 300)
        om = np.sort(oth[oth.m == st].s.to_numpy(np.int64))
        act = (np.searchsorted(om, g, "left") - np.searchsorted(om, g - 1000, "left")).astype(float)
        cw = cl[cl.st == st]
        for is_up, sg in ((True, 1.0), (False, -1.0)):
            if is_up:
                ak, ak5 = at(ba, g), at(ba, g - 500); ch = np.r_[True, np.diff(ba) != 0]
            else:
                ak, ak5 = 1 - at(bb, g), 1 - at(bb, g - 500); ch = np.r_[True, np.diff(bb) != 0]
            tch = rs[ch]; ic = np.searchsorted(tch, g, "right") - 1
            age = np.where(ic >= 0, g - tch[np.clip(ic, 0, None)], np.nan).astype(float)
            mm = np.sort(cw[cw.is_up == is_up].mm.to_numpy(np.int64))
            y = (np.searchsorted(mm, g + 600, "left") - np.searchsorted(mm, g + 100, "left")) > 0
            k = okc & np.isfinite(ak) & np.isfinite(ak5) & (ak > 0.03) & (ak < 0.97)
            if not k.any():
                continue
            rp = np.sign(np.round((ak[k] - ak5[k]) * 100))
            fu, ba_ = _haz_design(sg * comp[k], rp, age[k], act[k], ak[k])
            y2 = (np.searchsorted(mm, g + HAZ_LABEL_MS_PIT[1], "left") - np.searchsorted(mm, g + HAZ_LABEL_MS_PIT[0], "left")) > 0
            Y.append(y[k]); F.append(fu); B.append(ba_); U.append(np.full(k.sum(), st)); Y2.append(y2[k])
            from scipy.stats import norm as _norm
            mo = np.clip(midU[k] if is_up else 1 - midU[k], 0.01, 0.99)
            dl = _norm.pdf(_norm.ppf(mo)) / (EDGE_SIGMA_BP * np.sqrt(tau[k]))
            gain = 100 * dl * sg * mvb[k]; cost = 100 * ((ak[k] - mo) + EDGE_FEE_NET * ak[k] * (1 - ak[k]))
            V.append(EDGE_K * gain - cost)
    if not Y:
        return None
    _live_hazard_data.edge_V = np.concatenate(V)
    _live_hazard_data.y_pit = np.concatenate(Y2).astype(int)
    return np.concatenate(Y).astype(int), np.vstack(F), np.vstack(B), np.concatenate(U)


def _live_hazard(fills: pd.DataFrame, start_ts: int, end_ts: int, intervals=None) -> dict | None:
    d = _live_hazard_data(fills, start_ts, end_ts, intervals)
    if d is None or HAZ_FULL_COEF is None:
        return None
    y, F, B, U = d
    if y.min() == y.max():
        return {"grid_points": int(len(y)), "positives": int(y.sum())}
    sf = F @ np.array(HAZ_FULL_COEF[1:]) + HAZ_FULL_COEF[0]
    sb = B @ np.array(HAZ_BASE_COEF[1:]) + HAZ_BASE_COEF[0]
    out = {"grid_points": int(len(y)), "positives": int(y.sum()), "windows": int(len(np.unique(U))),
           "auc_full": round(float(_auc(y, sf)), 4), "auc_pm_activity_baseline": round(float(_auc(y, sb)), 4)}
    rng = np.random.default_rng(3); uu = np.unique(U); idx = {u: np.where(U == u)[0] for u in uu}; gains = []
    for _ in range(2000):
        pick = np.concatenate([idx[u] for u in rng.choice(uu, len(uu))])
        if y[pick].min() == y[pick].max():
            continue
        gains.append(_auc(y[pick], sf[pick]) - _auc(y[pick], sb[pick]))
    g = np.array(gains)
    out["gain"] = round(out["auc_full"] - out["auc_pm_activity_baseline"], 4)
    out["gain_ci95_window_bootstrap"] = [round(float(np.percentile(g, 2.5)), 4), round(float(np.percentile(g, 97.5)), 4)] if len(g) else None
    out["gain_p_le_0"] = round(float((g <= 0).mean()), 4) if len(g) else None
    # iteration 9, PRE-REGISTERED secondary (10-31 ~20:15 UTC, k chosen on 10-31 14:55-16:04 lab feeds; first clean test
    # 11-01 06-12): the two-parameter EDGE RULE "act on o iff EDGE_K x 100 Delta_o x (mean BTC microprice move toward o over
    # [t - 600, t - 100) ms) > 100 x (half spread + EDGE_FEE_NET x p (1 - p))", Delta_o = phi(Phi^-1(mid_o)) / (sigma sqrt(tau)).
    # Precision / recall for the match label, against the frozen FULL hazard flagging the same volume.
    Vv = getattr(_live_hazard_data, "edge_V", None)
    if Vv is not None and len(Vv) == len(y):
        fl = np.nan_to_num(Vv, nan=-1e9) > 0
        rule = {"flagged_share": round(float(fl.mean()), 4), "base_rate": round(float(y.mean()), 4)}
        if fl.any():
            rule["precision"] = round(float(y[fl].mean()), 4); rule["recall"] = round(float(fl[y == 1].mean()), 4)
            rule["lift"] = round(float(y[fl].mean() / max(y.mean(), 1e-9)), 3)
            thr = np.quantile(sf, 1 - fl.mean()); ff = sf >= thr
            rule["full_hazard_same_volume_precision"] = round(float(y[ff].mean()), 4); rule["full_hazard_same_volume_recall"] = round(float(ff[y == 1].mean()), 4)
        out["edge_rule_V8"] = rule
    # iteration 10, PRE-REGISTERED (X73): the same frozen scores against the point-in-time clean label (a match on o in
    # [t + D + delta, t + D + delta + 500) ms, i.e. a decision at a - delta in [t, t + 500)); never refit.
    y2 = getattr(_live_hazard_data, "y_pit", None)
    if y2 is not None and len(y2) == len(y) and y2.min() != y2.max():
        pit = {"positives": int(y2.sum()), "auc_full": round(float(_auc(y2, sf)), 4), "auc_pm_activity_baseline": round(float(_auc(y2, sb)), 4)}
        g2 = []
        rng2 = np.random.default_rng(4)
        for _ in range(2000):
            pick = np.concatenate([idx[u] for u in rng2.choice(uu, len(uu))])
            if y2[pick].min() == y2[pick].max():
                continue
            g2.append(_auc(y2[pick], sf[pick]) - _auc(y2[pick], sb[pick]))
        g2 = np.array(g2)
        pit["gain"] = round(pit["auc_full"] - pit["auc_pm_activity_baseline"], 4)
        pit["gain_ci95_window_bootstrap"] = [round(float(np.percentile(g2, 2.5)), 4), round(float(np.percentile(g2, 97.5)), 4)] if len(g2) else None
        out["pit_label"] = pit
    return out


def _pnl_overlap(fills: pd.DataFrame, win: pd.DataFrame) -> dict | None:
    """Iteration 7 (X28, diagnostics only; uses the wallet's OWN fills, so it never counts toward the target): per-window
    PnL is a sum of order-level bets (PnL ~ net x outcome); split-half reliability of a wallet's own orders, and the
    oracle-decision ceilings of a replica that holds the wallet's exact orders at a fixed 30 shares or at its size class
    (>= 90 filled shares -> 100, else 30)."""
    if not len(fills):
        return None
    f = fills.assign(pay=np.where(fills.is_up, fills.up_payout, 1 - fills.up_payout))
    f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd
    f["usd"] = f.shares * f.price
    o = f.groupby(["wallet", "oh"], sort=False).agg(cid=("cid", "first"), pay=("pay", "first"), shares=("shares", "sum"), usd=("usd", "sum"),
                                                    fee=("fee_usd", "sum"), pnl=("pnl", "sum")).reset_index()
    o["vwap"] = o.usd / o.shares; o["fps"] = o.fee / o.shares; o["big"] = o.shares >= 90
    o["half"] = o.oh.str[-1].map(lambda c: int(c, 16) % 2)
    cids = win.cid.to_numpy()

    def pw(df, col):
        return df.groupby("cid")[col].sum().reindex(cids).fillna(0.0).to_numpy()

    def cc(a, b):
        return [round(float(np.corrcoef(a, b)[0, 1]), 4), round(float(pd.Series(a).corr(pd.Series(b), method="spearman")), 4)] if np.std(a) > 0 and np.std(b) > 0 else None
    out = {}
    for w in ("DS", "GF", "XM", "pool"):
        x = o if w == "pool" else o[o.wallet == w]
        if not len(x):
            continue
        tot = pw(x, "pnl")
        x = x.assign(p30=30 * (x.pay - x.vwap - x.fps), pcl=np.where(x.big, 100, 30) * (x.pay - x.vwap - x.fps))
        out[w] = {"orders": int(len(x)), "big_share": round(float(x.big.mean()), 4), "split_half": cc(pw(x[x.half == 0], "pnl"), pw(x[x.half == 1], "pnl")),
                  "big_orders_vs_total": cc(pw(x[x.big], "pnl"), tot), "oracle_30_shares": cc(pw(x, "p30"), tot), "oracle_size_class": cc(pw(x, "pcl"), tot)}
    return out


def _b1_ladder(fills: pd.DataFrame, win: pd.DataFrame, n_max: int = B1_SAMPLE_TXS) -> dict | None:
    """Iteration 5 (catalog B1, order generation decoded from V2 calldata): every cluster order is PRE-SIGNED in a burst
    (a ladder over the 1-cent price grid, both outcomes) at three fixed times per window, rel = -89.5 s, +42.4 s and
    +173.3 s; an order is submitted 4-136 s after it was signed. Prediction checked here on a seeded sample of the
    period's cluster transactions: the share of filled cluster orders whose signing timestamp (calldata) falls in a
    predicted batch, and the share signed >= 3 s before their block."""
    try:
        import calldata as _cd
    except Exception:
        return None
    if fills.empty:
        return None
    txs = fills.tx.drop_duplicates()
    txs = txs.sample(min(n_max, len(txs)), random_state=11).tolist()
    try:
        rows = _cd.fetch_txs(txs, threads=2, log_every=10**9)
    except Exception as e:
        return {"error": type(e).__name__}
    d = _cd.to_frame(rows)
    if d.empty or "maker" not in d:
        return None
    touch = _calldata_touch(d)
    d = d[d.role.isin(["T", "M"]) & d.maker.str.lower().isin(WALLETS)].copy()
    tsm = fills.drop_duplicates("tx").set_index("tx")[["ts", "start_ts"]]
    d = d.join(tsm, on="tx")
    d["rel_sign"] = d.sign_ms / 1000.0 - d.start_ts
    d["gap"] = d.ts - d.sign_ms / 1000.0
    inb = np.zeros(len(d), bool)
    for c, w in LADDER_BATCHES:
        inb |= np.abs(d.rel_sign.to_numpy() - c) <= w
    d["wallet"] = d.maker.str.lower().map(WALLETS)
    out = {"orders": int(len(d)), "share_signed_in_predicted_batches": round(float(inb.mean()), 4) if len(d) else None,
           "chance_share_of_batches": round(sum(2 * w for _, w in LADDER_BATCHES) / 300.0, 4),
           "share_gap_ge_3s": round(float((d.gap >= 3.0).mean()), 4) if len(d) else None,
           "gap_median_s": round(float(d.gap.median()), 2) if len(d) else None,
           "by_wallet": {w: round(float(inb[(d.wallet == w).to_numpy()].mean()), 4) for w in ("GF", "XM", "DS") if (d.wallet == w).any()},
           "salt_over_sign_ms_max": round(float((d.salt.astype(float) / d.sign_ms.astype(float)).max()), 4) if len(d) else None,
           "calldata_touch": touch}
    return out


def _calldata_touch(d: pd.DataFrame) -> dict | None:
    """Iteration 6 (price component, historical): the touch at each match is on chain. For every cluster TAKER order of a
    sampled matchOrders tx, the effective asks of the maker orders it consumed (a SELL of the same token at p is an ask at
    p; a BUY of the complementary token at q is an ask at 1 - q). Rule: limit = the touch (best consumed effective ask).
    This measures the decoded rule on the match itself (the trivial 'touch' anchor, stated as such); it is not a PIT
    forecast of the touch. VALIDATE + BUILD sample (11 h, 11,382 taker orders): equal 83.1%, within one tick 94.8%."""
    if d.empty:
        return None
    d = d.copy()
    d["px"] = np.where(d.oside == 0, d.maker_amt / d.taker_amt, d.taker_amt / d.maker_amt)
    tk = d[(d.role == "T") & d.maker.str.lower().isin(WALLETS)].copy()
    mk = d[d.role == "M"][["tx", "token", "oside", "px"]].merge(tk[["tx", "token"]].rename(columns={"token": "t_token"}), on="tx")
    if tk.empty or mk.empty:
        return None
    same = mk.token == mk.t_token
    mk["eff"] = np.where(same & (mk.oside == 1), mk.px, np.where(~same & (mk.oside == 0), 1.0 - mk.px, np.nan))
    g = mk.groupby("tx").agg(best=("eff", "min"), worst=("eff", "max"))
    tk = tk.join(g, on="tx")
    tk = tk[tk.best.notna()]
    if tk.empty:
        return None
    db = (tk.px - tk.best).round(4)
    tk["wallet"] = tk.maker.str.lower().map(WALLETS)
    res = {"n_taker_orders": int(len(tk)), "limit_eq_touch": round(float((db.abs() < 1e-6).mean()), 4),
           "within_1tick_touch": round(float((db.abs() <= 0.0100001).mean()), 4),
           "limit_above_every_consumed_level": round(float(((tk.px - tk.worst).round(4) > 1e-6).mean()), 4),
           "by_wallet": {w: round(float((db[(tk.wallet == w).to_numpy()].abs() <= 0.0100001).mean()), 4) for w in ("GF", "XM", "DS") if (tk.wallet == w).any()}}
    return res


def evaluate(start_ts: int, end_ts: int, intervals=None) -> dict:
    """The frozen rule on [start_ts, end_ts) (only windows starting in `intervals` when given). Iteration 8 robustness wrapper
    (the rule is unchanged): if the historical pipeline cannot run (e.g. the Binance daily archive of a recent day is not
    published yet, so the spot frame is empty), the live components are still computed from the exam-input recordings and
    returned with the historical keys set to None and the error recorded."""
    try:
        return _evaluate_full(start_ts, end_ts, intervals)
    except Exception as e:
        return _evaluate_live_only(start_ts, end_ts, intervals, f"{type(e).__name__}: {e}"[:300])


def _evaluate_live_only(start_ts: int, end_ts: int, intervals, err: str) -> dict:
    t0 = time.time()
    win = load_windows(start_ts, end_ts)
    win = win[win.up_payout.notna()].sort_values("start_ts").reset_index(drop=True)
    if intervals:
        st = win.start_ts.to_numpy()
        keep = np.zeros(len(win), bool)
        for a, b in intervals:
            keep |= (st >= a) & (st < b)
        win = win[keep].reset_index(drop=True)
    out = {"historical_error": err, "windows": int(len(win)),
           "note": "historical components need the Binance daily archives (published the next day UTC); live components only"}
    fills = cluster_fills(start_ts, end_ts, win)
    out["fills"] = int(len(fills))
    try:  # iteration 14 (pre-registration 5): decision-clock side re-anchored on exchange time (dc_exam14; needs no Binance daily archive)
        import dc_exam14
        out["side_decision_clock"] = dc_exam14.decision_clock_side(fills, start_ts, end_ts, allow_sealed=ALLOW_SEALED)
    except Exception as e:
        out["side_decision_clock"] = {"error": f"{type(e).__name__}: {e}"[:200]}
    try:  # iteration 14 (X126 = X136): decision-clock take hazard on the knee clock (dc_hazard14; reported, VALIDATE-only)
        import dc_hazard14
        out["presence_decision_clock"] = dc_hazard14.decision_clock_presence(fills, win, start_ts, end_ts, allow_sealed=ALLOW_SEALED)
    except Exception as e:
        out["presence_decision_clock"] = {"error": f"{type(e).__name__}: {e}"[:200]}
    for key, fn in (("side_live_decision", lambda: _live_vote(fills, win, start_ts, end_ts)),
                    ("side_live_decision_ext", lambda: _live_vote(fills, win, start_ts, end_ts, feeds=LIVE_VOTE_FEEDS_EXT, venues=LIVE_VOTE_VENUES_EXT)),
                    ("presence_live_decision", lambda: _live_hazard(fills, start_ts, end_ts, intervals)),
                    ("price_live_book", lambda: _live_touch(fills, win, start_ts, end_ts)),
                    ("side_live_decision_pit", lambda: _live_vote(fills, win, start_ts, end_ts, win_ms=LIVE_VOTE_WIN_MS_PIT)),
                    ("price_live_book_pit", lambda: _live_touch(fills, win, start_ts, end_ts, pre_ms=PRE_MATCH_MS_PIT))):
        try:
            out[key] = fn()
        except Exception as e:
            out[key] = {"error": type(e).__name__}
    sl = out.get("side_live_decision") or {}
    pl = out.get("presence_live_decision") or {}
    lb = out.get("price_live_book") or {}
    out["target_metrics"] = {k: None for k in ("presence_auc", "presence_baseline", "selection_auc", "selection_baseline", "selection_recall", "selection_lift",
                                                "side_accuracy", "side_baseline", "pnl_corr_pearson", "pnl_corr_spearman")}
    out["target_metrics"].update({
        "side_accuracy_live_decision": sl.get("agree_on_voted"), "side_accuracy_live_decision_abstain_half": sl.get("accuracy_all_covered_abstain_half"),
        "side_accuracy_live_decision_full_coverage": (sl.get("full_coverage") or {}).get("accuracy"),
        "presence_live_decision_auc": pl.get("auc_full"), "presence_live_decision_baseline": pl.get("auc_pm_activity_baseline"),
        "price_within_tick": lb.get("within_1tick_ask_match") if isinstance(lb, dict) else None,
        "coverage_fills": 1.0 if len(fills) else None, "coverage_abs_pnl": 1.0 if len(fills) else None})
    sp = out.get("side_live_decision_pit") or {}; lp = out.get("price_live_book_pit") or {}
    out["target_metrics"].update({
        "side_accuracy_live_decision_pit": sp.get("agree_on_voted") if isinstance(sp, dict) else None,
        "side_accuracy_live_decision_pit_full_coverage": (sp.get("full_coverage") or {}).get("accuracy") if isinstance(sp, dict) else None,
        "price_within_tick_live_pit": lp.get("within_1tick_ask_match") if isinstance(lp, dict) else None,
        "presence_live_decision_auc_pit": ((pl.get("pit_label") or {}).get("auc_full")) if isinstance(pl, dict) else None,
        "presence_live_decision_baseline_pit": ((pl.get("pit_label") or {}).get("auc_pm_activity_baseline")) if isinstance(pl, dict) else None})
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


def _evaluate_full(start_ts: int, end_ts: int, intervals=None) -> dict:
    t0 = time.time()
    win = load_windows(start_ts, end_ts)
    win = win[win.up_payout.notna()].sort_values("start_ts").reset_index(drop=True)
    if intervals:  # only units (windows) that START in one of the [a, b) intervals count
        st = win.start_ts.to_numpy()
        keep = np.zeros(len(win), bool)
        for a, b in intervals:
            keep |= (st >= a) & (st < b)
        win = win[keep].reset_index(drop=True)
    sp, spot_frame = load_spot(start_ts, end_ts)
    fills = cluster_fills(start_ts, end_ts, win)
    tf.TAPE_DIR = load_tapes(win, end_ts)
    cells = cellsmod.build_cells(win, fills, sp)
    cells = tf.add_tape_feats(cells, fills, sp)
    cells = add_inv(cells, fills, len(win))
    cells = add_extra(cells)
    cells = add_reference_feats(cells, spot_frame, end_ts)
    p = _predict(MODEL_Y, cells, FEATURES)
    pT = _predict(MODEL_T, cells, FEATURES)
    pM = _predict(MODEL_M, cells, FEATURES)
    pK = _predict(MODEL_MKT, cells, MARKET_FEATURES)
    pO = _predict(MODEL_OWN, cells, OWN_FEATURES)
    p2 = _predict(MODEL_IT2, cells, IT2_FEATURES)
    cells["p"] = p; cells["p_mkt"] = pK; cells["p_it2"] = p2
    cells["sh"] = np.clip(_predict(MODEL_SHARES, cells, FEATURES), 0, None) if os.path.exists(MODEL_SHARES) else np.nan
    # iteration 5 (D1): decision-aligned presence. The bot's pre-signed order is SUBMITTED at the decision time, which the
    # live lab puts ~2.0 s before its block; label y1 = cluster fill at block second s + 1 predicted from cell s (horizon
    # s - 1 = decision time), against the PURE market-activity baseline (no reference feed at all; the older baseline
    # contained Binance fair-value gaps and the spot move since the last print).
    dp = None
    if all(os.path.exists(f) for f in (MODEL_DP_FULL, MODEL_DP_PURE, MODEL_DP0_PURE)):
        y1 = _shift(cells.y.to_numpy(), 1)
        pf1 = _predict_named(MODEL_DP_FULL, cells); pb1 = _predict_named(MODEL_DP_PURE, cells); pb0 = _predict_named(MODEL_DP0_PURE, cells)
        dp = {"label": "cluster BUY fill at block second s+1 (decision time = s-1 horizon)", "auc_full": _auc(y1, pf1),
              "auc_pure_market_baseline": _auc(y1, pb1),
              "auc_block_label_pure_market_baseline": _auc(cells.y, pb0),
              "by_wallet": {w: {"full": _auc(_shift(cells[f"y{w}"].to_numpy(), 1), pf1), "pure": _auc(_shift(cells[f"y{w}"].to_numpy(), 1), pb1)} for w in ("GF", "XM", "DS")}}
        dp["gain"] = round(dp["auc_full"] - dp["auc_pure_market_baseline"], 4) if dp["auc_full"] and dp["auc_pure_market_baseline"] else None
        dp["gain_block_bootstrap_2h"] = _block_boot_gain(y1, pf1, pb1, (cells.start_ts.to_numpy() + cells.rel.to_numpy()) // 7200)
        dp["at_threshold"] = _recall_lift(y1, pf1 >= P_THRESH)
        cells["p_pure"] = pb0
    blk = None
    if all(os.path.exists(f) for f in (MODEL_BLK_FULL, MODEL_BLK_PURE)) and len(fills):
        tsec = (cells.start_ts.to_numpy() + cells.rel.to_numpy()).astype(np.int64)
        kb = _block_keep(tsec, fills[["block", "ts"]])
        cb = cells[kb]
        pfb = _predict_named(MODEL_BLK_FULL, cb); ppb = _predict_named(MODEL_BLK_PURE, cb)
        yb = cb.y.to_numpy()
        blk = {"unit": "block seconds (Polygon block clock fitted per hour; seconds without a block cannot hold a fill)",
               "share_cells_kept": round(float(kb.mean()), 4), "positives_outside_block_seconds": int(((cells.y.to_numpy() == 1) & ~kb).sum()),
               "auc_full": _auc(yb, pfb), "auc_pure_market_baseline": _auc(yb, ppb),
               "by_wallet": {w: {"full": _auc(cb[f"y{w}"].to_numpy(), pfb), "pure": _auc(cb[f"y{w}"].to_numpy(), ppb)} for w in ("GF", "XM", "DS")},
               "gain_block_bootstrap_2h": _block_boot_gain(yb, pfb, ppb, tsec[kb] // 7200)}
        blk["gain"] = round(blk["auc_full"] - blk["auc_pure_market_baseline"], 4) if blk["auc_full"] and blk["auc_pure_market_baseline"] else None
        half = tsec[kb] < (int(start_ts) + int(end_ts)) // 2
        blk["halves"] = {nm: {"full": _auc(yb[m], pfb[m]), "pure": _auc(yb[m], ppb[m])} for nm, m in (("first", half), ("second", ~half)) if m.any()}
        blk["at_threshold"] = _recall_lift(yb, pfb >= P_THRESH)
    flag = p >= P_THRESH
    out = {"period": [int(start_ts), int(end_ts)], "windows": int(len(win)), "cells": int(len(cells)), "cluster_fills": int(len(fills)),
           "use_venues": USE_VENUES, "six_series": SIX_SERIES, "use_alts": USE_ALTS, "alt_set": ALT_SET, "models": _TAG,
           "reference_feed_coverage": {"futures": round(float(np.isfinite(cells.F_pm1000).mean()), 4)}}
    if USE_ALTS:
        out["reference_feed_coverage"].update({sub: round(float(np.isfinite(cells[f"{p}_pm1000"]).mean()), 4) for p, sub in _ALTS})
    if USE_VENUES:
        out["reference_feed_coverage"].update({"okx": round(float(np.isfinite(cells.O_pm1000).mean()), 4), "bybit": round(float(np.isfinite(cells.B_pm1000).mean()), 4)})
        if SIX_SERIES:
            out["reference_feed_coverage"].update({k: round(float(np.isfinite(cells[f"{p}_pm1000"]).mean()), 4) for p, k in (("S", "binance_spot_aggtrades"), ("Y", "bybit_spot"), ("K", "okx_spot"))})
    # (a) presence, with the co-occurrence baseline (market activity only) and the own-state variant
    a_any = _auc(cells.y, p); a_mkt = _auc(cells.y, pK)
    out["presence"] = {
        "auc_any_no_own_state": a_any, "auc_taker": _auc(cells.yT, pT), "auc_maker": _auc(cells.yM, pM),
        "auc_any_by_wallet": {w: _auc(cells[f"y{w}"], p) for w in ("GF", "XM", "DS")},
        "co_occurrence_baseline_auc": a_mkt, "gain_over_baseline": round(a_any - a_mkt, 4) if a_any and a_mkt else None,
        "auc_with_own_state": _auc(cells.y, pO), "auc_iteration2_rule_spot_tape": _auc(cells.y, p2),
        "base_rate": round(float(cells.y.mean()), 4), "at_threshold": _recall_lift(cells.y, flag),
        "baseline_at_threshold": _recall_lift(cells.y, pK >= P_THRESH),
        "pure_market_baseline_auc_block_label": dp.get("auc_block_label_pure_market_baseline") if dp else None,
        "decision_aligned": dp,
        "block_seconds": blk,
    }
    # (b) side: seconds where the cluster bought exactly one outcome; rule = dedicated side model (ps >= 0.5 -> Up)
    up, dn = _pairs(cells)
    X = pd.concat([up[FEATURES].reset_index(drop=True), pd.DataFrame({"D_" + k: dn[k].to_numpy() for k in DSIDE})], axis=1)
    nf = _predict(MODEL_NETFLOW, X, SIDE_FEATURES) if os.path.exists(MODEL_NETFLOW) else None  # signed net share flow per second
    if SIDE_LAG:
        X = lag_feats(X, ALT_BETA)
    ps = _predict(MODEL_SIDE, X, SIDE_FEATURES + (list(LAG_FEATS) if SIDE_LAG else []))
    ps_it4 = ps
    if USE_BOOK and SIDE_LAG and os.path.exists(MODEL_SIDE_BOOK):  # iteration 5: + Bybit perpetual top-of-book features
        X = _add_book(X, up.start_ts.to_numpy(np.int64) + up.rel.to_numpy(np.int64), end_ts)
        out["reference_feed_coverage"]["bybit_book"] = round(float(np.isfinite(X.BK_imb.to_numpy(float)).mean()), 4)
        ps = _predict(MODEL_SIDE_BOOK, X, SIDE_FEATURES + list(LAG_FEATS) + list(BOOK_FEATS))
    del X
    sd = {}
    r3z = np.abs(up.r3.to_numpy()) < 0.01
    mx6 = np.nanmax(np.abs(np.stack([up[f"{q}_pm3000"].to_numpy(float) for q in "FOBSYK"], 1)), 1) if SIX_SERIES else np.full(len(up), np.nan)
    flat6 = mx6 <= 0.1  # no move above 0.1 bp on any of the six BTC series over the last 3 s before the horizon
    for lab in ("y", "yT"):
        one = (up[lab].to_numpy() + dn[lab].to_numpy()) == 1
        truth = up[lab].to_numpy()[one] == 1
        ok1 = (ps[one] >= 0.5) == truth
        okp = (up.p.to_numpy()[one] >= dn.p.to_numpy()[one]) == truth
        ok0 = (up.p_mkt.to_numpy()[one] >= dn.p_mkt.to_numpy()[one]) == truth
        okf = (up.m_last.to_numpy()[one] >= 0.5) == truth
        conf = np.abs(ps[one] - 0.5); q50 = np.quantile(conf, 0.5) if len(conf) else 0
        ok4 = (ps_it4[one] >= 0.5) == truth
        sd[lab] = {"n_seconds": int(one.sum()), "accuracy_side_model": round(float(ok1.mean()), 4),
                   "accuracy_side_model_it4b_without_book": round(float(ok4.mean()), 4), "mcnemar_p_vs_it4b_without_book": _mcnemar(ok1, ok4),
                   "accuracy_presence_argmax": round(float(okp.mean()), 4),
                   "baseline_market_only_model": round(float(ok0.mean()), 4), "baseline_favourite": round(float(okf.mean()), 4),
                   "mcnemar_p_vs_market_only": _mcnemar(ok1, ok0), "mcnemar_p_vs_favourite": _mcnemar(ok1, okf),
                   "accuracy_spot_3s_move_zero": round(float(ok1[r3z[one]].mean()), 4), "share_spot_3s_move_zero": round(float(r3z[one].mean()), 4),
                   "accuracy_spot_moving": round(float(ok1[~r3z[one]].mean()), 4),
                   "accuracy_six_series_flat": round(float(ok1[flat6[one]].mean()), 4) if flat6[one].any() else None,
                   "share_six_series_flat": round(float(flat6[one].mean()), 4),
                   "accuracy_six_series_moving": round(float(ok1[~flat6[one]].mean()), 4) if (~flat6[one]).any() else None,
                   "accuracy_top_half_confidence": round(float(ok1[conf >= q50].mean()), 4)}
    sd["by_wallet"] = {}
    for w in ("GF", "XM", "DS"):
        if f"y{w}" in up and f"y{w}" in dn:
            one_w = (up[f"y{w}"].to_numpy() + dn[f"y{w}"].to_numpy()) == 1
            if one_w.any():
                tr_w = up[f"y{w}"].to_numpy()[one_w] == 1
                sd["by_wallet"][w] = {"n_seconds": int(one_w.sum()), "accuracy_side_model": round(float(((ps[one_w] >= 0.5) == tr_w).mean()), 4)}
    # iteration 7: side in the pre-registered DECISION units (per taker order at the block second of its first fill; per
    # one-sided window by its first taker order), every taker order scored (no one-sided-second filter), with the
    # market-only baseline (presence of the market-activity model, argmax over the two outcomes) on the same orders
    try:
        idx = pd.MultiIndex.from_arrays([up.cid.to_numpy(), up.rel.to_numpy().astype(np.int64)])
        psmap = pd.Series(ps, index=idx); pkmap = pd.Series(up.p_mkt.to_numpy() - dn.p_mkt.to_numpy(), index=idx)
        fo = fills.groupby(["wallet", "oh"], sort=False).agg(cid=("cid", "first"), rel=("rel", "first"), role0=("role", "first"), is_up=("is_up", "first")).reset_index()
        fo = fo[(fo.role0 == "T") & (fo.rel >= 0) & (fo.rel < 300)].copy()
        ii = pd.MultiIndex.from_arrays([fo.cid.to_numpy(), fo.rel.to_numpy().astype(np.int64)])
        fo["ps"] = psmap.reindex(ii).to_numpy(); fo["pk"] = pkmap.reindex(ii).to_numpy()
        fo = fo[np.isfinite(fo.ps.to_numpy(float))]
        sdu = {}
        for w in ("GF", "XM", "DS", "pool"):
            x = fo if w == "pool" else fo[fo.wallet == w]
            if not len(x):
                continue
            ws = (fills if w == "pool" else fills[fills.wallet == w]).groupby("cid").is_up.agg(["min", "max"])
            one = set(ws.index[ws["min"] == ws["max"]])
            xf = x[x.cid.isin(one)].drop_duplicates("cid")
            sdu[w] = {"taker_orders": int(len(x)), "accuracy_per_order": round(float(((x.ps >= 0.5) == x.is_up).mean()), 4),
                      "baseline_market_only_per_order": round(float(((x.pk >= 0) == x.is_up).mean()), 4),
                      "one_sided_windows": int(len(one)), "n_windows_scored": int(len(xf)),
                      "accuracy_per_one_sided_window_first_decision": round(float(((xf.ps >= 0.5) == xf.is_up).mean()), 4) if len(xf) else None,
                      "baseline_market_only_per_window": round(float(((xf.pk >= 0) == xf.is_up).mean()), 4) if len(xf) else None}
        sd["decision_units"] = sdu
    except Exception as e:
        sd["decision_units"] = {"error": repr(e)[:200]}
    out["side"] = sd
    # (c) price: predicted taker price = last implied ask of the outcome from others' prints (<= s-1)
    key = cells.set_index(["cid", "is_up", "rel"])[["ask_o"]]
    fz = fills[(fills.rel >= 0) & (fills.rel < 300)]
    j = fz.join(key, on=["cid", "is_up", "rel"])
    out["price"] = {}
    for role in ("T", "M"):
        g = j[(j.role == role) & np.isfinite(j.ask_o)]
        out["price"][f"{role}_within_1tick_of_last_ask"] = round(float((np.abs(g.price - g.ask_o) <= 0.0101).mean()), 4) if len(g) else None
    # selection: all in-window taker prints (every trader), cluster vs others, scored by p of the print's cell
    rows = []
    for cid in win.cid:
        tp = f"{tf.TAPE_DIR}/{cid}.parquet"
        if os.path.exists(tp):
            d = pd.read_parquet(tp)
            if len(d) and "timestamp" in d:
                rows.append(d[["proxyWallet", "outcome", "timestamp", "price", "size"]].assign(cid=cid))
    if rows:
        tp = pd.concat(rows).merge(win[["cid", "start_ts"]], on="cid")
        tp["rel"] = tp.timestamp - tp.start_ts
        tp = tp[(tp.rel >= 0) & (tp.rel < 300)]
        tp["is_up"] = tp.outcome == "Up"
        tp = tp.join(cells.set_index(["cid", "is_up", "rel"])[["p", "p_mkt"] + (["p_pure"] if "p_pure" in cells else [])], on=["cid", "is_up", "rel"])
        lab = tp.proxyWallet.str.lower().isin(WALLETS).to_numpy()
        size_rule = np.isin(np.round(tp["size"].astype(float).to_numpy(), 2), ORDER_SIZES)
        score = size_rule.astype(float) + tp.p.to_numpy()
        aw, ww = [], []
        for _, g in pd.DataFrame({"cid": tp.cid.to_numpy(), "lab": lab, "score": score}).groupby("cid"):
            if 0 < g.lab.sum() < len(g):
                aw.append(roc_auc_score(g.lab, g.score)); ww.append(g.lab.sum())
        out["selection"] = {"taker_prints": int(len(tp)), "cluster_share": round(float(lab.mean()), 4),
                            "auc_cell_score_only": _auc(lab, tp.p.to_numpy()), "co_occurrence_baseline_auc": _auc(lab, tp.p_mkt.to_numpy()),
                            "auc_size_plus_cell_score": _auc(lab, score),
                            "co_occurrence_baseline_auc_size_plus_market_only_score": _auc(lab, size_rule.astype(float) + tp.p_mkt.to_numpy()),
                            "auc_within_window_size_plus_cell_score": round(float(np.average(aw, weights=ww)), 4) if aw else None,
                            "at_preregistered_threshold_score_ge_1.30": _recall_lift(lab, score >= SEL_THRESH),
                            "size_rule_only": _recall_lift(lab, size_rule),
                            "note": "pooled AUC over in-window taker prints of every trader"}
        # iteration 3 (sizes decoded on BUILD): full orders {30, 50, 60, 100}; partial fills of an order are multiples of 5 below 30
        sz = np.round(tp["size"].astype(float).to_numpy(), 2)
        full = np.isin(sz, FULL_SIZES); part = np.isin(sz, PARTIAL_SIZES)
        score3 = 2.0 * full + 1.0 * part + tp.p.to_numpy()
        flag3 = full | (part & (tp.p.to_numpy() >= P_THRESH))
        aw3, ww3 = [], []
        for _, g in pd.DataFrame({"cid": tp.cid.to_numpy(), "lab": lab, "score": score3}).groupby("cid"):
            if 0 < g.lab.sum() < len(g):
                aw3.append(roc_auc_score(g.lab, g.score)); ww3.append(g.lab.sum())
        out["selection"]["v3_size_classes"] = {
            "auc_pooled": _auc(lab, score3), "auc_within_window": round(float(np.average(aw3, weights=ww3)), 4) if aw3 else None,
            "co_occurrence_baseline_auc": _auc(lab, 2.0 * full + 1.0 * part + tp.p_mkt.to_numpy()),
            "pure_market_baseline_auc": _auc(lab, 2.0 * full + 1.0 * part + tp.p_pure.to_numpy()) if "p_pure" in tp else None,
            "at_preregistered_flag_full_or_partial_and_p_ge_0.30": _recall_lift(lab, flag3),
            "baseline_flag_full_or_partial_and_p_mkt_ge_0.30": _recall_lift(lab, full | (part & (tp.p_mkt.to_numpy() >= P_THRESH)))}
    # outcome: per-window PnL correlation; soft proxy = p x 30 shares at the last implied ask (primary), hard = flag -> 30 shares
    pay_u = up.merge(win[["cid", "up_payout"]], on="cid", how="left").up_payout.to_numpy()
    res_o = {}
    okU = np.isfinite(up.ask_o.to_numpy()) & (up.ask_o.to_numpy() > 0.05) & (up.ask_o.to_numpy() < 0.95)
    okD = np.isfinite(dn.ask_o.to_numpy()) & (dn.ask_o.to_numpy() > 0.05) & (dn.ask_o.to_numpy() < 0.95)
    aU = np.nan_to_num(up.ask_o.to_numpy()); aD = np.nan_to_num(dn.ask_o.to_numpy())
    uU = np.where(okU, pay_u - aU - FEE_RATE * aU * (1 - aU), 0.0); uD = np.where(okD, (1 - pay_u) - aD - FEE_RATE * aD * (1 - aD), 0.0)
    pu, pdn = up.p.to_numpy(), dn.p.to_numpy(); vol = pu + pdn
    fw = fills.assign(pay=np.where(fills.is_up, fills.up_payout, 1 - fills.up_payout)) if len(fills) else fills
    fw["pnl"] = fw.shares * (fw.pay - fw.price) - fw.fee_usd
    wal_w = fw.groupby("cid").pnl.sum().rename("wallet")
    variants = [("soft", pu * okU, pdn * okD), ("hard", (pu >= P_THRESH) * okU, (pdn >= P_THRESH) * okD), ("soft_side", vol * ps * okU, vol * (1 - ps) * okD)]
    if nf is not None:  # iteration 4: buy the predicted signed net flow (shares) of the cluster in every second
        variants.append(("netflow", np.clip(nf, 0, None) / ORDER_SHARES * okU, np.clip(-nf, 0, None) / ORDER_SHARES * okD))
    if np.isfinite(up.sh.to_numpy()).all():  # iteration 4 (primary): buy the predicted cluster shares of each outcome in every cell
        variants.append(("shares", up.sh.to_numpy() / ORDER_SHARES * okU, dn.sh.to_numpy() / ORDER_SHARES * okD))
    for nm, wu, wd in variants:
        g = pd.DataFrame({"cid": up.cid.to_numpy(), "pnl": ORDER_SHARES * (wu * uU + wd * uD), "usd": ORDER_SHARES * (wu * aU + wd * aD)}).groupby("cid").sum()
        both = g.join(wal_w, how="outer").reindex(win.cid).fillna(0.0)
        res_o[f"per_window_pnl_corr_{nm}_pearson"] = round(float(both.pnl.corr(both.wallet)), 4)
        res_o[f"per_window_pnl_corr_{nm}_spearman"] = round(float(both.pnl.corr(both.wallet, method="spearman")), 4)
        res_o[f"rule_return_{nm}"] = round(float(both.pnl.sum() / both.usd.sum()), 4) if both.usd.sum() > 0 else None
    res_o["wallet_return_before_rebates"] = round(float(fw.pnl.sum() / fw.usdc.sum()), 4) if len(fw) else None
    res_o["note"] = ("rule PnL is a proxy (buys at the last observed ask at s-1, no queue/fill check), not a strict-fill backtest; "
                     "primary = shares (iteration 4, chosen on VALIDATE: Pearson 0.439, net-position corr 0.467; netflow 0.434, soft_side 0.426, soft 0.418)")
    res_o["primary"] = "shares" if np.isfinite(up.sh.to_numpy()).all() else "soft_side"
    res_o["strict_fill_backtest"] = _strict_backtest(up, dn, ps, win, fills) if len(fills) else None
    # iteration 12 (pre-registered): exposure tracker on the target flow 0.5 x it4b netflow + 0.5 x nf12b (primary, (a))
    try:
        flow4 = np.nan_to_num(np.asarray(nf, float)) if nf is not None else np.zeros(len(up))
        f12 = _nf12b_flow(cells, sp, up) if os.path.exists(MODEL_NF12B) else np.zeros(len(up))
        flow = TRK_W_IT4B * flow4 + TRK_W_NF12B * f12
        res_o["exposure_tracker"] = {"primary": "avg_a", "target_flow": f"{TRK_W_IT4B} x it4b netflow + {TRK_W_NF12B} x nf12b",
                                     "avg_a": _strict_tracker(up, dn, flow, win, fills, "a") if len(fills) else None,
                                     "avg_b": _strict_tracker(up, dn, flow, win, fills, "b") if len(fills) else None,
                                     "it4b_only_a": _strict_tracker(up, dn, flow4, win, fills, "a") if len(fills) else None}
        # iteration 14 (PRE-REGISTRATION 7, adopted): target = 0.5 x the avg flow + 0.5 x HAZ_C x the decision-hazard imbalance h(s)
        # from the public capture (dc_hazard14.hazard_imbalance; VALIDATE 10-20..22: 0.5065 / 0.4674 vs avg 0.4973 / 0.4607)
        try:
            import dc_hazard14
            hz = dc_hazard14.hazard_imbalance(fills, win, start_ts, end_ts, allow_sealed=ALLOW_SEALED)
            if hz is not None and len(hz) and len(fills):
                hv = hz.set_index(["cid", "rel"]).h.reindex(pd.MultiIndex.from_arrays([up.cid.to_numpy(), up.rel.to_numpy().astype(np.int64)])).fillna(0.0).to_numpy()
                flow_mix = 0.5 * flow + 0.5 * dc_hazard14.HAZ_C * hv
                res_o["exposure_tracker"]["mix14_a"] = _strict_tracker(up, dn, flow_mix, win, fills, "a")
                res_o["exposure_tracker"]["mix14_hazard_coverage"] = round(float((hv != 0).mean()), 4)
                res_o["exposure_tracker"]["primary"] = "mix14_a"
                res_o["exposure_tracker"]["target_flow"] = "0.5 x (0.5 it4b + 0.5 nf12b) + 0.5 x HAZ_C x hazard imbalance (dc_hazard14)"
        except Exception as e:
            res_o["exposure_tracker"]["mix14_error"] = repr(e)[:300]
    except Exception as e:
        res_o["exposure_tracker"] = {"error": repr(e)[:300]}
    # per-wallet PnL correlation of the primary proxy
    prim = [v for v in variants if v[0] == res_o["primary"]]
    if prim and len(fw):
        nm, wu, wd = prim[0]
        g = pd.DataFrame({"cid": up.cid.to_numpy(), "pnl": ORDER_SHARES * (wu * uU + wd * uD)}).groupby("cid").pnl.sum()
        res_o["per_window_pnl_corr_primary_by_wallet"] = {}
        for w in ("GF", "XM", "DS"):
            ww = fw[fw.wallet == w].groupby("cid").pnl.sum()
            bb = pd.DataFrame({"r": g}).join(ww.rename("w"), how="outer").reindex(win.cid).fillna(0.0)
            res_o["per_window_pnl_corr_primary_by_wallet"][w] = {"pearson": round(float(bb.r.corr(bb.w)), 4), "spearman": round(float(bb.r.corr(bb.w, method="spearman")), 4)}
    out["outcome"] = res_o
    # iteration 5: price against the recorded Polymarket book (where the live lab covers the period) and the B1 ladder check
    try:
        out["price"]["live_book"] = _live_touch(fills, win, start_ts, end_ts)
    except Exception as e:
        out["price"]["live_book"] = {"error": type(e).__name__}
    try:
        out["order_generation_b1"] = _b1_ladder(fills, win) if B1_SAMPLE_TXS > 0 else None
    except Exception as e:
        out["order_generation_b1"] = {"error": type(e).__name__}
    out["price"]["calldata_touch"] = (out.get("order_generation_b1") or {}).get("calldata_touch")
    # iteration 7: decision-level side on the exam-input recording (future blocks), and the PnL overlap diagnostics
    try:
        out["side_live_decision"] = _live_vote(fills, win, start_ts, end_ts)
    except Exception as e:
        out["side_live_decision"] = {"error": type(e).__name__}
    # iteration 8: pre-registered secondary vote with Bybit linear L1 (btc5m_xfam), and the decision-level hazard (presence)
    try:
        out["side_live_decision_ext"] = _live_vote(fills, win, start_ts, end_ts, feeds=LIVE_VOTE_FEEDS_EXT, venues=LIVE_VOTE_VENUES_EXT)
    except Exception as e:
        out["side_live_decision_ext"] = {"error": type(e).__name__}
    try:
        out["presence_live_decision"] = _live_hazard(fills, start_ts, end_ts, intervals)
    except Exception as e:
        out["presence_live_decision"] = {"error": type(e).__name__}
    # iteration 10 (X73, pre-registered): point-in-time clean live side and price under the 150-ms taker delay
    try:
        out["side_live_decision_pit"] = _live_vote(fills, win, start_ts, end_ts, win_ms=LIVE_VOTE_WIN_MS_PIT)
    except Exception as e:
        out["side_live_decision_pit"] = {"error": type(e).__name__}
    try:
        out["price"]["live_book_pit"] = _live_touch(fills, win, start_ts, end_ts, pre_ms=PRE_MATCH_MS_PIT)
    except Exception as e:
        out["price"]["live_book_pit"] = {"error": type(e).__name__}
    # iteration 14 (PRE-REGISTRATION 5, X125 = X135): the side at the DECISION clock re-anchored on EXCHANGE time (dc_exam14: matching-
    # engine ms by tx hash from the public HF capture; Binance spot book / trades cut at m - 260 ms exchange time; frozen
    # model_it14_dcside_spot.txt, fitted on 10-17..19; VALIDATE 10-20..22 83.7% per order). It is target_metrics.side_accuracy from
    # iteration 14 on (pre-registered consequence); the block-clock side model stays as side_accuracy_block_clock.
    try:
        import dc_exam14
        out["side_decision_clock"] = dc_exam14.decision_clock_side(fills, start_ts, end_ts, allow_sealed=ALLOW_SEALED)
    except Exception as e:
        out["side_decision_clock"] = {"error": f"{type(e).__name__}: {e}"[:200]}
    try:  # iteration 14 (X126 = X136): decision-clock take hazard on the knee clock (dc_hazard14; reported, VALIDATE-only)
        import dc_hazard14
        out["presence_decision_clock"] = dc_hazard14.decision_clock_presence(fills, win, start_ts, end_ts, allow_sealed=ALLOW_SEALED)
    except Exception as e:
        out["presence_decision_clock"] = {"error": f"{type(e).__name__}: {e}"[:200]}
    try:
        res_o["pnl_overlap_diagnostics"] = _pnl_overlap(fills, win)
    except Exception as e:
        res_o["pnl_overlap_diagnostics"] = {"error": type(e).__name__}
    # coverage: the rule's universe is every BTC 5m window of the period (all cluster fills and PnL are in it)
    one_w = None
    if len(fw):
        wsides = fw.groupby("cid").is_up.agg(["min", "max"])
        one_w = round(float((wsides["min"] == wsides["max"]).mean()), 4)
        # iteration 6: the side condition is judged per wallet (XM is one-sided in ~24% of its VALIDATE windows)
        out["side_condition_by_wallet"] = {}
        for w in ("GF", "XM", "DS"):
            x = fw[fw.wallet == w]
            if len(x):
                ws = x.groupby("cid").is_up.agg(["min", "max"])
                out["side_condition_by_wallet"][w] = {"windows": int(len(ws)), "share_one_sided_windows": round(float((ws["min"] == ws["max"]).mean()), 4)}
    lb = out["price"].get("live_book") or {}
    sb30 = res_o.get("strict_fill_backtest") or {}
    _et = res_o.get("exposure_tracker") or {}
    sb = _et.get(_et.get("primary", "avg_a")) or _et.get("avg_a") or sb30  # iteration 12: the exposure tracker is the PnL rule; iteration 14: mix14_a when the capture exists
    out["target_metrics"] = {
        "presence_auc": (blk or {}).get("auc_full") or out["presence"]["auc_any_no_own_state"], "presence_baseline": (blk or {}).get("auc_pure_market_baseline") or out["presence"]["pure_market_baseline_auc_block_label"] or out["presence"]["co_occurrence_baseline_auc"],
        "presence_unit": "block seconds" if blk else "all seconds",
        "selection_auc": (out.get("selection") or {}).get("v3_size_classes", {}).get("auc_pooled"),
        "selection_baseline": (out.get("selection") or {}).get("v3_size_classes", {}).get("pure_market_baseline_auc") or (out.get("selection") or {}).get("v3_size_classes", {}).get("co_occurrence_baseline_auc"),
        "selection_recall": ((out.get("selection") or {}).get("v3_size_classes", {}).get("at_preregistered_flag_full_or_partial_and_p_ge_0.30") or {}).get("recall"),
        "selection_lift": ((out.get("selection") or {}).get("v3_size_classes", {}).get("at_preregistered_flag_full_or_partial_and_p_ge_0.30") or {}).get("lift"),
        "side_accuracy": (out.get("side_decision_clock") or {}).get("accuracy_per_order") if (out.get("side_decision_clock") or {}).get("accuracy_per_order") is not None else sd.get("y", {}).get("accuracy_side_model"),
        "side_accuracy_source": "decision clock per taker order (dc_exam14, pre-registration 5)" if (out.get("side_decision_clock") or {}).get("accuracy_per_order") is not None else "block-clock side model per one-sided second",
        "side_accuracy_per_decision": (out.get("side_decision_clock") or {}).get("accuracy_per_decision"),
        "side_accuracy_by_wallet": (out.get("side_decision_clock") or {}).get("by_wallet"),
        "side_accuracy_halves_by_wallet": (out.get("side_decision_clock") or {}).get("halves_by_wallet"),
        "side_accuracy_block_clock": sd.get("y", {}).get("accuracy_side_model"),
        "presence_decision_clock_auc": (out.get("presence_decision_clock") or {}).get("auc_full"),
        "presence_decision_clock_baseline": (out.get("presence_decision_clock") or {}).get("auc_pm_only_baseline"),
        "presence_decision_clock_by_wallet": (out.get("presence_decision_clock") or {}).get("by_wallet"),
        "side_baseline": sd.get("y", {}).get("baseline_market_only_model"),
        "side_accuracy_live_decision": (out.get("side_live_decision") or {}).get("agree_on_voted"),
        "side_accuracy_live_decision_abstain_half": (out.get("side_live_decision") or {}).get("accuracy_all_covered_abstain_half"),
        "side_accuracy_live_decision_full_coverage": ((out.get("side_live_decision") or {}).get("full_coverage") or {}).get("accuracy"),
        "presence_live_decision_auc": (out.get("presence_live_decision") or {}).get("auc_full"),
        "presence_live_decision_baseline": (out.get("presence_live_decision") or {}).get("auc_pm_activity_baseline"),
        "share_one_sided_windows": one_w,
        "price_within_tick": lb.get("within_1tick_ask_match") if lb.get("within_1tick_ask_match") is not None else (lb.get("within_1tick_ask_lag") if lb.get("within_1tick_ask_lag") is not None else ((out["price"].get("calldata_touch") or {}).get("within_1tick_touch") or out["price"].get("T_within_1tick_of_last_ask"))),
        "price_source": "recorded book 50 ms before the recorded match" if lb.get("within_1tick_ask_match") is not None else ("recorded book (block - DECISION_LAG_S)" if lb.get("within_1tick_ask_lag") is not None else ("touch of the same match from calldata (consumed maker orders; trivial touch anchor, not a PIT forecast)" if (out["price"].get("calldata_touch") or {}).get("within_1tick_touch") is not None else "last implied ask from others' prints")),
        "price_tape_anchor_T_within_1tick": out["price"].get("T_within_1tick_of_last_ask"),
        "pnl_corr_pearson": sb.get("per_window_pnl_corr_pearson"), "pnl_corr_spearman": sb.get("per_window_pnl_corr_spearman"),
        "pnl_rule": (f"exposure tracker {_et.get('primary', 'avg_a')}" if sb is not sb30 else "30-share strict replica (iteration 4)"),
        "pnl_corr_pearson_avg_a": (_et.get("avg_a") or {}).get("per_window_pnl_corr_pearson"), "pnl_corr_spearman_avg_a": (_et.get("avg_a") or {}).get("per_window_pnl_corr_spearman"),
        "pnl_corr_by_wallet": sb.get("by_wallet"),
        "pnl_corr_pearson_conv_b": (((res_o.get("exposure_tracker") or {}).get("avg_b")) or {}).get("per_window_pnl_corr_pearson"),
        "pnl_corr_spearman_conv_b": (((res_o.get("exposure_tracker") or {}).get("avg_b")) or {}).get("per_window_pnl_corr_spearman"),
        "pnl_corr_pearson_frozen30": sb30.get("per_window_pnl_corr_pearson"), "pnl_corr_spearman_frozen30": sb30.get("per_window_pnl_corr_spearman"),
        "pnl_corr_proxy_pearson": res_o.get(f"per_window_pnl_corr_{res_o['primary']}_pearson"),
        "coverage_fills": 1.0 if len(fills) else None, "coverage_abs_pnl": 1.0 if len(fills) else None,
        "side_accuracy_live_decision_pit": (out.get("side_live_decision_pit") or {}).get("agree_on_voted"),
        "side_accuracy_live_decision_pit_full_coverage": ((out.get("side_live_decision_pit") or {}).get("full_coverage") or {}).get("accuracy"),
        "price_within_tick_live_pit": (out["price"].get("live_book_pit") or {}).get("within_1tick_ask_match"),
        "presence_live_decision_auc_pit": (((out.get("presence_live_decision") or {}).get("pit_label")) or {}).get("auc_full"),
        "presence_live_decision_baseline_pit": (((out.get("presence_live_decision") or {}).get("pit_label")) or {}).get("auc_pm_activity_baseline"),
    }
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    import json
    print(json.dumps(evaluate(a, b), indent=1, default=str))
