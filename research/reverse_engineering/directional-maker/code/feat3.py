"""Iteration 3, family N3 ("who is arriving"): counterparty-type and order-size arrival features per
(BTC 5m window, side, 10-s bin), from the CLEAN tape (every print in a cluster transaction and every
cluster taker print removed), point-in-time (prints with ts < bin start).

Motivation (iteration 2): the cluster's counterparties are larger (median 18 vs 8 shares), dispersed
takers; the high-frequency takers rarely hit it (0.3% of their prints). If fills need a large, slow taker
to cross the cluster's top-of-book bid, the recent arrival rate of such takers on each side should
predict presence beyond raw print counts.

HFT takers = wallets with >= 5,000 clean BTC 5m taker prints in the BUILD week (frozen list saved to
code/hft_takers3.json; built from BUILD only).

python code/feat3.py hft      build the frozen HFT list from BUILD days
python code/feat3.py          write feat3_day_<d>.parquet for every day (joined later on cid, rel, side_up)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from panel2 import OUT, WALLETS, H, cluster_trades  # noqa: E402

VAL0 = 1792108800
REL = np.arange(0, 300, 10)
HFT_FILE = HERE / "hft_takers3.json"
NEW_S = ["bh_big_s30", "bh_big_s60", "bh_big_s120", "bh_hft_s60", "bh_slow_s60", "bh_max_s60", "age_big_s", "dir20_s",
         "bh_big_o60", "bh_slow_o60", "bh_max_o60", "age_big_o"]
NEW_W = ["hft_sh60", "slow_nt60", "n120"]
NEW = NEW_S + NEW_W


def clean_day(f: Path, ctx: set, cw: set) -> pd.DataFrame:
    tk = pd.read_parquet(f, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])
    return tk[~(tk["tx"].isin(ctx) | tk["wallet"].isin(cw))]


def build_hft():
    ct = cluster_trades()
    ctx, cw = set(ct["tx"]), set(WALLETS.values())
    cnt = None
    for f in sorted(OUT.glob("taker5m_day_*.parquet")):
        d = int(f.stem.split("_")[-1])
        if d >= VAL0:
            continue
        c = clean_day(f, ctx, cw)["wallet"].value_counts()
        cnt = c if cnt is None else cnt.add(c, fill_value=0)
    hft = sorted(cnt.index[cnt >= 5000].tolist())
    HFT_FILE.write_text(json.dumps(hft))
    print("hft takers", len(hft), "share of BUILD clean prints", round(float(cnt[hft].sum() / cnt.sum()), 3))


def window_feats(win, g: pd.DataFrame, hft: set) -> pd.DataFrame:
    t = win.start_ts + REL
    n = len(t)
    tts = g["ts"].to_numpy().astype(np.int64)
    o = np.argsort(tts, kind="stable")
    tts = tts[o]
    is_up = (g["asset"].to_numpy() == win.up_token)[o]
    buy = (g["side"].astype(str).to_numpy() == "BUY")[o]
    sz = g["size"].to_numpy().astype(float)[o]
    wal = g["wallet"].to_numpy()[o]
    ish = np.isin(wal, list(hft))
    hit_up = (is_up & ~buy) | (~is_up & buy)
    big = sz >= 20
    idx = np.searchsorted(tts, t, side="left")

    def csum(mask):
        return np.concatenate([[0], np.cumsum(mask)])

    def wcount(c, k):
        j = np.searchsorted(tts, t - k, side="left")
        return (c[idx] - c[j]).astype(np.float32)

    out = {}
    for s, hs in (("up", hit_up), ("down", ~hit_up)):
        r = {}
        cb = csum(hs & big)
        r["bh_big_s30"], r["bh_big_s60"], r["bh_big_s120"] = wcount(cb, 30), wcount(cb, 60), wcount(cb, 120)
        r["bh_hft_s60"] = wcount(csum(hs & ish), 60)
        r["bh_slow_s60"] = wcount(csum(hs & ~ish), 60)
        j60 = np.searchsorted(tts, t - 60, side="left")
        szh = np.where(hs, sz, 0.0)
        r["bh_max_s60"] = np.array([szh[a:b].max() if b > a else 0.0 for a, b in zip(j60, idx)], dtype=np.float32)
        bb = np.flatnonzero(hs & (sz >= 50))
        kk = np.searchsorted(tts[bb], t, side="left") - 1 if len(bb) else np.full(n, -1)
        r["age_big_s"] = np.where(kk >= 0, t - tts[bb][np.clip(kk, 0, None)] if len(bb) else 9999, 9999).astype(np.float32)
        ch = csum(hs)
        j20 = np.maximum(idx - 20, 0)
        r["dir20_s"] = np.where(idx > 0, (ch[idx] - ch[j20]) / np.maximum(idx - j20, 1), np.nan).astype(np.float32)
        out[s] = r
    j60 = np.searchsorted(tts, t - 60, side="left")
    j120 = np.searchsorted(tts, t - 120, side="left")
    cnt60 = (idx - j60).astype(np.float32)
    hft_sh60 = np.where(cnt60 > 0, (csum(ish)[idx] - csum(ish)[j60]) / np.maximum(cnt60, 1), np.nan).astype(np.float32)
    slow_nt60 = np.array([len(set(wal[a:b][~ish[a:b]])) for a, b in zip(j60, idx)], dtype=np.float32)
    rows = []
    for s in ("up", "down"):
        oth = "down" if s == "up" else "up"
        d = {"cid": win.cid, "rel": REL, "side_up": int(s == "up")}
        for k in ("bh_big_s30", "bh_big_s60", "bh_big_s120", "bh_hft_s60", "bh_slow_s60", "bh_max_s60", "age_big_s", "dir20_s"):
            d[k] = out[s][k]
        d["bh_big_o60"], d["bh_slow_o60"], d["bh_max_o60"], d["age_big_o"] = (out[oth]["bh_big_s60"], out[oth]["bh_slow_s60"],
                                                                              out[oth]["bh_max_s60"], out[oth]["age_big_s"])
        d["hft_sh60"], d["slow_nt60"], d["n120"] = hft_sh60, slow_nt60, (idx - j120).astype(np.float32)
        rows.append(pd.DataFrame(d))
    return pd.concat(rows, ignore_index=True)


def main(days=None):
    hft = set(json.loads(HFT_FILE.read_text()))
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[w["end_ts"] <= H]
    ct = cluster_trades()
    ctx, cw = set(ct["tx"]), set(WALLETS.values())
    for f in sorted(OUT.glob("taker5m_day_*.parquet")):
        d = int(f.stem.split("_")[-1])
        if days and d not in days:
            continue
        pf = OUT / f"feat3_day_{d}.parquet"
        if pf.exists():
            continue
        tk = clean_day(f, ctx, cw)
        tk = tk[tk["ts"] < H]
        wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400)]
        groups = {c: g for c, g in tk.groupby("cid", sort=False)}
        empty = tk.iloc[:0]
        fr = [window_feats(win, groups.get(win.cid, empty), hft) for win in wd.itertuples(index=False)]
        pd.concat(fr, ignore_index=True).to_parquet(pf, index=False)
        print("day", d, len(wd), flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "hft":
        build_hft()
    else:
        main([int(x) for x in sys.argv[1:]] or None)
