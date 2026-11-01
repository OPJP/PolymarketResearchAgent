"""iteration 18, T6 = X215 step 4 (mechanics P1; pre-registered 12:42 UTC 11-01): Spearman over days (BUILD 10-09..22,
STUDY 10-23..26) between the iteration-11 best posture multiplier k and the day's median P / v300 at the cluster's
non-decided BTC 5m fills."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "code17"))
import sched_vol as sv  # noqa: E402
import inform_gate as ig  # noqa: E402
from features2 import Spot  # noqa: E402

C = sv.C
R = HERE.parent / "results"


def main():
    T = pd.read_parquet(C / "it18" / "slot_rv.parquet")
    Pf = sv.profiles(T)["utc_N28"]
    kb = json.loads((R / "iter11_k_by_day_binance.json").read_text())
    kl = json.loads((R / "iter11_k_by_day.json").read_text())["by_day"]
    best = {}
    for k, v in kb.items():
        md = k.split()[0]
        best[md] = v["best_k"]
    for md in ("10-23", "10-24", "10-25", "10-26"):
        best[md] = kl[md]["best_k"]
    a = pd.read_parquet(C / "spot_btc_1s.parquet")
    b = pd.read_parquet(C / "exam" / "spot_btc_1s.parquet")
    s = pd.concat([a, b]).dropna().drop_duplicates("sec").sort_values("sec")
    sp = Spot(s.sec.to_numpy(np.int64), s.px.to_numpy(float))
    F = ig.build_fills()
    F = F[(F.en - F.st) == 300]
    F = F[np.abs(F.mid_up - 0.5) <= 0.4]
    vb = sp.sigma(F.ts.to_numpy(np.int64) - 2, look=300)
    rb = sv.prof_col(Pf, F.st.to_numpy()) / vb
    db = pd.to_datetime(F.ts, unit="s").dt.strftime("%m-%d").to_numpy()
    V = pd.read_parquet(C / "it12" / "typed_fills.parquet", columns=["st", "en", "b", "mid_up", "v300", "sp"])
    V = V[(V.sp == "study") & ((V.en - V.st) == 300) & (np.abs(V.mid_up - 0.5) <= 0.4)]
    rl = sv.prof_col(Pf, V.st.to_numpy()) / V.v300.to_numpy()
    dl = pd.to_datetime(V.b, unit="s").dt.strftime("%m-%d").to_numpy()
    rows = []
    for md, k in sorted(best.items()):
        r = np.r_[rb[db == md], rl[dl == md]]
        r = r[np.isfinite(r)]
        if len(r) >= 50:
            rows.append((md, k, float(np.median(r)), int(len(r))))
    D = pd.DataFrame(rows, columns=["day", "best_k", "med_ratio", "n"])
    rho, p = spearmanr(D.best_k, D.med_ratio)
    out = {"days": D.to_dict("records"), "spearman": round(float(rho), 3), "p": float(p), "reading_met": bool(rho >= 0.4 and p < 0.05)}
    (R / "iter18_k_vs_profile.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
