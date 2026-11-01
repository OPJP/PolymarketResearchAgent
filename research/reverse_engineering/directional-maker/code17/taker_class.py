"""iteration 17, X196 (information panel P2, pre-registered in NOTES.md 10:52 UTC 11-01): is the 11-01 side 'regime'
the counterparties? Every cluster BTC 5m/15m BUY fill with a shared-recorder match ms (X178's sets), joined to the
V2 calldata of its transaction: the taker order's signing ms, its signer and its limit. L = match ms - taker sign ms.
Classes: auto L <= 300 ms, mid 0.3-2 s, slow > 2 s. Side scored per block x class x |F1 - mid| band (report k1.0,
nowcast k1.0, cheaper). Reweighting: 10-31's class x band accuracies weighted by 11-01's class x band shares, against
11-01's actual (pre-registered reading: within 0.03 -> counterparties; else the cluster's quote changed). Also the
taker hold (X195 part): quantiles of L over all matched takers (a hold of ~150 ms puts a floor near 150-200 ms).
    python taker_class.py <a1> <b1> <a2> <b2>"""
import glob
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code16"))
sys.path.insert(0, str(HERE.parent / "code14"))
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE.parent / "code4"))
import inst_side as ins  # noqa: E402
from lagged_quote import fut_mid, at, sec_sigma, cl_source  # noqa: E402
import final_rule as fr  # noqa: E402
import calldata as cd  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
CD = C / "calldata"


