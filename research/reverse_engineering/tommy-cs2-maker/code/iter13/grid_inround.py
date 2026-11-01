"""X188 first pass (self-proposed, iteration 13): the operator's value process where its push feed does NOT reach. The
operator's 5-share / 20-share accounts 0x67119033 and 0x52661b8e quoted GRID CS2 events in October with the same design
(BUY-only, whole cents, band; activity before H). GRID events are outside the wallet's selection and its feed product
(group P), and GRID's official data reaches the market fast. Same in-round drift test as inround_drift.py (rounds
inferred from the print with the true bo3 winner sequence; AUC of the within-round change of its level vs the
print's for the round winner; guards 10-45 s), on their GRID map markets; and, as the reference, the same accounts'
non-GRID CS2 map markets when enough bursts exist. If the in-round lead depends on the feed's coverage, it vanishes in
GRID events.
Output: results/grid_inround.json
"""
from __future__ import annotations

import glob
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
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from inround_drift import auc  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
ACC = {"0x671190333b064b0899b4ac1aec86744b1f82885b", "0x52661b8e13158f23d94a9e8302ab0295704c22ac"}
H = 1792713600


def bo3_slugs(h, days):
    out = []
    for day in days:
        d, _ = h.get_json("https://api.bo3.gg/api/v2/matches/finished", {"date": day, "filter[discipline_id][eq]": 1}, adapter="bo3gg.matches", max_age=None)
        for _tier, v in ((d or {}).get("data") or {}).get("tiers", {}).items():
            for m in v.get("matches", []):
                if m.get("parsed_status") == "done":
                    out.append(m["slug"])
    return out


