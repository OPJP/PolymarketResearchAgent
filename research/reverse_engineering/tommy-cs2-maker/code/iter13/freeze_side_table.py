"""X181 step 4 (assumptions panel iter-12 P2): a side-aware MR12 table at freeze time. Per map, team A's round-win
probability as CT (q_CT) and as T (q_T) on a 0.30..0.70 grid, sides from bo3 game_round_team_clans, MR12 with an
approximate overtime; observations = the first burst after each print-inferred round end (the X171 print fit with the
true winner sequence) with the score before the round; per-token offsets (V) / one offset (print) removed; the grid
point minimising each series' residual SD is chosen separately (fair to both). Signature (panel): V's freeze-time
residual <= 2c and >= 0.7c below the print's. Output: results/freeze_side_table.json
Based on: X181 (assumptions panel iter-12 P2), historical: does its value move WITHIN a round toward the round's winner more
than the market's print does? Maps and data as code/iter12/round_markov_fit.py (CS2 map markets of 16-22 Oct with a bo3
round sequence, the wallet's filled maker bursts, the last public print without wallet transactions at the burst times).
Round boundaries come from the PRINT: the X171 hidden-Markov fit of the print with the true winner sequence (so the
clock is wallet-value-independent and favours the print). For each inferred round r with >= 2 bursts inside:
Delta_w = its level (team-A space) at the last burst in r minus at the first burst in r; Delta_p the same for the
print; outcome = team A won round r (bo3). Statistics: AUC of Delta_w and of Delta_p for the outcome, AUC of Delta_w
residualised on Delta_p (OLS), with a map-cluster bootstrap (2,000 draws) of AUC(Delta_w) - AUC(Delta_p).
Guarded variants: the same with the last burst at least g = 10 / 20 / 30 / 45 s before the print-inferred end (the
first burst of the next segment), to keep out its earlier reaction to the round result itself (the print reacts late,
so the inferred end can follow the true end). Early windows: only bursts within the first 30 / 60 s after the round's
first burst (and >= 10 s before the inferred end). Pre-move window: only bursts before the print's first move of >= 2c
(either direction) inside the round, i.e. while the market has not yet priced anything of the round.
Output: results/inround_drift.json
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
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter12"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter2"))
import round_markov_fit as R  # noqa: E402
from polyrea.adapters.http import shared_client  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
GUARDS = (10, 20, 30, 45)
EARLY = (30, 60)  # early windows: last burst within E s after the round's first burst (and before the guard-free end)  # seconds before the print-inferred end of the round (the next segment's first burst)


def auc(s, y):
    s, y = np.asarray(s, float), np.asarray(y, int)
    if y.min() == y.max():
        return np.nan
    from scipy.stats import rankdata
    r = rankdata(s)
    n1 = y.sum()
    n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main():
    h = shared_client()
    slugs = R.bo3_maps(h)
    mk = json.load(open(OUT / "markets_dev.json"))
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "price", "cid", "oi", "role"])
    o = o[(o.role == "maker") & (o.sign_ms / 1000 < R.H)]
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    bad = set(cd.loc[cd.maker == R.WALLET, "tx"])
    rows = []
    nmaps = 0
    for cid, x in mk.items():
        if x.get("sportsMarketType") != "child_moneyline" or not x.get("question", "").startswith("Counter-Strike"):
            continue
        mm = re.search(r"Map (\d)", x["question"])
        if not mm:
            continue
        mapno = int(mm.group(1))
        oo = o[o.cid == cid].sort_values("sign_ms")
        if len(oo) < 30:
            continue
        outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
        a, b = R.norm(outs[0])[:6], R.norm(outs[1])[:6]
        cand = [s for s in slugs if a in R.norm(s) and b in R.norm(s)]
        if not cand:
            continue
        g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{cand[0]}", {"with": "games"}, adapter="bo3gg.match", max_age=None)
        gm = [yy for yy in (g.get("games") or []) if yy.get("number") == mapno]
        if not gm:
            continue
        r, _ = h.get_json(f"https://api.bo3.gg/api/v1/games/{gm[0]['id']}/rounds", {}, adapter="bo3gg.rounds", max_age=None)
        rounds = r.get("game_rounds") if isinstance(r, dict) else None
        if not rounds or len(rounds) < 13:
            continue
        rounds = sorted(rounds, key=lambda z: z["round_number"])
        wn = [R.norm(z.get("winner_clan_name")) for z in rounds]
        fa, fb = R.norm(outs[0]), R.norm(outs[1])
        isa = np.array([(w[:6] == a) or (len(w) >= 3 and (w in fa or fa in w)) for w in wn])
        isb = np.array([(w[:6] == b) or (len(w) >= 3 and (w in fb or fb in w)) for w in wn])
        if (isa & isb).any() or (isa | isb).mean() < 0.95 or isa.sum() == 0 or isb.sum() == 0:
            continue
        win = isa.astype(int)
        oo = oo.assign(tok=oo.oi.astype(int))
        oo = oo[(oo.price > 0.06) & (oo.price < 0.94)]
        if len(oo) < 30:
            continue
        oo = oo.sort_values(["tok", "sign_ms"])
        newb = (oo.tok.diff() != 0) | (oo.sign_ms.diff() > R.BURST_MS)
        oo["bid"] = newb.cumsum()
        bb = oo.groupby("bid").agg(sign_ms=("sign_ms", "min"), price=("price", "max"), tok=("tok", "first")).sort_values("sign_ms")
        y = np.where(bb.tok == 0, bb.price, 1 - bb.price).astype(float)
        tok = bb.tok.to_numpy(int)
        tt = bb.sign_ms.to_numpy() / 1000.0
        tp = R.TAPES / f"{cid}_tkw.parquet"
        if not tp.exists():
            continue
        d = pd.read_parquet(tp)
        d = d[(d.timestamp < R.H) & ~d.transactionHash.isin(bad)].sort_values("timestamp")
        if len(d) < 20:
            continue
        ts = d.timestamp.to_numpy(float)
        pa = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        j = np.searchsorted(ts, tt, side="right") - 1
        ok = j >= 0
        if ok.sum() < 30:
            continue
        y, tok, tt, yp = y[ok], tok[ok], tt[ok], pa[j[ok]]
        fp = R.fit(yp, tok * 0, tt, win[None, :])
        path = fp["path"][0]
        # A's side per round (bo3 game_round_team_clans)
        sideA = []
        for z in rounds:
            sd = None
            for tc in z.get("game_round_team_clans") or []:
                cn = R.norm(tc.get("clan_name"))
                if cn[:6] == a or (len(cn) >= 3 and (cn in fa or fa in cn)):
                    sd = tc.get("team_side")
            sideA.append(1 if sd == "CT" else (0 if sd == "T" else -1))
        if (np.array(sideA) < 0).mean() > 0.1:
            continue
        nmaps += 1
        inc = np.where(np.diff(path) > 0)[0] + 1   # first burst after each inferred round end
        for i in inc:
            r_ = int(path[i])                       # rounds completed
            if r_ >= len(win):
                continue
            sa = int(win[:r_].sum()); sb = r_ - sa
            rows.append({"cid": cid, "r": r_, "sa": sa, "sb": sb, "y": float(y[i]), "tok": int(tok[i]), "yp": float(yp[i]),
                         "sides": json.dumps(sideA)})
    D = pd.DataFrame(rows)
    out = {"maps": nmaps, "freeze_obs": int(len(D))}
    grid = np.round(np.arange(0.30, 0.701, 0.05), 3)

    def table(sides, qct, qt):
        memo = {}
        def V(sa, sb):
            if sa >= 13 and sa - sb >= 2:
                return 1.0
            if sb >= 13 and sb - sa >= 2:
                return 0.0
            if sa + sb >= 24:
                pbar = 0.5 * (qct + qt)
                return float(np.clip(0.5 + 1.5 * (pbar - 0.5) + 0.25 * (sa - sb), 0.02, 0.98)) if sa != sb else float(np.clip(0.5 + 1.5 * (pbar - 0.5), 0.02, 0.98))
            k = (sa, sb)
            if k in memo:
                return memo[k]
            rr = sa + sb
            q = qct if (rr < len(sides) and sides[rr] == 1) else qt
            v = q * V(sa + 1, sb) + (1 - q) * V(sa, sb + 1)
            memo[k] = v
            return v
        return V
    res_v, res_p, best_rows = [], [], []
    for cid, g in D.groupby("cid"):
        if len(g) < 8:
            continue
        sides = json.loads(g.sides.iloc[0])
        bestv = bestp = None
        for qct in grid:
            for qt in grid:
                V = table(sides, qct, qt)
                tv = np.array([V(int(r.sa), int(r.sb)) for r in g.itertuples()])
                rv = g.y.to_numpy() - tv
                for s_ in (0, 1):
                    m_ = g.tok.to_numpy() == s_
                    if m_.any():
                        rv[m_] -= np.mean(rv[m_])
                rp = g.yp.to_numpy() - tv
                rp = rp - np.mean(rp)
                sv, sp = float(np.std(rv)), float(np.std(rp))
                if bestv is None or sv < bestv[0]:
                    bestv = (sv, qct, qt)
                if bestp is None or sp < bestp[0]:
                    bestp = (sp, qct, qt)
        best_rows.append({"cid": cid, "n": int(len(g)), "sd_v": bestv[0], "sd_p": bestp[0], "q_v": [bestv[1], bestv[2]], "q_p": [bestp[1], bestp[2]]})
    B = pd.DataFrame(best_rows)
    if len(B):
        out.update({"maps_fitted": int(len(B)), "freeze_sd_v_median_c": round(float(B.sd_v.median()) * 100, 2),
                    "freeze_sd_p_median_c": round(float(B.sd_p.median()) * 100, 2),
                    "share_maps_v_below_p": round(float((B.sd_v < B.sd_p).mean()), 3),
                    "share_maps_v_le_2c": round(float((B.sd_v <= 0.02).mean()), 3),
                    "signature_v_le_2c_and_0p7_below_print": bool(B.sd_v.median() <= 0.02 and B.sd_v.median() <= B.sd_p.median() - 0.007)})
    (RES / "freeze_side_table.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
