"""Iteration 10 (X61, panel iter7 I7-3): when is the strike public? Scheduled poller for ONE development hour
(default 11-01 06:00-07:00 UTC, a development block by tools/sealed.py). For every BTC 5m and 15m window starting in the
hour, it polls once per second from S - 15 s to S + 20 s: Gamma `markets?slug=...` (eventMetadata.priceToBeat in the
market's events) and Polymarket's crypto-price endpoint (openPrice for eventStartTime = S), and records the first receive
time each value is available, relative to the window start S. Output: .cache/re/directional-maker/strike_poll_<start>.jsonl.
It refuses to poll any window that tools/sealed.py marks sealed. Hard stop --until; it only sleeps until --start."""
import argparse
import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
import sealed  # noqa: E402

OUT = ROOT / ".cache/re/directional-maker"
GAMMA = "https://gamma-api.polymarket.com/markets"
CP = "https://polymarket.com/api/crypto/crypto-price"


def ptb_gamma(cli, slug):
    try:
        r = cli.get(GAMMA, params={"slug": slug})
        if r.status_code != 200:
            return None
        j = r.json()
        for m in j or []:
            for e in m.get("events") or []:
                v = (e.get("eventMetadata") or {}).get("priceToBeat")
                if v is not None:
                    return float(v)
    except Exception:  # noqa: BLE001
        return None
    return None


def open_cp(cli, S, variant):
    try:
        r = cli.get(CP, params={"symbol": "BTC", "variant": variant, "eventStartTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(S))})
        if r.status_code != 200:
            return None
        return r.json().get("openPrice")
    except Exception:  # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1793512800)
    ap.add_argument("--until", type=int, default=1793516400)
    a = ap.parse_args()
    st = sealed.load_state("directional-maker")
    while time.time() < a.start - 20:
        time.sleep(min(60, a.start - 20 - time.time()))
    cli = httpx.Client(timeout=10, headers={"User-Agent": "polyrea/0.1 (research)", "Accept": "application/json"})
    f = OUT / f"strike_poll_{a.start}.jsonl"
    wins = [(S, f"btc-updown-5m-{S}", "fiveminute") for S in range(a.start, a.until, 300)]
    wins += [(S, f"btc-updown-15m-{S}", "fifteen") for S in range(a.start, a.until, 900)]
    wins.sort()
    for S, slug, variant in wins:
        if time.time() > a.until or sealed.is_sealed(S, "directional-maker", st):
            continue
        while time.time() < S - 15:
            time.sleep(0.2)
        rec = {"S": S, "slug": slug, "gamma_first_s": None, "gamma_value": None, "cp_first_s": None, "cp_value": None}
        while time.time() < S + 20 and time.time() < a.until:
            t0 = time.time()
            if rec["gamma_first_s"] is None:
                v = ptb_gamma(cli, slug)
                if v is not None:
                    rec["gamma_first_s"], rec["gamma_value"] = round(time.time() - S, 3), v
            if rec["cp_first_s"] is None:
                v = open_cp(cli, S, variant)
                if v is not None:
                    rec["cp_first_s"], rec["cp_value"] = round(time.time() - S, 3), v
            if rec["gamma_first_s"] is not None and rec["cp_first_s"] is not None:
                break
            time.sleep(max(0.0, 1.0 - (time.time() - t0)))
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
