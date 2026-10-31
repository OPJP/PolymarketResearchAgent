"""Presence dataset: one row per (market, 30-s bin) of every CS2 match / map-winner market.

Universe (pre-registered): moneyline + child_moneyline markets with gameStartTime in [d0, d1), bins
[gs + 30k, gs + 30k + 30) for k = 0..479, truncated at H. Label: the wallet has >= 1 TRADE in the bin.
Features use only taker prints stamped strictly before the bin start, excluding every transaction in
which the wallet traded (its own prints and prints where it was the maker are never features), plus
listing metadata. No own-state features here.
Output: .cache/re/tommy-cs2-maker/bins_<d0>_<d1>.parquet
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import H, OUT, TAPES  # noqa: E402

BIN = 30
NB = 480


def map_no(q: str, smt: str) -> int:
    if smt == "moneyline":
        return 0
    m = re.search(r"(?:Map|Game)\s*(\d)", str(q))
    return int(m.group(1)) if m else 9


def wallet_trades() -> pd.DataFrame:
    a = pd.read_parquet(OUT / "activity_dev.parquet", columns=["timestamp", "conditionId", "type", "size", "usdcSize", "price", "outcomeIndex", "transactionHash"])
    t = a[a["type"] == "TRADE"].copy()
    for c in ["timestamp", "size", "usdcSize", "price"]:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t["outcomeIndex"] = pd.to_numeric(t["outcomeIndex"], errors="coerce").astype(int)
    return t[t["timestamp"] < H]


def load_tape(cid: str, bad_tx: set) -> pd.DataFrame:
    p = TAPES / f"{cid}_tkw.parquet"
    if not p.exists():
        return None
    d = pd.read_parquet(p)
    if len(d) == 0:
        return d.assign(p0=pd.Series(dtype=float), usd=pd.Series(dtype=float))
    d = d[(d["timestamp"] < H) & ~d["transactionHash"].isin(bad_tx)].copy()
    d["price"] = d["price"].astype(float)
    d["size"] = d["size"].astype(float)
    oi = d["outcomeIndex"].astype(int)
    # outcome-0 probability implied by the print (a BUY of outcome 1 at p means outcome 0 at 1-p)
    d["p0"] = np.where(oi == 0, d["price"], 1 - d["price"])
    d["usd"] = d["price"] * d["size"]
    return d.sort_values("timestamp", kind="stable").reset_index(drop=True)


def window_feats(ts: np.ndarray, usd: np.ndarray, p0: np.ndarray, wal: np.ndarray, starts: np.ndarray, pfx: str) -> dict:
    """Counts / volumes / price moves of prints with timestamp < bin start."""
    out = {}
    cu = np.concatenate([[0.0], np.cumsum(usd)]) if len(ts) else np.zeros(1)
    i_now = np.searchsorted(ts, starts, side="left")  # prints strictly before start
    for w in (30, 120, 600):
        i0 = np.searchsorted(ts, starts - w, side="left")
        out[f"{pfx}n{w}"] = (i_now - i0).astype(np.float32)
        out[f"{pfx}v{w}"] = (cu[i_now] - cu[i0]).astype(np.float32)
    out[f"{pfx}cum"] = i_now.astype(np.float32)
    last = np.where(i_now > 0, ts[np.maximum(i_now - 1, 0)] if len(ts) else 0, np.nan)
    out[f"{pfx}tsl"] = np.minimum(np.where(np.isfinite(last), starts - last, 7200), 7200).astype(np.float32)
    if p0 is not None:
        pl = np.where(i_now > 0, p0[np.maximum(i_now - 1, 0)] if len(ts) else np.nan, np.nan)
        out[f"{pfx}p"] = pl.astype(np.float32)
        out[f"{pfx}dev"] = np.abs(pl - 0.5).astype(np.float32)
        for w in (60, 300):
            j = np.searchsorted(ts, starts - w, side="left")
            pw = np.where(j > 0, p0[np.maximum(j - 1, 0)] if len(ts) else np.nan, np.nan)
            out[f"{pfx}dp{w}"] = np.abs(pl - pw).astype(np.float32)
        # distinct taker wallets in the last 600 s
        i0 = np.searchsorted(ts, starts - 600, side="left")
        out[f"{pfx}nw600"] = np.array([len(set(wal[a:b])) for a, b in zip(i0, i_now)], dtype=np.float32)
    return out


def main(d0: int, d1: int) -> None:
    u = pd.read_parquet(OUT / "universe.parquet")
    u = u[u["smt"].isin(["moneyline", "child_moneyline"]) & (u["gs_ts"] >= d0) & (u["gs_ts"] < min(d1, H))].copy()
    u["gs_ts"] = u["gs_ts"].astype("int64")
    wt = wallet_trades()
    bad_tx = set(wt["transactionHash"])
    tapes = {cid: load_tape(cid, bad_tx) for cid in u["cid"]}
    missing = [c for c, d in tapes.items() if d is None]
    print("markets", len(u), "missing tapes", len(missing), flush=True)
    u = u[~u["cid"].isin(missing)]
    wt_by = {c: g["timestamp"].to_numpy() for c, g in wt.groupby("conditionId")}
    frames = []
    for ev, ge in u.groupby("event_slug"):
        et = pd.concat([tapes[c] for c in ge["cid"]], ignore_index=True).sort_values("timestamp", kind="stable")
        ets, eusd = et["timestamp"].to_numpy(np.int64), et["usd"].to_numpy(float)
        for r in ge.itertuples():
            gs = int(r.gs_ts)
            starts = gs + BIN * np.arange(NB, dtype=np.int64)
            starts = starts[starts + BIN <= H]
            if len(starts) == 0:
                continue
            d = tapes[r.cid]
            ts = d["timestamp"].to_numpy(np.int64)
            f = window_feats(ts, d["usd"].to_numpy(float), d["p0"].to_numpy(float), d["proxyWallet"].to_numpy(), starts, "m_")
            f.update(window_feats(ets, eusd, None, None, starts, "e_"))
            # pre-game liquidity of the event (prints in [gs-1h, gs)), known at gs
            pre = ((ets >= gs - 3600) & (ets < gs)).sum()
            wts = wt_by.get(r.cid, np.zeros(0, np.int64))
            y = (np.searchsorted(wts, starts + BIN, side="left") - np.searchsorted(wts, starts, side="left")) > 0 if len(wts) else np.zeros(len(starts), bool)
            df = pd.DataFrame(f)
            df["cid"] = r.cid
            df["event"] = ev
            df["start"] = starts
            df["elapsed"] = ((starts - gs) / 60).astype(np.float32)
            df["is_match"] = np.float32(r.smt == "moneyline")
            df["map_no"] = np.float32(map_no(r.question, r.smt))
            df["e_pre"] = np.float32(pre)
            df["tier"] = np.float32(pd.to_numeric(r.league_tier, errors="coerce"))
            df["league"] = str(r.league)
            df["gs_hour"] = np.float32(pd.Timestamp(gs, unit="s").hour)
            df["y"] = y.astype(np.int8)
            frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["league"] = out["league"].astype("category")
    out.to_parquet(OUT / f"bins_{d0}_{d1}.parquet", index=False)
    print("bins", len(out), "pos", int(out["y"].sum()), "markets", out["cid"].nunique(), "wallet markets", out.loc[out.y == 1, "cid"].nunique(), flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
