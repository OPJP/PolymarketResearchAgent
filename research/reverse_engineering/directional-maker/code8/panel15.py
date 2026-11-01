"""Iteration 8 (A1 / X69): clean point-in-time panels for BTC 15m windows, 2026-10-09..30 (development: BUILD < 10-27,
VALIDATE 10-27..30 aggregate only), same construction as code/panel2.py with code8/features15.py (bins [0, 900) s).
Cluster fills from the three wallets' data-api activity (BUILD file + released-lot file); a fill is a taker fill when
the 15m taker tape lists the same transaction with that wallet as the taker. Every tape row in a cluster transaction is
dropped before the features. Output .cache/re/directional-maker/p15/panel15_day_<day>.parquet.
    python code8/panel15.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from features15 import Spot, build_panel, clean_tape  # noqa: E402

H = 1792713600
T0 = 1793404800
C = ROOT / ".cache/re/directional-maker"
OUT = C / "p15"
OUT.mkdir(exist_ok=True)
WALLETS = {"bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
           "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


def cluster_trades() -> pd.DataFrame:
    fr = []
    for name, addr in WALLETS.items():
        for f, lo, hi in ((C / f"activity_{name}.parquet", 0, H), (C / "exam" / f"activity_{name}.parquet", H, T0)):
            a = pd.read_parquet(f)
            a = a[(a["type"] == "TRADE") & (a["timestamp"] >= lo) & (a["timestamp"] < hi)]
            fr.append(pd.DataFrame({"wallet": addr, "tx": a["transactionHash"], "token_id": a["asset"].astype(str),
                                    "ts": a["timestamp"].astype(np.int64), "side": a["side"], "price": a["price"].astype(float),
                                    "shares": a["size"].astype(float), "cid": a["conditionId"]}))
    return pd.concat(fr, ignore_index=True)


def main() -> None:
    w = pd.read_parquet(C / "t15" / "windows_15m.parquet")
    w = w[w["end_ts"] <= T0]
    w["up_token"] = w["up_token"].astype(str)
    w["down_token"] = w["down_token"].astype(str)
    ct = cluster_trades()
    ctx = set(ct["tx"])
    cw = set(WALLETS.values())
    sp1 = pd.read_parquet(C / "spot_btc_1s.parquet")
    sp2 = pd.read_parquet(C / "exam" / "spot_btc_1s.parquet")
    spd = pd.concat([sp1, sp2]).drop_duplicates("sec").sort_values("sec")
    spd = spd[spd["sec"] < T0]
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    toks = set(w["up_token"]) | set(w["down_token"])
    buys = ct[(ct["side"] == "BUY") & ct["token_id"].isin(toks)]
    allfills = []
    for f in sorted((C / "t15").glob("taker15m_day_*.parquet")):
        d = int(f.stem.split("_")[-1])
        pf = OUT / f"panel15_day_{d}.parquet"
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
              "panel", p.shape, "pos", round(float(p["y"].mean()), 4), flush=True)
    pd.concat(allfills, ignore_index=True).to_parquet(OUT / "cluster_btc15m_fills.parquet", index=False)


if __name__ == "__main__":
    main()
