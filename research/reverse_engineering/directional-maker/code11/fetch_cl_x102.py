"""Iteration 11 (X102, copy of code10/fetch_cl_hist.py with its own queue/status; waits for the iteration-10 job to finish). Iteration 10 (A1 = X97, I9-4 = X90): detached, polite fetch of historical Chainlink BTC/USD 1-s values from
Polymarket's crypto-price endpoint (30-day horizon) for the stamps queued in .cache/re/directional-maker/a1_queue10.parquet
(priority order). One request gives the value stamped tau (openPrice) and tau + 300 (closePrice). Writes one parquet per
chunk into .cache/re/directional-maker/cl/ (tau, open, close, completed), which cl_source._cache() reads. Every stamp is
checked with sealed.is_sealed (released lots and pre-H days only). Hard stop: --until (unix s). Rate: adaptive, about
1-1.5 requests/s, slower after HTTP 429. Status: .cache/re/directional-maker/cl_fetch10_status.json."""
import argparse, json, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd, httpx
HERE = Path(__file__).resolve().parent
CODE10 = HERE.parent / "code10"
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
sys.path.insert(0, str(HERE.parent / "code"))
import sealed  # noqa: E402
import cl_source  # noqa: E402
C = ROOT / ".cache/re/directional-maker"
BASE = "https://polymarket.com/api/crypto/crypto-price"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--until", type=int, required=True); ap.add_argument("--chunk", type=int, default=60)
    a = ap.parse_args()
    while True:  # wait for the iteration-10 fetch to finish (or pass its hard stop)
        try:
            st10 = json.loads((C / "cl_fetch10_status.json").read_text())
        except Exception:  # noqa: BLE001
            st10 = {}
        if st10.get("finished") or time.time() > st10.get("until", 0) + 60:
            break
        if time.time() > a.until:
            return
        time.sleep(60)
    q = pd.read_parquet(C / "a1_queue11.parquet")
    have = set(cl_source._cache().keys())
    st = sealed.load_state("directional-maker")
    todo, seen = [], set()
    for s in q.stamp.astype(np.int64):
        s = int(s)
        if s in have or s in seen or sealed.is_sealed(s, "directional-maker", st):
            continue
        seen.add(s); todo.append(s)
    # pair stamps 300 s apart into one request
    tset, taus = set(todo), []
    used = set()
    for s in todo:
        if s in used:
            continue
        if s + 300 in tset and s + 300 not in used:
            taus.append(s); used.update((s, s + 300))
        elif s - 300 in tset and s - 300 not in used:
            taus.append(s - 300); used.update((s, s - 300))
        else:
            taus.append(s); used.add(s)
    lock, nxt, gap = threading.Lock(), [time.time()], [0.7]
    cli = httpx.Client(timeout=20, headers={"User-Agent": "polyrea/0.1 (research)", "Accept": "application/json"})
    stat = {"queued_requests": len(taus), "done": 0, "ok": 0, "n429": 0, "started": int(time.time()), "until": a.until}

    def one(t):
        for _ in range(40):
            if time.time() > a.until:
                return t, None, None, False
            with lock:
                wait = nxt[0] - time.time(); nxt[0] = max(nxt[0], time.time()) + gap[0]
            if wait > 0:
                time.sleep(wait)
            try:
                r = cli.get(BASE, params={"symbol": "BTC", "variant": "fiveminute", "eventStartTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))})
            except Exception:  # noqa: BLE001
                time.sleep(2); continue
            if r.status_code == 429:
                with lock:
                    stat["n429"] += 1; gap[0] = min(2.0, gap[0] + 0.05); nxt[0] = max(nxt[0], time.time() + 2.0)
                continue
            if r.status_code != 200:
                time.sleep(1); continue
            with lock:
                gap[0] = max(0.45, gap[0] - 0.002)
            d = r.json()
            return t, d.get("openPrice"), d.get("closePrice"), bool(d.get("completed"))
        return t, None, None, False

    k = 0
    with ThreadPoolExecutor(3) as ex:
        for i in range(0, len(taus), a.chunk):
            if time.time() > a.until:
                break
            rows = list(ex.map(one, taus[i:i + a.chunk]))
            df = pd.DataFrame(rows, columns=["tau", "open", "close", "completed"])
            keep = df[df.completed & df.open.notna()]
            if len(keep):
                keep.to_parquet(C / "cl" / f"cl_hist11_{stat['started']}_{k:05d}.parquet", index=False); k += 1
            stat["done"] += len(rows); stat["ok"] += int(len(keep)); stat["gap"] = gap[0]; stat["t"] = int(time.time())
            (C / "cl_fetch11_status.json").write_text(json.dumps(stat))
    stat["finished"] = int(time.time()); (C / "cl_fetch11_status.json").write_text(json.dumps(stat))


if __name__ == "__main__":
    main()
