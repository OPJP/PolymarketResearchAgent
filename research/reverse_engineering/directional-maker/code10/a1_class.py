"""Iteration 10 (A1 = X97 follow-up, discovered 23:17 UTC): the side rule by rung class on the lot. The scored lot fills
(random subsample with the real Chainlink value; pre-registered match-clock proxies) split by the calldata original size:
500-class (500 x 2^k), 62, 250, 100 / 12 (one-fifth rungs), pairing class (non-schedule, = |own imbalance|), other.
Per class: region D share and P(bought the Chainlink favourite) there; the frozen posture with S = Chainlink; and the
candidate side rules for the non-500 rungs: cheaper side, market favourite, Binance posture (Binance S and strike), the
under-held outcome (own state), the side of the wallet's previous 500-class fill in the window (own state).
STUDY case by case; VALIDATE aggregate. Also the size mix by UTC hour block to see when each class is used."""
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


def cls_of(o, pair):
    if pair:
        return "pair"
    if o in (500, 1000, 2000):
        return "500"
    if o == 62 or abs(o - 61.99) < 0.02:
        return "62"
    if o == 250 or o == 125:
        return "250"
    if o in (100, 12):
        return "100_12"
    return "other"


def main():
    ptb = pd.read_parquet(C / "cl/ptb_lot.parquet")
    K = dict(zip(ptb.start_ts.astype(int), ptb.ptb.astype(float)))
    clv = cl_source._cache()
    A5 = M1.load_act()
    G = {k: v for k, v in A5.groupby(["wallet", "st"])}
    out = {}
    for sp, fn, ofn in (("study", "b1_takers_study", "b1_cluster_orders_study"), ("validate", "b1_takers_valid", "b1_cluster_orders_valid")):
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
        # own state: imbalance before the fill and the side of the previous 500-class fill in the window
        inv, prev500 = [], []
        o500 = ob.assign(orig=(ob.taker_amount / 1e6).round(2))
        o500 = o500[o500.orig.isin([500.0, 1000.0, 2000.0])]
        k500 = set(o500.tx.str.lower() + "|" + o500.w.astype(str))
        for r in v.itertuples(index=False):
            g = G.get((r.wn, int(r.st)))
            if g is None:
                inv.append(np.nan)
                prev500.append(np.nan)
                continue
            bb = g[g.timestamp < r.b]
            inv.append(bb.loc[bb.isup, "size"].sum() - bb.loc[~bb.isup, "size"].sum())
            p5 = bb[(bb.tx + "|" + r.wn).isin(k500)]
            prev500.append(float(p5.isup.iloc[-1]) if len(p5) else np.nan)
        v["inv"], v["prev500_up"] = inv, prev500
        v["pair"] = (~v.orig.isin(STD)) & ((v.orig / v.inv.abs().replace(0, np.nan) - 1).abs() < 0.02)
        v["cls"] = [cls_of(o, p) for o, p in zip(v.orig.fillna(-1), v.pair)]
        h = v.dropna(subset=["cl", "K"]).copy()
        x = np.log(h.cl.to_numpy(float) / h.K.to_numpy(float))
        m = h.mid_up.to_numpy(float)
        y = h.is_up.to_numpy() == 1
        tau = np.maximum(h.en.to_numpy() - h.T_hat.to_numpy() / 1000.0, 1.0)
        fair = norm.cdf(x / (1.4 * h.v300.to_numpy(float) * np.sqrt(tau)))
        xb = np.log(h.S.to_numpy(float) / h.K_bn.to_numpy(float))
        fbn = norm.cdf(xb / (1.4 * h.v300.to_numpy(float) * np.sqrt(tau)))
        D = np.isfinite(m) & ((x > 0) != (m > 0.5)) & (x != 0)
        o = {"n_scored": int(len(h))}
        for c in ("500", "62", "250", "100_12", "pair", "other"):
            k = (h.cls == c).to_numpy()
            if k.sum() < 10:
                continue
            under = ((h.inv.to_numpy() < 0) == y)
            pv = h.prev500_up.to_numpy()
            kp = k & np.isfinite(pv)
            o[c] = {"n": int(k.sum()), "region_D_n": int((D & k).sum()),
                    "region_D_acc_cl": float(np.mean(((x > 0) == y)[D & k])) if (D & k).any() else None,
                    "posture_cl": float(np.mean(((fair > m) == y)[k])),
                    "posture_binance": float(np.mean(((fbn > m) == y)[k])),
                    "cheaper_side": float(np.mean(((m < 0.5) == y)[k])),
                    "market_favourite": float(np.mean(((m > 0.5) == y)[k])),
                    "under_held_own_state": float(np.mean(under[k & (h.inv.to_numpy() != 0)])) if (k & (h.inv.to_numpy() != 0)).any() else None,
                    "same_side_as_previous_500_own_state": [int(kp.sum()), float(np.mean(((pv == 1) == y)[kp])) if kp.any() else None]}
        hr = (h.b.to_numpy() // 3600) % 24
        o["class_mix_by_utc_block"] = {f"{b0:02d}-{b0 + 6:02d}": h.cls[(hr >= b0) & (hr < b0 + 6)].value_counts(normalize=True).round(3).to_dict() for b0 in (0, 6, 12, 18)}
        out[sp] = o
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_a1_class.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
