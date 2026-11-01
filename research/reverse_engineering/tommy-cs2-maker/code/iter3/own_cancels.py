"""Iteration 3, X26 / X34: are the 100-share cancels stamped 13-16 ms after the wallet's taker signing its OWN
complement bids (one client: FAK on team X + cancel of its bids on team Y)?

Own recorder (server clock, 10-31 14:50 UTC on), the wallet's dev-unit markets. Cancels = level decreases without a
trade print within 150 ms. Tests:
 (1) share of the wallet's taker orders followed by a size-100 cancel on the consumed side within [0, 40] ms, vs the
     same window after pack taker orders (same markets) and after random times;
 (2) of all size-100 cancels in these books, the share that falls in [0, 40] ms after a wallet taker signing;
 (3) the price of the cancelled level as a complement-token bid vs the wallet's re-pair bids (its filled complement
     maker orders signed 0.5-2 s after the take): cancelled price minus re-posted price (cents);
 (4) size-100 cancels on the NON-consumed side (its bids on the team it buys) in the same window.
Output: results/own_cancels.json
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, PACK, read  # noqa: E402

OWN0 = 1793458232000


def main():
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    m = m[m.wallet_trades > 0]
    tok = {}
    for r in m.itertuples():
        tok[r.tok0] = (r.cid, 0, r.tok0)
        tok[r.tok1] = (r.cid, 1, r.tok0)
    tok0 = set(m.tok0)
    ow = read("tommy_cs2_near", tok0, OWN0 / 1000, time.time())
    trades = defaultdict(list)
    for r in ow:
        if r["k"] == "x":
            trades[r["a"]].append(r["s"])
    trades = {a: np.sort(np.array(v, float)) for a, v in trades.items()}
    dec, books = [], {}
    for r in sorted([r for r in ow if r["k"] in ("f", "pc")], key=lambda r: (r["s"], r["t"])):
        a = r["a"]
        if r["k"] == "f":
            books[a] = ({float(p): float(z) for p, z in r["b"]}, {float(p): float(z) for p, z in r["o"]})
            continue
        if a not in books:
            continue
        bd, od = books[a]
        for side, p, z in r["c"]:
            bk = bd if side == "BUY" else od
            p, z = float(p), float(z)
            old = bk.get(p, 0.0)
            if z < old - 1e-9:
                tr = trades.get(a, np.array([]))
                k = np.searchsorted(tr, r["s"] - 150)
                if not (k < len(tr) and tr[k] <= r["s"] + 150):
                    dec.append((a, side, r["s"], p, round(old - z, 2)))
            if z == 0:
                bk.pop(p, None)
            else:
                bk[p] = z
    D = pd.DataFrame(dec, columns=["a", "side", "s", "p", "dz"])
    D100 = D[D.dz == 100]
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    d = d[(d.sign_ms >= OWN0 + 2000) & (d.sign_ms < 1.8e12) & d.token_id.astype(str).isin(tok)]
    tk = d[d.idx == -1].drop_duplicates("tx").copy()
    tk["a"] = tk.token_id.astype(str).map(lambda t: tok[t][2])
    tk["oi"] = tk.token_id.astype(str).map(lambda t: tok[t][1])
    tk["team"] = np.where(tk.side == 0, tk.oi, 1 - tk.oi)
    wm = d[(d.idx >= 0) & (d.maker == WALLET)].drop_duplicates(["salt", "sign_ms"]).copy()
    wm["a"] = wm.token_id.astype(str).map(lambda t: tok[t][2])
    wm["oi"] = wm.token_id.astype(str).map(lambda t: tok[t][1])
    res = {}
    rng = np.random.default_rng(11)
    for grp, sel in (("wallet", tk.maker == WALLET), ("pack", tk.maker.isin(PACK)), ("other", ~tk.maker.isin(PACK | {WALLET}))):
        g = tk[sel]
        hit_c, hit_o, n_c = [], [], []
        for r in g.itertuples():
            cons = "SELL" if r.team == 0 else "BUY"
            oth = "BUY" if cons == "SELL" else "SELL"
            x = D100[(D100.a == r.a) & (D100.s >= r.sign_ms) & (D100.s <= r.sign_ms + 40)]
            hit_c.append(bool((x.side == cons).any()))
            hit_o.append(bool((x.side == oth).any()))
            n_c.append(int((x.side == cons).sum()))
        res[grp] = {"orders": int(len(g)), "size100_cancel_consumed_side_0_40ms": round(float(np.mean(hit_c)), 3) if hit_c else None,
                    "size100_cancel_other_side_0_40ms": round(float(np.mean(hit_o)), 3) if hit_o else None,
                    "mean_count_consumed": round(float(np.mean(n_c)), 2) if n_c else None}
    ctrl = []
    for r in tk[tk.maker == WALLET].itertuples():
        cons = "SELL" if r.team == 0 else "BUY"
        for t in r.sign_ms + rng.uniform(-900000, -60000, 20):
            x = D100[(D100.a == r.a) & (D100.side == cons) & (D100.s >= t) & (D100.s <= t + 40)]
            ctrl.append(len(x) > 0)
    res["random_time_size100_cancel_0_40ms"] = round(float(np.mean(ctrl)), 4)
    # (2) share of all size-100 cancels that sit 0-40 ms after a wallet taker signing (any side) in the same market
    ws = tk[tk.maker == WALLET]
    near = []
    for q in D100.itertuples():
        s = ws[ws.a == q.a].sign_ms.to_numpy()
        near.append(bool(((q.s - s >= 0) & (q.s - s <= 40)).any()))
    res["size100_cancels_total"] = int(len(D100))
    res["share_of_size100_cancels_within_0_40ms_after_wallet_take"] = round(float(np.mean(near)), 3) if near else None
    res["all_cancels_total"] = int(len(D))
    # (3) cancelled complement price vs re-posted complement bids 0.5-2 s later
    diffs = []
    for r in ws.itertuples():
        cons = "SELL" if r.team == 0 else "BUY"
        x = D100[(D100.a == r.a) & (D100.side == cons) & (D100.s >= r.sign_ms) & (D100.s <= r.sign_ms + 40)]
        if not len(x):
            continue
        cprice = (1 - x.p) if r.team == 0 else x.p  # as a bid on the complement token (team 1 - team)
        rep = wm[(wm.a == r.a) & (wm.oi == 1 - r.team) & (wm.sign_ms >= r.sign_ms + 500) & (wm.sign_ms <= r.sign_ms + 2000)]
        if len(rep):
            diffs.append(round((float(cprice.max()) - float(rep.price.max())) * 100))
    res["cancelled_minus_reposted_top_complement_bid_cents"] = {"n": len(diffs), "values": sorted(diffs)}
    json.dump(res, open(RES / "own_cancels.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
