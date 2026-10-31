"""Iteration 4, X45 (mechanics iter3 P3) and X48a (assumptions iter3 P2a): is the FAK limit the bot's private estimate
of the post-event value?

16-22 Oct (development). Taker orders of the wallet (calldata_all, idx -1, BUY): limit L, stale ask a = the lowest
ask-equivalent price it was filled at (first matched level), premium = L - a (cents). Public price path of the bought
team from the windowed taker tapes, every tx that contains a wallet order excluded, last print at sign + h for
h = 10, 30, 60, 120 s (block time), mirrored to the bought outcome.
Reported per split (BUILD gs < 10-21, VALIDATE 10-21..22):
  * mean move (p_h - a) by premium bucket and the gap p_h - L ("does the price level off at its limit?");
  * Spearman(premium, move_h) with an event bootstrap (2,000 draws);
  * the same for other takers' BUY orders in the same markets (calldata_pub), as the control: is premium-scaling
    specific to the wallet (a private valuation) or shared by every aggressive taker?
  * fan-out pairs (map + match legs signed <= 5 ms apart): premium ratio match / map by map number, against the
    series sensitivity S = P(series | win map) - P(series | lose map) with q = 0.5 (maps 1-2: 0.5; map 3: 1.0).
Output: results/premium_value.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0, H = 1792540800, 1792713600
HS = (10, 30, 60, 120)


def takers(cd, wallet_only):
    t = cd[(cd.idx == -1) & (cd.side == 0)]
    t = t[(t.maker == WALLET) if wallet_only else (t.maker != WALLET)]
    mk = cd[cd.idx >= 0]
    # ask-equivalent on the bought token X: maker SELL X at p -> p ; maker BUY complement at q -> 1 - q
    tx_tok = dict(zip(t.tx, t.oi))
    mk = mk[mk.tx.isin(tx_tok)].copy()
    x = mk.tx.map(tx_tok)
    mk["aeq"] = np.where((mk.side == 1) & (mk.oi == x), mk.price, np.where((mk.side == 0) & (mk.oi != x), 1 - mk.price, np.nan))
    a = mk.groupby("tx").aeq.min()
    t = t.drop_duplicates("tx").copy()
    t["a"] = t.tx.map(a)
    t = t[t.a.notna() & (t.sign_ms > 1.7e12) & (t.sign_ms < 1.8e12)]
    t["prem_c"] = np.round((t.price - t.a) * 100).astype(int)
    return t


def main():
    cols = ["tx", "idx", "maker", "side", "token_id", "price", "shares", "sign_ms", "fill"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)
    b = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted((OUT / "calldata_pub").glob("*.parquet"))])
    cd = pd.concat([a, b[~b.tx.isin(set(a.tx))]], ignore_index=True)
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "token_id", "oi", "gs_ts", "event", "smt"]).drop_duplicates("token_id")
    tok = {str(k): v for k, v in zip(o.token_id, zip(o.cid, o.oi, o.gs_ts, o.event, o.smt))}
    cd["tok"] = cd.token_id.astype(str)
    cd = cd[cd.tok.isin(tok)].copy()
    for i, c in enumerate(["cid", "oi", "gs", "event", "smt"]):
        cd[c] = cd.tok.map(lambda t: tok[t][i])
    own_tx = set(cd.loc[cd.maker == WALLET, "tx"])
    # price paths per market (block-time taker prints, wallet txs excluded), outcome-0 price
    path = {}
    for cid in cd.cid.unique():
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p, columns=["transactionHash", "timestamp", "outcomeIndex", "price"])
        d = d[~d.transactionHash.isin(own_tx)].sort_values("timestamp", kind="stable")
        p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        path[cid] = (d.timestamp.to_numpy(float), p0)

    def moves(t):
        rows = []
        for r in t.itertuples():
            pp = path.get(r.cid)
            if pp is None:
                continue
            ts, p0 = pp
            rec = {"tx": r.tx, "cid": r.cid, "event": r.event, "gs": r.gs, "smt": r.smt, "prem": r.prem_c, "L": r.price,
                   "a": r.a, "sign": r.sign_ms}
            for h in HS:
                k = np.searchsorted(ts, r.sign_ms / 1000 + h, side="right") - 1
                if k < 0 or ts[k] < r.sign_ms / 1000:
                    rec[f"p{h}"] = np.nan
                    continue
                v = p0[k] if r.oi == 0 else 1 - p0[k]
                rec[f"p{h}"] = v
            rows.append(rec)
        x = pd.DataFrame(rows)
        for h in HS:
            x[f"mv{h}"] = (x[f"p{h}"] - x.a) * 100
            x[f"gapL{h}"] = (x[f"p{h}"] - x.L) * 100
        return x

    res = {}
    W = moves(takers(cd, True))
    O = moves(takers(cd, False))
    rng = np.random.default_rng(7)
    for split, f in (("BUILD", lambda x: x.gs < VAL0), ("VALIDATE", lambda x: (x.gs >= VAL0) & (x.gs < H))):
        out = {}
        for lab, X in (("wallet", W), ("other_takers", O)):
            x = X[f(X)].copy()
            x = x[(x.prem >= 0) & (x.prem <= 10)]
            x["pb"] = np.minimum(x.prem, 5)
            o2 = {"n": int(len(x)), "premium_share": {str(k): round(float(v), 3) for k, v in x.pb.value_counts(normalize=True).sort_index().items()}}
            for h in HS:
                y = x[np.isfinite(x[f"mv{h}"])]
                rho = stats.spearmanr(y.prem, y[f"mv{h}"])[0] if len(y) > 10 else np.nan
                ev = y.event.unique()
                bs = []
                if lab == "wallet" and len(ev) > 5:
                    gi = {e: y.index[y.event == e] for e in ev}
                    for _ in range(1000):
                        pick = rng.choice(ev, len(ev))
                        z = y.loc[np.concatenate([gi[e] for e in pick])]
                        bs.append(stats.spearmanr(z.prem, z[f"mv{h}"])[0])
                o2[f"h{h}"] = {"spearman_prem_move": round(float(rho), 3),
                               "ci95": [round(float(np.nanpercentile(bs, 2.5)), 3), round(float(np.nanpercentile(bs, 97.5)), 3)] if bs else None,
                               "mean_move_c_by_prem": {str(k): round(float(g[f"mv{h}"].mean()), 2) for k, g in y.groupby("pb")},
                               "mean_gap_to_limit_c_by_prem": {str(k): round(float(g[f"gapL{h}"].mean()), 2) for k, g in y.groupby("pb")},
                               "median_gap_to_limit_c_by_prem": {str(k): round(float(g[f"gapL{h}"].median()), 2) for k, g in y.groupby("pb")}}
            out[lab] = o2
        res[split] = out
    # fan-out pairs
    w = W.copy()
    w["is_map"] = w.smt.eq("child_moneyline")
    pairs = []
    for ev, g in w.groupby("event"):
        mp = g[g.is_map].sort_values("sign")
        mt = g[~g.is_map].sort_values("sign")
        if len(mp) == 0 or len(mt) == 0:
            continue
        for r in mp.itertuples():
            j = np.argmin(np.abs(mt.sign.to_numpy() - r.sign))
            if abs(mt.sign.iloc[j] - r.sign) <= 5:
                pairs.append({"event": ev, "gs": r.gs, "cid_map": r.cid, "prem_map": r.prem, "prem_match": int(mt.prem.iloc[j]),
                              "a_map": r.a, "a_match": float(mt.a.iloc[j])})
    P = pd.DataFrame(pairs)
    # map number from the market slug (game1..3) via Gamma slugs in markets_dev.json
    mj = json.load(open(OUT / "markets_dev.json"))
    num = {}
    for cid, x in mj.items():
        s = str(x.get("slug") or "")
        num[cid] = int(s.rsplit("game", 1)[1][:1]) if "-game" in s else None
    if len(P):
        P["mapno"] = P.cid_map.map(num)
        fo = {"pairs": int(len(P))}
        for k, g in P.groupby("mapno"):
            g2 = g[g.prem_map > 0]
            fo[f"map{int(k)}"] = {"n": int(len(g)), "n_map_prem_pos": int(len(g2)),
                                 "mean_prem_map_c": round(float(g.prem_map.mean()), 2), "mean_prem_match_c": round(float(g.prem_match.mean()), 2),
                                 "ratio_of_means": round(float(g.prem_match.mean() / max(g.prem_map.mean(), 1e-9)), 2),
                                 "spearman": round(float(stats.spearmanr(g.prem_map, g.prem_match)[0]), 3) if len(g) > 5 else None,
                                 "S_q05": 1.0 if int(k) == 3 else 0.5}
        res["fanout"] = fo
    json.dump(res, open(RES / "premium_value.json", "w"), indent=1)
    print(json.dumps({k: (v if k == "fanout" else {kk: {"n": vv["n"], "h10": vv["h10"]["spearman_prem_move"], "h60": vv["h60"]["spearman_prem_move"],
                                                         "ci60": vv["h60"]["ci95"], "gapL60": vv["h60"]["mean_gap_to_limit_c_by_prem"],
                                                         "mv60": vv["h60"]["mean_move_c_by_prem"]} for kk, vv in v.items()}) for k, v in res.items()}, indent=1))


if __name__ == "__main__":
    main()
