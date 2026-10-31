"""Iteration 5, assumptions panel iter4 P1 step 4 (X58, live): at events the PACK trades without the wallet, does the
wallet pull its exposed ladder (i.e. does it see those events and choose not to take), or is it hit / blind?

Server clock, own recorder tommy_cs2_near, 10-31 14:50-18:00 UTC development block, the wallet's dev-unit CS2 markets.
For each pack taker order (pack signers, calldata_dev) with no wallet take on the same market within +-3 s: the
consumed side of the token-0 book (= the wallet's complement bids are asks there); own-size cancels (100 / 68 / 58 /
54) on that side in [sign - 300, sign) ms (before the pack signs), [sign, sign + 150) ms, [sign + 150, match) ms and
whether the wallet's maker orders were filled in the pack's tx (calldata_dev). Same for the wallet's own takes as a
reference (its pull is known to follow at +11-19 ms). Null: the same windows shifted +-7 / 13 / 23 s.
Output: results/pack_event_pulls.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OWN = (100.0, 68.0, 58.0, 54.0)
OWN0, END = 1793458232, 1793469600
SHIFTS = (-23000, -13000, -7000, 7000, 13000, 23000)


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
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
    C = E[(E.kind == "cancel") & E["size"].round(2).isin(OWN) & E.whole]
    can = {k: np.sort(g.s.to_numpy(float)) for k, g in C.groupby(["a", "side"])}
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    tk = cd[cd.idx == -1].drop_duplicates("tx").copy()
    tk["tok"] = tk.token_id.astype(str)
    tk = tk[tk.tok.isin(t0map) & (tk.sign_ms > 1.7e12) & (tk.sign_ms < 1.8e12)]
    tk["m"] = tk.tx.str.lower().map(mt)
    tk = tk[tk.m.notna() & (tk.sign_ms >= OWN0 * 1000) & (tk.sign_ms < END * 1000)].copy()
    tk["a"] = tk.tok.map(t0map)
    tk["cside"] = np.where((tk.side == 0) == (tk.tok == tk.a), "SELL", "BUY")
    pack = set(pd.read_parquet(OUT / "pack_orders.parquet", columns=["maker"]).maker.str.lower()) - {WALLET}
    pack |= {"0x72aaaaf9", "0xfe8a28be", "0x2529c68d", "0xf1ee4842", "0x93078b5d"}
    tk["mk"] = tk.maker.str.lower()
    w_t = {a: np.sort(g.sign_ms.to_numpy(float)) for a, g in tk[tk.mk == WALLET].groupby("a")}
    wm_tx = set(cd[(cd.idx >= 0) & (cd.maker == WALLET)].tx)

    def near_w(a, s):
        x = w_t.get(a)
        if x is None or len(x) == 0:
            return False
        j = np.searchsorted(x, s)
        return min(abs(x[j] - s) if j < len(x) else 1e18, abs(x[j - 1] - s) if j > 0 else 1e18) <= 3000

    groups = {"wallet_takes": tk[(tk.mk == WALLET) & (tk.side == 0)],
              "pack_takes_without_wallet": tk[(tk.mk.isin(pack) | tk.mk.str[:10].isin(pack)) & (tk.side == 0)]}
    groups["pack_takes_without_wallet"] = groups["pack_takes_without_wallet"][[not near_w(r.a, r.sign_ms) for r in groups["pack_takes_without_wallet"].itertuples()]]
    res = {}
    for nm, g in groups.items():
        wins = {"[-300,0)": (-300, 0), "[0,150)": (0, 150), "[150,match)": (150, None)}
        out = {"n": int(len(g)), "wallet_maker_hit_in_tx": round(float(g.tx.isin(wm_tx).mean()), 3)}
        for wn, (lo, hi) in wins.items():
            hit, null = [], []
            for r in g.itertuples():
                x = can.get((r.a, r.cside))
                hh = (r.m - r.sign_ms) if hi is None else hi
                if x is None:
                    hit.append(0); null.extend([0] * len(SHIFTS)); continue
                hit.append(int(np.searchsorted(x, r.sign_ms + hh) - np.searchsorted(x, r.sign_ms + lo) > 0))
                for sh in SHIFTS:
                    null.append(int(np.searchsorted(x, r.sign_ms + sh + hh) - np.searchsorted(x, r.sign_ms + sh + lo) > 0))
            out[wn] = {"rate": round(float(np.mean(hit)), 3), "null": round(float(np.mean(null)), 3),
                       "ratio": round(float(np.mean(hit) / max(np.mean(null), 1e-9)), 2)}
        res[nm] = out
    (RES / "pack_event_pulls.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
