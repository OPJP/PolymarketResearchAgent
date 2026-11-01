"""Iteration 16 (X151 step 1 = information P1, partial; X155 input): each wallet's Polymarket VIEW clock from the complete calldata of
10-20 (every operator taker order's limit L) and o's ask vector at 16 offsets m - x before the match (capture L2, book clock).
For orders whose o-ask changed between m - 500 and m - 125, P(L - c_w == best ask at m - x) by wallet and offset, with c_w the
iteration-13 pay-up (DS 0, GF 1, XM 1 c) and with c = 0 / 1 / 2 for all wallets; the latest offset still on the plateau is the view
edge. Also P(L >= ask(m - x)) (marketable). Usage: python view16.py"""
import os, json
import numpy as np, pandas as pd

S = os.environ["RE16_SCRATCH"]
od = pd.read_parquet(S + "/it15/l2ordb_2026-10-20.parquet")
ov = np.load(S + "/it15/l2ordb_2026-10-20.npy", mmap_mode="r")
q = json.load(open(S + "/it15/l2ordb_2026-10-20_qoff.json")); ix = {x: i for i, x in enumerate(q)}
cd = pd.concat([pd.read_parquet(S + "/it16/cdfull_10-20.parquet", columns=["tx", "role", "maker_amt", "taker_amt", "oside", "sign_ms", "block"]),
                pd.read_parquet(".cache/re/btc5m-bot/calldata_sample.parquet", columns=["tx", "role", "maker_amt", "taker_amt", "oside", "sign_ms", "block"]),
                pd.read_parquet(S + "/it15/cl_orders.parquet", columns=["tx", "role", "maker_amt", "taker_amt", "oside", "sign_ms", "block"])])
cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["tx"] = cd.tx.str.lower(); cd = cd.drop_duplicates("tx")
cd["L"] = np.round(100 * cd.maker_amt / cd.taker_amt).astype(int); cd["orig"] = cd.taker_amt
od["row"] = np.arange(len(od)); od["tx"] = od.tx.str.lower()
j = od.merge(cd[["tx", "L", "orig", "sign_ms"]], on="tx", how="inner")
print("orders", len(od), "with calldata", len(j), flush=True)
r = j.row.to_numpy()


def best(v):
    pos = v[:, 1:] > 0
    return np.where(pos.any(1), pos.argmax(1) + 1, 0)


B = {x: best(np.asarray(ov[r, ix[x], :])) for x in q}
for x in q:
    j[f"a{x}"] = B[x]
chg = (j.a500 != j.a125) | (j.a250 != j.a125) | (j.a180 != j.a125) | (j.a150 != j.a125)
cw = j.wallet.map({"DS": 0, "GF": 1, "XM": 1}).to_numpy()
res = {"n_orders": int(len(j)), "n_changed": int(chg.sum()), "by_wallet_changed": j[chg].wallet.value_counts().to_dict()}
for nm, cvec in (("c_w", cw), ("c0", 0), ("c1", 1), ("c2", 2)):
    tab = {}
    for w in ("DS", "GF", "XM"):
        mw = (j.wallet == w).to_numpy() & chg.to_numpy()
        cc = cvec[mw] if isinstance(cvec, np.ndarray) else cvec
        tab[w] = {x: round(float(((j.L.to_numpy()[mw] - cc) == j[f"a{x}"].to_numpy()[mw]).mean()), 3) for x in q}
    res[f"P(L-c==ask(m-x))|{nm}"] = tab
tab = {}
for w in ("DS", "GF", "XM"):
    mw = (j.wallet == w).to_numpy() & chg.to_numpy()
    tab[w] = {x: round(float((j.L.to_numpy()[mw] >= j[f"a{x}"].to_numpy()[mw]).mean()), 3) for x in q}
res["P(L>=ask(m-x))"] = tab
# signing lead: sign_ms vs the match (pre-signed cells) by wallet
j["lead"] = j.m - j.sign_ms
res["sign_lead_ms_quantiles"] = {w: g.lead.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(0).to_dict() for w, g in j.groupby("wallet")}
print(json.dumps(res, indent=1))
json.dump(res, open("research/reverse_engineering/btc5m-bot/results/view16.json", "w"), indent=1)
