"""Iteration 9, finding 14 -> source: do the wallet's informative add levels precede the takes of the feed's other
subscribers (group P and group G, BUILD lists) on the same token? BUILD-live (10-31 12-18), the seven recorded books.
Member taker BUYs from the markets' public taker tapes (data-api, development units), signing ms from their decoded
calldata (publicnode). For each member take on token z at signing time t: own validated adds on z in [t - 1000, t] ms
with offset >= -1.5c from the others' mid ("up" re-pricing of z), and own adds on the complement with offset <= -4.5c
("down" re-pricing), against the same windows shifted by +-30..300 s (300 draws). Output: results/feed_member_adds.json"""
import json, sys
from pathlib import Path
import httpx, numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
from polyrea.adapters.polymarket import PolymarketData
from fetch_calldata import rows_of
OUT = ROOT / ".cache/re/tommy-cs2-maker"; RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
cfg = json.load(open(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/final_rule_v5_groupP.json"))
MEM = set(cfg["members"]) | set(cfg["group_G"])
dm = pd.read_parquet(OUT / "dev_markets.parquet")
la = pd.read_parquet(OUT / "linked_adds_dev.parquet")
dm = dm[dm.slug.isin(set(la.slug))]
pm = PolymarketData()
txs = []
for r in dm.itertuples():
    rows, _, _ = pm.market_trades(r.cid, start=int(r.gs) - 3600, end=int(r.gs) + 4 * 3600, taker_only=True)
    for x in rows:
        if str(x.get("proxyWallet", "")).lower() in MEM:
            txs.append(x["transactionHash"])
txs = sorted(set(txs))
recs = []
cli = httpx.Client(timeout=40)
for i in range(0, len(txs), 40):
    body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(txs[i:i + 40])]
    for x in cli.post("https://polygon-bor-rpc.publicnode.com", json=body).json():
        if x.get("result"):
            recs += rows_of(x["result"])
C = pd.DataFrame(recs)
C["maker"] = C.maker.str.lower(); C["token_id"] = C.token_id.astype(str)
T = C[(C.idx == -1) & (C.side == 0) & C.maker.isin(MEM) & (C.sign_ms > 1.79e12)]
tok0 = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
tok1 = {str(r.tok1): str(r.tok0) for r in dm.itertuples()}
A = la[la.kind == "add"].copy()
A["vown"] = (A.owner == "wallet") | (A.F_mkt & (A.in_burst | (A["size"] != 100)))
A = A[A.vown]
M = pd.read_parquet(OUT / "others_mid_dev.parquet").sort_values(["a", "s"])
mids = {str(a): (g.s.to_numpy(float), g.mid.to_numpy(float)) for a, g in M.groupby("a")}
def off_of(r):
    ts, md = mids.get(str(r.a), (None, None))
    if ts is None: return np.nan
    j = np.searchsorted(ts, r.s - 100, side="right") - 1
    if j < 0: return np.nan
    t0 = r.side == "BUY"; m0 = md[j] if t0 else 1 - md[j]
    return ((r.p if t0 else 1 - r.p) - m0) * 100
A["off"] = [off_of(r) for r in A.itertuples()]
A["a"] = A.a.astype(str)
# own adds per (book token0, token side): z0 = bid on token 0 (BUY side), z1 = bid on token 1 (SELL side)
up = {}; dn = {}
for a, g in A.groupby("a"):
    for zside, zz in (("BUY", 0), ("SELL", 1)):
        h = g[g.side == zside]
        up[(a, zz)] = np.sort(h.loc[h.off >= -1.5, "s"].to_numpy(float))
        dn[(a, zz)] = np.sort(h.loc[h.off <= -4.5, "s"].to_numpy(float))
def count(t, key_up, key_dn, shift=0.0):
    tt = t + shift
    u = up.get(key_up, np.array([])); d = dn.get(key_dn, np.array([]))
    cu = int(np.searchsorted(u, tt, side="right") - np.searchsorted(u, tt - 1000, side="left"))
    cd = int(np.searchsorted(d, tt, side="right") - np.searchsorted(d, tt - 1000, side="left"))
    return cu, cd
obs_u = obs_d = 0; keys = []
for r in T.itertuples():
    if r.token_id in tok0: a, z = tok0[r.token_id], 0
    elif r.token_id in tok1: a, z = tok1[r.token_id], 1
    else: continue
    keys.append((float(r.sign_ms), (a, z), (a, 1 - z)))
for t, ku, kd in keys:
    cu, cd = count(t, ku, kd); obs_u += cu > 0; obs_d += cd > 0
rng = np.random.default_rng(13)
nu, nd = [], []
for _ in range(300):
    su = sd = 0
    for t, ku, kd in keys:
        cu, cd = count(t, ku, kd, rng.choice([-1, 1]) * rng.uniform(30000, 300000)); su += cu > 0; sd += cd > 0
    nu.append(su); nd.append(sd)
res = {"member_txs": len(txs), "member_takes_on_books": len(keys), "by_member": {k[:10]: int(v) for k, v in T.maker.value_counts().items()},
       "takes_with_own_up_add_on_token_1s_before": int(obs_u), "null_mean_up": round(float(np.mean(nu)), 2), "null_p95_up": float(np.percentile(nu, 95)), "p_up": round(float(np.mean(np.array(nu) >= obs_u)), 4),
       "takes_with_own_down_add_on_complement_1s_before": int(obs_d), "null_mean_down": round(float(np.mean(nd)), 2), "null_p95_down": float(np.percentile(nd, 95)), "p_down": round(float(np.mean(np.array(nd) >= obs_d)), 4)}
print(json.dumps(res, indent=1)); json.dump(res, open(RES / "feed_member_adds.json", "w"), indent=1)
