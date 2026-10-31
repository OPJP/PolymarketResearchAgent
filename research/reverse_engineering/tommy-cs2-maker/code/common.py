"""Shared loaders for tommy-cs2-maker (development data only; everything ends before H)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

H = 1792713600
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OUT = ROOT / ".cache/re/tommy-cs2-maker"
TAPES = OUT / "tapes"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker"
MAKER_START = 1792108800  # 2026-10-16 00:00 UTC (fixed: the cloud value 1792540800-4*86400 was 17 Oct)
SPLIT = 1792540800  # 2026-10-21 00:00 UTC: BUILD = [MAKER_START, SPLIT), VALIDATE = [SPLIT, H)


def token_map() -> dict[str, tuple[str, int]]:
    """token id -> (condition id, outcome index) from Gamma clobTokenIds (wallet markets + universe)."""
    out: dict[str, tuple[str, int]] = {}
    m = json.load(open(OUT / "markets_dev.json"))
    for cid, x in m.items():
        toks = x.get("clobTokenIds")
        toks = json.loads(toks) if isinstance(toks, str) else (toks or [])
        for i, t in enumerate(toks):
            out[str(t)] = (cid, i)
    u = pd.read_parquet(OUT / "universe.parquet")
    for cid, toks in zip(u["cid"], u["tokens"]):
        toks = json.loads(toks) if isinstance(toks, str) else (toks or [])
        for i, t in enumerate(toks):
            out.setdefault(str(t), (cid, i))
    return out


def chain_fills() -> pd.DataFrame:
    f = pd.read_parquet(OUT / "chain_fills_1791072000_1792713600.parquet")
    f = f[f["bts"] < H].copy()
    tm = token_map()
    f["cid"] = f["token_id"].map(lambda t: tm.get(str(t), (None, -1))[0])
    f["oi"] = f["token_id"].map(lambda t: tm.get(str(t), (None, -1))[1])
    f["price"] = f["usdc"] / f["shares"]
    return f


def universe() -> pd.DataFrame:
    u = pd.read_parquet(OUT / "universe.parquet")
    u["gs_ts"] = u["gs_ts"].astype("int64")
    return u


def tape(cid: str, kind: str = "full") -> pd.DataFrame | None:
    p = TAPES / f"{cid}_{kind}.parquet"
    if not p.exists():
        return None
    d = pd.read_parquet(p)
    return d[d["timestamp"] < H]


def auc(score, y) -> float:
    from scipy.stats import rankdata
    score = np.asarray(score, float); y = np.asarray(y).astype(bool)
    m = np.isfinite(score); s = score[m]; yy = y[m]
    n1 = yy.sum(); n0 = (~yy).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[yy].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
