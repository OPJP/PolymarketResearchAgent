"""Iteration 6, panel iter5 information I1 (X26): the price rule on the match clock from the SHARED recorder.

For every cluster BTC 5m maker BUY fill of a development live block (data-api activity, maker role from calldata), the
server match ms is the first 'x' record of its tx hash in the shared recorder (clob_crypto). Candidate price rules
(all point-in-time with respect to the match; the cluster's own transactions are removed from the anchor stream):
  (a) last clean x print on the fill's token before the match, minus 0.01 (frozen candidate, the trivial anchor
      'last print' with the 0.01 offset);
  (a_L) the same with the anchor at least L ms before the match (L = 250 ... 3000: the block-time tape sees prints
      ~1-3 s late, so L ~ 2000-2500 approximates R3's block-clock anchor on the same fills);
  (b) the token's best bid in the shared 200-ms top-10 snapshot at match - 200 ms (reported; contaminated by the
      cluster's own resting order when it is the touch);
  trivial anchors: last clean print itself, touch (best bid at match - 200 ms), touch - 0.01.
Split (pre-registered in NOTES, iteration 6): live BUILD = 2026-10-31 12:00-15:00 UTC, live VALIDATE = 15:00-18:00 UTC.
    python code6/i1_price_match.py <start_ts> <end_ts>
"""
import glob
import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
from rawread import iter_dm  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
RES = HERE.parent / "results"
W = {"0x32ed2e546b187ca15e2841edc82b22c713cf8ec3", "0x3725d52f3c252e8374999cc8617292ea2608ad88",
     "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed"}
LIVE_SPLIT = 1793458800  # 2026-10-31 15:00 UTC


def load(a, b):
    acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))]).drop_duplicates(
        subset=["transactionHash", "asset", "w", "size", "price"])
    acts = acts[(acts.type == "TRADE") & (acts.side == "BUY") & acts.slug.str.contains("btc-updown-15m", na=False)
                & (acts.timestamp >= a) & (acts.timestamp < b)].copy()
    cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata/live*.parquet"))])
    cd["maker"] = cd.maker.str.lower()
    mk_tx = set(cd.loc[(cd.role == "maker") & cd.maker.isin(W), "tx"].str.lower())
    tk_tx = set(cd.loc[(cd.role == "taker") & cd.maker.isin(W), "tx"].str.lower())
    acts["tx"] = acts.transactionHash.str.lower()
    acts["role"] = np.where(acts.tx.isin(mk_tx), "maker", np.where(acts.tx.isin(tk_tx), "taker", "unknown"))
    up_of, tok2up = {}, {}
    for r in iter_dm("subs", a - 3600, b):
        if r.get("feed") != "clob_crypto":
            continue
        for slug, toks in r["markets"].items():
            if "btc-updown-15m" in slug and len(toks) == 2:
                up_of[slug] = toks[0]
                tok2up[toks[0]] = (toks[0], True)
                tok2up[toks[1]] = (toks[0], False)
    need_up = {up_of[s] for s in acts.slug.unique() if s in up_of}
    Q = {u: [] for u in need_up}
    X = []
    try:
        for r in iter_dm("clob_crypto", a - 60, b + 60):
            k = r.get("k")
            if k in ("q", "f") and r.get("a") in Q:
                bb = max((p for p, z in r["b"]), default=np.nan)
                ba = min((p for p, z in r["o"]), default=np.nan)
                Q[r["a"]].append((r["s"], bb, ba))
            elif k == "x" and r.get("a") in tok2up:
                up, isup = tok2up[r["a"]]
                if up in need_up:
                    X.append((r["s"], up, isup, r["p"], r.get("z", np.nan), (r.get("h") or "").lower(), str(r.get("d"))))
    except zlib.error as e:
        print("zlib stop", e)
    X = pd.DataFrame(X, columns=["s", "up", "isup", "p", "z", "h", "d"]).sort_values("s", kind="stable")
    cl_tx = set(acts.tx) | mk_tx | tk_tx
    X["clean"] = ~X.h.isin(cl_tx)
    X["p_up"] = np.where(X.isup, X.p, 1 - X.p)
    return acts, up_of, Q, X


