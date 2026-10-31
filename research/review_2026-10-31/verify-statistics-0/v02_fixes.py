"""Test the two proposed corrections over all 500 wallets.

(a) share_positive_{weeks,months} computed over weeks/blocks whose |sum| > tol
    (tol=0 => exclude exact zeros only), everything else unchanged.
(b) start each wallet's record at first real activity: first day where the
    running sum of |daily economic PnL| exceeds `thr`; rerun the full screen
    (metrics, Holm over 500, bootstrap, DSR) on the trimmed series.
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("/home/user/PolymarketResearchAgent")
sys.path.insert(0, str(REPO))
from polyrea.workflows import screen as SC  # noqa: E402
from polyrea.analysis.pnl import daily_frame, weekly_sums, monthly_blocks  # noqa: E402
from polyrea.stats import significance as S  # noqa: E402

OUT = Path(__file__).parent
blob = json.load(gzip.open(OUT / "points.json.gz", "rt"))
as_of, points = blob["as_of"], blob["points"]
a1 = json.loads((REPO / "research/stage_a/stage_a1.json").read_text())
rows = a1["wallets"]
wallets = [r["wallet"] for r in rows]
stored_pass = set(a1["evidence"]["derived"]["a1_pass"])
name = {r["wallet"]: r["name"] for r in rows}
rank = {r["wallet"]: r["rank"] for r in rows}
MO = "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"
crit = SC.CRITERIA


def screen(pts_by_w):
    res = {w: SC.wallet_pnl_metrics(pts_by_w[w], as_of) for w in wallets}
    p_pre = [res[w].get("p_pre", 1.0) if res[w].get("pre_selection_days", 0) >= crit.min_pre_selection_days else 1.0 for w in wallets]
    for w, ph in zip(wallets, S.holm_bonferroni(p_pre)):
        res[w]["p_holm_pre"] = ph
    for w in wallets:
        if res[w].get("history_days", 0) > 0:
            d = daily_frame(pts_by_w[w], as_of=as_of)["d_economic_pnl"].iloc[1:].to_numpy()
            res[w]["deflated_sharpe"] = S.deflated_sharpe_ratio(d, n_trials=len(wallets))
    return res


# ---------- baseline
base = screen(points)
base_pass = {w for w in wallets if not SC.apply_criteria(base[w])}
assert base_pass == stored_pass, "baseline mismatch"
print("baseline A1 passes:", len(base_pass))

# ---------- (a) exclude inactive weeks/blocks from denominators
def series(w, pts=None):
    df = daily_frame(pts if pts is not None else points[w], as_of=as_of)
    if df.empty or "d_economic_pnl" not in df:
        return None
    return df["d_economic_pnl"].iloc[1:]


print("\n(a) exclude inactive weeks/blocks from the share denominators")
for wk_tol, blk_tol in [(0, 0), (1, 1), (10, 10), (100, 100), (1000, 5000)]:
    newpass = set()
    for w in wallets:
        m = dict(base[w])
        d = series(w)
        if d is None or m.get("history_days", 0) == 0:
            continue
        wk = weekly_sums(d)
        mb = np.array(monthly_blocks(d))
        wk_a = wk[np.abs(wk) > wk_tol]
        mb_a = mb[np.abs(mb) > blk_tol]
        m["share_positive_weeks"] = float((wk_a > 0).mean()) if len(wk_a) else None
        m["share_positive_months"] = float((mb_a > 0).mean()) if len(mb_a) else None
        if not SC.apply_criteria(m):
            newpass.add(w)
    print(f"  tol week ${wk_tol} / block ${blk_tol}: passes={len(newpass)}  new={[name[w] for w in newpass - base_pass]}  lost={[name[w] for w in base_pass - newpass]}")
    if wk_tol == 0:
        d = series(MO)
        wk = weekly_sums(d); mb = np.array(monthly_blocks(d))
        print(f"    mo-money: pos weeks {(wk[wk!=0]>0).mean():.3f} ({(wk[wk!=0]>0).sum()}/{(wk!=0).sum()}), pos blocks {(mb[mb!=0]>0).mean():.3f} ({(mb[mb!=0]>0).sum()}/{(mb!=0).sum()})")

# ---------- (b) trim leading dormancy
def trim_points(pts, thr):
    df = daily_frame(pts, as_of=as_of)
    if df.empty or "d_economic_pnl" not in df:
        return pts, 0
    d = df["d_economic_pnl"].iloc[1:]
    run = d.abs().cumsum()
    hit = np.nonzero(run.to_numpy() > thr)[0]
    if len(hit) == 0:
        return pts, 0
    k = int(hit[0])
    if k == 0:
        return pts, 0
    start_day = d.index[k]  # first kept PnL day (day_end stamp)
    anchor = int((start_day - pd.Timedelta(days=1)).timestamp())  # level row that gets dropped
    kept = [p for p in pts if p["timestamp"] >= anchor]
    # make sure the anchor midnight exists so the first diff is a real day
    assert any(p["timestamp"] == anchor for p in kept), "no anchor point"
    return kept, k


print("\n(b) trim leading dormancy, full rescreen with Holm/bootstrap/DSR")
for thr in [0.0, 100.0, 1000.0, 5000.0]:
    tp, ntrim = {}, {}
    for w in wallets:
        tp[w], ntrim[w] = trim_points(points[w], thr)
    res = screen(tp)
    newpass = {w for w in wallets if not SC.apply_criteria(res[w])}
    print(f"  thr ${thr:,.0f}: wallets trimmed={sum(1 for v in ntrim.values() if v>0)}  passes={len(newpass)}  new={[(name[w], ntrim[w]) for w in newpass - base_pass]}  lost={[name[w] for w in base_pass - newpass]}")
    if thr == 1000.0:
        m = res[MO]
        keys = ["history_days", "first_day", "pre_selection_days", "p_pre", "p_holm_pre", "p_boot_pre", "deflated_sharpe", "annual_sharpe", "last_30d_pnl", "median_month_pnl", "share_positive_weeks", "share_positive_months", "monthly_pnl_recent_first"]
        for k in keys:
            print(f"    mo-money {k}: {m.get(k)}")
        order = sorted(wallets, key=lambda w: res[w].get("p_pre", 1) if res[w].get("pre_selection_days", 0) >= 60 else 1)
        print("    rank of mo-money p_pre among 500:", order.index(MO) + 1, " smallest p_pre wallets:", [(name[w], f"{res[w]['p_pre']:.2e}") for w in order[:3]])
        print("    reasons:", SC.apply_criteria(m))
        # survivors under trim: any reason changes?
        for w in sorted(base_pass):
            if ntrim[w]:
                print(f"    survivor {name[w]} trimmed {ntrim[w]}d, still passes={not SC.apply_criteria(res[w])}")
        json.dump({w: {"trimmed_days": ntrim[w], "reasons": SC.apply_criteria(res[w])} for w in wallets}, open(OUT / "trim1000.json", "w"), indent=1)

# ---------- counterfactual: drop only the Feb-2026 test trade points of mo-money
pts = points[MO]
df = daily_frame(pts, as_of=as_of)
d = df["d_economic_pnl"].iloc[1:]
first_june = d.index[np.nonzero((d.index >= pd.Timestamp("2026-03-01", tz="UTC")) & (d.to_numpy() != 0))[0][0]]
anchor = int((first_june - pd.Timedelta(days=1)).timestamp())
cf = dict(points); cf[MO] = [p for p in pts if p["timestamp"] >= anchor]
res = screen(cf)
print(f"\ncounterfactual: mo-money record starts {first_june.date()} (first nonzero day after Feb); reasons={SC.apply_criteria(res[MO])}; pos weeks {res[MO]['share_positive_weeks']:.3f} pos months {res[MO]['share_positive_months']:.3f} p_holm {res[MO]['p_holm_pre']:.2e} history {res[MO]['history_days']}d pre {res[MO]['pre_selection_days']}d")
cfpass = {w for w in wallets if not SC.apply_criteria(res[w])}
print("  passes:", len(cfpass), " others changed:", [name[w] for w in (cfpass ^ base_pass) - {MO}])
