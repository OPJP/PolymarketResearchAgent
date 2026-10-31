"""Live lab part h (I3 horse race, quote level): near-touch 500/100 adds vs a TWAP-60 digital fair from (a) Binance
USD-M futures bookTicker mid with the futures strike, (b) Polymarket RTDS Chainlink 1-s price with strike = the
Chainlink TWAP-60 at the window start (= priceToBeat), at lags 0 / 2 s (RTDS arrives ~1.8 s late). Also the
settlement check: RTDS crypto_prices_twap_sixty at the window end vs Gamma finalPrice."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live5, live5b  # noqa
from rawread import iter_dm  # noqa

def rtds(a, b):
    tw, cl = {}, {}
    for r in iter_dm("dm_rtds", a - 600, b):
        j = json.loads(r["m"]); d = j.get("payload", {}).get("data", [])
        tgt = tw if r["q"] == "crypto_prices_twap_sixty" else cl
        for x in d:
            tgt[int(x["timestamp"])] = float(x["value"])
    return tw, cl

def main(a, b):
    ev, tr, bk = live5.load_clob(a, b)
    refs = live5.load_ref(a, b)
    tw, cl = rtds(a, b)
    ev = ev.sort_values("s", kind="stable").reset_index(drop=True)
    ev["bb_prev"] = ev.groupby("w").bb.shift(1); ev["ba_prev"] = ev.groupby("w").ba.shift(1)
    e = ev[((np.abs(ev.d - 500) < 0.01) | (np.abs(ev.d - 100) < 0.01))].copy()
    e["tok_up"] = e.side == 1
    e["q"] = np.where(e.tok_up, e.p, 1 - e.p).round(3)
    e["tick"] = ((np.where(e.tok_up, e.bb_prev, 1 - e.ba_prev) - e.q) / 0.01).round(0)
    e = e[e.tick.between(-1, 2)]
    e["start"] = e.w.str.extract(r"-(\d{9,})$")[0].astype(np.int64)
    e["end"] = e.start + np.where(e.w.str.contains("-15m-"), 900, 300)
    e = e[(e.s / 1000 >= e.start + 5) & (e.s / 1000 < e.end - 5)]
    clr = pd.DataFrame(sorted(cl.items()), columns=["s", "px"])
    out = {"near_adds": int(len(e)), "chainlink_secs": len(cl), "twap_secs": len(tw)}
    fits = {}
    for name, ref, strike_mode in (("futures", refs["bn_fut_bt"], "feed"), ("chainlink", clr, "twap")):
        sec, v = live5b.sec_series(ref); rms, rpx = ref.s.to_numpy(), ref.px.to_numpy().astype(float)
        for L in (0, 2000):
            for k in (1.0, 1.4):
                fs = []
                for (w, st_, en_), g in e.groupby(["w", "start", "end"]):
                    if st_ - 60 < sec[0] or (strike_mode == "twap" and st_ * 1000 not in tw):
                        continue
                    fu = live5b.fair_token(rms, rpx, sec, v, st_, en_, g.s.to_numpy() - L, k_vol=k)
                    if strike_mode == "twap":  # re-centre on the true strike (priceToBeat = TWAP-60 at start)
                        a0, a1 = np.searchsorted(sec, st_ - 60), np.searchsorted(sec, st_)
                        s_feed = v[a0:a1].mean()
                        # shift the digital by the strike difference: recompute with the true strike via z shift
                        fu = live5b.fair_token(rms, rpx - (tw[st_ * 1000] - s_feed), sec, v - (tw[st_ * 1000] - s_feed), st_, en_, g.s.to_numpy() - L, k_vol=k)
                    fs.append(pd.Series(np.where(g.tok_up, fu, 1 - fu), index=g.index))
                if not fs: continue
                f = pd.concat(fs); q = e.q.reindex(f.index); ok = f.notna() & (f > 0.05) & (f < 0.95); r = (q - f)[ok]
                fits[f"{name}_L{L}_k{k}"] = {"n": int(ok.sum()), "median": round(float(r.median()), 4), "mad": round(float((r - r.median()).abs().median()), 4),
                                            "corr": round(float(np.corrcoef(q[ok], f[ok])[0, 1]), 4)}
    out["fits"] = fits
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / f"iter5_live_h_{a}_{b}.json").write_text(json.dumps(out, indent=1))

if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
