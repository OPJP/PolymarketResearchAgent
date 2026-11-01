"""Examiner: on-chain check of the labels. A seeded random sample of holdout BTC 5m cluster BUY fills (data-api
activity, role inferred from the taker tape as the rule does) is matched to Polygon receipts (OrderFilled, decoded by
polyrea.adapters.chain.decode_fills): does the wallet's order appear, with the same token, side BUY, shares and the
same maker/taker role?

python exam_onchain.py N SEED   -> results/exam_onchain_roles.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.chain import PolygonChain, decode_fills  # noqa: E402

EX = ROOT / ".cache/re/directional-maker/exam"
RES = HERE.parent / "results"


def main(n: int, seed: int) -> None:
    f = pd.read_parquet(EX / "fills_holdout.parquet")
    s = f.sample(n=min(n, len(f)), random_state=seed)
    chain = PolygonChain()
    rec, _ = chain.receipts(s["txh"].tolist())
    out = {"n": int(len(s)), "receipt_found": 0, "order_found": 0, "role_agree": 0, "shares_agree": 0,
           "tape_role_counts": s["role"].value_counts().to_dict(), "disagree": []}
    for r in s.itertuples(index=False):
        rc = rec.get(r.txh)
        if not rc:
            continue
        out["receipt_found"] += 1
        fl = [x for x in decode_fills(rc) if x.maker == r.wallet and x.token_id == r.token_id and x.side == "BUY"]
        if not fl:
            continue
        out["order_found"] += 1
        roles = {x.role_of(r.wallet) for x in fl}
        sh = sum(x.shares for x in fl)
        out["shares_agree"] += int(abs(sh - r.shares) <= 0.005 * max(r.shares, 1))
        if r.role in roles and len(roles) == 1:
            out["role_agree"] += 1
        else:
            out["disagree"].append({"tx": r.txh, "tape_role": r.role, "chain_roles": sorted(x for x in roles if x)})
    print(json.dumps(out, indent=1))
    (RES / "exam_onchain_roles.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
