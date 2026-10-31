"""Iteration 9 (X76 I8-3): per-wallet posture by region (D sigma-free / A vol comparison) and a sigma-scale scan per
wallet (v3600 x k), 10-31 12:00-18:00 match-clock fills (side_D). Development, descriptive."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
C = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker/it9"
D = pd.read_parquet(C / "side_D_1793448000_1793469600.parquet")
sp = pd.read_parquet(C / "spot1s_rest_1793440800_1793469600.parquet").sort_values("sec")
b0 = int(sp.sec.iloc[0]); px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan); px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
px = pd.Series(px).ffill().to_numpy(); rr = np.r_[0.0, np.diff(np.log(px))]; cs = np.r_[0.0, np.cumsum(rr * rr)]
i = D["T"].to_numpy() // 1000 - 1 - b0
v300 = np.sqrt((cs[i + 1] - cs[i + 1 - 300]) / 300); v3600 = np.sqrt((cs[i + 1] - cs[i + 1 - 3600]) / 3600)
tau = np.maximum(D.en.to_numpy() - D["T"].to_numpy() / 1000, 1.0); x = np.log(D.cl.to_numpy(float) / D.K.to_numpy(float))
m = D.mid_up.to_numpy(); y = D.is_up.to_numpy() == 1; regA = np.sign(x) == np.sign(m - 0.5)
names = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "mo-money"}
out = {}
for ad, nm in names.items():
    g = (D.wallet == ad).to_numpy()
    rec = {"n": int(g.sum()), "regionD_n": int((g & ~regA).sum()), "regionD_acc": round(float(((x > 0) == y)[g & ~regA].mean()), 3)}
    for k in (0.5, 0.7, 1.0, 1.4, 2.0):
        ok = (norm.cdf(x / (k * v3600 * np.sqrt(tau))) > m) == y
        rec[f"A_v3600x{k}"] = round(float(ok[g & regA].mean()), 3)
    ok6 = (norm.cdf(x / (1.4 * v300 * np.sqrt(tau))) > m) == y
    rec["A_frozen"] = round(float(ok6[g & regA].mean()), 3)
    rec["A_bought_favourite"] = round(float(((m > 0.5) == y)[g & regA].mean()), 3)
    out[nm] = rec
print(json.dumps(out, indent=1))
(Path(__file__).resolve().parents[1] / "results" / "iter9_wallet_sigma.json").write_text(json.dumps(out, indent=1))
