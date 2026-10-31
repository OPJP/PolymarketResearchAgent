"""Examiner: wallet persistence (polyrea.tools.assess_persistence) at the latest full day, plus the daily
economic PnL of the three wallets over the holdout days and the 30 days before H (user-pnl series)."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import numpy as np
from polyrea.tools import assess_persistence, _pm
from polyrea.analysis.pnl import daily_frame
from polyrea.stats.persistence import persistence_report  # noqa: F401

H = 1792713600
AS_OF = int(sys.argv[1]) if len(sys.argv) > 1 else 1793404800
W = {"momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
     "bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed"}
out = {"as_of": AS_OF}
tot = None
for n, a in W.items():
    r = assess_persistence(a, as_of=AS_OF)
    d = r.get("derived", {})
    keep = {}
    for k, v in d.items():
        keep[k] = {kk: ({k3: v[kk][k3] for k3 in ("statistic", "p_value", "n", "mean", "estimate") if k3 in v[kk]} if isinstance(v[kk], dict) else v[kk]) for kk in v if not isinstance(v[kk], list)}
    body, _ = _pm().user_pnl(a, max_age=6 * 3600)
    df = daily_frame(body.get("points") or [], as_of=AS_OF)
    s = df["d_economic_pnl"]
    idx = df.index if "day" not in df.columns else df["day"]
    days = [str(x)[:10] for x in idx]
    ser = dict(zip(days, [float(x) for x in s.to_numpy()]))
    out[n] = {"persistence": keep, "bonuses_removed": r.get("observed", {}).get("one_off_bonuses_removed"),
              "daily_last_40": dict(list(ser.items())[-40:])}
    print(n, json.dumps(keep, default=str)[:1500], flush=True)
(Path(__file__).resolve().parent.parent / "results" / "exam_persistence_raw.json").write_text(json.dumps(out, indent=1, default=str))
