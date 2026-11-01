"""X140 refit (panel iter12 assumptions P1, the pre-registered folds): the R3 model class (final_rule FEATS 'rule' and
'activity', train2 PARAMS, 300 rounds) refitted on BUILD-stable 08-14..09-10 and scored on STUDY-stable 09-11..25 and
VALIDATE-stable 09-26..10-11 (BTC 5m windows of the UTC hours 02/08/14/20; code13/fetch_stable_build.py and
fetch_stable.py tapes). Also the bin-level side of the refitted presence score (side_metrics) and the cheaper-token share.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE))
import lightgbm as lgb  # noqa: E402
from features2 import Spot, build_panel, clean_tape  # noqa: E402
import final_rule as fr  # noqa: E402
from train2 import PARAMS, ROUNDS  # noqa: E402
from stable_score import tx_int, CL, NAME2ADDR  # noqa: E402
from train2 import side_metrics  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
B0, S0, V0, V1 = 1786665600, 1789084800, 1790380800, 1791763200


def main():
    from polyrea.analysis.updown import snap_price
    ws = []
    for dname in ("stable_build", "stable"):
        w = pd.read_parquet(C / f"it13/{dname}/windows.parquet")
        w["dir"] = dname
        ws.append(w)
    w = pd.concat(ws, ignore_index=True).drop_duplicates("cid").sort_values("start_ts").reset_index(drop=True)
    w["up_payout"] = np.nan
    tk = []
    for r in w.itertuples(index=False):
        f = C / f"it13/{r.dir}/t_{int(r.start_ts)}.parquet"
        if not f.exists():
            continue
        t = pd.read_parquet(f)
        if t.empty or "price" not in t:
            continue
        t = t[(t.ts >= r.start_ts - fr.PRE) & (t.ts < r.end_ts)]
        tk.append(pd.DataFrame({"cid": r.cid, "ts": t.ts.astype(np.int64), "side": t.side.astype(str), "asset": t.asset.astype(str),
                                "price": t.price.astype(float).map(snap_price).astype(np.float32), "size": t["size"].astype(np.float32),
                                "wallet": t.wallet.astype(str), "tx": tx_int(t.tx16)}))
    tk = pd.concat(tk, ignore_index=True)
    for c in ("cid", "asset", "wallet", "side"):
        tk[c] = tk[c].astype(str).astype("category")
    w = w[w.cid.isin(set(tk.cid.astype(str)))].reset_index(drop=True)
    from stable_score import load_fills
    ct = load_fills(w)  # hist_btc to 10-08 + activity_*.parquet after it (no double count)
    from polyrea.adapters.spot import binance_seconds
    rows, _ = binance_seconds("btc", B0 - 7200, V1)
    a = np.asarray(rows, dtype=float).reshape(-1, 2)
    sp = Spot(a[:, 0].astype(np.int64), a[:, 1])
    toks = set(w.up_token) | set(w.down_token)
    buys = ct[(ct.side == "BUY") & ct.token_id.isin(toks)].copy()
    own_rows = tk[tk.wallet.astype(str).isin(set(CL))]
    taker_pairs = set(zip(own_rows.tx, own_rows.wallet.astype(str)))
    buys["role"] = ["taker" if (x, y) in taker_pairs else "maker" for x, y in zip(buys.tx, buys.wallet)]
    mk = buys[buys.role == "maker"].copy()
    clean = clean_tape(tk, set(ct.tx), set(CL))
    panel = build_panel(w, sp, clean, mk)
    panel = fr._add_clock(panel)
    st_of = dict(zip(w.cid, w.start_ts))
    panel["start"] = panel.cid.map(st_of)
    fold = np.where(panel.start < S0, "build", np.where(panel.start < V0, "study", "validate"))
    res = {"windows": {k: int(panel.cid[fold == k].nunique()) for k in ("build", "study", "validate")}, "maker_fills": int(len(mk))}
    b = panel[fold == "build"]
    for nm in ("rule", "activity"):
        m = lgb.train(PARAMS, lgb.Dataset(b[fr.FEATS[nm]], b["y"]), ROUNDS)
        panel["p_" + nm] = m.predict(panel[fr.FEATS[nm]])
        res["importance_" + nm] = dict(sorted(zip(fr.FEATS[nm], m.feature_importance("gain").round(0).tolist()), key=lambda x: -x[1])[:10])
    for nm in ("rule", "activity"):
        mo = lgb.Booster(model_file=str(HERE.parent / "code" / f"presence3_{nm}.txt"))
        panel["q_" + nm] = mo.predict(panel[fr.FEATS[nm]])
    for k in ("study", "validate"):
        g = panel[fold == k]
        res[k] = {"refit_auc": fr._auc(g.y, g.p_rule), "refit_activity": fr._auc(g.y, g.p_activity),
                  "frozen_auc": fr._auc(g.y, g.q_rule), "frozen_activity": fr._auc(g.y, g.q_activity), "pos_rate": float(g.y.mean())}
        res[k]["refit_gain"] = res[k]["refit_auc"] - res[k]["refit_activity"]
        try:
            res[k]["refit_side"] = side_metrics(g, "p_rule")
            res[k]["refit_activity_side"] = side_metrics(g, "p_activity")["acc"]
        except Exception as ex:  # noqa: BLE001
            res[k]["side_error"] = repr(ex)[:200]
        pw = {}
        for addr, name in CL.items():
            yw = fr._wallet_labels(g, w[w.cid.isin(set(g.cid))], mk[mk.cid.isin(set(g.cid))], addr)
            if yw.sum():
                pw[name] = {"refit_auc": fr._auc(yw, g.p_rule.to_numpy()), "refit_activity": fr._auc(yw, g.p_activity.to_numpy())}
        res[k]["per_wallet"] = pw
    (HERE.parent / "results/iter13_stable_refit.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float)[:5000])


if __name__ == "__main__":
    main()
