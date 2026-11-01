"""X144 tests (information panel iter-10 P1), FROZEN before any development record of tommy_tp_odds2 exists
(written 2026-11-01 ~06:15 UTC; the first development unit with records is expected from ~09:00 UTC).

Usage: .venv/Scripts/python.exe research/reverse_engineering/tommy-cs2-maker/code/iter11/tp_valuation_tests.py START END
       [START END ...]   (UTC epoch seconds of DEVELOPMENT blocks; all blocks are pooled before any verdict)

Inputs: tommy_tp_odds2 (B = live index, U = upcoming index, P = per-match object; development records only through
iter_live), the shared recorder's clob_wallets books ('q' records, server clock 's'), the wallet's public activity and
its taker prints (data-api market trades, taker_only) for the matched Polymarket match market. Units: bo3 matches matched
to a Polymarket CS2 event whose game start (and game start - 30 min) is a development unit.
Forms of Thunderpick's price for the Polymarket token 0 (team mapped by name): prop = (1/c0) / (1/c0 + 1/c1),
lay = 1 - 1/c_other (a bid that copies the book's price for the other side).
Tests:
 (1) cadence: distinct (c1, c2, a1, a2) states per minute and the median gap between changes, B vs P (same match, same
     window). If P's median gap is >= 30% shorter, P is the series used below, else B.
 (2) pre-game: the wallet's MAKER fills on the match market (fills, censored) stamped before the scheduled
     start + 120 s; p_TP from U/B records before each fill; delta = median(fill - form) on the first half of the
     pooled rows (by time), scored on the second half: within one tick of round(form + delta) for both forms, vs the
     last public print and the book's touch (best bid of the token) at the same moment.
 (3) in-play (start + 120 s on): the same, plus a margin linear in |form - 0.5| (least squares on the first half).
 (4) event time: the wallet's maker fill-price CHANGES on the match market (consecutive maker fills of a token at
     different prices); share within 6 s after a p_TP change vs 2,000 within-match circular shifts of the p_TP change
     times (p = share of shifts >= observed).
 (5) shared vendor: cross-correlation of 5-s changes of the wallet's maker fill level (step series on a 1-s grid) and of
     p_TP at lags -10..+10 s; the peak lag and its value.
Pre-registered verdicts (panel): E4 SUPPORTED iff (2) one form within one tick on >= 0.60 of pre-game fills while the
touch / last print <= 0.40, or (3) one form >= 0.60 on in-play match-market fills and >= touch + 0.10, AND (4) >= 3x
the shift null; E4 CLOSED for Thunderpick iff (2) and (3) are both below the touch / last print and (4) is at the null
(p > 0.05); otherwise undecided (more blocks). A refresh slower than 30 s (median gap of the faster source) rules out
the timing role whatever (2)-(3) give. Output: results/tp_valuation_tests_<first START>.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
import sealed  # noqa: E402

KEY = "tommy-cs2-maker"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def sim(a, b):
    return bool(a) and bool(b) and (a in b or b in a or (len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4]))


def hit(p, a):
    p, a = np.asarray(p, float), np.asarray(a, float)
    t = np.where((a >= 0.04) & (a <= 0.96), 0.01, 0.001)
    return np.isfinite(a) & np.isfinite(p) & (np.abs(p - a) <= t + 1e-9)


def gamma_event(slug):
    from polyrea.adapters.http import shared_client
    d, _ = shared_client().get_json("https://gamma-api.polymarket.com/events", {"slug": slug}, adapter="gamma.events", max_age=3600)
    e = (d or [None])[0]
    if not e:
        return None
    for m in e.get("markets") or []:
        if m.get("sportsMarketType") == "moneyline":
            return {"cid": m.get("conditionId"), "outcomes": json.loads(m.get("outcomes") or "[]"),
                    "tokens": json.loads(m.get("clobTokenIds") or "[]"), "gst": m.get("gameStartTime")}
    return None


def ts_of(gst):
    t = pd.Timestamp(gst)
    return (t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC")).timestamp()


def main(blocks):
    for a, b in blocks:
        assert not sealed.is_sealed(a, KEY) and not sealed.is_sealed(b - 1, KEY), "not a development block"
    R = []
    for a, b in blocks:
        R += [r for r in live.iter_live("tommy_tp_odds2", a, b) if r.get("ev")]
    out = {"blocks": blocks, "records": len(R), "matches": {}, "pooled": {}}
    if not R:
        (RES / f"tp_valuation_tests_{int(blocks[0][0])}.json").write_text(json.dumps(out, indent=1))
        print(json.dumps(out)); return
    D = pd.DataFrame(R)
    from polyrea.adapters.polymarket import PolymarketData
    pdx = PolymarketData()
    pre_rows, ip_rows, ev_stats, xc = [], [], [], []
    for ev, g in D.groupby("ev"):
        ge = gamma_event(ev)
        if not ge or len(ge["outcomes"]) != 2 or not ge.get("gst"):
            continue
        gs = ts_of(ge["gst"])
        if sealed.is_sealed(gs, KEY) or sealed.is_sealed(gs - 1800, KEY):
            out["matches"][ev] = {"skipped": "not a development unit"}; continue
        o0 = norm(ge["outcomes"][0])
        g = g.sort_values("t")
        flip = sim(o0, norm(g.n2.iloc[0])) and not sim(o0, norm(g.n1.iloc[0]))
        ok = g.c1.notna() & g.c2.notna() & (g.c1 > 1) & (g.c2 > 1)
        g = g[ok].copy()
        if g.empty:
            continue
        c0, c1 = (g.c2, g.c1) if flip else (g.c1, g.c2)
        g["prop"] = (1 / c0) / (1 / c0 + 1 / c1)
        g["lay"] = 1 - 1 / c1
        r = {}
        # (1) cadence
        for k in ("B", "P", "U"):
            s = g[g.k == k]
            if len(s) > 1:
                dt = np.diff(s.t.to_numpy(float)) / 1000
                span = (s.t.iloc[-1] - s.t.iloc[0]) / 60000
                r[f"cadence_{k}"] = {"states": int(len(s)), "per_min": round(len(s) / span, 3) if span > 0 else None,
                                     "median_gap_s": round(float(np.median(dt)), 1)}
        use = "B"
        if "cadence_P" in r and "cadence_B" in r and r["cadence_P"]["median_gap_s"] <= 0.7 * r["cadence_B"]["median_gap_s"]:
            use = "P"
        r["series_used"] = use
        S = g[(g.k == use) | (g.k == "U")].sort_values("t")
        tS = S.t.to_numpy(float) / 1000
        # wallet maker fills on the match market
        a0, a1 = min(blocks)[0], max(blocks)[1]
        try:
            act, _, _ = pdx.activity(W, int(a0), int(a1))
            act = pd.DataFrame(act)
            tk = pdx.market_trades(ge["cid"], int(a0), int(a1), taker_only=True)
            tk = pd.DataFrame(tk[0] if isinstance(tk, tuple) else tk)
        except Exception as e:  # noqa: BLE001
            r["error"] = repr(e)[:160]; out["matches"][ev] = r; continue
        if act.empty or "conditionId" not in act:
            out["matches"][ev] = r; continue
        f = act[(act.conditionId == ge["cid"]) & (act.get("type", "TRADE") == "TRADE")].copy()
        wtk = set(tk[tk.proxyWallet.str.lower() == W].transactionHash) if len(tk) and "proxyWallet" in tk else set()
        f = f[~f.transactionHash.isin(wtk)]
        if f.empty:
            out["matches"][ev] = r; continue
        f["p0"] = np.where(f.outcomeIndex.astype(int) == 0, f.price.astype(float), 1 - f.price.astype(float))
        f = f.sort_values("timestamp")
        tf = f.timestamp.to_numpy(float)
        j = np.searchsorted(tS, tf, side="right") - 1
        f["prop"] = np.where(j >= 0, S.prop.to_numpy(float)[np.maximum(j, 0)], np.nan)
        f["lay"] = np.where(j >= 0, S.lay.to_numpy(float)[np.maximum(j, 0)], np.nan)
        pub = tk[(tk.proxyWallet.str.lower() != W)].sort_values("timestamp") if len(tk) else tk
        if len(pub):
            tp = pub.timestamp.to_numpy(float)
            pp = np.where(pub.outcomeIndex.astype(int) == 0, pub.price.astype(float), 1 - pub.price.astype(float))
            jj = np.searchsorted(tp, tf - 1e-9, side="right") - 1
            f["last"] = np.where(jj >= 0, np.round(pp[np.maximum(jj, 0)], 2), np.nan)
        else:
            f["last"] = np.nan
        f["phase"] = np.where(tf < gs + 120, "pre", "inplay")
        f["ev"] = ev
        for x in f.itertuples():
            (pre_rows if x.phase == "pre" else ip_rows).append({"ev": ev, "t": x.timestamp, "p": x.p0, "prop": x.prop, "lay": x.lay, "last": x.last})
        # (4) event time: fill-price changes vs p_TP change times
        chg = []
        for oi, h in f.groupby("outcomeIndex"):
            pr = h.price.astype(float).to_numpy()
            tt = h.timestamp.to_numpy(float)
            chg += list(tt[1:][np.abs(np.diff(pr)) > 0.0049])
        cts = tS[1:][np.abs(np.diff(S.prop.to_numpy(float))) > 1e-6]
        if len(chg) >= 5 and len(cts) >= 3:
            chg = np.sort(np.array(chg))

            def share(ct):
                k = np.searchsorted(ct, chg, side="right") - 1
                return float(np.mean((k >= 0) & (chg - ct[np.maximum(k, 0)] <= 6.0)))
            obs = share(cts)
            lo, hi = tS.min(), tS.max()
            rng = np.random.default_rng(1)
            nul = []
            for _ in range(2000):
                sh = rng.uniform(0, hi - lo)
                nul.append(share(np.sort(lo + (cts - lo + sh) % (hi - lo))))
            nul = np.array(nul)
            ev_stats.append((obs, float(nul.mean()), float((nul >= obs).mean()), len(chg)))
            r["event_time"] = {"changes": len(chg), "share_within_6s": round(obs, 3), "null_mean": round(float(nul.mean()), 3),
                               "p": round(float((nul >= obs).mean()), 4)}
        # (5) shared-vendor cross-correlation on a 1-s grid
        if len(f) >= 20 and len(S) >= 10:
            t0, t1 = max(tf.min(), tS.min()), min(tf.max(), tS.max())
            if t1 - t0 > 600:
                grid = np.arange(t0, t1, 1.0)
                i1 = np.searchsorted(tf, grid, side="right") - 1
                i2 = np.searchsorted(tS, grid, side="right") - 1
                Lw = f.p0.to_numpy(float)[np.maximum(i1, 0)]
                Lp = S.prop.to_numpy(float)[np.maximum(i2, 0)]
                dW, dP = Lw[5:] - Lw[:-5], Lp[5:] - Lp[:-5]
                cc = {}
                for L in range(-10, 11):  # positive L: p_TP first
                    x_ = dP[:len(dP) - L] if L > 0 else dP[-L:]
                    y_ = dW[L:] if L > 0 else dW[:len(dW) + L]
                    cc[L] = float(np.corrcoef(x_, y_)[0, 1]) if np.std(x_) > 0 and np.std(y_) > 0 else np.nan
                k = max(cc, key=lambda z: -np.inf if not np.isfinite(cc[z]) else cc[z])
                r["xcorr"] = {"peak_lag_s": int(k), "peak": round(cc[k], 3), "at_0": round(cc[0], 3)}
                xc.append((k, cc[k]))
        out["matches"][ev] = r

    def score(rows, name):
        if len(rows) < 10:
            return {"n": len(rows)}
        X = pd.DataFrame(rows).sort_values("t")
        h = len(X) // 2
        A, Bh = X.iloc[:h], X.iloc[h:]
        o = {"n": int(len(X)), "n_scored": int(len(Bh)), "last_print": round(float(hit(Bh.p, Bh["last"]).mean()), 3)}
        for form in ("prop", "lay"):
            d = float(np.nanmedian(A.p - A[form]))
            o[form] = {"delta_c": round(d * 100, 2), "within_tick": round(float(hit(Bh.p, np.round(Bh[form] + d, 2)).mean()), 3),
                       "sd_c": round(float(np.nanstd((Bh.p - Bh[form]) * 100)), 2)}
            k = np.isfinite(A[form]) & np.isfinite(A.p)
            if k.sum() >= 10:
                Z = np.c_[np.ones(k.sum()), np.abs(A[form][k] - 0.5)]
                beta = np.linalg.lstsq(Z, (A.p - A[form])[k], rcond=None)[0]
                pr = Bh[form] + beta[0] + beta[1] * np.abs(Bh[form] - 0.5)
                o[form]["level_margin_within_tick"] = round(float(hit(Bh.p, np.round(pr, 2)).mean()), 3)
        return o
    out["pooled"]["pre_game"] = score(pre_rows, "pre")
    out["pooled"]["in_play"] = score(ip_rows, "inplay")
    if ev_stats:
        out["pooled"]["event_time"] = {"matches": len(ev_stats), "share": round(float(np.mean([e[0] for e in ev_stats])), 3),
                                       "null": round(float(np.mean([e[1] for e in ev_stats])), 3),
                                       "ratio": round(float(np.mean([e[0] for e in ev_stats]) / max(1e-9, np.mean([e[1] for e in ev_stats]))), 2)}
    if xc:
        out["pooled"]["xcorr_peaks"] = xc
    (RES / f"tp_valuation_tests_{int(blocks[0][0])}.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps(out, indent=1, default=float)[:4000])


if __name__ == "__main__":
    a = [float(x) for x in sys.argv[1:]]
    main([(a[i], a[i + 1]) for i in range(0, len(a), 2)])
