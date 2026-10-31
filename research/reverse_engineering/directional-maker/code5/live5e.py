"""Live lab part e: quote function fit of the 500/100 adds by distance from the touch (all adds in window):
q - fair (Binance futures TWAP-60 digital, vol scale k) by tick bucket, size, and time to expiry; price histogram."""
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
    e = ev[((np.abs(ev.d - 500) < 0.01) | (np.abs(ev.d - 100) < 0.01))].copy()
    e["tok_up"] = e.side == 1
    e["q"] = np.where(e.tok_up, e.p, 1 - e.p).round(3)
    e["tok_bb"] = np.where(e.tok_up, e.bb_prev, 1 - e.ba_prev)
    e["tok_ba"] = np.where(e.tok_up, e.ba_prev, 1 - e.bb_prev)
    e["tick"] = ((e.tok_bb - e.q) / 0.01).round(0)
    e["start"] = e.w.str.extract(r"-(\d{9,})$")[0].astype(np.int64)
    e["len"] = np.where(e.w.str.contains("-15m-"), 900, 300)
    e["end"] = e.start + e.len
    e = e[(e.s / 1000 >= e.start + 5) & (e.s / 1000 < e.end - 5)]
    ref = refs["bn_fut_bt"]; sec, v = live5b.sec_series(ref); rms, rpx = ref.s.to_numpy(), ref.px.to_numpy().astype(float)
    fs = []
    for (w, st_, en_), g in e.groupby(["w", "start", "end"]):
        if st_ - 60 < sec[0]: continue
        fu = live5b.fair_token(rms, rpx, sec, v, st_, en_, g.s.to_numpy(), k_vol=1.0)
        fs.append(pd.Series(np.where(g.tok_up, fu, 1 - fu), index=g.index))
    e["fair"] = pd.concat(fs).reindex(e.index)
    e = e[e.fair.notna()]
    e["res"] = e.q - e.fair
    e["mid"] = (e.tok_bb + e.tok_ba) / 2
    e["tb"] = pd.cut(e.tick, [-9, -1, 0, 1, 2, 5, 99], labels=["improve", "0", "1", "2", "3-5", "6+"])
    out = {"n": int(len(e))}
    for (tb, S), g in e.groupby(["tb", e.d.round(0)], observed=True):
        out[f"{tb}_{int(S)}"] = {"n": int(len(g)), "res_med": round(float(g.res.median()), 4), "res_mad": round(float((g.res - g.res.median()).abs().median()), 4),
                                  "corr_q_fair": round(float(np.corrcoef(g.q, g.fair)[0, 1]), 3) if len(g) > 10 else None,
                                  "corr_q_mid": round(float(np.corrcoef(g.q, g.mid)[0, 1]), 3) if len(g) > 10 else None,
                                  "q_quantiles": g.q.quantile([.1, .5, .9]).round(2).tolist(), "fair_minus_mid_med": round(float((g.fair - g.mid).median()), 4)}
    # the near-touch quote: q vs floor((fair - h)/0.01)*0.01 for a grid of h, by size
    near = e[e.tick.between(-1, 0)]
    grid = {}
    for S, g in near.groupby(near.d.round(0)):
        best = None
        for h in np.arange(0.0, 0.051, 0.005):
            for mode in ("floor", "round"):
                qq = np.floor((g.fair - h) / 0.01 + 1e-9) * 0.01 if mode == "floor" else np.round((g.fair - h) / 0.01) * 0.01
                w1 = float(np.mean(np.abs(qq - g.q) <= 0.0105)); ex = float(np.mean(np.abs(qq - g.q) < 0.0005))
                if best is None or w1 > best[2]:
                    best = (round(h, 3), mode, round(w1, 3), round(ex, 3))
        grid[int(S)] = best
    out["at_touch_quote_rule_best"] = grid
    # time to expiry dependence of the residual near the touch
    near = near.assign(left=(near.end - near.s / 1000))
    out["near_res_by_time_left"] = {str(k): round(float(v), 4) for k, v in near.groupby(pd.cut(near.left, [0, 30, 60, 120, 240, 900])).res.median().items()}
    out["near_res_by_fair"] = {str(k): round(float(v), 4) for k, v in near.groupby(pd.cut(near.fair, [0, .2, .4, .6, .8, 1])).res.median().items()}
    print(json.dumps(out, indent=1, default=str)[:7000])
    (HERE.parent / "results" / f"iter5_live_e_{a}_{b}.json").write_text(json.dumps(out, indent=1, default=str))

if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
