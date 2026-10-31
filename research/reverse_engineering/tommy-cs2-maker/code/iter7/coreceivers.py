"""Iteration 7: the co-receivers of the wallet's taker events (assumptions panel iter6 P1 step 1 = X97, P3 steps 1-2 =
X99). 16-22 Oct full matched-order record (calldata_all = every tx with a wallet order, calldata_pub = every other taker
tx in its markets). Development data only (every record before H).

Part A, fan-out signature (X97 step 1, pre-registered by the panel): offsets d = signer stamp - wallet stamp of the
closest BUY taker order on the same token (P4e 0x4ebc2722 in [-120, +20] ms, 0x2005d16a in [-80, +40] ms) for every
wallet BUY taker order. Variance components by MixedLM (groups = event; fixed: platform Kick / Twitch / other, match vs
map leg, day, game-time tercile). Decision (pre-registered): shared push feed if the event random-effect SD and the
platform difference are each < 15 / 20 ms; per-subscriber stream pipelines if either >= 100 ms.

Part B, Y1 on the taker module (X99 step 2): units = census informed bursts (3c+ in 10 s) that contain a P4e BUY
signing within [t0 - 1 s, t0 + 10 s]. Edge left after P4e = shares bought by OTHER later takers (not P4e, not the
wallet) on the same token, signed in (p, p + 3 s], at limits <= P4e's limit + 0.5c (stale asks still there after P4e's
match). Large edge: P4e fully filled, move10 >= 5c and edge left >= 100 shares. Statistic: the wallet's presence (any
wallet BUY take on the token in [p - 20 ms, p + 300 ms], or labelled led / near) by edge class and by reversal type
(previous census burst in the market within 5-120 s on the other team vs same team vs none). Y1 (sees, declines by
edge) predicts presence rising with edge; Y2 (blind to those events) predicts ~0 at large edge on same-team follow-ons.
Output: results/coreceivers.json
"""
from __future__ import annotations

import glob
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
H = 1792713600
P4E, R2 = "0x4ebc2722", "0x2005d16a"


def load_takers():
    cols = ["tx", "idx", "maker", "side", "token_id", "price", "shares", "fill", "sign_ms"]
    ca = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["cid", "oi", "smt", "gs_ts", "event"])
    meta = ca.drop_duplicates("token_id")[["token_id", "cid", "oi", "smt", "gs_ts", "event"]]
    pub = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(OUT / "calldata_pub/*.parquet")))])
    T = pd.concat([ca[ca.idx == -1][cols], pub[pub.idx == -1][cols]]).drop_duplicates(["tx"])
    T["token_id"] = T.token_id.astype(str)
    meta["token_id"] = meta.token_id.astype(str)
    T = T.merge(meta, on="token_id", how="inner")
    T["maker"] = T.maker.str.lower()
    T = T[(T.side == 0) & (T.sign_ms > 1.79e12) & (T.sign_ms < H * 1000)]
    return T


def part_a(T, em):
    import statsmodels.formula.api as smf
    wt = T[T.maker == W]
    out = {}
    plat = em.set_index("event_slug").resolution_source.str.extract(r"(kick|twitch)", expand=False).fillna("other")
    for who, lo, hi in ((P4E, -120, 20), (R2, -80, 40)):
        g = {k: v.sign_ms.to_numpy() for k, v in T[T.maker.str.startswith(who)].groupby("token_id")}
        rows = []
        for r in wt.itertuples():
            a = g.get(r.token_id)
            if a is None:
                continue
            x = a - r.sign_ms
            x = x[(x >= lo) & (x <= hi)]
            if len(x):
                c = (lo + hi) / 2
                rows.append({"d": float(x[np.argmin(np.abs(x - c))]), "event": r.event, "smt": r.smt,
                             "day": pd.to_datetime(r.sign_ms, unit="ms").strftime("%m-%d"),
                             "gmin": (r.sign_ms / 1000 - r.gs_ts) / 60})
        D = pd.DataFrame(rows)
        D["platform"] = D.event.map(plat).fillna("other")
        D["gt3"] = pd.qcut(D["gmin"], 3, labels=["early", "mid", "late"]).astype(str)
        o = {"n": int(len(D)), "events": int(D.event.nunique()),
             "median_ms": round(float(D.d.median()), 1),
             "iqr_ms": round(float(np.subtract(*np.percentile(D.d, [75, 25]))), 1),
             "by_platform": D.groupby("platform").d.agg(["count", "median"]).round(1).to_dict("index"),
             "by_leg": D.groupby("smt").d.agg(["count", "median"]).round(1).to_dict("index"),
             "by_gametime": D.groupby("gt3").d.agg(["count", "median"]).round(1).to_dict("index"),
             "by_day": D.groupby("day").d.agg(["count", "median"]).round(1).to_dict("index")}
        try:
            m = smf.mixedlm("d ~ C(platform) + C(smt) + C(gt3) + C(day)", D, groups=D["event"]).fit(reml=True)
            o["mixedlm"] = {"event_sd_ms": round(float(np.sqrt(max(m.cov_re.iloc[0, 0], 0))), 2),
                            "resid_sd_ms": round(float(np.sqrt(m.scale)), 2),
                            "fe": {k: [round(float(v), 2), round(float(m.pvalues[k]), 4)] for k, v in m.params.items()
                                   if k != "Group Var"}}
        except Exception as e:  # noqa: BLE001
            o["mixedlm"] = str(e)[:200]
        # bootstrap of the Kick - Twitch median difference over events
        ev = D.event.unique()
        rng = np.random.default_rng(7)
        bd = []
        byev = {e: D[D.event == e] for e in ev}
        for _ in range(2000):
            s = pd.concat([byev[e] for e in rng.choice(ev, len(ev))])
            k, t = s[s.platform == "kick"].d, s[s.platform == "twitch"].d
            if len(k) > 3 and len(t) > 3:
                bd.append(k.median() - t.median())
        if bd:
            o["kick_minus_twitch_ms_ci95"] = [round(float(x), 1) for x in np.percentile(bd, [2.5, 50, 97.5])]
        es = D.groupby("event").d.agg(["count", "median"])
        o["between_event_sd_of_median_ms_events_ge4"] = round(float(es[es["count"] >= 4]["median"].std()), 1)
        out[who] = o
    return out


