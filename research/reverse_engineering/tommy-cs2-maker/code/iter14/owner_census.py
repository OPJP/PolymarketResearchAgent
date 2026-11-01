"""X203 (assumptions panel iter-13 P5), steps 1 and 4 (first pass): find the operator's other processes by key
fingerprint, not by co-signing time. Every signature-type-3 address with >= 50 orders (maker or taker) in the decoded
calldata of the wallet's markets (calldata_all + calldata_pub, all before H) and in the operator's sibling calldata
(sib7d67*, sib_grid, sib5266_sport): eth_getCode at latest (read-only chain state, not tied to any market unit) ->
owner = the last 20 bytes of the 125- or 146-byte deposit-wallet proxy (the wallet / 0x7d67f01d use 125 bytes, 0x52661b8e / 0x67119033 146) -> the
owner's code: EIP-7702 designator 0xef0100 + delegate. The operator's three known owner keys delegate to
0x63c0c19a282a1b52b07dd5a65b58948a07dae32b; other bots' owners checked so far are plain EOAs.
For every deposit wallet whose owner delegates to that address: its orders in the decoded calldata (BUY share, whole
cents, band, sizes, maker share, markets). Output: results/owner_census.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
RPC = "https://polygon-bor-rpc.publicnode.com"
DELEGATE = "0x63c0c19a282a1b52b07dd5a65b58948a07dae32b"
KNOWN = {"0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2": "wallet", "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14": "BACKTESTEOCARAIO1",
         "0x52661b8e13158f23d94a9e8302ab0295704c22ac": "TommyLeePeeecan", "0x671190333b064b0899b4ac1aec86744b1f82885b": "0x67119033"}


def batch_code(cli, addrs):
    out = {}
    for i in range(0, len(addrs), 40):
        part = addrs[i:i + 40]
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getCode", "params": [a, "latest"]} for j, a in enumerate(part)]
        for attempt in range(6):
            try:
                r = cli.post(RPC, json=body, timeout=40)
                res = r.json()
                if isinstance(res, list):
                    for x in res:
                        out[part[x["id"]]] = x.get("result") or ""
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2 + 2 * attempt)
        time.sleep(0.3)
    return out


def main():
    cols = ["tx", "idx", "maker", "side", "price", "shares", "sig_type", "token_id"]
    parts = [pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)]
    for d in ["calldata_pub", "sib7d67/calldata", "sib7d67_sep/calldata", "sib7d67_jun/calldata", "sib_grid/calldata", "sib5266_sport/calldata"]:
        p = OUT / d
        if p.exists():
            for f in sorted(p.glob("*.parquet")):
                try:
                    parts.append(pd.read_parquet(f, columns=cols))
                except Exception:  # noqa: BLE001
                    pass
    c = pd.concat(parts, ignore_index=True).drop_duplicates(["tx", "idx"])
    c["maker"] = c.maker.str.lower()
    c = c[c.sig_type == 3]
    cnt = c.groupby("maker").size()
    addrs = sorted(cnt[cnt >= 50].index)
    cli = httpx.Client(headers={"User-Agent": "polyrea-research"})
    code = batch_code(cli, addrs)
    owner = {a: "0x" + x[-40:] for a, x in code.items() if x and (len(x) - 2) // 2 in (125, 146)}
    oc = batch_code(cli, sorted(set(owner.values())))
    deleg = {o: ("0x" + x[8:48] if x.startswith("0xef0100") else ("eoa" if x in ("0x", "") else "contract")) for o, x in oc.items()}
    rows = []
    for a in addrs:
        o = owner.get(a)
        rows.append({"addr": a, "orders": int(cnt[a]), "proxy125": a in owner, "owner": o, "owner_kind": deleg.get(o) if o else None})
    X = pd.DataFrame(rows)
    out = {"addresses_ge50": int(len(X)), "proxy125": int(X.proxy125.sum()),
           "owner_kinds": X.owner_kind.map(lambda k: "delegate_operator" if k == DELEGATE else (k if k in ("eoa", "contract", None) else "delegate_other")).value_counts(dropna=False).to_dict(),
           "other_delegates": X[X.owner_kind.notna() & ~X.owner_kind.isin(["eoa", "contract", DELEGATE])].owner_kind.value_counts().head(10).to_dict()}
    op = X[X.owner_kind == DELEGATE]
    det = []
    for r in op.itertuples():
        g = c[c.maker == r.addr]
        p = g.price.astype(float)
        det.append({"addr": r.addr, "known": KNOWN.get(r.addr, "NEW"), "owner": r.owner, "orders": int(len(g)),
                    "maker_share": round(float((g.idx >= 0).mean()), 3), "buy_share": round(float((g.side == 0).mean()), 3),
                    "whole_cents": round(float((np.abs(p * 100 - np.round(p * 100)) < 1e-6).mean()), 3),
                    "band": round(float(((p >= 0.05 - 1e-9) & (p <= 0.95 + 1e-9)).mean()), 3),
                    "sizes": {str(k): int(v) for k, v in g.shares.round(0).value_counts().head(5).items()}, "tokens": int(g.token_id.nunique())})
    out["operator_delegate_accounts"] = det
    out["new_candidates"] = [d for d in det if d["known"] == "NEW"]
    (RES / "owner_census.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1)[:3000])


if __name__ == "__main__":
    main()
