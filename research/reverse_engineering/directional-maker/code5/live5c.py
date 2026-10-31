"""Live lab part c: near-touch 500/100 quotes only (0-2 ticks below the token's best bid before the add, or improving it):
quote vs a TWAP-60 digital fair of each feed and lag, requote direction vs feed moves, lifetimes, and the cluster's own
filled orders (calldata) as the reference subset.   python live5c.py <a> <b>"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live5, live5b  # noqa

def main(a, b):
    ev, tr, bk = live5.load_clob(a, b)
    refs = live5.load_ref(a, b)
    ev = ev.sort_values(["s"], kind="stable").reset_index(drop=True)
    ev["bb_prev"] = ev.groupby("w").bb.shift(1); ev["ba_prev"] = ev.groupby("w").ba.shift(1)
    e = ev[(np.abs(np.abs(ev.d) - 500) < 0.01) | (np.abs(np.abs(ev.d) - 100) < 0.01)].copy()
    e["tok_up"] = e.side == 1
    e["q"] = np.where(e.tok_up, e.p, 1 - e.p).round(3)
    e["tok_bb_prev"] = np.where(e.tok_up, e.bb_prev, 1 - e.ba_prev)
    e["tick"] = ((e.tok_bb_prev - e.q) / 0.01).round(0)
    e["start"] = e.w.str.extract(r"-(\d{9,})$")[0].astype(np.int64)
    e["end"] = e.start + np.where(e.w.str.contains("-15m-"), 900, 300)
    adds = e[(e.d > 0) & e.tick.between(-1, 2)]
    adds = adds[(adds.s / 1000 >= adds.start + 5) & (adds.s / 1000 < adds.end - 5)]
    res = {"period": [a, b], "near_touch_adds": int(len(adds)), "by_tick": adds.tick.value_counts().sort_index().to_dict(),
           "by_size": adds.d.round(0).value_counts().to_dict(), "by_market": adds.w.str.slice(0, 15).value_counts().to_dict()}
    out = {}
    for feed in ("bn_fut_bt", "bn_spot_tr", "coinbase", "bybit_perp", "okx_swap", "hyperliquid"):
        ref = refs[feed]
        if len(ref) < 100: continue
        sec, v = live5b.sec_series(ref)
        rms, rpx = ref.s.to_numpy(), ref.px.to_numpy().astype(float)
        out[feed] = {}
        for k in (1.0, 1.4):
          for L in (0, 100, 250, 500, 1000, 2000):
            fs = []
            for (w, st_, en_), g in adds.groupby(["w", "start", "end"]):
                if st_ - 60 < sec[0]:
                    continue
                fu = live5b.fair_token(rms, rpx, sec, v, st_, en_, g.s.to_numpy() - L, k_vol=k)
                fs.append(pd.Series(np.where(g.tok_up, fu, 1 - fu), index=g.index))
            if not fs: continue
            f = pd.concat(fs)
            q = adds.q.reindex(f.index)
            ok = f.notna() & (f > 0.05) & (f < 0.95)
            r = (q - f)[ok]
            out[feed][f"k{k}_L{L}"] = {"n": int(ok.sum()), "median": round(float(r.median()), 4), "mad": round(float((r - r.median()).abs().median()), 4),
                                       "corr": round(float(np.corrcoef(q[ok], f[ok])[0, 1]), 4)}
    res["quote_vs_fair_near_touch"] = out
    # requotes near the touch: removal then add (same size, same side, same market) within 100 ms, price changed
    rq = []
    for (w, side), g in e.groupby(["w", "side"]):
        s_, d_, p_, tk = g.s.to_numpy(), g.d.to_numpy(), g.p.to_numpy(), g.tick.to_numpy()
        for i in np.where(d_ < 0)[0]:
            j = i + 1
            while j < len(s_) and s_[j] - s_[i] <= 100:
                if d_[j] > 0 and abs(d_[j] + d_[i]) < 0.01 and abs(p_[j] - p_[i]) > 0.005:
                    q0 = p_[i] if side == 1 else 1 - p_[i]; q1 = p_[j] if side == 1 else 1 - p_[j]
                    rq.append((s_[j], w, side, np.sign(q1 - q0), side == 1, tk[j], s_[j] - s_[i])); break
                j += 1
    rq = pd.DataFrame(rq, columns=["s", "w", "side", "dir", "tok_up", "tick", "gap"])
    near = rq[rq.tick.between(-1, 2)]
    res["requotes"] = {"all": int(len(rq)), "near_touch": int(len(near))}
    hr = {}
    for feed in ("bn_fut_bt", "bybit_perp", "okx_swap", "coinbase", "bn_spot_tr", "hyperliquid"):
        ref = refs[feed]; rms, rpx = ref.s.to_numpy(), ref.px.to_numpy().astype(float)
        hr[feed] = {}
        for nm, R in (("near", near), ("deep", rq[rq.tick >= 6])):
            for L0, L1 in ((0, 50), (0, 100), (0, 250), (50, 250), (100, 300), (0, 500), (250, 1000), (1000, 3000), (-250, 0)):
                i1 = np.searchsorted(rms, R.s.to_numpy() - L0, side="right") - 1
                i0 = np.searchsorted(rms, R.s.to_numpy() - L1, side="right") - 1
                ok = (i0 >= 0) & (i1 >= 0)
                mv = np.where(ok, rpx[np.clip(i1, 0, None)] - rpx[np.clip(i0, 0, None)], 0)
                want = np.where(R.tok_up, np.sign(mv), -np.sign(mv)); m = ok & (mv != 0)
                hr[feed][f"{nm}_{L0}-{L1}"] = (int(m.sum()), round(float((want[m] == R.dir.to_numpy()[m]).mean()), 3) if m.sum() else None)
    res["requote_direction"] = hr
    # share of requotes with NO futures move in the previous 500 ms (timer-driven requotes?)
    ref = refs["bn_fut_bt"]; rms, rpx = ref.s.to_numpy(), ref.px.to_numpy().astype(float)
    i1 = np.searchsorted(rms, near.s.to_numpy(), side="right") - 1; i0 = np.searchsorted(rms, near.s.to_numpy() - 500, side="right") - 1
    res["near_requotes_without_futures_move_500ms"] = float(np.mean(rpx[np.clip(i1,0,None)] == rpx[np.clip(i0,0,None)])) if len(near) else None
    # time from the latest futures mid change to the requote (near touch)
    last_chg = rms[np.clip(i1, 0, None)]
    res["near_requote_ms_after_last_futures_change_q"] = pd.Series(near.s.to_numpy() - last_chg).quantile([.1, .25, .5, .75, .9]).round(0).to_dict() if len(near) else None
    # same for random times (null)
    rt = np.random.default_rng(1).integers(int(near.s.min()), int(near.s.max()), 5000) if len(near) else np.array([])
    j1 = np.searchsorted(rms, rt, side="right") - 1
    res["random_ms_after_last_futures_change_q"] = pd.Series(rt - rms[np.clip(j1, 0, None)]).quantile([.1, .25, .5, .75, .9]).round(0).to_dict() if len(rt) else None
    print(json.dumps(res, indent=1, default=str)[:9000])
    (HERE.parent / "results" / f"iter5_live_c_{a}_{b}.json").write_text(json.dumps(res, indent=1, default=str))

if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
