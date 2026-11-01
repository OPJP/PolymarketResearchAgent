"""X181 (assumptions panel iter-12 P2), historical: does its value move WITHIN a round toward the round's winner more
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
        nmaps += 1
        # wallet token offsets: put both tokens on one scale (subtract the per-token median gap to the print)
        off = {s: float(np.median((y - yp)[tok == s])) if (tok == s).any() else 0.0 for s in (0, 1)}
        yc = y - np.array([off[s] for s in tok])
        ks = np.unique(path)
        for ki, k in enumerate(ks):
            m = np.where(path == k)[0]
            if len(m) < 2 or k >= len(win):
                continue
            i0, i1 = m[0], m[-1]
            t_next = tt[np.where(path == ks[ki + 1])[0][0]] if ki + 1 < len(ks) else np.inf
            rec = {"cid": cid, "build": bool(pd.Timestamp(x.get("gameStartTime")).timestamp() < R.SPLIT), "round": int(k), "A_won": int(win[k]), "dW": float(yc[i1] - yc[i0]), "dP": float(yp[i1] - yp[i0]),
                   "n": int(len(m)), "dur": float(tt[i1] - tt[i0])}
            # before the print's first move of >= 2c (either direction) inside the round
            mv = np.where(np.abs(yp[m] - yp[i0]) >= 0.02 - 1e-9)[0]
            mpre = m[: mv[0]] if len(mv) else m
            if len(mpre) >= 2:
                rec["dW_pre"] = float(yc[mpre[-1]] - yc[mpre[0]])
                rec["dP_pre"] = float(yp[mpre[-1]] - yp[mpre[0]])
                rec["pre_print_moved_later"] = bool(len(mv) > 0)
            for esec in EARLY:
                me = m[(tt[m] <= tt[i0] + esec) & (tt[m] <= t_next - 10)]
                if len(me) >= 2:
                    rec[f"dW_e{esec}"] = float(yc[me[-1]] - yc[me[0]])
                    rec[f"dP_e{esec}"] = float(yp[me[-1]] - yp[me[0]])
            for gsec in GUARDS:
                mg = m[tt[m] <= t_next - gsec]
                if len(mg) >= 2:
                    rec[f"dW_g{gsec}"] = float(yc[mg[-1]] - yc[mg[0]])
                    rec[f"dP_g{gsec}"] = float(yp[mg[-1]] - yp[mg[0]])
            rows.append(rec)
    D = pd.DataFrame(rows)
    out = {"maps": nmaps, "rounds": int(len(D))}
    if len(D) > 30:
        yv = D.A_won.to_numpy()
        out["auc_dW"] = round(auc(D.dW, yv), 4)
        out["auc_dP"] = round(auc(D.dP, yv), 4)
        X = np.column_stack([np.ones(len(D)), D.dP.to_numpy()])
        beta = np.linalg.lstsq(X, D.dW.to_numpy(), rcond=None)[0]
        resid = D.dW.to_numpy() - X @ beta
        out["auc_dW_resid_on_dP"] = round(auc(resid, yv), 4)
        out["share_rounds_dW_nonzero"] = round(float(np.mean(D.dW != 0)), 3)
        out["share_rounds_dP_nonzero"] = round(float(np.mean(D.dP != 0)), 3)
        rng = np.random.default_rng(13)
        maps = D.cid.unique()
        by = {c: D[D.cid == c] for c in maps}
        diffs, res_aucs = [], []
        for _ in range(2000):
            s = pd.concat([by[c] for c in rng.choice(maps, len(maps))])
            yy = s.A_won.to_numpy()
            if yy.min() == yy.max():
                continue
            diffs.append(auc(s.dW, yy) - auc(s.dP, yy))
        diffs = np.array(diffs)
        out["auc_diff_W_minus_P"] = round(out["auc_dW"] - out["auc_dP"], 4)
        out["auc_diff_ci95"] = [round(float(np.quantile(diffs, 0.025)), 4), round(float(np.quantile(diffs, 0.975)), 4)]
        out["auc_diff_p_le0"] = round(float(np.mean(diffs <= 0)), 4)
        # rounds where the print did not move inside the round
        Z = D[D.dP == 0]
        if len(Z) > 20 and Z.A_won.nunique() == 2:
            out["auc_dW_when_print_flat"] = {"n": int(len(Z)), "auc": round(auc(Z.dW, Z.A_won.to_numpy()), 4)}
        for gsec in GUARDS:
            Zg = D.dropna(subset=[f"dW_g{gsec}"])
            if len(Zg) > 30 and Zg.A_won.nunique() == 2:
                yy = Zg.A_won.to_numpy()
                out[f"guard_{gsec}s"] = {"rounds": int(len(Zg)), "auc_dW": round(auc(Zg[f"dW_g{gsec}"], yy), 4),
                                         "auc_dP": round(auc(Zg[f"dP_g{gsec}"], yy), 4)}
        out["by_split"] = {nm: {"maps": int(g.cid.nunique()), "rounds": int(len(g)), "auc_dW": round(auc(g.dW, g.A_won.to_numpy()), 4),
                                "auc_dP": round(auc(g.dP, g.A_won.to_numpy()), 4),
                                "auc_dW_pre": round(auc(g.dropna(subset=["dW_pre"]).dW_pre, g.dropna(subset=["dW_pre"]).A_won.to_numpy()), 4) if "dW_pre" in g else None,
                                "auc_dP_pre": round(auc(g.dropna(subset=["dW_pre"]).dP_pre, g.dropna(subset=["dW_pre"]).A_won.to_numpy()), 4) if "dW_pre" in g else None}
                           for nm, g in (("BUILD", D[D.build]), ("VALIDATE", D[~D.build]))}
        if "dW_pre" in D:
            Zp = D.dropna(subset=["dW_pre"])
            if len(Zp) > 30 and Zp.A_won.nunique() == 2:
                yy = Zp.A_won.to_numpy()
                out["pre_print_move"] = {"rounds": int(len(Zp)), "auc_dW": round(auc(Zp.dW_pre, yy), 4), "auc_dP": round(auc(Zp.dP_pre, yy), 4),
                                         "share_dW_nonzero": round(float(np.mean(Zp.dW_pre != 0)), 3)}
                Zm = Zp[Zp.pre_print_moved_later.astype(bool)]
                if len(Zm) > 30 and Zm.A_won.nunique() == 2:
                    out["pre_print_move"]["rounds_where_print_later_moved"] = {"rounds": int(len(Zm)), "auc_dW": round(auc(Zm.dW_pre, Zm.A_won.to_numpy()), 4)}
        for esec in EARLY:
            Ze = D.dropna(subset=[f"dW_e{esec}"])
            if len(Ze) > 30 and Ze.A_won.nunique() == 2:
                yy = Ze.A_won.to_numpy()
                out[f"early_{esec}s"] = {"rounds": int(len(Ze)), "auc_dW": round(auc(Ze[f"dW_e{esec}"], yy), 4),
                                         "auc_dP": round(auc(Ze[f"dP_e{esec}"], yy), 4)}
    (RES / "inround_drift.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