def main(a, b):
    acts, up_of, Q, X = load(a, b)
    match_s = X.groupby("h").s.min()
    xc = {u: g for u, g in X[X.clean].groupby("up")}
    rows = []
    for f in acts.itertuples():
        if f.slug not in up_of or f.tx not in match_s.index:
            continue
        up = up_of[f.slug]
        isup = f.asset == up
        ms = int(match_s[f.tx])
        row = {"w": f.w, "role": f.role, "price": float(f.price), "isup": isup, "ms": ms, "ts": int(f.timestamp),
               "half": "live_validate" if f.timestamp >= LIVE_SPLIT else "live_build", "size": float(f.size)}
        q = np.array(Q.get(up) or [])
        if len(q):
            i = np.searchsorted(q[:, 0], ms - 200, side="right") - 1
            if i >= 0:
                row["touch200"] = q[i, 1] if isup else 1 - q[i, 2]
        g = xc.get(up)
        if g is not None:
            gs, gp, gd = g.s.to_numpy(), g.p_up.to_numpy(), g.d.to_numpy()
            gi = g.isup.to_numpy()
            for L in (0, 250, 500, 1000, 1500, 2000, 2500, 3000):
                j = np.searchsorted(gs, ms - L, side="left") - 1
                if j >= 0:
                    lp = gp[j] if isup else 1 - gp[j]
                    row[f"last{L}"] = lp
                    if L == 0:
                        row["last_dt"] = ms - gs[j]
                        sold_up = (gi[j] and str(gd[j]).upper().startswith("S")) or ((not gi[j]) and str(gd[j]).upper().startswith("B"))
                        row["last_sold_s"] = bool(sold_up == isup)
        rows.append(row)
    R = pd.DataFrame(rows)
    M = R[R.role != "taker"].copy()
    tol = 0.0105

    def acc(D, col, off=0.0):
        m = D[col].notna()
        if not m.any():
            return None
        e = np.abs(D.loc[m, col] - off - D.loc[m, "price"])
        return {"within_tick": round(float((e <= tol).mean()), 4), "exact": round(float((e <= 0.0005).mean()), 4), "n": int(m.sum())}

    out = {"period": [a, b], "n_fills_activity": int(len(acts)), "n_with_match_ms": int(len(R)), "n_maker": int(len(M)),
           "x_coverage_of_fills": round(len(R) / max(len(acts[acts.slug.isin(up_of)]), 1), 4)}
    for half, D in [("all", M)] + list(M.groupby("half")):
        h = {"rule_a_last_clean_print_minus_0.01": acc(D, "last0", 0.01),
             "anchor_last_print": acc(D, "last0"),
             "anchor_touch_200ms": acc(D, "touch200"),
             "anchor_touch_200ms_minus_0.01": acc(D, "touch200", 0.01),
             "decay_last_print_minus_0.01_at_least_L_ms": {L: acc(D, f"last{L}", 0.01) for L in (250, 500, 1000, 1500, 2000, 2500, 3000)},
             "per_wallet_rule_a": {w: acc(g, "last0", 0.01) for w, g in D.groupby("w")},
             "side_eq_token_just_sold": round(float(D.last_sold_s.mean()), 4) if "last_sold_s" in D else None,
             "last_print_age_ms_quantiles": D.last_dt.quantile([.1, .25, .5, .75, .9]).round(0).to_dict() if "last_dt" in D else None}
        # error structure of rule (a)
        m = D.last0.notna()
        err = np.round((D.loc[m, "price"] - (D.loc[m, "last0"] - 0.01)) * 100).astype(int)
        h["rule_a_error_ticks"] = err.clip(-4, 4).value_counts(normalize=True).sort_index().round(4).to_dict()
        # by size bucket
        h["rule_a_by_size"] = {str(k): acc(g, "last0", 0.01) for k, g in D.groupby(pd.cut(D["size"], [0, 20, 100, 499.9, 1e9]), observed=True)}
        out[half] = h
    out = json.loads(json.dumps(out, default=str))
    p = RES / f"iter6_i1_price15_{a}_{b}.json"
    p.write_text(json.dumps(out, indent=1))
    M.to_parquet(C / "it6" / f"i1_fills15_{a}_{b}.parquet")
    print(json.dumps({k: out[k] for k in ("n_fills_activity", "n_with_match_ms", "n_maker", "x_coverage_of_fills")}))
    for half in ("live_build", "live_validate", "all"):
        if half in out:
            h = out[half]
            print(half, "ruleA", h["rule_a_last_clean_print_minus_0.01"], "last", h["anchor_last_print"], "touch200", h["anchor_touch_200ms"],
                  "touch-0.01", h["anchor_touch_200ms_minus_0.01"])
            print("  decay", {k: (v or {}).get("within_tick") for k, v in h["decay_last_print_minus_0.01_at_least_L_ms"].items()})
            print("  per wallet", {k: (v or {}).get("within_tick") for k, v in h["per_wallet_rule_a"].items()}, "err ticks", h["rule_a_error_ticks"])
            print("  side=just sold", h["side_eq_token_just_sold"], "by size", {k: (v or {}).get("within_tick") for k, v in h["rule_a_by_size"].items()})


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
