"""Q1 step 2 (partial): does R3's price rule (last clean print on s - 0.01) and the edge story transfer to BTC 15m?
Cluster BTC 15m BUY fills (lot activity), role from the 15m taker tape (cluster wallet as taker -> taker), clean tape =
prints not in a cluster transaction. STUDY case by case, VALIDATE aggregate."""
import json, glob
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache/re/directional-maker"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
w = pd.read_parquet(C / "t15" / "windows_15m.parquet")
acts = []
for addr, n in CL.items():
    a = pd.read_parquet(C / "exam" / f"activity_{n}.parquet"); a["wallet"] = addr; acts.append(a)
a = pd.concat(acts)
a = a[(a.type == "TRADE") & a.slug.str.startswith("btc-updown-15m", na=False)]
a["start"] = a.slug.str.extract(r"-(\d{9,})$")[0].astype(np.int64)
res = {}
for name, (s0, s1) in (("study", (1792713600, 1793059200)), ("validate", (1793059200, 1793404800))):
    aa = a[(a.start >= s0) & (a.start < s1)]
    days = range(s0, s1, 86400)
    tk = pd.concat([pd.read_parquet(C / "t15" / f"taker15m_day_{d}.parquet") for d in days])
    ctx = set(aa.transactionHash.str.lower())
    tk["txl"] = tk.tx.str.lower()
    own_taker = set(zip(tk[tk.wallet.isin(CL)].txl, tk[tk.wallet.isin(CL)].wallet))
    aa = aa.assign(txl=aa.transactionHash.str.lower())
    aa["role"] = ["taker" if (x, y) in own_taker else "maker" for x, y in zip(aa.txl, aa.wallet)]
    clean = tk[~tk.txl.isin(ctx) & ~tk.wallet.isin(CL)]
    wi = w.set_index("cid")
    clean = clean.join(wi[["up_token"]], on="cid")
    clean["up_px"] = np.where(clean.asset == clean.up_token, clean.price, 1 - clean.price)
    by = {c: (g.ts.to_numpy(), g.up_px.to_numpy()) for c, g in clean.sort_values("ts", kind="stable").groupby("cid")}
    mk = aa[(aa.role == "maker") & (aa.side == "BUY")]
    pred, act, rel = [], [], []
    for r in mk.itertuples(index=False):
        x = by.get(r.conditionId)
        if x is None: continue
        i = np.searchsorted(x[0], r.timestamp, side="left") - 1
        if i < 0: continue
        up = r.outcome == "Up"
        ls = x[1][i] if up else 1 - x[1][i]
        pred.append(round(ls - 0.01, 2)); act.append(r.price); rel.append(r.timestamp - r.start)
    e = np.abs(np.array(act) - np.array(pred))
    pay = wi.up_payout
    mk = mk.assign(won=np.where(mk.outcome == "Up", mk.conditionId.map(pay), 1 - mk.conditionId.map(pay)))
    ret = float(((mk.won - mk.price) * mk["size"]).sum() / (mk.price * mk["size"]).sum())
    res[name] = {"fills": int(len(aa)), "maker_share": round(float((aa.role == "maker").mean()), 3), "maker_buy_fills": int(len(mk)),
                 "price_rule_within_tick": round(float(np.mean(e <= 0.0105)), 3), "price_rule_exact": round(float(np.mean(e < 0.0005)), 3),
                 "fill_time_quantiles_s": pd.Series(rel).quantile([.1, .5, .9]).round(0).tolist(), "maker_return_on_usd": round(ret, 4),
                 "on_001_grid": round(float(np.mean(np.abs(mk.price * 100 - np.round(mk.price * 100)) < 1e-6)), 3),
                 "sizes_top": mk["size"].round(1).value_counts().head(6).to_dict()}
    print(name, res[name])
(ROOT / "research/reverse_engineering/directional-maker/results/iter5_q1_15m.json").write_text(json.dumps(res, indent=1))
