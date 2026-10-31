"""Live lab, iteration 5, part b: the quote function of the 500/100-share orders (the cluster's size class today).

For every exact-500 / exact-100 add in the raw book (dm_clob_raw), development block only:
  * the quoted token and price q (Up-book bid at p = BUY Up at p; Up-book ask at p = BUY Down at 1 - p);
  * distance from the touch before the add (ticks below the best bid of its token);
  * a TWAP-60 digital fair value of its token from each reference feed (server stamps) at lag L before the add
    (strike = the feed's mean over [start-60, start), vol = 1-s realised over the last 15 min x k);
  * residual q - fair, MAD and correlation by feed and lag (which feed and latency explain the quotes best);
  * requote direction: removal at p0 followed within 100 ms by an add of the same size at p1 on the same side of the
    same market: sign(p1 - p0) vs the sign of the feed's move over the previous L ms.
Fingerprint null: share of non-cluster trades with a +500 / +100 add at the hit level within 400 ms before.
    python live5b.py <start_ts> <end_ts>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live5  # noqa: E402


def sec_series(ref):
    """last price per second -> dict of arrays."""
    s = (ref.s.to_numpy() // 1000).astype(np.int64)
    px = ref.px.to_numpy().astype(float)
    last = pd.Series(px).groupby(s).last()
    sec = np.arange(last.index.min(), last.index.max() + 1)
    v = last.reindex(sec).ffill().to_numpy()
    return sec, v


def fair_token(ref_ms, ref_px, sec, v, start, end, t_ms, k_vol=1.0):
    """P(Up) at t_ms using the feed up to t_ms (TWAP-60 digital, as polyrea's fair_up_vectorized)."""
    t = t_ms / 1000.0
    i = np.searchsorted(ref_ms, t_ms, side="right") - 1
    st = np.where(i >= 0, ref_px[np.clip(i, 0, None)], np.nan)
    a0, a1 = np.searchsorted(sec, start - 60), np.searchsorted(sec, start)
    s0 = v[a0:a1].mean() if a1 > a0 else np.nan
    # vol: 1-s log returns over the 900 s before t (per sqrt s)
    j = np.searchsorted(sec, np.floor(t)).astype(np.int64)
    lr = np.diff(np.log(v))
    c1 = np.r_[0, np.cumsum(lr)]
    c2 = np.r_[0, np.cumsum(lr ** 2)]
    lo = np.clip(j - 900, 0, None)
    n = np.maximum(j - lo, 1)
    var = (c2[np.clip(j, 0, len(c2) - 1)] - c2[lo]) / n - ((c1[np.clip(j, 0, len(c1) - 1)] - c1[lo]) / n) ** 2
    sig = np.sqrt(np.maximum(var, 1e-12)) * k_vol
    twap_start = end - 60
    before = t < twap_start
    var_before = np.clip(twap_start - t, 0, None) + 20.0
    r = np.clip(end - t, 0, None)
    # inside the closing TWAP: known part from the 1-s series
    a_known = np.array([v[np.searchsorted(sec, twap_start):np.searchsorted(sec, min(tt, end))].mean()
                        if tt > twap_start and np.searchsorted(sec, min(tt, end)) > np.searchsorted(sec, twap_start) else np.nan for tt in np.atleast_1d(t)])
    a_known = np.where(np.isnan(a_known), st, a_known)
    mean_in = ((60 - r) * a_known + r * st) / 60
    sd_in = (r / 60) * np.sqrt(np.maximum(r, 1e-9) / 3.0)
    mean = np.where(before, st, mean_in)
    sd_units = np.where(before, np.sqrt(var_before), sd_in)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (mean - s0) / (st * sig * sd_units)
    return stats.norm.cdf(z)


def main(a, b):
    ev, tr, bk = live5.load_clob(a, b)
    refs = live5.load_ref(a, b)
    act, cd = live5.cluster_orders(a, b)
    res = {"period": [a, b]}
    # --- fingerprint null
    ctx = set(act.transactionHash.str.lower())
    t2 = tr[(tr.s >= a * 1000) & (tr.s < b * 1000)].copy()
    t2["side"] = np.where(t2.ai == 0, np.where(t2.d == "BUY", 0, 1), np.where(t2.d == "BUY", 1, 0))
    t2["lvl"] = np.where(t2.ai == 0, t2.p, 1 - t2.p).round(2)
    t2["clu"] = t2.h.isin(ctx)
    for S in (500.0, 100.0):
        e = ev[np.abs(ev.d - S) < 0.01]
        g = {k: x.s.to_numpy() for k, x in e.groupby(["w", "side", "p"])}
        hit = []
        for r in t2.itertuples(index=False):
            arr = g.get((r.w, r.side, r.lvl))
            if arr is None:
                hit.append(False)
                continue
            i = np.searchsorted(arr, r.s, side="right") - 1
            hit.append(bool(i >= 0 and r.s - arr[i] <= 400))
        t2[f"add{int(S)}"] = hit
        res[f"null_add{int(S)}_within_400ms"] = {"non_cluster_trades": float(t2.loc[~t2.clu, f"add{int(S)}"].mean()),
                                                  "cluster_trades": float(t2.loc[t2.clu, f"add{int(S)}"].mean()) if t2.clu.any() else None,
                                                  "n_cluster_trades": int(t2.clu.sum())}
    # --- the 500/100 adds: token, price, distance from the touch before the add
    ev = ev.sort_values(["s"], kind="stable").reset_index(drop=True)
    ev["bb_prev"] = ev.groupby("w").bb.shift(1)
    ev["ba_prev"] = ev.groupby("w").ba.shift(1)
    adds = ev[(np.abs(ev.d - 500) < 0.01) | (np.abs(ev.d - 100) < 0.01)].copy()
    adds["S"] = adds.d.round(0)
    adds["tok_up"] = adds.side == 1
    adds["q"] = np.where(adds.tok_up, adds.p, 1 - adds.p).round(3)
    # best bid of its own token before the add: Up bid = bb_prev; Down bid = 1 - Up ask
    adds["tok_bb_prev"] = np.where(adds.tok_up, adds.bb_prev, 1 - adds.ba_prev)
    adds["ticks_below_touch"] = ((adds.tok_bb_prev - adds.q) / 0.01).round(0)
    res["add_vs_touch"] = {str(int(S)): {str(k): float(v) for k, v in g.ticks_below_touch.clip(-3, 6).value_counts(normalize=True).sort_index().round(3).items()}
                           for S, g in adds.groupby("S")}
    # --- quote vs fair by feed and lag (in-window adds only)
    adds["start"] = adds.w.str.extract(r"-(\d{9,})$")[0].astype(np.int64)
    adds["len"] = np.where(adds.w.str.contains("-15m-"), 900, 300)
    adds["end"] = adds.start + adds.len
    inw = adds[(adds.s / 1000 >= adds.start + 5) & (adds.s / 1000 < adds.end - 5)].copy()
    out = {}
    for feed in ("bn_fut_bt", "bn_spot_tr", "coinbase", "okx_swap", "bybit_perp", "hyperliquid"):
        ref = refs[feed]
        if len(ref) < 100:
            continue
        sec, v = sec_series(ref)
        rms, rpx = ref.s.to_numpy(), ref.px.to_numpy().astype(float)
        out[feed] = {}
        for L in (0, 100, 250, 500, 1000, 2000, 4000):
            fs = []
            for (w, st_, en_), g in inw.groupby(["w", "start", "end"]):
                if st_ - 60 < sec[0] + 900 * 0:  # need the strike window inside the recording
                    if st_ - 60 < sec[0]:
                        fs.append(pd.Series(np.nan, index=g.index))
                        continue
                fu = fair_token(rms, rpx, sec, v, st_, en_, g.s.to_numpy() - L, k_vol=1.4)
                fs.append(pd.Series(np.where(g.tok_up, fu, 1 - fu), index=g.index))
            f = pd.concat(fs).reindex(inw.index)
            ok = f.notna() & (f > 0.03) & (f < 0.97)
            resid = (inw.q - f)[ok]
            out[feed][L] = {"n": int(ok.sum()), "mad": round(float(np.median(np.abs(resid - np.median(resid)))), 4) if ok.sum() else None,
                            "median_resid": round(float(np.median(resid)), 4) if ok.sum() else None,
                            "corr": round(float(np.corrcoef(inw.q[ok], f[ok])[0, 1]), 4) if ok.sum() > 10 else None}
    res["quote_vs_fair"] = out
    # --- requote direction vs feed move
    rq = []
    e = ev[(np.abs(np.abs(ev.d) - 500) < 0.01) | (np.abs(np.abs(ev.d) - 100) < 0.01)].sort_values("s", kind="stable")
    for (w, side), g in e.groupby(["w", "side"]):
        s_, d_, p_ = g.s.to_numpy(), g.d.to_numpy(), g.p.to_numpy()
        for i in np.where(d_ < 0)[0]:
            j = i + 1
            while j < len(s_) and s_[j] - s_[i] <= 100:
                if d_[j] > 0 and abs(d_[j] + d_[i]) < 0.01 and abs(p_[j] - p_[i]) > 0.005:
                    q0 = p_[i] if side == 1 else 1 - p_[i]
                    q1 = p_[j] if side == 1 else 1 - p_[j]
                    rq.append((s_[j], w, side, np.sign(q1 - q0), side == 1))
                    break
                j += 1
    rq = pd.DataFrame(rq, columns=["s", "w", "side", "dir", "tok_up"])
    res["requotes_with_price_change"] = int(len(rq))
    hr = {}
    for feed in ("bn_fut_bt", "bn_spot_tr", "coinbase", "okx_swap", "bybit_perp", "hyperliquid"):
        ref = refs[feed]
        if len(ref) < 100 or len(rq) < 10:
            continue
        rms, rpx = ref.s.to_numpy(), ref.px.to_numpy().astype(float)
        hr[feed] = {}
        for L0, L1 in ((0, 100), (0, 250), (0, 500), (0, 1000), (100, 500), (250, 1000), (500, 2000), (1000, 3000), (-200, 0)):
            i1 = np.searchsorted(rms, rq.s.to_numpy() - L0, side="right") - 1
            i0 = np.searchsorted(rms, rq.s.to_numpy() - L1, side="right") - 1
            ok = (i0 >= 0) & (i1 >= 0)
            mv = np.where(ok, rpx[np.clip(i1, 0, None)] - rpx[np.clip(i0, 0, None)], 0)
            # a rise of BTC raises the Up quote and lowers the Down quote
            want = np.where(rq.tok_up, np.sign(mv), -np.sign(mv))
            m = ok & (mv != 0)
            hr[feed][f"{L0}-{L1}"] = {"n_moved": int(m.sum()), "agree": round(float((want[m] == rq.dir.to_numpy()[m]).mean()), 3) if m.sum() else None}
    res["requote_direction_vs_feed"] = hr
    print(json.dumps(res, indent=1, default=str)[:7000])
    (HERE.parent / "results" / f"iter5_live_b_{a}_{b}.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
