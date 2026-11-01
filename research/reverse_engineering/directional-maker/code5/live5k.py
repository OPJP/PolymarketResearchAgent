"""Live lab part k: the three-wallet signature. 500-share adds come in bursts of <= 3 within 20 ms on the same side of a
market (exactly 3 in 27%, >= 4 in 0.6%), 88% at one price: the three copies of the engine posting the same quote.
Bursts of 2-3 = the cluster's quote events (attribution without the shared size class). Tests on them:
 (a) quote level vs futures TWAP-60 fair and distance from the touch; (b) burst-to-burst price change direction vs the
 futures mid move; (c) state "a cluster burst quote rests at the token's best bid" (live until the next burst on that side)
 vs fills in the next 10 s, and whether the futures edge predicts that state."""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live5, live5b  # noqa
C = HERE.parents[3] / ".cache/re/directional-maker"

def bursts(ev):
    e = ev[np.abs(ev.d - 500) < 0.01].sort_values("s", kind="stable")
    out = []
    for (w, side), g in e.groupby(["w", "side"]):
        s_, p_, bb, ba = g.s.to_numpy(), g.p.to_numpy(), g.bb_prev.to_numpy(), g.ba_prev.to_numpy()
        i = 0
        while i < len(s_):
            j = i
            while j + 1 < len(s_) and s_[j + 1] - s_[i] <= 20: j += 1
            n = j - i + 1
            if 2 <= n <= 3:
                p = float(np.median(p_[i:j + 1]))
                out.append((s_[i], w, side, round(p, 2), n, bb[i], ba[i]))
            i = j + 1
    d = pd.DataFrame(out, columns=["s", "w", "side", "p", "n", "bb_prev", "ba_prev"])
    d["tok_up"] = d.side == 1
    d["q"] = np.where(d.tok_up, d.p, 1 - d.p).round(2)
    d["tok_bb"] = np.where(d.tok_up, d.bb_prev, 1 - d.ba_prev)
    d["tick"] = ((d.tok_bb - d.q) / 0.01).round(0)
    d["start"] = d.w.str.extract(r"-(\d{9,})$")[0].astype(np.int64)
    d["end"] = d.start + np.where(d.w.str.contains("-15m-"), 900, 300)
    return d

