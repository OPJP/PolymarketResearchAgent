"""Coverage-preserving null: rotate each print's spot path to another 5m window of the same 2h TEST block.
Compares raw AUC (as match_test) and a price-stratified AUC, at the latency match_test chose for each label set."""
import pickle, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.analysis.updown import SpotIndex, score_prints, auc
D = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/verify-lookahead-0/"
d = pickle.load(open(D + "data.pkl", "rb"))
spot = SpotIndex(d["spot_ts"])
T = d["test_prints"].reset_index(drop=True)
blocks = d["test_blocks"]
st = T["start_ts"].to_numpy()
bstart = np.full(len(T), -1)
for a, b in blocks:
    m = (st >= a) & (st < b); bstart[m] = a
assert (bstart >= 0).all()
j = (st - bstart) // 300
price = T["price"].to_numpy()
print("share of prices on 1-cent grid: %.3f" % np.mean(np.isclose(price * 100, np.round(price * 100), atol=1e-6)))
pbin = np.searchsorted(np.quantile(price, np.linspace(0, 1, 101)[1:-1]), price, side="right")  # 100 price quantile bins
def strat_auc(s, y, g=pbin):
    df = pd.DataFrame({"s": s, "y": y, "g": g}); df = df[np.isfinite(df.s)]
    num = den = 0.0
    for _, q in df.groupby("g"):
        n1 = q.y.sum(); n0 = len(q) - n1
        if n1 == 0 or n0 == 0: continue
        r = q.s.rank().to_numpy(); a = (r[q.y.to_numpy() == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
        num += a * n1 * n0; den += n1 * n0
    return num / den
def run(name, y, lat):
    s = score_prints(T, spot, lat)
    raw, sa = auc(s, y), strat_auc(s, y)
    nr, ns, fin = [], [], []
    for k in range(1, 24):
        sh = (((j + k) % 24) - j) * 300
        sp = score_prints(T, spot, lat, shift=sh)
        fin.append(np.isfinite(sp).mean()); nr.append(auc(sp, y)); ns.append(strat_auc(sp, y))
    nr, ns = np.array(nr), np.array(ns)
    pr = (1 + (nr >= raw).sum()) / 24; ps = (1 + (ns >= sa).sum()) / 24
    print(f"{name:14s} lat {lat:2d} | raw AUC {raw:.4f} rot-null mean {nr.mean():.4f} max {nr.max():.4f} p {pr:.3f} | "
          f"price-strat AUC {sa:.4f} rot-null mean {ns.mean():.4f} max {ns.max():.4f} p {ps:.3f} | null finite min {min(fin):.3f}", flush=True)
for W, L in [("0x3048d65321be3497164cdfc2996f94f98a2e7537", 20), ("0xb55fa1296e6ec55d0ce53d93b9237389f11764d4", 0)]:
    y = (T["wallet"] == W).to_numpy().astype(int); print(W[:10], "AUC(-price) %.4f" % auc(-price, y)); run(W[:10], y, L)
