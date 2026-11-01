"""iteration 16, X183 (assumptions panel P3): strict per-market replay of the idle module's decoded opening on the alt
5m/15m families (ETH, SOL, XRP, BNB, DOGE), STUDY 10-23..26 per day and VALIDATE 10-27..30 (aggregate), the outcome
criterion per market.
Rule (frozen from T1d, no fitting): at T = st + 5 s, posture side s* = Up iff Phi(ln(S/K) / (0.7 sigma300 sqrt(tau))) >
p_up, S = Binance close(T - 3), K = the Binance TWAP-60 stand-in mean close[st - 60, st - 1], p_up = the last clean
taker print stamped <= T - 2 mapped to Up (0.5 if none); bid q = p_s* - 0.01 for the family's off-session size (ETH 5m
50, SOL 5m 50, XRP 5m 10, BNB 5m 10, DOGE 5m 10, ETH/SOL 15m 30, other 15m 10); strict fills from T + 2 s to end - 30 s
on the clean taker tape (a taker SELL of s* below q, or a taker BUY of the complement above 1 - q), fill size = print
size; held to resolution (Gamma outcome). Compared per market with the cluster's own BUY-fill PnL held to resolution;
also with the cluster's own opening side (the outcome of its first fill) as an oracle side.
    python idle_replay.py"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, pearsonr, spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code15"))
from nb_side import Spot, C  # noqa: E402

SIZE = {"eth-5m": 50, "sol-5m": 50, "xrp-5m": 10, "bnb-5m": 10, "doge-5m": 10, "eth-15m": 30, "sol-15m": 30}
a = pd.read_parquet(C / "it15_nb_side.parquet")
allc = set(a.transactionHash.str.lower())
a = a[a.fam.str.match(r"^(eth|sol|xrp|bnb|doge)-(5m|15m)$") & (a.fold.str.startswith("STUDY") | (a.fold == "VALIDATE"))].copy()
mk = a.groupby("conditionId").agg(slug=("slug", "first"), st=("st", "first"), L=("L", "first"), fam=("fam", "first"),
                                  sym=("sym", "first"), fold=("fold", "first")).reset_index()
print("markets", len(mk), flush=True)
from polyrea.workflows.updown_study import fetch_windows  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
raw = fetch_windows(sorted(set(mk.slug)))
info = {}
for m in raw.values():
    try:
        toks = json.loads(m["clobTokenIds"]) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds")
        outs = json.loads(m["outcomes"]) if isinstance(m.get("outcomes"), str) else m.get("outcomes")
        op = json.loads(m["outcomePrices"]) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices")
        if not m.get("closed"):
            continue
        win = outs[int(np.argmax([float(x) for x in op]))]
        info[m["slug"]] = (str(toks[outs.index("Up")]), str(toks[outs.index("Down")]), 1.0 if win == "Up" else 0.0)
    except Exception:  # noqa: BLE001
        pass
pm = PolymarketData()


def get(row):
    cid, st, L = row
    try:
        rows, _, _ = pm.market_trades(cid, start=int(st) - 3600, end=int(st + L) + 60, taker_only=True)
    except Exception:  # noqa: BLE001
        return cid, None
    return cid, [(int(r["timestamp"]), str(r.get("asset")), float(r["price"]), float(r.get("size") or 0), str(r.get("side")),
                  str(r.get("transactionHash", "")).lower()) for r in rows]


t0 = time.time()
tapes = {}
with ThreadPoolExecutor(3) as ex:
    for i, (cid, rows) in enumerate(ex.map(get, mk[["conditionId", "st", "L"]].itertuples(index=False, name=None))):
        tapes[cid] = rows
        if i % 300 == 0:
            print("tapes", i, len(mk), round(time.time() - t0), "s", flush=True)
sp = Spot()
res = []
for r in mk.itertuples(index=False):
    if r.slug not in info or not tapes.get(r.conditionId):
        continue
    up, dn, pay_up = info[r.slug]
    tp = [x for x in tapes[r.conditionId] if x[5] not in allc]
    tp.sort(key=lambda x: x[0])
    st, L = int(r.st), int(r.L)
    T = st + 5
    S = sp.close_at(r.sym, np.array([T - 3]))[0]
    Kv = sp.close_at(r.sym, np.arange(st - 60, st))
    K = np.nanmean(Kv) if np.isfinite(Kv).sum() >= 30 else np.nan
    grid = np.arange(T - 3 - 300, T - 2)
    v = np.log(sp.close_at(r.sym, grid))
    sig = np.nanstd(np.diff(v)) if np.isfinite(v).sum() > 100 else np.nan
    if not (np.isfinite(S) and np.isfinite(K) and np.isfinite(sig) and sig > 0):
        continue
    pre = [x for x in tp if x[0] <= T - 2]
    p_up = (pre[-1][2] if pre[-1][1] == up else 1 - pre[-1][2]) if pre else 0.5
    F_up = norm.cdf(np.log(S / K) / (0.7 * sig * np.sqrt(max(st + L - T, 1))))
    g = a[a.conditionId == r.conditionId].sort_values("timestamp", kind="stable")
    clus_pnl = float((g["size"] * (np.where(g.outcome == "Up", pay_up, 1 - pay_up) - g.price)).sum())
    clus_open = (g.outcome.iloc[0] == "Up")
    out = {"cid": r.conditionId, "fam": r.fam, "fold": "STUDY" if r.fold.startswith("STUDY") else "VALIDATE", "fold_day": r.fold,
           "st": st, "clus_pnl": clus_pnl, "clus_cost": float((g["size"] * g.price).sum()), "first_up": bool(clus_open),
           "first_t": int(g.timestamp.iloc[0] - st)}
    for lab, side_up in (("rule", F_up > p_up), ("oracle_first", clus_open)):
        tok = up if side_up else dn
        p_s = p_up if side_up else 1 - p_up
        q = round(max(0.01, min(0.99, p_s - 0.01)), 2)
        rem = SIZE.get(r.fam, 10)
        filled = 0.0
        for ts, asset, pr, sz, sd, _h in tp:
            if ts < T + 2 or ts > st + L - 30 or rem <= 0:
                continue
            x = pr if asset == tok else 1 - pr
            taker_sells_s = (asset == tok and sd == "SELL") or (asset != tok and sd == "BUY")
            if taker_sells_s and x < q - 1e-9:
                f = min(rem, sz)
                filled += f
                rem -= f
        pay = pay_up if side_up else 1 - pay_up
        out[f"{lab}_pnl"] = filled * (pay - q)
        out[f"{lab}_filled"] = filled
        out[f"{lab}_up"] = bool(side_up)
    res.append(out)
R = pd.DataFrame(res)
R.to_parquet(C / "it16_idle_replay.parquet", index=False)
summ = {}
for f_, g in [("STUDY", R[R.fold == "STUDY"]), ("VALIDATE", R[R.fold == "VALIDATE"])] + [(d_, R[R.fold_day == d_]) for d_ in sorted(R.fold_day.unique()) if d_.startswith("STUDY")]:
    row = {"markets": int(len(g)), "rule_side_eq_first": round(float((g.rule_up == g.first_up).mean()), 3),
           "rule_filled_share": round(float((g.rule_filled > 0).mean()), 3), "clus_pnl": round(float(g.clus_pnl.sum()), 1),
           "clus_ret": round(float(g.clus_pnl.sum() / max(1e-9, g.clus_cost.sum())), 4), "rule_pnl": round(float(g.rule_pnl.sum()), 1)}
    for lab in ("rule", "oracle_first"):
        if len(g) > 5 and g[f"{lab}_pnl"].std() > 0:
            row[f"{lab}_pearson"] = round(float(pearsonr(g[f"{lab}_pnl"], g.clus_pnl)[0]), 3)
            row[f"{lab}_spearman"] = round(float(spearmanr(g[f"{lab}_pnl"], g.clus_pnl)[0]), 3)
    # sign agreement of per-market PnL where both nonzero
    m = (g.rule_pnl != 0) & (g.clus_pnl != 0)
    row["sign_agree_rule"] = round(float((np.sign(g.rule_pnl[m]) == np.sign(g.clus_pnl[m])).mean()), 3) if m.any() else None
    summ[f_] = row
print(json.dumps(summ, indent=1))
(HERE.parent / "results/iter16_idle_replay.json").write_text(json.dumps(summ, indent=1))
