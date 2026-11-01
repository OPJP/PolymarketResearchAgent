"""iteration 16, X187 step 1 (information panel I15-5): label purity of the 4h ladder sizes (600 / 400 / 300 and the
cluster's 4h table size 400) from the all-match calldata of every shared-recorder trade (clob_crypto 'x') of the BTC / ETH /
SOL 4h windows in a development span; per coin and size, non-extreme bids.
    python purity_4h.py <a> <b>"""
import collections
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code4")); sys.path.insert(0, str(HERE.parent / "code"))
import calldata as cd  # noqa: E402
import final_rule as fr  # noqa: E402
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


def main(a, b):
    import json as _j
    from polyrea.workflows.updown_study import fetch_windows
    slugs = [f"{c}-updown-4h-{s}" for c in ("btc", "eth", "sol") for s in range(a - a % 14400, b, 14400)]
    raw = fetch_windows(slugs)
    tok = {}
    for m in raw.values():
        t = _j.loads(m["clobTokenIds"]) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds")
        for x in t or []:
            tok[str(x)] = m["slug"].split("-")[0]
    hs = {}
    for r in fr._iter_live_xq(a, b, set(tok)):
        if r.get("k") == "x" and r.get("h") and str(r.get("a")) in tok:
            hs.setdefault(str(r["h"]).lower(), tok[str(r["a"])])
    print("4h windows", len(raw), "trade txs", len(hs), flush=True)
    cnt, tot, mine = collections.Counter(), collections.Counter(), collections.Counter()
    for h, tx in cd.fetch_txs(list(hs), batch=40, pause=0.15):
        d = cd.decode(tx["input"]) if tx else None
        if not d:
            continue
        coin = hs.get(h.lower())
        for m in d["makers"]:
            if m["oside"] != 0 or not m["taker_amount"]:
                continue
            sh = round(m["taker_amount"] / 1e6, 2); px = m["maker_amount"] / m["taker_amount"]
            if not (0.03 < px < 0.97):
                continue
            ours = m["maker"].lower() in W
            if ours:
                mine[f"{coin}|{sh}"] += 1
            if sh in (300.0, 400.0, 600.0, 200.0, 800.0):
                tot[f"{coin}|{sh}"] += 1; cnt[f"{coin}|{sh}"] += int(ours)
    out = {"span": [a, b], "txs": len(hs), "purity": {k: [round(cnt[k] / tot[k], 3), tot[k]] for k in sorted(tot)},
           "cluster_order_sizes_top": dict(mine.most_common(15))}
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / f"iter16_purity_4h_{a}_{b}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
