"""Iteration 3: a point-in-time 'pack coverage' selection feature (feed-coverage proxy, U7).

For every CS2 event of 16-22 Oct (events_sel_bo3.parquet, complete universe), pack presence = any in-play taker print
by the informed pack (0x4ebc2722, 0x93078b5d, the 3-wallet cluster, 0xf1ee4842) in [gs, gs + 4 h] over the event's
markets (windowed taker tapes). Lagged league feature for event e: the pack-presence rate of earlier events of the same
league whose game started more than 4 h before e (their in-play window is over), shrunk (k = 3) toward the rate of all
earlier non-GRID events. Only 16-22 Oct events feed it (the earlier tapes cover a wallet-selected subset, which would
leak its later choices). Logistic models fitted on BUILD, scored on VALIDATE, against activity A and activity + GRID G.
Output: results/selection_pack_lag.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET  # noqa: E402
from selection_bo3 import boot_gain, rec_lift  # noqa: E402

VAL0, H = 1792540800, 1792713600
PACKS = {"0x4ebc2722adc772bde8680792d0a6fdf15499a33d", "0x93078b5dd1c34d0f288d2f51b23f1347520d9da3",
         "0xfe8a28be83ba295a9384f72f240d2cfa96bc23ce", "0x2529c68db36ce8aa64c64affe620267744a3548a",
         "0x72aaaaf9f6b0286e390de5b568af0f99a00c90e0", "0xf1ee4842fa0c7283632185e42577027452d4519c"}


def main():
    e = pd.read_parquet(OUT / "events_sel_bo3.parquet")
    u = pd.read_parquet(OUT / "universe.parquet", columns=["event_slug", "cid", "smt"])
    u = u[u.smt.isin(["moneyline", "child_moneyline"]) & u.event_slug.isin(e.event_slug)]
    pres, cov = {}, {}
    for ev, g in u.groupby("event_slug"):
        gs = float(e.loc[e.event_slug == ev, "gs"].iloc[0])
        hit, have = False, False
        for cid in g.cid:
            p = OUT / "tapes" / f"{cid}_tkw.parquet"
            if not p.exists():
                continue
            have = True
            d = pd.read_parquet(p, columns=["proxyWallet", "timestamp"])
            ts = d.timestamp.astype(float)
            if (d.proxyWallet.str.lower().isin(PACKS) & (ts >= gs) & (ts < gs + 4 * 3600)).any():
                hit = True
                break
        pres[ev], cov[ev] = hit, have
    e["pack"] = e.event_slug.map(pres).fillna(False).astype(bool)
    e["tape"] = e.event_slug.map(cov).fillna(False).astype(bool)
    e = e.sort_values("gs").reset_index(drop=True)
    lag = []
    for i, r in e.iterrows():
        prev = e[(e.gs < r.gs - 4 * 3600) & e.tape]
        base = prev[~prev.grid].pack.mean() if len(prev[~prev.grid]) else 0.0
        pl = prev[prev.league == r.league]
        lag.append((pl.pack.sum() + 3 * base) / (len(pl) + 3) if not r.grid else 0.0)
    e["pack_lag"] = lag
    e["la"] = np.log1p(e.e_pre_n.fillna(0))
    e["lv"] = np.log1p(e.e_pre_v.fillna(0))
    e["lw"] = np.log1p(e.e_pre_w.fillna(0))
    e["grid_f"] = e.grid.astype(float)
    bu, va = e[e.gs < VAL0], e[(e.gs >= VAL0) & (e.gs < H)]
    res = {"events": int(len(e)), "tape_coverage": round(float(e.tape.mean()), 3),
           "pack_present_by_traded_nonGRID": e[~e.grid].groupby("y").pack.mean().round(3).to_dict()}
    feats = {"A": ["la", "lv", "lw"], "G": ["la", "lv", "lw", "grid_f"], "GP": ["la", "lv", "lw", "grid_f", "pack_lag"]}
    sc = {}
    for k, f in feats.items():
        lr = LogisticRegression(max_iter=2000).fit(bu[f].astype(float), bu.y)
        sc[k] = (lr.predict_proba(bu[f].astype(float))[:, 1], lr.predict_proba(va[f].astype(float))[:, 1], dict(zip(f, np.round(lr.coef_[0], 3))))
    y = va.y.to_numpy()
    for k, (sb, sv, coef) in sc.items():
        ci, p = boot_gain(y, sv, sc["A"][1], None) if k != "A" else (None, None)
        rec, lift = rec_lift(bu.y.to_numpy(), sb, y, sv)
        days = {}
        for dn, msk in (("10-21", (va.gs < VAL0 + 86400).to_numpy()), ("10-22", (va.gs >= VAL0 + 86400).to_numpy())):
            days[dn] = round(roc_auc_score(y[msk], sv[msk]) - roc_auc_score(y[msk], sc["A"][1][msk]), 4)
        res[k] = {"auc": round(roc_auc_score(y, sv), 4), "gain_vs_A": round(roc_auc_score(y, sv) - roc_auc_score(y, sc["A"][1]), 4),
                  "gain_ci95": ci, "p_gain_le0": p, "recall": rec, "lift": lift, "coef": coef, "gain_by_day": days}
    newl = ~va.league.isin(set(bu.league))
    res["new_league_validate_events"] = {"n": int(newl.sum()), "traded": int(va[newl].y.sum()),
                                         "auc_GP": round(roc_auc_score(y[newl.to_numpy()], sc["GP"][1][newl.to_numpy()]), 3) if va[newl].y.nunique() > 1 else None,
                                         "auc_G": round(roc_auc_score(y[newl.to_numpy()], sc["G"][1][newl.to_numpy()]), 3) if va[newl].y.nunique() > 1 else None}
    json.dump(res, open(RES / "selection_pack_lag.json", "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
