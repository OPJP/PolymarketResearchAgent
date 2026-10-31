"""Iteration 8, X23 historical part (panel-mechanics iter5 P1, prey makers) and X51 step 5 (panel-mechanics iter7 P3,
counterparties of big fills). Calldata sample (11 pre-H hours): for every cluster TAKER order (role T, maker = a cluster
wallet), the maker orders it consumed (role M of the same tx): maker identity, the maker order's age at the block
(block ts - signing ms; maker clients that sign at submission), its original size in shares, its class (one-shot = the
maker has <= 3 orders in the sample hour; quoter = more), split by the cluster order's size (large vs small) and by a
quiet market (|Binance 1-s move| over [s-4, s-2] <= 0.5 bp). Writes results/prey8.json."""
import os, json
import numpy as np, pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")
W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
d = pd.read_parquet(os.path.join(C, "calldata_sample.parquet"), columns=["tx", "role", "maker", "sign_ms", "maker_amt", "taker_amt", "oside", "token"])
tx = pd.read_parquet(os.path.join(C, "calldata_sample_txs.parquet")).drop_duplicates("tx").set_index("tx").ts
d["ts"] = d.tx.map(tx)
d["maker"] = d.maker.str.lower()
tk = d[(d.role == "T") & d.maker.isin(W)].drop_duplicates("tx").copy()
tk["size"] = tk.taker_amt.round(0)
tk["hr"] = (tk.ts // 3600).astype("Int64")
mins = tk.groupby("hr")["size"].agg(lambda s: s.value_counts().index[s.value_counts().values >= 0.03 * len(s)].min())
tk["large"] = tk["size"] > tk.hr.map(mins) + 1e-9
mk = d[(d.role == "M") & d.tx.isin(set(tk.tx))].copy()
mk = mk[~mk.maker.isin(W)]
# original size in shares: a SELL maker gives shares (maker_amt), a BUY maker receives shares (taker_amt)
mk["orig_sh"] = np.where(mk.oside == 1, mk.maker_amt, mk.taker_amt)
mk["age_s"] = mk.ts - mk.sign_ms / 1000.0
mk["hr"] = (mk.ts // 3600).astype("Int64")
cnt = mk.groupby(["hr", "maker"]).size()
mk["n_in_hour"] = [cnt.get((h, m), 0) for h, m in zip(mk.hr, mk.maker)]
mk["quoter"] = mk.n_in_hour > 3
mk = mk.merge(tk[["tx", "large", "size", "ts"]].rename(columns={"ts": "tts"}), on="tx", how="left")
bn = pd.read_parquet(os.path.join(C, "binance_1s.parquet"))
px = pd.Series(bn.close.values.astype(float), index=bn.sec.values.astype(np.int64)).sort_index()
px = px[~px.index.duplicated()]
s = mk.tts.to_numpy(np.int64)
r = (px.reindex(s - 2).values / px.reindex(s - 4).values - 1) * 1e4
mk["quiet"] = np.abs(r) <= 0.5
valid_age = (mk.age_s > -5) & (mk.age_s < 7 * 86400)
res = {"cluster_taker_orders": int(len(tk)), "consumed_maker_orders": int(len(mk)), "distinct_makers": int(mk.maker.nunique())}
top = mk.maker.value_counts()
res["top10_maker_share"] = round(float(top.head(10).sum() / len(mk)), 3)
res["top5_makers"] = {k[:10]: int(v) for k, v in top.head(5).items()}
res["sell_share"] = round(float((mk.oside == 1).mean()), 3)
for nm, k in (("all", np.ones(len(mk), bool)), ("cluster_large", mk.large.fillna(False).to_numpy(bool)), ("cluster_small", ~mk.large.fillna(False).to_numpy(bool)),
              ("quiet", mk.quiet.to_numpy(bool)), ("moving", ~mk.quiet.to_numpy(bool))):
    x = mk[k & valid_age.to_numpy(bool)]
    res[nm] = {"n": int(k.sum()), "age_median_s": round(float(x.age_s.median()), 2) if len(x) else None, "age_lt_1s": round(float((x.age_s < 1).mean()), 3) if len(x) else None,
               "age_gt_60s": round(float((x.age_s > 60).mean()), 3) if len(x) else None, "quoter_share": round(float(mk.quoter[k].mean()), 3),
               "orig_size_median": round(float(mk.orig_sh[k].median()), 1), "orig_ge_3x_cluster": round(float((mk.orig_sh[k] >= 3 * mk["size"][k]).mean()), 3),
               "top10_share": round(float(mk.maker[k].isin(set(top.head(10).index)).mean()), 3)}
print(json.dumps(res, indent=0))
json.dump(res, open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "prey8.json"), "w"), indent=1)
