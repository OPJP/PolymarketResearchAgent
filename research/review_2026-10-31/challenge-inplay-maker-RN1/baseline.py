"""Baseline facts on the 160-market sample: passive BUY fill returns for RN1 vs other makers,
and their dependence on public-tape state (seconds since last tape jump)."""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from common import load, W, tape_state, S
from polyrea.stats.significance import hac_t_test

tk, mk, meta = load()
pay = meta["payouts"]
fam = meta["family"]
mb = mk[mk.side == "BUY"].copy()
mb["pay"] = np.where(mb.outcome == 0, mb.condition_id.map(pay), 1 - mb.condition_id.map(pay))
mb["usd"] = mb["price"] * mb["size"]
mb["pnl"] = mb["size"] * (mb["pay"] - mb["price"])
mb["is_w"] = mb.wallet == W
mb["period"] = np.where(mb.condition_id.isin(meta["test"]), "test", "fit")
mb["fam"] = mb.condition_id.map(fam)
mb["fam2"] = mb["fam"].map(lambda f: "tennis" if f in ("sports:atp", "sports:wta", "sports:itf") else ("esports" if f.startswith("esports") else ("us" if f in ("sports:nfl", "sports:cfb", "sports:nba", "sports:mlb", "sports:nhl", "sports:wnba") else "soccer/other")))
out = {}

def summ(d):
    per_m = d.groupby("condition_id")["pnl"].sum()
    t = hac_t_test(per_m.to_numpy()) if len(per_m) > 3 else None
    return {"fills": int(len(d)), "markets": int(per_m.size), "usd": float(d.usd.sum()), "pnl": float(d.pnl.sum()),
            "ret": float(d.pnl.sum() / d.usd.sum()) if d.usd.sum() else None, "per_market_p_gt0": t.p_value if t else None}

for per in ("fit", "test", "all"):
    d = mb if per == "all" else mb[mb.period == per]
    out[per] = {"rn1": summ(d[d.is_w]), "others": summ(d[~d.is_w])}
out["by_family_all"] = {f: {"rn1": summ(g[g.is_w]), "others": summ(g[~g.is_w])} for f, g in mb.groupby("fam2")}

# PIT tape state for every passive buy (latency 0 - uses prints strictly before the fill second)
parts = []
for cid, g in mb.groupby("condition_id"):
    tkm = tk[tk.condition_id == cid]
    last, sj, rng = tape_state(tkm, g["ts"].to_numpy(), latency=0, jump=0.05, look=30)
    gg = g.copy()
    gg["last_p0"], gg["since_jump"], gg["rng30"] = last, sj, rng
    parts.append(gg)
mb = pd.concat(parts)
# price of the fill relative to the last implied price of the bought outcome
mb["last_po"] = np.where(mb.outcome == 0, mb.last_p0, 1 - mb.last_p0)
mb["offset"] = (mb["price"] - mb["last_po"]).round(3)
bins = [-1, 5, 10, 30, 60, 300, 1e10]
mb["sj_bin"] = pd.cut(mb.since_jump, bins, labels=["0-5", "5-10", "10-30", "30-60", "60-300", "300+"])
tab = {}
for who, g in (("rn1", mb[mb.is_w]), ("others", mb[~mb.is_w])):
    tab[who] = {str(b): {"fills": int(len(x)), "usd": float(x.usd.sum()), "ret": float(x.pnl.sum() / x.usd.sum()) if len(x) else None,
                         "share_fills": float(len(x) / len(g))} for b, x in g.groupby("sj_bin", observed=False)}
out["by_seconds_since_tape_jump_5c_30s"] = tab
off = {}
for who, g in (("rn1", mb[mb.is_w]), ("others", mb[~mb.is_w])):
    q = g.offset.dropna()
    off[who] = {"median": float(q.median()), "share_at_or_above_last": float((q >= -0.0001).mean()),
                "share_1c_below": float(((q < -0.0001) & (q >= -0.0101)).mean()), "share_more_than_1c_below": float((q < -0.0101).mean()),
                "ret_by_offset": {str(k): float(x.pnl.sum() / x.usd.sum()) for k, x in g.groupby(pd.cut(g.offset, [-1, -0.0201, -0.0101, -0.0001, 0.0001, 1])) if len(x)}}
out["fill_price_minus_last_print"] = off
mb.to_pickle(S / "passive_buys_annotated.pkl")
print(json.dumps(out, indent=1))
json.dump(out, open(S / "baseline.json", "w"), indent=1)