def frame(a, b):
    d = ins.acts(a, b)
    up, K = ins.tokens(set(d.slug))
    d["up_tok"] = d.asset.astype(str).map(lambda t: up.get(t, (None, None))[1])
    d["y"] = (d.outcome == "Up").astype(int)
    ups = set(x for x in d.up_tok.dropna())
    match, books = {}, {}
    for r in fr._iter_live_xq(a - 120, b + 120, ups):
        if r.get("k") == "x":
            h = str(r.get("h", "")).lower()
            if h and h not in match and r.get("s"):
                match[h] = int(r["s"])
        elif r.get("k") == "q" and str(r.get("a")) in ups and r.get("s"):
            bb_, oo_ = r.get("b") or [], r.get("o") or []
            if bb_ and oo_:
                books.setdefault(str(r["a"]), []).append(
                    (int(r["s"]), (max(float(x[0]) for x in bb_) + min(float(x[0]) for x in oo_)) / 2))
    bk = {}
    for t_, v in books.items():
        v.sort()
        bk[t_] = (np.array([x[0] for x in v], np.int64), np.array([x[1] for x in v]))
    del books
    d["T"] = d.transactionHash.str.lower().map(match)
    d = d[d["T"].notna() & d.up_tok.notna()].copy()
    d["T"] = d["T"].astype(np.int64)
    mid = np.full(len(d), np.nan)
    for i, (u, T) in enumerate(zip(d.up_tok, d["T"])):
        if u in bk:
            s_, m_ = bk[u]
            j = np.searchsorted(s_, T, side="left") - 1
            if j >= 0 and T - s_[j] <= 10000:
                mid[i] = m_[j]
    d["mid"] = mid
    d = d[np.isfinite(d.mid)].copy()
    E, M = fut_mid(a - 900, b + 60)
    sig = sec_sigma(E, M, 300)
    T = d["T"].to_numpy(np.int64)
    s = (T - 1432) // 1000
    clv = cl_source.cl_values(sorted(set(s.tolist())), allow_sealed=False, fetch=False)
    cl = pd.Series(s).map(clv).to_numpy(float)
    now = cl + at(E, M, T - 50) - at(E, M, s * 1000)
    kk = d.slug.map(K).to_numpy(float)
    en = d.st.to_numpy() + np.where(d.slug.str.contains("-15m-"), 900, 300)
    tau = np.maximum(en - T / 1000, 1.0)
    s0 = sig.reindex(T // 1000).to_numpy(float)
    md = d.mid.to_numpy(float)
    F1 = norm.cdf((cl - kk) / (s0 * np.sqrt(tau)))
    Fn = norm.cdf((now - kk) / (s0 * np.sqrt(tau)))
    d["p_report"] = np.where(np.isfinite(F1), (F1 > md).astype(float), np.nan)
    d["p_nowcast"] = np.where(np.isfinite(Fn), (Fn > md).astype(float), np.nan)
    d["p_cheaper"] = (md < 0.5).astype(float)
    d["band"] = np.abs(F1 - md)
    return d


def taker_orders(hashes):
    have = {}
    for f in glob.glob(str(CD / "*.parquet")):
        try:
            x = pd.read_parquet(f, columns=["tx", "role", "sign_ms", "maker", "signer", "oside", "maker_amount",
                                            "taker_amount", "token_id"])
        except Exception:  # noqa: BLE001
            continue
        x = x[x.role == "taker"]
        for r in x.itertuples(index=False):
            have.setdefault(str(r.tx).lower(), r._asdict())
    need = [h for h in hashes if h not in have]
    print("calldata cached", len(hashes) - len(need), "to fetch", len(need), flush=True)
    rows = []
    for h, tx in cd.fetch_txs(need, batch=40, pause=0.15):
        dd = cd.decode(tx["input"]) if tx else None
        if not dd:
            continue
        t = dd["taker"]
        rows.append({"tx": h, "role": "taker", "sign_ms": t["sign_ms"], "maker": t["maker"], "signer": t["signer"],
                     "oside": t["oside"], "maker_amount": t["maker_amount"], "taker_amount": t["taker_amount"],
                     "token_id": t["token_id"], "block": int(tx["blockNumber"], 16)})
    if rows:
        nd = pd.DataFrame(rows)
        nd.to_parquet(CD / f"it17_taker_{int(time.time())}.parquet")
        for r in nd.itertuples(index=False):
            have[str(r.tx).lower()] = r._asdict()
    return have


def acc(P, y, m):
    m = m & np.isfinite(P)
    return [round(float((P[m] == y[m]).mean()), 3) if m.sum() else None, int(m.sum())]


CLS = (("auto", -1e18, 300), ("mid", 300, 2000), ("slow", 2000, 1e18))
BANDS = ((0, 0.05), (0.05, 0.1), (0.1, 1.01))


def score(d):
    y = d.y.to_numpy()
    midb = ((d.price > 0.10) & (d.price < 0.90)).to_numpy()
    L = d.L.to_numpy(float)
    band = d.band.to_numpy(float)
    out = {}
    for w_ in ("bosona", "almach", "momoney", "all"):
        mw = (d.wallet == w_).to_numpy() if w_ != "all" else np.ones(len(d), bool)
        r = {"n_mid": int((mw & midb).sum()), "n_with_L": int((mw & midb & np.isfinite(L)).sum())}
        for cn, lo, hi in CLS:
            mc = mw & midb & np.isfinite(L) & (L > lo) & (L <= hi)
            r[f"{cn}_share"] = round(float(mc.sum() / max(1, (mw & midb & np.isfinite(L)).sum())), 3)
            for nm in ("p_report", "p_nowcast", "p_cheaper"):
                r[f"{cn}_{nm}"] = acc(d[nm].to_numpy(float), y, mc)
            for blo, bhi in BANDS:
                mb = mc & np.isfinite(band) & (band >= blo) & (band < bhi)
                r[f"{cn}_b{blo}_report"] = acc(d["p_report"].to_numpy(float), y, mb)
                r[f"{cn}_b{blo}_nowcast"] = acc(d["p_nowcast"].to_numpy(float), y, mb)
                r[f"{cn}_b{blo}_cheaper"] = acc(d["p_cheaper"].to_numpy(float), y, mb)
        out[w_] = r
    return out


def cells(d, col):
    """accuracy and share per (class, band) on the mid band with L."""
    y = d.y.to_numpy()
    P = d[col].to_numpy(float)
    midb = ((d.price > 0.10) & (d.price < 0.90)).to_numpy()
    L = d.L.to_numpy(float)
    band = d.band.to_numpy(float)
    base = midb & np.isfinite(L) & np.isfinite(band) & np.isfinite(P)
    res = {}
    for cn, lo, hi in CLS:
        for blo, bhi in BANDS:
            m = base & (L > lo) & (L <= hi) & (band >= blo) & (band < bhi)
            res[(cn, blo)] = (float((P[m] == y[m]).mean()) if m.sum() else np.nan, int(m.sum()))
    return res, int(base.sum()), float((P[base] == y[base]).mean()) if base.sum() else np.nan


def main(a1, b1, a2, b2):
    frames = []
    for blk, (a, b) in (("1031", (a1, b1)), ("1101", (a2, b2))):
        d = frame(a, b)
        d["blk"] = blk
        frames.append(d)
        print(blk, len(d), flush=True)
    d = pd.concat(frames, ignore_index=True)
    hs = sorted(set(d.transactionHash.str.lower()))
    have = taker_orders(hs)
    tk = pd.DataFrame([dict(v, tx=k) for k, v in have.items() if k in set(hs)])
    tk = tk.drop_duplicates("tx")
    d["txl"] = d.transactionHash.str.lower()
    d = d.merge(tk[["tx", "sign_ms", "maker", "oside", "maker_amount", "taker_amount"]].rename(
        columns={"tx": "txl", "maker": "taker_addr", "oside": "taker_oside"}), on="txl", how="left")
    d["L"] = d["T"] - d["sign_ms"].astype(float)
    d.loc[(d.sign_ms <= 0) | (d.sign_ms.isna()), "L"] = np.nan
    d[["blk", "wallet", "txl", "T", "sign_ms", "L", "taker_addr", "taker_oside", "y", "price", "mid", "band",
       "p_report", "p_nowcast", "p_cheaper", "slug"]].to_parquet(C / "it17_taker_class.parquet")
    out = {"spans": [[a1, b1], [a2, b2]], "n": int(len(d)), "n_with_L": int(d.L.notna().sum())}
    for blk in ("1031", "1101"):
        x = d[d.blk == blk]
        Lq = x.L.dropna()
        out[blk] = {"L_quantiles_ms": {q: round(float(Lq.quantile(q)), 1) for q in (0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9)}
                    if len(Lq) else None, "n": int(len(x)), "n_takers": int(x.taker_addr.nunique()),
                    "by_wallet": score(x)}
        top = x.taker_addr.value_counts().head(8)
        out[blk]["top_takers"] = {k: [int(v), round(float(x[x.taker_addr == k].L.median()), 0)] for k, v in top.items()}
    # reweighting (pre-registered): 10-31 class x band accuracies with 11-01's shares
    rw = {}
    for who in ("all", "bosona"):
        x0 = d[(d.blk == "1031") & ((d.wallet == who) if who != "all" else True)]
        x1 = d[(d.blk == "1101") & ((d.wallet == who) if who != "all" else True)]
        for col in ("p_report", "p_nowcast", "p_cheaper"):
            c0, n0, a0 = cells(x0, col)
            c1, n1, a1_ = cells(x1, col)
            num = den = 0.0
            for k, (acc1, n_1) in c1.items():
                acc0 = c0[k][0]
                if n_1 and np.isfinite(acc0):
                    num += n_1 * acc0
                    den += n_1
            rw[f"{who}_{col}"] = {"acc_1031": round(a0, 3), "acc_1101_actual": round(a1_, 3),
                                  "acc_1101_reweighted": round(num / den, 3) if den else None, "n_1031": n0,
                                  "n_1101": n1, "cells_1031": {f"{k[0]}_{k[1]}": [round(v[0], 3) if np.isfinite(v[0]) else None, v[1]] for k, v in c0.items()},
                                  "cells_1101": {f"{k[0]}_{k[1]}": [round(v[0], 3) if np.isfinite(v[0]) else None, v[1]] for k, v in c1.items()}}
    out["reweighting"] = rw
    print(json.dumps({k: out[k] for k in ("n", "n_with_L")}), json.dumps(rw)[:4000])
    for blk in ("1031", "1101"):
        print(blk, json.dumps(out[blk]["L_quantiles_ms"]), json.dumps(out[blk]["top_takers"])[:600])
    (HERE.parent / "results" / "iter17_taker_class.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(*[int(x) for x in sys.argv[1:5]])
