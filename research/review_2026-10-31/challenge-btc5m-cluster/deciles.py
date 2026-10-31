import numpy as np, pandas as pd
F = pd.read_pickle("features_taker.pkl")
CL = ["0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"]
pd.set_option("display.width", 220)
for per in ("fit", "test"):
    P = F[per]
    P = P[(P.rel >= 0) & (P.rel < 300) & P.up_payout.notna()].copy()
    P["gross"] = P.payout_side - P.price          # per share
    P["net"] = P.gross - P.fee_ps
    P["usd"] = P.price * P["size"].clip(upper=25 / P.price)
    P["net_ret"] = P.net / P.price
    P["gross_ret"] = P.gross / P.price
    P["cl"] = P.wallet.isin(CL)
    print("=====", per, "all takers: mean gross ret", round(P.gross_ret.mean(), 4), "net", round(P.net_ret.mean(), 4), "| cluster gross", round(P[P.cl].gross_ret.mean(), 4), "net", round(P[P.cl].net_ret.mean(), 4))
    for c in ("dside_60", "fside_20", "sside_10", "price", "px_vs_last", "rel"):
        q = pd.qcut(P[c].rank(method="first"), 10, labels=False)
        g = P.groupby(q).agg(lo=(c, "min"), hi=(c, "max"), n=(c, "size"), cl_share=("cl", "mean"), gross=("gross_ret", "mean"), net=("net_ret", "mean"), fee=("fee_ps", "mean"))
        print(c); print(g.round(4).T.to_string())
