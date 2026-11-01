"""Iteration 9: horizon-matched volatility? (new hypothesis V10: the engine's sigma is a realised vol whose lookback scales
with the window length). Lookback scan L in {300, 900, 1800, 3600, 7200} x k in {1, 1.4} on (a) BTC hourly fills (block
clock, BUILD+STUDY choice, VALIDATE aggregate), (b) BTC 5m block-clock tables (code9/vol_hist.py), (c) live 15m and 5m
match-clock fills (side_D, descriptive)."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"
LS = (300, 900, 1800, 3600, 7200)
out = {}
# (b) BTC 5m historical
for sp_ in ("build", "study", "validate"):
    D = pd.read_parquet(C / "it9" / f"volhist_{sp_}.parquet")
    y = D.is_up.to_numpy() == 1; x = np.log(D.S / D.K).to_numpy(); m = D.mid_up.to_numpy(); st = np.sqrt(D.tau.to_numpy())
    out[f"btc5m_{sp_}"] = {f"v{L}x{k}": round(float(np.mean((norm.cdf(x / (k * D[f"v{L}"].to_numpy() * st)) > m) == y)), 3) for L in LS for k in (1.0, 1.4)}
# (c) live side_D by family
D = pd.read_parquet(C / "it9" / "side_D_1793448000_1793469600.parquet")
sp = pd.read_parquet(C / "it9" / "spot1s_rest_1793440800_1793469600.parquet").sort_values("sec")
b0 = int(sp.sec.iloc[0]); px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan); px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
px = pd.Series(px).ffill().to_numpy(); rr = np.r_[0.0, np.diff(np.log(px))]; cs = np.r_[0.0, np.cumsum(rr * rr)]
i = D["T"].to_numpy() // 1000 - 1 - b0
tau = np.maximum(D.en.to_numpy() - D["T"].to_numpy() / 1000, 1.0); x = np.log(D.cl.to_numpy(float) / D.K.to_numpy(float)); m = D.mid_up.to_numpy(); y = D.is_up.to_numpy() == 1
fam = np.where(D.en - D.st == 900, "15m", "5m")
for f in ("5m", "15m"):
    g = fam == f
    out[f"live_{f}"] = {f"v{L}x{k}": round(float(np.mean(((norm.cdf(x / (k * np.sqrt((cs[i + 1] - cs[i + 1 - L]) / L) * np.sqrt(tau))) > m) == y)[g])), 3) for L in LS for k in (1.0, 1.4)}
    out[f"live_{f}"]["n"] = int(g.sum())
for k_, v in out.items():
    best = max((kk for kk in v if kk != "n"), key=lambda kk: v[kk])
    print(k_, "best", best, v[best], "|", {kk: v[kk] for kk in v if kk.endswith("x1.0")})
(HERE.parent / "results" / "iter9_horizon_sigma.json").write_text(json.dumps(out, indent=1))
