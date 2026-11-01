"""Iteration 17 (panel iter16 information P1 = X164, assumptions P1 step 1 / P3 = X173 / X175): the FIRST OUT-OF-TIME decision record
in the new routing regime. Development block 11-01 06-12 UTC only (sealed.intervals clamps every range; windows must START in a
development interval). Steps:
  1. BTC 5m windows (Gamma listing, final_rule.load_windows) starting in [A, B);
  2. on-chain V2 OrderFilled of the FIVE operator wallets (DS, GF, XM, W4, W5; topic2 = order owner), both exchanges;
  3. V2 matchOrders calldata of every operator taker tx (original size, limit, signing ms), decoded fields only;
  4. server-ms match time per tx from the live lab's Polymarket trade records ('x' records with tx hash: clob_crypto and
     btc5m_clob_raw2), through tools/live.py iter_live (development blocks only).
Outputs (session scratchpad it17/): post17_windows.parquet, post17_fills.parquet, post17_cd.parquet, post17_xms.parquet.
Usage: python post17.py A_TS B_TS"""
import os, sys, time, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import sealed, live
import final_rule as fr
import rpc, calldata

S = os.environ["RE16_SCRATCH"]
OUT = S + "/it17"
os.makedirs(OUT, exist_ok=True)
W5 = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM",
      "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS", "0xd84403efd50b49a1d8a7181627e00307e6ea5908": "W4",
      "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c": "W5"}
A, B = int(sys.argv[1]), int(sys.argv[2])
ivs = sealed.intervals("btc5m-bot", A, B, sealed=False)
print("development intervals", ivs, flush=True)
assert ivs, "no development interval"
t0 = time.time()
wins = []
for (a, b) in ivs:
    w = fr.load_windows(int(a), int(b) + 300)
    wins.append(w[(w.start_ts >= a) & (w.start_ts < b)])
win = pd.concat(wins).drop_duplicates("cid").reset_index(drop=True)
for r in win.itertuples():
    assert not sealed.is_sealed(r.start_ts, "btc5m-bot")
win.to_parquet(OUT + "/post17_windows.parquet", index=False)
print("windows", len(win), round(time.time() - t0), "s", flush=True)
fa, fb = int(win.start_ts.min()), int(win.end_ts.max()) + 5
b0, b1 = fr._find_block(fa), fr._find_block(fb)
pads = [rpc.pad(x) for x in W5]
rows = []
for a in range(b0, b1, 3000):
    b = min(a + 2999, b1 - 1)
    for ex in fr.EXCHANGES:
        rows += [fr._decode(l) for l in fr._get_logs_chunked(ex, a, b, [rpc.TOPIC_V2, None, pads])]
df = pd.DataFrame(rows)
miss = df.ts < 0
if miss.any():
    for blk in df.loc[miss, "block"].unique():
        df.loc[df.block == blk, "ts"] = rpc.block_ts(int(blk))
df = df.drop_duplicates(["tx", "li"])
df["wallet"] = df.owner.str.lower().map(W5)
df["role"] = np.where(df.cp.str.lower().isin([e.lower() for e in fr.EXCHANGES]), "T", "M")
buy = df.side == 0
df["usdc"] = np.where(buy, df.mamt, df.tamt) / 1e6
df["shares"] = np.where(buy, df.tamt, df.mamt) / 1e6
df["price"] = df.usdc / df.shares
df["fee_usd"] = df.fee / 1e6
up = win[["cid", "start_ts", "end_ts", "up_token", "up_payout"]].rename(columns={"up_token": "token"}).assign(is_up=True)
dn = win[["cid", "start_ts", "end_ts", "down_token", "up_payout"]].rename(columns={"down_token": "token"}).assign(is_up=False)
df = df.merge(pd.concat([up, dn]), on="token", how="inner")
df["rel"] = df.ts - df.start_ts
df.to_parquet(OUT + "/post17_fills.parquet", index=False)
print("fills", len(df), df.groupby(["wallet", "role"]).size().to_dict(), round(time.time() - t0), "s", flush=True)
txs = sorted(set(df[(df.role == "T") & (df.side == 0)].tx.str.lower()))
print("operator taker BUY txs", len(txs), flush=True)
rowsc = calldata.fetch_txs(txs, threads=2, log_every=40)
cd = calldata.to_frame(rowsc)
cd.to_parquet(OUT + "/post17_cd.parquet", index=False)
print("calldata rows", len(cd), "txs", cd.tx.nunique(), round(time.time() - t0), "s", flush=True)
want = set(txs)
xm = {}
for feed in ("clob_crypto", "btc5m_clob_raw2"):
    n = 0
    for rec in live.iter_live(feed, fa - 60, fb + 60):
        if not isinstance(rec, dict) or rec.get("k") != "x":
            continue
        h = str(rec.get("h") or "").lower()
        if h in want:
            s = rec.get("s"); t = rec.get("t")
            k = (h, feed)
            if k not in xm or (s is not None and s < xm[k][0]):
                xm[k] = (s, t, rec.get("a"), rec.get("p"), rec.get("z"), rec.get("d")); n += 1
    print(feed, "matched tx records", n, flush=True)
xr = pd.DataFrame([dict(tx=k[0], feed=k[1], s=v[0], t=v[1], a=v[2], p=v[3], z=v[4], d=v[5]) for k, v in xm.items()])
xr.to_parquet(OUT + "/post17_xms.parquet", index=False)
print("xms rows", len(xr), "txs covered", xr.tx.nunique() if len(xr) else 0, "of", len(txs), round(time.time() - t0), "s", flush=True)
print("DONE", flush=True)
