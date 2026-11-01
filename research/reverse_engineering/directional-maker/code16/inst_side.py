"""iteration 16, T2 = X178 (natural experiment for the side reading, E3 vs E1/E2) and the nowcast on fills (X179 part):
every cluster BTC 5m/15m BUY fill with a match ms (shared recorder clob_crypto trade with its tx hash, server ms) in the
given spans; posture from the Chainlink report stamped <= T - 1,432 ms (cl_source, development only), Gamma strike,
futures sigma300 (dm_bnf), k 1.0 / 1.4, against the Up mid just before the match (clob_crypto top-10 book, server ms);
the nowcast S_now = CL(s) + F(T - 50) - F(s * 1000); per wallet, per |F - mid| band, mid-band prices only.
    python inst_side.py <a> <b> [<a2> <b2> ...]"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code14"))
sys.path.insert(0, str(HERE.parent / "code"))
from lagged_quote import fut_mid, at, sec_sigma, cl_source  # noqa: E402
import final_rule as fr  # noqa: E402
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import sealed  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
NAMES = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
         "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}


def acts(a, b):
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    fr_ = []
    for x0, x1 in sealed.intervals("directional-maker", a, b, sealed=False):
        for addr, n in NAMES.items():
            rows, _, _ = pm.activity(addr, start=x0, end=x1 - 1)
            d = pd.DataFrame(rows)
            if len(d):
                d = d[(d.type == "TRADE") & (d.side == "BUY") & (d.timestamp >= x0) & (d.timestamp < x1)].copy()
                d["wallet"] = n
                fr_.append(d)
    d = pd.concat(fr_, ignore_index=True)
    d = d[d.slug.astype(str).str.match(r"^btc-updown-(5m|15m)-\d+$")].copy()
    d["st"] = d.slug.str.rsplit("-", n=1).str[1].astype(int)
    d = d[~d.st.map(lambda s: sealed.is_sealed(int(s), "directional-maker"))]
    return d.drop_duplicates(["transactionHash", "asset", "wallet", "size", "timestamp"])


def tokens(slugs):
    from polyrea.workflows.updown_study import fetch_windows
    raw = fetch_windows(sorted(slugs))
    up, K = {}, {}
    for m in raw.values():
        try:
            toks = json.loads(m["clobTokenIds"]) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds")
            outs = json.loads(m["outcomes"]) if isinstance(m.get("outcomes"), str) else m.get("outcomes")
        except Exception:  # noqa: BLE001
            continue
        if not toks or not outs:
            continue
        u = toks[outs.index("Up")]
        dn = toks[outs.index("Down")]
        up[str(u)] = (m["slug"], str(u))
        up[str(dn)] = (m["slug"], str(u))
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    return up, K


def acc(P, y, ok):
    return [round(float((P[ok] == y[ok]).mean()), 3) if ok.sum() else None, int(ok.sum())]


def run(a, b):
    d = acts(a, b)
    up, K = tokens(set(d.slug))
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
    y = d.y.to_numpy()
    md = d.mid.to_numpy(float)
    pr = d.price.to_numpy(float)
    out = {"span": [a, b], "n": int(len(d)), "matched_tx": len(match)}
    F1 = norm.cdf((cl - kk) / (s0 * np.sqrt(tau)))
    preds = {}
    for nm, S in (("report", cl), ("nowcast", now)):
        for k in (1.0, 1.4, 2.0):
            F = norm.cdf((S - kk) / (k * s0 * np.sqrt(tau)))
            preds[f"{nm}_k{k}"] = np.where(np.isfinite(F), (F > md).astype(float), np.nan)
    preds["cheaper"] = (md < 0.5).astype(float)
    band = np.abs(F1 - md)
    midb = (pr > 0.10) & (pr < 0.90)
    res = {}
    for w_ in ("bosona", "almach", "momoney", "all"):
        mw = (d.wallet == w_).to_numpy() if w_ != "all" else np.ones(len(d), bool)
        r = {}
        for pb, mm in (("mid", midb), ("deep", ~midb)):
            for nm, P in preds.items():
                r[f"{pb}_{nm}"] = acc(P, y, mw & mm & np.isfinite(P))
            for lo, hi in ((0, 0.05), (0.05, 0.1), (0.1, 1.01)):
                bm = mw & mm & np.isfinite(band) & (band >= lo) & (band < hi)
                r[f"{pb}_band{lo}-{hi}_report_k1.0"] = acc(preds["report_k1.0"], y, bm & np.isfinite(preds["report_k1.0"]))
                r[f"{pb}_band{lo}-{hi}_nowcast_k1.0"] = acc(preds["nowcast_k1.0"], y, bm & np.isfinite(preds["nowcast_k1.0"]))
                r[f"{pb}_band{lo}-{hi}_cheaper"] = acc(preds["cheaper"], y, bm)
        den = (mw & midb & np.isfinite(band)).sum()
        r["share_band_ge0.1_mid"] = round(float(((band >= 0.1) & mw & midb & np.isfinite(band)).sum() / max(1, den)), 3)
        res[w_] = r
    out["by_wallet"] = res
    hr = (T // 3600000) * 3600
    out["hourly_mid"] = {}
    for h in np.unique(hr):
        mm = (hr == h) & midb
        row = {nm: acc(P, y, mm & np.isfinite(P)) for nm, P in preds.items()}
        row["wallet_n"] = d.wallet[mm].value_counts().to_dict()
        out["hourly_mid"][time.strftime("%m-%d %H", time.gmtime(int(h)))] = row
    return out


if __name__ == "__main__":
    args = [int(x) for x in sys.argv[1:]]
    allo = {}
    for i in range(0, len(args), 2):
        o = run(args[i], args[i + 1])
        allo[f"{args[i]}_{args[i + 1]}"] = o
        print(json.dumps(o)[:3000])
    (HERE.parent / "results" / f"iter16_inst_side_{args[0]}_{args[-1]}.json").write_text(json.dumps(allo, indent=1))
