import pickle, json, sys
import pandas as pd, numpy as np
d = pickle.load(open('data.pkl', 'rb'))
W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
t = d["test"]
wins = {w.condition_id: w for w in t["windows"]}
# pick a window where GF is active
p = t["prints"]
cnt = p[p.wallet.isin(W)].groupby("condition_id").size().sort_values()
cid = cnt.index[len(cnt) // 2]
w = wins[cid]
print(w, cnt[cid])
tape = t["full_tapes"][cid]
taker = t["tapes"][cid]
tk = {}
for r in taker:
    tk[(r["transactionHash"], r["proxyWallet"].lower(), r["asset"], r["side"])] = 1
rows = []
for r in tape:
    k = (r["transactionHash"], r["proxyWallet"].lower(), r["asset"], r["side"])
    rows.append({"rel": r["timestamp"] - w.start_ts, "tx": r["transactionHash"][:8], "who": W.get(r["proxyWallet"].lower(), r["proxyWallet"][:6]), "role": "T" if k in tk else "m", "side": r["side"], "out": r["outcome"], "px": round(float(r["price"]), 3), "sz": round(float(r["size"]), 1)})
df = pd.DataFrame(rows).sort_values(["rel", "tx"])
df = df[df.rel >= -5]
pd.set_option("display.width", 200); pd.set_option("display.max_rows", 400)
print(df.head(300).to_string())
