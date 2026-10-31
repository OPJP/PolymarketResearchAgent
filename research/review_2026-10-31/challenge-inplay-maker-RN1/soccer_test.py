"""H-C: soccer goal / red-card quote pulling with ESPN soccer key events (public, wall-clock).

(a) ESPN wall clock vs first Polymarket tape jump (is the wall clock the event time?).
(b) Stale-quote returns of touch fills by seconds after goal; RN1 share 0-10 s vs other makers.
(c) Match: does 'no goal known in the last W s (goal wallclock + D)' predict RN1 being at the touch?
    D, W fitted on FIT games; TEST AUC vs a null that shifts each TEST game's key-event timeline by
    +-5..40 min (wrapping inside the game window), 1000 shifts.
(d) Backtest: slow public maker (fair = last print at t0-1 s, bids at floor(fair-delta), 10 s requote,
    trade-through and at-touch fills) that pauses P s after each goal/red card known at wallclock + D.
    delta, P fitted on FIT (strict per-market t) for each D; TEST strict / at-touch, HAC + bootstrap.
"""
import json, sys
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from common import S, W, implied_p0
from grid_maker import jump_times
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue

games = {g["event_slug"]: g for g in json.load(open(S / "soccer_games.json"))}
tk = pd.read_pickle(S / "soccer_taker.pkl"); mk = pd.read_pickle(S / "soccer_maker.pkl")
mm = {m["condition_id"]: m for m in json.load(open(S / "soccer_markets.json"))["markets"]}
ev_of = {c: m["event_slug"] for c, m in mm.items()}
kicks = {e: g["kick"] for e, g in games.items() if e in set(ev_of.values())}
split = np.median(list(kicks.values()))
period = {e: ("fit" if k < split else "test") for e, k in kicks.items()}
KEY = {e: np.array(sorted(k["ts"] for k in g["key_events"] if k["scoring"] or k["type"] in ("red-card", "penalty---saved", "penalty---missed")), dtype=np.int64) for e, g in games.items()}
GOALS = {e: np.array(sorted(k["ts"] for k in g["key_events"] if k["scoring"]), dtype=np.int64) for e, g in games.items()}
out = {"games": len(kicks), "markets": len(mm), "fit_games": sum(v == "fit" for v in period.values()), "test_games": sum(v == "test" for v in period.values()),
       "goals": int(sum(len(GOALS[e]) for e in kicks)), "key_events_used": int(sum(len(KEY[e]) for e in kicks))}

# (a) lag between ESPN goal wall clock and first >=5c jump on the event's tapes
lags = []
for e in kicks:
    g = tk[tk.event_slug == e]
    jt = []
    for cid, x in g.groupby("condition_id"):
        x = x.sort_values("ts"); ts = x.ts.to_numpy().astype(np.int64)
        if len(ts) > 2:
            jt.append(jump_times(ts, implied_p0(x), 0.05, 30))
    jt = np.sort(np.concatenate(jt)) if jt else np.array([])
    for gt in GOALS[e]:
        after = jt[(jt >= gt - 120) & (jt <= gt + 300)]
        if len(after):
            lags.append(int(after[0] - gt))
lags = np.array(lags)
out["espn_goal_vs_first_tape_jump_s"] = {"n": int(len(lags)), "quantiles_10_25_50_75_90": np.percentile(lags, [10, 25, 50, 75, 90]).tolist() if len(lags) else None,
                                          "share_tape_first": float((lags < 0).mean()) if len(lags) else None}

# touch events
mb = mk[mk.side == "BUY"]
rows = []
for cid, g in mb.groupby("condition_id"):
    ev = g.groupby(["tx", "outcome"]).agg(ts=("ts", "first"), q=("price", "max"), qmin=("price", "min")).reset_index()
    at = g.merge(ev[["tx", "outcome", "q"]], on=["tx", "outcome"]); at = at[np.abs(at.price - at.q) < 1e-9]
    ev = ev.join(at.groupby(["tx", "outcome"])["size"].sum().rename("size_q"), on=["tx", "outcome"])
    ev = ev.join(at.assign(w=at.wallet == W).groupby(["tx", "outcome"])["w"].any().rename("rn1"), on=["tx", "outcome"])
    ev["condition_id"] = cid; ev["event_slug"] = ev_of[cid]
    p0 = mm[cid]["pay0"]; ev["ret"] = np.where(ev.outcome == 0, p0, 1 - p0) - ev.q
    rows.append(ev)
