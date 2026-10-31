"""Iteration 4: cross-asset point-in-time features (Binance USD-M ETHUSDT perpetual, optionally SOL / XRP / DOGE perps)
for cells. PIT: alt trades with T < (s - 1) * 1000 ms (same horizon as the BTC venues). Directional features are oriented
toward the cell's outcome (+ = the alt moved in the direction that favours the outcome, i.e. up for Up).
Features per alt prefix p: p_pm{500..10000} (log move, bp), p_ofin1000/3000 (signed volume share), p_age_tr, p_ntr1000,
p_rel{1000,2000,3000} = p_pm - BETA[p] * C6_pm (alt move not yet seen in the six-series BTC mean), p_since (alt move since
the last Polymarket print). With several alts also composites in BTC-equivalent units (divided by BETA): A_relmean{w},
A_pmmean{w}, A_nup3000 / A_ndn3000 (alts whose BTC-equivalent relative 3-s move is >= +0.3 / <= -0.3 bp).
BETA was measured on BUILD side rows only (train5.py / train6.py) and is frozen here."""
import os
import numpy as np, pandas as pd
from ofi import Agg
from venue_cells import feats_for, VWIN

ALTS = (("E", "ethfut"),)                                                   # iteration-4 rule it4 (ETH only)
ALTS4 = (("E", "ethfut"), ("L", "solfut"), ("X", "xrpfut"), ("G", "dogefut"))  # iteration-4 rule it4b (ETH, SOL, XRP, DOGE)
# regression slope of the alt 3-s move on the six-series BTC mean 3-s move, BUILD side rows (E from train5.py; L/X/G from train6.py)
BETA = {"E": 1.235, "L": 1.508, "X": 1.376, "G": 1.428}
_PER = [f"pm{w}" for w in VWIN] + ["ofin1000", "ofin3000", "age_tr", "ntr1000"] + [f"rel{w}" for w in (1000, 2000, 3000)] + ["since"]
COMP = [f"A_relmean{w}" for w in (1000, 2000, 3000)] + [f"A_pmmean{w}" for w in (1000, 2000, 3000)] + ["A_nup3000", "A_ndn3000"]


def feat_names(alts):
    return [f"{p}_{k}" for p, _ in alts for k in _PER] + (COMP if len(alts) > 1 else [])


ALT_FEATS = feat_names(ALTS)
ALT4_FEATS = feat_names(ALTS4)


def alt_frame(sub: str, day0: int, ven_dir: str):
    parts = [pd.read_parquet(f"{ven_dir}/{sub}/{d}.parquet") for d in (day0 - 86400, day0, day0 + 86400) if os.path.exists(f"{ven_dir}/{sub}/{d}.parquet")]
    if not parts:
        return None
    return pd.concat(parts, ignore_index=True).drop_duplicates()


def _lp_before(a: Agg, t_ms):
    i = np.searchsorted(a.T, np.asarray(t_ms, np.int64), side="left") - 1
    return np.where(i >= 0, a.lp[np.clip(i, 0, None)], np.nan)


def alt_feats(c: pd.DataFrame, aggs: dict, c6_pm: dict, beta: dict = None, alts=ALTS) -> pd.DataFrame:
    """c needs start_ts, rel, is_up, age_last; aggs = {prefix: Agg|None}; c6_pm = {1000|2000|3000: oriented six-series mean
    move (same rows)}."""
    beta = BETA if beta is None else beta
    s = c.start_ts.to_numpy(np.int64) + c.rel.to_numpy(np.int64)
    sg = np.where(c.is_up.to_numpy(), 1.0, -1.0)
    t_end = (s - 1) * 1000
    age = c.age_last.to_numpy(float)
    t_last = np.where(np.isfinite(age), (s - np.nan_to_num(age, nan=0.0) - 1) * 1000, 0).astype(np.int64)
    out = {}
    for p, _ in alts:
        a = aggs.get(p)
        if a is None:
            for k in _PER:
                out[f"{p}_{k}"] = np.full(len(c), np.nan, np.float32)
            continue
        out.update(feats_for(a, t_end, sg, p))
        for w in (1000, 2000, 3000):
            out[f"{p}_rel{w}"] = (out[f"{p}_pm{w}"].astype(float) - beta[p] * np.nan_to_num(np.asarray(c6_pm[w], float), nan=0.0)).astype(np.float32)
        cov = (t_end - 15000 >= a.T[0]) & (t_end <= a.T[-1]) & np.isfinite(age)
        out[f"{p}_since"] = np.where(cov, sg * (_lp_before(a, t_end) - _lp_before(a, t_last)) * 1e4, np.nan).astype(np.float32)
    if len(alts) > 1:
        add_composites(out, alts, beta)
    return pd.DataFrame(out)


