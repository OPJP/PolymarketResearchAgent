"""Iteration 10 (version10b: every day of August, 80 sampled txs of hour 16-17 UTC; X75 / X9 follow-up): did the bot change version between the delay-regime periods? For one sampled hour per period
(16-17 UTC on 08-12 [D 250 ms], 08-19 [50 ms, early], 09-01 [50 ms, late], 09-08 [150 ms]): the operator wallets' fill logs
(V2 exchanges; eth_getLogs in 100-block chunks), a seeded sample of their tx hashes, V2 calldata (decoded fields only, in memory):
per period the cluster's order sizes (menu), the signing-time phase mod 300 s (the pre-signed ladder bursts at rel -89.5 / +42 /
+173 s), the share of orders signed inside those bursts, signature type, and the role mix (taker order vs maker orders).
Usage: python version10.py OUT_JSON"""
import os, sys, json, time, calendar
import numpy as np, pandas as pd, httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc, calldata

WAL = {"0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS", "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF",
       "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xd84403efd50b49a1d8a7181627e00307e6ea5908": "W4"}
H = 1792713600
HOURS = {f"d{d}": f"2026-08-{d:02d}" for d in range(1, 32)}  # version10b: every day of August (hour 16-17 UTC)
ANCH = {1785542400: None, 1786320000: 91743315, 1787356800: 92434515, 1788134400: 92952915, 1789084800: 93586511}  # from delayreg10 (first block >= ts)


def logs(b0, b1, cl):
    body = {"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs",
            "params": [{"address": rpc.V2_EXCHANGES, "fromBlock": hex(b0), "toBlock": hex(b1), "topics": [rpc.TOPIC_V2, None, [rpc.pad(a) for a in WAL]]}]}
    for k in range(5):
        try:
            j = cl.post(rpc.RPC, json=body, timeout=60).json()
            if "result" in j:
                return j["result"]
        except Exception:
            pass
        time.sleep(1 + 2 * k)
    return []


def main(out):
    if ANCH.get(1785542400) is None:
        import delayreg10
        ANCH[1785542400] = delayreg10.find_block(1785542400)
    at = np.array(sorted(ANCH)); ab = np.array([ANCH[t] for t in at])
    cl = httpx.Client()
    rng = np.random.default_rng(10)
    res = {}
    for nm, d in HOURS.items():
        t0 = calendar.timegm(time.strptime(f"{d} 16", "%Y-%m-%d %H")); t1 = t0 + 3600
        assert t1 <= H
        b0 = int(np.interp(t0, at, ab)); b1 = int(np.interp(t1, at, ab))
        txs = set()
        for x in range(b0, b1 + 1, 100):
            for lg in logs(x, min(x + 99, b1), cl):
                bt = int(lg.get("blockTimestamp", "0x0"), 16) if isinstance(lg.get("blockTimestamp"), str) else t0
                if t0 <= bt < t1:
                    txs.add(lg["transactionHash"])
        txs = sorted(txs)
        samp = list(rng.choice(txs, min(80, len(txs)), replace=False)) if txs else []
        cd = calldata.to_frame(calldata.fetch_txs(samp, threads=2, log_every=10 ** 6)) if samp else pd.DataFrame()
        if not len(cd):
            res[nm] = {"txs": len(txs)}; continue
        c = cd[cd.maker.isin(list(WAL))].copy()
        c["w"] = c.maker.map(WAL); c["Z"] = c.taker_amt.astype(float).round(0)
        c["ph"] = (c.sign_ms / 1000.0) % 300
        def inb(ph):
            return ((np.abs(ph - (300 - 89.5)) < 3) | (np.abs(ph - 42.4) < 4) | (np.abs(ph - 173.3) < 4))
        res[nm] = {"txs_in_hour": len(txs), "sampled": len(samp), "cluster_orders": int(len(c)),
                   "role_T_share": round(float((c.role == "T").mean()), 4),
                   "sizes_top": {w: g.Z.value_counts().head(4).to_dict() for w, g in c.groupby("w")},
                   "share_signed_in_bursts": round(float(inb(c.ph.to_numpy()).mean()), 4),
                   "phase_q10_50_90": [round(float(x), 1) for x in np.percentile(c.ph, [10, 50, 90])],
                   "sig_type": c.sig_type.value_counts().to_dict(), "sig_len": c.sig_len.value_counts().head(3).to_dict()}
        print(nm, json.dumps(res[nm], default=str), flush=True)
    json.dump(res, open(out, "w"), indent=1, default=str)


if __name__ == "__main__":
    main(sys.argv[1])
