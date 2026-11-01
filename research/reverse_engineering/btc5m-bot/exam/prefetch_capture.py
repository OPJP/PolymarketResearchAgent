"""Examiner r1: prefetch the public HF capture row groups (same memo files run_eval.memo_read serves) for given time ranges.
Usage: python prefetch_capture.py SUB DAY_LIST RANGE_A RANGE_B [RANGE_A RANGE_B ...]
  SUB = polymarket | btc ; DAY_LIST = comma-separated YYYY-MM-DD day files; ranges in epoch seconds (row groups whose time
  statistics overlap any range are fetched)."""
import os, sys, time
sys.argv, ARGS = sys.argv[:1], sys.argv[1:]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_eval as R
import httpx
from concurrent.futures import ThreadPoolExecutor

sub, days = ARGS[0], ARGS[1].split(",")
rr = [int(x) for x in ARGS[2:]]
ranges = [(a * 1000 - 10000, b * 1000 + 320000) for a, b in zip(rr[::2], rr[1::2])]
tcol = "exchangeTimestampMs" if sub == "polymarket" else "receivedTimestampMs"
cl = httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "research-exam-route"})
t0 = time.time()
for day in days:
    M = R._meta(cl, sub, day)
    if M is None:
        print(sub, day, "missing", flush=True); continue
    idx = [i for i, (has, mn, mx) in enumerate(M["stats"][tcol]) if has and any(not (mx < a or mn > b) for a, b in ranges)]
    todo = [i for i in idx if not os.path.exists(f"{R.CAP}/{sub}_{day}_rg{i}.parquet")]
    print(sub, day, "row groups", len(idx), "todo", len(todo), flush=True)
    if not todo:
        continue
    R._rg(cl, sub, day, M, todo[0])
    cls = {}

    def one(i):
        import threading
        k = threading.get_ident()
        if k not in cls:
            cls[k] = httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "research-exam-route"})
        return R._rg(cls[k], sub, day, M, i)
    n = 0
    with ThreadPoolExecutor(4) as ex:
        for _ in ex.map(one, todo[1:]):
            n += 1
            if n % 100 == 0:
                print(sub, day, n, len(todo), round(time.time() - t0), flush=True)
    print(sub, day, "done", round(time.time() - t0), flush=True)
print("PREFETCH DONE", round(time.time() - t0), flush=True)
