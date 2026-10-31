"""Iteration 9 (panel iter8 assumptions P1 step 1, part): role census and side-condition applicability per wallet and day.
Per wallet x UTC day (BUILD + VALIDATE from fills.parquet; the 10-31 development blocks from on-chain fills): fills, maker share
of fills and of shares, maker-first order share, one-sided share of the wallet's windows and its ORDER-COUNT NULL (keep the
wallet's order count per window; draw each order's outcome from the pooled cluster's Up share of orders in that window; 200
draws). The brief applies the side condition where a wallet is one-sided in >= 20% of its windows.
Usage: python census9.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd

C = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", ".cache", "re", "btc5m-bot"))
EX = {"0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"}
W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}


def load():
    f = pd.read_parquet(C + "/fills.parquet", columns=["oh", "wallet", "role", "shares", "start_ts", "is_up", "ts", "li", "block"])
    f["src"] = "hist"
    d = pd.read_parquet(C + "/it9/own_1231_12_18.parquet")
    d0 = pd.read_parquet(C + "/post/own_1793404800_1793426400.parquet")
    d = pd.concat([d0, d]).drop_duplicates(["tx", "li"])
    d["wallet"] = d.owner.map(W); d["role"] = np.where(d.cp.isin(EX), "T", "M"); d["shares"] = d.tamt / 1e6
    # window start and outcome from the token: use gamma-free mapping through the clob subscriptions is costly; the window start
    # of a 10-31 fill is floor(ts / 300) * 300 for fills inside the window (BTC 5m windows trade only while open)
    d["start_ts"] = (d.ts // 300) * 300
    tok_up = {}
    # outcome side: the Up token is the one with the larger token id? not reliable -> use per-window token pairs: the side is
    # defined only up to a label swap, which is all the one-sided share and its null need
    d["is_up"] = d.groupby("start_ts").token.transform(lambda s: s == s.min())
    d["src"] = "dev1031"
    keep = ["oh", "wallet", "role", "shares", "start_ts", "is_up", "ts", "li", "block", "src"]
    return pd.concat([f[keep], d[keep]], ignore_index=True)


def main(out):
    f = load()
    f["day"] = pd.to_datetime(f.start_ts, unit="s").dt.strftime("%m-%d")
    f = f.sort_values(["block", "li"])
    first = f.groupby("oh").role.first()
    f["first"] = f.oh.map(first)
    res = {}
    rng = np.random.default_rng(3)
    for (day, wl), g in f.groupby(["day", "wallet"]):
        orders = g.drop_duplicates("oh")
        r = {"fills": int(len(g)), "maker_share_fills": round(float((g.role == "M").mean()), 3),
             "maker_share_shares": round(float(g.shares[g.role == "M"].sum() / g.shares.sum()), 3),
             "maker_first_order_share": round(float((orders["first"] == "M").mean()), 3), "orders": int(len(orders)),
             "windows": int(g.start_ts.nunique())}
        ws = orders.groupby("start_ts").is_up.agg(["mean", "size"])
        r["one_sided_share"] = round(float(((ws["mean"] == 0) | (ws["mean"] == 1)).mean()), 3)
        # count null: pooled cluster Up share of orders in the window
        allo = f[f.day == day].drop_duplicates("oh")
        pu = allo.groupby("start_ts").is_up.mean()
        p = pu.reindex(ws.index).to_numpy(); n = ws["size"].to_numpy()
        sims = []
        for _ in range(200):
            k = rng.binomial(n, p)
            sims.append(((k == 0) | (k == n)).mean())
        r["one_sided_null"] = round(float(np.mean(sims)), 3)
        r["orders_per_window"] = round(float(n.mean()), 1)
        res.setdefault(day, {})[wl] = r
    # summary by period
    summ = {}
    for nm, days in (("BUILD", [f"10-{d:02d}" for d in range(9, 16)]), ("VALIDATE", [f"10-{d:02d}" for d in range(16, 23)]), ("dev_10-31", ["10-31"])):
        for wl in ("DS", "GF", "XM"):
            sub = f[f.day.isin(days) & (f.wallet == wl)]
            if not len(sub):
                continue
            orders = sub.drop_duplicates("oh")
            ws = orders.groupby("start_ts").is_up.agg(["mean", "size"])
            allo = f[f.day.isin(days)].drop_duplicates("oh"); pu = allo.groupby("start_ts").is_up.mean()
            p = pu.reindex(ws.index).to_numpy(); n = ws["size"].to_numpy()
            sims = [(((k := rng.binomial(n, p)) == 0) | (k == n)).mean() for _ in range(200)]
            summ.setdefault(nm, {})[wl] = {"one_sided_share": round(float(((ws["mean"] == 0) | (ws["mean"] == 1)).mean()), 3),
                                           "count_null": round(float(np.mean(sims)), 3), "windows": int(len(ws)),
                                           "maker_share_fills": round(float((sub.role == "M").mean()), 3),
                                           "maker_first_order_share": round(float((orders["first"] == "M").mean()), 3),
                                           "fills_per_day": round(float(len(sub) / len(days)), 0)}
    out_d = {"by_period": summ, "by_day": res}
    json.dump(out_d, open(out, "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
