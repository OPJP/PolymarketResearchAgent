"""X160 step 5 in clock-free form (information panel iter-11 P3): does the wallet's level carry round economy beyond the
score table, more than the public print does?

Uses the X171 hidden-Markov fit (round_markov_fit.py) on the TRUE bo3 winner sequence only. For every burst that is
the first after an inferred round end (the path increments k -> k+1: the buy / freeze phase of round k+1), the residual
y - M_k(p) - mu_token is regressed on round k+1's bo3 economy of team A minus team B: equipment value ($1000s), economy
level difference, and A's side (CT = 1), with the same regression for the last public print at those times (its own
fitted path). Spearman of residual vs equipment differential with a map-cluster bootstrap. Development data only.
Output: results/round_econ.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from round_markov_fit import H, OUT, RES, SPLIT, TAPES, WALLET, bo3_maps, fit, norm, shared_client  # noqa: E402


def econ_of(rounds, a_full, b_full):
    out = []
    for z in rounds:
        rec = {"eqA": np.nan, "eqB": np.nan, "elA": np.nan, "elB": np.nan, "sideA_CT": np.nan}
        for t in z.get("game_round_team_clans") or []:
            nm = norm(t.get("clan_name"))
            isA = nm[:6] == a_full[:6] or (len(nm) >= 3 and (nm in a_full or a_full in nm))
            isB = nm[:6] == b_full[:6] or (len(nm) >= 3 and (nm in b_full or b_full in nm))
            if isA and not isB:
                rec["eqA"] = t.get("equipment_value"); rec["elA"] = t.get("economy_level"); rec["sideA_CT"] = 1.0 if t.get("team_side") == "CT" else 0.0
            elif isB and not isA:
                rec["eqB"] = t.get("equipment_value"); rec["elB"] = t.get("economy_level")
        out.append(rec)
    return out


def main():
    h = shared_client()
    slugs = bo3_maps(h)
    mk = json.load(open(OUT / "markets_dev.json"))
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "price", "cid", "oi", "role"])
    o = o[(o.role == "maker") & (o.sign_ms / 1000 < H)]
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    bad = set(cd.loc[cd.maker == WALLET, "tx"])
    rows = []
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
        a, b = norm(outs[0])[:6], norm(outs[1])[:6]
        fa, fb = norm(outs[0]), norm(outs[1])
        cand = [s for s in slugs if a in norm(s) and b in norm(s)]
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
        wn = [norm(z.get("winner_clan_name")) for z in rounds]
        isa = np.array([(w[:6] == a) or (len(w) >= 3 and (w in fa or fa in w)) for w in wn])
        isb = np.array([(w[:6] == b) or (len(w) >= 3 and (w in fb or fb in w)) for w in wn])
        if (isa & isb).any() or (isa | isb).mean() < 0.95 or isa.sum() == 0 or isb.sum() == 0:
            continue
        win = isa.astype(int)
        ec = econ_of(rounds, fa, fb)
        oo = oo.assign(tok=oo.oi.astype(int))
        oo = oo[(oo.price > 0.06) & (oo.price < 0.94)].sort_values(["tok", "sign_ms"])
        if len(oo) < 30:
            continue
        newb = (oo.tok.diff() != 0) | (oo.sign_ms.diff() > 50)
        oo["bid"] = newb.cumsum()
        bb = oo.groupby("bid").agg(sign_ms=("sign_ms", "min"), price=("price", "max"), tok=("tok", "first")).sort_values("sign_ms")
        y = np.where(bb.tok == 0, bb.price, 1 - bb.price).astype(float)
        tok = bb.tok.to_numpy(int); tt = bb.sign_ms.to_numpy() / 1000.0
        W = win[None, :]
        fv = fit(y, tok, tt, W)
        path = fv["path"][0]; res = fv["res"][0]
        inc = np.where(np.diff(path) > 0)[0] + 1
        # print control at the same times
        tp = TAPES / f"{cid}_tkw.parquet"
        yp = None
        if tp.exists():
            d = pd.read_parquet(tp)
            d = d[(d.timestamp < H) & ~d.transactionHash.isin(bad)].sort_values("timestamp")
            if len(d) >= 20:
                ts = d.timestamp.to_numpy(float)
                pa = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
                j = np.searchsorted(ts, tt, side="right") - 1
                yp = np.where(j >= 0, pa[np.maximum(j, 0)], np.nan)
        rp = None
        if yp is not None and np.isfinite(yp).sum() >= 30:
            okp = np.isfinite(yp)
            fp = fit(yp[okp], tok[okp] * 0, tt[okp], W)
            rp = (fp["path"][0], fp["res"][0])
        for i in inc:
            k = int(path[i])  # rounds completed; the burst is in round k+1 (index k)
            if k >= len(ec):
                continue
            e = ec[k]
            row = {"cid": cid, "build": pd.Timestamp(x.get("gameStartTime")).timestamp() < SPLIT, "k": k, "res_v": float(res[i]),
                   "y": float(y[i]), "tok": int(tok[i]), "yp": float(yp[i]) if yp is not None and np.isfinite(yp[i]) else np.nan,
                   "prevA": float(2 * win[k - 1] - 1) if k >= 1 else np.nan, "prev2A": float(win[max(k - 3, 0):k].sum() * 2 - min(k, 3)) if k >= 1 else np.nan,
                   "scoreA": float(win[:k].sum() - (k - win[:k].sum())), "dt_prev": float(tt[i] - tt[i - 1]) if i >= 1 else np.nan,
                   "eq_diff": (e["eqA"] - e["eqB"]) / 1000.0 if e["eqA"] is not None and e["eqB"] is not None else np.nan,
                   "el_diff": (e["elA"] - e["elB"]) if e["elA"] is not None and e["elB"] is not None else np.nan,
                   "sideA_CT": e["sideA_CT"]}
            rows.append(row)
        if rp is not None:
            pinc = np.where(np.diff(rp[0]) > 0)[0] + 1
            for i in pinc:
                k = int(rp[0][i])
                if k >= len(ec):
                    continue
                e = ec[k]
                rows.append({"cid": cid, "build": pd.Timestamp(x.get("gameStartTime")).timestamp() < SPLIT, "k": k, "res_p": float(rp[1][i]),
                             "eq_diff": (e["eqA"] - e["eqB"]) / 1000.0 if e["eqA"] is not None and e["eqB"] is not None else np.nan,
                             "el_diff": (e["elA"] - e["elB"]) if e["elA"] is not None and e["elB"] is not None else np.nan,
                             "sideA_CT": e["sideA_CT"]})
    D = pd.DataFrame(rows)
    D.to_parquet(OUT / "iter12/round_econ_rows.parquet", index=False)
    rng = np.random.default_rng(5)
    out = {}
    import statsmodels.api as sm
    for col in ("res_v", "res_p"):
        S = D.dropna(subset=[col, "eq_diff"]).copy()
        S = S[np.isfinite(S.eq_diff)]
        rho = S[[col, "eq_diff"]].corr(method="spearman").iloc[0, 1]
        cids = S.cid.unique(); boots = []
        for _ in range(1000):
            pick = rng.choice(cids, len(cids), replace=True)
            Z = pd.concat([S[S.cid == c_] for c_ in pick])
            boots.append(Z[[col, "eq_diff"]].corr(method="spearman").iloc[0, 1])
        X = sm.add_constant(S[["eq_diff", "sideA_CT"]].fillna(0.5))
        ols = sm.OLS(S[col], X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(S.cid)[0]})
        out[col] = {"n": int(len(S)), "maps": int(S.cid.nunique()), "spearman_eq": round(float(rho), 3),
                    "ci95": [round(float(np.nanpercentile(boots, 2.5)), 3), round(float(np.nanpercentile(boots, 97.5)), 3)],
                    "ols_eq_coef_c_per_1k": round(float(ols.params["eq_diff"] * 100), 3), "ols_eq_t": round(float(ols.tvalues["eq_diff"]), 2),
                    "ols_ct_coef_c": round(float(ols.params["sideA_CT"] * 100), 3)}
    S = D.dropna(subset=["res_v", "eq_diff", "yp"]).copy()
    S["offset"] = S.y - S.yp
    X = sm.add_constant(S[["eq_diff", "tok"]].astype(float))
    ols = sm.OLS(S.offset, X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(S.cid)[0]})
    rho = S.assign(o2=S.offset - S.groupby("tok").offset.transform("mean"))[["o2", "eq_diff"]].corr(method="spearman").iloc[0, 1]
    S2 = S.dropna(subset=["prevA", "prev2A"]).copy()
    X2 = sm.add_constant(S2[["eq_diff", "tok", "prevA", "prev2A", "scoreA"]].astype(float))
    ols2 = sm.OLS(S2.offset, X2).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(S2.cid)[0]})
    out["offset_vs_print_ctrl_prev_rounds"] = {"n": int(len(S2)), "eq_coef_c_per_1k": round(float(ols2.params["eq_diff"] * 100), 3), "eq_t": round(float(ols2.tvalues["eq_diff"]), 2),
                                               "prevA_coef_c": round(float(ols2.params["prevA"] * 100), 3), "prevA_t": round(float(ols2.tvalues["prevA"]), 2),
                                               "prev2A_coef_c": round(float(ols2.params["prev2A"] * 100), 3), "scoreA_coef_c": round(float(ols2.params["scoreA"] * 100), 3)}
    for nm_, sub in (("prev_A_won", S2[S2.prevA > 0]), ("prev_A_lost", S2[S2.prevA < 0])):
        X3 = sm.add_constant(sub[["eq_diff", "tok"]].astype(float))
        o3 = sm.OLS(sub.offset, X3).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(sub.cid)[0]})
        out[f"offset_vs_print_{nm_}"] = {"n": int(len(sub)), "eq_coef_c_per_1k": round(float(o3.params["eq_diff"] * 100), 3), "eq_t": round(float(o3.tvalues["eq_diff"]), 2)}
    out["offset_vs_print"] = {"n": int(len(S)), "maps": int(S.cid.nunique()), "spearman_eq_tokdemeaned": round(float(rho), 3),
                              "ols_eq_coef_c_per_1k": round(float(ols.params["eq_diff"] * 100), 3), "ols_eq_t": round(float(ols.tvalues["eq_diff"]), 2)}
    (RES / "results/round_econ.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
