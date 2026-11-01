"""X167 step 1 (assumptions panel iter-11 P1, historical pass): is the wallet's Dota level a learnable map of PUBLIC game
state? An inverse fit of its own filled-order prices (not an outcome model as X123).

Maps and clock as code/iter9/dota_v_anchor.py (the 6 Dota maps of 10-22 plus the 2 of 10-31 BUILD-live; OpenDota per-minute
radiant gold / xp advantage and per-kill times; wall(tau) = start_time + D + tau with D from P4e's takes only; public
state at tau(t) - 5 s). Features oriented to the order's team: gold lead, xp lead, kill lead (k$ / k / count), minute,
their per-minute-scaled versions, and the map's pre-game prior logit(last public print before tau = 0).
Models (leave one map out): (a) logistic-link least squares price = sigmoid(w . [logit prior, state]); (b) LightGBM on the
same features (max_bin 63); (c) last public print >= 2 s before signing (lp); (d) lp + the model's change since the
print. Within one tick (1c) of its price, per map and pooled; placebo: state at clocks shifted by +-300 s.
Output: results/dota_inverse_fit.json
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
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter9"))
from polyrea.adapters.http import shared_client  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import final_rule as F  # noqa: E402
from dota_v_anchor import D_P4E, SERIES, W, norm  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def main():
    h = shared_client()
    ud = pd.read_parquet(OUT / "universe_dota.parquet")
    ud = ud[ud.event_slug.isin(SERIES) & (ud.smt == "child_moneyline")]
    mk, _ = PolymarketData().markets_by_condition(sorted(ud.cid))
    cd = pd.concat([pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "token_id", "price", "shares", "sign_ms", "salt"]),
                    pd.read_parquet(OUT / "calldata_dev.parquet", columns=["tx", "idx", "maker", "token_id", "price", "shares", "sign_ms", "salt"])])
    cd["maker"] = cd.maker.str.lower(); cd["token_id"] = cd.token_id.astype(str)
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
            ga, xa = np.array(g.get("radiant_gold_adv") or [], float), np.array(g.get("radiant_xp_adv") or [], float)
            if not len(ga):
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
            st = float(g["start_time"]); D0 = D_P4E[mid]

            def state(tau):
                mi = int(np.clip(np.floor(tau / 60), 0, len(ga) - 1))
                kd = float(kt[kt[:, 0] <= tau, 1].sum()) if len(kt) else 0.0
                return ga[mi] / 1e3, xa[min(mi, len(xa) - 1)] / 1e3 if len(xa) else 0.0, kd, max(tau, 0) / 60.0
            k0 = np.searchsorted(tts, st + D0, side="right") - 1
            prior0 = p0[k0] if k0 >= 0 else np.nan
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
                prior = prior0 if oi == 0 else 1 - prior0
                rec = {"series": ev, "map": f"{ev}#{mm.group(1)}", "price": float(q.price), "lp": float(lp), "prior": float(prior),
                       "period": "validate" if r.gs_ts < F.H else "build_live"}
                for name, D in (("true", D0), ("m300", D0 - 300), ("p300", D0 + 300)):
                    tau = t - st - D - 5
                    taul = tts[k] - st - D - 5
                    gg, xx, kk, mn = state(tau)
                    g2, x2, k2, m2 = state(taul)
                    rec.update({f"g_{name}": s_ * gg, f"x_{name}": s_ * xx, f"k_{name}": s_ * kk, f"m_{name}": mn, f"tau_{name}": tau,
                                f"gl_{name}": s_ * g2, f"xl_{name}": s_ * x2, f"kl_{name}": s_ * k2, f"ml_{name}": m2})
                rows.append(rec)
    A = pd.DataFrame(rows)
    A = A[(A.tau_true > 0) & (A.tau_true < 3600) & np.isfinite(A.prior)].copy()
    A.to_parquet(OUT / "iter12/dota_inverse_rows.parquet", index=False)

    def X_of(df, name, lag=False):
        p = np.clip(df.prior.to_numpy(), 0.02, 0.98)
        pre = "l" if lag else ""
        g, x, k = df[f"g{pre}_{name}"].to_numpy(), df[f"x{pre}_{name}"].to_numpy(), df[f"k{pre}_{name}"].to_numpy()
        m = np.maximum(df[f"m{pre}_{name}"].to_numpy(), 1) / 30.0
        return np.column_stack([np.log(p / (1 - p)), g, x, k, g / m, x / m, k / m])

    from scipy.optimize import least_squares
    import lightgbm as lgb

    def sig(z):
        return 1 / (1 + np.exp(-z))
    out = {"orders": int(len(A)), "maps": int(A["map"].nunique()), "by_map_n": A.groupby("map").size().to_dict()}
    for name in ("true", "m300", "p300"):
        pred_ls = np.full(len(A), np.nan); pred_gb = np.full(len(A), np.nan); pred_d = np.full(len(A), np.nan)
        for mp in A["map"].unique():
            te = (A["map"] == mp).to_numpy()
            Xtr, ytr = X_of(A[~te], name), A.price.to_numpy()[~te]
            f = lambda w: sig(Xtr @ w[1:] + w[0]) - ytr  # noqa: E731
            w = least_squares(f, np.r_[0.0, 1.0, np.zeros(Xtr.shape[1] - 1)]).x
            Xte = X_of(A[te], name)
            pred_ls[te] = sig(Xte @ w[1:] + w[0])
            Xl = X_of(A[te], name, lag=True)
            pred_d[te] = A.lp.to_numpy()[te] + (sig(Xte @ w[1:] + w[0]) - sig(Xl @ w[1:] + w[0]))
            m = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.05, num_leaves=15, max_bin=63, min_child_samples=20, verbose=-1)
            m.fit(Xtr, ytr)
            pred_gb[te] = m.predict(Xte)
        r = {}
        for nm_, pr in (("logistic_ls", pred_ls), ("lgbm", pred_gb), ("lp_plus_dmodel", pred_d)):
            hit = np.abs(np.round(pr, 2) - A.price.to_numpy()) <= 0.0101
            r[nm_] = {"within_tick": round(float(hit.mean()), 3), "mae_c": round(float(np.nanmean(np.abs(pr - A.price.to_numpy())) * 100), 2),
                      "by_period": {k: round(float(hit[(A.period == k).to_numpy()].mean()), 3) for k in A.period.unique()}}
        out[f"clock_{name}"] = r
    hit_lp = np.abs(A.lp.to_numpy() - A.price.to_numpy()) <= 0.0101
    out["last_print"] = {"within_tick": round(float(hit_lp.mean()), 3), "mae_c": round(float(np.mean(np.abs(A.lp - A.price)) * 100), 2),
                         "by_period": {k: round(float(hit_lp[(A.period == k).to_numpy()].mean()), 3) for k in A.period.unique()}}
    (RES / "dota_inverse_fit.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
