"""Size/power of match_test's spot-clock-shift null with synthetic wallets on the real BTC 5m prints."""
import pickle, sys, time
import numpy as np
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.analysis.updown import SpotIndex, match_test, score_prints, auc
D = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/verify-lookahead-0/"
d = pickle.load(open(D + "data.pkl", "rb"))
spot = SpotIndex(d["spot_ts"])
FIT, TEST = d["fit_prints"].reset_index(drop=True), d["test_prints"].reset_index(drop=True)
kind = sys.argv[1]; seeds = [int(x) for x in sys.argv[2].split(",")]; n_perm = int(sys.argv[3])
edge_fit, edge_te = score_prints(FIT, spot, 2), score_prints(TEST, spot, 2)
def weights(df, edge):
    p = df["price"].to_numpy()
    if kind == "uniform": return np.ones(len(p))
    if kind == "expensive3": return p ** 3
    if kind == "expensive1": return p
    if kind == "cheap3": return (1 - p) ** 3
    if kind == "cheap3_edge": return (1 - p) ** 3 * np.exp(3.0 * np.nan_to_num(edge))
    if kind == "edge_only": return np.exp(3.0 * np.nan_to_num(edge))
    if kind == "edge_only10": return np.exp(10.0 * np.nan_to_num(edge))
    raise SystemExit(kind)
def label(df, edge, rng, rate=0.038):
    w = weights(df, edge); pr = np.clip(rate * w / w.mean(), 0, 1)
    out = df.copy(); out["wallet"] = np.where(rng.random(len(df)) < pr, "synth", "other"); return out
for s in seeds:
    rng = np.random.default_rng(1000 + s)
    f, t = label(FIT, edge_fit, rng), label(TEST, edge_te, rng)
    t0 = time.time()
    mt = match_test(f, t, "synth", spot, n_perm=n_perm, seed=s)
    r = mt["test"]
    y = (t["wallet"] == "synth").to_numpy().astype(int)
    print(f"{kind:12s} seed {s} n_perm {n_perm} lat {mt['chosen_latency_s']:3d} AUC {r['auc']:.4f} null_mean {r['auc_null_mean']:.4f} "
          f"null_p95 {r['auc_null_p95']:.4f} perm_p {r['auc_perm_p']:.4f} mcc_p {r['mcc_perm_p']:.3f} AUC(-price) {auc(-t['price'].to_numpy(), y):.3f} "
          f"MW p {r['mannwhitney_p']:.2g} ({time.time()-t0:.0f}s)", flush=True)
