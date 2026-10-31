"""btc5m-bot frozen rule (iteration 3).

Point-in-time behaviour-cloning rule for the three-wallet BTC 5-minute Up/Down bot
(GF 0x0ca4e9d2..., XM 0x3048d653..., DS 0xc53375ff...). Every cell (window, outcome, second s of the window) is
scored with frozen LightGBM models trained on BUILD only (windows 2026-10-09 .. 2026-10-16 00:00 UTC; model files
model_it3*_*.txt next to this script). Inputs, all public and available before second s:
  - Binance BTCUSDT spot 1-s closes of seconds <= s-2 (cells.py),
  - Binance USD-M futures BTCUSDT aggTrades with T < (s-1)*1000 ms (fut_cells.py, new in iteration 3),
  - OKX BTC-USDT-SWAP and Bybit BTCUSDT perpetual trades with T < (s-1)*1000 ms (venue_cells.py, new in iteration 3,
    used when USE_VENUES is True),
  - other traders' data-api taker prints with block ts <= s-1 (cluster prints and prints that traded against a
    cluster maker order removed) (tape_feats.py),
  - listing metadata (window start/end, token ids).
No own-state features in the primary score; nothing fitted on VALIDATE or the holdout.

Outputs per cell: presence score p (any cluster BUY fill in that cell), flag p >= P_THRESH; per second: side = the
dedicated side model's choice (Up if ps >= 0.5); print-level selection score = 1[size in ORDER_SIZES] + p.

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

# ----------------------------------------------------------------------------- frozen constants
WALLETS = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
H = 1792713600  # holdout start; development runs (end_ts <= H) never download an archive that extends past H
USE_VENUES = True   # iteration 3: OKX + Bybit perpetual features in the primary score and the side model
SIX_SERIES = True   # iteration 3: + Binance spot aggTrades, Bybit spot, OKX spot and the six-series composite (requires USE_VENUES)
SPOT_FEATURES = list(cellsmod.FEATS)
TAPE_FEATURES = list(tf.TAPE_FEATS)
FEATURES = SPOT_FEATURES + TAPE_FEATURES + list(EXTRA) + list(FUT_FEATS) + (list(VEN_FEATS) if USE_VENUES else []) + (list(VEN2_FEATS) if USE_VENUES and SIX_SERIES else [])
MARKET_FEATURES = ["rel", "tau"] + TAPE_FEATURES + list(EXTRA)    # co-occurrence baseline: market activity only (no reference feed)
OWN_FEATURES = FEATURES + list(OWN)                               # secondary: + cluster inventory (own state)
DSIDE = ["ask_o", "bid_o", "age_ask", "age_bid", "n1", "n2", "n5", "n30", "vol30", "dm5", "dm10", "dm30", "F_gap_ask", "F_gap_m", "gap_ask", "gap_m"]
SIDE_FEATURES = FEATURES + ["D_" + k for k in DSIDE]             # side model: Up-cell features + Down-cell non-mirror features
_TAG = ("it3s" if SIX_SERIES else "it3v") if USE_VENUES else None
_M = f"model_{_TAG}_all" if USE_VENUES else "model_it3_spot_tape_fut"
MODEL_Y = f"{CODE}/{_M}_y.txt"          # label: any cluster BUY fill on (window, outcome, second)
MODEL_T = f"{CODE}/{_M}_yT.txt"         # label: cluster taker fill
MODEL_M = f"{CODE}/{_M}_yM.txt"         # label: cluster maker fill
MODEL_OWN = f"{CODE}/{f'model_{_TAG}_all_own' if USE_VENUES else 'model_it3_spot_tape_fut_own'}_y.txt"  # + own state (secondary)
MODEL_SIDE = f"{CODE}/{f'model_{_TAG}_side' if USE_VENUES else 'model_it3_side'}.txt"                  # side given a one-sided second
MODEL_MKT = f"{CODE}/model_it2_market_only_y.txt"                  # co-occurrence baseline (market activity only)
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


def cluster_fills(start_ts: int, end_ts: int, windows: pd.DataFrame) -> pd.DataFrame:
    """Every OrderFilled of the cluster's own orders (maker and taker role) in [start_ts, end_ts)."""
    b0, b1 = _find_block(start_ts), _find_block(end_ts)
    pads = [rpc.pad(x) for x in WALLETS]
    rows = []
    for a in range(b0, b1, 3000):
        b = min(a + 2999, b1 - 1)
        for ex in EXCHANGES:
            rows += [_decode(l) for l in rpc.get_logs(ex, a, b, [rpc.TOPIC_V2, None, pads])]
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
    sub = {"fut": "fut", "okx": "venues/okx", "bybit": "venues/bybit", "bnspot": "venues/bnspot", "bybitspot": "venues/bybitspot", "okxspot": "venues/okxspot"}[venue]
    for base in (DEV_CACHE, EVAL_DIR):
        p = f"{base}/{sub}/{day0}.parquet"
        if os.path.exists(p):
            return p
    out_dir = f"{EVAL_DIR}/{sub}"; os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="dl_", dir=EVAL_DIR)
    d = _day_str(day0)
    try:
        if venue in ("fut", "bnspot"):
            url = (FUT_URL if venue == "fut" else BNSPOT_URL).format(d=d)
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


