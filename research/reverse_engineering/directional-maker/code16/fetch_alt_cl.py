"""iteration 16, I15-2 part (a): per-symbol Chainlink value (Polymarket crypto-price endpoint, openPrice = the value
stamped at eventStartTime) at T - 2 for every opening fill (< 20 s) of the ETH / SOL / XRP 5m / 15m windows (verified
variants), VALIDATE first, then STUDY, then BUILD; plus the 60 values [st - 61, st - 2] of a few windows per symbol to
verify priceToBeat = mean CL. Adaptive limiter (~1.5 requests/s), hard stop at --until. Output
.cache/re/directional-maker/cl/alt_open.parquet (sym, tau, open, close, completed).
    python fetch_alt_cl.py --until 1793528400"""
import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
OUT = C / "cl" / "alt_open.parquet"
BASE = "https://polymarket.com/api/crypto/crypto-price"
SYM = {"ETHUSDT": "ETH", "SOLUSDT": "SOL", "XRPUSDT": "XRP"}


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(t)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", type=int, required=True)
    args = ap.parse_args()
    a = pd.concat([pd.read_parquet(C / "it15_nb_public_lot.parquet"), pd.read_parquet(C / "it15_nb_public_build.parquet")],
                  ignore_index=True)
    a = a[a.fam.str.match(r"^(eth|sol|xrp)-(5m|15m)$") & (a.timestamp - a.st < 20) & a.sym.isin(list(SYM))].copy()
    a["fold2"] = np.where(a.fold.str.startswith("STUDY"), "STUDY", np.where(a.fold == "VALIDATE", "VALIDATE", "BUILD"))
    order = []
    # verification windows first: two per symbol from STUDY
    for sym in SYM:
        g = a[(a.sym == sym) & (a.fold2 == "STUDY")].drop_duplicates("st").head(2)
        for st in g.st:
            order += [(SYM[sym], int(t)) for t in range(int(st) - 61, int(st) - 1)]
    for f_ in ("VALIDATE", "STUDY", "BUILD"):
        g = a[a.fold2 == f_]
        order += [(SYM[s], int(t) - 2) for s, t in zip(g.sym, g.timestamp)]
    order = list(dict.fromkeys(order))
    done = set()
    if OUT.exists():
        d0 = pd.read_parquet(OUT)
        done = set(zip(d0.sym, d0.tau.astype(int)))
    todo = [x for x in order if x not in done]
    print("todo", len(todo), "done", len(done), flush=True)
    import httpx
    lock, nxt, gap = threading.Lock(), [time.time()], [0.6]
    cli = httpx.Client(timeout=20, headers={"User-Agent": "polyrea/0.1 (research)", "Accept": "application/json"})

    def get(params):
        while True:
            if time.time() > args.until:
                return None
            with lock:
                wait = nxt[0] - time.time()
                nxt[0] = max(nxt[0], time.time()) + gap[0]
            if wait > 0:
                time.sleep(wait)
            r = cli.get(BASE, params=params)
            if r.status_code == 429:
                with lock:
                    gap[0] = min(1.2, gap[0] + 0.05)
                    nxt[0] = max(nxt[0], time.time() + 2.0)
                continue
            r.raise_for_status()
            with lock:
                gap[0] = max(0.5, gap[0] - 0.002)
            return r.json()

    def one(x):
        sym, t = x
        for k in range(4):
            try:
                d = get({"symbol": sym, "variant": "fiveminute", "eventStartTime": iso(t)})
                if d is None:
                    return None
                return (sym, t, d.get("openPrice"), d.get("closePrice"), bool(d.get("completed")))
            except Exception as e:  # noqa: BLE001
                err = repr(e)[:160]
                time.sleep(2 * (k + 1))
        print("FAIL", sym, t, err, flush=True)
        return (sym, t, None, None, False)

    rows, t0 = [], time.time()
    with ThreadPoolExecutor(2) as ex:
        for i, r in enumerate(ex.map(one, todo)):
            if r is not None:
                rows.append(r)
            if len(rows) >= 100 or (i == len(todo) - 1 and rows):
                df = pd.DataFrame(rows, columns=["sym", "tau", "open", "close", "completed"])
                if OUT.exists():
                    df = pd.concat([pd.read_parquet(OUT), df]).drop_duplicates(["sym", "tau"])
                df.to_parquet(OUT, index=False)
                rows = []
                print("saved", i + 1, "of", len(todo), round(time.time() - t0), "s", flush=True)
            if time.time() > args.until:
                break
    if rows:
        df = pd.DataFrame(rows, columns=["sym", "tau", "open", "close", "completed"])
        if OUT.exists():
            df = pd.concat([pd.read_parquet(OUT), df]).drop_duplicates(["sym", "tau"])
        df.to_parquet(OUT, index=False)
    print("end", round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main()
