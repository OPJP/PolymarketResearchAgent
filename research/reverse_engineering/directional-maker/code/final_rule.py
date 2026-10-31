"""Frozen rule for the directional-maker cluster (bosona, almach, mo-money). Iteration 8 rule R6 = R5 below on BTC 5m
(unchanged) + BTC 15m in the universe + the fill side per fill on the match clock:
* universe (pre-registered 2026-10-31, iteration 8): BTC 5m and BTC 15m Up/Down windows; metrics per family and pooled
  over the union ('btc15m', 'union_btc5m_15m', 'scope'); a block with BTC 5m off is scored on BTC 15m;
* BTC 15m presence: R3's features on bins [0, 900) s (features15.py) scored by presence15_rule.txt (baseline
  presence15_activity.txt), fitted on BUILD 15m windows 2026-10-09..26 (code8/train15.py);
* side per fill ('side_posture_match_clock'): for each cluster maker BUY fill whose transaction is in the shared
  recorder's trade stream, Up iff the digital fair of Up from the Chainlink report stamped floor((T - CL_DELAY_MS)/1000)
  (Gamma priceToBeat, 1.4 x 300-s Binance 1-s vol) exceeds the Up mid of the shared recorder's latest book record
  before the match ms T; no fitted parameter;
* fixes: R4's match-clock price now maps the compact transaction keys to full hashes (it returned an error before);
  Binance 1-s seconds fall back to the public REST klines for days whose archive is not yet published.

Iteration 6 rule R4 =
iteration-4 rule R3 (unchanged below) + a price rule on the match clock for periods the shared live recorder covers.

R4 addition (iteration 6, panel iter5 information I1; chosen on the pre-registered live split, BUILD = 2026-10-31
12:00-15:00 UTC, VALIDATE = 15:00-18:00 UTC): for each cluster maker BUY fill whose transaction appears in the shared
recorder's trade stream (tools/live.py feed clob_crypto, records 'x' with tx hash and server ms), the predicted limit
price = the last trade of the same market before the fill's match ms whose transaction holds no cluster trade (either
token, mapped to the fill's token) minus 0.01. This is the trivial anchor "last print" minus a tick on the match clock.
Fills without a recorded match fall back to R3's block-clock anchor. evaluate() reports it under "price_match_clock"
(pooled and per wallet, with the trivial anchors and the coverage). The live trades are read with a tolerant gzip-member
reader that honours ALLOW_SEALED (development blocks only unless the examiner's driver sets it).


Iteration 7 rule R5 = R4 + a presence score stacked with the Chainlink settlement stream (code/r5.py, code/cl_source.py):
p_R5 = sigmoid(b0 + b . [logit(p_R3), Chainlink fair - Binance fair, Chainlink edge, 10-s Chainlink change, z, fair]) with
the Chainlink value stamped t - 3 s (live recorders dy_rtds / dx_rtds / dm_rtds, else Polymarket's crypto-price endpoint,
fetched only when <= MAX_CL_REQUESTS requests are needed) and Gamma priceToBeat; fitted on a STUDY sample, adopted on the
pre-registered VALIDATE sample criterion (gain +0.0075, 2-h block-bootstrap 95% [+0.0016, +0.0131]). evaluate() reports
it under 'presence_r5' (bins with Chainlink; R3 fallback elsewhere) next to R3's 'presence'.


R3 = R2 (iteration 2; archived unchanged in final_rule_r2.py) with two changes, both chosen on the iteration-4
VALIDATE (2026-10-27..30, the second half of the released lot):
* the presence models are refitted on the expanded BUILD (2026-10-09..26: old BUILD + old VALIDATE + the lot's first
  half) with the same LightGBM parameters (code4/train6.py, code4/train4.py);
* the operator's clock schedule is an input: UTC hour, weekday and the US-session flag (weekday 12:00-21:00 UTC), the
  boundary at which the cluster's order size switches (iteration-4 calldata finding).
Everything else (tape hygiene, features, side, price, selection models and thresholds) is R2's.

* Tape hygiene: every data-api taker print in a transaction where a cluster wallet traded (maker or taker) is removed
  before any feature is computed.
* Presence: P(cluster gets >= 1 maker BUY fill on side s in the 10-s bin [t, t+10)), t in [0, 300) s
  = presence3_rule.txt on features published by t (features2.build_panel + clock): time, side, clean-tape activity,
  Binance 1-s fair value of the TWAP-60 settlement, z, returns, realized vol, edge = fair - last clean print, window
  path features, previous-window proxy outcome and strike move, UTC hour, weekday, US-session flag. No own-state.
  Baseline: presence3_activity.txt (market activity only, same BUILD). Own-inventory variant: presence3_own.txt.
* Side (bins where it fills exactly one side): the side with the higher predicted presence.
* Price: last clean taker print on s strictly before the fill second, minus 0.01, rounded to 0.01.
* Selection: R2's selection2_all.txt / THETA_SEL (unchanged).
* Per-window rule PnL: sum over bins and sides of P(fill) * (payout_s - rule price).

evaluate(start_ts, end_ts, intervals=None) loads [start_ts, end_ts) through the polyrea adapters (Gamma windows,
data-api taker tapes [start-120, end) and the three wallets' activity, Binance 1-s archive), applies the frozen
models and returns presence / side / price / PnL / selection metrics with the market-activity-only baselines, pooled
and per wallet. With intervals (list of [a, b) pairs) only windows starting in them count. Nothing is fitted here.
local=True (development only) reads cached day files when they exist. R3 reads no live recording; R4 reads the
shared trade stream for its price part only (ALLOW_SEALED is set by the examiner's driver).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from features2 import Spot, build_panel, clean_tape  # noqa: E402
from train2 import SETS  # noqa: E402

ALLOW_SEALED = False             # only the examiner's driver sets True (R4 price reads the shared live trade stream)
MODEL = "rule"                   # presence3_rule.txt: R2 features + clock, refit on BUILD 2026-10-09..26 (iteration 4)
BASELINE = "activity"            # presence3_activity.txt: market-activity-only (co-occurrence) baseline, same BUILD
OWN_MODEL = "own"                # presence3_own.txt: reported separately (own inventory)
CLOCK = ["hour_utc", "dow", "us_session"]
FEATS = {"rule": SETS["all_path_xwin"] + CLOCK, "activity": SETS["activity"],
         "own": SETS["all_path_xwin"] + CLOCK + ["inv_s", "inv_o"]}
FETCH_CL = True                  # R5: fetch missing Chainlink stamps from the endpoint (slow: ~1.5 requests/s)
MAX_CL_REQUESTS = 3000
THETA_SEL = {"all": 0.01698130336758783, "activity": 0.01736697994132774}  # BUILD top-15% score thresholds (sel2.py fit)
PRICE_OFFSET = 0.01
PRE = 120
SEL_NEG_FRAC = 0.10
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
CACHE = ROOT / ".cache/re/directional-maker"


def _windows(start_ts: int, end_ts: int) -> pd.DataFrame:
    from polyrea.analysis.updown import windows_from_markets
    from polyrea.workflows.updown_study import fetch_windows, window_slugs
    ws = [x for x in windows_from_markets(fetch_windows(window_slugs("btc", "5m", start_ts, end_ts)))
          if start_ts <= x.start_ts and x.end_ts <= end_ts]
    return pd.DataFrame([{"cid": x.condition_id, "start_ts": x.start_ts, "end_ts": x.end_ts, "up_token": x.up_token,
                          "down_token": x.down_token, "up_payout": x.up_payout} for x in ws]).sort_values("start_ts").reset_index(drop=True)


def _ptb(w: pd.DataFrame) -> dict:
    """Gamma priceToBeat (the strike, fixed at the window start; eventMetadata) by window start."""
    from polyrea.workflows.updown_study import fetch_windows
    out = {}
    raw = fetch_windows([f"btc-updown-5m-{int(s)}" for s in w["start_ts"]])
    for m in raw.values():
        try:
            st = int(str(m.get("slug")).rsplit("-", 1)[1])
        except (IndexError, ValueError):
            continue
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                out[st] = float(v)
    return out


def _txint(x: pd.Series) -> pd.Series:
    """Compact transaction key (first 60 bits of the hash) to keep a week of tapes under ~0.5 GB."""
    def one(h):
        try:
            return int(h, 16)
        except (TypeError, ValueError):
            return 0
    return x.astype(str).str.slice(2, 17).map(one).astype(np.int64)


def _compact(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    t["tx"] = _txint(t["tx"])
    for c in ("cid", "asset", "wallet", "side"):
        t[c] = t[c].astype(str).astype("category")
    t["price"] = t["price"].astype(np.float32)
    t["size"] = t["size"].astype(np.float32)
    return t


def _tapes(w: pd.DataFrame, pm, end_ts: int, local: bool) -> pd.DataFrame:
    from polyrea.adapters.http import HttpError
    from polyrea.analysis.updown import snap_price
    out, have = [], set()
    if local:
        for d in sorted(set(w["start_ts"] // 86400 * 86400)):
            f = CACHE / f"taker5m_day_{d}.parquet"
            if f.exists():
                t = pd.read_parquet(f)
                t = t[t["cid"].isin(set(w["cid"])) & (t["ts"] < end_ts)]
                out.append(_compact(t))
                have |= set(t["cid"])
    rows = []
    for win in w.itertuples(index=False):
        if win.cid in have:
            continue
        try:
            rs, _, _ = pm.market_trades(win.cid, start=int(win.start_ts) - PRE, end=min(int(win.end_ts), end_ts - 1), taker_only=True)
        except HttpError:
            continue
        for r in rs:
            if int(r["timestamp"]) < end_ts:
                rows.append((win.cid, int(r["timestamp"]), r.get("side"), str(r.get("asset")), snap_price(float(r.get("price", 0))),
                             float(r.get("size", 0)), (r.get("proxyWallet") or "").lower(), r.get("transactionHash")))
    out.append(_compact(pd.DataFrame(rows, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])))
    tk = pd.concat(out, ignore_index=True)
    for c in ("cid", "asset", "wallet", "side"):
        tk[c] = tk[c].astype(str).astype("category")
    return tk


def _cluster_trades(start_ts: int, end_ts: int, pm, local: bool) -> pd.DataFrame:
    rows = []
    for addr, name in CLUSTER.items():
        f = CACHE / f"activity_{name}.parquet"
        if local and f.exists():
            a = pd.read_parquet(f)
            a = a[(a["type"] == "TRADE") & (a["timestamp"] >= start_ts) & (a["timestamp"] < end_ts)]
            recs = a.rename(columns={"transactionHash": "tx", "asset": "token_id", "timestamp": "ts", "size": "shares",
                                     "conditionId": "cid"}).to_dict("records")
        else:
            act, _, _ = pm.activity(addr, start=start_ts, end=end_ts - 1)
            recs = [{"tx": r.get("transactionHash"), "token_id": r.get("asset"), "ts": r.get("timestamp"), "side": r.get("side"),
                     "price": r.get("price"), "shares": r.get("size"), "cid": r.get("conditionId")}
                    for r in act if r.get("type") == "TRADE" and start_ts <= int(r["timestamp"]) < end_ts]
        for r in recs:
            rows.append({"wallet": addr, "tx": r["tx"], "token_id": str(r["token_id"]), "ts": int(r["ts"]), "side": r["side"],
                         "price": float(r["price"]), "shares": float(r["shares"]), "cid": r["cid"]})
    ct = pd.DataFrame(rows, columns=["wallet", "tx", "token_id", "ts", "side", "price", "shares", "cid"])
    ct["tx"] = _txint(ct["tx"])
    return ct


def _cluster_tx_hashes(start_ts: int, end_ts: int, pm, local: bool) -> dict:
    """compact tx key (_txint) -> full transaction hash, from the three wallets' activity."""
    out = {}
    for addr, name in CLUSTER.items():
        f = CACHE / f"activity_{name}.parquet"
        if local and f.exists():
            a = pd.read_parquet(f, columns=["transactionHash", "timestamp", "type"])
            a = a[(a["type"] == "TRADE") & (a["timestamp"] >= start_ts) & (a["timestamp"] < end_ts)]
            hs = a["transactionHash"].astype(str)
        else:
            act, _, _ = pm.activity(addr, start=start_ts, end=end_ts - 1)
            hs = pd.Series([r.get("transactionHash") for r in act if r.get("type") == "TRADE"], dtype=str)
        for k, h in zip(_txint(hs), hs):
            out[int(k)] = h
    return out


