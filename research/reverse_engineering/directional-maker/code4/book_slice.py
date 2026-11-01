"""Quote state from the calldata of every match (STUDY slice 2026-10-26 13:00-13:30 UTC, 6 BTC 5m windows, 9,778 txs).
For each match that fills bids on a token s (maker BUY s, or maker SELL of the other token = bid on s at 1 - price):
the best filled bid price p*, the makers filled at p* and their order ages at the match (taker signing ms - maker
signing ms), and whether the cluster is filled there. Descriptive only (uses the match itself)."""
import glob
import numpy as np, pandas as pd
C = ".cache/re/directional-maker/"
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
win = pd.read_parquet(C + "exam/windows_5m.parquet")
up_of = {**{t: (c, 1) for t, c in zip(win.up_token, win.cid)}, **{t: (c, 0) for t, c in zip(win.down_token, win.cid)}}
d = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(C + "calldata/bk1026_*.parquet"))], ignore_index=True)
tk = d[d.role == "taker"].set_index("tx")
m = d[(d.role == "maker") & d.token_id.isin(up_of.keys())].copy()
m["cid"] = m.token_id.map(lambda t: up_of[t][0]); m["tok_up"] = m.token_id.map(lambda t: up_of[t][1])
m["lim"] = np.where(m.oside == 0, m.maker_amount / m.taker_amount, m.taker_amount / m.maker_amount)
# express every maker order as a bid on a side s (Up=1 / Down=0): BUY token -> bid on that token; SELL token -> bid on the other at 1-p
m["bid_side"] = np.where(m.oside == 0, m.tok_up, 1 - m.tok_up)
m["bid_px"] = np.where(m.oside == 0, m.lim, 1 - m.lim).round(3)
m["clu"] = m.maker.isin(W)
m["mms"] = m.tx.map(tk.sign_ms)
m["age"] = np.where(m.sign_ms > 0, (m.mms - m.sign_ms) / 1000.0, np.nan)
rows = []
for (tx, s), g in m.groupby(["tx", "bid_side"]):
    p = g.bid_px.max()
    top = g[g.bid_px == p]
    oth = top[~top.clu]
    rows.append({"tx": tx, "side": s, "p": p, "clu_at_top": bool(top.clu.any()), "clu_any": bool(g.clu.any()),
                 "n_top": len(top), "n_oth_top": len(oth), "oth_age_med": oth.age.median(), "oth_age_min": oth.age.min(),
                 "oth_orig_size_med": (np.where(oth.oside == 0, oth.taker_amount, oth.maker_amount) / 1e6).mean() if len(oth) else np.nan})
e = pd.DataFrame(rows)
print("bid-hit events", len(e), "cluster at the best filled price", int(e.clu_at_top.sum()), "cluster anywhere", int(e.clu_any.sum()))
for k, g in e.groupby("clu_at_top"):
    print("cluster at top" if k else "cluster absent", "n", len(g), "other makers at p*: n median", g.n_oth_top.median(),
          "| their age at match (s): median of medians", round(g.oth_age_med.median(), 2), "q25/q75", g.oth_age_med.quantile([.25, .75]).round(2).tolist(),
          "| youngest other at p* median", round(g.oth_age_min.median(), 2))
e["p_b"] = pd.cut(e.p, [0, .1, .3, .5, .7, .9, 1.0])
print("share of bid-hit events with the cluster at the top, by price:", e.groupby("p_b", observed=True).clu_at_top.mean().round(3).to_dict())
e["age_b"] = pd.cut(e.oth_age_min, [-1e9, 0.5, 1, 2, 5, 30, 1e9])
print("... by age of the youngest other maker at p* (s):", e.groupby("age_b", observed=True).clu_at_top.agg(["mean", "size"]).round(3).to_dict())
e.drop(columns=["p_b", "age_b"]).to_parquet(C + "book_slice_events.parquet")
