"""Iteration 19, X191 (pre-registration 16c, written 11-01 ~13:20 UTC before this run): uncertainty for pre-registration 16b's statistic
E = sum over events of the excess (same - opposite side) first legs in [0, 230) ms after a Binance spot microprice jump, over the
excess in the reaction band [230, 320) ms; isolated events only (no |z| > 2 move in the 2 s before; see knee19b).
Tests, one-sided as stated, fixed here:
 T1  E(open hours) > E(closed hours), operator: hourly values (hours with >= 60 isolated events), Mann-Whitney; and a 30-min block
     bootstrap of the difference of the pooled ratios (2,000 draws).
 T2  break hour (Mon-Thu 21-22 UTC) < neighbours (20-21 and 22-23 UTC) of the same day, operator: per-day sign count over 4 days and a
     30-min block bootstrap of the pooled difference.
 T3  operator excess over the crowd: the open-minus-closed difference in E for the operator minus the same for the crowd (bootstrap).
 Also reported: per wallet E by session (operator), and the hazard-free 'lead share' = early excess / (early + peak excess).
Usage: python knee19c.py FRAME_DIR HF_DIR"""
import os, sys, json, gc
import numpy as np, pandas as pd, pyarrow.parquet as pq
from scipy.stats import mannwhitneyu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knee19b import at, cell, events

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"


