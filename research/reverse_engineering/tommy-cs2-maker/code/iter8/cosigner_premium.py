"""Iteration 8, X105 (information panel iter7 P5): value or raw events? On co-signed events (the wallet and P4e BUY the
same token within 120 ms, 16-22 Oct full matched-order record), each signer's premium = its limit minus the event's
stale ask a_e (the lowest ask-equivalent price filled in ANY transaction of the cluster: the first level consumed).
A value-carrying feed predicts limit_i = V_e - m_i: premiums correlated across signers with a near-constant offset
(residual SD of the difference < 1c), beyond what the realised move explains. Raw events predict premiums that are
correlated only through the event's realised move. Reported: corr(prem_wallet, prem_P4e), partial correlation given
the 60-s realised move, SD of the limit difference, and the same for P4e vs P93 (pairs within 700 ms).
Output: results/cosigner_premium.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
P4E = "0x4ebc2722adc772bde8680792d0a6fdf15499a33d"
P93 = "0x93078b5dd1c34d0f288d2f51b23f1347520d9da3"
H = 1792713600


def main():
    cols = ["tx", "idx", "maker", "side", "token_id", "price", "shares", "sign_ms", "fill"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)
    b = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted((OUT / "calldata_pub").glob("*.parquet"))])
    cd = pd.concat([a, b[~b.tx.isin(set(a.tx))]], ignore_index=True)
    cd["maker"] = cd.maker.str.lower()
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "token_id", "oi"]).drop_duplicates("token_id")
    tok = {str(k): (c, i) for k, c, i in zip(o.token_id, o.cid, o.oi)}
    cd["tok"] = cd.token_id.astype(str)
    cd = cd[cd.tok.isin(tok)].copy()
    cd["cid"] = cd.tok.map(lambda t: tok[t][0])
    cd["oi"] = cd.tok.map(lambda t: tok[t][1])
    tk = cd[(cd.idx == -1) & (cd.side == 0) & (cd.sign_ms > 1.79e12) & (cd.sign_ms < H * 1000)].drop_duplicates("tx")
    mk = cd[cd.idx >= 0]
    x = mk.tx.map(dict(zip(tk.tx, tk.oi)))
    mk = mk.assign(aeq=np.where((mk.side == 1) & (mk.oi == x), mk.price, np.where((mk.side == 0) & (mk.oi != x), 1 - mk.price, np.nan)))
    first = mk.groupby("tx").aeq.min()
    tk = tk.assign(a=tk.tx.map(first))
    # public price path of token 0 from all takers' fills (approximate: limit-capped fill levels by sign time)
    pth = {}
    for cid, g in tk[tk.a.notna()].groupby("cid"):
        p0 = np.where(g.oi == 0, g.a, 1 - g.a)
        s = np.argsort(g.sign_ms.to_numpy())
        pth[cid] = (g.sign_ms.to_numpy(float)[s], p0[s])

    def move60(cid, t, oi, a0):
        ts, p0 = pth.get(cid, (np.array([]), np.array([])))
        j = np.searchsorted(ts, t + 60000, side="right") - 1
        if j < 0 or ts[j] <= t + 5000:
            return np.nan
        pv = p0[j] if oi == 0 else 1 - p0[j]
        return pv - a0

    res = {}
    for name, lead, foll, lo, hi in (("wallet_vs_p4e", P4E, W, 0, 120), ("p93_vs_p4e", P4E, P93, 150, 700)):
        L = tk[tk.maker == lead]
        F = {k: g for k, g in tk[tk.maker == foll].groupby("tok")}
        rows = []
        for r in L.itertuples():
            g = F.get(r.tok)
            if g is None:
                continue
            d = g.sign_ms.to_numpy(float) - r.sign_ms
            m = (d >= lo) & (d <= hi)
            if not m.any():
                continue
            f = g[m].iloc[0]
            # cluster stale ask: min ask-equivalent over both transactions
            ae = np.nanmin([r.a if r.a == r.a else np.nan, f.a if f.a == f.a else np.nan])
            if not np.isfinite(ae):
                continue
            rows.append({"cid": r.cid, "pl": r.price - ae, "pf": f.price - ae, "dl": f.price - r.price,
                         "mv": move60(r.cid, r.sign_ms, int(r.oi), ae)})
        D = pd.DataFrame(rows).dropna()
        o = {"pairs": int(len(D)), "events": int(D.cid.nunique()) if len(D) else 0}
        if len(D) >= 10:
            o["prem_lead_mean_c"] = round(float(D.pl.mean() * 100), 2)
            o["prem_follow_mean_c"] = round(float(D.pf.mean() * 100), 2)
            o["corr_premiums"] = round(float(np.corrcoef(D.pl, D.pf)[0, 1]), 3)
            o["corr_lead_move60"] = round(float(np.corrcoef(D.pl, D.mv)[0, 1]), 3)
            o["corr_follow_move60"] = round(float(np.corrcoef(D.pf, D.mv)[0, 1]), 3)
            Z = np.c_[np.ones(len(D)), D.mv]
            rl = D.pl - Z @ np.linalg.lstsq(Z, D.pl, rcond=None)[0]
            rf = D.pf - Z @ np.linalg.lstsq(Z, D.pf, rcond=None)[0]
            o["partial_corr_given_move60"] = round(float(np.corrcoef(rl, rf)[0, 1]), 3)
            o["limit_diff_sd_c"] = round(float(D.dl.std() * 100), 2)
            o["limit_diff_median_c"] = round(float(D.dl.median() * 100), 2)
            o["share_limit_diff_within_1c"] = round(float((D.dl.abs() <= 0.0101).mean()), 3)
        res[name] = o
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "cosigner_premium.json", "w"), indent=1)


if __name__ == "__main__":
    main()
