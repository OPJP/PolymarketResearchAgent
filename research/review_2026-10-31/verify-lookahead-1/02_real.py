"""Rebuild run_sports_study's inputs for a wallet from the HTTP cache, check them
against the stored sports_study.json, and measure the effect of the delay grid."""
import json, pickle, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd
from polyrea.adapters.polymarket import PolymarketData
from polyrea.workflows.sports_study import load_games, game_prints, scoring_events, annotate, reaction_stats, _backtest, _replay

wallet = sys.argv[1]; max_games = int(sys.argv[2]); stored_path = sys.argv[3]; as_of = int(sys.argv[4]) if len(sys.argv) > 4 else None
out = Path(__file__).parent / "data" / f"{wallet[:10]}_{max_games}_{as_of}.pkl"
if out.exists():
    d = pickle.load(open(out, "rb"))
else:
    pm = PolymarketData(); t0 = time.time()
    loaded = load_games(wallet, 30, as_of, max_games, 11, pm)
    games, markets = loaded["games"], loaded["markets"]
    with ThreadPoolExecutor(6) as ex:
        frames = list(ex.map(lambda e: game_prints(e, markets, wallet, pm, "taker"), games))
    events = {e["event_slug"]: scoring_events(e["game"]) for e in games}
    split = int(np.median([e["start"] for e in games]))
    fit = [e["event_slug"] for e in games if e["start"] < split]
    test = [e["event_slug"] for e in games if e["start"] >= split]
    allp = pd.concat(frames, ignore_index=True); allp = allp[allp["side_kind"].notna()]
    d = {"allp": allp, "events": events, "fit": fit, "test": test, "n_games": len(games)}
    pickle.dump(d, open(out, "wb")); print("loaded in", round(time.time() - t0, 1), "s")
allp, events, fit, test = d["allp"], d["events"], d["fit"], d["test"]
stored = json.load(open(stored_path))
print("rebuilt: games", d["n_games"], "fit", len(fit), "test", len(test), "prints", len(allp), "wallet prints", int(allp["is_wallet"].sum()))
print("stored :", stored["observed"])

def annotated(slugs, delay):
    parts = [annotate(allp[allp["event_slug"] == s], events[s], delay) for s in slugs if (allp["event_slug"] == s).any()]
    return pd.concat(parts, ignore_index=True)

grid_d = [-10, -5, 0, 5, 10, 20, 30, 60]; grid_w = [10, 20, 30, 60, 120]
scan = []
for D in grid_d:
    a = annotated(fit, D)
    for W in grid_w:
        r = reaction_stats(a, W)
        scan.append({"delay": D, "window_s": W, "excess": r["wallet_share_reactive"] - r["others_share_reactive"]})
sdf = pd.DataFrame(scan).sort_values("excess", ascending=False)
print("\nFIT scan top 6 (rebuilt):"); print(sdf.head(6).to_string(index=False))
print("stored chosen D,W:", stored["derived"]["chosen_delay_s"], stored["derived"]["chosen_window_s"])
nonneg = sdf[sdf["delay"] >= 0].iloc[0]
print("argmax restricted to D>=0:", int(nonneg["delay"]), int(nonneg["window_s"]))
Dc, Wc = int(sdf.iloc[0]["delay"]), int(sdf.iloc[0]["window_s"])

# per-print 'true' wallclock of the latest play used (delay-independent): the play the print is attributed to
def attributed_wallclock(a_slugs, delay):
    rows = []
    for s in a_slugs:
        p = allp[allp["event_slug"] == s]
        if p.empty: continue
        a = annotate(p, events[s], delay)
        a["play_wallclock"] = a["ts"] - a["since"] - delay  # known = wallclock + delay; since = ts - known
        rows.append(a)
    return pd.concat(rows, ignore_index=True)

print(f"\nTEST backtest REACT(D, W={Wc}) on {len(test)} held-out games:")
for D in (-10, -5, 0, 5, 10):
    a = attributed_wallclock(test, D)
    bt = _backtest(a, Wc)
    sel = a[(a["since"] >= 0) & (a["since"] <= Wc) & (a["fav"] > 0) & a["payout"].notna()]
    pre = (sel["ts"] < sel["play_wallclock"]).mean()
    same = (sel["ts"] == sel["play_wallclock"]).mean()
    print(f"  D={D:>3}: trades {bt['trades']:>6} usd {bt['usd_traded']:>12,.0f} pnl {bt['pnl']:>9,.0f} return {bt['return_on_traded']:+.4f} per-game p {bt['per_game_p']:.3f} | share of selected trades before play wallclock {pre:.3f}, same second {same:.3f}")
print("stored backtest_test_games:", {k: stored["derived"]["backtest_test_games"][k] for k in ("trades", "pnl", "return_on_traded", "per_game_p")})
print("stored latency_degradation:", {k: (v["return_on_traded"], v["per_game_p"]) for k, v in stored["derived"]["latency_degradation"].items()})

# Also: at chosen D, does the TEST reaction/direction stat match stored?
r = reaction_stats(annotated(test, Dc), Wc)
print("\nTEST reaction at chosen D (rebuilt):", {k: r[k] for k in ("wallet_share_reactive", "others_share_reactive", "wallet_direction_agree", "wallet_n_reactive")})
print("stored                             :", {k: stored["derived"]["test_reaction"][k] for k in ("wallet_share_reactive", "others_share_reactive", "wallet_direction_agree", "wallet_n_reactive")})
