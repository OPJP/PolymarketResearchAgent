"""Iteration 5, assumptions panel iter4 P2 step 3 (X60): is there a LEAK of pending (1-s delayed) taker orders?

If some makers could see a taker order while it waits in the in-play delay queue, their cancels would cluster right
after the order ARRIVES at the engine, whoever the taker is (retail included). Arrival a = server match time - 1,000 ms
(the delay) - processing; the window [m - 1,045, m - 985] ms covers the per-signer calibration (match - sign = 1,034 -
1,052 ms for fast signers) and the processing uncertainty. Server clock (record field s), own recorder tommy_cs2_near,
10-31 14:50-18:00 UTC development block, the wallet's dev-unit CS2 markets (level_events_dev.parquet from X49).

Counted: non-own cancels (level decreases with no trade within 150 ms, sizes other than 100 / 68 / 58 / 54) on the side
the taker order consumes, in the arrival window; also in [m - 985, m - 50] (the rest of the delay) per 100 ms.
Classes: wallet takes; pack (the 9 pack signers + the 3-wallet cluster + P93 / Pf1); retail = takers with <= 20 taker
txs in these markets whose order is > 3 s from any wallet / pack take in the market; other.
Null: the same windows shifted by +-7, +-13, +-23 s (same market and side).
Output: results/leak_control.json
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

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OWN_SIZES = (100.0, 68.0, 58.0, 54.0)
OWN0, END = 1793458232, 1793469600
SHIFTS = (-23000, -13000, -7000, 7000, 13000, 23000)


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    # match times by tx hash from the recorder's trade records (server clock)
    mt = {}
    h = int(OWN0 // 3600 * 3600)
    while h < END:
        try:
            for r in live.iter_live("tommy_cs2_near", max(h, OWN0), min(h + 3600, END)):
                if r.get("k") == "x" and str(r.get("a")) in t0map and r.get("h"):
                    hh = str(r["h"]).lower()
                    mt[hh] = min(mt.get(hh, 1e18), int(r["s"]))
        except Exception as e:  # noqa: BLE001
            print("feed stopped", type(e).__name__, flush=True)
        h += 3600
    E = pd.read_parquet(OUT / "level_events_dev.parquet")
    C = E[(E.kind == "cancel") & (~E["size"].round(2).isin(OWN_SIZES))]
    can = {k: np.sort(g.s.to_numpy(float)) for k, g in C.groupby(["a", "side"])}
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    tk = cd[cd.idx == -1].drop_duplicates("tx").copy()
    tk["tok"] = tk.token_id.astype(str)
    tk = tk[tk.tok.isin(t0map)]
    tk["m"] = tk.tx.str.lower().map(mt)
    tk = tk[tk.m.notna() & (tk.m >= OWN0 * 1000) & (tk.m < END * 1000)].copy()
    tk["a"] = tk.tok.map(t0map)
    is0 = tk.tok == tk.a
    buy = tk.side == 0
    tk["cside"] = np.where(buy == is0, "SELL", "BUY")  # consumed side of the token-0 book
    pack = set(pd.read_parquet(OUT / "pack_orders.parquet", columns=["maker"]).maker.str.lower()) - {WALLET}
    pack |= {"0x72aaaaf9", "0xfe8a28be", "0x2529c68d", "0xf1ee4842", "0x93078b5d"}
    tk["mk"] = tk.maker.str.lower()
    cnt = tk.mk.value_counts()
    inf = tk[(tk.mk == WALLET) | tk.mk.isin(pack) | tk.mk.str[:10].isin(pack)]
    inf_t = {a: np.sort(g.m.to_numpy(float)) for a, g in inf.groupby("a")}

    def near_inf(a, m):
        x = inf_t.get(a)
        if x is None or len(x) == 0:
            return False
        j = np.searchsorted(x, m)
        d = min(abs(x[j] - m) if j < len(x) else 1e18, abs(x[j - 1] - m) if j > 0 else 1e18)
        return d <= 3000

    def cls(r):
        if r.mk == WALLET:
            return "wallet"
        if r.mk in pack or r.mk[:10] in pack:
            return "pack"
        if cnt.get(r.mk, 0) <= 20 and not near_inf(r.a, r.m):
            return "retail"
        return "other"

    tk["cls"] = [cls(r) for r in tk.itertuples()]
    windows = {"arrival_[-1045,-985]": (-1045, -985)}
    for k in range(0, 9):
        windows[f"delay_[{-985 + 100 * k},{-885 + 100 * k}]"] = (-985 + 100 * k, -885 + 100 * k)
    res = {"n_takes": tk.cls.value_counts().to_dict(), "classes": {}}
    for c, g in tk.groupby("cls"):
        out = {}
        for wn, (lo, hi) in windows.items():
            hit = []
            null = []
            for r in g.itertuples():
                x = can.get((r.a, r.cside))
                if x is None:
                    hit.append(0)
                    null.extend([0] * len(SHIFTS))
                    continue
                n = np.searchsorted(x, r.m + hi) - np.searchsorted(x, r.m + lo)
                hit.append(int(n > 0))
                for sh in SHIFTS:
                    nn = np.searchsorted(x, r.m + sh + hi) - np.searchsorted(x, r.m + sh + lo)
                    null.append(int(nn > 0))
            hit, null = np.array(hit), np.array(null)
            out[wn] = {"rate": round(float(hit.mean()), 4), "null": round(float(null.mean()), 4),
                       "ratio": round(float(hit.mean() / max(null.mean(), 1e-9)), 2), "n": int(len(hit))}
        res["classes"][c] = out
    # also: wallet takes, window relative to its SIGNING (the X49 window), for comparison
    w = tk[tk.cls == "wallet"]
    sg = []
    for r in w.itertuples():
        x = can.get((r.a, r.cside))
        if x is None or not (1.7e12 < r.sign_ms < 1.8e12):
            continue
        sg.append((r.m - r.sign_ms, int(np.searchsorted(x, r.sign_ms + 15) - np.searchsorted(x, r.sign_ms + 3) > 0)))
    if sg:
        res["wallet_match_minus_sign_ms_p10_p50_p90"] = [round(float(v), 1) for v in np.percentile([s[0] for s in sg], [10, 50, 90])]
        res["wallet_noown_cancel_in_sign+[3,15]ms"] = round(float(np.mean([s[1] for s in sg])), 4)
    (RES / "leak_control.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1)[:5000])


if __name__ == "__main__":
    main()
