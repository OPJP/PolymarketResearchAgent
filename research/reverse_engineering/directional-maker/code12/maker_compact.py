"""Iteration 12: compact the maker-row tapes (it12/makers/m_<start>.parquet, 1,056 windows) into one table of maker rows
with integer wallet codes: it12/maker_rows.parquet (st, ts, wid, side_buy, price, size, tx8, is_up) and
it12/maker_wallet_codes.parquet; taker rows (marked with the taker-only tape) are dropped. Deletes the per-window files
when the table is written (the raw responses stay in the shared HTTP cache).
    python code12/maker_compact.py
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"
LOT0 = 1792713600


def main():
    W = pd.concat([pd.read_parquet(C / "windows_5m.parquet", columns=["cid", "up_token"]),
                   pd.read_parquet(C / "exam" / "windows_5m.parquet", columns=["cid", "up_token"])]).drop_duplicates("cid").set_index("cid")
    fs = sorted(glob.glob(str(C / "it12" / "makers" / "m_*.parquet")))
    by_day = {}
    for f in fs:
        st = int(Path(f).stem.split("_")[1])
        by_day.setdefault(st // 86400 * 86400, []).append((st, f))
    codes = {}
    out = []
    ntak = 0
    for day, lst in sorted(by_day.items()):
        tf = (C / "exam" / f"taker5m_day_{day}.parquet") if day >= LOT0 else (C / f"taker5m_day_{day}.parquet")
        T = pd.read_parquet(tf, columns=["cid", "tx", "wallet", "asset", "side"])
        T["k"] = T.tx.str.lower() + "|" + T.wallet.str.lower() + "|" + T.asset.astype(str) + "|" + T.side.astype(str)
        TK = {c: set(g.k) for c, g in T.groupby("cid")}
        del T
        for st, f in lst:
            d = pd.read_parquet(f)
            if d.empty:
                continue
            keys = TK.get(d.cid.iloc[0], set())
            pw = d.proxyWallet.str.lower()
            k = d.transactionHash.str.lower() + "|" + pw + "|" + d.asset.astype(str) + "|" + d.side.astype(str)
            tk = np.fromiter((x in keys for x in k), dtype=bool, count=len(k))
            ntak += int(tk.sum())
            d = d[~tk]
            pw = pw[~tk]
            wid = np.array([codes.setdefault(w, len(codes)) for w in pw], dtype=np.int32)
            up = str(W.at[d.cid.iloc[0], "up_token"]) if d.cid.iloc[0] in W.index else ""
            out.append(pd.DataFrame({"st": np.int64(st), "ts": d.timestamp.astype("int64").to_numpy(), "wid": wid,
                                     "buy": (d.side == "BUY").to_numpy(), "price": d.price.astype("float32").to_numpy(),
                                     "size": d["size"].astype("float32").to_numpy(), "tx8": d.transactionHash.str[2:18].to_numpy(),
                                     "is_up": (d.asset.astype(str) == up).to_numpy()}))
        print(pd.to_datetime(day, unit="s").date(), len(lst), flush=True)
    M = pd.concat(out, ignore_index=True)
    M.to_parquet(C / "it12" / "maker_rows.parquet", index=False)
    pd.DataFrame({"pw": list(codes), "wid": list(codes.values())}).to_parquet(C / "it12" / "maker_wallet_codes.parquet", index=False)
    print("rows", len(M), "taker rows dropped", ntak, "wallets", len(codes), flush=True)
    for f in fs:
        Path(f).unlink()
    print("deleted", len(fs))


if __name__ == "__main__":
    main()