E = pd.concat(rows, ignore_index=True)
E = E[E.event_slug.isin(kicks) & (E.ts >= E.event_slug.map(kicks))]
E["period"] = E.event_slug.map(period)
E["cap"] = np.minimum(E.size_q, 50)


def since_known(e_arr, ts, D):
    if len(e_arr) == 0:
        return np.full(len(ts), 1e7)
    known = e_arr + D
    k = np.searchsorted(known, ts - 1, side="right") - 1
    return np.where(k >= 0, ts - known[np.clip(k, 0, None)], 1e7)


def add_since(df, D, shift=None, which=KEY):
    s = np.full(len(df), 1e7)
    for e, idx in df.groupby("event_slug").groups.items():
        arr = which[e]
        if shift is not None:
            k0 = kicks[e]
            arr = np.sort(k0 + ((arr - k0 + shift[e]) % 9000))
        s[df.index.get_indexer(idx)] = since_known(arr, df.loc[idx, "ts"].to_numpy().astype(np.int64), D)
    return s

E = E.reset_index(drop=True)
E["sg0"] = add_since(E, 0, which=GOALS)
bins = [-1, 5, 10, 30, 60, 300, 1e8]
lab = ["0-5", "5-10", "10-30", "30-60", "60-300", "300+"]
E["b"] = pd.cut(E.sg0, bins, labels=lab)
stale = {}
for who, x in (("others_touch", E[~E.rn1]), ("rn1_touch", E[E.rn1])):
    stale[who] = {str(b): {"events": int(len(y)), "ret_cap50_usd": float((y.cap * y.ret).sum() / (y.cap * y.q).sum()) if len(y) else None, "share": float(len(y) / len(x))}
                  for b, y in x.groupby("b", observed=False)}
out["touch_returns_by_s_after_espn_goal"] = stale

# (c) match test
def auc_for(df, D, Wn, shift=None):
    s = add_since(df, D, shift)
    score = np.log1p(np.minimum(s, 1e4))  # larger = longer since last key event = calmer
    return roc_auc_score(df.rn1.astype(int), score) if Wn is None else roc_auc_score(df.rn1.astype(int), (s >= Wn).astype(float) + 1e-6 * score)

F = E[E.period == "fit"].reset_index(drop=True); T = E[E.period == "test"].reset_index(drop=True)
scan = []
for D in (0, 2, 5, 10, 20, 30, 60):
    for Wn in (10, 30, 60, 120, 300, None):
        scan.append({"D": D, "W": Wn, "fit_auc": auc_for(F, D, Wn)})
best = max(scan, key=lambda r: r["fit_auc"])
obs = auc_for(T, best["D"], best["W"])
rng = np.random.default_rng(3)
tg = T.event_slug.unique()
null = []
for _ in range(1000):
    sh = {e: int(rng.integers(300, 2400) * rng.choice([-1, 1])) for e in tg}
    null.append(auc_for(T, best["D"], best["W"], sh))
null = np.array(null)
out["match"] = {"fit_best": best, "fit_scan_top5": sorted(scan, key=lambda r: -r["fit_auc"])[:5], "test_auc": float(obs), "test_rn1_rate": float(T.rn1.mean()),
                "test_events": int(len(T)), "null_mean": float(null.mean()), "null_p99": float(np.quantile(null, 0.99)),
                "perm_p": float((1 + (null >= obs).sum()) / (1 + len(null)))}
print(json.dumps(out, indent=1))

# (d) backtest
REQ, SIZE, TICK = 10, 20.0, 0.01
fees = {c: (json.loads(m["fee"]) if isinstance(m["fee"], str) else m["fee"]) or {} for c, m in mm.items()}


