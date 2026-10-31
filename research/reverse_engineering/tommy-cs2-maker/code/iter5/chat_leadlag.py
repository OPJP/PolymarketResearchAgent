"""PRE-REGISTERED analysis for X38 (written in iteration 5, 2026-10-31, before any chat record of a traded event exists).

Question: does broadcast chat react to the wallet's taker decisions after ~a stream delay (V1: its feed is upstream of
the broadcast, peak lag 60-300 s) or almost at once (V2: its feed is derived from the stream, peak lag 0-20 s)?

Inputs (development blocks only, iter_live without allow_sealed; units filtered by game start):
  * tommy_chat records {"k": "chat", "s": tmi_sent_ts_ms, "ch": channel} and {"k": "sub", "m": {channel: [[slug, gs]..]}}
    (v1 format {channel: [slug, gs]} accepted);
  * the wallet's taker signings: a calldata parquet (idx == -1, maker == wallet, side 0, sign_ms) of the development-unit
    markets, mapped to event slugs with a markets table (cid -> event slug); both given on the command line.
Method (frozen):
  1. Per channel-event pair (channel streaming the event, gs in a development block): chat counts per 1-s bin over
     [gs, gs + 4 h]; standardise by a centred 120-s rolling median and MAD -> z(t).
  2. Event-triggered average of z at lags L = -60..+600 s (1-s steps) around each wallet take of that event (fan-out legs
     within 5 ms merged); smooth with a 5-s boxcar; peak lag L* = argmax over L in [0, 600] s.
  3. Null: the same statistic with the takes shifted by a uniform +-[600, 1800] s (2,000 draws, shifts that leave the
     event window are re-drawn); p = share of null peaks >= the observed peak height (one-sided).
  4. Event block bootstrap (1,000 draws over channel-event pairs) for the CI of L*.
Decision (pre-registered): p < 0.0025 and L* in [60, 300] s -> V1; p < 0.0025 and L* in [0, 20] s -> V2; else
inconclusive (report L*, p, CI). Also report, as a calibration, the same triggered average around the PUBLIC repricing
jumps (>= 4c moves of the event's markets in 10 s, from the recorder's trades), whose own lag D_M dates the market vs
the broadcast.
Usage: chat_leadlag.py START_TS END_TS CALLDATA_PARQUET MARKETS_PARQUET(cid, slug|event)  -> results/chat_leadlag.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
import sealed  # noqa: E402

KEY = "tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
LAGS = np.arange(-60, 601)
ALPHA = 0.0025


def read(feed, start, end):
    out = []
    h = int(start // 3600 * 3600)
    while h < end:
        try:
            out.extend(live.iter_live(feed, max(h, start), min(h + 3600, end)))
        except Exception:  # noqa: BLE001  (file still being written)
            pass
        h += 3600
    return out


def zseries(counts):
    s = pd.Series(counts, dtype=float)
    med = s.rolling(121, center=True, min_periods=30).median()
    mad = (s - med).abs().rolling(121, center=True, min_periods=30).median().replace(0, np.nan)
    return ((s - med) / (1.4826 * mad)).fillna(0).clip(-10, 10).to_numpy()


def triggered(z, idx):
    rows = []
    for i in idx:
        lo, hi = i + LAGS[0], i + LAGS[-1]
        if lo < 0 or hi >= len(z):
            continue
        rows.append(z[lo:hi + 1])
    if not rows:
        return None
    m = np.mean(rows, axis=0)
    return np.convolve(m, np.ones(5) / 5, mode="same")


def main(start, end, calldata_path, markets_path):
    recs = read("tommy_chat", start, end)
    chans = defaultdict(set)
    chat = defaultdict(list)
    for r in recs:
        if r.get("k") == "sub":
            for ch, v in (r.get("m") or {}).items():
                units = v if (isinstance(v, list) and v and isinstance(v[0], list)) else [v]
                for u in units:
                    slug, gs = u[0], float(u[1])
                    if not sealed.is_sealed(gs, KEY):
                        chans[ch].add((slug, gs))
        elif r.get("k") == "chat" and r.get("s"):
            chat[r["ch"]].append(int(r["s"]) // 1000)
    cd = pd.read_parquet(calldata_path)
    mk = pd.read_parquet(markets_path)
    slug_col = "event" if "event" in mk.columns else "slug"
    cid2ev = dict(zip(mk.cid, mk[slug_col]))
    tk = cd[(cd.idx == -1) & (cd.maker == WALLET) & (cd.side == 0)].copy()
    if "cid" not in tk.columns and "condition_id" in tk.columns:
        tk["cid"] = tk.condition_id
    tk["ev"] = tk.cid.map(cid2ev)
    tk = tk[tk.ev.notna() & (tk.sign_ms > 1.7e12)].sort_values("sign_ms")
    pairs = []
    for ch, units in chans.items():
        for slug, gs in units:
            ts = np.array(chat.get(ch, []), dtype=np.int64)
            ts = ts[(ts >= gs) & (ts < gs + 4 * 3600)]
            if len(ts) < 200:
                continue
            counts = np.bincount((ts - int(gs)).astype(int), minlength=4 * 3600)
            z = zseries(counts)
            s = tk[tk.ev.astype(str).str.contains(str(slug).split("-")[-1], regex=False) | (tk.ev == slug)].sign_ms.to_numpy(float) / 1000
            s = s[np.r_[True, np.diff(s) > 0.005]] if len(s) else s
            idx = (s - gs).astype(int)
            idx = idx[(idx >= 0) & (idx < len(z))]
            if len(idx) >= 3:
                pairs.append((ch, slug, z, idx))
    res = {"pairs": [(p[0], p[1], int(len(p[3]))) for p in pairs], "decision": "no data"}
    if pairs:
        def stat(ps, shift=None, rng=None):
            acc = []
            for ch, slug, z, idx in ps:
                ii = idx
                if shift is not None:
                    ii = idx + rng.choice([-1, 1]) * rng.integers(600, 1801)
                tr = triggered(z, ii)
                if tr is not None:
                    acc.append(tr)
            return np.mean(acc, axis=0) if acc else None

        obs = stat(pairs)
        pos = LAGS >= 0
        Lstar = int(LAGS[pos][np.argmax(obs[pos])])
        peak = float(obs[pos].max())
        rng = np.random.default_rng(0)
        null = []
        for _ in range(2000):
            t = stat(pairs, shift=True, rng=rng)
            if t is not None:
                null.append(float(t[pos].max()))
        p = float(np.mean(np.array(null) >= peak)) if null else None
        boot = []
        for _ in range(1000):
            pick = [pairs[i] for i in rng.integers(0, len(pairs), len(pairs))]
            t = stat(pick)
            if t is not None:
                boot.append(int(LAGS[pos][np.argmax(t[pos])]))
        dec = "inconclusive"
        if p is not None and p < ALPHA:
            dec = "V1 (upstream of the broadcast)" if 60 <= Lstar <= 300 else ("V2 (stream-derived)" if 0 <= Lstar <= 20 else "inconclusive")
        res.update({"peak_lag_s": Lstar, "peak_z": round(peak, 3), "p_null": p, "lag_ci95": [int(np.percentile(boot, 2.5)), int(np.percentile(boot, 97.5))] if boot else None,
                    "decision": dec, "triggered_mean": {int(l): round(float(v), 3) for l, v in zip(LAGS[::10], obs[::10])}})
    (RES / "chat_leadlag.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "triggered_mean"}, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(float(a[0]), float(a[1]), a[2], a[3])
