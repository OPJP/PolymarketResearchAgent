"""iteration 15 (X170 on the current block): purity of the exact-size maker orders filled in BTC 5m/15m windows of
11-01 07:00-<end> (all-match calldata of every trade transaction recorded in dm_clob_raw 'x'), by size class and bid
region: the share of exact-500 / 100 / 250 / 1000 filled maker orders that belong to the cluster.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code15/purity_today.py 1793516400 <end>
"""
import collections
import json
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code4")); sys.path.insert(0, str(HERE.parent / "code14"))
import calldata as cd  # noqa: E402
from lagged_quote import live  # noqa: E402

W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


def main(a, b):
    hs = []
    for h in range(a - a % 3600, b, 3600):
        try:
            for r in live.iter_live("dm_clob_raw", max(h, a), min(h + 3600, b)):
                if r.get("k") == "x" and r.get("h"):
                    hs.append(str(r["h"]).lower())
        except (zlib.error, EOFError, OSError):
            pass
    hs = list(dict.fromkeys(hs))
    print("trade txs", len(hs), flush=True)
    cnt = collections.Counter(); tot = collections.Counter()
    for h, tx in cd.fetch_txs(hs, batch=40, pause=0.15):
        d = cd.decode(tx["input"]) if tx else None
        if not d:
            continue
        for m in d["makers"]:
            if m["oside"] != 0 or not m["taker_amount"]:
                continue
            sh = round(m["taker_amount"] / 1e6, 2); px = m["maker_amount"] / m["taker_amount"]
            if sh not in (62.0, 100.0, 250.0, 500.0, 1000.0):
                continue
            reg = "extreme" if (px <= 0.03 or px >= 0.97) else "mid"
            key = f"{int(sh)}_{reg}"
            tot[key] += 1
            if m["maker"].lower() in W:
                cnt[key] += 1
    out = {"span": [a, b], "txs": len(hs), "purity": {k: [round(cnt[k] / tot[k], 3), tot[k]] for k in sorted(tot)}}
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / f"iter15_purity_{a}_{b}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
