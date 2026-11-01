"""Iteration 17 (X175 / X165 replication): the size-class rates and the taker shares on the two 10-31 development blocks (00-06, 12-18),
from the cached on-chain fills of the three studied wallets (.cache/re/btc5m-bot/post/own_*.parquet, development blocks only) and the
calldata of a random sample of their taker txs (<= 1,500 per block; decoded fields only, session scratchpad it17/). Reports per block:
taker order shares, menu, P(large) by wallet (original >= 90), maker share of fills. Usage: python census31_17.py"""
import os, sys, glob, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import sealed, calldata
S = os.environ["RE16_SCRATCH"] + "/it17"
W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
EX = ["0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"]
d = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(_ROOT + "/.cache/re/btc5m-bot/post/own_*.parquet"))]).drop_duplicates(["tx", "li"])
d = d[[not sealed.is_sealed(int(t), "btc5m-bot") for t in d.ts]]
d["wallet"] = d.owner.str.lower().map(W); d["role"] = np.where(d.cp.str.lower().isin(EX), "T", "M"); d = d[d.side == 0]
d["blk"] = (d.ts - 1793404800) // 21600
rng = np.random.default_rng(17); res = {}
for b, g in d.groupby("blk"):
    txs = sorted(set(g[g.role == "T"].tx.str.lower()))
    samp = list(rng.choice(txs, min(1500, len(txs)), replace=False))
    fn = f"{S}/cd31_blk{b}.parquet"
    if os.path.exists(fn):
        cd = pd.read_parquet(fn)
    else:
        cd = calldata.to_frame(calldata.fetch_txs(samp, threads=2, log_every=30)); cd.to_parquet(fn, index=False)
    cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["wallet"] = cd.maker.str.lower().map(W); cd = cd[cd.wallet.notna()]
    r = {"block_utc": f"10-31 {int(b) * 6:02d}-{int(b) * 6 + 6:02d}", "fills_by_wallet_role": g.groupby(["wallet", "role"]).size().unstack(fill_value=0).to_dict("index"),
         "taker_txs": len(txs), "sampled": len(samp), "orders_decoded": int(len(cd)),
         "order_share": {w: round(float((cd.wallet == w).mean()), 4) for w in ("DS", "GF", "XM")},
         "menu_top": {w: {str(int(k)): int(v) for k, v in cd[cd.wallet == w].taker_amt.round().value_counts().head(5).items()} for w in ("DS", "GF", "XM")},
         "P_large_ge90": {w: round(float((cd[cd.wallet == w].taker_amt >= 90).mean()), 4) for w in ("DS", "GF", "XM")},
         "P_large_pooled": round(float((cd.taker_amt >= 90).mean()), 4)}
    res[str(b)] = r
    print(json.dumps(r), flush=True)
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/census31_17.json", "w"), indent=1, default=str)
