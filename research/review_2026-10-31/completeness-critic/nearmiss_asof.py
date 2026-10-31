"""Time-sensitivity of the A1 near misses: refetch user-pnl now (scratch cache) and re-apply A1 at the frozen as_of
(2026-10-30, reproduces the record) and at 2026-10-31 (one more complete day). Holm uses the recorded p_pre of the
other 499 wallets with this wallet's p replaced."""
import json, sys
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
import numpy as np
from polyrea.adapters.polymarket import PolymarketData
from polyrea.workflows.screen import wallet_pnl_metrics, apply_criteria
from polyrea.stats import significance as S
from polyrea.analysis.pnl import daily_frame
OUT = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/completeness-critic"
A1 = json.load(open("/home/user/PolymarketResearchAgent/research/stage_a/stage_a1.json"))["wallets"]
pvec = {r["wallet"]: (r["metrics"].get("p_pre", 1.0) if (r["metrics"].get("pre_selection_days") or 0) >= 60 else 1.0) for r in A1}
pvec = {k: (1.0 if v is None or not np.isfinite(v) else v) for k, v in pvec.items()}
names = {r["wallet"]: (r["name"], r["rank"]) for r in A1}
targets = ["0x60a92c8620846d81f5ea17b0564e0d4b7c545a71", "0xa797d6bd8fe6e404bb4d8e4ab3d97c38336fdede", "0x41e2e1ccf1e4940029af02259a31c6b89b9fa354",
           "0xeea3f08e8a36081233e4c4b4142fd61a7b56a6a2", "0xc8b9a30184244d427169cf62485dde6041b2b836", "0xc0e4f49b80a2162aa8c1c1ad1bd0867574e3dd38",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3", "0xc23dc0eca9e1c2e293de8911b9ac254f0bcd82c8", "0x00110b8ef00db2a1a6bbe1198e52fc4eb5a84333",
           "0xee65685de42f8de9a03b4c53ee77d56a20d2cfc9", "0x31864feb9d25dee93728c6225ba891530967e9ca"]
pm = PolymarketData()
res = {}
for w in targets:
    body, src = pm.user_pnl(w, max_age=0)
    pts = body.get("points") or []
    res[w] = {"name": names[w][0], "rank": names[w][1], "last_point_ts": max(int(p.get("timestamp") or 0) for p in pts) if pts else None}
    for tag, as_of in (("frozen_1030", 1793318400), ("asof_1031", 1793404800)):
        m = wallet_pnl_metrics(pts, as_of)
        df = daily_frame(pts, as_of=as_of)
        m["deflated_sharpe"] = S.deflated_sharpe_ratio(df["d_economic_pnl"].iloc[1:].to_numpy(), n_trials=500)
        pv = dict(pvec); pv[w] = m["p_pre"] if m.get("pre_selection_days", 0) >= 60 else 1.0
        keys = list(pv); h = S.holm_bonferroni([pv[k] for k in keys]); m["p_holm_pre"] = h[keys.index(w)]
        reasons = apply_criteria(m)
        res[w][tag] = {"last_30d": round(m["last_30d_pnl"]), "median_month": round(m["median_month_pnl"] or 0), "pre_days": m["pre_selection_days"],
                       "p_holm": float(m["p_holm_pre"]), "p_boot": m.get("p_boot_pre"), "dsr": float(m["deflated_sharpe"]), "sharpe": round(float(m["annual_sharpe"]), 2),
                       "pos_weeks": round(float(m["share_positive_weeks"]), 3), "pos_months": round(float(m["share_positive_months"]), 3), "reasons": [x[:45] for x in reasons]}
    print(names[w], json.dumps(res[w]), flush=True)
json.dump(res, open(f"{OUT}/nearmiss_asof.json", "w"), indent=1, default=float)
