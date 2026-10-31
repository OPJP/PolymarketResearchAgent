"""Iteration 11 (panel iter10 mechanics P4 = X95, correction of iteration-10 finding 17): were the August orders signed FRESH
(decision-time signing) or PRE-SIGNED on another schedule? For sampled hours (16:00-16:20 UTC) of 08-05 (the 08-01..07 phase
schedule), 08-12 (the panel's day) and 08-15 (still before the 08-17 delay cut): operator fill logs in 100-block chunks, block
timestamps from the logs, a seeded sample of 60 txs, V2 calldata decoded in memory (fields only): sign-to-block = block ts -
sign_ms / 1000 for the operator's orders by role (T = the tx's taker order, M = maker orders) and for other wallets' taker
orders in the same txs (fresh-signing reference), plus the signing phase mod 300 s.
Usage: python version11.py OUT_JSON"""
import os, sys, json, time, calendar
import numpy as np, pandas as pd, httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc, calldata
from version10b import logs, ANCH, WAL

DAYS = ("2026-08-05", "2026-08-12", "2026-08-15")


def main(out):
    if ANCH.get(1785542400) is None:
        import delayreg10
        ANCH[1785542400] = delayreg10.find_block(1785542400)
    at = np.array(sorted(ANCH)); ab = np.array([ANCH[t] for t in at])
    cl = httpx.Client(); rng = np.random.default_rng(11)
    res = {}
    for d in DAYS:
        t0 = calendar.timegm(time.strptime(f"{d} 16", "%Y-%m-%d %H")); t1 = t0 + 1200
        b0 = int(np.interp(t0, at, ab)) - 50; b1 = int(np.interp(t1, at, ab)) + 50
        bts = {}
        for x in range(b0, b1 + 1, 100):
            for lg in logs(x, min(x + 99, b1), cl):
                bt = int(lg.get("blockTimestamp", "0x0"), 16) if isinstance(lg.get("blockTimestamp"), str) else None
                if bt is not None and t0 <= bt < t1:
                    bts[lg["transactionHash"]] = bt
        txs = sorted(bts)
        samp = list(rng.choice(txs, min(60, len(txs)), replace=False)) if txs else []
        cd = calldata.to_frame(calldata.fetch_txs(samp, threads=2, log_every=10 ** 6)) if samp else pd.DataFrame()
        if not len(cd):
            res[d] = {"txs": len(txs)}; continue
        cd["bt"] = cd.tx.map(bts)
        if cd.bt.isna().all():
            cd["bt"] = cd.tx.str.lower().map({k.lower(): v for k, v in bts.items()})
        cd["s2b"] = cd.bt - cd.sign_ms / 1000.0
        op = cd[cd.maker.isin(list(WAL))].copy(); op["w"] = op.maker.map(WAL)
        oth = cd[~cd.maker.isin(list(WAL)) & (cd.role == "T")]
        row = {"txs_in_20min": len(txs), "sampled": len(samp), "operator_orders": int(len(op))}
        for (w, role), g in op.groupby(["w", "role"]):
            v = g.s2b.dropna().to_numpy()
            if len(v):
                row[f"{w}_{role}"] = {"n": int(len(v)), "sign_to_block_s_min_q25_50_75": [round(float(x), 2) for x in (v.min(), *np.percentile(v, [25, 50, 75]))]}
        v = oth.s2b.dropna().to_numpy()
        if len(v):
            row["other_wallets_T"] = {"n": int(len(v)), "sign_to_block_s_min_q25_50_75": [round(float(x), 2) for x in (v.min(), *np.percentile(v, [25, 50, 75]))]}
        ph = (op.sign_ms / 1000.0) % 300
        row["operator_phase_hist_30s"] = [int(x) for x in np.histogram(ph, bins=np.arange(0, 301, 30))[0]]
        row["operator_share_signed_within_5s_of_block"] = round(float((op.s2b < 5).mean()), 4)
        row["sizes"] = {str(k): int(v) for k, v in op.taker_amt.astype(float).round(0).value_counts().head(5).items()}
        row["same_ms_copies_share"] = round(float(op.duplicated(["sign_ms", "maker"], keep=False).mean()), 4)
        res[d] = row
        print(d, json.dumps(row), flush=True)
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