def main():
    D, A = sys.argv[1], sys.argv[2]
    P = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["wallet", "up", "m0", "rank", "day"])
    P = P[P["rank"] == 0].reset_index(drop=True)
    Cw = pd.read_parquet(f"{D}/dcclock14_crowd.parquet", columns=["mc", "up"])
    groups = {"operator": (P.m0.to_numpy(np.int64), np.where(P.up.to_numpy() == 1, 1, -1), P.wallet.to_numpy()),
              "crowd": (Cw.mc.to_numpy(np.int64), np.where(Cw.up.to_numpy() == 1, 1, -1), np.full(len(Cw), "crowd", dtype=object))}
    rows = []
    for day in sorted(P.day.unique()):
        d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
        for h0 in range(0, 24, 6):
            lo, hi = (d0 + h0 * 3600) * 1000, (d0 + (h0 + 6) * 3600) * 1000
            t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity"],
                              filters=[("receivedTimestampMs", ">=", lo - 70000), ("receivedTimestampMs", "<", hi + 2000), ("type", "=", "book")])
            Tb = t.column("receivedTimestampMs").to_numpy() - 131
            bp, bq, ap, aq = (t.column(k).to_numpy(zero_copy_only=False).astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
            mic = (bp * aq + ap * bq) / (bq + aq); o = np.argsort(Tb, kind="stable"); Tb, mic = Tb[o], mic[o]
            del t, bp, bq, ap, aq; gc.collect()
            if len(Tb) < 1000:
                continue
            te, se, iso = events(Tb, mic, lo - 60000, hi)
            k_ = (te >= lo) & (iso == 1); te, se = te[k_], se[k_]
            ce = cell(te)
            for g, (M, Y, Wl) in groups.items():
                sel = np.where((M >= lo - 1000) & (M < hi + 1000))[0]
                o2 = np.argsort(M[sel], kind="stable"); ms_, ys_, ws_ = M[sel][o2], Y[sel][o2], Wl[sel][o2]
                a = np.searchsorted(ms_, te - 500, "left"); b = np.searchsorted(ms_, te + 1000, "left")
                for k in range(len(te)):
                    lag = ms_[a[k]:b[k]] - te[k]; sg = np.where(ys_[a[k]:b[k]] == se[k], 1.0, -1.0); ww = ws_[a[k]:b[k]]
                    e1 = (lag >= 0) & (lag < 230); e2 = (lag >= 230) & (lag < 320)
                    rec = {"g": g, "t": int(te[k]), "cell": ce[k], "early": float(sg[e1].sum()), "peak": float(sg[e2].sum())}
                    if g == "operator":
                        for w in ("DS", "GF", "XM"):
                            rec[f"early_{w}"] = float(sg[e1 & (ww == w)].sum()); rec[f"peak_{w}"] = float(sg[e2 & (ww == w)].sum())
                    rows.append(rec)
            del Tb, mic; gc.collect()
        print(day, len(rows), flush=True)
    E = pd.DataFrame(rows)
    E["hour"] = E.t // 3600000; E["blk"] = E.t // 1800000
    E["open"] = ~E.cell.isin(["closed_weekend", "break_21"])
    rng = np.random.default_rng(19)
    res = {"prereg": "16c", "isolated_events": int((E.g == "operator").sum())}

    def ratio(d):
        p = d.peak.sum()
        return float(d.early.sum() / p) if p > 0 else np.nan
    for g in ("operator", "crowd"):
        d = E[E.g == g]
        hr = d.groupby("hour").agg(n=("early", "size"), early=("early", "sum"), peak=("peak", "sum"), open=("open", "first"), cell=("cell", "first"))
        hr = hr[(hr.n >= 60) & (hr.peak > 0)]; hr["E"] = hr.early / hr.peak
        mw = mannwhitneyu(hr.E[hr.open], hr.E[~hr.open], alternative="greater")
        res[g] = {"E_open": round(ratio(d[d.open]), 3), "E_closed": round(ratio(d[~d.open]), 3),
                  "hours_open_closed": [int(hr.open.sum()), int((~hr.open).sum())],
                  "hourly_median_open_closed": [round(float(hr.E[hr.open].median()), 3), round(float(hr.E[~hr.open].median()), 3)],
                  "T1_mannwhitney_p": float(mw.pvalue)}
        print(g, res[g], flush=True)
    # bootstrap over 30-min blocks (T1, T3, T2)
    blks = np.unique(E.blk); bi = {b: np.where(E.blk.to_numpy() == b)[0] for b in blks}
    g_op = (E.g == "operator").to_numpy(); op_ = E.open.to_numpy(); ce = E.cell.to_numpy()
    ear, pk = E.early.to_numpy(), E.peak.to_numpy()

    def stats(ix):
        out = {}
        for gg, gm in (("operator", g_op), ("crowd", ~g_op)):
            m = np.zeros(len(E), bool); m[ix] = True
            for nm, cm in (("open", op_), ("closed", ~op_), ("break", ce == "break_21"), ("nbr", np.isin(ce, ["pre_break_20", "post_break_22"]))):
                s = ix[(gm & cm)[ix]]
                out[(gg, nm)] = ear[s].sum() / pk[s].sum() if pk[s].sum() > 0 else np.nan
        return out
    base = stats(np.arange(len(E)))
    bs = []
    for _ in range(2000):
        ix = np.concatenate([bi[b] for b in rng.choice(blks, len(blks))])
        bs.append(stats(ix))
    def ci(f):
        v = np.array([f(s) for s in bs]); v = v[np.isfinite(v)]
        return [round(float(f(base)), 3), round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3), round(float((v <= 0).mean()), 4)]
    res["T1_operator_open_minus_closed"] = ci(lambda s: s[("operator", "open")] - s[("operator", "closed")])
    res["T1_crowd_open_minus_closed"] = ci(lambda s: s[("crowd", "open")] - s[("crowd", "closed")])
    res["T3_operator_minus_crowd_session_effect"] = ci(lambda s: (s[("operator", "open")] - s[("operator", "closed")]) - (s[("crowd", "open")] - s[("crowd", "closed")]))
    res["T2_operator_neighbours_minus_break"] = ci(lambda s: s[("operator", "nbr")] - s[("operator", "break")])
    res["T2_crowd_neighbours_minus_break"] = ci(lambda s: s[("crowd", "nbr")] - s[("crowd", "break")])
    res["bootstrap_format"] = "[point, 2.5%, 97.5%, one-sided p = share of draws <= 0]"
    # T2 per day
    d = E[(E.g == "operator") & E.cell.isin(["break_21", "pre_break_20", "post_break_22"])].copy()
    d["day"] = pd.to_datetime(d.t, unit="ms").dt.strftime("%m-%d")
    pd_ = {}
    for dy, g2 in d.groupby("day"):
        b2 = g2[g2.cell == "break_21"]; n2 = g2[g2.cell != "break_21"]
        pd_[dy] = {"break": round(ratio(b2), 3) if len(b2) else None, "neighbours": round(ratio(n2), 3) if len(n2) else None, "n_break": int(len(b2))}
    res["T2_per_day_operator"] = pd_
    # per wallet
    dw = E[E.g == "operator"]
    res["per_wallet"] = {w: {"E_open": round(float(dw[f"early_{w}"][dw.open].sum() / dw[f"peak_{w}"][dw.open].sum()), 3),
                             "E_closed": round(float(dw[f"early_{w}"][~dw.open].sum() / dw[f"peak_{w}"][~dw.open].sum()), 3)} for w in ("DS", "GF", "XM")}
    for k, v in res.items():
        print(k, v, flush=True)
    json.dump(res, open(f"{R}/knee19c.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
