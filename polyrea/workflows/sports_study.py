"""In-play sports study: does a wallet trade on live game events, how fast, and
can a rule driven by public ESPN data reproduce and profit from it?

Hypothesis REACT(D, W): within W seconds after a scoring play becomes known
(play wall clock + information delay D), buy outcomes that the play favoured
(the scoring team on moneyline/spread, "Over" on totals).

Walk-forward: games are split by start time into FIT (older half) and TEST
(newer half). FIT chooses D and W; TEST measures, untouched, the wallet's
excess reaction vs. other takers and vs. a permutation null that shifts each
game's play timeline, the rule's backtest and the wallet's own outcome.
Decision features use only plays with wallclock + D <= decision time.
"""

from __future__ import annotations

import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from polyrea.adapters.espn import ESPN, LEAGUES, Game, team_matches
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.profile import resolution_info
from polyrea.evidence import Coverage, Evidence
from polyrea.stats.significance import hac_t_test, permutation_pvalue, stationary_bootstrap_pvalue
from polyrea.workflows.investigate import load_window

SPORTS_FEE_RATE = 0.05


def _outcome_side(outcome: str, game: Game) -> str | None:
    """'home' / 'away' for team outcomes, 'over' / 'under' for totals."""
    o = (outcome or "").strip().lower()
    if o in ("over", "under"):
        return o
    home_c = {"team": {"displayName": game.home, "shortDisplayName": game.home.split()[-1], "name": game.home.split()[-1], "location": " ".join(game.home.split()[:-1])}}
    away_c = {"team": {"displayName": game.away, "shortDisplayName": game.away.split()[-1], "name": game.away.split()[-1], "location": " ".join(game.away.split()[:-1])}}
    if team_matches(outcome, home_c):
        return "home"
    if team_matches(outcome, away_c):
        return "away"
    return None


def scoring_events(game: Game) -> pd.DataFrame:
    rows, prev = [], (0, 0)
    for p in game.plays:
        cur = (p.home_score, p.away_score)
        if cur != prev:
            rows.append({"ts": p.ts, "home_pts": cur[0] - prev[0], "away_pts": cur[1] - prev[1]})
        prev = cur
    return pd.DataFrame(rows)


def favoured(side: str, ev_home_pts: np.ndarray, ev_away_pts: np.ndarray) -> np.ndarray:
    if side == "home":
        return np.sign(ev_home_pts - ev_away_pts)
    if side == "away":
        return np.sign(ev_away_pts - ev_home_pts)
    if side == "over":
        return np.where(ev_home_pts + ev_away_pts > 0, 1, 0)
    if side == "under":
        return np.where(ev_home_pts + ev_away_pts > 0, -1, 0)
    return np.zeros_like(ev_home_pts)


def annotate(prints: pd.DataFrame, events: pd.DataFrame, delay: int, shift: int = 0) -> pd.DataFrame:
    """Per print: seconds since the latest scoring play known at the print, and whether it favoured the bought side.

    A play is known at wallclock + delay (+ shift for the permutation null).
    """
    out = prints.copy()
    if events.empty or out.empty:
        out["since"], out["fav"] = np.nan, 0
        return out
    known = events["ts"].to_numpy() + delay + shift
    order = np.argsort(known)
    known = known[order]
    hp = events["home_pts"].to_numpy()[order]
    ap = events["away_pts"].to_numpy()[order]
    idx = np.searchsorted(known, out["ts"].to_numpy(), side="right") - 1
    has = idx >= 0
    out["since"] = np.where(has, out["ts"].to_numpy() - known[np.clip(idx, 0, None)], np.nan)
    fav = np.zeros(len(out))
    for side in out["side_kind"].dropna().unique():
        m = (out["side_kind"] == side).to_numpy() & has
        fav[m] = favoured(side, hp[idx[m]], ap[idx[m]])
    out["fav"] = fav
    return out


