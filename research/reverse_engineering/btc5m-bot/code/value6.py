"""Iteration 6 (X13 value threshold / X21 inverse-fit FV; panel iteration 5): is the quiet-order side a VALUE (level) rule?
Live development events from live6.py (live6_events.parquet: one row per cluster taker match, server ms m, side).
For window W before the decision (end m - 50 ms): dPM = change of the Polymarket Up mid (shared clob_crypto book),
dS = BTC move (bp) on a reference feed. Under a digital-option fair value with the market's own implied d = Phi^-1(mid),
the Up value moves by delta = phi(d) / (sigma_bp sqrt(tau)) per bp; the value gap of Up is gap = delta dS - dPM. Value
rule: buy Up iff gap > 0 (Down iff gap < 0). sigma_bp fitted on the first half of the events (by side accuracy), tested
on the second half. Compared with: sign(dS) (momentum), sign(-dPM) (fade of the Polymarket move).
Usage: python value6.py START END"""
import os, sys, json, glob
import numpy as np, pandas as pd
from scipy.stats import norm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6
C = L.C


def mid_at(arr, t):
    i = np.searchsorted(arr[:, 0], t, side="left") - 1
    if i < 0:
        return np.nan
    bb, ba = arr[i, 2], arr[i, 3]
    if not (np.isfinite(bb) and np.isfinite(ba)) or ba - bb > 0.05:
        return np.nan
    return (bb + ba) / 2


def acc(pred, up, mask):
    ok = mask & np.isfinite(pred) & (pred != 0)
    if ok.sum() == 0:
        return {"n": 0, "acc": None}
    return {"n": int(ok.sum()), "cover": round(float(ok.sum() / max(mask.sum(), 1)), 3), "acc": round(float(((pred[ok] > 0) == up[ok]).mean()), 4)}


def main(a, b):
    ev = pd.read_parquet(C + "/live6_events.parquet")
    tok, books, trades = L.load_books(a, b)
    feeds = {}
    for v, sym in [("bnf", "BTCUSDT"), ("bnf", "ETHUSDT"), ("bns", "BTCUSDT"), ("cb", "BTC-USD")]:
        s = live6.series(sorted(glob.glob(f"{live6.P}/rest6_{v}_{sym}_*.parquet")))
        if s is not None:
            feeds[f"{v}_{sym[:3]}"] = s
    m = ev.m.to_numpy(np.int64); up = ev.is_up.to_numpy(bool)
    quiet = ev.quiet_trades8.to_numpy(bool) if "quiet_trades8" in ev else np.zeros(len(ev), bool)
    tau = (ev.start.to_numpy(float) + 300.0) - m / 1000.0
    res = {"n": int(len(ev)), "quiet": int(quiet.sum())}
    half = np.arange(len(ev)) < len(ev) // 2
    for W in (1000, 3000, 5000, 10000):
        p1 = np.array([mid_at(books[u], t - 50) if u in books else np.nan for u, t in zip(ev.up_token, m)])
        p0 = np.array([mid_at(books[u], t - 50 - W) if u in books else np.nan for u, t in zip(ev.up_token, m)])
        dPM = p1 - p0
        r = {"fade_pm": {"all": acc(-dPM, up, np.ones(len(ev), bool)), "quiet": acc(-dPM, up, quiet)}}
        for fname, (T, p) in feeds.items():
            dS = live6.move_bp(T, p, m, W, 50)
            if fname.startswith("bnf_ETH"):
                dS = dS / 1.235  # ETH bp per BTC bp (BUILD slope, iteration 4)
            d = norm.ppf(np.clip(p0, 0.01, 0.99))
            best = None
            for sig in (0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0):
                delta = norm.pdf(d) / (sig * np.sqrt(np.maximum(tau, 5.0)))
                gap = delta * dS - dPM
                a_tr = acc(gap, up, half & quiet)
                if a_tr["acc"] is not None and (best is None or a_tr["acc"] > best[1]):
                    best = (sig, a_tr["acc"])
            sig = best[0] if best else 1.0
            delta = norm.pdf(d) / (sig * np.sqrt(np.maximum(tau, 5.0)))
            gap = delta * dS - dPM
            r[fname] = {"momentum_all": acc(dS, up, np.ones(len(ev), bool)), "momentum_quiet": acc(dS, up, quiet),
                        "value_sigma_bp_fit_half1": sig, "value_test_half2_quiet": acc(gap, up, ~half & quiet), "value_test_half2_all": acc(gap, up, ~half),
                        "value_all": acc(gap, up, np.ones(len(ev), bool)), "value_quiet": acc(gap, up, quiet)}
        res[f"W{W}"] = r
    return res


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    res = main(a, b)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_value_iter6.json")
    json.dump(res, open(out, "w"), indent=1, default=str)
    for k, v in res.items():
        if isinstance(v, dict):
            print(k, json.dumps(v)[:1500])
        else:
            print(k, v)
