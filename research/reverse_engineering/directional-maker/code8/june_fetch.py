"""directional-maker iteration 8, panel iter7 assumptions A5 (X73): the June engine signed real ms timestamps.

For a few June days, fetch the cluster's activity (data-api, cached adapter), sample TRADE transactions per wallet and
day, fetch their calldata (publicnode batched eth_getTransactionByHash via code4/calldata.py) and keep only decoded
fields of every order in the match (cluster and other makers, and the taker): salt, sign_ms, sizes, price, side,
signature type, role, block time. Development data (June 2026, long before H).

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code8/june_fetch.py 2026-06-10 2026-06-12 2026-06-16
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code4"))
import calldata as C  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache" / "re" / "directional-maker" / "june"
OUT.mkdir(parents=True, exist_ok=True)
W = {"bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
     "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
CL = set(W.values())
PER_WALLET_DAY = 1500


def main(days):
    pm = PolymarketData()
    rng = np.random.default_rng(8)
    for day in days:
        a = int(pd.Timestamp(day, tz="UTC").timestamp())
        b = a + 86400
        fo = OUT / f"orders_{day}.parquet"
        if fo.exists():
            continue
        acts = []
        for n, w in W.items():
            rows, _, _ = pm.activity(w, a, b)
            d = pd.DataFrame(rows)
            if not len(d):
                print(day, n, "no rows", flush=True)
                continue
            d["wallet"] = n
            acts.append(d)
            print(day, n, len(d), "activity rows", d.type.value_counts().to_dict(), flush=True)
        if not acts:
            continue
        act = pd.concat(acts, ignore_index=True)
        keep = [c for c in ["wallet", "type", "timestamp", "transactionHash", "slug", "side", "size", "price", "usdcSize", "asset", "outcome", "conditionId"] if c in act.columns]
        act[keep].to_parquet(OUT / f"activity_{day}.parquet", index=False)
        tr = act[act.type == "TRADE"]
        hs = []
        for n, g in tr.groupby("wallet"):
            u = g.transactionHash.drop_duplicates().to_numpy()
            if len(u) > PER_WALLET_DAY:
                u = rng.choice(u, PER_WALLET_DAY, replace=False)
            hs += list(u)
        hs = list(dict.fromkeys(hs))
        tmap = tr.drop_duplicates("transactionHash").set_index("transactionHash").timestamp.to_dict()
        smap = tr.drop_duplicates("transactionHash").set_index("transactionHash").slug.to_dict()
        print(day, "fetching", len(hs), "txs", flush=True)
        out, t0 = [], time.time()
        for k, (h, tx) in enumerate(C.fetch_txs(hs, batch=25)):
            if not tx:
                continue
            dec = C.decode(tx["input"])
            if not dec:
                out.append(dict(tx=h, role="notv2", sel=tx["input"][:10], bt=tmap.get(h)))
                continue
            for i, (role, o) in enumerate([("taker", dec["taker"])] + [("maker", m) for m in dec["makers"]]):
                out.append(dict(tx=h, bt=tmap.get(h), slug=str(smap.get(h))[:40], role=role, idx=i, maker=o["maker"].lower(),
                                cl=o["maker"].lower() in CL, salt=float(int(o["salt"])) if int(o["salt"]) < 2 ** 63 else np.nan,
                                salt_big=int(o["salt"]) >= 2 ** 63, sign_ms=o["sign_ms"], oside=o["oside"], sig=o["sig_type"],
                                mk=o["maker_amount"], tk=o["taker_amount"], token=str(o.get("token_id", ""))[-12:],
                                meta=o["metadata"][-8:], builder=o["builder"][-8:], fill=o.get("fill_amount", dec["taker_fill"] if role == "taker" else None)))
            if k and k % 2000 == 0:
                print(day, k, "txs", round(time.time() - t0), "s", flush=True)
        df = pd.DataFrame(out)
        df.to_parquet(fo, index=False)
        print(day, "orders", len(df), "cluster orders", int(df.get("cl", pd.Series(dtype=bool)).sum()), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
