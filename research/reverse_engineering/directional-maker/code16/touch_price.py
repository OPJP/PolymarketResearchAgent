"""iteration 16, X184 (assumptions panel P4, price on thin books): the cluster's BUY fill price against book anchors on
the recorded books of the development block 11-01 06:00-now (and 10-31 12-18 / 00-06 where the shared recorder has the
family). Match ms = the recorder's trade record with the fill's tx hash (server ms). Anchors, from the last book record
of the bought token strictly before the match: touch (best bid), touch - 0.01, best ask - 0.01; and R7 (the last clean
print of the market before the match, mapped to the bought token, - 0.01). Books: dw_clob (alt 5m/15m: 'pc' rows carry
the Up book's best bid / ask) and clob_crypto (BTC/ETH/SOL 5m/15m/4h: 'q' top-10 books per token). Within a tick =
|anchor - price| <= 0.0101. Per family group and wallet. The touch anchors include the cluster's own resting order when it
is the best bid: they are trivial anchors (description), reported against R7.
    python touch_price.py <a> <b>"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
from inst_side import acts, NAMES  # noqa: E402,F401
import sealed  # noqa: E402


def all_acts(a, b):
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    fr = []
    for x0, x1 in sealed.intervals("directional-maker", a, b, sealed=False):
        for addr, n in NAMES.items():
            rows, _, _ = pm.activity(addr, start=x0, end=x1 - 1)
            d = pd.DataFrame(rows)
            if len(d):
                d = d[(d.type == "TRADE") & (d.timestamp >= x0) & (d.timestamp < x1)].copy()
                d["wallet"] = n
                fr.append(d)
    d = pd.concat(fr, ignore_index=True).drop_duplicates(["transactionHash", "asset", "wallet", "size", "timestamp"])
    m = d.slug.astype(str).str.extract(r"^(\w+)-updown-(5m|15m|4h)-(\d+)$")
    d = d[m[0].notna()].copy()
    d["coin"], d["len"], d["st"] = m[0][m[0].notna()], m[1][m[0].notna()], m[2][m[0].notna()].astype(int)
    d = d[~d.st.map(lambda s: sealed.is_sealed(int(s), "directional-maker"))]
    return d


def main(a, b):
    d = all_acts(a, b)
    ctx = set(d.transactionHash.str.lower())
    buys = d[d.side == "BUY"].copy()
    from polyrea.workflows.updown_study import fetch_windows
    raw = fetch_windows(sorted(set(buys.slug)))
    upt = {}
    for m in raw.values():
        try:
            toks = json.loads(m["clobTokenIds"]) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds")
            outs = json.loads(m["outcomes"]) if isinstance(m.get("outcomes"), str) else m.get("outcomes")
            upt[m["slug"]] = (str(toks[outs.index("Up")]), str(toks[outs.index("Down")]))
        except Exception:  # noqa: BLE001
            pass
    tok2slug = {t: s for s, (u, dn) in upt.items() for t in (u, dn)}
    # dw_clob: Up book bb/ba per window, trades per window
    wbook, wtr, match = {}, {}, {}
    for r in live.iter_live("dw_clob", a - 60, b + 60):
        k = r.get("k")
        if k == "pc" and r.get("s"):
            wbook.setdefault(r["w"], []).append((int(r["s"]), float(r["bb"]), float(r["ba"])))
        elif k == "x" and r.get("s"):
            h = str(r.get("h", "")).lower()
            match.setdefault(h, int(r["s"]))
            if h not in ctx:
                wtr.setdefault(r["w"], []).append((int(r["s"]), int(r.get("ai", -1)), float(r["p"])))
    # clob_crypto: per token best bid / ask, trades per token
    tbook, ttr = {}, {}
    toks = set(tok2slug)
    for r in live.iter_live("clob_crypto", a - 60, b + 60):
        k = r.get("k")
        if k == "q" and r.get("s") and str(r.get("a")) in toks:
            bb_, oo_ = r.get("b") or [], r.get("o") or []
            if bb_ and oo_:
                tbook.setdefault(str(r["a"]), []).append((int(r["s"]), max(float(x[0]) for x in bb_), min(float(x[0]) for x in oo_)))
        elif k == "x" and r.get("s"):
            h = str(r.get("h", "")).lower()
            match.setdefault(h, int(r["s"]))
            if h not in ctx and str(r.get("a")) in toks:
                ttr.setdefault(str(r["a"]), []).append((int(r["s"]), float(r["p"])))
    for dct in (wbook, wtr, tbook, ttr):
        for kk in dct:
            dct[kk].sort()
    rows = []
    for r in buys.itertuples(index=False):
        T = match.get(str(r.transactionHash).lower())
        if T is None or r.slug not in upt:
            continue
        u, dn = upt[r.slug]
        tok = str(r.asset)
        isup = tok == u
        bid = ask = last = np.nan
        src = None
        if r.slug in wbook:
            v = wbook[r.slug]
            i = np.searchsorted([x[0] for x in v], T, side="left") - 1
            if i >= 0 and T - v[i][0] <= 30000:
                bb, ba = v[i][1], v[i][2]
                bid, ask = (bb, ba) if isup else (1 - ba, 1 - bb)
                src = "dw_clob"
            tv = wtr.get(r.slug, [])
            j = np.searchsorted([x[0] for x in tv], T, side="left") - 1
            if j >= 0:
                ai, p = tv[j][1], tv[j][2]
                last = p if ((ai == 0) == isup) else 1 - p
        elif tok in tbook:
            v = tbook[tok]
            i = np.searchsorted([x[0] for x in v], T, side="left") - 1
            if i >= 0 and T - v[i][0] <= 30000:
                bid, ask = v[i][1], v[i][2]
                src = "clob_crypto"
            other = dn if isup else u
            best = None
            for tt, sgn in ((tok, 1), (other, -1)):
                tv = ttr.get(tt, [])
                j = np.searchsorted([x[0] for x in tv], T, side="left") - 1
                if j >= 0 and (best is None or tv[j][0] > best[0]):
                    best = (tv[j][0], tv[j][1] if sgn == 1 else 1 - tv[j][1])
            if best:
                last = best[1]
        if src is None:
            continue
        fam = f"{r.coin}-{r.len}"
        grp = "btc-5m/15m" if fam in ("btc-5m", "btc-15m") else ("4h" if r.len == "4h" else "alt-5m/15m")
        rows.append((r.wallet, fam, grp, float(r.price), bid, ask, last, src, float(r.price) <= 0.10 or float(r.price) >= 0.90))
    D = pd.DataFrame(rows, columns=["wallet", "fam", "grp", "price", "bid", "ask", "last", "src", "deep"])
    out = {"span": [a, b], "n": int(len(D))}

    def wt(x, m):
        mm = m & np.isfinite(x)
        return [round(float((np.abs(x[mm] - D.price.to_numpy()[mm]) <= 0.0101).mean()), 3) if mm.sum() else None, int(mm.sum())]
    for g, gm in [("all", np.ones(len(D), bool))] + [(g_, (D.grp == g_).to_numpy()) for g_ in sorted(D.grp.unique())] + \
            [(f"wallet_{w_}", (D.wallet == w_).to_numpy()) for w_ in sorted(D.wallet.unique())]:
        for lab, mk in (("all", gm), ("mid", gm & ~D.deep.to_numpy())):
            out[f"{g}_{lab}"] = {"touch": wt(D.bid.to_numpy(), mk), "touch_m1": wt(D.bid.to_numpy() - 0.01, mk),
                                 "ask_m1": wt(D.ask.to_numpy() - 0.01, mk), "r7_last_m1": wt(D["last"].to_numpy() - 0.01, mk),
                                 "last": wt(D["last"].to_numpy(), mk),
                                 "price_minus_touch_median": round(float(np.nanmedian((D.price - D.bid).to_numpy()[mk])), 3) if mk.sum() else None}
    print(json.dumps(out, indent=1)[:4000])
    (HERE.parent / "results" / f"iter16_touch_price_{a}_{b}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
