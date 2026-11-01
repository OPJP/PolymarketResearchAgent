"""Iteration 10: are the 62/250 rungs the far-side rungs of the 500 posture ladder? For each 62/250-class fill of the lot
(all fills with calldata sizes; no Chainlink needed), the side of the same wallet's nearest 500-class fill in the same window
within +-30 s: share on the OPPOSITE outcome. Also the same for 500-class fills vs other 500-class fills (control: a
posture ladder keeps one side for a while, so 500 vs 500 should be mostly the same side). STUDY case by case; VALIDATE
aggregate."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import a1_score as A  # noqa: E402

C = ROOT / ".cache/re/directional-maker"


def main():
    out = {}
    for sp, ofn in (("study", "b1_cluster_orders_study"), ("validate", "b1_cluster_orders_valid")):
        v = pd.read_parquet(C / f"it9/volhist_{sp}.parquet", columns=["txh", "wallet", "b", "st", "is_up", "token"])
        ob = pd.read_parquet(C / f"{ofn}.parquet", columns=["tx", "w", "token_id", "taker_amount", "oside", "role"])
        ob = ob[(ob.role == "maker") & (ob.oside == 0)].copy()
        ob["key"] = ob.tx.str.lower() + "|" + ob.w.astype(str) + "|" + ob.token_id.astype(str)
        om = (ob.drop_duplicates("key").set_index("key").taker_amount / 1e6).round(2)
        v["txh"] = v.txh.str.lower()
        v["wn"] = v.wallet.astype(str).str.lower().map(lambda a: A.NAME.get(a, a))
        v["orig"] = (v.txh + "|" + v.wn + "|" + v.token.astype(str)).map(om)
        v["c"] = np.where(v.orig.isin([500, 1000, 2000]), "500", np.where(v.orig.isin([62, 61.99, 250, 125]), "62_250", "x"))
        res = {}
        for c_ in ("62_250", "500"):
            opp, same = 0, 0
            for (w, st), g in v.groupby(["wn", "st"]):
                f5 = g[g.c == "500"]
                if not len(f5):
                    continue
                q = g[g.c == c_]
                b5 = f5.b.to_numpy()
                u5 = f5.is_up.to_numpy()
                for r in q.itertuples(index=False):
                    dt = np.abs(b5 - r.b)
                    if c_ == "500":
                        dt = np.where(dt == 0, 10 ** 9, dt)  # exclude itself (same second)
                    j = int(np.argmin(dt))
                    if dt[j] <= 30:
                        if u5[j] == r.is_up:
                            same += 1
                        else:
                            opp += 1
            res[c_] = {"pairs": opp + same, "share_opposite_outcome": round(opp / max(opp + same, 1), 3)}
        res["windows_with_both"] = int(v.groupby(["wn", "st"]).c.agg(lambda s: ("500" in set(s)) and ("62_250" in set(s))).sum())
        out[sp] = res
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_opp_side.json", "w"), indent=1)


if __name__ == "__main__":
    main()
