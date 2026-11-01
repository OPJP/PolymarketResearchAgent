"""X229 step 2 (assumptions panel iter-15 P3): split the wallet's V-change decisions (dark_split rows, 16-22 Oct) by the
clock of the visible message. For each decision with a wallet-free group-P take on the event signed in the 3 s before
it (agreeing in direction: 'visible_agree'), lag = decision - take signing: class 1 (co-sign, 0-100 ms), class 2 (inside
the 1-s delay, 0.1-1.04 s: before the take's CLOB match), class 3 (after the match, 1.04-3 s). Shares, excess over a
take times shifted by +-30..120 s null, and the 60-s markout (clean print move in the decision's direction, cents) per
class; dark = no group-P take in the 3 s before. Output: results/message_classes.json"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
CODE = ROOT / "research/reverse_engineering/tommy-cs2-maker/code"
sys.path.insert(0, str(CODE / "iter4"))
sys.path.insert(0, str(CODE))
from queue_replay import load_record  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
SP = Path(r"C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/m14/dark_split.parquet")
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
GP = set(json.load(open(CODE / "final_rule_v5_groupP.json"))["members"])
BINS = [("class1_cosign_0_100ms", 0.0, 0.1), ("class2_in_delay_0.1_1.04s", 0.1, 1.04), ("class3_after_match_1.04_3s", 1.04, 3.0)]


def main():
    d = pd.read_parquet(SP)
    cd, _ = load_record()
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "event"]).drop_duplicates("cid")
    ev_of = dict(zip(o.cid, o.event))
    wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"]).query("maker == @W").tx)
    tk = cd[(cd.idx == -1) & (cd.sign_ms > 1.7e12) & ~cd.tx.isin(wtx)].drop_duplicates("tx").copy()
    tk = tk[tk.maker.str.lower().isin(GP)]
    tk["event"] = tk.cid.map(ev_of)
    tk = tk[tk.event.notna()]
    take_t = {ev: np.sort(g.sign_ms.to_numpy(float) / 1000.0) for ev, g in tk.groupby("event")}
    rng = np.random.default_rng(229)
    out = {}
    for per, X in d.groupby("period"):
        t = X.t.to_numpy(float) / 1000.0
        ev = X.event.to_numpy()
        lag = np.full(len(X), np.nan)
        lag_null = np.full(len(X), np.nan)
        for e in np.unique(ev):
            k = ev == e
            tt = take_t.get(e)
            if tt is None or not len(tt):
                continue
            for arr, shift in ((lag, 0.0), (lag_null, None)):
                tq = t[k] - (0.0 if shift is not None else rng.choice([-1, 1], k.sum()) * rng.uniform(30, 120, k.sum()))
                j = np.searchsorted(tt, tq, side="right") - 1
                ok = j >= 0
                v = np.full(k.sum(), np.nan)
                v[ok] = tq[ok] - tt[j[ok]]
                arr[k] = v
        agree = (X.vis == "visible_agree").to_numpy()
        res = {"n": int(len(X)), "dark_share": round(float((X.vis == "dark").mean()), 3),
               "dark_m60_c": round(float(X.loc[X.vis == "dark", "m60"].mean()), 2)}
        for nm, a, b in BINS:
            m = agree & (lag >= a) & (lag < b)
            mn = (lag_null >= a) & (lag_null < b)
            res[nm] = {"n": int(m.sum()), "share_of_all": round(float(m.mean()), 4), "any_take_share": round(float(((lag >= a) & (lag < b)).mean()), 4),
                       "null_share": round(float(mn.mean()), 4), "m60_c": round(float(X.m60.to_numpy()[m].mean()), 2) if m.any() else None}
        out[per] = res
    (RES / "message_classes.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