def add_reference_feats(cells: pd.DataFrame, spot_frame: pd.DataFrame, end_ts: int) -> pd.DataFrame:
    """Binance futures (+ OKX, Bybit) PIT features, computed per UTC day of the window start (as in training)."""
    day = (cells.start_ts.to_numpy(np.int64) // 86400) * 86400
    F_all = pd.DataFrame(index=cells.index, columns=[k for k in FEATURES if k in set(FUT_FEATS) | set(VEN_FEATS) | set(VEN2_FEATS)], dtype=np.float32)
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


def evaluate(start_ts: int, end_ts: int) -> dict:
    t0 = time.time()
    win = load_windows(start_ts, end_ts)
    win = win[win.up_payout.notna()].sort_values("start_ts").reset_index(drop=True)
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
    flag = p >= P_THRESH
    out = {"period": [int(start_ts), int(end_ts)], "windows": int(len(win)), "cells": int(len(cells)), "cluster_fills": int(len(fills)),
           "use_venues": USE_VENUES, "six_series": SIX_SERIES, "reference_feed_coverage": {"futures": round(float(np.isfinite(cells.F_pm1000).mean()), 4)}}
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
    }
    # (b) side: seconds where the cluster bought exactly one outcome; rule = dedicated side model (ps >= 0.5 -> Up)
    up, dn = _pairs(cells)
    X = pd.concat([up[FEATURES].reset_index(drop=True), pd.DataFrame({"D_" + k: dn[k].to_numpy() for k in DSIDE})], axis=1)
    ps = _predict(MODEL_SIDE, X, SIDE_FEATURES); del X
    sd = {}
    r3z = np.abs(up.r3.to_numpy()) < 0.01
    for lab in ("y", "yT"):
        one = (up[lab].to_numpy() + dn[lab].to_numpy()) == 1
        truth = up[lab].to_numpy()[one] == 1
        ok1 = (ps[one] >= 0.5) == truth
        okp = (up.p.to_numpy()[one] >= dn.p.to_numpy()[one]) == truth
        ok0 = (up.p_mkt.to_numpy()[one] >= dn.p_mkt.to_numpy()[one]) == truth
        okf = (up.m_last.to_numpy()[one] >= 0.5) == truth
        conf = np.abs(ps[one] - 0.5); q50 = np.quantile(conf, 0.5) if len(conf) else 0
        sd[lab] = {"n_seconds": int(one.sum()), "accuracy_side_model": round(float(ok1.mean()), 4),
                   "accuracy_presence_argmax": round(float(okp.mean()), 4),
                   "baseline_market_only_model": round(float(ok0.mean()), 4), "baseline_favourite": round(float(okf.mean()), 4),
                   "mcnemar_p_vs_market_only": _mcnemar(ok1, ok0), "mcnemar_p_vs_favourite": _mcnemar(ok1, okf),
                   "accuracy_spot_3s_move_zero": round(float(ok1[r3z[one]].mean()), 4), "share_spot_3s_move_zero": round(float(r3z[one].mean()), 4),
                   "accuracy_spot_moving": round(float(ok1[~r3z[one]].mean()), 4),
                   "accuracy_top_half_confidence": round(float(ok1[conf >= q50].mean()), 4)}
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
        tp = tp.join(cells.set_index(["cid", "is_up", "rel"])[["p", "p_mkt"]], on=["cid", "is_up", "rel"])
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
    for nm, wu, wd in [("soft", pu * okU, pdn * okD), ("hard", (pu >= P_THRESH) * okU, (pdn >= P_THRESH) * okD), ("soft_side", vol * ps * okU, vol * (1 - ps) * okD)]:
        g = pd.DataFrame({"cid": up.cid.to_numpy(), "pnl": ORDER_SHARES * (wu * uU + wd * uD), "usd": ORDER_SHARES * (wu * aU + wd * aD)}).groupby("cid").sum()
        both = g.join(wal_w, how="outer").reindex(win.cid).fillna(0.0)
        res_o[f"per_window_pnl_corr_{nm}_pearson"] = round(float(both.pnl.corr(both.wallet)), 4)
        res_o[f"per_window_pnl_corr_{nm}_spearman"] = round(float(both.pnl.corr(both.wallet, method="spearman")), 4)
        res_o[f"rule_return_{nm}"] = round(float(both.pnl.sum() / both.usd.sum()), 4) if both.usd.sum() > 0 else None
    res_o["wallet_return_before_rebates"] = round(float(fw.pnl.sum() / fw.usdc.sum()), 4) if len(fw) else None
    res_o["note"] = "rule PnL is a proxy (buys at the last observed ask at s-1, no queue/fill check), not a strict-fill backtest; primary = soft_side (chosen on VALIDATE in iteration 3: 0.436 vs soft 0.412)"
    out["outcome"] = res_o
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    import json
    print(json.dumps(evaluate(a, b), indent=1, default=str))
