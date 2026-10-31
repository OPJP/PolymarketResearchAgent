"""Recompute stage A1 for all 500 wallets from the exact cached user-pnl bodies.

Reads the HTTP cache read-only (sqlite uri mode=ro), checks each body's sha256
against the one recorded in research/stage_a/stage_a1.json, then reruns
wallet_pnl_metrics + Holm + DSR + apply_criteria exactly like run_screen.
Writes points to points.json.gz (scratch) for later scripts.
"""
import gzip
import hashlib
import json
import sqlite3
import sys
import zlib
from pathlib import Path

import numpy as np

REPO = Path("/home/user/PolymarketResearchAgent")
sys.path.insert(0, str(REPO))
from polyrea.workflows import screen as SC  # noqa: E402
from polyrea.analysis.pnl import daily_frame  # noqa: E402
from polyrea.stats import significance as S  # noqa: E402

OUT = Path(__file__).parent
a1 = json.loads((REPO / "research/stage_a/stage_a1.json").read_text())
as_of = a1["evidence"]["subject"]["as_of"]
rows = a1["wallets"]
db = sqlite3.connect(f"file:{REPO/'.cache/http.sqlite'}?mode=ro", uri=True)

points = {}
mismatch = 0
for r in rows:
    src = r["metrics"].get("source") or {}
    url = src.get("url")
    want = src.get("body_sha256")
    cands = db.execute("SELECT body FROM responses WHERE url=?", (url,)).fetchall()
    found = None
    for (blob,) in cands:
        raw = zlib.decompress(blob)
        if hashlib.sha256(raw).hexdigest() == want:
            found = raw
    if found is None:
        mismatch += 1
        if cands:
            found = zlib.decompress(cands[0][0])
    body = (json.loads(found).get("data") or {}) if found else {}
    points[r["wallet"]] = body.get("points") or []
print(f"as_of={as_of}  wallets={len(rows)}  sha256 mismatches={mismatch}")
with gzip.open(OUT / "points.json.gz", "wt") as f:
    json.dump({"as_of": as_of, "points": points}, f)

# rerun screen exactly
results = {}
for r in rows:
    w = r["wallet"]
    results[w] = SC.wallet_pnl_metrics(points[w], as_of)
wallets = [r["wallet"] for r in rows]
crit = SC.CRITERIA
p_pre = [results[w].get("p_pre", 1.0) if results[w].get("pre_selection_days", 0) >= crit.min_pre_selection_days else 1.0 for w in wallets]
holm = S.holm_bonferroni(p_pre)
for w, ph in zip(wallets, holm):
    results[w]["p_holm_pre"] = ph
passes = []
diff = 0
for r in rows:
    w = r["wallet"]
    m = results[w]
    if m.get("history_days", 0) > 0:
        d = daily_frame(points[w], as_of=as_of)["d_economic_pnl"].iloc[1:].to_numpy()
        m["deflated_sharpe"] = S.deflated_sharpe_ratio(d, n_trials=len(rows))
    reasons = SC.apply_criteria(m)
    if not reasons:
        passes.append(w)
    if reasons != r["stage_a1_reasons"]:
        diff += 1
stored = set(a1["evidence"]["derived"]["a1_pass"])
print(f"recomputed A1 passes={len(passes)}  stored={len(stored)}  same set={set(passes)==stored}  reason-list diffs={diff}")

MO = "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"
m = results[MO]
print("mo-money reasons:", SC.apply_criteria(m))
df = daily_frame(points[MO], as_of=as_of)
d = df["d_economic_pnl"].iloc[1:]
print("first midnight point:", df.index.min().date(), " first d day:", d.index.min().date(), " n=", len(d))
from polyrea.analysis.pnl import weekly_sums, monthly_blocks
wk = weekly_sums(d)
mb = monthly_blocks(d)
print("weekly sums (oldest first):", [round(x) for x in wk])
print("30d blocks (recent first):", [round(x) for x in mb])
print(f"positive weeks {np.mean(wk>0):.3f} ({(wk>0).sum()}/{len(wk)}), exact-zero weeks {(wk==0).sum()}")
print(f"positive blocks {np.mean(np.array(mb)>0):.3f} ({sum(x>0 for x in mb)}/{len(mb)}), exact-zero blocks {sum(x==0 for x in mb)}")
nz = d[d != 0]
print("nonzero days in first 140:", [(str(i.date()), round(v, 2)) for i, v in d.iloc[:140][d.iloc[:140] != 0].items()][:20])
json.dump({w: {"reasons": SC.apply_criteria(results[w]), **{k: results[w].get(k) for k in ("history_days", "p_pre", "p_holm_pre", "p_boot_pre", "deflated_sharpe", "share_positive_weeks", "share_positive_months", "annual_sharpe", "last_30d_pnl", "median_month_pnl", "pre_selection_days")}} for w in wallets}, open(OUT / "a1_recomputed.json", "w"), indent=1, default=float)
