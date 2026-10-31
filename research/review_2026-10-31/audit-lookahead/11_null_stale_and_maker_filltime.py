"""(1) Of the shifted-null scores that ARE finite, how many use a strike S0 or S_t from a spot
record that is hours stale (shift landed in a gap between loaded blocks)?
(2) Maker match test scores passive fills at FILL time: edge of all passive buys vs. the spot lag
used, showing the fill-time score is dominated by spot moves after the quote was posted."""
import pickle
from pathlib import Path
import numpy as np
from polyrea.analysis.updown import SpotIndex, score_prints, maker_buy_prints

D = pickle.load(open(Path(__file__).parent / "data" / "btc5m.pkl", "rb"))
spot = SpotIndex(D["spot_ts"]); test = D["test"]; p = test["prints"]
lat = 20
rng = np.random.default_rng(7)
stale_s0, stale_st, fin = [], [], []
for _ in range(50):
    sh = int(rng.integers(3600, 6 * 3600)) * int(rng.choice([-1, 1]))
    s = score_prints(p, spot, lat, shift=sh); ok = np.isfinite(s)
    st = p["start_ts"].to_numpy() + sh; td = p["ts"].to_numpy() - lat + sh
    win = ok & (td >= st)  # in-window prints (pre-window prints get 0.5 regardless)
    i0 = spot._idx_available(st[win]); it = spot._idx_available(td[win])
    stale_s0.append(np.mean(st[win] - spot.av[np.clip(i0, 0, None)] > 5)); stale_st.append(np.mean(td[win] - spot.av[np.clip(it, 0, None)] > 5)); fin.append(ok.mean())
print(f"shift null (50 shifts, lat {lat}): finite share median {np.median(fin):.3f}; among finite in-window scores, strike S0 from a record >5 s stale: median {np.median(stale_s0):.3f} (max {np.max(stale_s0):.3f}); S_t stale: median {np.median(stale_st):.3f}")
s_real = score_prints(p, spot, lat); td = p["ts"].to_numpy() - lat; st = p["start_ts"].to_numpy(); win = td >= st
print(f"real scores: S0 stale >5 s share {np.mean(st[win] - spot.av[np.clip(spot._idx_available(st[win]),0,None)] > 5):.4f}")

m = maker_buy_prints(test["full_tapes"], test["tapes"], test["windows"])
inwin = (m["ts"] - 60 >= m["start_ts"]) & (m["ts"] < m["end_ts"])
mm = m[inwin]
print(f"passive buys in-window (TEST): {len(mm)}")
for L in (-5, 0, 2, 5, 10, 30, 60):
    s = score_prints(mm, spot, L)
    print(f"  edge of passive fills using spot available at fill_ts - {L:>3}s: mean {np.nanmean(s):+.4f}  share>0 {np.nanmean(s > 0):.3f}")
