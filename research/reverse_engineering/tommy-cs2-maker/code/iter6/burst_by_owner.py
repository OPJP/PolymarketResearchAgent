"""Iteration 6, Y4 / Y7 quick discriminator (self-proposed X85 / X86): does the wallet's share of the informed bursts it
leads depend on who runs the league (a sportsbook-branded organiser: 1win, Stake) or on the stream platform (Kick vs
Twitch, from the listing's resolutionSource)? Y4 (bookmaker odds feed) predicts a higher led share in bookmaker-run
leagues; Y7 (low-latency stream arbitrage) predicts a platform effect. Census bursts (16-22 Oct), present = wallet-led
or wallet-near, wallet-late dropped; event-clustered bootstrap CIs; also the wallet's led share conditional on the
public-covariate model's score (residual effect).
Output: results/burst_by_owner.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
rng = np.random.default_rng(85)


def owner(league):
    s = str(league or "").lower()
    if "1win" in s or "stake" in s or "thunderpick" in s or "gg.bet" in s or "betboom" in s:
        return "bookmaker"
    return "other"


def platform(src):
    s = str(src or "").lower()
    if "kick.com" in s:
        return "kick"
    if "twitch" in s:
        return "twitch"
    if "youtube" in s:
        return "youtube"
    if "hltv" in s:
        return "hltv"
    return "other"


def boot(df, col):
    ev = df.event_slug.unique()
    out = {}
    for g, x in df.groupby(col):
        vals = []
        evs = x.event_slug.unique()
        by = {e: y.pres.to_numpy() for e, y in x.groupby("event_slug")}
        for _ in range(2000):
            pick = rng.choice(evs, len(evs))
            v = np.concatenate([by[e] for e in pick])
            vals.append(v.mean())
        out[g] = {"n_bursts": int(len(x)), "n_events": int(len(evs)), "present": round(float(x.pres.mean()), 3),
                  "ci95": [round(float(v), 3) for v in np.percentile(vals, [2.5, 97.5])]}
    return out


def main():
    B = pd.read_parquet(OUT / "census_bursts.parquet")
    B = B[B.label != "wallet-late"].copy()
    B["pres"] = B.label.isin(["wallet-led", "wallet-near"]).astype(int)
    U = pd.read_parquet(OUT / "universe.parquet", columns=["cid", "event_slug", "league"]).drop_duplicates("cid")
    E = pd.read_parquet(OUT / "events_meta.parquet", columns=["event_slug", "resolution_source"])
    B = B.merge(U, on="cid", how="left").merge(E, on="event_slug", how="left")
    B["owner"] = B.league.map(owner)
    B["platform"] = B.resolution_source.map(platform)
    res = {"n": int(len(B)), "by_owner": boot(B, "owner"), "by_platform": boot(B, "platform"),
           "by_league": B.groupby("league").pres.agg(["mean", "size"]).round(3).sort_values("size", ascending=False).head(15).to_dict("index")}
    (RES / "burst_by_owner.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
