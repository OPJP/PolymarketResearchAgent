"""Examiner round 2: independent recomputation of the BTC 5m presence, side and price metrics on lot f1.

Inputs: the rule's own lot panel and clean tape as built by the frozen evaluate() (captured, ev/), the examiner's own
activity fetch (trades_f1.parquet) for the labels, the full taker tape (ev/sel_tk_*), Gamma priceToBeat (exam cache), the
Chainlink BTC/USD values from the shared recorder's sealed 'rtds' feed (18:00-06:00) and from the endpoint values the
evaluate() run fetched (06-12, exam cache), and the shared recorder's sealed 'x' and 'q' records for the match clock.
Writes results/exam_r2_metrics.json and .cache/exam/directional-maker/side_fills.parquet / price_fills.parquet.
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import norm
from sklearn.metrics import roc_auc_score

from r2_common import CLUSTER, EXC, LOT, RES, ROOT, WS, iter_feed

import live  # noqa: E402  (tools/live.py)
from features2 import Spot, fair_up  # noqa: E402
from train2 import SETS  # noqa: E402
from r2_baseline_fit import add_clock, add_ext, SETS as XSETS  # noqa: E402

EV = EXC / "ev"
CODE = WS / "code"
CUT = json.loads((RES / "exam_r2_step0.json").read_text())["cut_ts"]
FEATS = {"rule": SETS["all_path_xwin"] + ["hour_utc", "dow", "us_session"], "activity": SETS["activity"],
         "own": SETS["all_path_xwin"] + ["hour_utc", "dow", "us_session", "inv_s", "inv_o"]}
NB = 2000
RNG = np.random.default_rng(7)


def auc(y, s):
    y = np.asarray(y); s = np.asarray(s, float)
    ok = np.isfinite(s)
    return float(roc_auc_score(y[ok], s[ok])) if 0 < y[ok].sum() < ok.sum() else float("nan")


def block_boot_gain(y, a, b, blocks, nb=NB, seed=11):
    """2-h block bootstrap of AUC(a) - AUC(b); returns (gain, lo, hi, p_one_sided_gain_le_0)."""
    rng = np.random.default_rng(seed)
    ub = np.unique(blocks)
    idx = {u: np.nonzero(blocks == u)[0] for u in ub}
    g0 = auc(y, a) - auc(y, b)
    gs = []
    for _ in range(nb):
        pick = rng.choice(ub, size=len(ub), replace=True)
        ii = np.concatenate([idx[u] for u in pick])
        gs.append(auc(y[ii], a[ii]) - auc(y[ii], b[ii]))
    gs = np.array(gs)
    return float(g0), float(np.nanquantile(gs, 0.025)), float(np.nanquantile(gs, 0.975)), float((np.sum(gs <= 0) + 1) / (nb + 1))


def chainlink_series():
    """btc/usd Chainlink value by value-stamp second: shared 'rtds' sealed + dev, then the exam endpoint cache."""
    out = {}
    for r in iter_feed("rtds", LOT[0][0] - 600, LOT[-1][1] + 600, need=b"btc"):
        try:
            j = json.loads(r["m"])
        except (KeyError, ValueError, TypeError):
            continue
        pl = j.get("payload") or {}
        if str(pl.get("symbol", "")).lower() not in ("btc/usd",):
            continue
        if j.get("topic") not in ("crypto_prices", "crypto_prices_chainlink"):
            continue
        for x in pl.get("data", []) or []:
            try:
                out.setdefault(int(x["timestamp"]) // 1000, float(x["value"]))
            except (KeyError, TypeError, ValueError):
                pass
    n_live = len(out)
    for f in (EXC / "cl").glob("*.parquet"):
        g = pd.read_parquet(f)
        if not {"tau", "open", "close"} <= set(g.columns):
            continue
        for t, o, c in zip(g["tau"].astype(np.int64), g["open"], g["close"]):
            if o is not None and np.isfinite(o):
                out.setdefault(int(t), float(o))
            if c is not None and np.isfinite(c):
                out.setdefault(int(t) + 300, float(c))
    return out, n_live


def ptb_of(w):
    from polyrea.workflows.updown_study import fetch_windows
    raw = fetch_windows([f"btc-updown-5m-{int(s)}" for s in w["start_ts"]])
    out = {}
    for m in raw.values():
        st = int(str(m.get("slug")).rsplit("-", 1)[1])
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                out[st] = float(v)
    return out


def main():
    t0 = time.time()
    res = {"cut_ts": CUT}
    w = pd.read_parquet(EV / "w5.parquet")
    w["up_token"], w["down_token"] = w["up_token"].astype(str), w["down_token"].astype(str)
    p = pd.read_parquet(EV / "panel5.parquet")
    p = add_clock(add_ext(p))
    for nm in ("rule", "activity", "own"):
        p["p_" + nm] = lgb.Booster(model_file=str(CODE / f"presence3_{nm}.txt")).predict(p[FEATS[nm]])
    for nm, fs in XSETS.items():
        p["x_" + nm] = lgb.Booster(model_file=str(EXC / "models" / f"exam_{nm}.txt")).predict(p[fs])
    # ---- labels from the examiner's own activity fetch; role from the full taker tape
    T = pd.read_parquet(EXC / "trades_f1.parquet")
    tk = pd.concat([pd.read_parquet(f) for f in EV.glob("sel_tk_*.parquet")], ignore_index=True)
    own_taker = tk[tk["wallet"].str.lower().isin(set(CLUSTER))]
    tx_full = {}
    A = pd.read_parquet(EXC / "activity_f1_all.parquet")
    for h in A["tx"].dropna().unique():
        try:
            tx_full[int(str(h)[2:17], 16)] = h
        except ValueError:
            pass
    taker_pairs = set(zip([tx_full.get(int(x), "") for x in own_taker["tx"]], own_taker["wallet"].str.lower()))
    inv_name = {v: k for k, v in CLUSTER.items()}
    T["addr"] = T["wallet"].map(inv_name)
    toks = {**{t: (c, 1, s, e) for t, c, s, e in zip(w.up_token, w.cid, w.start_ts, w.end_ts)},
            **{t: (c, 0, s, e) for t, c, s, e in zip(w.down_token, w.cid, w.start_ts, w.end_ts)}}
    B5 = T[T.asset.isin(set(toks)) & (T.side == "BUY")].copy()
    B5["role"] = ["taker" if (h, a) in taker_pairs else "maker" for h, a in zip(B5.tx, B5.addr)]
    B5.to_parquet(EXC / "btc5m_buys.parquet", index=False)
    mk = B5[B5.role == "maker"].copy()
    mk["cid"] = mk.asset.map(lambda t: toks[t][0])
    mk["is_up"] = mk.asset.map(lambda t: toks[t][1])
    mk["st"] = mk.asset.map(lambda t: toks[t][2])
    mk["en"] = mk.asset.map(lambda t: toks[t][3])
    mk["rel"] = ((mk.ts - mk.st) // 10 * 10).astype(int)
    res["labels"] = {"btc5m_buy_trades": int(len(B5)), "maker": int(len(mk)), "taker": int((B5.role == "taker").sum()),
                     "rule_mk_fills": int(len(pd.read_parquet(EV / "mk5.parquet")))}
    key = set(zip(mk.cid, mk.is_up, mk.rel))
    p["y_ex"] = [int((c, s, r) in key) for c, s, r in zip(p.cid, p.side_up, p.rel)]
    res["labels"]["bins_agree_with_rule_y"] = float((p.y_ex == p.y).mean())
    p["blk"] = (p.start_ts // 7200).astype(int)
    p["half"] = np.where(p.start_ts < CUT, "early", "late")
    y = p["y_ex"].to_numpy()

    def pres(mask, yy):
        d = {}
        for c in ("p_rule", "p_activity", "p_own", "x_activity_refit", "x_act_ext", "x_act_clock"):
            d[c] = auc(yy[mask], p[c].to_numpy()[mask])
        d["pos"] = int(yy[mask].sum()); d["n"] = int(mask.sum())
        strong = max(("p_activity", "x_act_ext"), key=lambda c: d[c])
        d["stronger_baseline"] = strong
        g, lo, hi, pv = block_boot_gain(yy[mask], p["p_rule"].to_numpy()[mask], p[strong].to_numpy()[mask], p["blk"].to_numpy()[mask])
        d.update({"gain": g, "gain_ci95": [lo, hi], "gain_p_le0": pv, "blocks": int(len(np.unique(p['blk'].to_numpy()[mask])))})
        return d
    allm = np.ones(len(p), bool)
    pc = EXC / "presence_cache.json"
    if pc.exists():
        res["presence"] = json.loads(pc.read_text())
    else:
        res["presence"] = {"pooled": pres(allm, y)}
        for h in ("early", "late"):
            res["presence"][h] = pres((p.half == h).to_numpy(), y)
        res["presence"]["per_wallet"] = {}
        for addr, nm in CLUSTER.items():
            k = set(zip(mk.cid[mk.addr == addr], mk.is_up[mk.addr == addr], mk.rel[mk.addr == addr]))
            yw = np.array([int((c, s, r) in k) for c, s, r in zip(p.cid, p.side_up, p.rel)])
            res["presence"]["per_wallet"][nm] = {"all": pres(allm, yw), "early": pres((p.half == "early").to_numpy(), yw),
                                                 "late": pres((p.half == "late").to_numpy(), yw), "fills": int((mk.addr == addr).sum())}
        act = p.groupby("cid")["y_ex"].transform("max").to_numpy() > 0
        res["presence"]["within_active_windows"] = {"rule": auc(y[act], p.p_rule.to_numpy()[act]), "activity": auc(y[act], p.p_activity.to_numpy()[act])}
        res["presence"]["active_window_share"] = float(p.groupby("cid")["y_ex"].max().mean())
        pc.write_text(json.dumps(res["presence"], default=str))
    p.to_parquet(EXC / "panel5_scored.parquet", index=False)
    print("presence done", round(time.time() - t0, 1), flush=True)

    # ---- side (R8c public): per BTC 5m maker fill on the block clock
    sp_d = pd.read_parquet(EV / "spot_btc.parquet")
    sp = Spot(sp_d["sec"].to_numpy(), sp_d["px"].to_numpy())
    clean = pd.read_parquet(EV / "clean5.parquet")
    cl, n_live = chainlink_series()
    ptb = ptb_of(w)
    upof = dict(zip(w.cid, w.up_token))
    mids = {}
    for cid, g in clean.groupby("cid"):
        g = g.sort_values("ts", kind="stable")
        pr = g.price.to_numpy(float)
        mids[cid] = (g.ts.to_numpy(np.int64), np.where(g.asset.to_numpy() == upof[cid], pr, 1 - pr))
    # cluster inventory (all three wallets, maker + taker BUY rows) for the own-inventory baselines
    B5["cid"] = B5.asset.map(lambda t: toks[t][0])
    B5["is_up"] = B5.asset.map(lambda t: toks[t][1])
    inv = {c: (g.ts.to_numpy(np.int64), np.cumsum(np.where(g.is_up == 1, g["size"], -g["size"]).astype(float)), g.is_up.to_numpy())
           for c, g in B5.sort_values("ts", kind="stable").groupby("cid")}
    rows = []
    for r in mk.itertuples(index=False):
        if r.cid not in mids:
            continue
        ts_, mu_ = mids[r.cid]
        b = int(r.ts)
        i = np.searchsorted(ts_, b - 3, side="right") - 1
        if i < 0:
            continue
        mid = float(mu_[i])
        i2 = np.searchsorted(ts_, b, side="left") - 1  # last clean print strictly before the fill second
        prev_mid = float(mu_[i - 1]) if i >= 1 else np.nan
        it, ic, iu = inv.get(r.cid, (np.array([], np.int64), np.array([]), np.array([])))
        j = np.searchsorted(it, b, side="left") - 1
        net = float(ic[j]) if j >= 0 else 0.0
        prev_up = int(iu[j]) if j >= 0 else -1
        clv = cl.get(b - 4, np.nan)
        K = ptb.get(int(r.st), np.nan)
        sig = float(sp.sigma(np.array([b - 2]), look=300)[0]) * 1.4
        tau = max(r.en - (b - 2.285), 1.0)
        fcl = norm.cdf(np.log(clv / K) / (sig * np.sqrt(tau))) if np.isfinite(clv) and np.isfinite(K) else np.nan
        fbn = float(fair_up(sp, np.array([r.st]), np.array([r.en]), np.array([b - 2]))[0][0])
        rows.append(dict(wallet=r.wallet, cid=r.cid, st=int(r.st), ts=b, is_up=int(r.is_up), mid=mid, prev_mid=prev_mid, net=net,
                         prev_up=prev_up, fcl=fcl, fbn=fbn, price=float(r.price), shares=float(r.size),
                         tx=r.tx, half="early" if r.st < CUT else "late", last_before=float(mu_[i2]) if i2 >= 0 else np.nan))
    S = pd.DataFrame(rows)
    yv = S.is_up.to_numpy() == 1
    dec = (S.mid - 0.5).abs().to_numpy() > 0.4
    cheap = S.mid.to_numpy() < 0.5
    post = np.where(np.isfinite(S.fcl), S.fcl > S.mid, S.fbn > S.mid)
    S["r8c"] = np.where(dec, cheap, post)
    S["cheaper"] = cheap
    S["favourite"] = ~cheap
    S["bn_posture"] = (S.fbn > S.mid).to_numpy()
    S["rose"] = np.where(np.isfinite(S.prev_mid), S.mid > S.prev_mid, True)
    S["held"] = np.where(S.net != 0, S.net > 0, True)
    S["under"] = np.where(S.net != 0, S.net < 0, True)
    S["prev_fill"] = np.where(S.prev_up >= 0, S.prev_up == 1, True)
    S.to_parquet(EXC / "side_fills.parquet", index=False)
    rules = ["r8c", "cheaper", "favourite", "bn_posture", "rose", "held", "under", "prev_fill"]

    def sidem(m):
        d = {k: float(np.mean((S[k].to_numpy() == yv)[m])) for k in rules}
        d["n"] = int(m.sum())
        mo = ["cheaper", "favourite", "bn_posture", "rose"]
        oo = ["held", "under", "prev_fill"]
        bm = max(mo, key=lambda k: d[k]); bo = max(oo, key=lambda k: d[k])
        d["best_market_only"] = [bm, d[bm]]; d["best_own_inventory_only"] = [bo, d[bo]]
        a = S["r8c"].to_numpy()[m] == yv[m]; c = S[bm].to_numpy()[m] == yv[m]
        n10, n01 = int(np.sum(a & ~c)), int(np.sum(~a & c))
        d["mcnemar_vs_market"] = {"rule_only": n10, "base_only": n01,
                                  "p_one_sided": float(stats.binomtest(n10, n10 + n01, 0.5, alternative="greater").pvalue) if n10 + n01 else None}
        d["share_decided"] = float(dec[m].mean()); d["chainlink_coverage"] = float(np.isfinite(S.fcl.to_numpy()[m]).mean())
        return d
    allS = np.ones(len(S), bool)
    res["side"] = {"pooled": sidem(allS), "early": sidem((S.half == "early").to_numpy()), "late": sidem((S.half == "late").to_numpy()),
                   "per_wallet": {nm: sidem((S.wallet == nm).to_numpy()) for ad, nm in CLUSTER.items()},
                   "per_wallet_half": {f"{nm}_{h}": sidem(((S.wallet == nm) & (S.half == h)).to_numpy()) for ad, nm in CLUSTER.items() for h in ("early", "late")},
                   "chainlink_values_live": n_live}
    # one-sidedness of windows (does side apply?)
    sh = mk.assign(up_sh=np.where(mk.is_up == 1, mk["size"], 0.0)).groupby("cid").agg(up=("up_sh", "sum"), tot=("size", "sum"), n=("size", "size"))
    frac = sh.up / sh.tot
    res["side"]["windows_with_fills"] = int(len(sh))
    res["side"]["one_sided_windows_share_95"] = float(((frac >= 0.95) | (frac <= 0.05)).mean())
    res["side"]["one_sided_windows_share_100"] = float(((frac == 1) | (frac == 0)).mean())
    print("side done", round(time.time() - t0, 1), flush=True)

    # ---- price: block clock (last clean print strictly before the fill second - 0.01) and the live match clock
    S["pred_block"] = np.round(S.last_before.where(S.is_up == 1, 1 - S.last_before) - 0.01, 2)
    S["anchor_last_block"] = np.round(S.last_before.where(S.is_up == 1, 1 - S.last_before), 2)
    within = lambda a: np.abs(S.price.to_numpy() - a) <= 0.0105
    # match clock from the shared recorder ('x' first server ms per tx, clean trades; 'q' touch)
    up_set = set(w.up_token); dn = dict(zip(w.down_token, w.cid)); upc = dict(zip(w.up_token, w.cid))
    ctx = set(A["tx"].str.lower())
    X, Q = [], {}
    for r in iter_feed("clob_crypto", LOT[0][0] - 300, LOT[-1][1] + 300):
        k = r.get("k")
        if k == "x":
            a = str(r.get("a"))
            c = upc.get(a) or dn.get(a)
            if c is None or not r.get("s"):
                continue
            X.append((int(r["s"]), c, a in up_set, float(r.get("p") or 0), str(r.get("h") or "").lower()))
        elif k in ("q", "f") and str(r.get("a")) in up_set and r.get("s"):
            bb = max((float(x[0]) for x in (r.get("b") or [])), default=np.nan)
            ba = min((float(x[0]) for x in (r.get("o") or [])), default=np.nan)
            Q.setdefault(str(r["a"]), []).append((int(r["s"]), bb, ba))
    X = pd.DataFrame(X, columns=["s", "cid", "isup", "p", "h"]).sort_values("s", kind="stable")
    X["p_up"] = np.where(X.isup, X.p, 1 - X.p)
    match = X.groupby("h").s.min()
    Xc = X[~X.h.isin(ctx)]
    byc = {c: (g.s.to_numpy(), g.p_up.to_numpy()) for c, g in Xc.groupby("cid")}
    Qa = {a: np.array(v) for a, v in Q.items()}
    for a in Qa:
        Qa[a] = Qa[a][np.argsort(Qa[a][:, 0], kind="stable")]
    pm, lastm, touch = [], [], []
    for r in S.itertuples(index=False):
        T_ = match.get(str(r.tx).lower())
        if T_ is None or r.cid not in byc:
            pm.append(np.nan); lastm.append(np.nan); touch.append(np.nan); continue
        ss, pp = byc[r.cid]
        i = np.searchsorted(ss, T_, side="left") - 1
        lp = (pp[i] if r.is_up == 1 else 1 - pp[i]) if i >= 0 else np.nan
        lastm.append(round(lp, 2) if np.isfinite(lp) else np.nan)
        pm.append(round(lp - 0.01, 2) if np.isfinite(lp) else np.nan)
        qa = Qa.get(upof[r.cid])
        tb = np.nan
        if qa is not None:
            j = np.searchsorted(qa[:, 0], T_, side="left") - 1
            if j >= 0 and T_ - qa[j, 0] < 10000:
                tb = qa[j, 1] if r.is_up == 1 else 1 - qa[j, 2]  # best bid of the bought token before the match
        touch.append(tb)
    S["pred_match"], S["anchor_last_match"], S["touch_bid"] = pm, lastm, touch
    S.to_parquet(EXC / "price_fills.parquet", index=False)
    mm = S.pred_match.notna().to_numpy()

    def pricem(m):
        d = {"n": int(m.sum()), "match_clock_share": float(mm[m].mean())}
        comb = np.where(mm, S.pred_match, S.pred_block)
        d["rule_block_clock"] = float(within(S.pred_block.to_numpy())[m].mean())
        d["rule_match_where_recorded_else_block"] = float(within(comb)[m].mean())
        d["anchor_last_print_block"] = float(within(S.anchor_last_block.to_numpy())[m].mean())
        k = m & mm
        if k.any():
            d["on_match_clock"] = {"n": int(k.sum()), "rule": float(within(S.pred_match.to_numpy())[k].mean()),
                                   "last_print": float(within(S.anchor_last_match.to_numpy())[k].mean()),
                                   "touch": float(within(S.touch_bid.to_numpy())[k & S.touch_bid.notna().to_numpy()].mean()) if (k & S.touch_bid.notna().to_numpy()).any() else None,
                                   "touch_minus_tick": float(within(S.touch_bid.to_numpy() - 0.01)[k & S.touch_bid.notna().to_numpy()].mean()) if (k & S.touch_bid.notna().to_numpy()).any() else None,
                                   "rule_block_same_fills": float(within(S.pred_block.to_numpy())[k].mean())}
        return d
    res["price"] = {"pooled": pricem(allS), "early": pricem((S.half == "early").to_numpy()), "late": pricem((S.half == "late").to_numpy()),
                    "per_wallet": {nm: pricem((S.wallet == nm).to_numpy()) for ad, nm in CLUSTER.items()},
                    "x_records": int(len(X)), "q_tokens": len(Qa)}
    res["secs"] = round(time.time() - t0, 1)
    (RES / "exam_r2_metrics.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:8000])


if __name__ == "__main__":
    main()
