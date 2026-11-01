"""Examiner round 2: the wallets' own persistence (polyrea.tools.assess_persistence) at the latest full day
(as_of = 2026-11-01 00:00 UTC: days through 10-31), one-off bonuses removed by the tool, plus the last 14 daily
economic PnL values per wallet and the pooled cluster series (exam cache)."""
from __future__ import annotations

import json

import numpy as np

from r2_common import CLUSTER, RES

from polyrea.tools import assess_persistence, _pm  # noqa: E402
from polyrea.analysis.pnl import daily_frame  # noqa: E402
from polyrea.stats.persistence import persistence_report  # noqa: E402

AS_OF = 1793491200


def slim(v):
    if isinstance(v, dict):
        return {k: slim(x) for k, x in v.items() if not isinstance(x, list)}
    return v


def main():
    out = {"as_of": AS_OF}
    tot = None
    for a, n in CLUSTER.items():
        r = assess_persistence(a, as_of=AS_OF)
        body, _ = _pm().user_pnl(a, max_age=None)
        df = daily_frame(body.get("points") or [], as_of=AS_OF)
        s = df["d_economic_pnl"].iloc[1:]
        out[n] = {"persistence": slim(r.get("derived", {})), "bonuses_removed": r.get("observed", {}).get("one_off_bonuses_removed"),
                  "last_14_days": {str(k)[:10]: round(float(v), 1) for k, v in s.iloc[-14:].items()},
                  "last_7_sum": round(float(s.iloc[-7:].sum()), 1), "last_30_sum": round(float(s.iloc[-30:].sum()), 1)}
        tot = s if tot is None else tot.add(s, fill_value=0.0)
    rep = persistence_report(tot.to_numpy(), recent_days=30)
    out["cluster_pooled"] = slim({"persistence": rep.__dict__ if hasattr(rep, "__dict__") else str(rep)})
    out["cluster_last_14_days"] = {str(k)[:10]: round(float(v), 1) for k, v in tot.iloc[-14:].items()}
    (RES / "exam_r2_persistence.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
