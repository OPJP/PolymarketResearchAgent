"""directional-maker iteration 14: the uncensored quote-unit side from the exam recorder dx_clob (examinable form).

Unit: every 500 / 1000 add at the touch of a BTC 5m / 15m window in dx_clob ('pc' rows [side, p, size_after, delta] with
the record's best bid / ask; side 1 = Up bid = Up BUY, side 0 = Up ask = Down BUY). Frozen side rule (iteration 14,
fit 10-31 14-16, test 16-18 on the full-depth book: 0.815 / 0.811): Up iff F_CL > Up mid just before the add, F_CL =
Phi((CL(stamp <= t - 1,000 ms) - priceToBeat) / (1.0 x sigma_fut300 x sqrt(tau))), sigma_fut300 = sd of 1-s changes of the
Binance USD-M bookTicker mid over the previous 300 s (dx_bnf, else dm_bnf). Baselines: always Up, cheaper outcome,
the outcome whose Up mid rose over the last 1 s (market-only, the engine follows the mid). Caveat: exact-size adds include
other makers' orders (~12% of exact 500s, X36); the label is the post, not the wallet.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code14/qu_dx.py <start> <end> [allow_sealed]
"""
from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
import live  # noqa: E402
import cl_source  # noqa: E402

QU_L_MS, QU_K, QU_LOOK = 1432, 1.0, 300   # fallback stamp lag = p90 publish delay (point-in-time safe)
SIZES = (500.0, 1000.0)


def _iter(feed, a, b, allow_sealed):
    for h in range(a - a % 3600, b, 3600):
        try:
            for r in live.iter_live(feed, max(h, a), min(h + 3600, b), allow_sealed=allow_sealed):
                yield r
        except (zlib.error, EOFError, OSError):
            continue


def _fut(a, b, allow_sealed):
    E, M = [], []
    for feed in ("dx_bnf", "dm_bnf"):
        for r in _iter(feed, a - QU_LOOK - 5, b, allow_sealed):
            v = r.get("r")
            if v and v[0] == "b":
                E.append(v[1]); M.append((v[3] + v[5]) / 2)
        if E:
            break
    E = np.asarray(E, np.int64); M = np.asarray(M, float); o = np.argsort(E, kind="stable")
    return E[o], M[o]


def _at(E, M, t):
    i = np.searchsorted(E, t, side="right") - 1
    return np.where(i >= 0, M[np.clip(i, 0, None)], np.nan)


