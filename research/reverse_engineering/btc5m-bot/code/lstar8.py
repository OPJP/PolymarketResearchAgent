"""Iteration 8, X47 (panel-information iter7 P4): the bot's decision instant on Polymarket's own clock.
Live cluster taker orders with calldata limits (post/cd6_live.parquet, 10-31 13:00-14:47) inside my unthrottled book
recording (btc5m_clob_raw, 14:13:33-14:54:34; server ms): P(limit == ask_o(m - L)) for L = 0..1000 ms in 10-ms steps,
on all matches and on matches where ask_o changed in [m - 1000, m]; placebo = same orders at m +- U(5, 60) s.
Pay-up split: limit > ask(m - 10) (consumed touch) into stale (ask(m - L*) > ask(m - 10), the bot saw a higher ask) and
deliberate (ask(m - L*) == ask(m - 10) < limit), by size. Writes results/lstar8.json."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import sealed
from gate8 import raw_touch

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
A, B = 1793456040, 1793458470

cd = pd.read_parquet(os.path.join(ROOT, ".cache", "re", "btc5m-bot", "post", "cd6_live.parquet"))
cd = cd[(cd.role == "T") & cd.maker.str.lower().isin(set(L.W))].copy()
cd["limit"] = cd.maker_amt / cd.taker_amt; cd["size"] = cd.taker_amt
tok, books, trades = L.load_books(A, B)
mt = trades.groupby("tx").s_ms.min()
cd["m"] = cd.tx.map(mt)
cd = cd[cd.m.notna() & cd.token.isin(tok.keys())].copy()
cd["start"] = cd.token.map(lambda t: tok[t][1]); cd["up"] = cd.token.map(lambda t: tok[t][2])
cd = cd[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in cd.start], bool)]
cd = cd[(cd.m >= A * 1000 + 3000) & (cd.m < B * 1000)].drop_duplicates("tx")
R = raw_touch("btc5m_clob_raw", A, B)
print("orders", len(cd), "raw records", len(R), flush=True)
Ls = np.arange(0, 1001, 10)
rng = np.random.default_rng(5)


def asks_at(ms_shift):
    out = np.full((len(cd), len(Ls)), np.nan)
    for s0, rg in R.groupby("m"):
        sel = np.where(cd.start.to_numpy() == s0)[0]
        if not len(sel):
            continue
        rs = rg.s.to_numpy(np.int64); ba = rg.ba.to_numpy(float); bb = rg.bb.to_numpy(float)
        for j, i in enumerate(sel):
            t = int(cd.m.iat[i]) + int(ms_shift[i]) - Ls
            k = np.searchsorted(rs, t, "right") - 1
            v = np.where(cd.up.iat[i], ba[np.clip(k, 0, None)], 1 - bb[np.clip(k, 0, None)])
            v = v.astype(float); v[k < 0] = np.nan
            out[i] = v
    return out


real = asks_at(np.zeros(len(cd)))
pl = asks_at((rng.choice([-1, 1], len(cd)) * rng.uniform(5000, 60000, len(cd))).astype(np.int64))
lim = cd.limit.to_numpy(float)[:, None]
eq = np.abs(np.round(real, 2) - np.round(lim, 2)) < 0.005
eqp = np.abs(np.round(pl, 2) - np.round(lim, 2)) < 0.005
okr = np.isfinite(real).all(axis=1)
chg = okr & (np.nanmax(real, axis=1) - np.nanmin(real, axis=1) > 0.005)
res = {"orders": int(len(cd)), "covered": int(okr.sum()), "changed_in_1s": int(chg.sum())}
prof = []
for j, Lj in enumerate(Ls):
    prof.append([int(Lj), round(float(eq[okr, j].mean()), 3), round(float(eq[chg, j].mean()), 3) if chg.any() else None,
                 round(float(eqp[np.isfinite(pl[:, j]), j].mean()), 3)])
res["profile_L_all_changed_placebo"] = prof
for p in prof[::5]:
    print(p)
# plateau end: the largest L at which the changed-subset equality is still within 3 points of its maximum
ch = np.array([p[2] for p in prof], float)
jmax = int(np.nanargmax(ch)); thr = ch[jmax] - 0.03
jend = jmax
while jend + 1 < len(ch) and ch[jend + 1] >= thr:
    jend += 1
res["L_max"] = int(Ls[jmax]); res["L_star_plateau_end"] = int(Ls[jend]); res["eq_at_max"] = round(float(ch[jmax]), 3)
# pay-up split at L*
a10 = real[:, 1]; aS = real[:, jend]
pay = okr & (lim[:, 0] > a10 + 0.005)
stale = pay & (aS > a10 + 0.005); delib = pay & (np.abs(aS - a10) < 0.005)
sz = cd["size"].to_numpy(float)
res["payup"] = {"n_payup": int(pay.sum()), "share_payup": round(float(pay.sum() / max(okr.sum(), 1)), 3), "stale": int(stale.sum()), "deliberate": int(delib.sum()),
                "by_size": {str(int(s)): {"n": int((okr & (sz == s)).sum()), "payup": int((pay & (sz == s)).sum()), "stale": int((stale & (sz == s)).sum()),
                                          "deliberate": int((delib & (sz == s)).sum())} for s in sorted(set(sz[okr]))}}
print(json.dumps({k: v for k, v in res.items() if k != "profile_L_all_changed_placebo"}))
json.dump(res, open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "lstar8.json"), "w"), indent=1)
