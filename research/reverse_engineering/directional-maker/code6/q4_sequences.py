"""Iteration 6, panel iter5 assumptions Q4 (X38): does the cluster's PnL come from continuing taker sequences?

Released lot (STUDY = 2026-10-23..26 case by case; VALIDATE = 10-27..30 aggregate only). For every data-api taker print
in a BTC 5m window: the token it sells (SELL s, or BUY of the complement = hit on s's bid); the taker's sequence = the
same taker, window and sold token with gaps <= 3 s; the print's position in it. Each cluster maker BUY fill inherits
the position of its transaction's taker print. Reported: share of cluster fills and of all bid hits by position, the
cluster's dollar PnL and return by position and by taker class (the BUILD high-frequency list code/hft_takers3.json).
    python code6/q4_sequences.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
E = ROOT / ".cache" / "re" / "directional-maker" / "exam"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88",
      "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
VAL0 = 1793059200


def main():
    w = pd.read_parquet(E / "windows_5m.parquet")
    hft = set(json.loads((HERE.parent / "code" / "hft_takers3.json").read_text()))
    hft = {h.lower() for h in (hft if isinstance(hft, (set, list)) else hft.keys())}
    up = dict(zip(w.cid, w.up_token.astype(str)))
    dn = dict(zip(w.cid, w.down_token.astype(str)))
    pay = dict(zip(w.cid, w.up_payout))
    f = pd.read_parquet(E / "fills_holdout.parquet")
    f = f[(f.role == "maker") & (f.side == "BUY")].copy()
    f["txh"] = f.txh.str.lower()
    out = {}
    allrows = []
    for p in sorted(E.glob("taker5m_day_*.parquet")):
        d = pd.read_parquet(p, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])
        d["asset"] = d.asset.astype(str)
        d["wallet"] = d.wallet.str.lower()
        d["tx"] = d.tx.str.lower()
        d = d[~d.wallet.isin(CL)]
        u = d.cid.map(up)
        dn_ = d.cid.map(dn)
        d["sold"] = np.where(d.side == "SELL", d.asset, np.where(d.asset == u, dn_, u))
        d = d.sort_values(["cid", "wallet", "sold", "ts"], kind="stable")
        g = d.groupby(["cid", "wallet", "sold"], sort=False)
        gap = g.ts.diff()
        newc = (gap.isna() | (gap > 3)).astype(int)
        d["chain"] = newc.groupby([d.cid, d.wallet, d.sold]).cumsum()
        d["pos"] = d.groupby(["cid", "wallet", "sold", "chain"]).cumcount() + 1
        d["cum_sh"] = d.groupby(["cid", "wallet", "sold", "chain"])["size"].cumsum() - d["size"]
        first = d.drop_duplicates("tx")[["tx", "pos", "cum_sh", "wallet", "size", "ts"]]
        day = int(p.stem.split("_")[-1])
        fd = f[(f.ts >= day) & (f.ts < day + 86400)].merge(first.rename(columns={"wallet": "taker", "size": "tsize", "ts": "tts"}), left_on="txh", right_on="tx", how="left")
        fd["won"] = [(pay.get(c) if str(t) == up.get(c) else 1 - pay.get(c)) if pay.get(c) is not None else np.nan for c, t in zip(fd.cid, fd.token_id.astype(str))]
        fd["pnl"] = (fd.won - fd.price) * fd.shares
        fd["usd"] = fd.price * fd.shares
        fd["half"] = "validate" if day >= VAL0 else "study"
        allrows.append(fd)
        # base rate: positions of all prints (bid hits) in this day
        bp = d.pos.clip(upper=6).value_counts(normalize=True).sort_index()
        out.setdefault("base_pos_share_by_day", {})[day] = bp.round(4).to_dict()
    F = pd.concat(allrows, ignore_index=True)
    F["pos_b"] = pd.cut(F.pos, [0, 1, 2, 5, 1e9], labels=["1", "2", "3-5", "6+"])
    F["cls"] = np.where(F.taker.isin(hft), "hft", "other")
    for half, H in F.groupby("half"):
        o = {"fills": int(len(H)), "matched_taker": round(float(H.pos.notna().mean()), 3)}
        o["fill_pos_share"] = H.pos.clip(upper=6).value_counts(normalize=True).sort_index().round(4).to_dict()
        agg = H.groupby("pos_b", observed=True).agg(n=("pnl", "size"), pnl=("pnl", "sum"), usd=("usd", "sum"))
        agg["ret"] = agg.pnl / agg.usd
        o["by_position"] = agg.round(4).to_dict("index")
        agg2 = H.groupby(["cls", "pos_b"], observed=True).agg(n=("pnl", "size"), pnl=("pnl", "sum"), usd=("usd", "sum"))
        agg2["ret"] = agg2.pnl / agg2.usd
        o["by_class_position"] = {f"{a}|{b}": v for (a, b), v in agg2.round(4).to_dict("index").items()}
        big = H[H.tsize >= 200]
        agg3 = big.groupby("pos_b", observed=True).agg(n=("pnl", "size"), pnl=("pnl", "sum"), usd=("usd", "sum"))
        agg3["ret"] = agg3.pnl / agg3.usd
        o["taker_print_ge_200sh_by_position"] = agg3.round(4).to_dict("index")
        o["total"] = {"pnl": round(float(H.pnl.sum()), 1), "ret": round(float(H.pnl.sum() / H.usd.sum()), 4)}
        out[half] = o
    out = json.loads(json.dumps(out, default=str))
    (HERE.parent / "results" / "iter6_q4_sequences.json").write_text(json.dumps(out, indent=1))
    for half in ("study", "validate"):
        o = out[half]
        print(half, o["fills"], o["matched_taker"], o["total"])
        print("  fill pos share", o["fill_pos_share"])
        print("  by pos", {k: (v["n"], round(v["pnl"]), round(v["ret"], 3)) for k, v in o["by_position"].items()})
        print("  by cls|pos", {k: (v["n"], round(v["pnl"]), round(v["ret"], 3)) for k, v in o["by_class_position"].items()})
        print("  big taker prints", {k: (v["n"], round(v["pnl"]), round(v["ret"], 3)) for k, v in o["taker_print_ge_200sh_by_position"].items()})
    print("base", list(out["base_pos_share_by_day"].values())[0])


if __name__ == "__main__":
    main()
