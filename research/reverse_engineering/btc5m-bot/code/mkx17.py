"""Iteration 17: decode the operator's MAKER component in the new regime (11-01 06:00-09:30 development windows), XM's 60-share bids in
particular (XM: 92% of its fills are maker fills there, 99% from maker-FIRST orders; on 10-14..22 XM had almost none of them; on
10-09..13 21-42% of XM's maker-first orders were 60 shares). From the calldata of the maker-only txs (mk17.py): each operator BUY
order resting as a maker: original size, limit, signing ms; joined to its on-chain fills (block ts). Book at signing from the shared
recorder's clob_crypto 'q' records (Up token; Down = 1 - Up mirrored). Reports per wallet x size: signing time in the window, limit
vs the best bid / ask of its outcome at signing, sign-to-fill lifetime, prices, fill rate (filled shares / original), and the
window-level PnL of the maker stream vs the taker stream. Usage: python mkx17.py"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live

S = os.environ["RE16_SCRATCH"] + "/it17"
W5 = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM",
      "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS", "0xd84403efd50b49a1d8a7181627e00307e6ea5908": "W4",
      "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c": "W5"}
win = pd.read_parquet(S + "/post17_windows.parquet")
fl = pd.read_parquet(S + "/post17_fills.parquet"); fl["tx"] = fl.tx.str.lower()
mk = pd.read_parquet(S + "/post17_mk_cd.parquet"); mk["tx"] = mk.tx.str.lower()
mk = mk[(mk.role == "M") & (mk.oside == 0)].copy(); mk["wallet"] = mk.maker.str.lower().map(W5); mk = mk[mk.wallet.notna()]
tok = pd.concat([win[["cid", "start_ts", "up_token", "up_payout"]].rename(columns={"up_token": "token"}).assign(is_up=True),
                 win[["cid", "start_ts", "down_token", "up_payout"]].rename(columns={"down_token": "token"}).assign(is_up=False)])
mk = mk.drop(columns=[c for c in ("cid",) if c in mk]).merge(tok, on="token", how="inner")
mk["orig"] = mk.taker_amt; mk["limit"] = (mk.maker_amt / mk.taker_amt).round(4)
mk["sign_rel"] = mk.sign_ms / 1000.0 - mk.start_ts
blk = fl.groupby("tx").ts.min()
mk["fill_ts"] = mk.tx.map(blk); mk["life_s"] = mk.fill_ts - mk.sign_ms / 1000.0
mk["fill_rel"] = mk.fill_ts - mk.start_ts
mk["oid"] = mk.wallet + "|" + mk.salt.astype(str)
o = mk.groupby("oid").agg(wallet=("wallet", "first"), orig=("orig", "first"), limit=("limit", "first"), sign_ms=("sign_ms", "first"),
                          sign_rel=("sign_rel", "first"), first_fill_rel=("fill_rel", "min"), life_first=("life_s", "min"),
                          filled=("fill_amt", "sum"), is_up=("is_up", "first"), cid=("cid", "first"), start_ts=("start_ts", "first"),
                          token=("token", "first"), up_payout=("up_payout", "first"))
# book at signing: clob_crypto 'q' for the Up token of these windows
upt = set(win.up_token.astype(str)); bt = {}
a0, b0 = int(win.start_ts.min()) - 400, int(win.end_ts.max()) + 10
for r in live.iter_live("clob_crypto", a0, b0):
    if r.get("k") not in ("q", "f"):
        continue
    a = str(r.get("a"))
    if a not in upt:
        continue
    bb = max((float(x[0]) for x in r.get("b") or []), default=np.nan); aa = min((float(x[0]) for x in r.get("o") or []), default=np.nan)
    bt.setdefault(a, []).append((r.get("s") or r["t"], bb, aa))
up_tok = dict(zip(win.cid, win.up_token.astype(str)))
bb_s, ba_s = [], []
for x in o.itertuples():
    arr = bt.get(up_tok[x.cid])
    if not arr:
        bb_s.append(np.nan); ba_s.append(np.nan); continue
    ts = np.array([z[0] for z in arr]); i = np.searchsorted(ts, x.sign_ms, "right") - 1
    if i < 0:
        bb_s.append(np.nan); ba_s.append(np.nan); continue
    ub, ua = arr[i][1], arr[i][2]
    if x.is_up:
        bb_s.append(ub); ba_s.append(ua)
    else:
        bb_s.append(1 - ua); ba_s.append(1 - ub)
o["bid_at_sign"] = bb_s; o["ask_at_sign"] = ba_s
o["lim_minus_bid_c"] = ((o["limit"] - o.bid_at_sign) * 100).round(1)
o["fill_frac"] = o.filled / o.orig
res = {"maker_orders": {w: int((o.wallet == w).sum()) for w in W5.values()}}
for w in ("XM", "DS", "GF", "W4"):
    x = o[o.wallet == w]
    if not len(x):
        continue
    d = {"n": int(len(x)), "orig_top": {str(int(k)): int(v) for k, v in x.orig.round().value_counts().head(5).items()}}
    for nm, g in (("all", x), ("size60", x[x.orig.round() == 60]), ("size30", x[x.orig.round() == 30]), ("size100", x[x.orig.round() == 100])):
        if len(g) < 5:
            continue
        d[nm] = {"n": int(len(g)), "sign_rel_q": [round(float(v), 1) for v in g.sign_rel.quantile([0.1, 0.25, 0.5, 0.75, 0.9])],
                 "first_fill_rel_q": [round(float(v), 1) for v in g.first_fill_rel.quantile([0.1, 0.5, 0.9])],
                 "life_q": [round(float(v), 1) for v in g.life_first.quantile([0.1, 0.25, 0.5, 0.75, 0.9])],
                 "limit_q": [round(float(v), 3) for v in g["limit"].quantile([0.1, 0.25, 0.5, 0.75, 0.9])],
                 "limit_top": {str(k): int(v) for k, v in g["limit"].round(2).value_counts().head(8).items()},
                 "lim_minus_bid_c_top": {str(k): int(v) for k, v in g.lim_minus_bid_c.value_counts().head(8).items()},
                 "below_ask_share": round(float((g["limit"] < g.ask_at_sign - 1e-9).mean()), 4),
                 "fill_frac_q": [round(float(v), 3) for v in g.fill_frac.quantile([0.25, 0.5, 0.75])],
                 "up_share": round(float(g.is_up.mean()), 3)}
    res[w] = d
# per-window PnL of maker vs taker streams per wallet (fills of the block)
f = fl[fl.side == 0].copy(); f["wallet"] = f.owner.str.lower().map(W5)
f["pay"] = np.where(f.is_up, f.up_payout, 1 - f.up_payout); f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd
pw = f.groupby(["wallet", "role"]).pnl.sum().round(1).unstack().to_dict("index")
res["pnl_by_wallet_role_usd_block"] = pw
res["shares_by_wallet_role_block"] = f.groupby(["wallet", "role"]).shares.sum().round(0).unstack().to_dict("index")
o.reset_index().to_parquet(S + "/mkx17_orders.parquet", index=False)
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/mkx17.json", "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
