"""X154 step 3-4 (assumptions panel iter-10 P2), historical part: do the wallet and the fast Feed-P makers share the
INCREMENT of their levels on synchronous re-pricings (16-22 Oct, development, filled orders only = censored)?

Rows: the wallet's filled maker orders (ledger_rows_iter10, all classes and the quiet class separately). Partner: a
filled BUY maker order of one of the six fast makers (0xed446954, 0x51dbdd2b, 0xaeb90af4, 0xe8e1b119, 0x2005d16a,
0x893575c7) on the SAME token signed within +-60 ms of the wallet's order (nearest one). dV = the order's price minus
the same maker's previous filled order price on that token (each maker's own predecessor, fill-selected for both).
Statistics per pair set: Pearson corr(dV_w, dV_peer), sign agreement (non-zero both), share |dV_w - dV_peer| <= 1c.
Null: the partner's order replaced by that maker's filled order on the token nearest to t - delta, delta uniform in
[2, 30] s (2,000 draws of the whole set). Pre-registered by the panel: shared increment iff corr >= 0.8 and
|dV_w - dV_peer| <= 1c on >= 60%; own model iff corr <= 0.3; between = partial sharing.
Output: results/shared_increment.json
"""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
C = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
FAST = ["0xed446954680979932092e970b443e6ae61e34f76", "0x51dbdd2b19427dc8e88bb15a4046a38d8427f9b3",
        "0xaeb90af434ee5f40544c96086ffb65bb4d3a59f9", "0xe8e1b119302ae410e77b2af7d7456809007549dd",
        "0x2005d16a84ceefa912d4e380cd32e7ff827875ea", "0x893575c7d99542163c6b6e8a0fe5af0b6d217daa"]


def stats_of(dw, dp):
    dw, dp = np.asarray(dw, float), np.asarray(dp, float)
    k = np.isfinite(dw) & np.isfinite(dp)
    dw, dp = dw[k], dp[k]
    if len(dw) < 10 or np.std(dw) == 0 or np.std(dp) == 0:
        return None
    nz = (dw != 0) & (dp != 0)
    return {"n": int(len(dw)), "corr": round(float(np.corrcoef(dw, dp)[0, 1]), 3),
            "sign_agree": round(float((np.sign(dw[nz]) == np.sign(dp[nz])).mean()), 3) if nz.any() else None,
            "within_1c": round(float((np.abs(dw - dp) <= 0.01 + 1e-9).mean()), 3)}


def main():
    L = pd.read_parquet(C / "ledger_rows_iter10.parquet", columns=["salt", "sign_ms", "cid", "oi", "price", "cls", "event"])
    o = pd.read_parquet(C / "orders.parquet", columns=["salt", "token_id"])
    L = L.merge(o, on="salt", how="left").sort_values(["token_id", "sign_ms"])
    L["dv"] = L.groupby("token_id").price.diff()
    cols = ["maker", "side", "token_id", "price", "sign_ms", "idx", "salt"]
    parts = [pd.read_parquet(p, columns=cols) for p in sorted(glob.glob(str(C / "calldata_pub/*.parquet")))]
    parts.append(pd.read_parquet(C / "calldata_all.parquet", columns=cols))
    P = pd.concat(parts, ignore_index=True)
    P["maker"] = P.maker.str.lower()
    P = P[(P.idx >= 0) & P.maker.isin(FAST) & (P.side == 0) & (P.sign_ms > 1.7e12) & (P.sign_ms < 1.8e12)]
    P = P.drop_duplicates("salt").sort_values(["maker", "token_id", "sign_ms"])
    P["dv"] = P.groupby(["maker", "token_id"]).price.diff()
    P["token_id"] = P.token_id.astype(str)
    L["token_id"] = L.token_id.astype(str)
    idx = {k: (g.sign_ms.to_numpy(float), g.dv.to_numpy(float)) for k, g in P.groupby(["maker", "token_id"])}
    rng = np.random.default_rng(3)
    out = {}
    for name, sub in (("all", L), ("quiet", L[L.cls == "quiet"])):
        pairs = []
        for r in sub.itertuples():
            best = None
            for mkr in FAST:
                v = idx.get((mkr, r.token_id))
                if v is None:
                    continue
                ts, dv = v
                j = np.searchsorted(ts, r.sign_ms)
                for jj in (j - 1, j):
                    if 0 <= jj < len(ts) and abs(ts[jj] - r.sign_ms) <= 60 and (best is None or abs(ts[jj] - r.sign_ms) < best[0]):
                        best = (abs(ts[jj] - r.sign_ms), mkr, jj)
            if best is not None:
                pairs.append((r.dv, best[1], r.token_id, r.sign_ms, idx[(best[1], r.token_id)][1][best[2]]))
        if not pairs:
            out[name] = None
            continue
        dw = np.array([p[0] for p in pairs], float)
        dp = np.array([p[4] for p in pairs], float)
        real = stats_of(dw, dp)
        by = {}
        for mkr in FAST:
            k = np.array([p[1] == mkr for p in pairs])
            if k.sum() >= 10:
                by[mkr[:10]] = stats_of(dw[k], dp[k])
        nulls = []
        for _ in range(2000):
            dpn = np.empty(len(pairs))
            for i, (_, mkr, tok, t, _) in enumerate(pairs):
                ts, dv = idx[(mkr, tok)]
                tt = t - rng.uniform(2000, 30000)
                j = int(np.clip(np.searchsorted(ts, tt), 0, len(ts) - 1))
                dpn[i] = dv[j]
            s = stats_of(dw, dpn)
            if s:
                nulls.append(s["corr"])
        nulls = np.array(nulls)
        out[name] = {"pairs": len(pairs), "of_orders": int(len(sub)), "real": real, "by_maker": by,
                     "null_corr_p50_p95": [round(float(np.percentile(nulls, 50)), 3), round(float(np.percentile(nulls, 95)), 3)],
                     "p_null_ge_real": round(float((nulls >= (real or {}).get("corr", 9)).mean()), 4) if real else None}
    v = out.get("all") or {}
    rc = (v.get("real") or {})
    verdict = ("shared increment" if rc.get("corr", 0) >= 0.8 and rc.get("within_1c", 0) >= 0.6 else
               "own model" if rc.get("corr", 1) <= 0.3 else "partial sharing")
    out["verdict_preregistered"] = verdict
    (RES / "shared_increment.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
