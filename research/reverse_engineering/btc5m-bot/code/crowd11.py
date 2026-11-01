"""Iteration 11 (panel iter10 information P1 step 0 = X87): crowd10 re-timed on the SERVER clock. crowd10 timed the crowd's
decisions at sign_ms (each client's own clock: per-wallet minima of match - sign spread over ~70-150 ms, some negative), while
the cluster was timed at match - 180. Here every crowd taker BUY is timed like the cluster: d = match - 150 (the taker delay)
- 30 ms (posting), the same clock for both. Variants (argv[2]): 'fresh' = only orders with 180 <= match - sign <= 2,000 ms
(crowd10's set), 'all' = every non-operator taker BUY (pre-signed or late-matched orders included), 'fast' = 180-260 ms.
Everything else (grid, features, labels, fit on A, scored on C) is crowd10's code unchanged.
Usage: python crowd11.py OUT_JSON fresh|all|fast"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crowd10

_orig = crowd10.crowd_decisions


def crowd_server_clock(tokmap):
    t = _orig(tokmap)
    t = t.copy()
    t["sign_ms"] = (t.m - 180).astype("int64")
    return t


if __name__ == "__main__":
    mode = sys.argv[2] if len(sys.argv) > 2 else "fresh"
    crowd10.DT = {"fresh": (180, 2000), "all": (-1e15, 1e15), "fast": (180, 260)}[mode]
    crowd10.crowd_decisions = crowd_server_clock
    crowd10.main(sys.argv[1])
