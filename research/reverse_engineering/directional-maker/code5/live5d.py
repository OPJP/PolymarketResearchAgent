"""Live lab part d: what triggers the near-touch 500/100 requotes? Inter-requote intervals per (market, side) (timer?),
requote direction vs futures aggTrade moves and vs the Polymarket touch, both-side synchrony.  python live5d.py a b"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live5  # noqa

def main(a, b):
    ev, tr, bk = live5.load_clob(a, b)
    refs = live5.load_ref(a, b)
    ev = ev.sort_values(["s"], kind="stable").reset_index(drop=True)
    ev["bb_prev"] = ev.groupby("w").bb.shift(1); ev["ba_prev"] = ev.groupby("w").ba.shift(1)
    e = ev[(np.abs(np.abs(ev.d) - 500) < 0.01) | (np.abs(np.abs(ev.d) - 100) < 0.01)].copy()
    e["tok_up"] = e.side == 1
    e["q"] = np.where(e.tok_up, e.p, 1 - e.p).round(3)
    e["tick"] = ((np.where(e.tok_up, e.bb_prev, 1 - e.ba_prev) - e.q) / 0.01).round(0)
    res = {"period": [a, b]}
    # all removals followed by an add (any price) of the same size, same market+side, within 100 ms = one requote
    rq = []
    for (w, side), g in e.groupby(["w", "side"]):
        s_, d_, p_, tk, bbp, bap = g.s.to_numpy(), g.d.to_numpy(), g.p.to_numpy(), g.tick.to_numpy(), g.bb_prev.to_numpy(), g.ba_prev.to_numpy()
        for i in np.where(d_ < 0)[0]:
            j = i + 1
            while j < len(s_) and s_[j] - s_[i] <= 100:
                if d_[j] > 0 and abs(d_[j] + d_[i]) < 0.01:
                    q0 = p_[i] if side == 1 else 1 - p_[i]; q1 = p_[j] if side == 1 else 1 - p_[j]
                    rq.append((s_[i], s_[j], w, side, round(q1 - q0, 3), side == 1, tk[j], abs(d_[j]))); break
                j += 1
    rq = pd.DataFrame(rq, columns=["s_rm", "s", "w", "side", "dq", "tok_up", "tick", "S"])
    near = rq[rq.tick.between(-1, 2)].copy()
    res["requotes"] = {"all": int(len(rq)), "near": int(len(near)), "near_same_price_share": float((near.dq == 0).mean()),
                       "near_dq_counts": near.dq.clip(-0.05, 0.05).value_counts().sort_index().to_dict(),
                       "cancel_to_add_ms_q": near.eval("s - s_rm").quantile([.1, .5, .9]).to_dict()}
    # inter-requote intervals per (market, side, size) near the touch (and all)
    for nm, R in (("near", near), ("all", rq)):
        iv = np.concatenate([np.diff(np.sort(g.s.to_numpy())) for _, g in R.groupby(["w", "side", "S"]) if len(g) > 2]) if len(R) else np.array([])
        h = pd.Series(iv[(iv > 0) & (iv < 3000)] // 50 * 50).value_counts().sort_index()
        res[f"interval_hist_{nm}_50ms"] = {int(k): int(v) for k, v in h.head(40).items()}
        res[f"interval_q_{nm}"] = pd.Series(iv).quantile([.1, .25, .5, .75, .9]).round(0).to_dict()
    # direction vs the futures aggTrade price and vs the Polymarket touch of its token before the requote
    fa = refs["bn_fut_tr"]; ms, px = fa.s.to_numpy(), fa.px.to_numpy()
    mv = near[near.dq != 0]
    out = {}
    for L0, L1 in ((0, 100), (0, 250), (50, 250), (0, 500), (250, 1000), (1000, 3000)):
        i1 = np.searchsorted(ms, mv.s.to_numpy() - L0, side="right") - 1; i0 = np.searchsorted(ms, mv.s.to_numpy() - L1, side="right") - 1
        d = px[np.clip(i1, 0, None)] - px[np.clip(i0, 0, None)]
        want = np.where(mv.tok_up, np.sign(d), -np.sign(d)); m = (i0 >= 0) & (d != 0)
        out[f"futtrade_{L0}-{L1}"] = (int(m.sum()), round(float((want[m] == np.sign(mv.dq.to_numpy())[m]).mean()), 3) if m.sum() else None)
    # polymarket touch: best bid of its token moved in the previous 250 ms?
    bkk = bk.sort_values("s")
    for L in (250, 1000):
        agree, n = 0, 0
        for (w,), g in mv.groupby(["w"]):
            bw = bkk[bkk.w == w]; evw = ev[ev.w == w]
            ts_all = np.r_[bw.s.to_numpy(), evw.s.to_numpy()]; o = np.argsort(ts_all, kind="stable")
            bb_all = np.r_[bw.bb.to_numpy(), evw.bb.to_numpy()][o]; ba_all = np.r_[bw.ba.to_numpy(), evw.ba.to_numpy()][o]; ts_all = ts_all[o]
            for r in g.itertuples(index=False):
                i1 = np.searchsorted(ts_all, r.s_rm, side="left") - 1; i0 = np.searchsorted(ts_all, r.s_rm - L, side="left") - 1
                if i0 < 0 or i1 < 0: continue
                if r.tok_up: d = bb_all[i1] - bb_all[i0]
                else: d = (1 - ba_all[i1]) - (1 - ba_all[i0])
                if d != 0 and np.isfinite(d):
                    n += 1; agree += int(np.sign(d) == np.sign(r.dq))
        out[f"own_touch_{L}"] = (n, round(agree / n, 3) if n else None)
    res["direction"] = out
    # both-side synchrony: share of near requotes on side s with a requote on the other side of the same market within 50 ms
    sync = 0
    for (w,), g in near.groupby(["w"]):
        s1 = np.sort(g[g.side == 1].s.to_numpy()); s0 = np.sort(g[g.side == 0].s.to_numpy())
        for x in s1:
            i = np.searchsorted(s0, x); c = [abs(s0[k] - x) for k in (i - 1, i) if 0 <= k < len(s0)]
            sync += int(bool(c) and min(c) <= 50)
    res["near_up_requotes_with_down_requote_within_50ms"] = round(sync / max((near.side == 1).sum(), 1), 3)
    print(json.dumps(res, indent=1, default=str)[:6000])
    (HERE.parent / "results" / f"iter5_live_d_{a}_{b}.json").write_text(json.dumps(res, indent=1, default=str))

if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