def reaction_stats(df: pd.DataFrame, window: int) -> dict[str, Any]:
    w = df[df["is_wallet"]]
    o = df[~df["is_wallet"]]

    def share(x):
        return float(((x["since"] >= 0) & (x["since"] <= window)).mean()) if len(x) else float("nan")

    def agree(x):
        r = x[(x["since"] >= 0) & (x["since"] <= window) & (x["fav"] != 0)]
        return float((r["fav"] > 0).mean()) if len(r) else float("nan"), int(len(r))

    sw, so = share(w), share(o)
    aw, nw = agree(w)
    ao, no = agree(o)
    return {"window_s": window, "wallet_share_reactive": sw, "others_share_reactive": so, "wallet_direction_agree": aw, "wallet_n_reactive": nw, "others_direction_agree": ao, "others_n_reactive": no}


def load_games(wallet: str, days: int, as_of: int | None, max_games: int, seed: int, pm: PolymarketData) -> dict[str, Any]:
    win = load_window(wallet, days=days, as_of=as_of, pm=pm)
    t, markets = win["trades"], win["markets"]
    t = t.assign(league=t["slug"].str.split("-").str[0])
    t = t[t["league"].isin(LEAGUES.keys())]
    gs = {c: pd.Timestamp(m["gameStartTime"]).timestamp() for c, m in markets.items() if m.get("gameStartTime")}
    t = t[t["condition_id"].map(lambda c: c in gs)]
    t = t[t["ts"] >= t["condition_id"].map(gs)]  # in-play fills only
    games = t.groupby("event_slug").agg(league=("league", "first"), n=("ts", "size"), first=("ts", "min"), cids=("condition_id", lambda x: sorted(set(x)))).reset_index()
    games = games[games["n"] >= 5].sort_values("first")
    rng = random.Random(seed)
    if len(games) > max_games:
        keep = sorted(rng.sample(range(len(games)), max_games))
        games = games.iloc[keep]
    espn = ESPN()
    out = []
    for _, g in games.iterrows():
        mk = [markets[c] for c in g["cids"]]
        ml = next((m for m in mk if m.get("sportsMarketType") == "moneyline"), mk[0])
        mt = re.match(r"(.+?) vs\.? (.+)", ml.get("question") or "")
        teams = json.loads(ml.get("outcomes") or "[]") if ml.get("sportsMarketType") == "moneyline" else ([mt.group(1), mt.group(2)] if mt else [])
        if len(teams) != 2:
            continue
        start = gs[g["cids"][0]]
        ev = espn.find_event(g["league"], int(start), teams[0], teams[1])
        if ev is None:
            continue
        game = espn.game(g["league"], ev)
        if game is None or not game.plays:
            continue
        out.append({"event_slug": g["event_slug"], "league": g["league"], "start": int(start), "game": game, "cids": g["cids"]})
    return {"games": out, "markets": markets, "window": win}


def game_prints(entry: dict[str, Any], markets: dict[str, dict[str, Any]], wallet: str, pm: PolymarketData) -> pd.DataFrame:
    game: Game = entry["game"]
    end = game.plays[-1].ts + 600
    rows = []
    for cid in entry["cids"]:
        m = markets[cid]
        tokens = json.loads(m.get("clobTokenIds") or "[]")
        outcomes = json.loads(m.get("outcomes") or "[]")
        res = resolution_info(m)
        tape, _, _ = pm.market_trades(cid, start=entry["start"], end=end, taker_only=True)
        for r in tape:
            if r.get("side") != "BUY" or str(r.get("asset")) not in tokens:
                continue
            k = tokens.index(str(r["asset"]))
            outcome = outcomes[k] if k < len(outcomes) else ""
            rows.append(
                {
                    "event_slug": entry["event_slug"],
                    "condition_id": cid,
                    "mtype": m.get("sportsMarketType") or "",
                    "ts": int(r["timestamp"]),
                    "is_wallet": (r.get("proxyWallet") or "").lower() == wallet.lower(),
                    "outcome": outcome,
                    "side_kind": _outcome_side(outcome, game),
                    "price": float(r["price"]),
                    "size": float(r["size"]),
                    "payout": res["payout"].get(str(r["asset"])) if res["resolved"] else np.nan,
                    "fee_rate": float((m.get("feeSchedule") or {}).get("rate", SPORTS_FEE_RATE)),
                }
            )
    return pd.DataFrame(rows)


