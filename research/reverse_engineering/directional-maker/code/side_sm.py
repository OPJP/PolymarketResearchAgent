"""R8 side (iteration 12): the decoded window state machine for the side of each cluster maker BUY fill, on the block
clock (no recordings needed). Branches, in order (frozen 2026-11-01 iteration 12; exploratory on VALIDATE, see NOTES):
  (i)   decided window: |Up mid - 0.5| > DECIDED at b - 3 (last clean print stamped <= b - 3) -> the cheaper token;
  (ii)  entry: the CLUSTER (all three wallets, maker + taker BUY rows) holds no net position in the window before the
        fill's second -> the Chainlink posture (report stamped b - 4 ~ floor((b - 2.285 s - 1.432 s)), Gamma strike,
        1.4 x 300-s Binance vol) where the value is available, else the Binance stand-in digital;
  (iii) after entry, the filled order's calldata original size is a schedule size -> the outcome the cluster holds more
        of (adds to the held outcome); not a schedule size (imbalance pairing bids) -> the under-held outcome;
        calldata missing -> the held outcome.
(ii)-(iii) use own state (the cluster's inventory, the order's own size): reported separately from the public part
('no_own_state' = (i) else the posture). Baselines: cheaper token, favourite, posture alone, held outcome alone, and the
own-history baseline 'own_history_prev_fill' (the outcome of the cluster's previous BUY fill in the window, strictly
earlier second; the posture where there is none). Iteration-12 finding: the own-history baseline (0.822 per fill on
VALIDATE) beats the own-state composite (0.790): after entry the fill side is mostly the persistence of same-side fill
runs, so the counted R8 side is the PUBLIC part 'no_own_state' (decided window -> cheaper token, else the posture).
Iteration 17 (R8c, pre-registered T5, adopted on VALIDATE 10-27..30: per fill 0.6925 -> 0.7009, STUDY 0.569 -> 0.577):
the BTC 5m window that starts at the NYSE open (09:30 America/New_York on a weekday; 13:30 UTC under US DST, 14:30
UTC otherwise) -> the cheaper token, whatever the posture says. Found from the out-of-fold BUILD residual (E2): in that
window the cluster fills ~4x its usual count, at a mean price ~0.2-0.3, on the cheaper token (STUDY 0.99, VALIDATE 0.90,
R8 0.40-0.44). The counted side is now 'r8c_no_own_state'; 'no_own_state' (R8) is still reported.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DECIDED = 0.4
SIGMA_K = 1.4
CL_STAMP_LAG = 4
STD_SIZES = (500, 1000, 250, 125, 100, 62, 50, 12, 300, 40, 200, 2000, 25, 31, 20, 10, 5)
IT12_MAX_TX = 3000
NYSE_OPEN_TO_CHEAPER = True  # iteration 17 R8c


def nyse_open_utc(day_ts: int):
    """09:30 America/New_York of the UTC day starting at day_ts as a UTC timestamp (US DST from the 2nd Sunday of March
    to the 1st Sunday of November); None on Saturdays and Sundays (NYSE holidays are not modelled)."""
    from datetime import datetime, timezone
    d = datetime.fromtimestamp(int(day_ts), tz=timezone.utc)
    if d.weekday() >= 5:
        return None

    def nth_sunday(month, n):
        first = datetime(d.year, month, 1, tzinfo=timezone.utc)
        return first.timestamp() + (((6 - first.weekday()) % 7) + 7 * (n - 1)) * 86400
    dst = nth_sunday(3, 2) <= day_ts < nth_sunday(11, 1)
    return int(day_ts + (13 if dst else 14) * 3600 + 1800)


def nyse_open_window(st, en) -> np.ndarray:
    """True for BTC 5m windows (en - st == 300) that start exactly at the NYSE open."""
    st = np.asarray(st, dtype=np.int64)
    en = np.asarray(en, dtype=np.int64)
    cache = {}
    out = np.zeros(len(st), dtype=bool)
    for i, (a, b) in enumerate(zip(st, en)):
        day = int(a) // 86400 * 86400
        if day not in cache:
            cache[day] = nyse_open_utc(day)
        out[i] = (int(b) - int(a) == 300) and cache[day] is not None and int(a) == cache[day]
    return out


def side_state_machine(mk: pd.DataFrame, buys: pd.DataFrame, w: pd.DataFrame, clean: pd.DataFrame, sp, txh: dict,
                       cluster: dict, ptb: dict | None = None, cl_values=None, max_tx: int = IT12_MAX_TX) -> dict:
    from scipy.stats import norm
    from features2 import fair_up as _fair_up
    if mk is None or not len(mk):
        return {"n": 0}
    w = w.copy()
    w["up_token"], w["down_token"] = w["up_token"].astype(str), w["down_token"].astype(str)
    tok2cid = {**dict(zip(w["up_token"], w["cid"])), **dict(zip(w["down_token"], w["cid"]))}
    up_of = dict(zip(w["cid"], w["up_token"]))
    st_of, en_of = dict(zip(w["cid"], w["start_ts"])), dict(zip(w["cid"], w["end_ts"]))
    mids = {}
    c2 = clean[clean["cid"].astype(str).isin(set(w["cid"]))]
    for cid, g in c2.groupby("cid", observed=True):
        cid = str(cid)
        g = g.sort_values("ts", kind="stable")
        isu = g["asset"].astype(str).to_numpy() == up_of[cid]
        pr = g["price"].to_numpy(dtype=float)
        mids[cid] = (g["ts"].to_numpy(dtype=np.int64), np.where(isu, pr, 1 - pr))
    b2 = buys.assign(cid2=buys["token_id"].astype(str).map(tok2cid)).dropna(subset=["cid2"])
    inv = {}
    for cid, g in b2.groupby("cid2"):
        g = g.sort_values("ts", kind="stable")
        isu = g["token_id"].astype(str).to_numpy() == up_of[cid]
        sh = g["shares"].to_numpy(dtype=float)
        inv[cid] = (g["ts"].to_numpy(dtype=np.int64), np.cumsum(np.where(isu, sh, -sh)), isu.astype(np.int8))
    rows = []
    for r in mk.itertuples(index=False):
        cid = tok2cid.get(str(r.token_id))
        if cid is None or cid not in mids:
            continue
        ts_, mu_ = mids[cid]
        i = np.searchsorted(ts_, int(r.ts) - 3, side="right") - 1
        if i < 0:
            continue
        it, ic, iu = inv.get(cid, (np.array([], dtype=np.int64), np.array([]), np.array([], dtype=np.int8)))
        j = np.searchsorted(it, int(r.ts), side="left") - 1
        net = float(ic[j]) if j >= 0 else 0.0
        prev_up = int(iu[j]) if j >= 0 else -1
        rows.append((str(r.wallet), cid, int(st_of[cid]), int(en_of[cid]), int(str(r.token_id) == up_of[cid]), int(r.ts),
                     float(mu_[i]), net, txh.get(int(r.tx)) if txh else None, str(r.token_id), prev_up))
    if not rows:
        return {"n": 0}
    D = pd.DataFrame(rows, columns=["wallet", "cid", "st", "en", "is_up", "ts", "mid_up", "net", "txh", "token", "prev_up"])
    y = D["is_up"].to_numpy() == 1
    mid = D["mid_up"].to_numpy()
    tsec = D["ts"].to_numpy()
    fb, _ = _fair_up(sp, D["st"].to_numpy(), D["en"].to_numpy(), tsec - 2)
    post = fb > mid
    cl_cov = 0.0
    if ptb is not None and cl_values is not None:
        try:
            stamps = sorted(set((tsec - CL_STAMP_LAG).astype(np.int64).tolist()))
            clv = cl_values(stamps)
            cl = np.array([clv.get(int(s), np.nan) for s in tsec - CL_STAMP_LAG], dtype=float)
            K = np.array([ptb.get(int(s), np.nan) for s in D["st"]], dtype=float)
            sig = np.array([float(sp.sigma(np.array([t - 2]), look=300)[0]) for t in tsec]) * SIGMA_K
            tau = np.maximum(D["en"].to_numpy() - (tsec - 2.285), 1.0)
            with np.errstate(divide="ignore", invalid="ignore"):
                fcl = norm.cdf(np.log(cl / K) / (sig * np.sqrt(tau)))
            okc = np.isfinite(fcl)
            post = np.where(okc, fcl > mid, post)
            cl_cov = float(okc.mean())
        except Exception:  # noqa: BLE001
            pass
    # order original size from the fill transactions' calldata (at most max_tx transactions)
    orig = np.full(len(D), np.nan)
    ntx = 0
    try:
        sys.path.insert(0, str(HERE.parent / "code4"))
        import calldata as _cd
        txs = [t for t in dict.fromkeys(D["txh"].dropna().astype(str))][:max_tx]
        ntx = len(txs)
        sizes = {}
        for hh, tx in _cd.fetch_txs(txs):
            dd = _cd.decode(tx["input"]) if tx else None
            if not dd:
                continue
            for o in dd.get("makers", []):
                if o["maker"].lower() in cluster and int(o["oside"]) == 0:
                    sizes[(hh.lower(), o["maker"].lower(), str(o["token_id"]))] = round(int(o["taker_amount"]) / 1e6, 2)
        orig = np.array([sizes.get((str(t_).lower(), str(w_).lower(), k_), np.nan) for t_, w_, k_ in zip(D["txh"], D["wallet"], D["token"])])
    except Exception:  # noqa: BLE001
        pass
    dec = np.abs(mid - 0.5) > DECIDED
    cheap = mid < 0.5
    net = D["net"].to_numpy()
    held = net > 0
    sched = np.isin(orig, STD_SIZES)
    known = np.isfinite(orig)
    after = np.where(known & ~sched, net < 0, held)
    comp = np.where(dec, cheap, np.where(net == 0, post, after))
    comp_ns = np.where(dec, cheap, np.where(net == 0, post, held))
    noown = np.where(dec, cheap, post)
    op = nyse_open_window(D["st"].to_numpy(), D["en"].to_numpy()) if NYSE_OPEN_TO_CHEAPER else np.zeros(len(D), bool)
    r8c = np.where(op, cheap, noown)
    rules = {"r8c_no_own_state": r8c, "composite_own_state": comp, "composite_own_state_no_size": comp_ns, "no_own_state": noown, "posture": post,
             "cheaper": cheap, "favourite": ~cheap, "held_only": np.where(net != 0, held, post),
             "own_history_prev_fill": np.where(D["prev_up"].to_numpy() >= 0, D["prev_up"].to_numpy() == 1, post)}

    def acc(p, m=None):
        m = np.ones(len(y), dtype=bool) if m is None else m
        return float(np.mean((p == y)[m])) if m.any() else None
    out = {"counted_side": "r8c_no_own_state", "n_nyse_open_window": int(op.sum()), "n": int(len(D)), "chainlink_coverage": cl_cov, "calldata_tx": ntx, "calldata_joined": float(known.mean()),
           "share_decided": float(dec.mean()), "share_entry": float((~dec & (net == 0)).mean()),
           "share_after_nonschedule": float((~dec & (net != 0) & known & ~sched).mean())}
    for k, p in rules.items():
        out[k] = acc(p)
    out["per_wallet"] = {nm: {k: acc(p, (D["wallet"].str.lower() == ad).to_numpy()) for k, p in rules.items() if k in ("composite_own_state", "no_own_state", "r8c_no_own_state")}
                         for ad, nm in cluster.items() if (D["wallet"].str.lower() == ad).any()}
    midt = (int(D["ts"].min()) + int(D["ts"].max())) // 2
    h1 = (D["ts"] < midt).to_numpy()
    out["halves"] = {"first": acc(comp, h1), "second": acc(comp, ~h1)}
    out["branches"] = {"decided": acc(comp, dec), "entry": acc(comp, ~dec & (net == 0)), "after_schedule_held": acc(comp, ~dec & (net != 0) & ~(known & ~sched)),
                       "after_nonschedule_under": acc(comp, ~dec & (net != 0) & known & ~sched)}
    # iteration 13 (reporting only; panel iter12 information C1/C4): the side per burst start, the quote-decision unit.
    # A burst = consecutive cluster fills of one window on one outcome with block-second gaps < 3 s; its start is the
    # first fill. Reported for every burst start and for starts after a gap of >= 30 s since the previous cluster fill.
    try:
        o_ = np.lexsort((D["ts"].to_numpy(), D["cid"].astype(str).to_numpy()))
        cid_o = D["cid"].astype(str).to_numpy()[o_]
        ts_o = D["ts"].to_numpy().astype(float)[o_]
        up_o = D["is_up"].to_numpy()[o_]
        same = np.r_[False, cid_o[1:] == cid_o[:-1]]
        gap = np.r_[np.inf, np.diff(ts_o)]
        gap[~same] = np.inf
        chg = np.r_[True, up_o[1:] != up_o[:-1]] | ~same
        bs = (gap >= 3) | chg
        m_all = np.zeros(len(y), dtype=bool)
        m_all[o_[bs]] = True
        m_long = np.zeros(len(y), dtype=bool)
        m_long[o_[bs & (gap >= 30)]] = True
        keys = ("r8c_no_own_state", "no_own_state", "posture", "cheaper", "composite_own_state", "own_history_prev_fill")
        out["per_burst_start"] = {"n": int(m_all.sum()), **{k: acc(rules[k], m_all) for k in keys},
                                  "gap_ge_30s": {"n": int(m_long.sum()), **{k: acc(rules[k], m_long) for k in keys}}}
    except Exception as ex:  # noqa: BLE001
        out["per_burst_start_error"] = repr(ex)[:200]
    return out
