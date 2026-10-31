"""Cluster co-trading on the TEST/FIT tapes: shared transactions and direct cluster-vs-cluster fills."""
import pickle, json
import numpy as np, pandas as pd
from collections import defaultdict, Counter
N = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
d = pickle.load(open("data.pkl", "rb"))
out = {}
for per in ("fit", "test"):
    t = d[per]
    tx_w = defaultdict(set); tx_roles = defaultdict(list)
    cl_usd = Counter(); vs_cluster_usd = Counter(); all_cluster_tx = set()
    for cid, full in t["full_tapes"].items():
        tk = {}
        for r in t["tapes"].get(cid, []):
            tk[r["transactionHash"]] = (r["proxyWallet"] or "").lower()
        for r in full:
            w = (r["proxyWallet"] or "").lower(); h = r["transactionHash"]
            role = "T" if tk.get(h) == w else "M"
            tx_roles[h].append((w, role, float(r["size"]) * float(r["price"])))
    shared = Counter(); direct = Counter(); n_tx = Counter(); usd_direct = Counter(); usd_total = Counter()
    for h, rows in tx_roles.items():
        cl = {w for w, _, _ in rows if w in N}
        for w in cl:
            n_tx[N[w]] += 1
            usd_total[N[w]] += sum(u for ww, _, u in rows if ww == w)
        if len(cl) >= 2:
            for a in cl:
                for b in cl:
                    if a < b:
                        shared[N[a] + "-" + N[b]] += 1
        taker = [w for w, r, _ in rows if r == "T"]
        if taker and taker[0] in N:
            makers = {w for w, r, _ in rows if r == "M" and w in N and w != taker[0]}
            if makers:
                direct[N[taker[0]] + "->" + ",".join(sorted(N[m] for m in makers))] += 1
                usd_direct[N[taker[0]]] += sum(u for w, r, u in rows if r == "T")
    out[per] = {"cluster_tx_per_wallet": dict(n_tx), "shared_tx_pairs": dict(shared), "direct_cluster_taker_vs_cluster_maker_tx": dict(direct),
                "taker_usd_filled_by_sibling_maker_share": {k: usd_direct[k] / usd_total[k] for k in usd_total}}
print(json.dumps(out, indent=1))
json.dump(out, open("selftrade.json", "w"), indent=1)
