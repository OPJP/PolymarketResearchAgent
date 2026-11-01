"""Lead from same_process_gate.json: 0x68915897 and 0x5d40576b co-sign with the wallet at 0-5 ms inside the wallet's own
10-31 txs (same market). Are they the operator's process (CROSS-market co-signing, the one-process test) and do they quote
the 10-31 GRID books? Development only: their data-api activity in the 10-31 12-18 block (clamped), their trade txs
decoded (publicnode), co-signing with the wallet's 10-31 orders on OTHER markets at 0-5 ms vs 5-50 ms, design, and the
events they traded. Output: results/grid_candidates.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grid_socket_clock as g1  # noqa: E402
import same_process_gate as S  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

RES = g1.RES
W = S.W
A, B = 1793448000, 1793469600  # 10-31 12-18 (development)
CANDS = {"0x68915897": "0x6891589732cf8beaaf424b117d5c5c20919f6bb9", "0x5d40576b": "0x5d40576be2e9c61d283f4fd80d7a5ccf2331ba95"}


def main():
    pm = PolymarketData()
    wal = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/calldata_dev.parquet")
    wal = wal[(wal.maker.str.lower() == W) & (wal.sign_ms > 1.7e12)].drop_duplicates(["salt", "sign_ms"])
    wtok = wal.token_id.astype(str).to_numpy()
    wms = wal.sign_ms.to_numpy(float)
    out = {}
    for name, a in CANDS.items():
        rows, _, _ = pm.activity(a, start=A, end=B - 1)
        act = pd.DataFrame(rows)
        if act.empty:
            out[name] = {"activity": 0}
            continue
        tr = act[act["type"] == "TRADE"].copy()
        # development units only: keep rows whose event is in the listing projection and started in a development period
        sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
        import sealed as _sealed
        u = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/universe_t0.parquet")
        egs = u.groupby("event_slug").gs_ts.min().to_dict()
        col = "eventSlug" if "eventSlug" in tr else "slug"
        g_ = tr[col].map(egs)
        keep = g_.notna() & g_.map(lambda x: (not _sealed.is_sealed(float(x), "tommy-cs2-maker")) if x == x else False).astype(bool)
        tr = tr[keep]
        ev = tr.groupby(col).size().sort_values(ascending=False).head(12).to_dict() if len(tr) else {}
        txs = tr.transactionHash.dropna().unique()
        cd = g1.decode(list(txs[:800]))
        c = cd[(cd.maker.str.lower() == a) & (cd.sign_ms > 1.7e12)].drop_duplicates(["salt", "sign_ms"])
        c = c[(c.sign_ms / 1000 >= A) & (c.sign_ms / 1000 < B)]
        ctok = c.token_id.astype(str).to_numpy()
        cms = c.sign_ms.to_numpy(float)
        # cross-market: wallet orders on tokens the candidate never traded in this block (other markets)
        other = ~np.isin(wtok, np.unique(ctok))
        cs_x = S.cosign(cms, None, wms[other], None)
        same = ~other
        cs_s = S.cosign(cms, None, wms[same], None) if same.any() else None
        out[name] = {"trades": int(len(tr)), "txs": int(len(txs)), "orders_decoded_block": int(len(c)), "events_top": ev,
                     "cosign_cross_market": cs_x, "cosign_same_tokens": cs_s, "design": S.design(c) if len(c) else None}
        print(name, json.dumps({k: out[name][k] for k in ("trades", "orders_decoded_block", "cosign_cross_market", "cosign_same_tokens")}), flush=True)
    (RES / "grid_candidates.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str)[:3500])


if __name__ == "__main__":
    main()
