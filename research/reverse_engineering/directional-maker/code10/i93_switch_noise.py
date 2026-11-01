"""Iteration 10 (I9-3 = X89, step 3; pre-registered in code10/i93_switch_stamps.py): Chainlink 1-s noise and the
Chainlink - Binance basis in the 2 h before each BTC 5m switch-off vs the same clock times 3 and 4 days earlier.
Per 30-s run: sd of 1-s Chainlink changes, lag-1 autocorrelation, basis = mean(CL - Binance spot 1-s), and the basis's
sd within the run. Reported per switch and label, and pooled switch vs control."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import cl_source  # noqa: E402

C = ROOT / ".cache/re/directional-maker"


def main():
    st = pd.read_parquet(C / "i93_switch_stamps.parquet")
    c = cl_source._cache()
    sp = pd.concat([pd.read_parquet(C / "spot_btc_1s.parquet"), pd.read_parquet(C / "exam/spot_btc_1s.parquet")])
    f31 = C / "it9/spot1s_rest_1793440800_1793469600.parquet"
    if f31.exists():
        sp = pd.concat([sp, pd.read_parquet(f31)[["sec", "px"]]])
    bn = sp.drop_duplicates("sec").set_index("sec").px
    rows = []
    st["run"] = st.groupby("split").cumcount() // 30
    for (lab, run), g in st.groupby(["split", "run"]):
        s = g.stamp.astype(int).to_numpy()
        v = np.array([c.get(int(x), np.nan) for x in s])
        if np.isfinite(v).sum() < 25:
            continue
        d = np.diff(v)
        d = d[np.isfinite(d)]
        b = v - np.array([bn.get(int(x), np.nan) for x in s])
        rows.append((lab, run, float(np.nanstd(d)), float(np.corrcoef(d[:-1], d[1:])[0, 1]) if len(d) > 5 else np.nan,
                     float(np.nanmean(b)), float(np.nanstd(b))))
    R = pd.DataFrame(rows, columns=["split", "run", "sd", "ac1", "basis", "basis_sd"])
    R["switch"] = R.split.str.split("_").str[1]
    R["kind"] = R.split.str.split("_").str[2]
    out = {"runs": int(len(R))}
    out["per_switch"] = {}
    for sw, g in R.groupby("switch"):
        out["per_switch"][sw] = {k: {"runs": int(len(h)), "sd": round(float(h.sd.median()), 2), "ac1": round(float(h.ac1.median()), 2),
                                     "basis": round(float(h.basis.mean()), 1), "basis_sd": round(float(h.basis_sd.median()), 2)}
                                 for k, h in g.groupby("kind")}
    out["pooled"] = {k: {"runs": int(len(h)), "sd": round(float(h.sd.median()), 2), "ac1": round(float(h.ac1.median()), 2), "basis_sd": round(float(h.basis_sd.median()), 2)}
                     for k, h in R.groupby(R.kind.where(R.kind == "switch", "control"))}
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_i93_switch_noise.json", "w"), indent=1)


if __name__ == "__main__":
    main()