def part_b(T, cb):
    p4 = T[T.maker.str.startswith(P4E)].sort_values("sign_ms")
    wtk = {k: np.sort(v.sign_ms.to_numpy()) for k, v in T[T.maker == W].groupby("token_id")}
    oth = T[(T.maker != W) & ~T.maker.str.startswith(P4E)]
    othg = {k: v.sort_values("sign_ms") for k, v in oth.groupby("token_id")}
    p4g = {k: v for k, v in p4.groupby("token_id")}
    tokmap = T.drop_duplicates(["cid", "oi"]).set_index(["cid", "oi"]).token_id.to_dict()
    cb = cb.sort_values(["cid", "t0"]).copy()
    prev = []
    for cid, g in cb.groupby("cid", sort=False):
        t, oi = g.t0.to_numpy(), g.oi.to_numpy()
        for i in range(len(g)):
            j = i - 1
            typ = "none"
            if j >= 0 and 5 <= t[i] - t[j] <= 120:
                typ = "other_team" if oi[j] != oi[i] else "same_team"
            prev.append(typ)
    cb["prev"] = prev
    rows = []
    for r in cb.itertuples():
        tk = tokmap.get((r.cid, r.oi))
        if tk is None or tk not in p4g:
            continue
        g = p4g[tk]
        s = g.sign_ms.to_numpy()
        lo, hi = np.searchsorted(s, r.t0 * 1000 - 1000), np.searchsorted(s, r.t0 * 1000 + 10000)
        if hi <= lo:
            continue
        x = g.iloc[lo]
        p, L = float(x.sign_ms), float(x.price)
        full = float(x.fill) >= 0.99 * float(x.shares)
        og = othg.get(tk)
        left = 0.0
        if og is not None:
            os_ = og.sign_ms.to_numpy()
            a, b = np.searchsorted(os_, p + 1), np.searchsorted(os_, p + 3000)
            sub = og.iloc[a:b]
            left = float(sub[(sub.price <= L + 0.0051) & (sub.fill > 0)].fill.sum())
        wa = wtk.get(tk)
        co = bool(wa is not None and np.any((wa >= p - 20) & (wa <= p + 300)))
        rows.append({"label": r.label, "split": r.split, "prev": r.prev, "move10": float(r.move10), "full": full,
                     "left": left, "co": co, "p4_first": bool(lo == np.searchsorted(s, r.t0 * 1000 - 1000))})
    D = pd.DataFrame(rows)
    D["present"] = D.label.isin(["wallet-led", "wallet-near"]) | D.co
    D["large"] = D.full & (D.move10 >= 0.05) & (D.left >= 100)
    D["edge_cls"] = np.where(D.large, "large", np.where(D.left >= 100, "left>=100", np.where(D.left > 0, "left>0", "none")))
    out = {"bursts_with_p4e": int(len(D)), "present_rate": round(float(D.present.mean()), 3)}
    out["by_edge"] = D.groupby("edge_cls").present.agg(["count", "mean"]).round(3).to_dict("index")
    out["by_prev_x_large"] = D.groupby(["prev", "large"]).present.agg(["count", "mean"]).round(3).reset_index().to_dict("records")
    D["mv"] = pd.cut(D.move10, [0.0299, 0.04, 0.06, 0.10, 1.0], labels=["3-4c", "4-6c", "6-10c", "10c+"]).astype(str)
    out["by_move10"] = D.groupby("mv").present.agg(["count", "mean"]).round(3).to_dict("index")
    out["by_split_large"] = D.groupby(["split", "large"]).present.agg(["count", "mean"]).round(3).reset_index().to_dict("records")
    # logistic: present ~ log1p(left) + move10 + prev + full
    try:
        import statsmodels.formula.api as smf
        D["ll"] = np.log1p(D.left)
        D["y"] = D.present.astype(int)
        m = smf.logit("y ~ ll + move10 + C(prev) + full", D).fit(disp=0)
        out["logit"] = {k: [round(float(v), 3), round(float(m.pvalues[k]), 4)] for k, v in m.params.items()}
    except Exception as e:  # noqa: BLE001
        out["logit"] = str(e)[:200]
    return out


def main():
    T = load_takers()
    em = pd.read_parquet(OUT / "events_meta.parquet", columns=["event_slug", "resolution_source", "league"])
    cb = pd.read_parquet(OUT / "census_bursts.parquet")
    res = {"part_a_fanout": part_a(T, em), "part_b_y1_taker": part_b(T, cb)}
    (RES / "coreceivers.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
