"""Iteration 8 (A1 / X69): VALIDATE (2026-10-27..30, aggregate only) metrics of rule R6 = R3/R5 on BTC 5m (frozen
presence3 models) + the R3-class BTC 15m model (presence15 models, code8/train15.py) over the union universe:
pooled presence AUC and activity baseline, side (bins where exactly one side fills), block-clock price within a tick
(last clean print - 0.01), per-window PnL correlation (rule expectation sum p x (payout - rule price) vs the cluster's
maker-fill PnL), each per family and pooled, plus per-wallet presence.
    python code8/union_val.py
"""
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE.parent / "code4"))
import train2 as T  # noqa: E402
from train6 import add_clock, CLOCK  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
V0, V1 = 1793059200, 1793404800
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
      "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
FE = {"rule": T.SETS["all_path_xwin"] + CLOCK, "activity": T.SETS["activity"]}


def fam_panel(kind):
    if kind == "5m":
        p = pd.concat([pd.read_parquet(C / "exam" / f"panel_day_{d}.parquet") for d in range(V0, V1, 86400)], ignore_index=True)
        p = p[[c for c in p.columns if not c.startswith("p_")]]
        pref = "presence3"
        w = pd.read_parquet(C / "exam" / "windows_5m.parquet")
        f = pd.read_parquet(C / "exam" / "fills_holdout.parquet")
    else:
        p = pd.concat([pd.read_parquet(C / "p15" / f"panel15_day_{d}.parquet") for d in range(V0, V1, 86400)], ignore_index=True)
        pref = "presence15"
        w = pd.read_parquet(C / "t15" / "windows_15m.parquet")
        f = pd.read_parquet(C / "p15" / "cluster_btc15m_fills.parquet")
    p = add_clock(p)
    for nm, cols in FE.items():
        p["p_" + nm] = lgb.Booster(model_file=str(HERE.parent / "code" / f"{pref}_{nm}.txt")).predict(p[cols])
    w = w[(w.start_ts >= V0) & (w.start_ts < V1)]
    f = f[(f.role == "maker") & (f.side == "BUY")]
    f = f.assign(token_id=f.token_id.astype(str))
    up = dict(zip(w.up_token.astype(str), w.cid))
    dn = dict(zip(w.down_token.astype(str), w.cid))
    f = f[f.token_id.isin(set(up) | set(dn))].copy()
    f["c"] = [up.get(t, dn.get(t)) for t in f.token_id]
    f["is_up"] = f.token_id.isin(set(up))
    pay = dict(zip(w.cid, w.up_payout))
    f["won"] = [pay[c] if u else 1 - pay[c] for c, u in zip(f.c, f.is_up)]
    return p, w, f


def main():
    out = {}
    pans = {}
    for kind in ("5m", "15m"):
        p, w, f = fam_panel(kind)
        pans[kind] = p
        r = {"bins": int(len(p)), "pos": int(p.y.sum()), "presence_auc": round(T.auc(p.y, p.p_rule), 4),
             "baseline": round(T.auc(p.y, p.p_activity), 4)}
        s = T.side_metrics(p, "p_rule")
        r["side"] = {"n": s["n"], "acc": round(s["acc"], 4)}
        r["side_activity"] = round(T.side_metrics(p, "p_activity")["acc"], 4)
        wal = ((f.won - f.price) * f.shares).groupby(f.c).sum()
        pr = p.dropna(subset=["won_s"]).copy()
        pr["rule_pnl"] = pr.p_rule * (pr.won_s - (pr.last_s.fillna(0.5) - 0.01).round(2))
        j = pd.concat([wal.rename("wallet"), pr.groupby("cid").rule_pnl.sum().rename("rule")], axis=1).dropna()
        r["pnl"] = {"windows": int(len(j)), "pearson": round(float(j.corr().iloc[0, 1]), 4),
                    "spearman": round(float(j.corr(method="spearman").iloc[0, 1]), 4)}
        r["maker_fills"] = int(len(f))
        out[kind] = r
        out[kind + "_pnl_frame"] = j
    u = pd.concat([pans["5m"], pans["15m"]], ignore_index=True)
    s = T.side_metrics(u, "p_rule")
    jj = pd.concat([out.pop("5m_pnl_frame"), out.pop("15m_pnl_frame")])
    out["union"] = {"presence_auc": round(T.auc(u.y, u.p_rule), 4), "baseline": round(T.auc(u.y, u.p_activity), 4),
                    "side": {"n": s["n"], "acc": round(s["acc"], 4)}, "side_activity": round(T.side_metrics(u, "p_activity")["acc"], 4),
                    "pnl": {"windows": int(len(jj)), "pearson": round(float(jj.corr().iloc[0, 1]), 4),
                            "spearman": round(float(jj.corr(method="spearman").iloc[0, 1]), 4)}}
    (HERE.parent / "results" / "iter8_union_val.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
