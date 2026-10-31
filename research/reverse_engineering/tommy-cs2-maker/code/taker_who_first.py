"""Who signs first: its taker orders vs other takers buying the same team in the same market within +-10 s
(signing times from the decoded calldata of every taker tx). Positive = the other taker signed after it.
Also for random control times. Development data."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RES, WALLET, SPLIT  # noqa: E402
from maker_compare import load_all  # noqa: E402

def main():
    a = load_all()
    a = a[a.cid.notna() & (a.sign_ms > 1.7e12) & (a.sign_ms < 1.8e12) & (a.idx == -1)].copy()
    a["o"] = np.where(a.side == 0, a.oi, 1 - a.oi).astype(int)  # team bought (SELL of a token = buying the other)
    a = a.drop_duplicates(["maker", "sign_ms", "token_id", "price"])
    me = a[a.maker == WALLET]; ot = a[a.maker != WALLET]
    lags, lags_opp, firsts = [], [], []
    for cid, g in me.groupby("cid"):
        h = ot[ot.cid == cid]
        ht = h.sign_ms.to_numpy() / 1000; ho = h.o.to_numpy()
        for t, team in zip(g.sign_ms / 1000, g.o):
            m = (ht >= t - 10) & (ht <= t + 10)
            same = m & (ho == team); opp = m & (ho != team)
            lags += list(ht[same] - t); lags_opp += list(ht[opp] - t)
            if same.any():
                firsts.append(float(np.min(ht[same]) - t))
    lags = np.array(lags); fi = np.array(firsts)
    bins = [-10, -5, -3, -2, -1, -0.5, 0, 0.5, 1, 2, 3, 5, 10]
    res = {"n_my_taker": int(len(me)), "n_same_team_others_10s": int(len(lags)), "n_opp_team_others_10s": int(len(lags_opp)),
           "same_team_lag_hist": dict(zip([str(b) for b in bins[:-1]], np.histogram(lags, bins)[0].tolist())),
           "share_others_after_me": round(float((lags > 0).mean()), 3),
           "orders_with_same_team_other_within_10s": int(len(fi)),
           "earliest_other_minus_me_q": pd.Series(fi).quantile([.1, .25, .5, .75, .9]).round(2).to_dict(),
           "share_me_first": round(float((fi > 0).mean()), 3)}
    json.dump(res, open(RES / "results/taker_who_first.json", "w"), indent=1)
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
