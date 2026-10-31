"""Which wallets fail exactly one or two A1 criteria, and does forming the Holm family
from only the wallets actually tested (>= 60 pre-selection days) change anything?"""
import collections
import json

import numpy as np

from common import SCR, board
from polyrea.stats import significance as S
from polyrea.workflows.screen import CRITERIA, apply_criteria

res = json.load(open(f"{SCR}/a1_recomputed.json"))
rows = board()
wallets = [r["user_id"].lower() for r in rows]
names = {r["user_id"].lower(): (r["rank"], r["user_name"]) for r in rows}


def tag(reason):
    for k, t in [("insufficient pre", "PRE<60"), ("Holm", "HOLM"), ("bootstrap", "BOOT"), ("deflated", "DSR"), ("last-30d", "LAST30"),
                 ("median monthly", "MEDIAN"), ("positive months", "POSMONTHS"), ("annualized Sharpe", "SHARPE"), ("positive weeks", "POSWEEKS"),
                 ("no PnL", "NOHIST")]:
        if k in reason:
            return t
    return reason


fails = {w: [tag(r) for r in apply_criteria(res[w])] if "error" not in res[w] else ["ERR"] for w in wallets}
cnt = collections.Counter(len(v) for v in fails.values())
print("number of failed criteria per wallet:", dict(sorted(cnt.items())))
print("\nwallets failing exactly one criterion:")
for w in wallets:
    if len(fails[w]) == 1:
        m = res[w]
        g = lambda k, f: (format(m[k], f) if isinstance(m.get(k), (int, float)) else str(m.get(k)))
        print(f"  rank {names[w][0]:3d} {names[w][1][:28]:28s} {fails[w]} pre={m.get('pre_selection_days')} p_pre={g('p_pre','.2e')} holm={g('p_holm_pre','.3g')} boot={g('p_boot_pre','.3g')} dsr={g('deflated_sharpe','.4f')} sharpe={g('annual_sharpe','.2f')} posw={g('share_positive_weeks','.2f')} posm={g('share_positive_months','.2f')} med={g('median_month_pnl',',.0f')} last30={g('last_30d_pnl',',.0f')}")
print("\nwallets failing exactly two criteria:")
for w in wallets:
    if len(fails[w]) == 2:
        m = res[w]
        print(f"  rank {names[w][0]:3d} {names[w][1][:28]:28s} {fails[w]} pre={m.get('pre_selection_days')} holm={m.get('p_holm_pre'):.3g} boot={m.get('p_boot_pre')} dsr={m.get('deflated_sharpe')} sharpe={m.get('annual_sharpe')}")

# --- Holm family
tested = [w for w in wallets if res[w].get("pre_selection_days", 0) >= CRITERIA.min_pre_selection_days]
print(f"\nwallets with >= 60 pre-selection days (actually tested): {len(tested)} of {len(wallets)}")
p_t = [res[w]["p_pre"] for w in tested]
holm_t = dict(zip(tested, S.holm_bonferroni(p_t)))
changed = [w for w in tested if (res[w]["p_holm_pre"] > 0.05) != (holm_t[w] > 0.05)]
print("wallets whose Holm decision flips when the family = tested wallets only:", len(changed))
for w in changed:
    m = res[w]
    other = [f for f in fails[w] if f != "HOLM"]
    print(f"  rank {names[w][0]} {names[w][1]} p_pre={m['p_pre']:.3g} holm(500)={m['p_holm_pre']:.3g} holm({len(tested)})={holm_t[w]:.3g}; other failures: {other}")
# Holm-adjusted p of the borderline
srt = sorted(res[w]["p_pre"] for w in tested)
print("smallest raw p_pre values:", [f"{x:.2e}" for x in srt[:5]], "... number with raw p < 0.05/500:", sum(x < 0.05 / 500 for x in srt), "raw p < 0.05/%d:" % len(tested), sum(x < 0.05 / len(tested) for x in srt))
print("number significant at BH q=0.05 (stored p_bh_pre):", sum(res[w]["p_bh_pre"] < 0.05 for w in wallets))
json.dump(fails, open(f"{SCR}/a1_fail_tags.json", "w"))
