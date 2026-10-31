"""Iteration 10 (panel iter9 information P3 = X75, block-level first step): Polymarket's taker-delay regimes as natural
experiments. Changelog: taker delay 250 ms until 2026-08-17 11:00 UTC, 50 ms until 09-04 14:00 UTC, 150 ms since (all before H).
Mechanism under test (iteration 10 findings 1, 3-4): the operator's maker fills are mostly LOST RACES that rest at the old ask
after the race in the delay queue is lost; with a shorter hold fewer races are lost, so the maker share of its fills should
FALL when D drops to 50 ms and RISE when D returns to 150 ms (a fixed passive-quoting component would not move).
Sample: hour 16-17 UTC, Monday-Thursday, of the weeks around each change (08-10..13 vs 08-18..21; 08-31..09-03 vs
09-07..10). Logs: OrderFilled of the four operator wallets (topic2 = wallet) on the V1 CTF exchange (0x4bfb41d5..., topic0
0xd0a08e8c...) and the V2 exchanges (topic0 0xd543adfd...); role = taker when topic3 is the exchange itself. Raw logs are not
stored (counts only). Day-block bootstrap of the before / after difference.
Usage: python delayreg10.py OUT_JSON"""
import os, sys, json, time, calendar
import numpy as np, httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc

V1 = "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"
EXS = [V1] + rpc.V2_EXCHANGES
T_V1 = "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"
WAL = {"DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9", "GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6",
       "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "W4": "0xd84403efd50b49a1d8a7181627e00307e6ea5908"}
H = 1792713600
DAYS = {"D250_before_0817": ["2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13"],
        "D50_after_0817": ["2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21"],
        "D50_before_0904": ["2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03"],
        "D150_after_0904": ["2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10"]}
HOURS = (16,)  # drpc free plan: getLogs <= ~100 blocks per call (10-31 21:50 UTC), so one hour per day


def ts_of(d, h):
    return calendar.timegm(time.strptime(f"{d} {h:02d}", "%Y-%m-%d %H"))


def find_block(ts, lo_hint=None):
    head = int(rpc.call("eth_blockNumber", [], max_age=3600), 16)
    est = head - int((rpc.block_ts(head) - ts) / 2.0)
    lo, hi = max(1, est - 600_000), min(head, est + 600_000)
    while rpc.block_ts(lo) >= ts:
        lo = max(1, lo - 600_000)
    while rpc.block_ts(hi) < ts:
        hi = min(head, hi + 600_000)
    while lo < hi:
        mid = (lo + hi) // 2
        if rpc.block_ts(mid) < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def logs(b0, b1, cl):
    body = {"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs",
            "params": [{"address": EXS, "fromBlock": hex(b0), "toBlock": hex(b1), "topics": [[T_V1, rpc.TOPIC_V2], None, [rpc.pad(a) for a in WAL.values()]]}]}
    for url in (rpc.RPC, rpc.RPC2):
        for k in range(4):
            try:
                r = cl.post(url, json=body, timeout=60)
                j = r.json()
                if "result" in j:
                    return j["result"]
                time.sleep(2 + 3 * k)
            except Exception:
                time.sleep(2 + 3 * k)
    raise RuntimeError("getLogs failed")


def main(out):
    anchors = {}
    for d in ("2026-08-10", "2026-08-22", "2026-08-31", "2026-09-11"):
        t = ts_of(d, 0); anchors[t] = find_block(t)
    at = np.array(sorted(anchors)); ab = np.array([anchors[t] for t in at])
    cl = httpx.Client()
    inv = {rpc.pad(a): w for w, a in WAL.items()}
    res = {"anchors": {str(t): int(b) for t, b in zip(at, ab)}, "periods": {}}
    per_hour = {}
    for per, days in DAYS.items():
        rows = []
        for d in days:
            for h in HOURS:
                t0 = ts_of(d, h); t1 = t0 + 3600
                assert t1 <= H
                b0 = int(np.interp(t0, at, ab)) - 400; b1 = int(np.interp(t1, at, ab)) + 400
                from concurrent.futures import ThreadPoolExecutor
                chunks = [(x, min(x + 99, b1)) for x in range(b0, b1 + 1, 100)]
                with ThreadPoolExecutor(2) as ex_:
                    parts = list(ex_.map(lambda c: logs(c[0], c[1], cl), chunks))
                lg = [x for p_ in parts for x in p_]
                cnt = {}
                for x in lg:
                    bt = int(x.get("blockTimestamp", "0x0"), 16) if isinstance(x.get("blockTimestamp"), str) else None
                    if bt is not None and not (t0 <= bt < t1):
                        continue
                    w = inv.get(x["topics"][2].lower())
                    if w is None:
                        continue
                    role = "T" if x["topics"][3].lower() == rpc.pad(x["address"]) else "M"
                    ver = "V1" if x["topics"][0].lower() == T_V1 else "V2"
                    c = cnt.setdefault(w, {"T": 0, "M": 0, "V1": 0, "V2": 0})
                    c[role] += 1; c[ver] += 1
                rows.append({"day": d, "hour": h, "logs": len(lg), "by_wallet": cnt})
                time.sleep(0.4)
        per_hour[per] = rows
        tot = {}
        for r in rows:
            for w, c in r["by_wallet"].items():
                t_ = tot.setdefault(w, {"T": 0, "M": 0, "V1": 0, "V2": 0, "hours_active": 0})
                for k in ("T", "M", "V1", "V2"):
                    t_[k] += c[k]
                t_["hours_active"] += int(c["T"] + c["M"] > 0)
        for w, t_ in tot.items():
            t_["maker_share"] = round(t_["M"] / max(t_["T"] + t_["M"], 1), 4)
            t_["fills_per_active_hour"] = round((t_["T"] + t_["M"]) / max(t_["hours_active"], 1), 1)
        allT = sum(t_["T"] for w, t_ in tot.items() if w != "W4"); allM = sum(t_["M"] for w, t_ in tot.items() if w != "W4")
        res["periods"][per] = {"by_wallet": tot, "cluster_maker_share": round(allM / max(allT + allM, 1), 4), "cluster_fills": allT + allM}
        print(per, json.dumps(res["periods"][per]), flush=True)
    # day-block bootstrap of the maker-share change at each date (cluster = DS + GF + XM)
    def day_shares(rows):
        out = {}
        for r in rows:
            m = sum(c["M"] for w, c in r["by_wallet"].items() if w != "W4"); t = sum(c["T"] for w, c in r["by_wallet"].items() if w != "W4")
            a = out.setdefault(r["day"], [0, 0]); a[0] += m; a[1] += m + t
        return np.array(list(out.values()), float)
    rng = np.random.default_rng(10)
    for nm, (p0, p1) in (("0817 (250 -> 50 ms)", ("D250_before_0817", "D50_after_0817")), ("0904 (50 -> 150 ms)", ("D50_before_0904", "D150_after_0904"))):
        A_, B_ = day_shares(per_hour[p0]), day_shares(per_hour[p1])
        if len(A_) and len(B_) and A_[:, 1].sum() > 0 and B_[:, 1].sum() > 0:
            d0 = B_[:, 0].sum() / B_[:, 1].sum() - A_[:, 0].sum() / A_[:, 1].sum()
            bs = []
            for _ in range(2000):
                a = A_[rng.integers(0, len(A_), len(A_))]; b = B_[rng.integers(0, len(B_), len(B_))]
                if a[:, 1].sum() > 0 and b[:, 1].sum() > 0:
                    bs.append(b[:, 0].sum() / b[:, 1].sum() - a[:, 0].sum() / a[:, 1].sum())
            res[f"maker_share_change_{nm}"] = {"diff": round(float(d0), 4), "ci95_day_bootstrap": [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]}
    res["per_hour"] = per_hour
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "per_hour"}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
