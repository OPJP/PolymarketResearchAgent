"""iteration 15, X176 (assumptions P4): print-level selection on the non-BTC 5m/15m families (no fitting).

Unit: every taker print (data-api taker tape) of the non-BTC 5m/15m windows the cluster traded in STUDY / VALIDATE /
after T0 (markets it never traded are not in this sample: a within-traded-market selection test). Label: the print's
transaction holds a cluster fill. The maker-BUY outcome of a print: a taker SELL of X is bought by makers as X, a taker
BUY of X is matched by makers buying the complement (mint) or selling X; the cluster only buys, so its outcome is X for
taker SELLs and not-X for taker BUYs. Frozen score (no fitting): s = 1[maker-BUY outcome is in the money (Binance S(T-3)
vs the TWAP-60 stand-in strike)] + 1[print in the first 20 s] + 0.5 x 1[taker size <= 2 x the family's configured size].
Reported: AUC (pooled and within-window by rank), recall and lift at the top-k = number of positives, against an
activity-only score (1[first 20 s] + taker size rank) and the itm part alone; opening prints separately.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
from nb_side import Spot, C, RES  # noqa: E402

FAM_SIZE = {"eth-5m": 50, "sol-5m": 50, "xrp-5m": 10, "bnb-5m": 10, "doge-5m": 10, "eth-15m": 30, "sol-15m": 30, "xrp-15m": 10,
            "bnb-15m": 10, "doge-15m": 40}


def main():
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    a = pd.read_parquet(C / "it15_nb_side.parquet")
    ctx = set(a.transactionHash.str.lower())
    a = a[a.fam.isin(FAM_SIZE) & (a.fold.str.startswith("STUDY") | a.fold.isin(["VALIDATE", "dev_after_T0"]))]
    mk = a.drop_duplicates("conditionId")[["conditionId", "slug", "fam", "sym", "st", "L", "K", "fold"]].reset_index(drop=True)
    print("markets", len(mk), flush=True)

    def get(r):
        rows, _, _ = pm.market_trades(r.conditionId, start=int(r.st) - 3600, end=int(r.st + r.L) + 60, taker_only=True)
        return r, rows
    recs = []
    with ThreadPoolExecutor(3) as ex:
        for r, rows in ex.map(get, mk.itertuples(index=False)):
            ups = {}
            for x in rows:
                t = int(x["timestamp"])
                if not (r.st <= t < r.st + r.L):
                    continue
                oc = str(x.get("outcome") or "").lower()
                if oc not in ("up", "down"):
                    continue
                sell = str(x.get("side", "")).upper() == "SELL"
                mb_up = (oc == "up") if sell else (oc != "up")
                recs.append((r.slug, r.fam, r.sym, r.fold, int(r.st), float(r.K), t, mb_up, float(x.get("size") or 0),
                             int(str(x.get("transactionHash", "")).lower() in ctx)))
    D = pd.DataFrame(recs, columns=["slug", "fam", "sym", "fold", "st", "K", "t", "mb_up", "size", "y"])
    sp = Spot()
    S = np.full(len(D), np.nan)
    for sym, g in D.groupby("sym"):
        S[g.index] = sp.close_at(sym, g.t.to_numpy(np.int64) - 3)
    D["itm_mb"] = np.where(np.isfinite(S) & np.isfinite(D.K), ((S > D.K) == D.mb_up).astype(float), np.nan)
    D["open"] = (D.t - D.st < 20).astype(float)
    D["small"] = (D["size"] <= 2 * D.fam.map(FAM_SIZE)).astype(float)
    D = D.dropna(subset=["itm_mb"]).reset_index(drop=True)
    D["score"] = D.itm_mb + D.open + 0.5 * D.small
    D["act"] = D.open + D["size"].rank(pct=True)
    out = {"prints": int(len(D)), "positives": int(D.y.sum()), "base_rate": round(float(D.y.mean()), 4)}

    def metr(g, col):
        if g.y.sum() == 0 or g.y.sum() == len(g):
            return None
        auc = roc_auc_score(g.y, g[col])
        k = int(g.y.sum())
        top = g.sort_values(col, ascending=False, kind="stable").head(k)
        rec = top.y.sum() / k
        return {"auc": round(float(auc), 4), "recall_at_k": round(float(rec), 4), "lift_at_k": round(float(rec / g.y.mean() * k / len(g)) if False else float(top.y.mean() / g.y.mean()), 3)}
    for nm, g in (("all", D), ("opening", D[D.open == 1]), ("later", D[D.open == 0])):
        out[nm] = {c: metr(g, c) for c in ("score", "itm_mb", "act")}
        out[nm]["n"] = int(len(g)); out[nm]["pos"] = int(g.y.sum())
    for fd in ("VALIDATE", "dev_after_T0"):
        g = D[D.fold == fd]
        out[f"all_{fd}"] = {c: metr(g, c) for c in ("score", "itm_mb", "act")}
    g = D[D.fold.str.startswith("STUDY")]
    out["all_STUDY"] = {c: metr(g, c) for c in ("score", "itm_mb", "act")}
    print(json.dumps(out, indent=1))
    (RES / "iter15_sel_open.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
