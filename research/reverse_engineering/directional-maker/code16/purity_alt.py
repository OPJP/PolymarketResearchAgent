"""iteration 16, X189 step 1 (mechanics panel P4): label purity of the alt families' configured sizes. All-match calldata
of every trade transaction recorded in dw_clob ('x' records with tx hash) in a development slice; for each filled maker
BUY order with an exact size, the share that belongs to the cluster, per family (from the window slug of the trade) and
size, non-extreme bids (0.03-0.97).
    python purity_alt.py <a> <b>"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code4"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import calldata as cd  # noqa: E402
import live  # noqa: E402

W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
SIZES = {"eth-5m": (50.0, 150.0), "sol-5m": (50.0, 100.0), "xrp-5m": (10.0, 50.0), "bnb-5m": (10.0, 40.0), "doge-5m": (10.0, 40.0),
         "eth-15m": (30.0,), "sol-15m": (30.0,), "xrp-15m": (10.0, 30.0), "bnb-15m": (10.0,), "doge-15m": (10.0,)}


def main(a, b):
    fam_of = {}
    for r in live.iter_live("dw_clob", a, b):
        if r.get("k") == "x" and r.get("h") and r.get("w"):
            p = r["w"].split("-")
            fam_of.setdefault(str(r["h"]).lower(), f"{p[0]}-{p[2]}")
    hs = list(fam_of)
    print("trade txs", len(hs), flush=True)
    cnt, tot, anyc = collections.Counter(), collections.Counter(), collections.Counter()
    for h, tx in cd.fetch_txs(hs, batch=40, pause=0.15):
        d = cd.decode(tx["input"]) if tx else None
        if not d:
            continue
        fam = fam_of.get(h.lower())
        for m in d["makers"]:
            if m["oside"] != 0 or not m["taker_amount"]:
                continue
            sh = round(m["taker_amount"] / 1e6, 2)
            px = m["maker_amount"] / m["taker_amount"]
            if not (0.03 < px < 0.97):
                continue
            mine = m["maker"].lower() in W
            if mine:
                anyc[f"{fam}|{sh}"] += 1
            if sh in SIZES.get(fam, ()):
                key = f"{fam}|{sh}"
                tot[key] += 1
                cnt[key] += int(mine)
    out = {"span": [a, b], "txs": len(hs), "purity": {k: [round(cnt[k] / tot[k], 3), tot[k]] for k in sorted(tot)},
           "cluster_order_sizes_top": dict(anyc.most_common(20))}
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / f"iter16_purity_alt_{a}_{b}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