def run_sports_study(
    wallet: str,
    days: int = 30,
    as_of: int | None = None,
    max_games: int = 120,
    seed: int = 11,
    n_perm: int = 200,
    out_dir: Path | None = None,
) -> Evidence:
    pm = PolymarketData()
    loaded = load_games(wallet, days, as_of, max_games, seed, pm)
    games, markets = loaded["games"], loaded["markets"]
    with ThreadPoolExecutor(6) as ex:
        frames = list(ex.map(lambda e: game_prints(e, markets, wallet, pm), games))
    events = {e["event_slug"]: scoring_events(e["game"]) for e in games}
    split = int(np.median([e["start"] for e in games])) if games else 0
    fit_slugs = [e["event_slug"] for e in games if e["start"] < split]
    test_slugs = [e["event_slug"] for e in games if e["start"] >= split]
    allp = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if allp.empty:
        return Evidence(tool="sports_study", subject={"wallet": wallet}, coverage=Coverage("empty", "no matched in-play games"))
    allp = allp[allp["side_kind"].notna()]

    def annotated(slugs: list[str], delay: int, shifts: dict[str, int] | None = None) -> pd.DataFrame:
        parts = []
        for s in slugs:
            p = allp[allp["event_slug"] == s]
            if p.empty:
                continue
            parts.append(annotate(p, events[s], delay, (shifts or {}).get(s, 0)))
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    # ---- FIT: choose delay D and reaction window W maximizing wallet excess reactivity
    grid_d = [-10, -5, 0, 5, 10, 20, 30, 60]
    grid_w = [10, 20, 30, 60, 120]
    scan = []
    for D in grid_d:
        a = annotated(fit_slugs, D)
        for W in grid_w:
            r = reaction_stats(a, W)
            scan.append({"delay": D, **r, "excess": r["wallet_share_reactive"] - r["others_share_reactive"]})
    scan_df = pd.DataFrame(scan)
    best = scan_df.loc[scan_df["excess"].idxmax()] if len(scan_df) else None
    D, W = (int(best["delay"]), int(best["window_s"])) if best is not None else (0, 30)

    # ---- TEST: excess reaction + direction with permutation null (timeline shift)
    test_a = annotated(test_slugs, D)
    obs = reaction_stats(test_a, W)
    obs_excess = obs["wallet_share_reactive"] - obs["others_share_reactive"]
    rng = np.random.default_rng(seed)
    null_excess, null_agree = [], []
    for _ in range(n_perm):
        shifts = {s: int(rng.integers(300, 1500)) * int(rng.choice([-1, 1])) for s in test_slugs}
        r = reaction_stats(annotated(test_slugs, D, shifts), W)
        null_excess.append(r["wallet_share_reactive"] - r["others_share_reactive"])
        null_agree.append(r["wallet_direction_agree"])
    null_excess = np.array([x for x in null_excess if np.isfinite(x)])
    null_agree = np.array([x for x in null_agree if np.isfinite(x)])
    # direction: binomial vs 0.5 and vs. other takers
    n_w = obs["wallet_n_reactive"]
    k_w = int(round(obs["wallet_direction_agree"] * n_w)) if n_w else 0
    binom_p = float(stats.binomtest(k_w, n_w, 0.5, alternative="greater").pvalue) if n_w else None
    # lag histogram of wallet fills around scoring plays (cross-correlogram, D = 0)
    lags = []
    for s in test_slugs + fit_slugs:
        ev = events[s]
        if ev.empty:
            continue
        wt = allp[(allp["event_slug"] == s) & allp["is_wallet"]]["ts"].to_numpy()
        for t in ev["ts"].to_numpy():
            d = wt - t
            lags.extend(d[(d >= -120) & (d <= 120)].tolist())
    hist, edges = np.histogram(lags, bins=np.arange(-120, 125, 5))

    # ---- backtest REACT(D, W) on TEST games: buy every favoured print in the reaction window
    bt = _backtest(test_a, W)
    degraded = {}
    for extra in (5, 10, 20, 30, 60):
        degraded[str(D + extra)] = {k: v for k, v in _backtest(annotated(test_slugs, D + extra), W).items() if k in ("trades", "pnl", "return_on_traded", "per_game_p")}
    replay = _replay(test_a)
    ev_out = Evidence(
        tool="sports_study",
        subject={"kind": "wallet", "wallet": wallet.lower(), "days": days},
        observed={
            "games_matched": len(games),
            "fit_games": len(fit_slugs),
            "test_games": len(test_slugs),
            "leagues": pd.Series([e["league"] for e in games]).value_counts().to_dict(),
            "taker_buy_prints": int(len(allp)),
            "wallet_prints": int(allp["is_wallet"].sum()),
        },
        derived={
            "fit_scan_top": scan_df.sort_values("excess", ascending=False).head(8).to_dict("records"),
            "chosen_delay_s": D,
            "chosen_window_s": W,
            "test_reaction": obs,
            "test_excess_reactive_share": obs_excess,
            "excess_null_p95": float(np.percentile(null_excess, 95)) if len(null_excess) else None,
            "excess_perm_p": permutation_pvalue(obs_excess, null_excess) if len(null_excess) else None,
            "direction_binom_p_vs_half": binom_p,
            "direction_null_p95": float(np.percentile(null_agree, 95)) if len(null_agree) else None,
            "direction_perm_p": permutation_pvalue(obs["wallet_direction_agree"], null_agree) if len(null_agree) else None,
            "wallet_lag_histogram_vs_espn_wallclock": {"bin_edges_s": edges.tolist(), "counts": hist.tolist()},
            "backtest_test_games": bt,
            "latency_degradation": degraded,
            "wallet_replay_test_games": replay,
        },
        coverage=Coverage("partial", f"{len(games)} sampled games matched to ESPN"),
        limitations=[
            "ESPN wall clock is the play time, not the time ESPN's API published it; the delay D is fitted, not observed.",
            "Backtest fills assume the observed taker liquidity at each print was available to us (no queue competition).",
            "Only scoring plays are modelled as events; turnovers, injuries, and fouls also move prices.",
            "Games are a deterministic random sample of the wallet's in-play games in the window.",
        ],
    )
    if out_dir is not None:
        d = out_dir / wallet.lower()
        d.mkdir(parents=True, exist_ok=True)
        (d / "sports_study.json").write_text(json.dumps(ev_out.to_dict(), indent=1))
    return ev_out


