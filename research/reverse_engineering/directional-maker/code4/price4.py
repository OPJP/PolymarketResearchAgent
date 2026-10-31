"""Price component (iteration 4): does the direction of the last clean print (did it hit a bid on s or lift an ask on s)
locate the cluster's bid better than R2's 'last print - 0.01'? STUDY case by case, VALIDATE aggregate only.
Point-in-time: the last clean print strictly before the fill second; Binance seconds published by the fill second - 2."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code"))
from features2 import Spot, fair_up  # noqa
C = HERE.parents[3] / ".cache/re/directional-maker/exam"
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
win = pd.read_parquet(C / "windows_5m.parquet")
f = pd.read_parquet(C / "fills_holdout.parquet")
mk = f[f.role == "maker"].copy()
ctx = set(f.txh)
s1 = pd.read_parquet(C / "spot_btc_1s.parquet"); sp = Spot(s1.sec.to_numpy(), s1.px.to_numpy())
tok = {**{t: (c, 1) for t, c in zip(win.up_token, win.cid)}, **{t: (c, 0) for t, c in zip(win.down_token, win.cid)}}
info = win.set_index("cid")
out = []
for d in range(1792713600, 1793404800, 86400):
    t = pd.read_parquet(C / f"taker5m_day_{d}.parquet")
    t = t[~t.tx.isin(ctx) & ~t.wallet.isin(W)]
    t = t.merge(win[["cid", "up_token"]], on="cid")
    is_up = (t.asset == t.up_token).to_numpy()
    buy = (t.side.astype(str) == "BUY").to_numpy()
    t["up_px"] = np.where(is_up, t.price, 1 - t.price)
    # print hit a bid on Up iff taker SELL Up or taker BUY Down (mint/merge against an Up bid)
    t["hit_up_bid"] = (is_up & ~buy) | (~is_up & buy)
    by = {c: (g.ts.to_numpy(), g.up_px.to_numpy(), g.hit_up_bid.to_numpy()) for c, g in t.sort_values("ts", kind="stable").groupby("cid")}
    m = mk[(mk.ts >= d) & (mk.ts < d + 86400)]
    for r in m.itertuples(index=False):
        v = tok.get(r.token_id)
        if v is None or v[0] not in by:
            continue
        cid, su = v
        ts_, px_, hb_ = by[cid]
        i = np.searchsorted(ts_, r.ts, side="left") - 1
        if i < 0:
            continue
        ls = px_[i] if su else 1 - px_[i]
        hit_bid_s = hb_[i] if su else not hb_[i]  # an Up-bid hit is a Down-ask lift
        st, en = int(info.loc[cid, "start_ts"]), int(info.loc[cid, "end_ts"])
        tp = int(ts_[i]); tf = int(r.ts) - 2
        fu_p = float(fair_up(sp, np.array([st]), np.array([en]), np.array([max(tp, st)]))[0][0])
        fu_f = float(fair_up(sp, np.array([st]), np.array([en]), np.array([max(tf, st)]))[0][0])
        dfair = (fu_f - fu_p) if su else (fu_p - fu_f)
        out.append((d, r.price, ls, hit_bid_s, dfair, r.ts - tp, r.shares))
o = pd.DataFrame(out, columns=["day", "price", "ls", "hit_bid", "dfair", "age", "shares"])
o["half"] = np.where(o.day < 1793059200, "STUDY", "VALIDATE")
cands = {
    "R2: last-0.01": (o.ls - 0.01).round(2),
    "dir: last if bid hit else last-0.01": np.where(o.hit_bid, o.ls, o.ls - 0.01).round(2),
    "dir + 0.5*dfair": (np.where(o.hit_bid, o.ls, o.ls - 0.01) + 0.5 * o.dfair).round(2),
    "dir + 1.0*dfair": (np.where(o.hit_bid, o.ls, o.ls - 0.01) + 1.0 * o.dfair).round(2),
    "last-0.01 + 0.5*dfair": (o.ls - 0.01 + 0.5 * o.dfair).round(2),
}
for h, g in o.groupby("half"):
    line = {"n": len(g)}
    for k, p in cands.items():
        e = np.abs(g.price.to_numpy() - np.asarray(p)[g.index])
        line[k] = (round(float(np.mean(e <= 0.0105)), 4), round(float(np.mean(e < 0.0005)), 4))
    print(h, line)
g = o[o.half == "STUDY"]
e = g.price - (g.ls - 0.01).round(2)
print("STUDY R2 error by last-print direction:", g.assign(e=e.round(2)).groupby("hit_bid").e.value_counts(normalize=True).round(3).groupby(level=0).head(4).to_dict())
