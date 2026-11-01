"""Iteration 11 (mechanics panel P3 = X108): is the off-session ladder two-sided? Same-pass salt adjacency on the lot's
BTC 5m cluster maker BUY orders (calldata; each order = wallet x salt within one daily counter epoch, epochs start at the
01:00 UTC restart). Pairs = two filled orders of the same wallet in the same market with 0 < delta salt <= 40 (~3 s of
signing at ~14 orders/s). Statistic = share of pairs on the other outcome; null = the outcome labels of the wallet's
filled orders permuted within (wallet, market), 200 draws. One-sided passes -> observed << null; two-sided passes ->
observed ~ null. By session (12-24 UTC vs 00-12 UTC) and rung class (500 x 2^k vs 62/250). VALIDATE aggregate only.
    python code11/salt_pass.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
DS = 40


def main():
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet")
    upset = set(W.up_token.astype(str))
    out = {}
    rng = np.random.default_rng(108)
    for sp, fn in (("study", "b1_cluster_orders_study"), ("validate", "b1_cluster_orders_valid")):
        b = pd.read_parquet(C / f"{fn}.parquet", columns=["salt", "w", "token_id", "bts", "cond", "taker_amount", "oside", "role"])
        b = b[(b.role == "maker") & (b.oside == 0)].copy()
        b["salt"] = pd.to_numeric(b.salt, errors="coerce")
        b = b.dropna(subset=["salt"])
        b["epoch"] = (b.bts - 3600) // 86400
        o = b.sort_values("bts").drop_duplicates(["w", "epoch", "salt"]).copy()
        o["up"] = o.token_id.astype(str).isin(upset).astype(int)
        o["orig"] = (o.taker_amount / 1e6).round(2)
        o["cls"] = np.where(o.orig.isin([500, 1000, 2000]), "500", np.where(o.orig.isin([62, 250, 125]), "62/250", "other"))
        o["sess"] = np.where(pd.to_datetime(o.bts, unit="s").dt.hour >= 12, "session_12_24", "off_00_12")
        pairs = []
        for (wn, ep), g in o.groupby(["w", "epoch"]):
            g = g.sort_values("salt")
            s = g.salt.to_numpy()
            c = g.cond.to_numpy()
            idx = g.index.to_numpy()
            for i in range(len(g)):
                j = i + 1
                while j < len(g) and s[j] - s[i] <= DS:
                    if c[j] == c[i] and s[j] > s[i]:
                        pairs.append((idx[i], idx[j]))
                    j += 1
        P = pd.DataFrame(pairs, columns=["a", "b"])
        if not len(P):
            out[sp] = {"pairs": 0}
            continue
        ua, ub = o.loc[P.a, "up"].to_numpy(), o.loc[P.b, "up"].to_numpy()
        other = ua != ub
        sess = o.loc[P.a, "sess"].to_numpy()
        cls = o.loc[P.a, "cls"].to_numpy()
        # null: permute 'up' within (wallet, market)
        grp = o.groupby(["w", "cond"]).indices
        pos = {ix: k for k, ix in enumerate(o.index)}
        upv = o.up.to_numpy().copy()
        ia = np.array([pos[x] for x in P.a])
        ib = np.array([pos[x] for x in P.b])
        nulls = {k: [] for k in ("all", "session_12_24", "off_00_12", "500", "62/250")}
        for _ in range(200):
            perm = upv.copy()
            for _, ii in grp.items():
                if len(ii) > 1:
                    perm[ii] = rng.permutation(upv[ii])
            oth = perm[ia] != perm[ib]
            nulls["all"].append(oth.mean())
            for k in ("session_12_24", "off_00_12"):
                m = sess == k
                nulls[k].append(oth[m].mean() if m.any() else np.nan)
            for k in ("500", "62/250"):
                m = cls == k
                nulls[k].append(oth[m].mean() if m.any() else np.nan)
        rec = {"orders": int(len(o)), "pairs": int(len(P))}
        for k, m in (("all", np.ones(len(P), bool)), ("session_12_24", sess == "session_12_24"), ("off_00_12", sess == "off_00_12"),
                     ("500", cls == "500"), ("62/250", cls == "62/250")):
            nn = np.array(nulls[k], float)
            rec[k] = {"pairs": int(m.sum()), "other_outcome_share": round(float(other[m].mean()), 4) if m.any() else None,
                      "null_mean": round(float(np.nanmean(nn)), 4), "null_q025_q975": [round(float(np.nanquantile(nn, 0.025)), 4), round(float(np.nanquantile(nn, 0.975)), 4)]}
        out[sp] = rec
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter11_salt_pass.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
