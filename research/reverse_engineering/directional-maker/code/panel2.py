"""Build the iteration-2 clean panels (BUILD and VALIDATE days) from the local re-fetch.

python code/panel2.py            builds panel2_day_<day0>.parquet for every day whose tape file exists
Cluster fills come from the data-api activity of the three wallets; a cluster fill is a taker fill
when the taker tape lists the same transaction with that wallet as the taker, otherwise a maker fill.
Every tape row in a cluster transaction is dropped before the features (features2.clean_tape).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from features2 import Spot, build_panel, clean_tape  # noqa: E402

H = 1792713600
OUT = ROOT / ".cache/re/directional-maker"
WALLETS = {"bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
           "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


def cluster_trades() -> pd.DataFrame:
    fr = []
    for name, addr in WALLETS.items():
        a = pd.read_parquet(OUT / f"activity_{name}.parquet")
        a = a[(a["type"] == "TRADE") & (a["timestamp"] < H)]
        fr.append(pd.DataFrame({"wallet": addr, "tx": a["transactionHash"], "token_id": a["asset"].astype(str),
                                "ts": a["timestamp"].astype(np.int64), "side": a["side"], "price": a["price"].astype(float),
                                "shares": a["size"].astype(float), "cid": a["conditionId"]}))
    return pd.concat(fr, ignore_index=True)


def main() -> None:
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[w["end_ts"] <= H]
    ct = cluster_trades()
    ctx = set(ct["tx"])
    cw = set(WALLETS.values())
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    spd = spd[spd["sec"] < H]
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    toks = set(w["up_token"]) | set(w["down_token"])
    buys = ct[(ct["side"] == "BUY") & ct["token_id"].isin(toks)]
    allfills = []
    for f in sorted(OUT.glob("taker5m_day_*.parquet")):
        d = int(f.stem.split("_")[-1])
        pf = OUT / f"panel2_day_{d}.parquet"
        tk = pd.read_parquet(f)
        wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400)]
        tok_d = set(wd["up_token"]) | set(wd["down_token"])
        b = buys[buys["token_id"].isin(tok_d)].copy()
        taker_pairs = set(zip(tk["tx"], tk["wallet"]))
        b["role"] = ["taker" if (x, y) in taker_pairs else "maker" for x, y in zip(b["tx"], b["wallet"])]
        b["day"] = d
        allfills.append(b)
        if pf.exists():
            continue
        clean = clean_tape(tk, ctx, cw)
        mk = b[b["role"] == "maker"]
        p = build_panel(wd, sp, clean, mk)
        p.to_parquet(pf, index=False)
        print("day", d, "windows", len(wd), "tape", len(tk), "clean", len(clean), "maker fills", len(mk),
              "taker fills", int((b["role"] == "taker").sum()), "panel", p.shape, "pos", round(float(p["y"].mean()), 4), flush=True)
    pd.concat(allfills, ignore_index=True).to_parquet(OUT / "cluster_btc5m_fills.parquet", index=False)


if __name__ == "__main__":
    main()
