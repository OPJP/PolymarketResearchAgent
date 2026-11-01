"""Iteration 6: out-of-sample replication of the microprice trigger on a LATER development interval (frozen definitions from
the first look, results_micro_iter6.json): matches = cluster taker fills with a recorded match ms (shared clob_crypto trade
records with the same tx hash); quiet = no move > 0.1 bp on any of the eight REST trade feeds over the last 1 s; trigger =
vote of tick-level (> 0.002 bp) microprice moves over [m - 600, m - 100) ms of the ten sized quote series of FEED
(BTC/ETH on Binance USD-M and spot, Bybit, OKX, Hyperliquid; ETH in BTC units). Placebo = same side labels at m +- U(5, 60) s.
Usage: python micro_rep6.py OWN_PARQUET START END VENUE_FEED"""
import os, sys, glob, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6
import sealed
C = L.C


def main(own_path, a, b, feed):
    d = live6.own_taker(own_path, a, b)
    tok, books, trades = L.load_books(a, b)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tok[t][1]); tk["is_up"] = tk.token.map(lambda t: tok[t][2])
    tk = tk[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in tk.start], bool)]
    tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()].sort_values("m").drop_duplicates(["tx", "token"])
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool)
    rng = np.random.default_rng(11)
    pl = m + (rng.choice([-1, 1], len(m)) * rng.uniform(5000, 60000, len(m))).astype(np.int64)
    MV = []
    for v, sym in [("bnf", "BTCUSDT"), ("bnf", "ETHUSDT"), ("bns", "BTCUSDT"), ("bns", "ETHUSDT"), ("cb", "BTC-USD"), ("cb", "ETH-USD"), ("okx", "BTC-USDT-SWAP"), ("okx", "ETH-USDT-SWAP")]:
        s = live6.series(sorted(glob.glob(f"{live6.P}/rest6_{v}_{sym}_*.parquet")))
        if s is not None:
            MV.append(live6.move_bp(s[0], s[1], m, 1000, 0))
    Mt = np.vstack(MV)
    quiet = ~(np.nanmax(np.abs(Mt), axis=0) > 0.1)
    rows = {}
    for r in L.recs(feed, a - 60, b):
        v = r.get("v")
        if v in ("bf", "by", "ok", "bs", "hl") and r.get("b") and r.get("a"):
            rows.setdefault((v, r["y"]), []).append((r.get("E") or 0, r["t"], r["b"], r.get("B") or 0, r["a"], r.get("A") or 0))
    off = None
    if ("bf", "BTC") in rows:
        x = np.array(rows[("bf", "BTC")], float); off = float(np.median(x[:, 1] - x[:, 0]))
    Q, Qp, cov = [], [], np.zeros(len(m), bool)
    for key, lst in sorted(rows.items()):
        x = np.array(lst, float)
        T = x[:, 0] if key[0] != "bs" else x[:, 1] - (off or 0)
        o = np.argsort(T, kind="stable"); x = x[o]; T = T[o].astype(np.int64)
        mic = (x[:, 2] * x[:, 5] + x[:, 4] * x[:, 3]) / np.maximum(x[:, 3] + x[:, 5], 1e-12)
        sc = 1.235 if key[1] == "ETH" else 1.0
        ins = (m > T[0] + 3000) & (m < T[-1] - 500)
        qa = live6.move_bp(T, mic, m, 500, 100) / sc; qb = live6.move_bp(T, mic, pl, 500, 100) / sc
        qa[~ins] = np.nan; qb[~ins] = np.nan
        Q.append(qa); Qp.append(qb); cov |= ins
    Q = np.vstack(Q); Qp = np.vstack(Qp)
    vote = np.nansum(np.sign(Q) * (np.abs(Q) > 0.002), axis=0); votep = np.nansum(np.sign(Qp) * (np.abs(Qp) > 0.002), axis=0)
    res = {"interval": [a, b], "feed": feed, "matches": int(len(m)), "covered": int(cov.sum()), "quiet_share_covered": round(float(quiet[cov].mean()), 4) if cov.any() else None}
    for lab, s in (("all", cov), ("quiet", cov & quiet), ("moving", cov & ~quiet)):
        k = s & (vote != 0)
        res[lab] = {"n": int(s.sum()), "cover": round(float(k.sum() / max(s.sum(), 1)), 4), "agree": round(float(((vote[k] > 0) == up[k]).mean()), 4) if k.any() else None}
    k = cov & (votep != 0)
    res["placebo"] = {"cover": round(float(k.sum() / max(cov.sum(), 1)), 4), "agree": round(float(((votep[k] > 0) == up[k]).mean()), 4) if k.any() else None}
    return res


if __name__ == "__main__":
    own_path, a, b, feed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    res = main(own_path, a, b, feed)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", f"results_micro_rep_iter6_{a}.json")
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))
