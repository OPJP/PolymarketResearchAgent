"""Iteration 6, economics of the Chainlink-skewed quote (live block, descriptive): are the cluster's fills adversely
selected when its Chainlink-based fair is above the faster futures-based fair?
For each cluster BTC 5m maker fill with a match ms (code6/i1_price_match.py output) from 14:06 UTC: gap = Chainlink fair
of the token (value stamped <= t-2 s, true strike) - futures fair of the token (bookTicker mid at t, futures TWAP strike).
Outcome per window from the RTDS TWAP-60 (Up iff TWAP stamped at the end >= TWAP stamped at the start, the settlement
rule). Reported by gap bucket: fills, mean price, win rate, payout - price per share, $ PnL, and the 60-s markout
(Chainlink fair at t+60 s - price).
    python code6/gap_markout.py <i1_a> <i1_b>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
from rawread import iter_dm  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"


def main(a, b):
    M = pd.read_parquet(C / "it6" / f"i1_fills_{a}_{b}.parquet")
    acts = pd.concat([pd.read_parquet(p) for p in (C).glob("live_activity_*.parquet")]).drop_duplicates(
        subset=["transactionHash", "asset", "w", "size", "price"])
    acts["tx"] = acts.transactionHash.str.lower()
    s0 = 1793455600
    M = M[M.ms >= s0 * 1000].copy()
    fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", s0 - 400, b + 400) if r["r"][0] == "b" and r["r"][2]]
    fu = pd.DataFrame(fut, columns=["s", "m"]).sort_values("s").drop_duplicates("s", keep="last")
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))
    cl, tw = {}, {}
    for r in iter_dm("dm_rtds", s0 - 400, b + 400):
        try:
            j = json.loads(r["m"])
        except ValueError:
            continue
        for x in (j.get("payload") or {}).get("data", []) or []:
            (cl if r["q"] == "crypto_prices_chainlink" else tw)[int(x["timestamp"]) // 1000] = float(x["value"])
    cls = np.array(sorted(cl))
    clv = np.array([cl[k] for k in cls])
    # windows: from the fills' match time (BTC 5m windows are 300-s aligned)
    M["st"] = (M.ms // 1000) // 300 * 300
    rows = []
    for r in M.itertuples(index=False):
        st, t = int(r.st), int(r.ms)
        K_c, K_e = tw.get(st), tw.get(st + 300)
        if K_c is None:
            continue
        jj = np.searchsorted(sec, t // 1000)
        sig = np.std(r1[max(jj - 300, 0):jj]) * 1.4
        tau = max(st + 300 - t / 1000, 1.0)
        K_f = ms_sec[np.searchsorted(sec, st - 60):np.searchsorted(sec, st)].mean()
        fmid = fm[max(np.searchsorted(fs, t, side="right") - 1, 0)]
        k = np.searchsorted(cls, t // 1000 - 2, side="right") - 1
        k60 = np.searchsorted(cls, t // 1000 + 60, side="right") - 1
        if k < 0 or not sig > 0:
            continue
        fc = norm.cdf(np.log(clv[k] / K_c) / (sig * np.sqrt(tau)))
        ff = norm.cdf(np.log(fmid / K_f) / (sig * np.sqrt(tau)))
        tau60 = max(tau - 60, 1.0)
        fc60 = norm.cdf(np.log(clv[k60] / K_c) / (sig * np.sqrt(tau60))) if k60 >= 0 else np.nan
        isup = bool(r.isup)
        won = np.nan if K_e is None else float((K_e >= K_c) == isup)
        sgn = 1 if isup else -1
        fc_s, ff_s = (fc if isup else 1 - fc), (ff if isup else 1 - ff)
        rows.append({"gap": fc_s - ff_s, "price": r.price, "size": r.size, "won": won, "edge_c": fc_s - r.price, "edge_f": ff_s - r.price,
                     "mk60": ((fc60 if isup else 1 - fc60) - r.price) if fc60 == fc60 else np.nan})
    D = pd.DataFrame(rows).dropna(subset=["won"])
    D["pnl"] = (D.won - D.price) * D["size"]
    D["b"] = pd.cut(D.gap, [-1, -0.03, -0.01, 0.01, 0.03, 1], labels=["<-3c", "-3..-1c", "-1..1c", "1..3c", ">3c"])
    agg = D.groupby("b", observed=True).agg(n=("pnl", "size"), price=("price", "mean"), win=("won", "mean"), pnl=("pnl", "sum"),
                                            usd=("price", lambda s: float((s * D.loc[s.index, "size"]).sum())), mk60=("mk60", "mean"),
                                            edge_c=("edge_c", "mean"), edge_f=("edge_f", "mean"))
    agg["ret"] = agg.pnl / agg.usd
    out = {"fills": int(len(D)), "windows": int(D.shape[0] and M.st.nunique()), "total_pnl": round(float(D.pnl.sum()), 1),
           "total_ret": round(float(D.pnl.sum() / (D.price * D["size"]).sum()), 4), "gap_q": D.gap.quantile([.1, .5, .9]).round(3).to_dict(),
           "by_gap": agg.round(4).to_dict("index"), "edge_c_mean": round(float(D.edge_c.mean()), 4), "edge_f_mean": round(float(D.edge_f.mean()), 4),
           "corr_pnl_per_share_vs_edge_c": round(float(np.corrcoef(D.won - D.price, D.edge_c)[0, 1]), 3),
           "corr_pnl_per_share_vs_edge_f": round(float(np.corrcoef(D.won - D.price, D.edge_f)[0, 1]), 3)}
    out = json.loads(json.dumps(out, default=str))
    (HERE.parent / "results" / f"iter6_gap_markout_{a}_{b}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
