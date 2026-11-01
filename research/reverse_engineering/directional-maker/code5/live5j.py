"""Live lab part j: null for the size fingerprint. For each cluster maker order (calldata size S, limit, token; server
match time from the raw x records), P(an add of exactly S at its level within X ms before the match) vs the same level
and size at the match time shifted by -20 s / -60 s (time-shift null), for X in 250 / 1000 / 5000 ms."""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live5  # noqa

def main(a, b):
    ev, tr, bk = live5.load_clob(a, b)
    act, cd = live5.cluster_orders(a, b)
    mk = cd[cd.role == "maker"].drop_duplicates(subset=["tx", "maker", "salt"])
    tx_s = tr.groupby("h").s.min()
    tok = {str(r.asset): (r.slug, r.outcome) for r in act.itertuples()}
    evg = {k: (g.s.to_numpy(), g.d.to_numpy()) for k, g in ev[ev.d > 0].groupby(["w", "side", "p"])}
    rows = []
    for r in mk.itertuples(index=False):
        sm = tx_s.get(r.tx); t = tok.get(str(r.token_id))
        if sm is None or t is None: continue
        slug, outc = t
        key = (slug, 1, round(r.lim, 2)) if outc == "Up" else (slug, 0, round(1 - r.lim, 2))
        x = evg.get(key)
        def found(T, X):
            if x is None: return False
            s_, d_ = x; i0, i1 = np.searchsorted(s_, T - X), np.searchsorted(s_, T, side="right")
            return bool(np.any(np.abs(d_[i0:i1] - r.S) < 0.01))
        rows.append({"S": r.S, **{f"f{X}": found(sm, X) for X in (250, 1000, 5000)}, **{f"n20_{X}": found(sm - 20000, X) for X in (250, 1000, 5000)},
                     **{f"n60_{X}": found(sm - 60000, X) for X in (250, 1000, 5000)}})
    d = pd.DataFrame(rows)
    res = {"orders": int(len(d)), "sizes": d.S.round(0).value_counts().head(5).to_dict()}
    for X in (250, 1000, 5000):
        res[f"within_{X}ms"] = {"cluster_at_match": round(float(d[f"f{X}"].mean()), 3), "null_shift_20s": round(float(d[f"n20_{X}"].mean()), 3),
                                "null_shift_60s": round(float(d[f"n60_{X}"].mean()), 3)}
    big = d[d.S.round(0).isin([500, 100])]
    res["500_100_only_within_1000ms"] = {"n": int(len(big)), "cluster": round(float(big.f1000.mean()), 3), "null20": round(float(big.n20_1000.mean()), 3)}
    odd = d[~d.S.round(0).isin([500, 100])]
    res["remainder_sizes_within_1000ms"] = {"n": int(len(odd)), "cluster": round(float(odd.f1000.mean()), 3) if len(odd) else None, "null20": round(float(odd.n20_1000.mean()), 3) if len(odd) else None}
    print(json.dumps(res, indent=1))
    (HERE.parent / "results" / f"iter5_live_j_{a}_{b}.json").write_text(json.dumps(res, indent=1))

if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
