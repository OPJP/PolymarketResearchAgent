"""Iteration 8, X116 (assumptions panel iter7 P5): discrete message kinds vs a continuous private fair value.
BUILD-live (10-31 14:50-18:00, the 7 recorded token-0 books). Unit: 1-s steps per book while the wallet has validated
own levels on it. y = a wallet take on that market in (t, t + 5 s]. Features: the number of validated UNTRIGGERED own
pulls (trig_code 0) on the book in [t - W, t) for W = 10 / 30 / 60 s, and their signed count (+1 when the pulled bids
are token-1 bids, i.e. the pull favours token 0); controls: non-own level events on the book in [t - 30, t) (public
activity) and trades. Dose-response = the take hazard by untriggered-pull count bins; direction = the share of takes
whose bought token matches the sign of the preceding signed count. Null for direction: 2,000 within-book shifts.
Output: results/accumulation.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
SUF = os.environ.get("TOMMY_BLOCK_SUFFIX", "")
# block parameters as in code/iter7 (TOMMY_BLOCK_START / TOMMY_BLOCK_END unix s; defaults = BUILD-live)
OWN0 = int(os.environ.get("TOMMY_BLOCK_START", 1793458232)) * 1000
END = int(os.environ.get("TOMMY_BLOCK_END", 1793469600)) * 1000


def main():
    B = pd.read_parquet(OUT / f"own_bursts_markouts_dev{SUF}.parquet")
    dm = pd.read_parquet(OUT / f"dev_markets{SUF}.parquet")
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet")
    E = pd.read_parquet(OUT / f"level_events_dev{SUF}.parquet", columns=["a", "s", "kind"])
    books = sorted(set(B.a))
    tok = {str(r.tok0): (str(r.tok0), 0) for r in dm.itertuples()}
    tok.update({str(r.tok1): (str(r.tok0), 1) for r in dm.itertuples()})
    cd["tok"] = cd.token_id.astype(str)
    tk = cd[(cd.idx == -1) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(tok)].drop_duplicates("tx")
    tk = tk.assign(a=tk.tok.map(lambda t: tok[t][0]), oi=tk.tok.map(lambda t: tok[t][1]))
    tk = tk[tk.a.isin(books)]
    P = B[(B.kind == "pull")]
    U = P[P.trig_code == 0]
    rows = []
    for a in books:
        own = B[B.a == a]
        lo, hi = max(own.s.min(), OWN0), min(own.s.max(), END)
        t = np.arange(lo, hi, 1000.0)
        us = np.sort(U[U.a == a].s.to_numpy(float))
        sg = np.where(U[U.a == a].sort_values("s").side.to_numpy() == "SELL", 1.0, -1.0)  # + favours token 0
        cs = np.concatenate([[0.0], np.cumsum(sg)])
        ev = np.sort(E[(E.a == a)].s.to_numpy(float))
        tr = np.sort(E[(E.a == a) & (E.kind == "cons")].s.to_numpy(float))
        ts = np.sort(tk[tk.a == a].sign_ms.to_numpy(float))
        f = {"a": a, "t": t}
        for W in (10, 30, 60):
            i1, i0 = np.searchsorted(us, t), np.searchsorted(us, t - W * 1000)
            f[f"n{W}"] = i1 - i0
            f[f"sg{W}"] = cs[i1] - cs[i0]
        f["pub30"] = np.searchsorted(ev, t) - np.searchsorted(ev, t - 30000)
        f["tr30"] = np.searchsorted(tr, t) - np.searchsorted(tr, t - 30000)
        f["y"] = (np.searchsorted(ts, t + 5000, side="right") - np.searchsorted(ts, t, side="right")) > 0
        rows.append(pd.DataFrame(f))
    X = pd.concat(rows, ignore_index=True)
    res = {"steps": int(len(X)), "takes": int(len(tk)), "untrig_pulls": int(len(U)), "base_rate": round(float(X.y.mean()), 4)}
    for W in (10, 30, 60):
        b = pd.cut(X[f"n{W}"], [-1, 0, 1, 2, 100], labels=["0", "1", "2", "3+"])
        res[f"hazard_by_n{W}"] = {str(k): [round(float(g.y.mean()), 4), int(len(g))] for k, g in X.groupby(b, observed=True)}
    import statsmodels.api as sm
    for W in (10, 30, 60):
        Z = sm.add_constant(np.column_stack([np.log1p(X[f"n{W}"]), np.log1p(X.pub30), np.log1p(X.tr30)]))
        try:
            m = sm.Logit(X.y.astype(float), Z).fit(disp=0)
            res[f"logit_n{W}"] = {"coef_log1p_untrig": [round(float(m.params.iloc[1]), 3), round(float(m.pvalues.iloc[1]), 4)],
                                  "coef_log1p_pub30": [round(float(m.params.iloc[2]), 3), round(float(m.pvalues.iloc[2]), 4)],
                                  "coef_log1p_trades30": [round(float(m.params.iloc[3]), 3), round(float(m.pvalues.iloc[3]), 4)]}
        except Exception as e:  # noqa: BLE001
            res[f"logit_n{W}"] = str(e)[:100]
    # direction: does the take buy the token favoured by the signed count before it?
    rng = np.random.default_rng(9)
    for W in (10, 30, 60):
        al, n = [], 0
        for r in tk.itertuples():
            us = U[U.a == r.a].sort_values("s")
            m = (us.s >= r.sign_ms - W * 1000) & (us.s < r.sign_ms)
            sgn = float(np.where(us.side.to_numpy()[m.to_numpy()] == "SELL", 1.0, -1.0).sum())
            if sgn != 0:
                al.append((sgn > 0) == (r.oi == 0))
        nul = []
        for _ in range(500):
            z = []
            for r in tk.itertuples():
                us = U[U.a == r.a]
                t0 = r.sign_ms + rng.choice([-1, 1]) * rng.uniform(60000, 600000)
                m = (us.s >= t0 - W * 1000) & (us.s < t0)
                sgn = float(np.where(us.side.to_numpy()[m.to_numpy()] == "SELL", 1.0, -1.0).sum())
                if sgn != 0:
                    z.append((sgn > 0) == (r.oi == 0))
            nul.append(np.mean(z) if z else np.nan)
        res[f"direction_W{W}"] = {"takes_with_signed_pulls": len(al), "aligned_share": round(float(np.mean(al)), 3) if al else None,
                                  "null_aligned_mean": round(float(np.nanmean(nul)), 3),
                                  "p_upper": round(float(np.nanmean(np.array(nul) >= np.mean(al))), 4) if al else None}
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / f"accumulation{SUF}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
