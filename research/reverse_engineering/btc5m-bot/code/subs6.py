"""Iteration 6 (X15 = panel-assumptions proposal 3): decode SUBMISSIONS, not fills. From my unthrottled BTC 5m book feed
(btc5m_clob_raw, development blocks only), rebuild the Up-token book (snapshots + every near-touch price change) and find
size increments of exactly a bot size (30, 50, 60, 100, 200 shares) at the touch: a bid on Up at L (BUY Up at L) or an ask
on Up at x (mirror of a BUY Down at 1 - x), at a price that was the bought outcome's best ask within the previous 300 ms
(a lost or partly lost race leaves the order resting at the old ask). Each insertion is linked to a cluster fill (maker or
taker) on the same window, outcome and price within 30 s; unlinked ones are unfilled submissions (or the sibling W4's,
which uses the same sizes). Lifetime: time until the level's size drops back by the bot size without a trade at that
price (cancel) or with one (fill).
Usage: python subs6.py OWN_PARQUET START END"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6
C = L.C
SIZES = np.array([30.0, 50.0, 60.0, 100.0, 200.0])


def main(own_path, a, b):
    recs = list(L.recs("btc5m_clob_raw", a, b))
    tok = {}
    for r in recs:
        if r.get("k") == "S":
            tok[r["u"]] = (r["m"], True); tok[r["d"]] = (r["m"], False)
    books = {}  # m -> {"B": {p: z}, "S": {p: z}}
    hist = {}   # m -> list of (s, bb, ba) touch history
    ins = []
    trades = {}
    for r in recs:
        k = r.get("k")
        if k == "f" and r.get("u") == 1:
            books[r["m"]] = {"B": {p: z for p, z in r["b"]}, "S": {p: z for p, z in r["o"]}}
        elif k == "x":
            trades.setdefault(r["m"], []).append((r["s"], r["u"], r["p"], r["z"], r["d"], r["h"]))
        elif k == "p":
            mm = r["m"]
            bk = books.setdefault(mm, {"B": {}, "S": {}})
            side = bk[r["d"]]
            prev = side.get(r["p"], 0.0)
            new = r["z"] or 0.0
            if new == 0:
                side.pop(r["p"], None)
            else:
                side[r["p"]] = new
            h = hist.setdefault(mm, [])
            delta = new - prev
            if delta > 0 and np.min(np.abs(SIZES - delta)) < 0.011:
                # outcome and its old ask within the previous 300 ms
                past = [x for x in h[-400:] if r["s"] - 300 <= x[0] < r["s"]]
                if r["d"] == "B":   # bid on Up at L: BUY Up at L; old Up ask in the window
                    hit = any(abs(x[2] - r["p"]) < 1e-9 for x in past if x[2] is not None)
                    ins.append((r["s"], mm, True, r["p"], round(delta, 2), hit))
                else:               # ask on Up at x: BUY Down at 1 - x; old Down ask = 1 - old Up bid
                    hit = any(abs(x[1] - r["p"]) < 1e-9 for x in past if x[1] is not None)
                    ins.append((r["s"], mm, False, round(1 - r["p"], 4), round(delta, 2), hit))
            h.append((r["s"], r.get("bb"), r.get("ba")))
    ins = pd.DataFrame(ins, columns=["s", "m", "is_up", "price", "size", "at_old_ask"])
    res = {"bot_size_insertions": int(len(ins)), "at_old_ask": int(ins.at_old_ask.sum()) if len(ins) else 0,
           "by_size": ins[ins.at_old_ask].groupby("size").size().to_dict() if len(ins) else {}}
    # link to cluster fills (any role) on the same window, outcome, price, block ts within [s - 2 s, s + 30 s]
    own = live6.own_taker(own_path, a, b)
    own["mstart"] = own.token.map(lambda t: tok.get(t, (np.nan, None))[0]); own["is_up"] = own.token.map(lambda t: tok.get(t, (np.nan, None))[1])
    own = own[own.mstart.notna()].copy()
    own["price"] = np.round(own.mamt / own.tamt, 4)  # BUY: maker amount USDC / taker amount shares
    keyed = {k: g.ts.to_numpy(float) for k, g in own.groupby(["mstart", "is_up", "price"])}
    kr = {k: g for k, g in own.groupby(["mstart", "is_up", "price"])}
    linked, role = [], []
    for s, mm, u, p, z, h in ins[ins.at_old_ask].itertuples(index=False):
        ts = keyed.get((mm, u, round(p, 4)))
        ok = ts is not None and np.any((ts >= s / 1000 - 2) & (ts <= s / 1000 + 30))
        linked.append(bool(ok))
        if ok:
            g = kr[(mm, u, round(p, 4))]
            g = g[(g.ts >= s / 1000 - 2) & (g.ts <= s / 1000 + 30)]
            role.append("M" if (g.role == "M").any() else "T")
        else:
            role.append(None)
    sub = ins[ins.at_old_ask].copy()
    sub["linked"] = linked; sub["role"] = role
    res["linked_share"] = round(float(sub.linked.mean()), 4) if len(sub) else None
    res["linked_role"] = sub.role.value_counts().to_dict()
    res["unlinked_by_size"] = sub[~sub.linked].groupby("size").size().to_dict()
    # cluster resting fills (role M): how many are preceded by a detected insertion?
    om = own[own.role == "M"].drop_duplicates("oh")
    res["cluster_maker_orders"] = int(len(om))
    sub_k = {k: g.s.to_numpy(float) / 1000 for k, g in sub.groupby(["m", "is_up", "price"])}
    pre = [bool((sub_k.get((r.mstart, r.is_up, r.price)) is not None) and np.any((sub_k[(r.mstart, r.is_up, r.price)] <= r.ts + 1) & (sub_k[(r.mstart, r.is_up, r.price)] >= r.ts - 60))) for r in om.itertuples()]
    res["cluster_maker_orders_with_detected_insertion"] = round(float(np.mean(pre)), 4) if len(pre) else None
    # moving vs quiet at the insertion time (7 trade feeds, 1 s, > 0.1 bp), against all taker matches' quiet share
    sub.to_parquet(C + "/subs6_insertions.parquet", index=False)
    return res


if __name__ == "__main__":
    own_path, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    res = main(own_path, a, b)
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_subs_iter6.json"), "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:3000])
