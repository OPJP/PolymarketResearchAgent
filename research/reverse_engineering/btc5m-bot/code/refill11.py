"""Iteration 11 (panel iter10 mechanics P3 = X94, step 2): does the remainder's resting time shrink when the taker delay D
rises (a cancel timer armed at the POST, so the resting time is tau - D)? Per order hash (topic1) of the operator wallets'
OrderFilled logs, hour 16-17 UTC Mon-Thu around the two changelog dates (delayreg10's sample; the 250 -> 50 ms cut of 08-17
falls inside one pre-signed schedule version, the 50 -> 150 ms rise of 09-04 inside the 80 / 200 version): among TAKER-FIRST
orders (first fill as taker), P(the same order later gets a maker fill) = the refill probability, and the block delay from the
taker fill to the first maker fill. Prediction under a POST-armed timer: refill probability UP after 08-17 (D 250 -> 50) and
DOWN after 09-04 (D 50 -> 150). Logs fetched in 100-block chunks (drpc free plan); only counts are kept.
Usage: python refill11.py OUT_JSON"""
import os, sys, json, time
import numpy as np, httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc, delayreg10 as D10
from concurrent.futures import ThreadPoolExecutor


def main(out):
    anchors = {}
    for d in ("2026-08-10", "2026-08-22", "2026-08-31", "2026-09-11"):
        t = D10.ts_of(d, 0); anchors[t] = D10.find_block(t)
    at = np.array(sorted(anchors)); ab = np.array([anchors[t] for t in at])
    cl = httpx.Client()
    inv = {rpc.pad(a): w for w, a in D10.WAL.items()}
    res = {"periods": {}}
    for per, days in D10.DAYS.items():
        rows = []
        for d in days:
            t0 = D10.ts_of(d, 16); t1 = t0 + 3600
            assert t1 <= D10.H
            b0 = int(np.interp(t0, at, ab)) - 400; b1 = int(np.interp(t1, at, ab)) + 400
            chunks = [(x, min(x + 99, b1)) for x in range(b0, b1 + 1, 100)]
            with ThreadPoolExecutor(2) as ex_:
                parts = list(ex_.map(lambda c: D10.logs(c[0], c[1], cl), chunks))
            lg = [x for p_ in parts for x in p_]
            orders = {}
            for x in lg:
                bt = int(x.get("blockTimestamp", "0x0"), 16) if isinstance(x.get("blockTimestamp"), str) else None
                if bt is None or not (t0 <= bt < t1 + 600):
                    continue
                w = inv.get(x["topics"][2].lower())
                if w is None or w == "W4":
                    continue
                role = "T" if x["topics"][3].lower() == rpc.pad(x["address"]) else "M"
                key = x["topics"][1].lower()
                blk = int(x["blockNumber"], 16); li = int(x["logIndex"], 16)
                orders.setdefault(key, []).append((blk, li, role, bt, w))
            nT = 0; nTref = 0; delays = []; nM = 0
            for k, v in orders.items():
                v.sort()
                if v[0][3] >= t1:  # order first filled after the hour
                    continue
                if v[0][2] == "T":
                    nT += 1
                    ms = [r for r in v if r[2] == "M"]
                    if ms:
                        nTref += 1; delays.append(ms[0][3] - v[0][3])
                else:
                    nM += 1
            rows.append({"day": d, "taker_first_orders": nT, "refilled": nTref, "maker_first_orders": nM,
                         "refill_p": round(nTref / max(nT, 1), 4), "refill_delay_s_q50_90": [float(np.percentile(delays, 50)), float(np.percentile(delays, 90))] if delays else None})
            print(per, rows[-1], flush=True)
            time.sleep(0.3)
        T = sum(r["taker_first_orders"] for r in rows); R = sum(r["refilled"] for r in rows); M = sum(r["maker_first_orders"] for r in rows)
        res["periods"][per] = {"days": rows, "refill_p": round(R / max(T, 1), 4), "taker_first": T, "maker_first": M,
                               "maker_first_share_of_orders": round(M / max(T + M, 1), 4)}
    def boot(p0, p1, n=2000, seed=3):
        rng = np.random.default_rng(seed)
        a = [(r["refilled"], r["taker_first_orders"]) for r in res["periods"][p0]["days"]]
        b = [(r["refilled"], r["taker_first_orders"]) for r in res["periods"][p1]["days"]]
        g = []
        for _ in range(n):
            ia = rng.integers(0, len(a), len(a)); ib = rng.integers(0, len(b), len(b))
            pa = sum(a[i][0] for i in ia) / max(sum(a[i][1] for i in ia), 1); pb = sum(b[i][0] for i in ib) / max(sum(b[i][1] for i in ib), 1)
            g.append(pb - pa)
        return [round(float(x), 4) for x in np.percentile(g, [2.5, 50, 97.5])]
    res["change_0817 (D 250->50)"] = boot("D250_before_0817", "D50_after_0817")
    res["change_0904 (D 50->150)"] = boot("D50_before_0904", "D150_after_0904")
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "periods"}, indent=1))
    print({p: (v["refill_p"], v["maker_first_share_of_orders"]) for p, v in res["periods"].items()})


if __name__ == "__main__":
    main(sys.argv[1])
