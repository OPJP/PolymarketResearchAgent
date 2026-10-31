"""Iteration 10: the pre-registered R7-side test (NOTES, 23:21 UTC). Side of each lot fill by the class of the filled
order (calldata original size): 500 x 2^k -> frozen Chainlink posture; 62 / 250 / 125 / 100 / 12 -> the public candidate
with the best STUDY accuracy among {cheaper side, market favourite, Binance posture, Chainlink posture}; pairing class
(non-schedule size within 2% of |own imbalance|) -> the under-held outcome (own state, reported separately); other
sizes -> Chainlink posture. Public variant: pairing-class fills keep the Chainlink posture. Confirmation on VALIDATE
(aggregate): class-conditional public rule minus the frozen posture on all fills >= +0.03 with the 2-h block bootstrap
lower bound > 0. Vectorised (merge_asof for the own imbalance). Scored fills = those with a fetched Chainlink value."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(ROOT))
import a1_score as A  # noqa: E402
import cl_source  # noqa: E402
import m1_pair_lot as M1  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
STD = {500, 1000, 250, 125, 100, 62, 50, 12, 300, 40, 200, 2000, 25, 31, 20, 10, 5}
CANDS = ("cheaper", "favourite", "binance", "chainlink")


def table(sp, fn, ofn, A5, K, clv):
    v = pd.read_parquet(C / f"it9/volhist_{sp}.parquet", columns=["txh", "wallet", "b", "st", "en", "is_up", "mid_up", "token", "v300", "S", "K"])
    v = v.rename(columns={"K": "K_bn"})
    t = pd.read_parquet(C / f"{fn}.parquet", columns=["tx", "sign_ms"])
    t["tx"] = t.tx.str.lower()
    t = t.drop_duplicates("tx").set_index("tx")
    v["txh"] = v.txh.str.lower()
    v["T_hat"] = A.that(v.txh.map(t.sign_ms), v.b.astype(float) * 1000)
    v["cl"] = ((v.T_hat - 1432) // 1000).astype(np.int64).map(lambda s: clv.get(int(s), np.nan))
    v["K"] = v.st.map(K)
    ob = pd.read_parquet(C / f"{ofn}.parquet", columns=["tx", "w", "token_id", "taker_amount", "oside", "role"])
    ob = ob[(ob.role == "maker") & (ob.oside == 0)].copy()
    ob["key"] = ob.tx.str.lower() + "|" + ob.w.astype(str) + "|" + ob.token_id.astype(str)
    om = (ob.drop_duplicates("key").set_index("key").taker_amount / 1e6).round(2)
    v["wn"] = v.wallet.astype(str).str.lower().map(lambda a: A.NAME.get(a, a))
    v["orig"] = (v.txh + "|" + v.wn + "|" + v.token.astype(str)).map(om)
    # own imbalance strictly before the fill's block second (vectorised)
    a = A5[["wallet", "st", "timestamp", "isup", "size"]].copy()
    a["sg"] = np.where(a.isup, a["size"], -a["size"])
    a = a.groupby(["wallet", "st", "timestamp"], as_index=False).sg.sum().sort_values("timestamp")
    a["cum"] = a.groupby(["wallet", "st"]).sg.cumsum()
    a = a.rename(columns={"wallet": "wn"})
    a["timestamp"] = a.timestamp.astype(np.int64)
    v["b"] = v.b.astype(np.int64)
    v["st"] = v.st.astype(np.int64)
    a["st"] = a.st.astype(np.int64)
    v = v.sort_values("b")
    v = pd.merge_asof(v, a[["wn", "st", "timestamp", "cum"]].sort_values("timestamp"), left_on="b", right_on="timestamp", by=["wn", "st"],
                      allow_exact_matches=False, direction="backward")
    v["inv"] = v.cum.fillna(0.0)
    v["pair"] = (~v.orig.isin(STD)) & ((v.orig / v.inv.abs().replace(0, np.nan) - 1).abs() < 0.02)
    o = v.orig.fillna(-1)
    v["cls"] = np.select([v.pair, o.isin([500, 1000, 2000]), (o == 62) | ((o - 61.99).abs() < 0.02), o.isin([250, 125]), o.isin([100, 12])],
                         ["pair", "500", "62", "250", "100_12"], "other")
    h = v.dropna(subset=["cl", "K", "mid_up"]).copy()
    x = np.log(h.cl.to_numpy(float) / h.K.to_numpy(float))
    m = h.mid_up.to_numpy(float)
    tau = np.maximum(h.en.to_numpy() - h.T_hat.to_numpy() / 1000.0, 1.0)
    sig = 1.4 * h.v300.to_numpy(float) * np.sqrt(tau)
    h["p_chainlink"] = norm.cdf(x / sig) > m
    h["p_binance"] = norm.cdf(np.log(h.S.to_numpy(float) / h.K_bn.to_numpy(float)) / sig) > m
    h["p_cheaper"] = m < 0.5
    h["p_favourite"] = m > 0.5
    h["p_under"] = h.inv.to_numpy() < 0
    h["y"] = h.is_up.to_numpy() == 1
    return h


def boot(h, a_col, b_col, n=2000, seed=10):
    blk = (h.b.to_numpy() // 7200)
    ub = np.unique(blk)
    da = (h[a_col].to_numpy() == h.y.to_numpy()).astype(float)
    db = (h[b_col].to_numpy() == h.y.to_numpy()).astype(float)
    sa = pd.Series(da).groupby(blk).sum()
    sb = pd.Series(db).groupby(blk).sum()
    nn = pd.Series(np.ones(len(h))).groupby(blk).sum()
    rng = np.random.default_rng(seed)
    g = []
    for _ in range(n):
        i = rng.integers(0, len(ub), len(ub))
        g.append((sa.to_numpy()[i].sum() - sb.to_numpy()[i].sum()) / nn.to_numpy()[i].sum())
    return float(np.mean(da) - np.mean(db)), [float(np.quantile(g, 0.025)), float(np.quantile(g, 0.975))]


def main():
    ptb = pd.read_parquet(C / "cl/ptb_lot.parquet")
    K = dict(zip(ptb.start_ts.astype(int), ptb.ptb.astype(float)))
    clv = cl_source._cache()
    A5 = M1.load_act()
    out = {}
    H = {sp: table(sp, fn, ofn, A5, K, clv) for sp, fn, ofn in (("study", "b1_takers_study", "b1_cluster_orders_study"),
                                                                 ("validate", "b1_takers_valid", "b1_cluster_orders_valid"))}
    st = H["study"]
    choice = {}
    for c in ("62", "250", "100_12"):
        g = st[st.cls == c]
        accs = {k: float(np.mean(g[f"p_{k}"] == g.y)) for k in CANDS} if len(g) else {}
        choice[c] = max(accs, key=accs.get) if accs else "chainlink"
        out.setdefault("study_candidates", {})[c] = {"n": int(len(g)), **{k: round(v, 3) for k, v in accs.items()}}
    out["chosen_on_study"] = choice
    for sp, h in H.items():
        rule = h.p_chainlink.copy()
        for c, k in choice.items():
            sel = h.cls == c
            rule[sel] = h.loc[sel, f"p_{k}"]
        h["r7_public"] = rule
        r7o = rule.copy()
        r7o[h.cls == "pair"] = h.loc[h.cls == "pair", "p_under"]
        h["r7_own"] = r7o
        res = {"n": int(len(h)), "class_mix": h.cls.value_counts(normalize=True).round(3).to_dict(),
               "frozen_all": float(np.mean(h.p_chainlink == h.y)), "r7_public": float(np.mean(h.r7_public == h.y)),
               "r7_with_pairing_own_state": float(np.mean(h.r7_own == h.y)),
               "by_class_frozen": {c: [int((h.cls == c).sum()), round(float(np.mean((h.p_chainlink == h.y)[h.cls == c])), 3)] for c in h.cls.unique()},
               "by_class_r7": {c: [int((h.cls == c).sum()), round(float(np.mean((h.r7_public == h.y)[h.cls == c])), 3)] for c in h.cls.unique()},
               "per_wallet_r7_public": {w: round(float(np.mean((g.r7_public == g.y))), 3) for w, g in h.groupby("wn")},
               "per_wallet_frozen": {w: round(float(np.mean((g.p_chainlink == g.y))), 3) for w, g in h.groupby("wn")},
               "baselines": {k: round(float(np.mean(h[f"p_{k}"] == h.y)), 3) for k in ("cheaper", "favourite", "binance", "under")}}
        res["gain_r7_public_vs_frozen"], res["gain_ci_2h_blocks"] = boot(h, "r7_public", "p_chainlink")
        x = np.log(h.cl.to_numpy(float) / h.K.to_numpy(float))
        D = ((x > 0) != (h.mid_up.to_numpy(float) > 0.5)) & (x != 0)
        hit = (x > 0) == h.y.to_numpy()
        res["region_D_by_class"] = {c: [int((D & (h.cls == c).to_numpy()).sum()), round(float(np.mean(hit[D & (h.cls == c).to_numpy()])), 3) if (D & (h.cls == c).to_numpy()).any() else None,
                                        int(h.st[D & (h.cls == c).to_numpy()].nunique())] for c in h.cls.unique()}
        res["class_mix_by_utc_block"] = {f"{b0:02d}-{b0 + 6:02d}": h.cls[((h.b // 3600) % 24 >= b0) & ((h.b // 3600) % 24 < b0 + 6)].value_counts(normalize=True).round(3).to_dict()
                                         for b0 in (0, 6, 12, 18)}
        k5 = (h.cls == "500").to_numpy()
        res["500_class_region_D_window_mean"] = float(pd.Series(hit[D & k5]).groupby(h.st.to_numpy()[D & k5]).mean().mean()) if (D & k5).any() else None
        out[sp] = res
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_r7_side.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