def main():
    h = shared_client()
    pm = PolymarketData()
    cols = ["tx", "idx", "maker", "token_id", "price", "shares", "sign_ms", "salt"]
    cd = pd.concat([pd.read_parquet(f, columns=cols) for f in glob.glob(str(OUT / "sib_grid/calldata/part_*.parquet"))])
    cd["maker"] = cd.maker.str.lower()
    cd["token_id"] = cd.token_id.astype(str)
    own_tx = set(cd.loc[cd.maker.isin(ACC), "tx"])
    act = pd.read_parquet(OUT / "sib_grid/activity.parquet")
    mk, _ = pm.markets_by_condition(sorted(act.conditionId.unique()))
    days = sorted({pd.to_datetime(t, unit="s").strftime("%Y-%m-%d") for t in act.timestamp})
    slugs = bo3_slugs(h, days)
    o = cd[cd.maker.isin(ACC) & (cd.idx != -1)].drop_duplicates(["maker", "salt", "sign_ms"])
    o = o[(o.sign_ms > 1.7e12) & (o.sign_ms < 1.8e12)]
    rows, nmaps, skipped = [], 0, {"no_map": 0, "few_orders": 0, "no_bo3": 0, "names": 0, "tape": 0}
    for cid, x in mk.items():
        if x.get("sportsMarketType") != "child_moneyline":
            skipped["no_map"] += 1
            continue
        mm = re.search(r"Map (\d)", x.get("question", ""))
        if not mm:
            skipped["no_map"] += 1
            continue
        mapno = int(mm.group(1))
        toks = [str(t) for t in (json.loads(x["clobTokenIds"]) if isinstance(x.get("clobTokenIds"), str) else x.get("clobTokenIds"))]
        oo = o[o.token_id.isin(toks)].copy()
        if len(oo) < 20:
            skipped["few_orders"] += 1
            continue
        outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
        a, b = R.norm(outs[0])[:6], R.norm(outs[1])[:6]
        cand = [s for s in slugs if a in R.norm(s) and b in R.norm(s)]
        if not cand:
            skipped["no_bo3"] += 1
            continue
        g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{cand[0]}", {"with": "games"}, adapter="bo3gg.match", max_age=None)
        gm = [yy for yy in (g.get("games") or []) if yy.get("number") == mapno]
        if not gm:
            skipped["no_bo3"] += 1
            continue
        r, _ = h.get_json(f"https://api.bo3.gg/api/v1/games/{gm[0]['id']}/rounds", {}, adapter="bo3gg.rounds", max_age=None)
        rounds = r.get("game_rounds") if isinstance(r, dict) else None
        if not rounds or len(rounds) < 13:
            skipped["no_bo3"] += 1
            continue
        rounds = sorted(rounds, key=lambda z: z["round_number"])
        wn = [R.norm(z.get("winner_clan_name")) for z in rounds]
        fa, fb = R.norm(outs[0]), R.norm(outs[1])
        isa = np.array([(w[:6] == a) or (len(w) >= 3 and (w in fa or fa in w)) for w in wn])
        isb = np.array([(w[:6] == b) or (len(w) >= 3 and (w in fb or fb in w)) for w in wn])
        if (isa & isb).any() or (isa | isb).mean() < 0.95 or isa.sum() == 0 or isb.sum() == 0:
            skipped["names"] += 1
            continue
        win = isa.astype(int)
        oo["tok"] = np.where(oo.token_id == toks[0], 0, 1)
        oo = oo[(oo.price > 0.06) & (oo.price < 0.94)].sort_values(["tok", "sign_ms"])
        if len(oo) < 20:
            skipped["few_orders"] += 1
            continue
        newb = (oo.tok.diff() != 0) | (oo.sign_ms.diff() > R.BURST_MS)
        oo["bid"] = newb.cumsum()
        bb = oo.groupby("bid").agg(sign_ms=("sign_ms", "min"), price=("price", "max"), tok=("tok", "first")).sort_values("sign_ms")
        y = np.where(bb.tok == 0, bb.price, 1 - bb.price).astype(float)
        tok = bb.tok.to_numpy(int)
        tt = bb.sign_ms.to_numpy() / 1000.0
        gs = pd.Timestamp(str(x.get("gameStartTime")).replace("+00", "+00:00") if str(x.get("gameStartTime")).endswith("+00") else x.get("gameStartTime")).timestamp()
        rows_t, _, _ = pm.market_trades(cid, start=int(gs) - 3600, end=int(min(gs + 4 * 3600 + 600, H - 1)), taker_only=True)
        d = pd.DataFrame(rows_t)
        if len(d) < 20:
            skipped["tape"] += 1
            continue
        d = d[~d.transactionHash.isin(own_tx)].sort_values("timestamp")
        ts = d.timestamp.to_numpy(float)
        pa = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        j = np.searchsorted(ts, tt, side="right") - 1
        ok = j >= 0
        if ok.sum() < 20:
            skipped["tape"] += 1
            continue
        y, tok, tt, yp = y[ok], tok[ok], tt[ok], pa[j[ok]]
        fp = R.fit(yp, tok * 0, tt, win[None, :])
        path = fp["path"][0]
        nmaps += 1
        off = {s: float(np.median((y - yp)[tok == s])) if (tok == s).any() else 0.0 for s in (0, 1)}
        yc = y - np.array([off[s] for s in tok])
        ks = np.unique(path)
        for ki, k in enumerate(ks):
            m = np.where(path == k)[0]
            if len(m) < 2 or k >= len(win):
                continue
            i0, i1 = m[0], m[-1]
            t_next = tt[np.where(path == ks[ki + 1])[0][0]] if ki + 1 < len(ks) else np.inf
            rec = {"cid": cid, "A_won": int(win[k]), "dW": float(yc[i1] - yc[i0]), "dP": float(yp[i1] - yp[i0])}
            for gsec in (10, 30, 45):
                mg = m[tt[m] <= t_next - gsec]
                if len(mg) >= 2:
                    rec[f"dW_g{gsec}"] = float(yc[mg[-1]] - yc[mg[0]])
                    rec[f"dP_g{gsec}"] = float(yp[mg[-1]] - yp[mg[0]])
            rows.append(rec)
    D = pd.DataFrame(rows)
    out = {"maps": nmaps, "rounds": int(len(D)), "skipped_markets": skipped, "bo3_days": len(days)}
    if len(D) > 30 and D.A_won.nunique() == 2:
        yv = D.A_won.to_numpy()
        out["auc_dW"] = round(auc(D.dW, yv), 4)
        out["auc_dP"] = round(auc(D.dP, yv), 4)
        for gsec in (10, 30, 45):
            Zg = D.dropna(subset=[f"dW_g{gsec}"])
            if len(Zg) > 30 and Zg.A_won.nunique() == 2:
                out[f"guard_{gsec}s"] = {"rounds": int(len(Zg)), "auc_dW": round(auc(Zg[f"dW_g{gsec}"], Zg.A_won.to_numpy()), 4),
                                         "auc_dP": round(auc(Zg[f"dP_g{gsec}"], Zg.A_won.to_numpy()), 4)}
        rng = np.random.default_rng(13)
        maps = D.cid.unique()
        by = {c: D[D.cid == c] for c in maps}
        diffs = []
        for _ in range(2000):
            s = pd.concat([by[c] for c in rng.choice(maps, len(maps))])
            yy = s.A_won.to_numpy()
            if yy.min() == yy.max():
                continue
            diffs.append(auc(s.dW, yy) - auc(s.dP, yy))
        diffs = np.array(diffs)
        out["auc_diff_ci95"] = [round(float(np.quantile(diffs, 0.025)), 4), round(float(np.quantile(diffs, 0.975)), 4)]
    (RES / "grid_inround.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
