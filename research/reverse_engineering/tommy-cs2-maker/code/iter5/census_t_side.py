"""Iteration 5 (X58 step 3b): the half-level T-side test applied to the census bursts (wallet-led/near vs wallet-absent).
Original docstring: Iteration 4, X50 follow-up (half-level clock): does the taker buy the T side (the planting side)?

If its trigger were bomb plants, the bought team would be the T side at the time of the take far more often than
half the time; if it were side-neutral in-round swings (kills, man advantage), about half. Same 16-22 Oct maps as
event_type_counts.py (bo3.gg per-round team stats matched to the wallet's map markets). Half-level clock: bo3 game
begin_at + duration x (share of the first 12 rounds' durations in all rounds' durations) = halftime; takes within
+-3 min of it, and takes after the end of round 24 (overtime), are dropped. T side in half 1 = the team with
team_side 'T' in round 1; it switches at halftime. Reported: the share of its take events (orders within 5 ms merged)
buying the T side, a binomial test against 0.5 and an event bootstrap over maps; the same for P4e; and the share with
the halves deliberately swapped (a sanity check, expected 1 - share).
Output: results/t_side_share.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import HttpClient  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
P4E = "0x4ebc2722"
DAYS = ("2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def main():
    h = HttpClient()
    bl = []
    for day in DAYS:
        d, _ = h.get_json("https://api.bo3.gg/api/v2/matches/finished", {"date": day, "filter[discipline_id][eq]": 1}, adapter="bo3gg.matches", max_age=None)
        for tier, v in (d or {}).get("data", {}).get("tiers", {}).items():
            for m in v.get("matches", []):
                if m.get("parsed_status") == "done":
                    bl.append(m["slug"])
    mj = json.load(open(OUT / "markets_dev.json"))
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["cid", "oi"])
    b = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted((OUT / "calldata_pub").glob("*.parquet"))])
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "token_id", "oi"]).drop_duplicates("token_id")
    tok = {str(k): v for k, v in zip(o.token_id, zip(o.cid, o.oi))}
    b["tok"] = b.token_id.astype(str)
    b = b[b.tok.isin(tok)].copy()
    b["cid"] = b.tok.map(lambda t: tok[t][0])
    b["oi"] = b.tok.map(lambda t: tok[t][1])
    cd = pd.concat([a, b.drop(columns=["tok"])], ignore_index=True)
    B = pd.read_parquet(OUT / "census_bursts.parquet")
    B["sign_ms"] = B.t0 * 1000.0
    who = {"wallet_led_or_near": B[B.label.isin(["wallet-led", "wallet-near"])], "wallet_absent": B[B.label == "wallet-absent"]}
    recs = {k: [] for k in who}
    nmaps = 0
    for cid, x in mj.items():
        if x.get("sportsMarketType") != "child_moneyline":
            continue
        mm = re.search(r"Map (\d)", x.get("question", ""))
        if not mm:
            continue
        outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
        an, bn = norm(outs[0])[:6], norm(outs[1])[:6]
        cand = [s for s in bl if an in norm(s) and bn in norm(s)]
        if not cand:
            continue
        g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{cand[0]}", {"with": "games"}, adapter="bo3gg.match", max_age=None)
        gm = [y for y in (g or {}).get("games") or [] if y.get("number") == int(mm.group(1))]
        if not gm:
            continue
        r, _ = h.get_json(f"https://api.bo3.gg/api/v1/games/{gm[0]['id']}/rounds", {}, adapter="bo3gg.rounds", max_age=None)
        if not isinstance(r, dict) or not r.get("game_rounds") or not r.get("begin_at") or not r.get("duration"):
            continue
        rounds = sorted(r["game_rounds"], key=lambda z: z["round_number"])
        if len(rounds) < 13:
            continue
        r1 = rounds[0].get("game_round_team_clans") or []
        t1 = [t for t in r1 if t.get("team_side") == "T"]
        if not t1:
            continue
        tname = norm(t1[0].get("clan_name"))[:6]
        if tname not in (an, bn):
            continue
        t_half1 = 0 if tname == an else 1  # outcome index of the T side in half 1
        dur = np.array([z["round_duration"] / 1e9 for z in rounds], float)
        begin = pd.Timestamp(r["begin_at"]).timestamp()
        total = r["duration"] / 1e9
        t_half = begin + total * dur[:12].sum() / dur.sum()
        t_reg_end = begin + total * dur[:24].sum() / dur.sum()
        nmaps += 1
        for lab, T in who.items():
            g2 = T[T.cid == cid].sort_values("sign_ms")
            if len(g2) == 0:
                continue
            ts = g2.sign_ms.to_numpy(float) / 1000
            keep = (ts >= begin) & (np.abs(ts - t_half) > 180) & (ts < t_reg_end)
            for t, oi in zip(ts[keep], g2.oi.to_numpy()[keep]):
                half = 1 if t < t_half else 2
                t_side = t_half1 if half == 1 else 1 - t_half1
                recs[lab].append({"cid": cid, "half": half, "buy_T": int(oi == t_side), "buy_T_swapped": int(oi != t_side)})
    res = {"maps_matched": nmaps}
    rng = np.random.default_rng(2)
    for lab, rows in recs.items():
        x = pd.DataFrame(rows)
        if len(x) == 0:
            continue
        k, n = int(x.buy_T.sum()), int(len(x))
        cids = x.cid.unique()
        gi = {c: x.index[x.cid == c] for c in cids}
        bs = [x.loc[np.concatenate([gi[c] for c in rng.choice(cids, len(cids))])].buy_T.mean() for _ in range(2000)]
        res[lab] = {"take_events": n, "maps": int(len(cids)), "share_buy_T_side": round(k / n, 3),
                    "binom_p_two_sided": float(f"{stats.binomtest(k, n, 0.5).pvalue:.3g}"),
                    "map_bootstrap_ci95": [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)],
                    "share_half1": round(float(x[x.half == 1].buy_T.mean()), 3), "share_half2": round(float(x[x.half == 2].buy_T.mean()), 3),
                    "swapped_halves_share": round(float(x.buy_T_swapped.mean()), 3)}
    json.dump(res, open(RES / "census_t_side.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
