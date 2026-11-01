"""Frozen rule of rn1-inplay-maker (iteration 1). All parameters are constants.

evaluate(start_ts, end_ts, intervals=None) -> dict loads what it needs for the period (RN1's activity, Gamma
listing fields, public tapes of a seeded sample of the events RN1 traded), applies the rule point in time and
returns the metrics, per wallet and pooled (one wallet). Nothing is written to disk: tapes and listings stay in
memory (the shared HTTP cache of the polyrea adapters still caches the responses).

The rule (components; tags in FINAL_RULE.md):
- presence / selection + timing: LightGBM FULL model (models/presence_FULL.txt, fitted on BUILD cells) over the
  pre-registered universe: every market of a sampled event, 60-s bins in [gameStart - 2 h, gameStart + 5 h] that
  carry >= 1 public taker print; label "RN1 has >= 1 maker fill in the bin". Features are point in time (rows
  with ts < bin start), never RN1's rows or rows of transactions it is in. The activity-only baselines are
  models/presence_ACT.txt and models/presence_ACT2.txt (+ tape spread proxies), same class, same BUILD data.
- side: two-sided BUY-only maker; the side it ends up with in a (market, bin) is predicted as the outcome priced
  below 0.5 at the last print ("underdog"), which is the market-only baseline itself.
- price: its bid on outcome k is the inside: join a 1-tick spread, improve a wider one by one tick (live books).
  On the tape (no book) the rule reduces to the last other-trader print on outcome k, minus one tick when that
  print lifted k's ask.
- size: ~1,500 shares per order (modes ~700 / 1,500 / 3,000), independent of price.
- exit: none; holds both outcomes to resolution, redeems (no SELL, MERGE or SPLIT rows in development data).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

ALLOW_SEALED = False
KEY = "rn1-inplay-maker"
WALLET = "0x2005d16a84ceefa912d4e380cd32e7ff827875ea"
SAMPLE_SEEDS = (1, 3)   # two disjoint seeded samples of 60 events (as fetch_tapes.py / fetch_tapes_more.py drew them)
SAMPLE_N = 60
TICK = 0.01
MODEL_VERSION = "v2"   # models/<version>/: v2 = fitted on the 60 pre-registered BUILD events
RULE_MODEL = "presence_FULL.txt"     # chosen on VALIDATE among ACT / LIST / FULL / FULL2 (iteration 1)
BASE_MODEL = "presence_ACT.txt"      # activity-only baseline (same class, BUILD data)
BASE2_MODEL = "presence_ACT2.txt"    # activity-only + tape spread proxies (the stronger of our two baselines)
N_BOOT = 2000


def _intervals(start_ts, end_ts, intervals):
    import sealed
    iv = [(start_ts, end_ts)] if intervals is None else [(max(a, start_ts), min(b, end_ts)) for a, b in intervals]
    iv = [(a, b) for a, b in iv if b > a]
    if ALLOW_SEALED:
        return iv
    dev = sealed.intervals(KEY, start_ts, end_ts, sealed=False)
    out = []
    for a, b in iv:
        for c, d in dev:
            lo, hi = max(a, c), min(b, d)
            if hi > lo:
                out.append((lo, hi))
    return out


def _in(ts, iv):
    return ts is not None and any(a <= ts < b for a, b in iv)


def _tape(pm, cid, tokens, a, b):
    taker, _, _ = pm.market_trades(cid, start=a, end=b, taker_only=True, max_rows=80_000)
    full, _, _ = pm.market_trades(cid, start=a, end=b, taker_only=False, max_rows=160_000)
    keys, out = {}, []
    for r in taker:
        k = (r.get("transactionHash"), (r.get("proxyWallet") or "").lower(), str(r.get("asset")), r.get("side"))
        keys[k] = keys.get(k, 0) + 1
        if str(r.get("asset")) in tokens:
            out.append((cid, int(r["timestamp"]), tokens.index(str(r["asset"])), r.get("side"), float(r["price"]), float(r["size"]),
                        (r.get("proxyWallet") or "").lower(), r.get("transactionHash"), "taker"))
    for r in full:
        k = (r.get("transactionHash"), (r.get("proxyWallet") or "").lower(), str(r.get("asset")), r.get("side"))
        if keys.get(k, 0) > 0:
            keys[k] -= 1
            continue
        if str(r.get("asset")) in tokens:
            out.append((cid, int(r["timestamp"]), tokens.index(str(r["asset"])), r.get("side"), float(r["price"]), float(r["size"]),
                        (r.get("proxyWallet") or "").lower(), r.get("transactionHash"), "maker"))
    return out


def _auc(y, s):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s)) if len(set(y)) == 2 else None


def _boot(y, sb, sn, groups, n=N_BOOT, seed=0):
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(seed)
    ug, inv = np.unique(groups, return_inverse=True)
    idx = [np.where(inv == g)[0] for g in range(len(ug))]
    d = []
    for _ in range(n):
        ii = np.concatenate([idx[g] for g in rng.integers(0, len(ug), len(ug))])
        if y[ii].min() == y[ii].max():
            continue
        d.append(roc_auc_score(y[ii], sn[ii]) - roc_auc_score(y[ii], sb[ii]))
    d = np.array(d)
    return [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))], float((d <= 0).mean())


def _side_price(tp_all):
    """Side and price metrics on RN1's maker fills of the sampled events (tape only, point in time)."""
    side_rows, price_rows = [], []
    for cid, g in tp_all.groupby("cid"):
        g = g.sort_values("ts")
        rn_tx = set(g.loc[g["wallet"] == WALLET, "tx"])
        lab = g[(g["wallet"] == WALLET) & (g["role"] == "maker")]
        if lab.empty:
            continue
        oth = g[~g["tx"].isin(rn_tx) & (g["role"] == "taker")]
        ts, o, pr, sd = oth["ts"].to_numpy(), oth["outcome"].to_numpy(), oth["price"].to_numpy(), oth["side"].to_numpy()
        for r in lab.itertuples():
            i = np.searchsorted(ts, r.ts, side="left") - 1
            if i < 0:
                continue
            pk = pr[i] if o[i] == r.outcome else 1 - pr[i]
            at_ask = (o[i] == r.outcome and sd[i] == "BUY") or (o[i] != r.outcome and sd[i] == "SELL")
            rule = pk - TICK if at_ask else pk
            p0 = pr[i] if o[i] == 0 else 1 - pr[i]
            price_rows.append((r.price, rule, pk))
            side_rows.append((cid, r.ts // 60, r.outcome, p0))
    out = {}
    if price_rows:
        d = np.array(price_rows, float)
        out["price_within_tick"] = float(np.mean(np.abs(d[:, 0] - d[:, 1]) <= TICK + 1e-9))
        out["price_exact"] = float(np.mean(np.abs(d[:, 0] - d[:, 1]) < 1e-6))
        out["price_anchor_last_print_within_tick"] = float(np.mean(np.abs(d[:, 0] - d[:, 2]) <= TICK + 1e-9))
        out["price_anchor_last_print_exact"] = float(np.mean(np.abs(d[:, 0] - d[:, 2]) < 1e-6))
        out["n_price"] = int(len(d))
    if side_rows:
        s = pd.DataFrame(side_rows, columns=["cid", "bin", "k", "p0"]).groupby(["cid", "bin"]).agg(k=("k", "mean"), p0=("p0", "first"))
        s = s[(s["k"] == 0) | (s["k"] == 1)]
        under = np.where(s["p0"] < 0.5, 0, 1)
        out["side_accuracy"] = float(np.mean(under == s["k"]))      # rule = underdog
        out["side_baseline_favourite"] = float(np.mean((1 - under) == s["k"]))
        out["side_baseline"] = max(out["side_accuracy"], out["side_baseline_favourite"])
        out["n_side"] = int(len(s))
    return out


def evaluate(start_ts, end_ts, intervals=None):
    import lightgbm as lgb
    from polyrea.adapters.polymarket import PolymarketData
    from common import parse_ts
    from presence import ACT, FULL, LIST, SPREAD, event_cells
    iv = _intervals(int(start_ts), int(end_ts), intervals)
    if not iv:
        return {"error": "no admissible interval"}
    pm = PolymarketData()
    acts = []
    for a, b in iv:
        for d in range(a, b, 86400):
            rows, _, _ = pm.activity(WALLET, start=d, end=min(d + 86400, b) - 1)
            acts += [r for r in rows if r.get("type") == "TRADE"]
    act = pd.DataFrame(acts)
    if act.empty:
        return {"error": "no activity"}
    import random
    evs = sorted(set(act["eventSlug"].dropna()) - {""})
    order, rest = [], list(evs)
    for sd in SAMPLE_SEEDS:
        pick = random.Random(sd).sample(rest, min(SAMPLE_N, len(rest)))
        order += pick
        rest = [x for x in rest if x not in set(pick)]
    hi_all = max(hi for _, hi in iv)
    cells, tapes, used = [], [], []
    for slug in order:
        d, _ = pm.http.get_json("https://gamma-api.polymarket.com/events", {"slug": slug}, adapter="gamma.events", max_age=None)
        e = d[0] if d else None
        if not e:
            continue
        ev_start = parse_ts(e.get("startTime"))
        mk = e.get("markets") or []
        gsts = [parse_ts(m.get("gameStartTime")) for m in mk]
        unit = min([g for g in gsts if g] or [ev_start or 0])
        if not _in(unit, iv):
            continue
        rows = []
        for m in mk:
            try:
                tokens = json.loads(m.get("clobTokenIds") or "[]")
            except ValueError:
                continue
            gst = parse_ts(m.get("gameStartTime")) or ev_start or parse_ts(m.get("endDate"))
            if gst is None or len(tokens) != 2:
                continue
            a, b = gst - 7200, gst + 5 * 3600
            b = min(b, hi_all - 1)
            if a >= b:
                continue
            rows += _tape(pm, m["conditionId"], tokens, a, b)
        tp = pd.DataFrame(rows, columns=["cid", "ts", "outcome", "side", "price", "size", "wallet", "tx", "role"])
        if tp.empty:
            continue
        # listing fields only for decisions (event_cells reads slug, markets, gameStartTime, sportsMarketType, ...)
        cells += event_cells(e, tp)
        tapes.append(tp)
        used.append(slug)
    if not cells:
        return {"error": "no cells"}
    c = pd.concat(cells, ignore_index=True)
    mdir = Path(__file__).resolve().parent / "models" / MODEL_VERSION
    rule = lgb.Booster(model_file=str(mdir / RULE_MODEL))
    base = lgb.Booster(model_file=str(mdir / BASE_MODEL))
    base2 = lgb.Booster(model_file=str(mdir / BASE2_MODEL))
    s_rule = rule.predict(c[ACT + LIST + FULL].astype("float32"))
    s_b1 = base.predict(c[ACT].astype("float32"))
    s_b2 = base2.predict(c[ACT + SPREAD].astype("float32"))
    y = c["y"].to_numpy()
    a1, a2 = _auc(y, s_b1), _auc(y, s_b2)
    s_base = s_b2 if (a2 or 0) >= (a1 or 0) else s_b1
    ci, p_le0 = _boot(y, s_base, s_rule, c["event"].to_numpy())
    tp_all = pd.concat(tapes, ignore_index=True)
    rn = tp_all[(tp_all["wallet"] == WALLET) & (tp_all["role"] == "maker")]
    in_cells = set(zip(c["cid"], c["t"]))
    gst = c.groupby("cid")["gst"].first()
    rn = rn[rn["cid"].isin(gst.index)]
    bins = gst.reindex(rn["cid"]).to_numpy() - 7200
    rn_bin = bins + ((rn["ts"].to_numpy() - bins) // 60) * 60
    cov = float(np.mean([(k, t) in in_cells for k, t in zip(rn["cid"], rn_bin)])) if len(rn) else None
    m = {"presence_auc": _auc(y, s_rule), "presence_baseline": max(a1 or 0, a2 or 0), "presence_baseline_act": a1,
         "presence_baseline_act2": a2, "presence_gain": None,
         "presence_gain_ci95": ci, "presence_p_gain_le_0": p_le0, "n_cells": int(len(c)), "pos_rate": float(y.mean()),
         "n_events": int(len(used)), "selection_auc": None, "selection_recall": None, "selection_lift": None,
         "selection_baseline": None, "pnl_corr_pearson": None, "pnl_corr_spearman": None,
         "coverage_fills": cov, "coverage_abs_pnl": None}
    if m["presence_auc"] is not None and m["presence_baseline"] is not None:
        m["presence_gain"] = m["presence_auc"] - m["presence_baseline"]
    m.update(_side_price(tp_all))
    return {"wallets": {WALLET: m}, "pooled": m, "intervals": iv}


if __name__ == "__main__":
    print(json.dumps(evaluate(int(sys.argv[1]), int(sys.argv[2])), indent=1, default=str))