def quote_unit_side(a: int, b: int, allow_sealed: bool = False, intervals=None) -> dict:
    adds, mids, last = [], [], {}
    for r in _iter("dx_clob", a, b, allow_sealed):
        if r.get("k") != "pc":
            continue
        w = r.get("w") or ""
        if not w.startswith(("btc-updown-5m-", "btc-updown-15m-")):
            continue
        bb, ba, s = r.get("bb"), r.get("ba"), r.get("s")
        if bb is None or ba is None or not s:
            continue
        mm = (bb + ba) / 2
        if last.get(w) != mm:
            last[w] = mm; mids.append((w, s, mm))
        for row in r.get("c") or []:
            if len(row) < 4:
                continue
            sd, p, dz = row[0], round(row[1], 3), round(row[3], 2)
            if dz in SIZES and ((sd == 1 and abs(p - bb) < 1e-9) or (sd == 0 and abs(p - ba) < 1e-9)):
                adds.append((w, s, sd, p, dz))
    if not adds:
        return {"n": 0, "note": "no dx_clob at-touch schedule adds in the period"}
    A = pd.DataFrame(adds, columns=["w", "s", "sd", "p", "dz"])
    if intervals:
        st_ = A.w.str.rsplit("-", n=1).str[1].astype(int)
        keep = np.zeros(len(A), bool)
        for lo, hi in intervals:
            keep |= ((st_ >= lo) & (st_ < hi)).to_numpy()
        A = A[keep].reset_index(drop=True)
        if A.empty:
            return {"n": 0, "note": "no at-touch schedule adds in windows starting in the intervals"}
    Mi = pd.DataFrame(mids, columns=["w", "s", "mid"]).sort_values(["w", "s"], kind="stable")
    ser = {w: (g.s.to_numpy(np.int64), g.mid.to_numpy(float)) for w, g in Mi.groupby("w")}
    t = A.s.to_numpy(np.int64); w_ = A.w.to_numpy(object)
    mid0 = np.full(len(A), np.nan); mid1 = np.full(len(A), np.nan)
    for w in np.unique(w_):
        ix = np.where(w_ == w)[0]; s_, m_ = ser[w]
        mid0[ix] = _at(s_, m_, t[ix] - 1); mid1[ix] = _at(s_, m_, t[ix] - 1000)
    E, M = _fut(a, b, allow_sealed)
    if len(E) == 0:
        return {"n": int(len(A)), "note": "no futures recording"}
    s0, s1 = int(E[0] // 1000), int(E[-1] // 1000) + 1
    secs = np.arange(s0, s1 + 1)
    d1 = np.diff(_at(E, M, secs * 1000 + 999), prepend=np.nan)
    sig = pd.Series(d1, index=secs).rolling(QU_LOOK, min_periods=QU_LOOK // 2).std().shift(1)
    clv = cl_source.cl_values(sorted(set(((t - QU_L_MS) // 1000).tolist())), allow_sealed=allow_sealed, fetch=True, max_requests=300)
    from polyrea.workflows.updown_study import fetch_windows
    raw = fetch_windows(sorted(set(A.w)))
    K = {}
    for m in raw.values():
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
    en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300)
    cl = clv.reindex((t - QU_L_MS) // 1000).to_numpy(float)
    # exact public publish clock where the streaming recorder dy_rtds has the report's publish ms ('P'): the latest BTC
    # Chainlink report published before the post (strictly point in time); else the stamp-lag fallback above
    pub = [(int(r["P"]), float(r["v"])) for r in _iter("dy_rtds", a - 10, b, allow_sealed)
           if r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P")]
    n_exact = 0
    if pub:
        pa = np.array(sorted(pub)); pm_, pv_ = pa[:, 0].astype(np.int64), pa[:, 1]
        i = np.searchsorted(pm_, t, side="right") - 1
        exact = (i >= 0) & (t - pm_[np.clip(i, 0, None)] < 3000)
        cl = np.where(exact, pv_[np.clip(i, 0, None)], cl)
        n_exact = int(exact.sum())
    sg = sig.reindex(t // 1000).to_numpy(float) * QU_K
    with np.errstate(divide="ignore", invalid="ignore"):
        F = norm.cdf((cl - A.w.map(K).to_numpy(float)) / (sg * np.sqrt(np.maximum(en - t / 1000, 1.0))))
    y = (A.sd == 1).to_numpy(float)
    ok = np.isfinite(F) & np.isfinite(mid0)
    P = (F > mid0).astype(float)
    rose = np.where(np.abs(mid0 - mid1) >= 0.005, (mid0 > mid1).astype(float), np.nan)

    def acc(pred, m):
        m = m & np.isfinite(pred)
        return [round(float((pred[m] == y[m]).mean()), 4) if m.sum() else None, int(m.sum())]
    half = t < (a + (b - a) // 2) * 1000
    out = {"n": int(len(A)), "n_scored": int(ok.sum()), "n_exact_publish_clock": n_exact,
           "rule": f"posture at the post: latest Chainlink report published before it (dy_rtds publish ms), else stamp <= t - {QU_L_MS} ms; k{QU_K} x futures sigma{QU_LOOK}",
           "side_accuracy": acc(P, ok), "first_half": acc(P, ok & half), "second_half": acc(P, ok & ~half),
           "btc5m": acc(P, ok & A.w.str.contains("-5m-").to_numpy()), "btc15m": acc(P, ok & A.w.str.contains("-15m-").to_numpy()),
           "baseline_always_up": round(float(y[ok].mean()), 4) if ok.any() else None,
           "baseline_cheaper": acc((mid0 < 0.5).astype(float), ok), "baseline_mid_rose_1s": acc(rose, ok),
           "caveat": "exact 500/1000 adds at the touch include other makers' orders (~12% of exact 500s, X36); unit = post, not wallet"}
    return out


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    r = quote_unit_side(a, b, allow_sealed="allow_sealed" in sys.argv[3:])
    print(json.dumps(r, indent=1))
    (HERE.parent / "results" / f"iter14_qu_dx_{a}_{b}.json").write_text(json.dumps(r, indent=1))
