"""Iteration 7, X96 step 1 (mechanics panel iter6 P5): V8 Math.random() with k extra draws per order (stride k + 1 =
1..9 generator positions between consecutive orders of a 5-order ladder burst, in both price orders, i.e. forward and
LIFO cache order), both mantissa conventions, DT in {0, 3} ms. A hit needs a consistent GF(2) system with >= 20
redundant equations. The panel tested strides 1-4; this extends to 9 (L = 40 symbolic outputs).
Output: results/v8stride_k8.json"""
import json, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(Path(__file__).resolve().parent))
res = {}
for variant in ("hi", "lo"):
    for DT in (0, 3):
        sys.argv = ["x", variant, str(DT), "5", "0"]
        if "v8salt_lib" in sys.modules:
            del sys.modules["v8salt_lib"]
        import v8salt_lib as V
        d = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/calldata_all.parquet", columns=["maker", "sign_ms", "salt", "price"])
        w = d[d.maker.str.lower() == V.W].copy()
        w["salt_i"] = w.salt.astype("int64")
        o = w.drop_duplicates("salt_i").sort_values("sign_ms").reset_index(drop=True)
        o["grp"] = (o.sign_ms.diff() > 3).cumsum()
        tried = hits = 0
        for g, gr in o.groupby("grp"):
            if len(gr) != 5:
                continue
            tried += 1
            gr = gr.sort_values("price")
            kb = [V.known_bits(int(s), int(t)) for s, t in zip(gr.salt_i, gr.sign_ms)]
            best = None
            for k in range(1, 10):
                for order in (list(range(5)), list(range(4, -1, -1))):
                    pos = [i * k for i in range(5)]
                    if max(pos) >= len(V.xs):
                        continue
                    eqs = []
                    for j, p_ in zip(order, pos):
                        eqs += V.eqs_for(p_, kb[j])
                    ok, red = V.solve(eqs)
                    if ok and red >= 20:
                        best = (k, red)
            if best:
                hits += 1
        res[f"{variant}_DT{DT}"] = {"bursts5": tried, "hits": hits}
        print(variant, DT, tried, hits, flush=True)
(ROOT / "research/reverse_engineering/tommy-cs2-maker/results/v8stride_k8.json").write_text(json.dumps(res, indent=1))