def slots(cid, lat=1):
    g = tk[tk.condition_id == cid].sort_values("ts")
    e = ev_of[cid]
    if len(g) < 2 or e not in kicks:
        return None
    ts = g.ts.to_numpy().astype(np.int64); p0 = implied_p0(g)
    oc, sd, pr, sz = g.outcome.to_numpy(), g.side.to_numpy(), g.price.to_numpy(), g["size"].to_numpy()
    t0s = np.arange(int(kicks[e]), int(kicks[e]) + 9000, REQ)
    k = np.searchsorted(ts, t0s - lat, side="right") - 1
    lo = np.searchsorted(ts, t0s, side="right"); hi = np.searchsorted(ts, t0s + REQ, side="right")
    keep = (k >= 0) & (hi > lo); t0s, k, lo, hi = t0s[keep], k[keep], lo[keep], hi[keep]
    rec = {"condition_id": cid, "event_slug": e, "t0": t0s}
    pay0 = mm[cid]["pay0"]; rate = float(fees[cid].get("rate", 0) or 0); rr = float(fees[cid].get("rebateRate", 0) or 0)
    for d in (0.005, 0.01, 0.02):
        for o in (0, 1):
            fair = p0[k] if o == 0 else 1 - p0[k]
            q = np.floor((fair - d) / TICK + 1e-9) * TICK
            fs, ft = np.zeros(len(t0s)), np.zeros(len(t0s))
            for i in range(len(t0s)):
                if q[i] < TICK or q[i] > 1 - TICK:
                    continue
                a, b = lo[i], hi[i]
                o_, s_, p_, z_ = oc[a:b], sd[a:b], pr[a:b], sz[a:b]
                ms = ((o_ == o) & (s_ == "SELL") & (p_ < q[i] - 1e-9)) | ((o_ != o) & (s_ == "BUY") & (p_ > 1 - q[i] + 1e-9))
                mt = ((o_ == o) & (s_ == "SELL") & (p_ <= q[i] + 1e-9)) | ((o_ != o) & (s_ == "BUY") & (p_ >= 1 - q[i] - 1e-9))
                fs[i] = min(SIZE, z_[ms].sum()); ft[i] = min(SIZE, z_[mt].sum())
            pay = pay0 if o == 0 else 1 - pay0
            tag = f"{int(d*1000)}_{o}"
            rec[f"usd_s{tag}"] = fs * q; rec[f"pnl_s{tag}"] = fs * (pay - q)
            rec[f"usd_t{tag}"] = ft * q; rec[f"pnl_t{tag}"] = ft * (pay - q); rec[f"reb_t{tag}"] = ft * rate * q * (1 - q) * rr
    return pd.DataFrame(rec)

G = pd.concat([x for x in (slots(c) for c in mm) if x is not None], ignore_index=True)
G["period"] = G.event_slug.map(period)


def bt(Gx, d, model, D, P):
    s = add_since(Gx.rename(columns={"t0": "ts"}), D)
    m = s >= P
    tag = int(d * 1000)
    usd = Gx[f"usd_{model}{tag}_0"] + Gx[f"usd_{model}{tag}_1"]
    pnl = Gx[f"pnl_{model}{tag}_0"] + Gx[f"pnl_{model}{tag}_1"]
    per = pd.DataFrame({"c": Gx.condition_id, "usd": usd * m, "pnl": pnl * m}).groupby("c").sum()
    per = per[per.usd > 0]
    if len(per) < 5:
        return None
    t = hac_t_test(per.pnl.to_numpy())
    return {"markets": int(len(per)), "usd": float(per.usd.sum()), "pnl": float(per.pnl.sum()), "ret": float(per.pnl.sum() / per.usd.sum()), "t": t.statistic, "p": t.p_value,
            "boot_p": stationary_bootstrap_pvalue(per.pnl.to_numpy(), n_boot=2000).p_value}

Gf, Gt = G[G.period == "fit"].reset_index(drop=True), G[G.period == "test"].reset_index(drop=True)
res = {}
for D in (0, 5, 10, 30):
    sc = []
    for d in (0.005, 0.01, 0.02):
        for P in (0, 30, 60, 120, 300, 600):
            r = bt(Gf, d, "s", D, P)
            if r:
                sc.append((r["t"], d, P, r["ret"]))
    tbest, d, P, fret = max(sc)
    res[f"D={D}"] = {"fit_best": {"delta": d, "pause_s": P, "fit_t": tbest, "fit_ret": fret},
                     "test_strict": bt(Gt, d, "s", D, P), "test_at_touch": bt(Gt, d, "t", D, P)}
out["backtest_goal_pause"] = res
print(json.dumps(res, indent=1))
json.dump(out, open(S / "soccer_test.json", "w"), indent=1)
