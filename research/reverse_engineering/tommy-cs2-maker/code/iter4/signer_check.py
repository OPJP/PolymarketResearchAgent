"""Iteration 4, X52 (assumptions iter3 P6): one operator across wallets? Re-decode the V2 order `signer` (the EOA that
signs for a POLY_PROXY / Safe / deposit wallet) of the wallet, the informed pack (P4e, P93, the 3-wallet cluster
0x72aaaaf9 / 0xfe8a28be / 0x2529c68d, Pf1, Pfe, ...) and the top delay-window late makers, from a few of their
16-22 Oct transactions (publicnode eth_getTransactionByHash, decoded in memory; raw inputs not stored).
Output: results/signer_check.json  {maker: {sig_types, signers, n_orders}} and shared-signer groups.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calldata import decode_match_orders  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
RPC = "https://polygon-bor-rpc.publicnode.com"
PREFIXES = ["0x0063b23c", "0x4ebc2722", "0x93078b5d", "0x72aaaaf9", "0xfe8a28be", "0x2529c68d", "0xf1ee4842", "0x8a80528d",
            "0xddb6e624", "0xed446954", "0x5d40576b", "0x893575c7", "0x68915897", "0x758dac51", "0x2e3c40fa", "0x2005d16a",
            "0xe8e1b119", "0xfca6d645"]


def main():
    cols = ["tx", "idx", "maker", "sign_ms"]
    parts = [pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)]
    parts += [pd.read_parquet(p, columns=cols) for p in sorted((OUT / "calldata_pub").glob("*.parquet"))]
    cd = pd.concat(parts, ignore_index=True)
    full = {}
    for pfx in PREFIXES:
        m = cd[cd.maker.str.lower().str.startswith(pfx)]
        if len(m):
            full[pfx] = m.maker.iloc[0].lower()
    txs = []
    for pfx, addr in full.items():
        g = cd[cd.maker.str.lower() == addr].drop_duplicates("tx")
        txs += g.tx.sample(min(3, len(g)), random_state=1).tolist()
    txs = list(dict.fromkeys(txs))
    cli = httpx.Client(timeout=40, headers={"User-Agent": "polyrea-research"})
    info = defaultdict(lambda: {"sig_types": set(), "signers": set(), "n": 0})
    for i in range(0, len(txs), 40):
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(txs[i:i + 40])]
        for attempt in range(5):
            r = cli.post(RPC, json=body)
            if r.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            res = r.json()
            break
        for x in res:
            t = x.get("result") or {}
            d = decode_match_orders(t.get("input", ""))
            if not d:
                continue
            for o in [d["taker"]] + d["makers"]:
                k = o["maker"].lower()
                info[k]["sig_types"].add(int(o["sig_type"]))
                info[k]["signers"].add(o["signer"].lower())
                info[k]["n"] += 1
        time.sleep(0.3)
    out = {}
    for pfx, addr in full.items():
        v = info.get(addr)
        if v:
            out[pfx] = {"address": addr, "sig_types": sorted(v["sig_types"]), "signers": sorted(v["signers"]), "n_orders": v["n"],
                        "signer_is_maker": addr in v["signers"]}
    by_signer = defaultdict(list)
    for k, v in info.items():
        for s in v["signers"]:
            by_signer[s].append(k)
    shared = {s: ks for s, ks in by_signer.items() if len(set(ks)) > 1}
    res = {"wallets": out, "shared_signers_among_all_decoded_orders": shared, "txs": len(txs)}
    json.dump(res, open(RES / "signer_check.json", "w"), indent=1)
    print(json.dumps(res, indent=1)[:4000])


if __name__ == "__main__":
    main()
