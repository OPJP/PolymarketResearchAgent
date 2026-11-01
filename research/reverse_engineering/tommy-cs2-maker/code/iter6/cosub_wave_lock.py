"""Iteration 6, follow-up of X78 for the co-timed maker 0x51dbdd2b (C1 / X65): at the pack's takes without a wallet
take, is 0x51dbdd2b's first cancel locked to the event (before the public wave: a more complete feed than the wallet's)
or to the wave (like the wallet)?

BUILD-live (10-31 14:50-18:00), server clock, level_events_dev.parquet. 0x51dbdd2b's cancels by a loose size
fingerprint: the sizes of its maker orders in calldata_dev that no other maker uses there (distinctive sizes). The
wave w' = the first cancel on the consumed side in (p, match) that is neither the wallet's (own sizes) nor 0x51dbdd2b's.
For its own first cancel c in [p - 300, match): shares before w', medians of c - p and c - w', for pack-only events
and for the wallet's takes (reference: iteration 4 found +9-13 ms after the wallet's signing in some takes).
Output: results/cosub_wave_lock.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wave_lock as W  # noqa: E402

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
COSUB = "0x51dbdd2b19427dc8e88bb15a4046a38d8427f9b3"
WALLET = W.WALLET


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    mt = W.match_times(t0map)
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    cd["tok"] = cd.token_id.astype(str)
    cd["a"] = cd.tok.map(t0map)
    mk = cd[(cd.idx >= 0) & cd.a.notna()].copy()
    mk["sz"] = mk.shares.round(2)
    own_sizes = {a: set(g[g.maker == WALLET].sz) | {100.0} for a, g in mk.groupby("a")}
    cos = mk[mk.maker.str.lower() == COSUB]
    others = mk[(mk.maker.str.lower() != COSUB)]
    other_sizes = set(others.sz)
    cos_sizes = {a: set(g.sz) - other_sizes for a, g in cos.groupby("a")}
    E = pd.read_parquet(OUT / "level_events_dev.parquet")
    E = E[E.kind == "cancel"].copy()
    E["sz"] = E["size"].round(2)
    E["own"] = [bool(w) and (z in own_sizes.get(a, {100.0})) for a, z, w in zip(E.a, E.sz, E.whole)]
    E["cos"] = [z in cos_sizes.get(a, set()) for a, z in zip(E.a, E.sz)]
    cos_c = {k: np.sort(g.s.to_numpy(float)) for k, g in E[E.cos & ~E.own].groupby(["a", "side"])}
    oth_c = {k: np.sort(g.s.to_numpy(float)) for k, g in E[~E.cos & ~E.own].groupby(["a", "side"])}
    tk = cd[cd.idx == -1].drop_duplicates("tx").copy()
    tk = tk[tk.a.notna() & (tk.sign_ms > 1.7e12) & (tk.sign_ms < 1.8e12)]
    tk["m"] = tk.tx.str.lower().map(mt)
    tk = tk[tk.m.notna() & (tk.sign_ms >= W.OWN0 * 1000) & (tk.sign_ms < W.END * 1000)].copy()
    tk["cside"] = np.where((tk.side == 0) == (tk.tok == tk.a), "SELL", "BUY")
    pack = set(pd.read_parquet(OUT / "pack_orders.parquet", columns=["maker"]).maker.str.lower()) - {WALLET}
    pack |= {"0x72aaaaf9", "0xfe8a28be", "0x2529c68d", "0xf1ee4842", "0x93078b5d"}
    tk["mkr"] = tk.maker.str.lower()
    is_pack = tk.mkr.isin(pack) | tk.mkr.str[:10].isin(pack)
    w_t = {a: np.sort(g.sign_ms.to_numpy(float)) for a, g in tk[tk.mkr == WALLET].groupby("a")}
    groups = {"wallet_takes": tk[(tk.mkr == WALLET) & (tk.side == 0)]}
    po = tk[is_pack & (tk.side == 0)]
    groups["pack_only"] = po[[W.nearest_gap(w_t.get(r.a), r.sign_ms) > 3000 for r in po.itertuples()]]
    res = {"cosub_distinctive_sizes_markets": {str(k)[:8]: sorted(v)[:10] for k, v in cos_sizes.items()},
           "cosub_cancels_fingerprinted": int(E.cos.sum())}
    for nm, g in groups.items():
        rows = []
        for r in g.itertuples():
            k = (r.a, r.cside)
            p, m = float(r.sign_ms), float(r.m)
            c = W.first_after(cos_c.get(k), p - 300, m)
            w = W.first_after(oth_c.get(k), p, m)
            rows.append((p, m, c, w))
        D = pd.DataFrame(rows, columns=["p", "m", "c", "w"])
        hc = D.c.notna()
        out = {"n": int(len(D)), "share_with_cosub_cancel": round(float(hc.mean()), 3)}
        if hc.any():
            x = D[hc]
            out["c_minus_p_ms_p25_p50_p75"] = [round(float(v), 1) for v in np.percentile(x.c - x.p, [25, 50, 75])]
            xb = x[x.w.notna()]
            if len(xb):
                out["n_with_wave"] = int(len(xb))
                out["cosub_before_wave_share"] = round(float((xb.c < xb.w).mean()), 3)
                out["c_minus_w_ms_p25_p50_p75"] = [round(float(v), 1) for v in np.percentile(xb.c - xb.w, [25, 50, 75])]
        res[nm] = out
    (RES / "cosub_wave_lock.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
