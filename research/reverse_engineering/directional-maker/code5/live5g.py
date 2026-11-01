"""Live lab part g: requote trigger from the full Binance USD-M futures bookTicker (every size change, from 14:22:43 UTC):
microprice = (bid*askQty + ask*bidQty)/(bidQty+askQty). For near-touch 500/100 requotes (price changed), the agreement of
the requote direction with the microprice / mid move over the previous window, and the requote rate after microprice moves
of various sizes vs random times."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live5  # noqa
from rawread import iter_dm  # noqa

def main(a, b):
    ev, tr, bk = live5.load_clob(a, b)
    rows = [(r["r"][2], r["r"][3], r["r"][4], r["r"][5], r["r"][6]) for r in iter_dm("dm_bnf", a, b) if r["r"][0] == "b"]
    fb = pd.DataFrame(rows, columns=["s", "b", "B", "a", "A"]).sort_values("s")
    fb["mid"] = (fb.b + fb.a) / 2
    fb["micro"] = (fb.b * fb.A + fb.a * fb.B) / (fb.A + fb.B)
    ev = ev.sort_values("s", kind="stable").reset_index(drop=True)
    ev["bb_prev"] = ev.groupby("w").bb.shift(1); ev["ba_prev"] = ev.groupby("w").ba.shift(1)
    e = ev[(np.abs(np.abs(ev.d) - 500) < 0.01) | (np.abs(np.abs(ev.d) - 100) < 0.01)].copy()
    e["q"] = np.where(e.side == 1, e.p, 1 - e.p)
    e["tick"] = ((np.where(e.side == 1, e.bb_prev, 1 - e.ba_prev) - e.q) / 0.01).round(0)
    rq = []
    for (w, side), g in e.groupby(["w", "side"]):
        s_, d_, p_, tk = g.s.to_numpy(), g.d.to_numpy(), g.p.to_numpy(), g.tick.to_numpy()
        for i in np.where(d_ < 0)[0]:
            j = i + 1
            while j < len(s_) and s_[j] - s_[i] <= 100:
                if d_[j] > 0 and abs(d_[j] + d_[i]) < 0.01:
                    q0 = p_[i] if side == 1 else 1 - p_[i]; q1 = p_[j] if side == 1 else 1 - p_[j]
                    rq.append((s_[i], w, side, np.sign(round(q1 - q0, 3)), tk[j])); break
                j += 1
    rq = pd.DataFrame(rq, columns=["s", "w", "side", "dir", "tick"])
    rq = rq[rq.s >= fb.s.min() + 3000]
    res = {"period": [a, b], "futures_book_updates": int(len(fb)), "requotes": int(len(rq)), "requotes_price_changed": int((rq.dir != 0).sum())}
    ms = fb.s.to_numpy()
    for col in ("mid", "micro"):
        px = fb[col].to_numpy()
        out = {}
        for nm, R in (("near", rq[(rq.dir != 0) & rq.tick.between(-1, 2)]), ("all", rq[rq.dir != 0])):
            for L0, L1 in ((0, 50), (0, 100), (0, 250), (50, 250), (0, 500), (250, 1000), (-250, 0)):
                i1 = np.searchsorted(ms, R.s.to_numpy() - L0, side="right") - 1; i0 = np.searchsorted(ms, R.s.to_numpy() - L1, side="right") - 1
                d = px[np.clip(i1, 0, None)] - px[np.clip(i0, 0, None)]
                want = np.where(R.side == 1, np.sign(d), -np.sign(d)); m = (i0 >= 0) & (np.abs(d) > 1e-9)
                out[f"{nm}_{L0}-{L1}"] = (int(m.sum()), int(len(R)), round(float((want[m] == R.dir.to_numpy()[m]).mean()), 3) if m.sum() else None)
        res[f"direction_vs_{col}"] = out
    # requote (any, incl. same price) rate in the 250 ms after a microprice move of >= x USD (over 100 ms) vs base
    t0, t1 = int(rq.s.min()), int(rq.s.max())
    grid = np.arange(t0, t1, 50)
    i1 = np.searchsorted(ms, grid, side="right") - 1; i0 = np.searchsorted(ms, grid - 100, side="right") - 1
    mv = np.abs(fb.micro.to_numpy()[np.clip(i1, 0, None)] - fb.micro.to_numpy()[np.clip(i0, 0, None)])
    rs = np.sort(rq.s.to_numpy())
    cnt = np.searchsorted(rs, grid + 250) - np.searchsorted(rs, grid)
    base = cnt.mean()
    res["requote_rate_ratio_after_micro_move"] = {str(x): round(float(cnt[mv >= x].mean() / base), 3) if (mv >= x).sum() > 20 else None for x in (0.05, 0.25, 1, 2, 5)}
    res["share_of_grid_with_move"] = {str(x): round(float((mv >= x).mean()), 4) for x in (0.05, 0.25, 1, 2, 5)}
    print(json.dumps(res, indent=1, default=str))
    (HERE.parent / "results" / f"iter5_live_g_{a}_{b}.json").write_text(json.dumps(res, indent=1, default=str))

if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
