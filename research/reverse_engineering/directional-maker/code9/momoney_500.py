"""Iteration 9 (X76): mo-money's 500-rung pass. Fills of 10-31 14:06-16:30 (it6/fill_side, with the Chainlink edge at
reference delays 700-3000 ms, frozen sigma) joined to the filled order's original size (calldata); posture accuracy by
wallet x delay for exact-500 orders and for the rest. Development, descriptive."""
import glob
import json
from pathlib import Path
import numpy as np
import pandas as pd
C = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker"
F = pd.read_parquet(C / "it6" / "fill_side_1793455600_1793464202.parquet")
X = pd.concat([pd.read_parquet(p, columns=["h", "s"]) for p in glob.glob(str(C / "it6" / "x_*.parquet"))]).drop_duplicates()
X["h"] = X.h.str.lower()
cd = pd.concat([pd.read_parquet(p, columns=["tx", "maker", "role", "maker_amount", "taker_amount", "oside"]) for p in glob.glob(str(C / "calldata" / "*1031_*.parquet"))])
cd["tx"], cd["maker"] = cd.tx.str.lower(), cd.maker.str.lower()
cd = cd[cd.role == "maker"]
cd["sh"] = np.where(cd.oside == 0, cd.taker_amount, cd.maker_amount) / 1e6
W = {"bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88", "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
m2h = X.groupby("s").h.apply(list).to_dict()
key = cd.groupby(["tx", "maker"]).sh.first().to_dict()
F["osz"] = [next((key[(h, W[w])] for h in m2h.get(int(T), []) if (h, W[w]) in key), np.nan) for T, w in zip(F["T"], F.wallet)]
y = F.up.to_numpy()
out = {}
for w in W:
    is5 = np.isclose(F.osz.to_numpy(float), 500, atol=0.6)
    kn = F.osz.notna().to_numpy()
    for cls, g in (("500", is5), ("other", kn & ~is5)):
        k = (F.wallet == w).to_numpy() & g
        if k.sum() < 20:
            continue
        out[f"{w}|{cls}"] = {"n": int(k.sum()), **{D_: round(float(np.mean(((F[f"e_cl_{D_}"] > 0).astype(int).to_numpy() == y)[k])), 3)
                                                   for D_ in ("D700", "D1083", "D1432", "D2000", "D3000")},
                            "block_clock": round(float(np.mean(((F.e_cl_block > 0).astype(int).to_numpy() == y)[k])), 3),
                            "futures_edge": round(float(np.mean(((F.e_f > 0).astype(int).to_numpy() == y)[k])), 3)}
print(json.dumps(out, indent=1))
(Path(__file__).resolve().parents[1] / "results" / "iter9_momoney_500.json").write_text(json.dumps(out, indent=1))
