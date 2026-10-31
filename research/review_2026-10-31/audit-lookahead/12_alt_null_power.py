"""Power check: the spot-USING synthetic wallet (prob ~ (1-p)^3 * exp(3*edge@2s)) that the code's null
missed in 5/5 seeds, scored with the within-block-shift + price-stratified null (23 shifts)."""
import pickle
from pathlib import Path
import numpy as np, pandas as pd
from polyrea.analysis.updown import SpotIndex, score_prints, fair_up_vectorized

D = pickle.load(open(Path(__file__).parent / "data" / "btc5m.pkl", "rb"))
spot = SpotIndex(D["spot_ts"]); testp = D["test"]["prints"]; blocks = np.array(D["test_blocks"])
def strat_auc(s, y, pb):
    ok = np.isfinite(s); df = pd.DataFrame({"s": s[ok], "y": y[ok], "pb": pb[ok]})
    df["r"] = df.groupby("pb")["s"].rank()
    g = df.groupby("pb").agg(n1=("y", "sum"), n=("y", "size")).join(df[df.y == 1].groupby("pb")["r"].sum().rename("r1")).fillna(0)
    g["n0"] = g.n - g.n1; g = g[(g.n1 > 0) & (g.n0 > 0)]
    return float((g.r1 - g.n1 * (g.n1 + 1) / 2).sum() / (g.n1 * g.n0).sum())
def wb(p, lat, k):
    st = p.start_ts.to_numpy(); a = blocks[np.searchsorted(blocks[:, 0], st, side="right") - 1, 0]
    sh = a + (st - a + 300 * k) % 7200 - st
    fu = fair_up_vectorized(spot, st + sh, p.end_ts.to_numpy() + sh, p.ts.to_numpy() - lat + sh, 60)
    return np.where(p.is_up.to_numpy(), fu, 1 - fu) - p.price.to_numpy()
pr = testp.price.to_numpy(); s2 = np.nan_to_num(score_prints(testp, spot, 2), nan=-1); pb = np.round(pr, 2)
for sd in (1, 2, 3):
    y = (np.random.default_rng(sd).random(len(testp)) < 0.03 * (1 - pr) ** 3 * np.exp(3 * s2)).astype(int)
    obs = strat_auc(score_prints(testp, spot, 2), y, pb); null = np.array([strat_auc(wb(testp, 2, k), y, pb) for k in range(1, 24)])
    print(f"seed {sd}: obs {obs:.4f} null mean {null.mean():.4f} max {null.max():.4f} p {(1 + (null >= obs).sum()) / 24:.3f}")
