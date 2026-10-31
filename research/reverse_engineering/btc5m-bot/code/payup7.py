"""Iteration 7 (catalog X42 = panel-mechanics iter6 P4, first step): when does the bot price its order ABOVE the touch
(a "pay-up" by k ticks)? Calldata sample (11 development hours): limit minus the best consumed effective ask
(calldata_touch6.touch_table), by size class, wallet, |p - 0.5|, rel and the BTC 1-s move over the 2-4 s before the
block (binance_1s). Usage: python payup7.py"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calldata_touch6 import touch_table
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
cd = pd.read_parquet(f"{C}/calldata_sample.parquet")
cd["maker"] = cd.maker.str.lower()
txs = pd.read_parquet(f"{C}/calldata_sample_txs.parquet").set_index("tx").ts
tk, m = touch_table(cd)
tk = tk[tk.best.notna()].copy()
tk["ts"] = tk.tx.map(txs)
win = pd.read_parquet(f"{C}/windows.parquet")
st = dict(zip(win.up_token, win.start_ts)); st.update(dict(zip(win.down_token, win.start_ts)))
tk["rel"] = tk.ts - tk.token.map(st)
tk["size"] = tk.taker_amt.astype(float)
tk["payup_c"] = ((tk.limit - tk.best) * 100).round()
tk["up_k"] = tk.payup_c >= 1
sp = pd.read_parquet(f"{C}/binance_1s.parquet").sort_values("sec")
sec, cl = sp.sec.to_numpy(np.int64), sp.close.to_numpy(float)
def px(t):
    i = np.clip(np.searchsorted(sec, t, "right") - 1, 0, len(cl) - 1); return cl[i]
t = tk.ts.to_numpy(np.int64)
tk["amv"] = np.abs(px(t - 2) / px(t - 4) - 1) * 1e4
res = {"n": int(len(tk)), "share_above_touch": round(float(tk.up_k.mean()), 4),
       "payup_c_dist": {str(int(k)): int(v) for k, v in tk.payup_c.clip(-3, 5).value_counts().sort_index().items()}}
res["by_size"] = {str(int(s)): [round(float(g.up_k.mean()), 4), int(len(g))] for s, g in tk.groupby("size") if len(g) >= 50}
res["by_wallet"] = {w: round(float(g.up_k.mean()), 4) for w, g in tk.groupby("wal")}
res["by_abs_move_bp"] = {str(k): [round(float(g.up_k.mean()), 4), int(len(g))] for k, g in tk.groupby(pd.cut(tk.amv, [-1, 0.05, 0.5, 1, 2, 100]), observed=True)}
res["by_dist"] = {str(k): [round(float(g.up_k.mean()), 4), int(len(g))] for k, g in tk.groupby(pd.cut((tk.limit - 0.5).abs(), [-0.01, 0.1, 0.2, 0.3, 0.5]), observed=True)}
res["by_rel"] = {str(k): [round(float(g.up_k.mean()), 4), int(len(g))] for k, g in tk.groupby(pd.cut(tk.rel, [-100, 60, 120, 180, 240, 300]), observed=True)}
res["by_n_makers"] = {str(k): [round(float(g.up_k.mean()), 4), int(len(g))] for k, g in tk.groupby(tk.n_mk.clip(1, 5))}
json.dump(res, open(os.path.join(_ROOT, "research/reverse_engineering/btc5m-bot/results/payup7.json"), "w"), indent=1)
print(json.dumps(res))
