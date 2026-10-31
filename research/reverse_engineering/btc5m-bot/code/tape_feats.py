"""Point-in-time Polymarket tape features for cells (window, outcome, second).

Uses taker rows of OTHER traders only: rows whose taker is a cluster wallet are dropped, and so are rows whose
transaction contains a cluster maker fill (takers that traded against the cluster), so no feature carries the
cluster's own fills. At cell second s only prints with block ts <= s-1 are used.
"""
import os as _os; _ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))  # repo root
import os
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"
TAPE_DIR = f"{C}/tapes"
CL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
TF = ["has_tape", "pU_last", "age_last", "askU", "age_askU", "bidU", "age_bidU", "vwap10", "vwap30", "n1", "n2", "n5", "n30", "flow1", "flow2", "flow5", "flow30", "vol30", "sp_since_last"]


def load_tape(cid, cluster_maker_txs):
    p = f"{TAPE_DIR}/{cid}.parquet"
    if not os.path.exists(p):
        return None
    d = pd.read_parquet(p)
    if len(d) == 0 or "timestamp" not in d:
        return d.iloc[0:0] if len(d) == 0 else None
    d = d[~d.proxyWallet.str.lower().isin(CL)]
    d = d[~d.transactionHash.isin(cluster_maker_txs)]
    return d.sort_values("timestamp", kind="stable")


def window_feats(d, start, rel, lp_fn):
    """rel: array of seconds (0..299) for this window; returns dict of Up-oriented arrays."""
    s = start + rel
    n = len(rel)
    out = {k: np.full(n, np.nan) for k in TF}
    if d is None:
        out["has_tape"][:] = 0
        return out
    out["has_tape"][:] = 1
    if len(d) == 0:
        return out
    ts = d.timestamp.to_numpy()
    up = (d.outcome.to_numpy() == "Up")
    buy = (d.side.to_numpy() == "BUY")
    p = d.price.to_numpy().astype(float)
    sz = d["size"].to_numpy().astype(float)
    pU = np.where(up, p, 1 - p)
    askU = np.where(up & buy, p, np.where(~up & ~buy, 1 - p, np.nan))
    bidU = np.where(up & ~buy, p, np.where(~up & buy, 1 - p, np.nan))
    flowU = np.where(up == buy, sz, -sz)
    idx = np.searchsorted(ts, s - 1, side="right") - 1  # last print with ts <= s-1
    ok = idx >= 0
    ii = np.clip(idx, 0, None)
    out["pU_last"] = np.where(ok, pU[ii], np.nan)
    out["age_last"] = np.where(ok, s - ts[ii], np.nan)
    for name, arr in (("askU", askU), ("bidU", bidU)):
        v = pd.Series(arr).ffill().to_numpy()
        tv = pd.Series(np.where(np.isfinite(arr), ts, np.nan)).ffill().to_numpy()
        out[name] = np.where(ok, v[ii], np.nan)
        out["age_" + name] = np.where(ok, s - tv[ii], np.nan)
    cs_n = np.r_[0, np.cumsum(np.ones(len(ts)))]
    cs_v = np.r_[0, np.cumsum(sz)]
    cs_pv = np.r_[0, np.cumsum(sz * pU)]
    cs_f = np.r_[0, np.cumsum(flowU)]
    hi = idx + 1
    for w, nm in ((1, "1"), (2, "2"), (5, "5"), (10, "10"), (30, "30")):
        lo = np.searchsorted(ts, s - 1 - w, side="right")  # prints with ts in (s-1-w, s-1]
        nn = cs_n[hi] - cs_n[lo]
        vv = cs_v[hi] - cs_v[lo]
        if nm in ("1", "2", "5", "30"):
            out["n" + nm] = nn
            out["flow" + nm] = cs_f[hi] - cs_f[lo]
        if nm in ("10", "30"):
            with np.errstate(invalid="ignore", divide="ignore"):
                out["vwap" + nm] = np.where(vv > 0, (cs_pv[hi] - cs_pv[lo]) / vv, np.nan)
        if nm == "30":
            out["vol30"] = vv
    # Binance move since the last print (both ends usable: last print ts <= s-1 -> spot second ts-1 used there)
    tl = np.where(ok, ts[ii], s - 2)
    out["sp_since_last"] = np.where(ok, (lp_fn(s - 2) - lp_fn(np.minimum(tl - 1, s - 2))) * 1e4, np.nan)
    return out


def add_tape_feats(cells, fills, sp):
    """Adds outcome-oriented tape features to a cell frame produced by cells.build_cells."""
    mk = fills[fills.role == "M"]
    cm_by_cid = {c: np.asarray(g.unique()) for c, g in mk.groupby("cid").tx}
    lp = np.log(sp.px)
    lp_fn = lambda t: lp[np.asarray(t, dtype=np.int64) - sp.s0]
    cols = {k: np.full(len(cells), np.nan, dtype=np.float32) for k in TF}
    g = cells.groupby("cid").indices
    for cid, ix in g.items():
        d = load_tape(cid, cm_by_cid.get(cid, np.array([], dtype=object)))
        start = int(cells.start_ts.iat[ix[0]])
        f = window_feats(d, start, cells.rel.to_numpy()[ix].astype(np.int64), lp_fn)
        for k in TF:
            cols[k][ix] = f[k]
    isup = cells.is_up.to_numpy()
    sg = np.where(isup, 1.0, -1.0)
    out = cells
    out["has_tape"] = cols["has_tape"]
    out["m_last"] = np.where(isup, cols["pU_last"], 1 - cols["pU_last"])
    out["age_last"] = cols["age_last"]
    out["ask_o"] = np.where(isup, cols["askU"], 1 - cols["bidU"])
    out["age_ask"] = np.where(isup, cols["age_askU"], cols["age_bidU"])
    out["bid_o"] = np.where(isup, cols["bidU"], 1 - cols["askU"])
    out["age_bid"] = np.where(isup, cols["age_bidU"], cols["age_askU"])
    out["vwap10"] = np.where(isup, cols["vwap10"], 1 - cols["vwap10"])
    out["vwap30"] = np.where(isup, cols["vwap30"], 1 - cols["vwap30"])
    for k in ("n1", "n2", "n5", "n30", "vol30"):
        out[k] = cols[k]
    out["flow1"] = sg * cols["flow1"]; out["flow2"] = sg * cols["flow2"]
    out["flow5"] = sg * cols["flow5"]; out["flow30"] = sg * cols["flow30"]
    out["sp_since"] = sg * cols["sp_since_last"]
    out["gap_m"] = out.fv - out.m_last
    out["gap_ask"] = out.fv - out.ask_o
    out["gap_vw"] = out.fv - out.vwap30
    out["spread"] = out.ask_o - out.bid_o
    return out


TAPE_FEATS = ["m_last", "age_last", "ask_o", "age_ask", "bid_o", "age_bid", "vwap10", "vwap30", "n1", "n2", "n5", "n30", "vol30", "flow1", "flow2", "flow5", "flow30", "sp_since", "gap_m", "gap_ask", "gap_vw", "spread"]
