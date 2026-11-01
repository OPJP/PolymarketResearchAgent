"""Iteration 9, X120 (information panel iter8 P3) and X128 (assumptions panel iter8 P2): GRID events as the natural
experiment. Group G = BUILD fixed-lag co-signers of P4e with >= 20% of their BUILD prints in GRID events
(selection_groupP.json). Data: decoded public taker transactions of the 25 GRID CS2 events of 16-22 Oct with the most
group-G prints (calldata_grid/, +-3 s around group-G prints) vs the wallet's (non-GRID) markets (calldata_pub/).
1. Relative lags of group-G members behind the reference member 0xf1ee4842 (same-token taker BUYs within +-1 s; median,
   IQR, n, 30-s shift null) in GRID vs non-GRID events.
2. The earliest signer of each group-G cluster (taker BUYs on the token in [first G sign - 1.5 s, first G sign + 0.3 s]):
   a group-G member, group P, or another wallet; and that wallet's presence in non-GRID events.
3. Information timing of group G's takes (cluster level): the bought token's last-print change in the 10 s before the
   first G sign (pre-move) and the 10-s / 60-s markouts from the last print before it (public tapes; prints in the
   cluster's own transactions excluded), GRID vs non-GRID, event bootstrap of the difference.
Output: results/grid_experiment.json
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
REF = "0xf1ee4842fa0c7283632185e42577027452d4519c"


def main():
    sg = json.load(open(RES / "selection_groupP.json"))
    GP = set(sg["members"])
    G = {w for w, v in sg["candidates"].items() if not v["member"] and (v["build_grid_share"] or 0) >= 0.2}
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms", "price"]
    gr = pd.concat([pd.read_parquet(p, columns=cols) for p in glob.glob(str(OUT / "calldata_grid" / "*.parquet"))])
    ng = pd.concat([pd.read_parquet(p, columns=cols) for p in glob.glob(str(OUT / "calldata_pub" / "*.parquet"))])
    u = pd.read_parquet(OUT / "universe.parquet")
    tok_cid, tok_oi = {}, {}
    for r in u.itertuples():
        t = json.loads(r.tokens) if isinstance(r.tokens, str) else r.tokens
        for i, x in enumerate(t or []):
            tok_cid[str(x)], tok_oi[str(x)] = r.cid, i
    cid_ev = dict(zip(u.cid, u.event_slug))
    res = {"group_G": sorted(G)}
    T = {}
    for nm, d in (("grid", gr), ("nongrid", ng)):
        d = d.drop_duplicates(["tx", "idx"]).copy()
        d["maker"] = d.maker.str.lower()
        d["token_id"] = d.token_id.astype(str)
        d = d[(d.idx == -1) & (d.side == 0) & (d.sign_ms > 1.79e12) & (d.sign_ms < 1.7928e12)]
        d["cid"] = d.token_id.map(tok_cid)
        d["ev"] = d.cid.map(cid_ev)
        T[nm] = d[d.cid.notna()]
    # 1. relative lags behind REF
    lagres = {}
    rng = np.random.default_rng(5)
    for nm, d in T.items():
        ref = d[d.maker == REF]
        by_tok = {k: v for k, v in d[d.maker.isin(G | GP | {W})].groupby("token_id")}
        o = {}
        for w_ in sorted((G | GP | {W}) - {REF}):
            lags, nul = [], 0.0
            for r in ref.itertuples():
                v = by_tok.get(r.token_id)
                if v is None:
                    continue
                x = v.loc[v.maker == w_, "sign_ms"].to_numpy(float)
                dd = x - r.sign_ms
                lags += list(dd[np.abs(dd) <= 1000])
                s_ = rng.choice([-30000, 30000])
                nul += float((np.abs(x - r.sign_ms - s_) <= 1000).sum())
            if len(lags) >= 5:
                L = np.array(lags)
                o[w_[:10]] = {"n": int(len(L)), "null": round(nul, 1), "median_ms": round(float(np.median(L)), 1),
                              "iqr_ms": round(float(np.percentile(L, 75) - np.percentile(L, 25)), 1)}
        lagres[nm] = {"ref_takes": int(len(ref)), "events": int(ref.ev.nunique()), "lags": o}
    res["lags_behind_0xf1ee4842"] = lagres
    # 2./3. clusters of group-G takes: first signer and information timing
    tapes = {}

    def tape(cid):
        if cid not in tapes:
            p = OUT / "tapes" / f"{cid}_tkw.parquet"
            if p.exists():
                x = pd.read_parquet(p, columns=["timestamp", "price", "outcomeIndex", "transactionHash"])
                x = x.sort_values("timestamp")
                x["p0"] = np.where(x.outcomeIndex.astype(int) == 0, x.price.astype(float), 1 - x.price.astype(float))
                tapes[cid] = x
            else:
                tapes[cid] = None
        return tapes[cid]
    cl_rows = []
    present_ng = set(T["nongrid"].maker)
    for nm, d in T.items():
        g_ = d[d.maker.isin(G)].sort_values("sign_ms")
        for tok, v in g_.groupby("token_id"):
            s = v.sign_ms.to_numpy(float)
            starts = s[np.r_[True, np.diff(s) > 3000]]
            allt = d[d.token_id == tok]
            for s0 in starts:
                win = allt[(allt.sign_ms >= s0 - 1500) & (allt.sign_ms <= s0 + 300)].sort_values("sign_ms")
                first = win.iloc[0]
                fm = first.maker
                cls = "G" if fm in G else ("P" if fm in GP else ("wallet" if fm == W else "other"))
                cid = tok_cid[tok]
                tp = tape(cid)
                pre = mk10 = mk60 = np.nan
                if tp is not None and len(tp):
                    excl = set(allt[(allt.sign_ms >= s0 - 1500) & (allt.sign_ms <= s0 + 3000)].tx)
                    x = tp[~tp.transactionHash.isin(excl)]
                    ts = x.timestamp.to_numpy(float)
                    pz = x.p0.to_numpy(float) if tok_oi[tok] == 0 else 1 - x.p0.to_numpy(float)
                    t0 = s0 / 1000

                    def at(t):
                        j = np.searchsorted(ts, t, side="right") - 1
                        return pz[j] if j >= 0 else np.nan
                    p_at = at(t0)
                    pre = p_at - at(t0 - 10)
                    mk10, mk60 = at(t0 + 10) - p_at, at(t0 + 60) - p_at
                cl_rows.append({"cls_set": nm, "ev": cid_ev.get(cid), "first_cls": cls, "first_maker": fm[:10],
                                "first_in_nongrid": fm in present_ng, "lead_ms": float(s0 - first.sign_ms),
                                "pre10": pre, "mk10": mk10, "mk60": mk60})
    C = pd.DataFrame(cl_rows)
    out2 = {}
    for nm, c in C.groupby("cls_set"):
        o = {"clusters": int(len(c)), "events": int(c.ev.nunique()),
             "first_signer_class": {k: int(v) for k, v in c.first_cls.value_counts().items()},
             "first_other_top": {k: int(v) for k, v in c.loc[c.first_cls == "other", "first_maker"].value_counts().head(5).items()},
             "first_other_seen_in_nongrid": round(float(c.loc[c.first_cls == "other", "first_in_nongrid"].mean()), 3) if (c.first_cls == "other").any() else None,
             "median_lead_of_first_over_G_ms": round(float(c.lead_ms.median()), 1)}
        for k in ("pre10", "mk10", "mk60"):
            o[f"{k}_mean_c"] = round(float(c[k].mean() * 100), 3)
            o[f"{k}_median_c"] = round(float(c[k].median() * 100), 3)
        out2[nm] = o
    # event bootstrap of GRID - non-GRID differences
    bs = {}
    for k in ("pre10", "mk10", "mk60"):
        a_ = C[C.cls_set == "grid"].dropna(subset=[k])
        b_ = C[C.cls_set == "nongrid"].dropna(subset=[k])
        ea, eb = a_.ev.unique(), b_.ev.unique()
        ga, gb = {e: x[k].to_numpy() for e, x in a_.groupby("ev")}, {e: x[k].to_numpy() for e, x in b_.groupby("ev")}
        dif = []
        for _ in range(2000):
            sa = np.concatenate([ga[e] for e in rng.choice(ea, len(ea))])
            sb = np.concatenate([gb[e] for e in rng.choice(eb, len(eb))])
            dif.append((sa.mean() - sb.mean()) * 100)
        bs[k] = {"diff_c": round(float((a_[k].mean() - b_[k].mean()) * 100), 3),
                 "ci95": [round(float(np.quantile(dif, 0.025)), 3), round(float(np.quantile(dif, 0.975)), 3)]}
    res["clusters"] = out2
    res["grid_minus_nongrid"] = bs
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "grid_experiment.json", "w"), indent=1)


if __name__ == "__main__":
    main()
