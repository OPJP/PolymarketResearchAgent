"""Iteration 9, X123 (mechanics panel iter8 P1) and X119 step 3 (information P2): a public game-state fair value V as the
Dota maker's quote anchor. Pre-registered in NOTES iteration 9.

V = P(radiant wins | gold lead, xp lead, kill lead, minute): logistic fitted on OpenDota pro matches of 10-08..10-20
(dota_train_minutes.parquet; no wallet data, test maps excluded). Clock: wall(tau) = start_time + D + tau with D per map
from P4e's takes only (finding 24, wallet-independent; maps without P4e anchors take the other map of the series; the
10-31 maps take the 10-22 ty-gl value of the same tournament). The public state at signing time t is the state at
tau(t) - 5 s (the brief's +5-s rule for a play at its broadcast time).
Orders: the wallet's maker BUY orders (unique salt / sign_ms) on the Dota map-winner markets of 10-22 (VALIDATE) and
10-31 12-18 (BUILD-live). Anchors (within one in-play tick = 0.01):
  lp      last public taker print on the token >= 2 s before signing (wallet transactions excluded)
  lp_s    floor((lp - s) x 100) / 100, s fitted on the other period
  dv      floor((lp + dV - s) x 100) / 100, dV = V(tau(t) - 5) - V(tau(t_lp) - 5): the game-state change since the print
  vabs    floor((V(tau(t) - 5) - s) x 100) / 100
and dv at shifted clocks D +- 120 / 300 s (placebos). Also Spearman(price - lp, dV) per clock.
Output: results/dota_v_anchor.json
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
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
from polyrea.adapters.http import shared_client  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import final_rule as F  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
SERIES = {"dota2-ty-gl-2026-10-22": [9056215433, 9056271057], "dota2-liquid-1win-2026-10-22": [9056618744, 9056794318],
          "dota2-ts8-legion1-2026-10-22": [9056353535, 9056429802], "dota2-ty-gl-2026-10-31": [9069952836, 9070062078]}
D_P4E = {9056215433: 1043, 9056271057: 1050, 9056618744: 1033, 9056794318: 1033, 9056353535: 840, 9056429802: 840,
         9069952836: 1046, 9070062078: 1046}  # P4e-only fits; fallbacks: same series' other map / same tournament


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def fit_v():
    from sklearn.linear_model import LogisticRegression
    d = pd.read_parquet(OUT / "dota_train_minutes.parquet")
    X = feats(d.gold_adv.to_numpy(), d.xp_adv.to_numpy(), d.kill_diff.to_numpy(), d.minute.to_numpy())
    lr = LogisticRegression(max_iter=5000, C=1.0).fit(X, d.radiant_win)
    from sklearn.metrics import roc_auc_score
    return lr, {"rows": int(len(d)), "matches": int(d.match_id.nunique()), "insample_auc": round(float(roc_auc_score(d.radiant_win, lr.predict_proba(X)[:, 1])), 4),
                "coef": [round(float(c), 4) for c in lr.coef_[0]]}


def feats(g, x, k, m):
    g, x, k, m = (np.asarray(v, float) for v in (g, x, k, m))
    mm = np.maximum(m, 1) / 30.0
    return np.column_stack([g / 1e3, x / 1e3, k, g / 1e3 / mm, x / 1e3 / mm, k / mm])


def main():
    lr, vinfo = fit_v()
    h = shared_client()
    ud = pd.read_parquet(OUT / "universe_dota.parquet")
    ud = ud[ud.event_slug.isin(SERIES) & (ud.smt == "child_moneyline")]
    mk, _ = PolymarketData().markets_by_condition(sorted(ud.cid))
    cd = pd.concat([pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "token_id", "price", "shares", "sign_ms", "salt"]),
                    pd.read_parquet(OUT / "calldata_dev.parquet", columns=["tx", "idx", "maker", "token_id", "price", "shares", "sign_ms", "salt"])])
    cd["maker"] = cd.maker.str.lower()
    cd["token_id"] = cd.token_id.astype(str)
    wtx = set(cd.loc[cd.maker == W, "tx"])
    wo = cd[(cd.maker == W) & (cd.idx != -1)].drop_duplicates(["salt", "sign_ms"])
    rows = []
    for ev, mids in SERIES.items():
        for r in ud[ud.event_slug == ev].itertuples():
            x = mk.get(r.cid) or {}
            mm = re.search(r"Game (\d)", x.get("question", ""))
            if not mm or int(mm.group(1)) > len(mids):
                continue
            mid = mids[int(mm.group(1)) - 1]
            g, _ = h.get_json(f"https://api.opendota.com/api/matches/{mid}", {}, adapter="opendota.match", max_age=None)
            ga, xa = g.get("radiant_gold_adv") or [], g.get("radiant_xp_adv") or []
            if not ga:
                continue
            rn = norm(g.get("radiant_name") or (g.get("radiant_team") or {}).get("name"))
            dn = norm(g.get("dire_name") or (g.get("dire_team") or {}).get("name"))
            kt = np.array([(k["time"], 1 if p.get("player_slot", 0) < 128 else -1) for p in g.get("players") or [] for k in (p.get("kills_log") or [])], float)
            outs = json.loads(x["outcomes"]) if isinstance(x.get("outcomes"), str) else x.get("outcomes")
            toks = json.loads(x["clobTokenIds"]) if isinstance(x.get("clobTokenIds"), str) else x.get("clobTokenIds")
            sgn = {}
            for i, nm in enumerate(outs):
                n5 = norm(nm)[:5]
                sgn[str(toks[i])] = 1 if n5 and n5 in rn else (-1 if n5 and n5 in dn else 0)
            tp = F._tape(r.cid, int(r.gs_ts), F.H if r.gs_ts < F.H else int(r.gs_ts) + 5 * 3600)
            tp = tp[~tp.transactionHash.isin(wtx)].sort_values("timestamp")
            tts = tp.timestamp.to_numpy(float)
            p0 = np.where(tp.outcomeIndex.astype(int) == 0, tp.price.astype(float), 1 - tp.price.astype(float))
            st = float(g["start_time"])
            D0 = D_P4E[mid]

            def vr(tau):  # radiant win prob at game time tau (public: last completed minute, kills up to tau)
                tau = np.asarray(tau, float)
                mi = np.clip(np.floor(tau / 60).astype(int), 0, len(ga) - 1)
                gg = np.array(ga, float)[mi]
                xx = np.array(xa, float)[np.clip(mi, 0, len(xa) - 1)]
                kd = np.array([kt[kt[:, 0] <= t_, 1].sum() if len(kt) else 0 for t_ in tau])
                v = lr.predict_proba(feats(gg, xx, kd, mi))[:, 1]
                return np.where(tau < 0, 0.5, v)
            o = wo[wo.token_id.isin([str(t) for t in toks])]
            for q in o.itertuples():
                s_ = sgn.get(q.token_id, 0)
                if s_ == 0:
                    continue
                t = q.sign_ms / 1000
                k = np.searchsorted(tts, t - 2, side="right") - 1
                if k < 0:
                    continue
                oi = [str(z) for z in toks].index(q.token_id)
                lp = p0[k] if oi == 0 else 1 - p0[k]
                rec = {"series": ev, "map": int(mm.group(1)), "match_id": mid, "price": float(q.price), "lp": float(lp),
                       "t": t, "tlp": float(tts[k]), "period": "validate" if r.gs_ts < F.H else "build_live"}
                for name, D in (("true", D0), ("m120", D0 - 120), ("p120", D0 + 120), ("m300", D0 - 300), ("p300", D0 + 300)):
                    tau, taul = t - st - D - 5, tts[k] - st - D - 5
                    v, vl = vr([tau, taul])
                    vt, vlt = (v, vl) if s_ == 1 else (1 - v, 1 - vl)
                    rec[f"v_{name}"] = float(vt)
                    rec[f"dv_{name}"] = float(vt - vlt)
                    rec[f"tau_{name}"] = float(tau)
                rows.append(rec)
    A = pd.DataFrame(rows)
    A = A[(A.tau_true > 0) & (A.tau_true < 3600)]
    res = {"v_model": vinfo, "orders": int(len(A)), "by_period": {k: int(v) for k, v in A.period.value_counts().items()}}

    def within(pred, p):
        return float((np.abs(np.asarray(pred) - np.asarray(p)) <= 0.01 + 1e-9).mean())

    def fl(x):
        return np.floor(np.asarray(x) * 100 + 1e-9) / 100

    from scipy.stats import spearmanr
    out = {}
    for test in ("validate", "build_live"):
        tr, te = A[A.period != test], A[A.period == test]
        if len(te) < 10 or len(tr) < 10:
            continue
        grid = np.arange(-0.03, 0.08, 0.005)
        s_lp = grid[np.argmax([within(fl(tr.lp - s), tr.price) for s in grid])]
        s_dv = grid[np.argmax([within(fl(tr.lp + tr.dv_true - s), tr.price) for s in grid])]
        s_va = grid[np.argmax([within(fl(tr.v_true - s), tr.price) for s in grid])]
        o = {"n": int(len(te)), "lp_round": within(np.round(te.lp, 2), te.price), "lp_s": within(fl(te.lp - s_lp), te.price),
             "s_lp": round(float(s_lp), 3), "dv": within(fl(te.lp + te.dv_true - s_dv), te.price), "s_dv": round(float(s_dv), 3),
             "vabs": within(fl(te.v_true - s_va), te.price), "s_vabs": round(float(s_va), 3)}
        for name in ("m120", "p120", "m300", "p300"):
            o[f"dv_{name}"] = within(fl(te.lp + te[f"dv_{name}"] - s_dv), te.price)
        for name in ("true", "m120", "p120", "m300", "p300"):
            rho, p = spearmanr(te.price - te.lp, te[f"dv_{name}"])
            o[f"spearman_dev_vs_dv_{name}"] = [round(float(rho), 3), float(p)]
        b = np.polyfit(te.dv_true, te.price - te.lp, 1)
        o["slope_dev_on_dv_true"] = round(float(b[0]), 3)
        o["share_dv_nonzero"] = round(float((np.abs(te.dv_true) > 0.005).mean()), 3)
        out[test] = o
    res["scores"] = out
    A.to_parquet(OUT / "dota_v_anchor_rows.parquet", index=False)
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "dota_v_anchor.json", "w"), indent=1)


if __name__ == "__main__":
    main()