def main(a, b):
    ev, tr, bk = live5.load_clob(a, b)
    ev = ev.sort_values("s", kind="stable").reset_index(drop=True)
    ev["bb_prev"] = ev.groupby("w").bb.shift(1); ev["ba_prev"] = ev.groupby("w").ba.shift(1)
    refs = live5.load_ref(a, b)
    ref = refs["bn_fut_bt"]; sec, v = live5b.sec_series(ref); rms, rpx = ref.s.to_numpy(), ref.px.to_numpy().astype(float)
    d = bursts(ev)
    d = d[(d.s / 1000 >= d.start + 3) & (d.s / 1000 < d.end - 3)]
    res = {"period": [a, b], "bursts": int(len(d)), "by_n": d.n.value_counts().to_dict(), "by_market": d.w.str.slice(0, 14).value_counts().to_dict(),
           "tick_from_touch": {str(int(k)): round(float(x), 3) for k, x in d.tick.clip(-2, 8).value_counts(normalize=True).sort_index().items()}}
    fs = []
    for (w, st_, en_), g in d.groupby(["w", "start", "end"]):
        if st_ - 60 < sec[0]: continue
        for k in (1.0, 1.4):
            fu = live5b.fair_token(rms, rpx, sec, v, st_, en_, g.s.to_numpy() - 100, k_vol=k)
            fs.append(pd.DataFrame({"k": k, "fair": np.where(g.tok_up, fu, 1 - fu)}, index=g.index))
    F = pd.concat(fs)
    fit = {}
    for k in (1.0, 1.4):
        f = F[F.k == k].fair; q = d.q.reindex(f.index); ok = f.notna() & (f > 0.05) & (f < 0.95); r = (q - f)[ok]
        fit[str(k)] = {"n": int(ok.sum()), "median": round(float(r.median()), 4), "mad": round(float((r - r.median()).abs().median()), 4),
                       "corr": round(float(np.corrcoef(q[ok], f[ok])[0, 1]), 4)}
        for h in (0.02, 0.03, 0.04, 0.05):
            qq = np.floor((f[ok] - h) / 0.01 + 1e-9) * 0.01
            fit[str(k)][f"floor_h{h}_within_tick"] = round(float(np.mean(np.abs(qq - q[ok]) <= 0.0105)), 3)
    res["quote_vs_futures_fair"] = fit
    # (b) direction of burst-to-burst price changes vs futures mid
    d = d.sort_values("s")
    d["dq"] = d.groupby(["w", "side"]).q.diff()
    d["gap"] = d.groupby(["w", "side"]).s.diff()
    ch = d[(d.dq.abs() > 0.005) & (d.gap <= 3000)]
    dirs = {}
    for L0, L1 in ((0, 100), (0, 250), (50, 300), (0, 500), (500, 2000)):
        i1 = np.searchsorted(rms, ch.s.to_numpy() - L0, side="right") - 1; i0 = np.searchsorted(rms, ch.s.to_numpy() - L1, side="right") - 1
        mv = rpx[np.clip(i1, 0, None)] - rpx[np.clip(i0, 0, None)]; m = (i0 >= 0) & (mv != 0)
        want = np.where(ch.tok_up, np.sign(mv), -np.sign(mv))
        dirs[f"{L0}-{L1}"] = (int(m.sum()), int(len(ch)), round(float((want[m] == np.sign(ch.dq.to_numpy())[m]).mean()), 3) if m.sum() else None)
    res["burst_requote_direction_vs_futures_mid"] = dirs
    res["burst_interval_same_side_ms_q"] = d.gap.quantile([.1, .25, .5, .75, .9]).round(0).to_dict()
    res["burst_same_price_as_previous"] = round(float((d.dq.abs() < 0.005).mean()), 3)
    # (c) state: latest burst quote on the side is at the token's best bid (now) -> fill in the next 10 s?
    acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))]).drop_duplicates(subset=["transactionHash", "asset", "w", "size", "price"])
    acts = acts[(acts.type == "TRADE") & (acts.side == "BUY")]
    amax = int(acts.timestamp.max())
    rows = []
    for w in sorted(d.w.unique()):
        st_ = int(w.split("-")[-1]); en_ = st_ + (900 if "-15m-" in w else 300)
        if st_ - 60 < sec[0] or en_ > min(b, amax) or "-15m-" in w: continue
        e = ev[ev.w == w]; bw = bk[bk.w == w]
        ts_all = np.r_[e.s.to_numpy(), bw.s.to_numpy()]; o = np.argsort(ts_all, kind="stable")
        bb_all = np.r_[e.bb.to_numpy(), bw.bb.to_numpy()][o]; ba_all = np.r_[e.ba.to_numpy(), bw.ba.to_numpy()][o]; ts_all = ts_all[o]
        grid = np.arange(st_ + 5, en_ - 5) * 1000
        i = np.searchsorted(ts_all, grid, side="right") - 1
        bb, ba = bb_all[np.clip(i, 0, None)], ba_all[np.clip(i, 0, None)]
        fu = live5b.fair_token(rms, rpx, sec, v, st_, en_, grid - 100, k_vol=1.4)
        aw = acts[acts.slug == w]
        for up in (True, False):
            g = d[(d.w == w) & (d.tok_up == up)]
            gs, gq = g.s.to_numpy(), g.q.to_numpy()
            j = np.searchsorted(gs, grid, side="right") - 1
            age = np.where(j >= 0, grid - gs[np.clip(j, 0, None)], 1e9)
            lastq = np.where(j >= 0, gq[np.clip(j, 0, None)], np.nan)
            tok_bb = bb if up else 1 - ba
            A = (np.abs(lastq - tok_bb) < 0.005) & (age <= 3000)
            ft = np.sort(aw[aw.outcome == ("Up" if up else "Down")].timestamp.to_numpy()) * 1000
            Fl = (np.searchsorted(ft, grid + 10000) - np.searchsorted(ft, grid)) > 0
            fair = fu if up else 1 - fu
            rows.append(pd.DataFrame({"A": A, "F": Fl, "edge": fair - tok_bb, "gapq": lastq - tok_bb}))
    if rows:
        z = pd.concat(rows).dropna()
        auc = lambda y, s: round(float(roc_auc_score(y, s)), 4) if 0 < np.asarray(y).sum() < len(y) else None
        res["state_test"] = {"seconds": int(len(z)), "A_rate": round(float(z.A.mean()), 4), "P_F_given_A": round(float(z[z.A].F.mean()), 4) if z.A.any() else None,
                             "P_F_given_notA": round(float(z[~z.A].F.mean()), 4), "auc_F_by_A": auc(z.F, z.A.astype(float)),
                             "auc_F_by_cluster_quote_minus_bb": auc(z.F, z.gapq), "auc_A_by_futures_edge": auc(z.A, z.edge), "auc_F_by_futures_edge": auc(z.F, z.edge)}
    print(json.dumps(res, indent=1, default=str))
    (HERE.parent / "results" / f"iter5_live_k_{a}_{b}.json").write_text(json.dumps(res, indent=1, default=str))

if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
