"""Iteration 3: assumptions panel P6 (X35, versions) and P4 (X33, price at the in-play tick) plus the maker price
against the SERVER-clock book (mechanics panel critique 2).

(a) Fingerprints, VALIDATE (gameStart 10-21..10-22, orders.parquet) vs the 10-31 development block (calldata_dev,
    dev-unit markets only): taker size caps (exactly 1000 / 2000 shares), taker fill fraction, maker size mix,
    fan-out share (taker orders in two markets of one event within 50 ms).
(b) Historical price metric at the in-play tick: per market, the tick is 0.01 until the first sub-cent order in all
    public calldata (calldata_all + calldata_pub); maker orders of VALIDATE scored within one tick (0.01) of the
    last print and of the rebuilt touch (price_touch.parquet).
(c) Live (dev block, server clock): maker order price minus the token's best bid in the book 50 ms before signing
    (book from tommy_cs2_near where available, else clob_wallets); also 300 ms after (self-reference check).
Output: results/versions_price.json
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, T0, read, series_own, series_shared  # noqa: E402

VAL0, H = 1792540800, 1792713600


def main():
    res = {}
    o = pd.read_parquet(OUT / "orders.parquet")
    v = o[(o.gs_ts >= VAL0) & (o.gs_ts < H)]
    tk, mk = v[v.role == "taker"], v[v.role == "maker"]
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    dev_cids = set(m.cid)
    d = d[d.condition_id.isin(dev_cids) & (d.sign_ms > 1.79e12) & (d.sign_ms < time.time() * 1000 + 5000)]
    dt = d[(d.idx == -1) & (d.maker == WALLET)].drop_duplicates("tx")
    dm = d[(d.idx >= 0) & (d.maker == WALLET)].drop_duplicates(["salt", "sign_ms"])

    def fp_t(x, fill, sh):
        return {"n": int(len(x)), "cap_1000_2000": round(float(x[sh].round(0).isin([1000, 2000]).mean()), 3),
                "size_median": float(x[sh].median()), "fill_frac_median": round(float((x[fill] / x[sh]).median()), 3),
                "fill_frac_lt5pct": round(float(((x[fill] / x[sh]) < 0.05).mean()), 3)}

    def fp_m(x, sh):
        s = x[sh].round(0)
        return {"n": int(len(x)), "s100": round(float((s == 100).mean()), 3), "s10": round(float((s == 10).mean()), 3),
                "s11_99": round(float(((s > 10) & (s < 100)).mean()), 3), "other": round(float(((s > 100) | (s < 10)).mean()), 3),
                "whole_cent": round(float((np.abs(x["price"] * 100 - np.round(x["price"] * 100)) < 1e-6).mean()), 3)}
    res["versions"] = {"VALIDATE_taker": fp_t(tk, "filled", "shares"), "DEV_taker": fp_t(dt, "fill", "shares"),
                       "VALIDATE_maker": fp_m(mk, "shares"), "DEV_maker": fp_m(dm, "shares")}
    # (b) in-play tick
    pubs = [pd.read_parquet(OUT / "calldata_all.parquet", columns=["condition_id", "price", "sign_ms", "idx"])]
    for p in (OUT / "calldata_pub").glob("*.parquet"):
        pubs.append(pd.read_parquet(p, columns=["condition_id", "price", "sign_ms", "idx"]))
    pub = pd.concat(pubs)
    pub = pub[(pub.idx >= 0) & (pub.price > 0) & (pub.price < 1)]  # maker (resting) orders only: limit prices
    p1000 = pub.price * 1000
    sub = pub[(np.abs(p1000 - np.round(p1000)) < 1e-6) & (np.abs(pub.price * 100 - np.round(pub.price * 100)) > 1e-6)]
    res["first_subcent_maker_price_median"] = float(sub.groupby("condition_id").price.first().median()) if len(sub) else None
    first_sub = sub.groupby("condition_id").sign_ms.min()
    pt = pd.read_parquet(OUT / "price_touch.parquet")
    pt = pt[(pt.gs >= VAL0) & (pt.gs < H)].copy()
    pt["tick"] = np.where(pt.s < pt.cid.map(first_sub).fillna(np.inf), 0.01, 0.001)
    out = {"n": int(len(pt)), "tick_0.01_share": round(float((pt.tick == 0.01).mean()), 3)}
    for anc in ("last", "top", "bid"):
        a = pt[pt[anc].notna()]
        out[f"within_tick_{anc}"] = round(float((np.abs(a.q - a[anc]) <= a.tick + 1e-9).mean()), 3)
        out[f"within_1c_{anc}"] = round(float((np.abs(a.q - a[anc]) <= 0.01 + 1e-9).mean()), 3)
        out[f"n_{anc}"] = int(len(a))
    res["historical_price_inplay_tick"] = out
    # (c) live maker price vs server-clock book
    tok = {}
    for r in m.itertuples():
        tok[r.tok0] = (r.tok0, 0)
        tok[r.tok1] = (r.tok0, 1)
    dm = dm[dm.token_id.astype(str).isin(tok)].copy()
    tok0 = {tok[str(t)][0] for t in dm.token_id}
    sh = read("clob_wallets", tok0, T0 + 12 * 3600, time.time())
    ow = read("tommy_cs2_near", tok0, T0 + 12 * 3600, time.time())
    ser = {}
    for a in tok0:
        so = series_own([r for r in ow if r["a"] == a and r["k"] in ("f", "pc")])
        ss = series_shared([r for r in sh if r["a"] == a])
        t0 = so[0][0] if so else np.inf
        ser[a] = pd.DataFrame([x for x in ss if x[0] < t0] + so, columns=["s", "t", "Db", "Do", "bb", "ba"]).sort_values("s").reset_index(drop=True)
    rows = []
    for r in dm.itertuples():
        a, k = tok[str(r.token_id)]
        df = ser[a]
        S = df.s.to_numpy()
        if len(S) == 0 or r.sign_ms < S[0] + 1000:
            continue
        row = {"p": r.price}
        for lab, off in (("m50", -50), ("p300", 300)):
            i = np.searchsorted(S, r.sign_ms + off, side="right") - 1
            bid = df.bb.iloc[i] if k == 0 else 1 - df.ba.iloc[i]
            ask = df.ba.iloc[i] if k == 0 else 1 - df.bb.iloc[i]
            row[f"rel_{lab}"] = round((r.price - bid) * 100)
            row[f"spr_{lab}"] = round((ask - bid) * 100)
        rows.append(row)
    x = pd.DataFrame(rows)
    live = {"n": int(len(x))}
    for lab in ("m50", "p300"):
        vc = x[f"rel_{lab}"].value_counts(normalize=True).sort_index()
        live[f"price_minus_bid_cents_{lab}"] = {str(int(k)): round(float(vv), 3) for k, vv in vc.items() if abs(k) <= 6}
        live[f"at_bid_{lab}"] = round(float((x[f"rel_{lab}"] == 0).mean()), 3)
        live[f"within_1c_{lab}"] = round(float((x[f"rel_{lab}"].abs() <= 1).mean()), 3)
        live[f"bid_minus_0_to_4c_{lab}"] = round(float(x[f"rel_{lab}"].between(-4, 0).mean()), 3)
        live[f"spread_median_{lab}"] = float(x[f"spr_{lab}"].median())
    res["live_maker_price_server_clock"] = live
    json.dump(res, open(RES / "versions_price.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
