"""Iteration 7 (catalog A4b, first test): does Kalshi's BTC 15-minute market (KXBTC15M, public API, microsecond trade
times) move before the bot's taker matches? Development block 10-31 14:50-16:25 only. For each cluster taker match (m =
matching-engine ms, outcome o), the change of the Kalshi YES price (the 15-min window containing m) over
[m - 2000, m - 100) ms and [m - 600, m - 100) ms; side agreement with o where it moved, against placebo times.
Usage: python kalshi7.py"""
import os, sys, json, time
import numpy as np, pandas as pd, httpx
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6, sealed
API = "https://api.elections.kalshi.com/trade-api/v2"
A, B = 1793458200, 1793463900
assert not sealed.future_block_sealed(A) and not sealed.future_block_sealed(B - 1)


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def main():
    with httpx.Client(timeout=20) as c:
        mk = c.get(f"{API}/markets", params={"series_ticker": "KXBTC15M", "min_close_ts": A, "max_close_ts": B + 900, "limit": 100}).json().get("markets", [])
        rows = []
        for m in mk:
            o, cl = ts(m["open_time"]), ts(m["close_time"])
            if cl <= A or o >= B:
                continue
            cur = None
            for _ in range(40):
                p = {"ticker": m["ticker"], "limit": 1000, "min_ts": int(max(o, A - 60)), "max_ts": int(min(cl, B))}
                if cur:
                    p["cursor"] = cur
                j = c.get(f"{API}/markets/trades", params=p).json()
                for t in j.get("trades", []):
                    rows.append((m["ticker"], o, cl, ts(t["created_time"]) * 1000, float(t["yes_price_dollars"]), float(t.get("count_fp") or 0)))
                cur = j.get("cursor")
                if not cur:
                    break
                time.sleep(0.2)
    K = pd.DataFrame(rows, columns=["tk", "o", "cl", "ms", "yes", "n"]).sort_values("ms")
    res = {"kalshi_markets": int(K.tk.nunique()), "kalshi_trades": int(len(K))}
    d = live6.own_taker(".cache/re/btc5m-bot/post/own_1793458200_1793462700.parquet", A, 1793462640)
    d2 = live6.own_taker(".cache/re/btc5m-bot/post/own_1793462640_1793464380.parquet", 1793462640, B)
    d = pd.concat([d, d2])
    tok, books, trades = L.load_books(A, B)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["is_up"] = tk.token.map(lambda t: tok[t][2]); tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()].drop_duplicates(["tx", "token"])
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool)
    rng = np.random.default_rng(11)
    pl = m + (rng.choice([-1, 1], len(m)) * rng.uniform(5000, 60000, len(m))).astype(np.int64)
    res["matches"] = int(len(m))

    def yes_at(t):
        out = np.full(len(t), np.nan)
        for tkr, g in K.groupby("tk"):
            o, cl = g.o.iloc[0] * 1000, g.cl.iloc[0] * 1000
            sel = (t >= o) & (t < cl)
            if not sel.any():
                continue
            T = g.ms.to_numpy(); Y = g.yes.to_numpy()
            i = np.searchsorted(T, t[sel], "right") - 1
            v = np.where(i >= 0, Y[np.clip(i, 0, len(Y) - 1)], np.nan)
            out[sel] = v
        return out
    for nm, w0 in (("[m-2000,m-100)", 2000), ("[m-600,m-100)", 600)):
        for lab, tt in (("match", m), ("placebo", pl)):
            dy = yes_at(tt - 100) - yes_at(tt - w0)
            mvd = np.isfinite(dy) & (np.abs(dy) >= 0.005)
            res[f"{nm}_{lab}"] = {"moved_share": round(float(mvd.mean()), 4), "agree": round(float(((dy[mvd] > 0) == up[mvd]).mean()), 4) if mvd.any() else None, "n_moved": int(mvd.sum())}
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "kalshi7.json"), "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
