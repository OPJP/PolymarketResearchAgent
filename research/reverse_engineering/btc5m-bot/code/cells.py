"""Cell grid (window, outcome, second) with point-in-time public features and cluster fill labels.

PIT rule: a cell is second s = start + rel, i.e. [s, s+1). Features use Binance closes of seconds <= s-2
(a kline [q, q+1) is usable from q+2). No own-state features here.
"""
import numpy as np, pandas as pd
from scipy.special import ndtr

RETS = (1, 2, 3, 5, 10, 20, 30, 60)


def build_cells(win, fills, sp, rel_max=300, nonpit_diag=False):
    win = win.sort_values("start_ts").reset_index(drop=True)
    nW = len(win)
    rel = np.tile(np.arange(rel_max), nW)
    wi = np.repeat(np.arange(nW), rel_max)
    start = win.start_ts.to_numpy()[wi]; end = win.end_ts.to_numpy()[wi]
    s = start + rel
    q = s - 2
    lp = np.log(sp.px)
    L = lambda t: lp[t - sp.s0]
    K = sp.mean(win.start_ts.to_numpy() - 60, win.start_ts.to_numpy())[wi]
    sig = sp.sigma(q)
    tau = (end - s).astype(float)
    lq = L(q)
    z = (lq - np.log(K)) / (sig * np.sqrt(np.maximum(tau, 1)))
    z = np.where(rel >= 1, z, np.nan)
    base = {"wi": wi.astype(np.int32), "rel": rel.astype(np.int16), "tau": tau.astype(np.float32), "sig": (sig * 1e5).astype(np.float32)}
    feats_up = {"z": z}
    for h in RETS:
        r = lq - L(q - h)
        feats_up[f"r{h}"] = r * 1e4
        feats_up[f"rn{h}"] = r / (sig * np.sqrt(h))
    # largest single-second move in the last 3 / 10 s (signed toward Up)
    r1 = np.stack([L(q - k) - L(q - k - 1) for k in range(10)], axis=1)
    feats_up["mx3"] = (r1[:, :3].max(1)) * 1e4; feats_up["mn3"] = (r1[:, :3].min(1)) * 1e4
    feats_up["mx10"] = (r1.max(1)) * 1e4; feats_up["mn10"] = (r1.min(1)) * 1e4
    feats_up["absr1"] = np.abs(r1[:, 0]) * 1e4
    if nonpit_diag:  # diagnostics only, NEVER used in a frozen rule
        for k in (1, 0, -1, -2):
            t1 = np.minimum(s - k, sp.s0 + len(lp) - 1)
            feats_up[f"diag_r_at{k}"] = np.where(s - k <= sp.s0 + len(lp) - 1, (L(t1) - L(t1 - 1)) * 1e4, np.nan)
    out = []
    for is_up in (True, False):
        sg = 1.0 if is_up else -1.0
        d = dict(base)
        d["is_up"] = np.full(len(rel), is_up)
        for k, v in feats_up.items():
            if k in ("absr1",):
                d[k] = v.astype(np.float32)
            elif k in ("mx3", "mn3", "mx10", "mn10"):
                continue
            else:
                d[k] = (sg * v).astype(np.float32)
        d["mxf3"] = (feats_up["mx3"] if is_up else -feats_up["mn3"]).astype(np.float32)   # biggest favourable 1-s move
        d["mxa3"] = (-feats_up["mn3"] if is_up else feats_up["mx3"]).astype(np.float32)   # biggest adverse 1-s move
        d["mxf10"] = (feats_up["mx10"] if is_up else -feats_up["mn10"]).astype(np.float32)
        d["mxa10"] = (-feats_up["mn10"] if is_up else feats_up["mx10"]).astype(np.float32)
        d["fv"] = ndtr(d["z"]).astype(np.float32)
        out.append(pd.DataFrame(d))
    cells = pd.concat(out, ignore_index=True)
    cells["cid"] = win.cid.to_numpy()[cells.wi.to_numpy()]
    cells["start_ts"] = win.start_ts.to_numpy()[cells.wi.to_numpy()]
    # labels
    f = fills[fills.cid.isin(set(win.cid))]
    key_c = pd.MultiIndex.from_arrays([cells.cid, cells.is_up, cells.rel.astype(np.int64)])
    for name, sel in [("y", slice(None)), ("yT", f.role == "T"), ("yM", f.role == "M"), ("yGF", f.wallet == "GF"), ("yXM", f.wallet == "XM"), ("yDS", f.wallet == "DS")]:
        g = f[sel] if not isinstance(sel, slice) else f
        g = g[(g.rel >= 0) & (g.rel < rel_max)]
        k = pd.MultiIndex.from_arrays([g.cid, g.is_up, g.rel.astype(np.int64)]).unique()
        cells[name] = key_c.isin(k).astype(np.int8)
    return cells


FEATS = ["rel", "tau", "sig", "z", "fv"] + [f"r{h}" for h in RETS] + [f"rn{h}" for h in RETS] + ["absr1", "mxf3", "mxa3", "mxf10", "mxa10"]
