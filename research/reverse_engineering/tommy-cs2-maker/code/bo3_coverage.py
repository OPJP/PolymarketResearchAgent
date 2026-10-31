"""Does the wallet's league selection follow live-data coverage? bo3.gg match details carry live_coverage /
live_coverage_source / live_updates. Match bo3.gg matches (20-22 Oct, development) to Polymarket CS2 events by team
names and compare coverage fields between events the wallet traded and those it skipped."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from polyrea.adapters.http import shared_client  # noqa: E402
from common import OUT, RES  # noqa: E402


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def main() -> None:
    h = shared_client()
    b = pd.read_parquet(OUT / "bo3_matches_20_22.parquet")
    b = b[b.parsed.isin(["done", "waiting", "rejected"])]
    det = []
    for slug in b.slug:
        try:
            g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{slug}", {}, adapter="bo3gg.match", max_age=None)
        except Exception as e:  # noqa: BLE001
            continue
        det.append({"slug": slug, "lc": json.dumps(g.get("live_coverage")), "lcs": json.dumps(g.get("live_coverage_source")),
                    "lca": json.dumps(g.get("live_coverage_advantage")), "lu": json.dumps(g.get("live_updates"))[:80],
                    "tier": g.get("tier"), "tour": g.get("tournament_id"), "parsed": g.get("parsed_status"),
                    "start": g.get("start_date")})
    d = pd.DataFrame(det)
    u = pd.read_parquet(OUT / "universe.parquet")
    u = u[(u.smt == "moneyline") & (u.gs_ts >= 1792454400) & (u.gs_ts < 1792713600)].copy()
    traded = set(pd.read_parquet(OUT / "orders.parquet", columns=["cid"]).cid)
    ev_tr = set(u.loc[u.cid.isin(traded), "event_slug"])
    rows = []
    for r in u.itertuples():
        outs = json.loads(r.outcomes) if isinstance(r.outcomes, str) else r.outcomes
        a, c = norm(outs[0])[:6], norm(outs[1])[:6]
        hit = d[d.slug.map(lambda s: a in norm(s) and c in norm(s))]
        rows.append({"event": r.event_slug, "league": r.league, "traded": r.event_slug in ev_tr, "matched": len(hit) > 0,
                     "lc": hit.lc.iloc[0] if len(hit) else None, "lcs": hit.lcs.iloc[0] if len(hit) else None,
                     "lca": hit.lca.iloc[0] if len(hit) else None, "bo3_tier": hit.tier.iloc[0] if len(hit) else None})
    x = pd.DataFrame(rows)
    res = {"bo3_details": len(d), "pm_events": len(x), "matched": int(x.matched.sum()),
           "by_traded": {str(k): {"n": len(s), "matched": int(s.matched.sum()), "lc": s.lc.value_counts(dropna=False).head(5).to_dict(),
                                  "lcs": s.lcs.value_counts(dropna=False).head(5).to_dict(), "bo3_tier": s.bo3_tier.value_counts(dropna=False).to_dict()}
                         for k, s in x.groupby("traded")}}
    json.dump(res, open(RES / "results/bo3_coverage.json", "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