def _binance_rest_seconds(start_ts: int, end_ts: int) -> list:
    """(second, close) of Binance BTCUSDT spot 1-s klines from the public REST API (api.binance.com/api/v3/klines,
    interval 1s, 1,000 per request), for periods whose daily archive is not published yet."""
    import time as _time
    import httpx
    out, t = [], int(start_ts)
    with httpx.Client(timeout=20) as c:
        while t < end_ts:
            for attempt in range(5):
                try:
                    r = c.get("https://api.binance.com/api/v3/klines", params={"symbol": "BTCUSDT", "interval": "1s",
                                                                               "startTime": t * 1000, "endTime": min(t + 1000, end_ts) * 1000 - 1, "limit": 1000})
                    if r.status_code == 429:
                        _time.sleep(2 + 2 * attempt)
                        continue
                    r.raise_for_status()
                    k = r.json()
                    break
                except Exception:  # noqa: BLE001
                    _time.sleep(1 + attempt)
                    k = []
            out += [(float(int(x[0]) // 1000), float(x[4])) for x in k]
            t += 1000
            _time.sleep(0.1)
    return out


def _auc(y, s):
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y)
    ok = np.isfinite(s)
    return float(roc_auc_score(y[ok], np.asarray(s)[ok])) if 0 < y[ok].sum() < ok.sum() else float("nan")


def _add_clock(panel: pd.DataFrame) -> pd.DataFrame:
    t = pd.to_datetime(panel["start_ts"], unit="s")
    panel["hour_utc"] = (t.dt.hour + t.dt.minute / 60).astype(np.float32).to_numpy()
    panel["dow"] = t.dt.day_of_week.astype(np.int8).to_numpy()
    panel["us_session"] = ((panel["dow"] < 5) & (panel["hour_utc"] >= 12) & (panel["hour_utc"] < 21)).astype(np.int8)
    return panel


def _wallet_labels(panel: pd.DataFrame, w: pd.DataFrame, mk: pd.DataFrame, wallet: str) -> np.ndarray:
    """y for one wallet: >= 1 maker BUY fill of that wallet on the bin's side in [t, t+10)."""
    side_of = {**{t: (c, 1, s) for t, c, s in zip(w["up_token"], w["cid"], w["start_ts"])},
               **{t: (c, 0, s) for t, c, s in zip(w["down_token"], w["cid"], w["start_ts"])}}
    m = mk[mk["wallet"] == wallet]
    keys = set()
    for tok, ts in zip(m["token_id"], m["ts"]):
        v = side_of.get(tok)
        if v is None:
            continue
        rel = int((ts - v[2]) // 10 * 10)
        if 0 <= rel < 300:
            keys.add((v[0], v[1], rel))
    return np.array([(c, sd, r) in keys for c, sd, r in zip(panel["cid"], panel["side_up"], panel["rel"])], dtype=np.int8)


LIVE_FEED = "clob_crypto"        # shared recorder (tools/live.py): 'x' = every last trade with tx hash and server ms
LIVE_PAD_S = 120


def _iter_live_x(start_ts: int, end_ts: int):
    """Tolerant reader of the shared recorder's trade records ('x'), development blocks only unless the examiner's
    driver sets ALLOW_SEALED = True. Each gzip member is decoded on its own (a member cut by a recorder restart keeps
    its complete lines; tools/live.iter_live stops there with zlib.error). Only lines holding a trade are parsed."""
    import calendar
    import json
    import time as _time
    import zlib
    sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
    import sealed as _sealed
    sys.path.insert(0, str(HERE.parent / "code5"))
    import rawread
    base = ROOT / ".cache" / "live"
    parts = ["dev", "sealed"] if ALLOW_SEALED else ["dev"]
    files = sorted((p for part in parts for p in (base / part / LIVE_FEED).glob("*.jsonl.gz")), key=lambda p: p.name)
    for p in files:
        hour = calendar.timegm(_time.strptime(p.name[:11], "%Y%m%dT%H"))
        if hour + 3600 <= start_ts or hour >= end_ts:
            continue
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        for chunk in rawread._members(raw):
            for line in chunk.split(b"\n"):
                if b'"k":"x"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                t = r.get("t", 0) / 1000.0
                if start_ts <= t < end_ts and (ALLOW_SEALED or not _sealed.future_block_sealed(t)):
                    yield r


def price_match_clock(mk: pd.DataFrame, w: pd.DataFrame, start_ts: int, end_ts: int, block_pred: pd.DataFrame) -> dict:
    """R4 price rule on the match clock (iteration 6, panel I1): for each cluster maker BUY fill whose transaction is in
    the shared recorder's trade stream, the server match ms is the first trade record of its tx hash; the predicted
    limit price = the last trade of the same market (either token, mapped to the fill's token) before the match whose
    transaction holds no cluster trade, minus PRICE_OFFSET. This IS the trivial anchor 'last print' (minus a tick) on
    the match clock; the trivial anchors are reported next to it. Fills without a recorded match fall back to R3's
    block-clock anchor (combined metric). Point-in-time with respect to the match (strictly earlier server ms)."""
    up2cid = dict(zip(w["up_token"], w["cid"]))
    dn2cid = dict(zip(w["down_token"], w["cid"]))
    rows = []
    for r in _iter_live_x(start_ts - LIVE_PAD_S, end_ts + LIVE_PAD_S):
        a = r.get("a")
        if a in up2cid:
            rows.append((r.get("s", 0), up2cid[a], True, float(r.get("p") or 0), (r.get("h") or "").lower()))
        elif a in dn2cid:
            rows.append((r.get("s", 0), dn2cid[a], False, float(r.get("p") or 0), (r.get("h") or "").lower()))
    out = {"x_records": len(rows), "fills": int(len(mk))}
    if not rows or not len(mk):
        out["note"] = "no live trade records for this period (block-clock price only)"
        return out
    X = pd.DataFrame(rows, columns=["s", "cid", "isup", "p", "h"]).sort_values("s", kind="stable")
    X["p_up"] = np.where(X["isup"], X["p"], 1 - X["p"])
    ctx = set(mk["tx"].str.lower())
    match_s = X.groupby("h")["s"].min()
    Xc = X[~X["h"].isin(ctx)]
    byc = {c: (g["s"].to_numpy(), g["p_up"].to_numpy()) for c, g in Xc.groupby("cid")}
    upset = set(w["up_token"])
    tok2cid = {**up2cid, **dn2cid}
    bp = dict(zip(zip(block_pred["tx"], block_pred["token_id"]), block_pred["pred_block"])) if len(block_pred) else {}
    recs = []
    for r in mk.itertuples(index=False):
        tx = str(r.tx).lower()
        cid = tok2cid.get(r.token_id)
        isup = r.token_id in upset
        pb = bp.get((r.tx, r.token_id))
        pm = np.nan
        if cid is not None and tx in match_s.index and cid in byc:
            ss, pp = byc[cid]
            i = np.searchsorted(ss, match_s[tx], side="left") - 1
            if i >= 0:
                lp = pp[i] if isup else 1 - pp[i]
                pm = round(lp - PRICE_OFFSET, 2)
        recs.append((r.wallet, float(r.price), pm, np.nan if pb is None else pb, tx in match_s.index))
    D = pd.DataFrame(recs, columns=["wallet", "price", "pm", "pb", "in_x"])
    D["pc"] = D["pm"].where(D["pm"].notna(), D["pb"])

    def acc(col, d):
        m = d[col].notna()
        e = np.abs(d.loc[m, col] - d.loc[m, "price"])
        return (float(np.mean(e <= 0.0105)) if m.any() else float("nan"), float(np.mean(e < 0.0005)) if m.any() else float("nan"), int(m.sum()))
    a1, a2, a3 = acc("pm", D)
    b1, b2, b3 = acc("pc", D)
    c1, _, c3 = acc("pb", D[D["pm"].notna()])
    D["last"] = D["pm"] + PRICE_OFFSET
    l1, _, _ = acc("last", D)
    out.update({"coverage_in_x": float(D["in_x"].mean()), "n_match_clock": a3, "within_0.01": a1, "exact": a2,
                "combined_within_0.01": b1, "combined_exact": b2, "combined_n": b3,
                "block_clock_same_fills_within_0.01": c1, "anchor_last_print_within_0.01": l1, "per_wallet": {}})
    for addr, name in CLUSTER.items():
        d = D[D["wallet"] == addr]
        if len(d):
            x1, x2, x3 = acc("pm", d)
            y1, _, _ = acc("pc", d)
            out["per_wallet"][name] = {"within_0.01": x1, "exact": x2, "n": x3, "combined_within_0.01": y1}
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Iteration 8 (R6 scope, panel iter7 A1 / M3, catalog X69): the BTC 15m family with R3's model class. Same features
# (code/features15.py = features2 with bins [0, 900) s and the previous 15-min window), same LightGBM parameters and the
# clock, fitted on BUILD 15m windows 2026-10-09..26 (code8/train15.py; presence15_rule.txt / presence15_activity.txt).
# Price: last clean print on s before the fill second - 0.01 (block clock; R4's match clock is reported for 5m only).
WIN15 = 900


def _windows15(start_ts: int, end_ts: int) -> pd.DataFrame:
    from polyrea.analysis.updown import windows_from_markets
    from polyrea.workflows.updown_study import fetch_windows, window_slugs
    ws = [x for x in windows_from_markets(fetch_windows(window_slugs("btc", "15m", start_ts, end_ts)))
          if start_ts <= x.start_ts and x.end_ts <= end_ts]
    if not ws:
        return pd.DataFrame(columns=["cid", "start_ts", "end_ts", "up_token", "down_token", "up_payout"])
    return pd.DataFrame([{"cid": x.condition_id, "start_ts": x.start_ts, "end_ts": x.end_ts, "up_token": x.up_token,
                          "down_token": x.down_token, "up_payout": x.up_payout} for x in ws]).sort_values("start_ts").reset_index(drop=True)


def _tapes15(w: pd.DataFrame, pm, end_ts: int, local: bool) -> pd.DataFrame:
    from polyrea.adapters.http import HttpError
    from polyrea.analysis.updown import snap_price
    out, have = [], set()
    if local:
        for d in sorted(set(w["start_ts"] // 86400 * 86400)):
            f = CACHE / "t15" / f"taker15m_day_{d}.parquet"
            if f.exists():
                t = pd.read_parquet(f)
                t = t[t["cid"].isin(set(w["cid"])) & (t["ts"] < end_ts)]
                out.append(_compact(t))
                have |= set(t["cid"])
    rows = []
    for win in w.itertuples(index=False):
        if win.cid in have:
            continue
        try:
            rs, _, _ = pm.market_trades(win.cid, start=int(win.start_ts) - PRE, end=min(int(win.end_ts), end_ts - 1), taker_only=True)
        except HttpError:
            continue
        for r in rs:
            if int(r["timestamp"]) < end_ts:
                rows.append((win.cid, int(r["timestamp"]), r.get("side"), str(r.get("asset")), snap_price(float(r.get("price", 0))),
                             float(r.get("size", 0)), (r.get("proxyWallet") or "").lower(), r.get("transactionHash")))
    out.append(_compact(pd.DataFrame(rows, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])))
    tk = pd.concat(out, ignore_index=True)
    for c in ("cid", "asset", "wallet", "side"):
        tk[c] = tk[c].astype(str).astype("category")
    return tk


def _wallet_labels_win(panel: pd.DataFrame, w: pd.DataFrame, mk: pd.DataFrame, wallet: str, win_len: int) -> np.ndarray:
    side_of = {**{t: (c, 1, s) for t, c, s in zip(w["up_token"], w["cid"], w["start_ts"])},
               **{t: (c, 0, s) for t, c, s in zip(w["down_token"], w["cid"], w["start_ts"])}}
    m = mk[mk["wallet"] == wallet]
    keys = set()
    for tok, ts in zip(m["token_id"], m["ts"]):
        v = side_of.get(tok)
        if v is None:
            continue
        rel = int((ts - v[2]) // 10 * 10)
        if 0 <= rel < win_len:
            keys.add((v[0], v[1], rel))
    return np.array([(c, sd, r) in keys for c, sd, r in zip(panel["cid"], panel["side_up"], panel["rel"])], dtype=np.int8)


def _evaluate_btc15m(start_ts, end_ts, intervals, pm, sp, ct, local):
    import lightgbm as lgb
    import features15
    from train2 import side_metrics
    w = _windows15(start_ts, end_ts)
    if intervals and len(w):
        keep = np.zeros(len(w), dtype=bool)
        for a_, b_ in intervals:
            keep |= (w["start_ts"].to_numpy() >= a_) & (w["start_ts"].to_numpy() < b_)
        w = w[keep].reset_index(drop=True)
    if not len(w):
        return {"windows": 0}, None, w, None
    w["up_token"], w["down_token"] = w["up_token"].astype(str), w["down_token"].astype(str)
    tk = _tapes15(w, pm, end_ts, local)
    toks = set(w["up_token"]) | set(w["down_token"])
    buys = ct[(ct["side"] == "BUY") & ct["token_id"].isin(toks)].copy()
    own_rows = tk[tk["wallet"].isin(set(CLUSTER))]
    taker_pairs = set(zip(own_rows["tx"], own_rows["wallet"].astype(str)))
    buys["role"] = ["taker" if (x, y) in taker_pairs else "maker" for x, y in zip(buys["tx"], buys["wallet"])]
    mk = buys[buys["role"] == "maker"]
    clean = features15.clean_tape(tk, set(ct["tx"]), set(CLUSTER))
    panel = features15.build_panel(w, sp, clean, mk)
    panel = _add_clock(panel)
    for nm in (MODEL, BASELINE):
        m = lgb.Booster(model_file=str(HERE / f"presence15_{nm}.txt"))
        panel["p_" + nm] = m.predict(panel[FEATS[nm]])
    act = panel.groupby("cid")["y"].transform("max") > 0
    out = {"windows": int(panel["cid"].nunique()), "bins": int(len(panel)), "cluster_maker_fills": int(len(mk)),
           "cluster_taker_fills": int((buys["role"] == "taker").sum()),
           "presence": {"auc": _auc(panel["y"], panel["p_" + MODEL]), "auc_activity_baseline": _auc(panel["y"], panel["p_" + BASELINE]),
                        "auc_within_active_windows": _auc(panel.loc[act, "y"], panel.loc[act, "p_" + MODEL]),
                        "pos_rate": float(panel["y"].mean()), "active_window_share": float(panel.groupby("cid")["y"].max().mean())}}
    out["presence"]["gain_over_baseline"] = out["presence"]["auc"] - out["presence"]["auc_activity_baseline"]
    try:
        out["side"] = side_metrics(panel, "p_" + MODEL)
        out["side_activity_baseline"] = side_metrics(panel, "p_" + BASELINE)["acc"]
    except Exception as ex:
        out["side"] = {"error": repr(ex)[:200]}
    upset = set(w["up_token"])
    tok2cid = {**dict(zip(w["up_token"], w["cid"])), **dict(zip(w["down_token"], w["cid"]))}
    c2 = clean.merge(w[["cid", "up_token"]], on="cid")
    c2["up_px"] = np.where(c2["asset"].astype(str) == c2["up_token"], c2["price"], 1 - c2["price"])
    by = {c: (g["ts"].to_numpy(), g["up_px"].to_numpy()) for c, g in c2.sort_values("ts", kind="stable").groupby("cid")}
    pred, actual, pw_wal = [], [], []
    for r in mk.itertuples(index=False):
        cid = tok2cid.get(r.token_id)
        if cid not in by:
            continue
        ts_, px_ = by[cid]
        i = np.searchsorted(ts_, r.ts, side="left") - 1
        if i < 0:
            continue
        ls = px_[i] if r.token_id in upset else 1 - px_[i]
        pred.append(round(ls - PRICE_OFFSET, 2))
        actual.append(r.price)
        pw_wal.append(r.wallet)
    e = np.abs(np.asarray(actual) - np.asarray(pred))
    out["price"] = {"n_fills": int(len(e)), "within_0.01": float(np.mean(e <= 0.0105)) if len(e) else float("nan")}
    pay = dict(zip(w["cid"], w["up_payout"]))
    mk2 = mk.assign(c=[tok2cid.get(t) for t in mk["token_id"]], up=mk["token_id"].isin(upset))
    mk2["won"] = [(pay.get(c) if u else 1 - pay.get(c)) if pay.get(c) is not None else np.nan for c, u in zip(mk2["c"], mk2["up"])]
    wal = ((mk2["won"] - mk2["price"]) * mk2["shares"]).groupby(mk2["c"]).sum()
    pr = panel.dropna(subset=["won_s"]).copy()
    pr["rule_pnl"] = pr["p_" + MODEL] * (pr["won_s"] - (pr["last_s"].fillna(0.5) - PRICE_OFFSET).round(2))
    j = pd.concat([wal.rename("wallet"), pr.groupby("cid")["rule_pnl"].sum().rename("rule")], axis=1).dropna()
    out["pnl"] = {"windows": int(len(j)), "pearson": float(j.corr().iloc[0, 1]) if len(j) > 2 else float("nan"),
                  "spearman": float(j.corr(method="spearman").iloc[0, 1]) if len(j) > 2 else float("nan")}
    pw = {}
    pw_wal = np.asarray(pw_wal)
    for addr, name in CLUSTER.items():
        yw = _wallet_labels_win(panel, w, mk, addr, WIN15)
        k = pw_wal == addr
        pw[name] = {"fills": int((mk["wallet"] == addr).sum()), "presence_auc": _auc(yw, panel["p_" + MODEL].to_numpy()),
                    "presence_auc_activity_baseline": _auc(yw, panel["p_" + BASELINE].to_numpy()),
                    "price_within_0.01": float(np.mean(e[k] <= 0.0105)) if k.any() else float("nan")}
    out["per_wallet"] = pw
    keep_cols = ["cid", "rel", "side_up", "y", "last_s", "fair_s", "start_ts", "p_" + MODEL, "p_" + BASELINE]
    return out, panel[keep_cols].copy(), w, mk



# ---------------------------------------------------------------------------------------------------------------------
# Iteration 8 (R6 side, panel iter7 mechanics critique 4): the fill side scored per fill with the decoded quote-side rule.
# For each cluster maker BUY fill (BTC 5m and 15m) whose transaction is in the shared recorder's trade stream, at its
# server match ms T: e_up = digital fair of Up from the Chainlink report stamped floor((T - CL_DELAY_MS) / 1000) (Gamma
# priceToBeat strike, sigma = 1.4 x the 300-s Binance 1-s realised vol, tau = end - T) minus the Up mid of the latest
# shared-recorder 'q' book record before T. Predicted side = Up iff e_up > 0. No fitted parameter (CL_DELAY_MS = the p90
# relay publish delay measured on 10-31). Market-only baselines: the Binance-spot fair edge sign (pre-window spot TWAP
# strike), the cheaper side, always-Up.
CL_DELAY_MS = 1432


def _ptb_any(w: pd.DataFrame) -> dict:
    """Gamma priceToBeat by (family tag, window start) for 5m and 15m windows."""
    from polyrea.workflows.updown_study import fetch_windows
    out = {}
    slugs = [f"btc-updown-{('15m' if int(e) - int(s) == 900 else '5m')}-{int(s)}" for s, e in zip(w["start_ts"], w["end_ts"])]
    raw = fetch_windows(slugs)
    for m in raw.values():
        try:
            st = int(str(m.get("slug")).rsplit("-", 1)[1])
            tag = str(m.get("slug")).split("-")[2]
        except (IndexError, ValueError):
            continue
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                out[(tag, st)] = float(v)
    return out


def _iter_live_xq(start_ts: int, end_ts: int, toks: set):
    """Trade ('x') and top-10 book ('q') records of the given tokens from the shared recorder (tolerant reader, same
    sealed rule as _iter_live_x)."""
    import calendar
    import json
    import time as _time
    sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
    import sealed as _sealed
    sys.path.insert(0, str(HERE.parent / "code5"))
    import rawread
    base = ROOT / ".cache" / "live"
    parts = ["dev", "sealed"] if ALLOW_SEALED else ["dev"]
    files = sorted((p for part in parts for p in (base / part / LIVE_FEED).glob("*.jsonl.gz")), key=lambda p: p.name)
    btoks = [t.encode() for t in toks]
    for p in files:
        hour = calendar.timegm(_time.strptime(p.name[:11], "%Y%m%dT%H"))
        if hour + 3600 <= start_ts or hour >= end_ts:
            continue
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        for chunk in rawread._members(raw):
            for line in chunk.split(b"\n"):
                isx = b'"k":"x"' in line
                if not (isx or b'"k":"q"' in line):
                    continue
                if not isx and not any(bt in line for bt in btoks):
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                t = r.get("t", 0) / 1000.0
                if start_ts <= t < end_ts and (ALLOW_SEALED or not _sealed.future_block_sealed(t)):
                    yield r


def side_posture_match_clock(mk: pd.DataFrame, w: pd.DataFrame, start_ts: int, end_ts: int, sp) -> dict:
    from scipy.stats import norm
    import cl_source
    from features2 import fair_up as _fair_up
    if mk is None or not len(mk):
        return {"n": 0}
    w = w.copy()
    w["up_token"], w["down_token"] = w["up_token"].astype(str), w["down_token"].astype(str)
    ups = set(w["up_token"])
    tok_info = {**{t: (s, e, 1) for t, s, e in zip(w["up_token"], w["start_ts"], w["end_ts"])},
                **{t: (s, e, 0) for t, s, e in zip(w["down_token"], w["start_ts"], w["end_ts"])}}
    up_of = {**dict(zip(w["up_token"], w["up_token"])), **dict(zip(w["down_token"], w["up_token"]))}
    match_ms, books = {}, {}
    for r in _iter_live_xq(start_ts - LIVE_PAD_S, end_ts + LIVE_PAD_S, ups):
        if r.get("k") == "x":
            h = str(r.get("h", "")).lower()
            if h and h not in match_ms:
                match_ms[h] = int(r.get("s") or r.get("t"))
        elif r.get("k") == "q" and str(r.get("a")) in ups:
            b, o = r.get("b") or [], r.get("o") or []
            if b and o:
                bb = max(float(x[0]) for x in b)
                ba = min(float(x[0]) for x in o)
                books.setdefault(str(r.get("a")), []).append((int(r.get("s") or r.get("t")), (bb + ba) / 2))
    bk = {t: (np.array([x[0] for x in v]), np.array([x[1] for x in v])) for t, v in books.items()}
    for t in bk:
        o = np.argsort(bk[t][0], kind="stable")
        bk[t] = (bk[t][0][o], bk[t][1][o])
    txh = mk["txh"] if "txh" in mk.columns else None
    if txh is None:
        return {"n": 0, "note": "fills carry no tx hash"}
    rows = []
    for r, h in zip(mk.itertuples(index=False), txh):
        T = match_ms.get(str(h).lower())
        inf = tok_info.get(str(r.token_id))
        if T is None or inf is None:
            continue
        u = up_of[str(r.token_id)]
        if u not in bk:
            continue
        ts_, mid_ = bk[u]
        i = np.searchsorted(ts_, T, side="left") - 1
        if i < 0 or T - ts_[i] > 10000:
            continue
        rows.append((str(r.wallet), int(inf[0]), int(inf[1]), int(inf[2]), int(T), float(mid_[i])))
    if not rows:
        return {"n": 0, "matched_trades": len(match_ms), "books_tokens": len(bk)}
    D = pd.DataFrame(rows, columns=["wallet", "st", "en", "is_up", "T", "mid_up"])
    ptb = _ptb_any(w)
    D["K"] = [ptb.get(("15m" if e - s == 900 else "5m", s)) for s, e in zip(D["st"], D["en"])]
    D = D.dropna(subset=["K"])
    stamps = sorted(set(((D["T"] - CL_DELAY_MS) // 1000).astype(np.int64)))
    clv = cl_source.cl_values(stamps, allow_sealed=ALLOW_SEALED, fetch=FETCH_CL, max_requests=MAX_CL_REQUESTS)
    D["cl"] = ((D["T"] - CL_DELAY_MS) // 1000).map(clv)
    tsec = (D["T"] // 1000).to_numpy()
    sig = np.array([float(sp.sigma(np.array([t]), look=300)[0]) for t in tsec]) * 1.4
    tau = np.maximum(D["en"].to_numpy() - D["T"].to_numpy() / 1000.0, 1.0)
    D["fair_cl"] = norm.cdf(np.log(D["cl"].to_numpy(dtype=float) / D["K"].to_numpy(dtype=float)) / (sig * np.sqrt(tau)))
    fb, _ = _fair_up(sp, D["st"].to_numpy(), D["en"].to_numpy(), tsec)
    D["fair_bn"] = fb
    D = D.dropna(subset=["fair_cl"])
    y = D["is_up"].to_numpy() == 1

    def acc(m):
        return float(np.mean((m) == y)) if len(y) else float("nan")
    out = {"n": int(len(D)), "matched_trades": len(match_ms), "accuracy_chainlink_edge_sign": acc(D["fair_cl"].to_numpy() > D["mid_up"].to_numpy()),
           "baseline_binance_spot_edge_sign": acc(D["fair_bn"].to_numpy() > D["mid_up"].to_numpy()),
           "baseline_cheaper_side": acc(D["mid_up"].to_numpy() < 0.5), "baseline_always_up": float(np.mean(y)),
           "cl_coverage": float(D["cl"].notna().mean())}
    fam = np.where(D["en"] - D["st"] == 900, "15m", "5m")
    out["per_family"] = {f: {"n": int((fam == f).sum()), "accuracy": float(np.mean(((D["fair_cl"] > D["mid_up"]).to_numpy() == y)[fam == f]))}
                         for f in ("5m", "15m") if (fam == f).any()}
    pwr = {}
    for addr, name in CLUSTER.items():
        k = (D["wallet"] == addr).to_numpy()
        if k.any():
            pwr[name] = {"n": int(k.sum()), "accuracy": float(np.mean(((D["fair_cl"] > D["mid_up"]).to_numpy() == y)[k]))}
    out["per_wallet"] = pwr
    return out



def evaluate(start_ts: int, end_ts: int, intervals=None, local: bool = False, n_perm: int = 99,
             cache_only: bool = False) -> dict:
    import lightgbm as lgb
    from scipy import stats
    if cache_only:
        os.environ["POLYREA_OFFLINE"] = "1"
    from polyrea.adapters.polymarket import PolymarketData
    from polyrea.adapters.spot import binance_seconds
    import sel2
    from train2 import side_metrics
    pm = PolymarketData()
    w = _windows(start_ts, end_ts)
    if intervals:
        keep = np.zeros(len(w), dtype=bool)
        for a_, b_ in intervals:
            keep |= (w["start_ts"].to_numpy() >= a_) & (w["start_ts"].to_numpy() < b_)
        w = w[keep].reset_index(drop=True)
    tk = _tapes(w, pm, end_ts, local)
    spd = None
    if local and (CACHE / "spot_btc_1s.parquet").exists():
        spd = pd.read_parquet(CACHE / "spot_btc_1s.parquet")
        spd = spd[(spd["sec"] >= start_ts - 7200) & (spd["sec"] < end_ts)]
        sec, px = spd["sec"].to_numpy(), spd["px"].to_numpy()
    if spd is None or len(spd) == 0:
        rows, _ = binance_seconds("btc", start_ts - 7200, end_ts)
        have = {int(r[0]) for r in rows}
        # iteration 8: the daily archive is published the next day; fill the missing seconds from Binance's public
        # REST 1-s klines (same series: BTCUSDT spot 1-s close)
        if len(have) < 0.9 * (end_ts - start_ts + 7200):
            rows = list(rows) + [r for r in _binance_rest_seconds(start_ts - 7200, end_ts) if int(r[0]) not in have]
            rows.sort()
        a = np.asarray(rows, dtype=float).reshape(-1, 2)
        sec, px = a[:, 0].astype(np.int64), a[:, 1]
    sp = Spot(sec, px)
    ct = _cluster_trades(start_ts, end_ts, pm, local)
    toks = set(w["up_token"]) | set(w["down_token"])
    buys = ct[(ct["side"] == "BUY") & ct["token_id"].isin(toks)].copy()
    own_rows = tk[tk["wallet"].isin(set(CLUSTER))]
    taker_pairs = set(zip(own_rows["tx"], own_rows["wallet"].astype(str)))
    buys["role"] = ["taker" if (x, y) in taker_pairs else "maker" for x, y in zip(buys["tx"], buys["wallet"])]
    mk = buys[buys["role"] == "maker"]
    ctx, cw = set(ct["tx"]), set(CLUSTER)
    clean = clean_tape(tk, ctx, cw)
    panel = build_panel(w, sp, clean, mk)
    panel["inv_net"] = panel["inv_s"] - panel["inv_o"]
    res = {"period": [start_ts, end_ts], "windows": int(panel["cid"].nunique()), "bins": int(len(panel)),
           "cluster_maker_fills": int(len(mk)), "cluster_taker_fills": int((buys["role"] == "taker").sum()),
           "tape_rows": int(len(tk)), "tape_rows_removed_cluster_tx": int(len(tk) - len(clean))}
    panel = _add_clock(panel)
    for nm in (MODEL, BASELINE, OWN_MODEL):
        m = lgb.Booster(model_file=str(HERE / f"presence3_{nm}.txt"))
        panel["p_" + nm] = m.predict(panel[FEATS[nm]])
    # R5 (iteration 7): R3 stacked with the Chainlink settlement stream where it is available
    try:
        import cl_source
        import r5
        ptb = _ptb(w)
        cl = cl_source.cl_values(r5.stamps_needed(panel), allow_sealed=ALLOW_SEALED, fetch=FETCH_CL, max_requests=MAX_CL_REQUESTS)
        panel = r5.add_cl(panel, cl, ptb)
        okb = panel["cl_ok"].to_numpy()
        panel["p_r5"] = np.where(okb, r5.score(panel, panel["p_" + MODEL].to_numpy()), panel["p_" + MODEL].to_numpy())
        okw = panel.groupby("cid")["cl_ok"].transform("all").to_numpy()
        sub = panel[okw]
        res["presence_r5"] = {"cl_coverage_bins": float(okb.mean()), "windows_with_cl": int(sub["cid"].nunique()),
                              "auc_r5_with_r3_fallback": _auc(panel["y"], panel["p_r5"]),
                              "auc_r5_on_cl_windows": _auc(sub["y"], sub["p_r5"]), "auc_r3_on_cl_windows": _auc(sub["y"], sub["p_" + MODEL]),
                              "auc_activity_on_cl_windows": _auc(sub["y"], sub["p_" + BASELINE])}
        if len(sub) and sub["y"].sum():
            res["presence_r5"]["side_r5_on_cl_windows"] = side_metrics(sub, "p_r5")
            res["presence_r5"]["side_r3_on_cl_windows"] = side_metrics(sub, "p_" + MODEL)
    except Exception as ex:  # the Chainlink part must never break the tape evaluation
        res["presence_r5"] = {"error": repr(ex)[:300]}
    act = panel.groupby("cid")["y"].transform("max") > 0
    res["presence"] = {"auc": _auc(panel["y"], panel["p_" + MODEL]), "auc_activity_baseline": _auc(panel["y"], panel["p_" + BASELINE]),
                       "auc_with_own_inventory": _auc(panel["y"], panel["p_" + OWN_MODEL]),
                       "auc_within_active_windows": _auc(panel.loc[act, "y"], panel.loc[act, "p_" + MODEL]),
                       "pos_rate": float(panel["y"].mean()), "active_window_share": float(panel.groupby("cid")["y"].max().mean())}
    res["presence"]["gain_over_baseline"] = res["presence"]["auc"] - res["presence"]["auc_activity_baseline"]
    res["side"] = side_metrics(panel, "p_" + MODEL)
    res["side_activity_baseline"] = side_metrics(panel, "p_" + BASELINE)["acc"]
    per_wallet = {}
    for addr, name in CLUSTER.items():
        yw = _wallet_labels(panel, w, mk, addr)
        pw = panel.assign(y=yw)
        per_wallet[name] = {"fills": int((mk["wallet"] == addr).sum()),
                            "presence_auc": _auc(yw, panel["p_" + MODEL].to_numpy()),
                            "presence_auc_activity_baseline": _auc(yw, panel["p_" + BASELINE].to_numpy()),
                            "side": side_metrics(pw, "p_" + MODEL)["acc"] if yw.sum() else float("nan")}
        if "p_r5" in panel.columns and "cl_ok" in panel.columns:
            okw_ = panel.groupby("cid")["cl_ok"].transform("all").to_numpy()
            if okw_.any():
                per_wallet[name]["presence_auc_r5_on_cl_windows"] = _auc(yw[okw_], panel["p_r5"].to_numpy()[okw_])
                per_wallet[name]["presence_auc_r3_on_cl_windows"] = _auc(yw[okw_], panel["p_" + MODEL].to_numpy()[okw_])
    # price: last clean print on s strictly before the fill second - 0.01
    upset = set(w["up_token"])
    tok2cid = {**dict(zip(w["up_token"], w["cid"])), **dict(zip(w["down_token"], w["cid"]))}
    c2 = clean.merge(w[["cid", "up_token"]], on="cid")
    c2["up_px"] = np.where(c2["asset"] == c2["up_token"], c2["price"], 1 - c2["price"])
    by = {c: (g["ts"].to_numpy(), g["up_px"].to_numpy()) for c, g in c2.sort_values("ts", kind="stable").groupby("cid")}
    by_block = by
    pred, actual, pw_wal = [], [], []
    for r in mk.itertuples(index=False):
        cid = tok2cid.get(r.token_id)
        if cid not in by:
            continue
        ts_, px_ = by[cid]
        i = np.searchsorted(ts_, r.ts, side="left") - 1
        if i < 0:
            continue
        ls = px_[i] if r.token_id in upset else 1 - px_[i]
        pred.append(round(ls - PRICE_OFFSET, 2))
        actual.append(r.price)
        pw_wal.append(r.wallet)
    e = np.abs(np.asarray(actual) - np.asarray(pred))
    res["price"] = {"n_fills": int(len(e)), "exact": float(np.mean(e < 0.0005)) if len(e) else float("nan"),
                    "within_0.01": float(np.mean(e <= 0.0105)) if len(e) else float("nan")}
    pw_wal = np.asarray(pw_wal)
    for addr, name in CLUSTER.items():
        k = pw_wal == addr
        per_wallet[name]["price_within_0.01"] = float(np.mean(e[k] <= 0.0105)) if k.any() else float("nan")
    # R4 price on the match clock (iteration 6): shared live recorder 'x' stream where it exists, block clock elsewhere
    try:
        bt = pd.DataFrame({"tx": [], "pred_block": []})
        if len(mk):
            bt_rows = []
            for r in mk.itertuples(index=False):
                cid = tok2cid.get(r.token_id)
                if cid not in by_block:
                    continue
                ts_, px_ = by_block[cid]
                i = np.searchsorted(ts_, r.ts, side="left") - 1
                if i >= 0:
                    ls = px_[i] if r.token_id in upset else 1 - px_[i]
                    bt_rows.append((r.tx, r.token_id, round(ls - PRICE_OFFSET, 2)))
            bt = pd.DataFrame(bt_rows, columns=["tx", "token_id", "pred_block"])
        # iteration 8 fix: _cluster_trades keeps compact tx keys; the live trade stream carries full hashes
        _txh = _cluster_tx_hashes(start_ts, end_ts, pm, local)
        mk_h = mk.assign(tx=mk["tx"].map(_txh).fillna("").astype(str))
        bt_h = bt.assign(tx=bt["tx"].map(_txh).fillna("").astype(str)) if len(bt) else bt
        res["price_match_clock"] = price_match_clock(mk_h, w, start_ts, end_ts, bt_h)
        for name, v in res["price_match_clock"].get("per_wallet", {}).items():
            per_wallet[name]["price_match_clock_within_0.01"] = v.get("within_0.01")
            per_wallet[name]["price_combined_within_0.01"] = v.get("combined_within_0.01")
    except Exception as ex:  # the live part must never break the tape evaluation
        res["price_match_clock"] = {"error": repr(ex)[:300]}
    # PnL per window: wallet maker fills vs the rule's expected PnL
    pay = dict(zip(w["cid"], w["up_payout"]))
    mk2 = mk.assign(c=[tok2cid.get(t) for t in mk["token_id"]], up=mk["token_id"].isin(upset))
    mk2["won"] = [(pay.get(c) if u else 1 - pay.get(c)) if pay.get(c) is not None else np.nan for c, u in zip(mk2["c"], mk2["up"])]
    wal = ((mk2["won"] - mk2["price"]) * mk2["shares"]).groupby(mk2["c"]).sum()
    pr = panel.dropna(subset=["won_s"]).copy()
    pr["rule_pnl"] = pr["p_" + MODEL] * (pr["won_s"] - (pr["last_s"].fillna(0.5) - PRICE_OFFSET).round(2))
    j = pd.concat([wal.rename("wallet"), pr.groupby("cid")["rule_pnl"].sum().rename("rule")], axis=1).dropna()
    usd = float((mk2["price"] * mk2["shares"]).sum())
    rule_w = pr.groupby("cid")["rule_pnl"].sum()
    for addr, name in CLUSTER.items():
        m2 = mk2[mk2["wallet"] == addr]
        ww = ((m2["won"] - m2["price"]) * m2["shares"]).groupby(m2["c"]).sum()
        jj = pd.concat([ww.rename("wallet"), rule_w.rename("rule")], axis=1).dropna()
        per_wallet[name]["pnl_pearson"] = float(jj.corr().iloc[0, 1]) if len(jj) > 2 else float("nan")
        per_wallet[name]["pnl_spearman"] = float(jj.corr(method="spearman").iloc[0, 1]) if len(jj) > 2 else float("nan")
        per_wallet[name]["pnl_windows"] = int(len(jj))
    res["per_wallet"] = per_wallet
    res["pnl"] = {"windows": int(len(j)), "pearson": float(j.corr().iloc[0, 1]) if len(j) > 2 else float("nan"),
                  "spearman": float(j.corr(method="spearman").iloc[0, 1]) if len(j) > 2 else float("nan"),
                  "wallet_maker_return_on_usd": float(((mk2["won"] - mk2["price"]) * mk2["shares"]).sum() / usd) if usd else float("nan")}
    del c2, by, clean
    # selection over in-window taker prints, per UTC day block, with the rotation null (scores aligned to rows)
    models = {nm: lgb.Booster(model_file=str(HERE / f"selection2_{nm}.txt")) for nm in ("all", "activity")}
    mk_tx = set(mk["tx"])
    rng = np.random.default_rng(12)
    te_all, S = [], []
    for d in sorted(set(w["start_ts"] // 86400 * 86400)):
        wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400)]
        if len(wd) < 4:
            continue
        te, pan_d, wdd = sel2.day_prints(d, w, sp, mk_tx, cw, SEL_NEG_FRAC, rng, tk=tk[tk["cid"].isin(set(wd["cid"]))],
                                         pan=panel[panel["cid"].isin(set(wd["cid"]))])
        if len(te) == 0:
            continue
        te = te.reset_index(drop=True)
        te["rid"] = np.arange(len(te))
        te["s_all"] = models["all"].predict(te[sel2.F_ALL]).astype(np.float32)
        te["s_activity"] = models["activity"].predict(te[sel2.F_ACT]).astype(np.float32)
        te["wkey"] = (te["day"] // 86400 * 1000 + te["widx"]).astype(np.int64)
        prng = np.random.default_rng(500 + d % 1000)
        sd = np.full((n_perm, len(te)), np.nan, np.float32)
        for i in range(n_perm):
            r = sel2.rotated(te, pan_d, wdd, sp, int(prng.integers(1, len(wdd))))
            sd[i, r["rid"].to_numpy()] = models["all"].predict(r[sel2.F_ALL]).astype(np.float32)
        S.append(sd)
        te_all.append(te[["wkey", "y", "wt", "q", "rel_p", "side_up", "s_all", "s_activity"]].rename(columns={"wkey": "cid"}))
        del te, pan_d, r
    sel = {}
    if te_all:
        te = pd.concat(te_all, ignore_index=True)
        S = np.concatenate(S, axis=1)
        gg, gw = sel2.strata(te, 50, 40, False), sel2.strata(te, 10, 10, True)
        y, wt = te["y"].to_numpy(), te["wt"].to_numpy()
        base = float(y.sum() / wt.sum())
        for nm in ("all", "activity"):
            s = te["s_" + nm].to_numpy()
            flag = s >= THETA_SEL[nm]
            sel[nm] = {"auc": sel2.wauc(s, y, wt), "auc_strat_global": sel2.wauc(s, y, wt, gg),
                       "auc_strat_window": sel2.wauc(s, y, wt, gw), "recall_at_theta": float(flag[y == 1].mean()),
                       "lift_at_theta": float(np.sum(flag & (y == 1)) / np.sum(wt * flag) / base) if flag.any() else float("nan")}
        ng, nw = [], []
        for i in range(n_perm):
            ok = np.isfinite(S[i])
            ng.append(sel2.wauc(S[i][ok], y[ok], wt[ok], gg[ok]))
            nw.append(sel2.wauc(S[i][ok], y[ok], wt[ok], gw[ok]))
        if n_perm:
            ng, nw = np.array(ng), np.array(nw)
            a = sel["all"]
            a["rotation_null"] = {"global_mean": float(ng.mean()), "global_max": float(ng.max()),
                                  "global_sd": float(ng.std(ddof=1)) if n_perm > 1 else float("nan"),
                                  "window_mean": float(nw.mean()), "window_max": float(nw.max()),
                                  "window_sd": float(nw.std(ddof=1)) if n_perm > 1 else float("nan"), "n_perm": n_perm}
            nn = a["rotation_null"]
            a["z_vs_null_global"] = (a["auc_strat_global"] - nn["global_mean"]) / nn["global_sd"] if nn["global_sd"] > 0 else float("nan")
            a["z_vs_null_window"] = (a["auc_strat_window"] - nn["window_mean"]) / nn["window_sd"] if nn["window_sd"] > 0 else float("nan")
            a["p_global"] = float((1 + (ng >= a["auc_strat_global"]).sum()) / (n_perm + 1))
            a["p_window"] = float((1 + (nw >= a["auc_strat_window"]).sum()) / (n_perm + 1))
            a["perm_p"] = max(a["p_global"], a["p_window"])
            a["criterion"] = {"auc_ge_0.80": a["auc"] >= 0.80, "recall_ge_0.50": a["recall_at_theta"] >= 0.5,
                              "lift_ge_3": a["lift_at_theta"] >= 3, "p_lt_0.01": a["perm_p"] < 0.01}
        sel["prints_sampled"] = int(len(te))
        sel["wallet_prints"] = int(y.sum())
    res["selection"] = sel
    res["note"] = ("selection population = in-window taker prints except the cluster's own taker prints; label = print's "
                   "transaction holds a cluster maker fill; negatives subsampled 10% (weights 10), AUCs unbiased; rotation null: "
                   "each day's windows take the spot path of the window k places later (bin-level spot columns and print fair recomputed)")
    # R6 scope (iteration 8): BTC 15m with R3's model class, and the union BTC 5m + 15m (pooled bins)
    try:
        from train2 import side_metrics as _sm
        r15, p15, w15, mk15 = _evaluate_btc15m(start_ts, end_ts, intervals, pm, sp, ct, local)
        res["btc15m"] = r15
        if p15 is not None and len(p15):
            u = pd.concat([panel[["cid", "rel", "side_up", "y", "last_s", "fair_s", "start_ts", "p_" + MODEL, "p_" + BASELINE]], p15],
                          ignore_index=True)
            res["union_btc5m_15m"] = {"presence_auc": _auc(u["y"], u["p_" + MODEL]),
                                      "presence_auc_activity_baseline": _auc(u["y"], u["p_" + BASELINE]),
                                      "bins": int(len(u)), "pos": int(u["y"].sum())}
            res["union_btc5m_15m"]["gain_over_baseline"] = (res["union_btc5m_15m"]["presence_auc"]
                                                            - res["union_btc5m_15m"]["presence_auc_activity_baseline"])
            try:
                res["union_btc5m_15m"]["side"] = _sm(u, "p_" + MODEL)
            except Exception as ex:
                res["union_btc5m_15m"]["side"] = {"error": repr(ex)[:200]}
            n5, n15 = int(res.get("price", {}).get("n_fills", 0)), int(r15.get("price", {}).get("n_fills", 0))
            if n5 + n15:
                res["union_btc5m_15m"]["price_within_0.01_block_clock"] = (
                    (res["price"]["within_0.01"] * n5 if n5 else 0.0) + (r15["price"]["within_0.01"] * n15 if n15 else 0.0)) / (n5 + n15)
            for name in CLUSTER.values():
                if name in res.get("per_wallet", {}) and name in r15.get("per_wallet", {}):
                    res["per_wallet"][name]["btc15m"] = r15["per_wallet"][name]
            # scope: share of the cluster BUY trades (maker and taker, every market) in BTC 5m and in BTC 5m + 15m
            fam = np.where(ct["cid"].isin(set(w["cid"])), "btc5m", np.where(ct["cid"].isin(set(w15["cid"])), "btc15m", "other"))
            bt_ = ct["side"].to_numpy() == "BUY"
            usd = (ct["price"] * ct["shares"]).to_numpy()
            tot_n, tot_usd = bt_.sum(), usd[bt_].sum()
            res["scope"] = {"buy_trades": int(tot_n),
                            "share_trades_btc5m": float((bt_ & (fam == "btc5m")).sum() / tot_n) if tot_n else float("nan"),
                            "share_trades_btc5m_15m": float((bt_ & (fam != "other")).sum() / tot_n) if tot_n else float("nan"),
                            "share_usd_btc5m": float(usd[bt_ & (fam == "btc5m")].sum() / tot_usd) if tot_usd else float("nan"),
                            "share_usd_btc5m_15m": float(usd[bt_ & (fam != "other")].sum() / tot_usd) if tot_usd else float("nan"),
                            "note": "rule universe = BTC 5m + BTC 15m; a block with BTC 5m off is scored on BTC 15m (pre-registered "
                                    "2026-10-31 iteration 8); trade-count and dollar shares of all cluster BUY trades; abs-PnL share not computed here"}
    except Exception as ex:  # the 15m part must never break the 5m evaluation
        res["btc15m"] = {"error": repr(ex)[:300]}
    # R6 side per fill on the match clock (iteration 8): BTC 5m + 15m maker fills with a recorded match
    try:
        mk_all, w_all = mk, w
        if "mk15" in locals() and mk15 is not None and len(mk15):
            mk_all = pd.concat([mk, mk15], ignore_index=True)
            w_all = pd.concat([w, w15], ignore_index=True)
        txh = _cluster_tx_hashes(start_ts, end_ts, pm, local)
        mk_all = mk_all.assign(txh=mk_all["tx"].map(txh))
        res["side_posture_match_clock"] = side_posture_match_clock(mk_all, w_all, start_ts, end_ts, sp)
    except Exception as ex:  # the live part must never break the tape evaluation
        res["side_posture_match_clock"] = {"error": repr(ex)[:300]}
    del stats
    return res


if __name__ == "__main__":
    import json
    a, b = int(sys.argv[1]), int(sys.argv[2])
    print(json.dumps(evaluate(a, b, local="local" in sys.argv[3:], cache_only="cache" in sys.argv[3:]), indent=1, default=str))
