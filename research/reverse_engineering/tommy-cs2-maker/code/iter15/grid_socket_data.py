"""X204 / X210 data step: the sports socket's per-round score clock and the operator accounts' fills on the GRID (and
other operator) CS2 events of the development blocks 10-31 12-18 and 11-01 06-12 (development units only; every
record is clamped to the end of the unit's development block, as the recordings are).

Outputs (.cache/re/tommy-cs2-maker/iter15/):
  socket_rounds.parquet  per (event, receive ms): parsed score string (round score of the current map | map score),
                         period, home / away team names
  op_trades.parquet      data-api trades (makers and takers) of the events' match / map markets in [gs - 1 h, block end)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
import sealed  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker/iter15"
OUT.mkdir(parents=True, exist_ok=True)
BLOCKS = [(1793448000, 1793469600), (1793512800, 1793534400)]  # 10-31 12-18, 11-01 06-12 (development)
EVENTS = ["cs2-fokus-baks-2026-10-31", "cs2-jjh-bmb-2026-10-31", "cs2-skr2-for10-2026-10-31", "cs2-lowcor1-tdp-2026-10-31",
          "cs2-1win-5s-2026-10-31", "cs2-bca-pha-2026-11-01", "cs2-jjh-mzp-2026-11-01"]


def main():
    u = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/universe_t0.parquet")
    u = u[u.event_slug.isin(EVENTS)].copy()
    egs = u.groupby("event_slug").gs_ts.transform("min")
    u["egs"] = egs
    for e, g in u.groupby("event_slug"):
        assert not sealed.is_sealed(float(g.egs.iloc[0]), "tommy-cs2-maker"), e
    ps = {int(p): e for e, p in zip(u.event_slug, u.pandascore_id) if pd.notna(p)}
    rows = []
    for a0, b0 in BLOCKS:
      for a in range(a0, b0, 900):  # 15-min slices: a corrupt hour file only loses its own slice
        b = min(a + 900, b0)
        try:
            for rec in live.iter_live("sports", a, b):
                try:
                    m = json.loads(rec["m"])
                except Exception:  # noqa: BLE001
                    continue
                gid = m.get("gameId")
                if gid in ps:
                    rows.append({"event": ps[gid], "t": rec["t"], "score": m.get("score"), "period": m.get("period"),
                                 "home": m.get("homeTeam"), "away": m.get("awayTeam"), "status": m.get("status")})
        except Exception as ex:  # noqa: BLE001
            print("iter_live stop", repr(ex)[:120])
    s = pd.DataFrame(rows)
    s.to_parquet(OUT / "socket_rounds.parquet", index=False)
    print("socket rows", len(s), s.groupby("event").size().to_dict() if len(s) else {})
    pm = PolymarketData()
    tr = []
    for r in u.itertuples():
        blk = [b for a, b in BLOCKS if a <= r.egs < b][0]
        rws, _, _ = pm.market_trades(r.cid, start=int(r.gs_ts) - 3600, end=int(blk) - 1, taker_only=False)
        tk, _, _ = pm.market_trades(r.cid, start=int(r.gs_ts) - 3600, end=int(blk) - 1, taker_only=True)
        tkh = {(x["transactionHash"], str(x.get("proxyWallet", "")).lower()) for x in tk}
        for x in rws:
            x = dict(x)
            x["cid"] = r.cid
            x["event"] = r.event_slug
            x["smt"] = r.smt
            x["outcomes"] = r.outcomes
            x["is_taker_row"] = (x["transactionHash"], str(x.get("proxyWallet", "")).lower()) in tkh
            tr.append(x)
    t = pd.DataFrame(tr)
    keep = [c for c in ["proxyWallet", "side", "asset", "outcomeIndex", "size", "price", "timestamp", "transactionHash", "cid",
                        "event", "smt", "outcomes", "is_taker_row"] if c in t.columns]
    t = t[keep]
    t["proxyWallet"] = t.proxyWallet.str.lower()
    t.to_parquet(OUT / "op_trades.parquet", index=False)
    OPS = {"0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2": "wallet", "0xd2bb94594762beda042e596598800d83f781bd8e": "d2bb",
           "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14": "7d67", "0x10d79cc72df76ea3d6bdc2d54f41dbcbbb18bbf6": "10d7",
           "0x52661b8e13158f23d94a9e8302ab0295704c22ac": "5266", "0x671190333b064b0899b4ac1aec86744b1f82885b": "6711"}
    t["op"] = t.proxyWallet.map(OPS)
    print(t[t.op.notna()].groupby(["event", "op", "is_taker_row"]).size())


if __name__ == "__main__":
    main()
