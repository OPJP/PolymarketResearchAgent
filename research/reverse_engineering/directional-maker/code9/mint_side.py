"""Iteration 9: is the historical fill side taker-driven? Each cluster maker BUY fill of the lot (block-clock tables) is
classed by the taker order of its transaction (lot calldata b1_takers_*): 'mint' = the taker BUYS the complement token,
'direct' = the taker SELLS the cluster's token. Posture accuracy (frozen, slow) and the cheaper-side share by class;
STUDY case by case, VALIDATE aggregate."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
C = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker"
out = {}
for sp_, tk in (("study", "b1_takers_study"), ("validate", "b1_takers_valid")):
    D = pd.read_parquet(C / "it9" / f"volhist_{sp_}.parquet")
    T = pd.read_parquet(C / f"{tk}.parquet", columns=["tx", "token_id", "oside"])
    T["tx"] = T.tx.str.lower()
    T = T.drop_duplicates("tx").set_index("tx")
    D = D[D.txh.isin(T.index)].copy()
    tt = T.loc[D.txh]
    same = tt.token_id.astype(str).to_numpy() == D.token.astype(str).to_numpy()
    side = tt.oside.to_numpy()
    cls = np.select([same & (side == 1), ~same & (side == 0)], ["direct", "mint"], "other")
    y = D.is_up.to_numpy() == 1; x = np.log(D.S / D.K).to_numpy(); m = D.mid_up.to_numpy(); st = np.sqrt(D.tau.to_numpy())
    okf = (norm.cdf(x / (1.4 * D.v300.to_numpy() * st)) > m) == y
    oks = (norm.cdf(x / (D.v3600.to_numpy() * st)) > m) == y
    und = (m < 0.5) == y
    rec = {"n_joined": int(len(D))}
    for c in ("direct", "mint", "other"):
        k = cls == c
        if k.any():
            rec[c] = {"share": round(float(k.mean()), 3), "frozen": round(float(okf[k].mean()), 3), "slow": round(float(oks[k].mean()), 3),
                      "bought_underdog": round(float(und[k].mean()), 3)}
    out[sp_] = rec
print(json.dumps(out, indent=1))
(Path(__file__).resolve().parents[1] / "results" / "iter9_mint_side.json").write_text(json.dumps(out, indent=1))
