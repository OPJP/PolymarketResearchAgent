"""Iteration 11 (exploratory, X104 / P1 entry): the window's entry side from the real-Chainlink posture at the first fill
(T_hat - 1,432 ms, frozen sigma, last clean print at b - 3) combined with the market-only taker-flow complement (net clean
taker demand over the previous 30 s). Reports each alone, their agreement share, and the accuracy where they agree /
disagree, per split (VALIDATE aggregate).
    python code11/entry_combo.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE))
import cl_source  # noqa: E402
from side_inblock import that  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
SPLIT_V = 1793059200


def main():
    ptb = pd.read_parquet(C / "cl/ptb_lot.parquet")
    K = dict(zip(ptb.start_ts.astype(int), ptb.ptb.astype(float)))
    clv = cl_source._cache()
    out = {}
    for sp, fn in (("study", "b1_takers_study"), ("validate", "b1_takers_valid")):
        v = pd.read_parquet(C / f"it9/volhist_{sp}.parquet", columns=["txh", "cid", "b", "st", "en", "is_up", "mid_up", "v300"])
        t = pd.read_parquet(C / f"{fn}.parquet", columns=["tx", "sign_ms"])
        t["tx"] = t.tx.str.lower()
        t = t.drop_duplicates("tx").set_index("tx")
        v["txh"] = v.txh.str.lower()
        v = v.sort_values(["cid", "b"]).groupby("cid").first().reset_index()  # the window's first cluster maker fill
        v["T_hat"] = that(v.txh.map(t.sign_ms), v.b.astype(float) * 1000)
        v["cl"] = ((v.T_hat - 1432) // 1000).astype(np.int64).map(lambda s: clv.get(int(s), np.nan))
        v["K"] = v.st.map(K)
        v["tau"] = np.maximum(v.en - v.T_hat / 1000.0, 1.0)
        h = v.dropna(subset=["cl", "K", "mid_up"]).copy()
        f = norm.cdf(np.log(h.cl / h.K) / (1.4 * h.v300 * np.sqrt(h.tau)))
        h["post_up"] = (f > h.mid_up).astype(int)
        out[sp] = {"first_fills": int(len(v)), "with_cl": int(len(h))}
        ef = pd.read_parquet(C / "it11" / "entry_flow_rows.parquet") if (C / "it11" / "entry_flow_rows.parquet").exists() else None
        if ef is None:
            continue
        h = h.merge(ef[["cid", "d30"]], on="cid", how="inner")
        h["flow_up"] = (h.d30 < 0).astype(int)
        y = h.is_up.to_numpy()
        agree = h.post_up == h.flow_up
        out[sp].update({"n": int(len(h)), "posture_acc": round(float((h.post_up == y).mean()), 4), "flow_complement_acc": round(float((h.flow_up == y).mean()), 4),
                        "agree_share": round(float(agree.mean()), 4), "acc_when_agree": round(float((h.post_up == y)[agree].mean()), 4),
                        "posture_acc_when_disagree": round(float((h.post_up == y)[~agree].mean()), 4)})
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter11_entry_combo.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