def _backtest(a: pd.DataFrame, window: int, size_cap_usd: float = 100.0) -> dict[str, Any]:
    if a.empty:
        return {"trades": 0}
    sel = a[(a["since"] >= 0) & (a["since"] <= window) & (a["fav"] > 0) & a["payout"].notna()].copy()
    if sel.empty:
        return {"trades": 0}
    usd = np.minimum(sel["size"] * sel["price"], size_cap_usd)
    shares = usd / sel["price"]
    fee = sel["fee_rate"] * sel["price"] * (1 - sel["price"]) * shares
    sel["pnl"] = shares * sel["payout"] - usd - fee
    per_game = sel.groupby("event_slug")["pnl"].sum()
    t = hac_t_test(per_game.to_numpy())
    return {
        "trades": int(len(sel)),
        "games": int(per_game.size),
        "usd_traded": float(usd.sum()),
        "pnl": float(sel["pnl"].sum()),
        "return_on_traded": float(sel["pnl"].sum() / usd.sum()),
        "per_game_mean": float(per_game.mean()),
        "per_game_t": t.statistic,
        "per_game_p": t.p_value,
        "per_game_bootstrap_p": stationary_bootstrap_pvalue(per_game.to_numpy(), n_boot=2000).p_value if per_game.size >= 5 else None,
    }


def _replay(a: pd.DataFrame) -> dict[str, Any]:
    w = a[a["is_wallet"] & a["payout"].notna()].copy() if not a.empty else a
    if w.empty:
        return {"trades": 0}
    usd = w["size"] * w["price"]
    fee = w["fee_rate"] * w["price"] * (1 - w["price"]) * w["size"]
    w["pnl"] = w["size"] * w["payout"] - usd - fee
    per_game = w.groupby("event_slug")["pnl"].sum()
    t = hac_t_test(per_game.to_numpy())
    return {"trades": int(len(w)), "usd_traded": float(usd.sum()), "pnl": float(w["pnl"].sum()), "return_on_traded": float(w["pnl"].sum() / usd.sum()), "per_game_p": t.p_value}
