"""X206 key-free part (information panel P3a, simplified): pre-game cross-book co-repricing moments. A feed that sends
pre-game messages (map picks / veto, lineups) makes the bot re-price several map books of an event at one moment before
the start; a relay of in-game state cannot. Filled maker orders (orders.parquet, 16-22 Oct), bursts per token (50 ms),
V-changes (top differs from the token's previous burst top); pre-game = signed before the event's game start. Moments =
V-changes on >= 2 DIFFERENT map books (child_moneyline) of the event within 1 s. Null: each book's pre-game V-change
times shifted by an independent uniform offset in +-[5, 30] min, kept inside the pre-game span, 200 draws. Also: the
share of observed moments with a wallet-free public print on any book of the event in the 5 s before (a public trigger).
Output: results/pregame_corepricing.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "price", "cid", "oi", "smt", "event", "role", "token_id", "gs_ts"])
o = o[(o.role == "maker") & (o.sign_ms > 1.7e12)].sort_values(["token_id", "sign_ms"])
egs = o.groupby("event").gs_ts.min()
o["egs"] = o.event.map(egs)
o["burst"] = (o.groupby("token_id").sign_ms.diff().fillna(1e12) > 50).cumsum()
b = o.groupby("burst").agg(t=("sign_ms", "min"), top=("price", "max"), tok=("token_id", "first"), cid=("cid", "first"), smt=("smt", "first"),
                           event=("event", "first"), egs=("egs", "first")).reset_index().sort_values(["tok", "t"])
b["dtop"] = b.groupby("tok").top.diff()
v = b[b.dtop.notna() & (b.dtop.abs() > 1e-9)].copy()
v["ts"] = v.t / 1000.0
pre = v[(v.ts < v.egs) & (v.smt == "child_moneyline")]
wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx"]).tx)
rng = np.random.default_rng(0)


def moments(times_by_book):
    allp = sorted((t, bk) for bk, ts in times_by_book.items() for t in ts)
    n, i = 0, 0
    out = []
    while i < len(allp):
        j = i
        books = {allp[i][1]}
        while j + 1 < len(allp) and allp[j + 1][0] - allp[i][0] <= 1.0:
            j += 1
            books.add(allp[j][1])
        if len(books) >= 2:
            out.append(allp[i][0])
            i = j + 1
        else:
            i += 1
    return out


obs, nulls, trig, n_ev = 0, np.zeros(200), [], 0
for ev, g in pre.groupby("event"):
    tb = {cid: h.ts.to_numpy(float) for cid, h in g.groupby("cid")}
    if len(tb) < 2:
        continue
    n_ev += 1
    lo, hi = g.ts.min(), float(g.egs.iloc[0])
    mo = moments(tb)
    obs += len(mo)
    for k in range(200):
        sh = {}
        for cid, ts in tb.items():
            off = rng.uniform(300, 1800) * rng.choice([-1, 1])
            x = ts + off
            span = max(hi - lo, 1.0)
            x = lo + np.mod(x - lo, span)
            sh[cid] = np.sort(x)
        nulls[k] += len(moments(sh))
    # public trigger: any wallet-free taker print on any book of the event in the 5 s before the moment
    cids = set(o.loc[o.event == ev, "cid"])
    pts = []
    for cid in cids:
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if p.exists():
            d = pd.read_parquet(p, columns=["timestamp", "transactionHash"])
            pts.append(d.loc[~d.transactionHash.isin(wtx), "timestamp"].to_numpy(float))
    pts = np.sort(np.concatenate(pts)) if pts else np.array([])
    for t in mo:
        k1, k0 = np.searchsorted(pts, t, side="right"), np.searchsorted(pts, t - 5, side="left")
        trig.append(bool(k1 > k0))
out = {"events_with_2plus_map_books_pregame": n_ev, "pregame_map_vchanges": int(len(pre)), "moments_obs": int(obs),
       "moments_null_mean": round(float(nulls.mean()), 2), "moments_null_p95": round(float(np.quantile(nulls, 0.95)), 2),
       "p_value": round(float((nulls >= obs).mean()), 4), "share_with_public_print_5s_before": round(float(np.mean(trig)), 3) if trig else None}
(RES / "pregame_corepricing.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
