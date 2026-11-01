"""Live lab part i: does the futures-fair quote predict WHEN the cluster's quote is at the touch?
1-s grid over BTC 5m windows of the live block, per side: observed state A = a fingerprint (500/100) order rests at the
token's best bid (raw-book reconstruction, an order lives from its add to an equal-size removal, at most 5 s);
F = a cluster maker fill on that side in [t, t+10). Score = futures TWAP-60 digital fair (t - 100 ms) minus the token's
best bid; baseline = bid hits on the side in the last 10 s (market activity). AUCs, development block only."""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live5, live5b  # noqa
C = HERE.parents[3] / ".cache/re/directional-maker"

def main(a, b):
    ev, tr, bk = live5.load_clob(a, b)
    refs = live5.load_ref(a, b)
    ref = refs["bn_fut_bt"]; sec, v = live5b.sec_series(ref); rms, rpx = ref.s.to_numpy(), ref.px.to_numpy().astype(float)
    acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))]).drop_duplicates(subset=["transactionHash", "asset", "w", "size", "price"])
    acts = acts[(acts.type == "TRADE") & (acts.side == "BUY")]
    amax = int(acts.timestamp.max())
    cdd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet"))])
    mtx = set(cdd[(cdd.role == "maker") & cdd.maker.str.lower().isin(live5.CL)].tx.str.lower())
    acts = acts[acts.transactionHash.str.lower().isin(mtx)]
    rows = []
    for w in sorted(ev.w.unique()):
        if not w.startswith("btc-updown-5m-"): continue
        st_ = int(w.split("-")[-1]); en_ = st_ + 300
        if st_ - 60 < sec[0] or en_ > min(b, amax): continue
        e = ev[ev.w == w].sort_values("s", kind="stable")
        bw = bk[bk.w == w]
        ts_all = np.r_[e.s.to_numpy(), bw.s.to_numpy()]; o = np.argsort(ts_all, kind="stable")
        bb_all = np.r_[e.bb.to_numpy(), bw.bb.to_numpy()][o]; ba_all = np.r_[e.ba.to_numpy(), bw.ba.to_numpy()][o]; ts_all = ts_all[o]
        grid = np.arange(st_ + 5, en_ - 5) * 1000
        i = np.searchsorted(ts_all, grid, side="right") - 1
        bb, ba = bb_all[np.clip(i, 0, None)], ba_all[np.clip(i, 0, None)]
        fu = live5b.fair_token(rms, rpx, sec, v, st_, en_, grid - 100, k_vol=1.4)
        f = e[(np.abs(np.abs(e.d) - 500) < 0.01) | (np.abs(np.abs(e.d) - 100) < 0.01)]
        lv = {k: (g.s.to_numpy(), g.d.to_numpy()) for k, g in f.groupby(["side", "p"])}
        # cluster fills on this window by token
        aw = acts[acts.slug == w]
        hits = tr[tr.w == w]
        hit_side = np.where(hits.ai == 0, np.where(hits.d == "BUY", 0, 1), np.where(hits.d == "BUY", 1, 0))  # 1 = Up bid hit
        for up in (True, False):
            tok_bb = bb if up else 1 - ba
            fair = fu if up else 1 - fu
            side, lvlp = (1, bb) if up else (0, ba)
            A = np.zeros(len(grid), dtype=bool)
            for k, (g, p) in enumerate(zip(grid, lvlp)):
                x = lv.get((side, round(float(p), 2)))
                if x is None: continue
                s_, d_ = x; j = np.searchsorted(s_, g, side="right"); live = 0
                for q in range(max(0, j - 30), j):
                    if d_[q] > 0 and g - s_[q] <= 5000: live += 1
                    elif d_[q] < 0 and live > 0: live -= 1
                A[k] = live > 0
            ft = np.sort(aw[aw.outcome == ("Up" if up else "Down")].timestamp.to_numpy()) * 1000
            F = (np.searchsorted(ft, grid + 10000) - np.searchsorted(ft, grid)) > 0
            hs = np.sort(hits.s.to_numpy()[hit_side == (1 if up else 0)])
            act10 = np.searchsorted(hs, grid) - np.searchsorted(hs, grid - 10000)
            rows.append(pd.DataFrame({"w": w, "up": up, "t": grid, "A": A, "F": F, "edge": fair - tok_bb, "fair": fair, "bb": tok_bb, "act10": act10}))
    d = pd.concat(rows).dropna(subset=["edge"])
    def auc(y, s):
        y = np.asarray(y); return round(float(roc_auc_score(y, s)), 4) if 0 < y.sum() < len(y) else None
    res = {"period": [a, b], "windows": int(d.w.nunique()), "seconds": int(len(d)), "A_rate": round(float(d.A.mean()), 4), "F_rate": round(float(d.F.mean()), 4),
           "auc_A_by_edge": auc(d.A, d.edge), "auc_A_by_activity": auc(d.A, d.act10), "auc_F_by_edge": auc(d.F, d.edge), "auc_F_by_activity": auc(d.F, d.act10),
           "auc_F_by_A": auc(d.F, d.A.astype(float)), "P_F_given_A": round(float(d[d.A].F.mean()), 4) if d.A.any() else None, "P_F_given_notA": round(float(d[~d.A].F.mean()), 4),
           "A_by_edge_bucket": {str(k): round(float(v), 3) for k, v in d.groupby(pd.cut(d.edge, [-1, -0.05, -0.02, 0, 0.02, 0.05, 1])).A.mean().items()}}
    print(json.dumps(res, indent=1))
    (HERE.parent / "results" / f"iter5_live_i_{a}_{b}.json").write_text(json.dumps(res, indent=1))

if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
