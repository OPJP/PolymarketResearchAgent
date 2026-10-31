"""Iteration 11 (X60 follow-up): the side rule in the 250-ms regime (pmxt hours 08-05 / 08-06 16-17 UTC, development). For each
cluster taker match (server ms m, bought outcome from the archive's BUY trade of the tx), the Binance USD-M BTCUSDT trade-price
move over the PIT window shifted by the longer hold, [m - D - 600, m - D - 30) with D = 250 ms (the 10-31 PIT window [m - 650,
m - 180) uses D = 150), and the frozen 10-31 window [m - 600, m - 100) for reference: agreement of sign(move) with the bought
outcome on voted decisions (|move| > 0), coverage, and a placebo (m +- 5-60 s). Single series (trades): the 10-31 six-series
vote was 83% on 67.6% voted.
Usage: python side11.py OUT_JSON"""
import os, sys, json, glob
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"


def r4(x):
    return round(float(x), 4)


def main(out):
    res = {}
    for tag, day, t0 in (("20260805_16", "2026-08-05", 1786291200 + 57600), ("20260806_16", "2026-08-06", 1786377600 + 57600)):
        Tr = pd.read_parquet(f"{C}/it11/pmxt_{tag}_trades.parquet"); F = pd.read_parquet(f"{C}/it11/pmxt_{tag}_cluster.parquet")
        up_tok = {k: str(v) for k, v in json.load(open(f"{C}/it11/pmxt_{tag}_markets.json"))["up_tokens"].items()}
        Tr["tx"] = Tr.transaction_hash.str.lower()
        ft = F[(F.role == "T") & F.m.notna() & (F.w != "W4")].drop_duplicates("tx")
        bt = Tr[Tr.side == "BUY"].sort_values("ms").drop_duplicates("tx")
        ft = ft.merge(bt[["tx", "market", "asset_id"]], on="tx", how="left"); ft = ft[ft.market.isin(up_tok)]
        ft["up"] = [str(a) == up_tok[mk] for a, mk in zip(ft.asset_id, ft.market)]
        B = pd.read_parquet(glob.glob(f"{C}/it11/bnf_{day}_*.parquet")[0])
        T = B["T"].to_numpy(np.int64); p = B["p"].to_numpy(float)
        def px(t):
            i = np.searchsorted(T, t, "right") - 1
            return np.where(i >= 0, p[np.clip(i, 0, None)], np.nan)
        m = ft.m.to_numpy(np.int64); up = ft.up.to_numpy(bool)
        rng = np.random.default_rng(5)
        pl = m + (rng.choice([-1, 1], len(m)) * rng.uniform(5000, 60000, len(m))).astype(np.int64)
        row = {"matches": int(len(m)), "by_wallet": {w: int(n) for w, n in ft.w.value_counts().items()}}
        for nm, (a_, b_) in (("pit_D250 [m-850, m-280)", (850, 280)), ("pit_D150 [m-650, m-180)", (650, 180)), ("frozen [m-600, m-100)", (600, 100)), ("late [m-280, m-30)", (280, 30))):
            mv = px(m - b_) - px(m - a_); mvp = px(pl - b_) - px(pl - a_)
            v = mv != 0; vp = mvp != 0
            row[nm] = {"voted": r4(np.mean(v)), "agree_on_voted": r4(np.mean((mv[v] > 0) == up[v])),
                       "placebo_agree": r4(np.mean((mvp[vp] > 0) == up[vp])), "full_coverage_tie_half": r4((np.sum((mv[v] > 0) == up[v]) + 0.5 * np.sum(~v)) / len(m))}
            for w in ("DS", "XM"):
                k = (ft.w.to_numpy() == w) & v
                if k.sum() >= 30:
                    row[nm][f"agree_{w}"] = r4(np.mean((mv[k] > 0) == up[k]))
        res[tag] = row
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
