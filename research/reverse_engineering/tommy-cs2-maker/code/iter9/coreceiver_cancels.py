"""Iteration 9, X121 first pass (information panel iter8 P4), BUILD-live: co-receiver makers around the wallet's takes.
The wallet's taker BUYs on the seven recorded books (calldata_dev, signing ms; server clock = signing + 0 here, the
books are on the server clock) are split into co-signed (a group P / G member take on the same token within 0..+800 ms,
from the decoded member transactions of feed_member_adds.py) and alone. Non-own cancels on the same book (level events,
kind cancel, minus cancels within 3 ms of a validated own pull burst on that book) are counted in (-150, -60], (-60, 0]
and (0, +8] ms around each take, against the same windows at random busy-phase times (each take's time shifted by
+-30..300 s, 300 draws). Signature (panel): one feed with a kind filter -> the pre-visibility (-150, 0] rate is the
same at alone and co-signed takes; exclusive input -> co-receivers fire at co-signed takes only.
Output: results/coreceiver_cancels.json"""
import json, sys
from pathlib import Path
import httpx, numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
from polyrea.adapters.polymarket import PolymarketData
from fetch_calldata import rows_of
OUT = ROOT / ".cache/re/tommy-cs2-maker"; RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
cfg = json.load(open(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/final_rule_v5_groupP.json"))
MEM = set(cfg["members"]) | set(cfg["group_G"])
dm = pd.read_parquet(OUT / "dev_markets.parquet")
la = pd.read_parquet(OUT / "linked_adds_dev.parquet", columns=["slug"])
dm = dm[dm.slug.isin(set(la.slug))]
tok_book = {}
for r in dm.itertuples():
    tok_book[str(r.tok0)] = str(r.tok0); tok_book[str(r.tok1)] = str(r.tok0)
cd = pd.read_parquet(OUT / "calldata_dev.parquet", columns=["idx", "maker", "side", "token_id", "sign_ms"])
cd["maker"] = cd.maker.str.lower(); cd["token_id"] = cd.token_id.astype(str)
wt = cd[(cd.maker == W) & (cd.idx == -1) & (cd.side == 0) & cd.token_id.isin(tok_book)].drop_duplicates(["token_id", "sign_ms"])
# member takes (re-decode, cached HTTP not used for RPC; same selection as feed_member_adds.py)
pm = PolymarketData(); txs = []
for r in dm.itertuples():
    rows, _, _ = pm.market_trades(r.cid, start=int(r.gs) - 3600, end=int(r.gs) + 4 * 3600, taker_only=True)
    txs += [x["transactionHash"] for x in rows if str(x.get("proxyWallet", "")).lower() in MEM]
txs = sorted(set(txs)); recs = []
cli = httpx.Client(timeout=40)
for i in range(0, len(txs), 40):
    body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(txs[i:i + 40])]
    for x in cli.post("https://polygon-bor-rpc.publicnode.com", json=body).json():
        if x.get("result"): recs += rows_of(x["result"])
C = pd.DataFrame(recs); C["maker"] = C.maker.str.lower(); C["token_id"] = C.token_id.astype(str)
mt = C[(C.idx == -1) & (C.side == 0) & C.maker.isin(MEM)]
E = pd.read_parquet(OUT / "level_events_dev.parquet", columns=["a", "s", "kind"])
E["a"] = E.a.astype(str)
ob = pd.read_parquet(OUT / "own_bursts_dev.parquet", columns=["a", "s", "kind"]); ob["a"] = ob.a.astype(str)
own_pull = {a: np.sort(g.s.to_numpy(float)) for a, g in ob[ob.kind == "pull"].groupby("a")}
canc = {}
for a, g in E[E.kind == "cancel"].groupby("a"):
    s_ = np.sort(g.s.to_numpy(float)); op = own_pull.get(a, np.array([]))
    if len(op):
        k = np.searchsorted(op, s_); near = np.zeros(len(s_), bool)
        for q in (k - 1, k):
            ok = (q >= 0) & (q < len(op)); near[ok] |= np.abs(op[np.clip(q, 0, len(op) - 1)][ok] - s_[ok]) <= 3
        s_ = s_[~near]
    canc[a] = s_
W_ = [(-150, -60), (-60, 0), (0, 8)]
def counts(a, t):
    s_ = canc.get(a, np.array([]))
    return [int(np.searchsorted(s_, t + hi, side="right") - np.searchsorted(s_, t + lo, side="right")) for lo, hi in W_]
rows = []
mt_by = {k: np.sort(v.sign_ms.to_numpy(float)) for k, v in mt.groupby("token_id")}
for r in wt.itertuples():
    a = tok_book[r.token_id]; t = float(r.sign_ms)
    m = mt_by.get(r.token_id, np.array([]))
    co = bool(((m - t >= 0) & (m - t <= 800)).any())
    rows.append({"a": a, "t": t, "co": co, "c": counts(a, t)})
X = pd.DataFrame(rows)
rng = np.random.default_rng(21)
res = {"wallet_takes": int(len(X)), "co_signed": int(X.co.sum()), "alone": int((~X.co).sum()), "windows_ms": W_}
for nm, g in (("co_signed", X[X.co]), ("alone", X[~X.co])):
    if len(g) == 0: continue
    obs = np.array(g.c.tolist()).mean(axis=0)
    nul = []
    for _ in range(300):
        nul.append(np.array([counts(r.a, r.t + rng.choice([-1, 1]) * rng.uniform(30000, 300000)) for r in g.itertuples()]).mean(axis=0))
    nul = np.array(nul)
    res[nm] = {"n": int(len(g)), "mean_cancels_per_window": [round(float(v), 3) for v in obs], "null_mean": [round(float(v), 3) for v in nul.mean(axis=0)],
               "null_p95": [round(float(v), 3) for v in np.percentile(nul, 95, axis=0)], "p": [round(float((nul[:, i] >= obs[i]).mean()), 4) for i in range(3)]}
print(json.dumps(res, indent=1)); json.dump(res, open(RES / "coreceiver_cancels.json", "w"), indent=1)