def add_composites(out, alts, beta):
    """out: dict-like with the per-alt columns; adds the BTC-equivalent alt composites in place."""
    for w in (1000, 2000, 3000):
        rel = np.stack([np.asarray(out[f"{p}_rel{w}"], float) / beta[p] for p, _ in alts], 1)
        pm = np.stack([np.asarray(out[f"{p}_pm{w}"], float) / beta[p] for p, _ in alts], 1)
        out[f"A_relmean{w}"] = np.nanmean(rel, 1).astype(np.float32)
        out[f"A_pmmean{w}"] = np.nanmean(pm, 1).astype(np.float32)
        if w == 3000:
            out["A_nup3000"] = np.nansum(rel >= 0.3, 1).astype(np.float32); out["A_ndn3000"] = np.nansum(rel <= -0.3, 1).astype(np.float32)


# iteration 4 (late): explicit lagged segments for the side model (decision-time alignment; side_lag.py, model_it4b_side_lag.txt)
LAG_SERIES = ["F", "O", "B", "S", "Y", "K", "E", "L", "X", "G"]
LAG_FEATS = [f"{q}_{k}" for q in LAG_SERIES for k in ("d21", "d32")] + ["M_d21", "N_d21", "C6_d21", "C6_d32", "A_d21", "A_d32"]


def lag_feats(s: pd.DataFrame, beta: dict = None) -> pd.DataFrame:
    """s: side frame (Up-cell features). q_d21 = q_pm2000 - q_pm1000 (move in [s-3, s-2)), q_d32 = q_pm3000 - q_pm2000
    ([s-4, s-3)); alts divided by BETA (BTC-equivalent); M_d21 = signed largest d21 across the ten series; N_d21 = number of
    series with d21 >= +0.3 minus number <= -0.3; composites' segments. Adds the columns in place and returns s."""
    beta = BETA if beta is None else beta
    st = []
    for q in LAG_SERIES:
        sc = beta.get(q, 1.0) if q in ("E", "L", "X", "G") else 1.0
        a1, a2, a3 = (s[f"{q}_pm{w}"].astype(float) / sc for w in (1000, 2000, 3000))
        s[f"{q}_d21"] = (a2 - a1).astype(np.float32); s[f"{q}_d32"] = (a3 - a2).astype(np.float32); st.append((a2 - a1).to_numpy())
    st = np.stack(st, 1); ab = np.where(np.isfinite(st), np.abs(st), -1.0); j = ab.argmax(1)
    s["M_d21"] = np.where(ab.max(1) >= 0, st[np.arange(len(st)), j], np.nan).astype(np.float32)
    s["N_d21"] = (np.nansum(st >= 0.3, 1) - np.nansum(st <= -0.3, 1)).astype(np.float32)
    s["C6_d21"] = (s.C6_pm2000 - s.C6_pm1000).astype(np.float32); s["C6_d32"] = (s.C6_pm3000 - s.C6_pm2000).astype(np.float32)
    s["A_d21"] = (s.A_pmmean2000 - s.A_pmmean1000).astype(np.float32); s["A_d32"] = (s.A_pmmean3000 - s.A_pmmean2000).astype(np.float32)
    return s
