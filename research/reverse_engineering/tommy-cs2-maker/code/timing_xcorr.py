"""Timing (component 2) at millisecond resolution: cross-correlogram of the wallet's order signing times against
every public taker's order signing time in the same market (decoded calldata of every taker tx), overall and for
price-moving taker orders (the taker's tx moved the public print by >= 2c). Also other large makers as controls.
Positive lag = wallet signs after the taker. Development data only."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import H, OUT, RES, WALLET  # noqa: E402
from maker_compare import load_all  # noqa: E402

def xcorr(a_by, b_by, lo=-10.0, hi=10.0, step=0.1):
    bins = np.arange(lo, hi + step / 2, step); h = np.zeros(len(bins) - 1)
    for cid, b in b_by.items():
        a = a_by.get(cid)
        if a is None or len(a) == 0: continue
        for t in b:
            i, j = np.searchsorted(a, t + lo), np.searchsorted(a, t + hi)
            if j > i: h += np.histogram(a[i:j] - t, bins=bins)[0]
    return bins, h

def main():
    a = load_all()
    a = a[a.cid.notna() & (a.sign_ms > 1.7e12) & (a.sign_ms < 1.8e12)]
    tk = a[a.idx == -1].copy()
    # price move of each taker tx: |print p0 - previous print p0| in that market (taker tape)
    mk = a[a.idx >= 0]
    sign = lambda d: d.drop_duplicates(["maker", "sign_ms", "token_id", "price"]).groupby("cid")["sign_ms"].apply(lambda s: np.sort(s.to_numpy() / 1000))
    w_by = sign(mk[mk.maker == WALLET]).to_dict()
    tk = tk[tk.maker != WALLET].sort_values(["cid", "bts"])
    tk["p0"] = np.where(((tk.side == 0) & (tk.oi == 0)) | ((tk.side == 1) & (tk.oi == 1)), np.where(tk.side == 0, tk.price, 1 - tk.price), np.where(tk.side == 0, 1 - tk.price, tk.price))
    tk["dp"] = tk.groupby("cid")["p0"].diff().abs()
    all_by = tk.groupby("cid")["sign_ms"].apply(lambda s: np.sort(s.to_numpy() / 1000)).to_dict()
    big_by = tk[tk.dp >= 0.02].groupby("cid")["sign_ms"].apply(lambda s: np.sort(s.to_numpy() / 1000)).to_dict()
    res = {}
    for name, ref in (("all_takers", all_by), ("moving_takers_2c", big_by)):
        bins, h = xcorr(w_by, ref)
        base = np.median(np.r_[h[:20], h[-20:]])
        res[name] = {"n_ref": int(sum(len(v) for v in ref.values())), "base": float(base),
                     "peak_lag": float(bins[np.argmax(h)] + 0.05), "peak_ratio": round(float(h.max() / max(base, 1)), 2),
                     "ratio_by_0.5s": {f"{lo:+.1f}": round(float(h[k:k+5].sum() / max(5 * base, 1)), 2) for k, lo in zip(range(0, len(h), 5), bins[::5])}}
    # controls: top other makers
    top = mk[mk.maker != WALLET].drop_duplicates(["maker", "sign_ms", "token_id", "price"]).maker.value_counts().head(6).index
    res["controls"] = {}
    for m_ in top:
        m_by = sign(mk[mk.maker == m_]).to_dict()
        bins, h = xcorr(m_by, big_by)
        base = np.median(np.r_[h[:20], h[-20:]])
        res["controls"][m_[:10]] = {"peak_lag": float(bins[np.argmax(h)] + 0.05), "peak_ratio": round(float(h.max() / max(base, 1)), 2),
                                    "ratio_by_0.5s": {f"{lo:+.1f}": round(float(h[k:k+5].sum() / max(5 * base, 1)), 2) for k, lo in zip(range(0, len(h), 5), bins[::5])}}
    json.dump(res, open(RES / "results/timing_xcorr.json", "w"), indent=1)
    print(json.dumps(res, indent=1)[:5000])

if __name__ == "__main__":
    main()
