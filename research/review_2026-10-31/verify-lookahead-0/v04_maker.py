"""Same diagnostics for the BTC 5m directional-maker match tests (passive-buy prints)."""
import pickle, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.analysis.updown import SpotIndex, score_prints, auc
D = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/verify-lookahead-0/"
d = pickle.load(open(D + "data.pkl", "rb"))
spot = SpotIndex(d["spot_ts"])
T = d["test_m"].reset_index(drop=True)
st = T["start_ts"].to_numpy(); bstart = np.full(len(T), -1)
for a, b in d["test_blocks"]:
    m = (st >= a) & (st < b); bstart[m] = a
assert (bstart >= 0).all()
j = (st - bstart) // 300; price = T["price"].to_numpy()
pbin = np.searchsorted(np.quantile(price, np.linspace(0, 1, 101)[1:-1]), price, side="right")
def strat_auc(s, y):
    df = pd.DataFrame({"s": s, "y": y, "g": pbin}); df = df[np.isfinite(df.s)]; num = den = 0.0
    for _, q in df.groupby("g"):
        n1 = q.y.sum(); n0 = len(q) - n1
        if n1 == 0 or n0 == 0: continue
        r = q.s.rank().to_numpy(); num += ((r[q.y.to_numpy() == 1].sum() - n1 * (n1 + 1) / 2)); den += n1 * n0
    return num / den
rng = np.random.default_rng(7)
shifts = [int(rng.integers(3600, 6 * 3600)) * int(rng.choice([-1, 1])) for _ in range(30)]
for W, f in [("0xc53375ff94e96100f2b30a4b5775db35218d69a9", None), ("0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", None)]:
    stored = json.load(open(f"/home/user/PolymarketResearchAgent/research/wallets/{W}/updown_maker_study_btc_5m.json"))["derived"]["match_test"]
    lat = stored["chosen_latency_s"]
    y = (T["wallet"] == W).to_numpy().astype(int)
    s = score_prints(T, spot, lat)
    fin = [np.isfinite(score_prints(T, spot, lat, shift=sh)).mean() for sh in shifts[:10]]
    clk = [auc(score_prints(T, spot, lat, shift=sh), y) for sh in shifts[:30]]
    nr, ns = [], []
    for k in range(1, 24):
        sh = (((j + k) % 24) - j) * 300; sp = score_prints(T, spot, lat, shift=sh)
        nr.append(auc(sp, y)); ns.append(strat_auc(sp, y))
    raw, sa = auc(s, y), strat_auc(s, y)
    print(f"{W[:10]} maker lat {lat}: stored AUC {stored['test']['auc']:.4f} recomputed {raw:.4f}; AUC(-price) {auc(-price, y):.4f}; "
          f"clock-shift null (30 of the stored shifts) mean {np.nanmean(clk):.4f}, finite share median {np.median(fin):.3f}")
    print(f"   rotation null raw: mean {np.mean(nr):.4f} max {np.max(nr):.4f} p {(1+(np.array(nr)>=raw).sum())/24:.3f} | "
          f"price-strat obs {sa:.4f} null mean {np.mean(ns):.4f} max {np.max(ns):.4f} p {(1+(np.array(ns)>=sa).sum())/24:.3f}", flush=True)
