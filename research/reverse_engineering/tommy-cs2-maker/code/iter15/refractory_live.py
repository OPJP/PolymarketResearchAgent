"""X212 (mechanics panel iter-14 P4), first pass: the wallet's UNCENSORED value path on the BUILD-live block (10-31 12-18;
iteration-12 slot_vrel_rows: V_after of every validated own add burst on the recorded book) against the bo3 rounds of
the same maps (development units, parsed), on a print-anchored clock (iteration-14 tracker: bo3 durations + gap G,
snapped to >= 2c clean-print jumps toward round r's winner within [-15, +30] s). Freeze-time refractory signature:
K (in-round events) predicts few value moves in the ~0-22 s after each round end (restart + freeze, no kills possible)
and most in the action phase; R predicts one step at the end and quiet otherwise. Hazard of value moments (|dV| >= 1c and
>= 3c, per token) by time since the previous snapped round end, 5-s bins, against the uniform expectation.
Output: results/refractory_live.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import sealed  # noqa: E402
from polyrea.adapters.http import shared_client  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
BLK_END = 1793469600
MAPS = {"cs2-shin-isg-2026-10-31-game1": ("shinden-vs-isurus-gaming-cs-go-31-10-2026", 1),
        "cs2-gls1-pcy-2026-10-31-game1": ("galorys-cs-vs-procyon-gaming-31-10-2026", 1),
        "cs2-gls1-pcy-2026-10-31-game2": ("galorys-cs-vs-procyon-gaming-31-10-2026", 2),
        "cs2-bhe-bar2-2026-10-31-game1": ("bounty-hunters-esports-vs-barca-br-31-10-2026", 1)}


def norm(x):
    return re.sub(r"[^a-z0-9]", "", str(x).lower())


def main():
    h = shared_client()
    pm = PolymarketData()
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    u = pd.read_parquet(OUT / "universe_t0.parquet")
    sv = pd.read_parquet(OUT / "iter12/slot_vrel_rows.parquet")
    sv = sv[(sv.kind == "add") & sv.V_after.notna()]
    res = {"maps": {}}
    hz1, hz3, expo = np.zeros(13), np.zeros(13), np.zeros(13)
    for slug, (bslug, mapno) in MAPS.items():
        row = dm[dm.slug == slug]
        if row.empty:
            continue
        cid, gs = row.cid.iloc[0], float(row.gs.iloc[0])
        assert not sealed.is_sealed(gs, "tommy-cs2-maker")
        outs = json.loads(u.loc[u.cid == cid, "outcomes"].iloc[0])
        g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{bslug}", {"with": "games"}, adapter="bo3gg.match", max_age=None)
        gm = [y for y in (g.get("games") or []) if y.get("number") == mapno]
        if not gm:
            res["maps"][slug] = "no bo3 game"
            continue
        r, _ = h.get_json(f"https://api.bo3.gg/api/v1/games/{gm[0]['id']}/rounds", {}, adapter="bo3gg.rounds", max_age=None)
        rounds = sorted((r or {}).get("game_rounds") or [], key=lambda z: z["round_number"])
        if len(rounds) < 13:
            res["maps"][slug] = f"rounds {len(rounds)}"
            continue
        fa, fb = norm(outs[0]), norm(outs[1])
        wn = [norm(z.get("winner_clan_name")) for z in rounds]
        isa = np.array([(w[:5] in fa) or (fa[:5] in w) for w in wn])
        isb = np.array([(w[:5] in fb) or (fb[:5] in w) for w in wn])
        if (isa & isb).any() or (isa | isb).mean() < 0.9:
            res["maps"][slug] = "winner names do not map"
            continue
        wsign = np.where(isa, 1.0, -1.0)
        dur = np.array([float(z.get("round_duration") or 0) / 1e9 for z in rounds])
        tk, _, _ = pm.market_trades(cid, start=int(gs) - 3600, end=BLK_END - 1, taker_only=True)
        d = pd.DataFrame(tk)
        if d.empty:
            res["maps"][slug] = "no tape"
            continue
        d = d[d.proxyWallet.str.lower() != W].sort_values("timestamp")
        ts = d.timestamp.to_numpy(float)
        pa = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        dp = np.diff(pa, prepend=np.nan)
        jj = np.where(np.abs(dp) >= 0.02 - 1e-9)[0]
        cc = np.column_stack([ts[jj], np.sign(dp[jj])]) if len(jj) else np.zeros((0, 2))
        v = sv[sv.slug == slug].sort_values("t")
        tv = v.t.to_numpy(float) / 1000.0
        if len(cc) < 5 or len(v) < 10:
            res["maps"][slug] = f"anchors {len(cc)} V rows {len(v)}"
            continue

        def track(ws, G):
            ct, cs = cc[:, 0], cc[:, 1]
            e = np.full(len(ws), np.nan)
            sn = np.zeros(len(ws), bool)
            c0 = np.where((cs == ws[0]) & (ct >= tv[0] - 300) & (ct <= tv[0] + 2400))[0]
            if not len(c0):
                return e, sn
            e[0], sn[0] = ct[c0[0]], True
            for k in range(1, len(ws)):
                pred = e[k - 1] + dur[k] + G
                cand = np.where((cs == ws[k]) & (ct >= pred - 15) & (ct <= pred + 30) & (ct > e[k - 1] + 20))[0]
                if len(cand):
                    e[k], sn[k] = ct[cand[0]], True
                else:
                    e[k] = pred
            return e, sn
        best = None
        for G in (0.0, 10.0, 20.0, 30.0):
            e, sn = track(wsign, G)
            if best is None or sn.sum() > best[1].sum():
                best = (e, sn, G)
        e, sn, G = best
        _, snp = track(wsign[::-1].copy(), G)
        # value moments per token: |dV_after| >= 1c / >= 3c between consecutive add bursts on the token
        moms = []
        for oi, q in v.groupby("oi"):
            q = q.sort_values("t")
            dv = np.diff(q.V_after.to_numpy(float), prepend=np.nan)
            tt = q.t.to_numpy(float) / 1000.0
            for t_, d_ in zip(tt, dv):
                if np.isfinite(d_) and abs(d_) >= 0.01 - 1e-9:
                    moms.append((t_, abs(d_)))
        M = np.array(moms) if moms else np.zeros((0, 2))
        n_r = 0
        for k in range(1, len(rounds)):
            if not (sn[k] and sn[k - 1]):
                continue
            a, z = e[k - 1], e[k]
            if z - a < 30:
                continue
            n_r += 1
            span = min(z - a, 65.0)
            nb = int(np.ceil(span / 5.0))
            expo[:nb] += 1
            sel = (M[:, 0] > a) & (M[:, 0] <= a + span)
            bins = np.minimum(((M[sel, 0] - a) // 5).astype(int), 12)
            np.add.at(hz1, bins, 1)
            np.add.at(hz3, bins[M[sel, 1] >= 0.03 - 1e-9], 1)
        res["maps"][slug] = {"rounds": len(rounds), "snapped": int(sn.sum()), "snapped_reversed": int(snp.sum()), "G": G,
                             "rounds_both_ends": n_r, "value_moments": int(len(M)), "anchors": int(len(cc))}
    rate1 = np.where(expo > 0, hz1 / np.maximum(expo, 1), np.nan)
    rate3 = np.where(expo > 0, hz3 / np.maximum(expo, 1), np.nan)
    res["hazard_bins_s"] = [f"{5 * i}-{5 * i + 5}" for i in range(13)]
    res["rounds_exposed_per_bin"] = expo.astype(int).tolist()
    res["moments_ge1c_per_round_per_5s"] = [round(float(x), 3) for x in rate1]
    res["moments_ge3c_per_round_per_5s"] = [round(float(x), 3) for x in rate3]
    if expo[0] > 0:
        early = rate1[:4].mean()  # 0-20 s after the end (restart + freeze)
        late = np.nanmean(rate1[5:12])  # 25-60 s (action phase)
        res["early_0_20s_vs_action_25_60s_ge1c"] = [round(float(early), 3), round(float(late), 3)]
        res["early_0_20s_vs_action_25_60s_ge3c"] = [round(float(rate3[:4].mean()), 3), round(float(np.nanmean(rate3[5:12])), 3)]
    (RES / "refractory_live.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
