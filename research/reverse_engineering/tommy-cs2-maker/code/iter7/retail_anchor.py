"""Iteration 7, X89 (information panel iter6 P3): Polymarket's slow (retail) flow as the broadcast's footprint, by
anchor class. 16-22 Oct (development), the X40 recipe (code/iter4/ui_clock.py) with census anchors instead of takes:
  (b) pack-only informed bursts  = census 'wallet-absent' bursts;
  (c) isolated wallet-led bursts = census 'wallet-led' bursts with no other census burst in the market within 30 s after.
For each anchor (first informed signing t, team X = the bought outcome), retail (<= 20 taker orders per address in these
markets) net flow on X per 4-s bin of (sign - t) in [-20, +120) s, minus the same around t + shifts (+-300/600/900 s).
Turn lag = first bin >= 0 s after which the cumulative excess stays > 0 for 3 consecutive bins. Per event: delta_e =
turn(pack) - turn(wallet) on the event's pooled curves; event bootstrap (2,000) on the pooled difference. BUILD for the
method, VALIDATE for the number. Reading (panel): similar turns -> both sources at the same point of the broadcast chain;
pack much later than wallet -> pack upstream / wallet broadcast-side; no turn -> retail is a price-chaser (ruled out).
Output: results/retail_anchor.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
BINS = np.arange(-20, 124, 4)
SHIFTS = (-900, -600, -300, 300, 600, 900)


def turn(ex):
    b = BINS[:-1]
    cum = np.cumsum(ex[b >= 0])
    pos = cum > 0
    for i in range(len(pos) - 2):
        if pos[i] and pos[i + 1] and pos[i + 2]:
            return int(b[b >= 0][i])
    return None


def main():
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)
    b = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted((OUT / "calldata_pub").glob("*.parquet"))])
    cd = pd.concat([a, b[~b.tx.isin(set(a.tx))]], ignore_index=True)
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "token_id", "oi", "event"]).drop_duplicates("token_id")
    tok = {str(k): v for k, v in zip(o.token_id, zip(o.cid, o.oi))}
    ev_of = dict(zip(o.cid, o.event))
    cd["tok"] = cd.token_id.astype(str)
    cd = cd[cd.tok.isin(tok) & (cd.idx == -1) & (cd.sign_ms > 1.7e12) & (cd.sign_ms < 1.8e12)].drop_duplicates("tx").copy()
    cd["cid"] = cd.tok.map(lambda t: tok[t][0])
    cd["oi"] = cd.tok.map(lambda t: tok[t][1]).astype(int)
    P = cd[cd.maker.str.lower() != WALLET].copy()
    cnt = P.maker.value_counts()
    P = P[P.maker.map(cnt) <= 20]
    P["d0"] = np.where(((P.side == 0) & (P.oi == 0)) | ((P.side == 1) & (P.oi == 1)), 1, -1)
    by = {c: (g.sign_ms.to_numpy(float), g.d0.to_numpy(float)) for c, g in P.groupby("cid")}
    B = pd.read_parquet(OUT / "census_bursts.parquet").sort_values(["cid", "t0"])
    iso = []
    for cid, g in B.groupby("cid", sort=False):
        t = g.t0.to_numpy()
        for i in range(len(g)):
            iso.append(not (i + 1 < len(g) and t[i + 1] - t[i] <= 30))
    B["iso"] = iso
    B["cls"] = np.where(B.label == "wallet-absent", "pack", np.where((B.label == "wallet-led") & B.iso, "wallet_iso", None))
    B = B[B.cls.notna()].copy()
    B["event"] = B.cid.map(ev_of)

    nb = len(BINS) - 1
    vec = np.zeros((len(B), nb))
    for i, r in enumerate(B.itertuples()):
        x = by.get(r.cid)
        if x is None:
            continue
        s_, d = x
        sgn = 1 if r.oi == 0 else -1
        rel = (s_ - r.t0 * 1000) / 1000
        obs = np.histogram(rel, BINS, weights=d * sgn)[0]
        ctl = np.zeros(nb)
        for sh in SHIFTS:
            ctl += np.histogram(rel - sh, BINS, weights=d * sgn)[0] / len(SHIFTS)
        vec[i] = obs - ctl
    B = B.reset_index(drop=True)
    res = {}
    rng = np.random.default_rng(13)
    for split in ("BUILD", "VALIDATE"):
        S = B[B.split == split]
        out = {"anchors": S.cls.value_counts().to_dict()}
        for c in ("pack", "wallet_iso"):
            idx = S.index[S.cls == c].to_numpy()
            ex = vec[idx].sum(0)
            k = max(len(idx), 1)
            out[c] = {"turn_s": turn(ex), "excess_0_12s_per_anchor": round(float(ex[(BINS[:-1] >= 0) & (BINS[:-1] < 12)].sum() / k), 3),
                      "excess_12_60s_per_anchor": round(float(ex[(BINS[:-1] >= 12) & (BINS[:-1] < 60)].sum() / k), 3),
                      "excess_60_120s_per_anchor": round(float(ex[(BINS[:-1] >= 60) & (BINS[:-1] < 120)].sum() / k), 3),
                      "curve_per_anchor": [round(float(v / k), 3) for v in ex]}
        evs = S.event.dropna().unique()
        ev_vec = {c: {e: vec[S.index[(S.cls == c) & (S.event == e)].to_numpy()].sum(0) for e in evs} for c in ("pack", "wallet_iso")}
        diffs = []
        for _ in range(2000):
            pick = rng.choice(evs, len(evs))
            tp = turn(sum(ev_vec["pack"][e] for e in pick))
            tw = turn(sum(ev_vec["wallet_iso"][e] for e in pick))
            if tp is not None and tw is not None:
                diffs.append(tp - tw)
        out["turn_pack_minus_wallet_s"] = (None if out["pack"]["turn_s"] is None or out["wallet_iso"]["turn_s"] is None
                                           else out["pack"]["turn_s"] - out["wallet_iso"]["turn_s"])
        out["boot_ci95_s"] = [float(x) for x in np.percentile(diffs, [2.5, 50, 97.5])] if len(diffs) > 50 else None
        out["boot_valid_draws"] = len(diffs)
        res[split] = out
    (RES / "retail_anchor.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    for s, v in res.items():
        print(s, v["anchors"], {c: (v[c]["turn_s"], v[c]["excess_0_12s_per_anchor"], v[c]["excess_12_60s_per_anchor"], v[c]["excess_60_120s_per_anchor"]) for c in ("pack", "wallet_iso")},
              v["turn_pack_minus_wallet_s"], v["boot_ci95_s"], v["boot_valid_draws"])


if __name__ == "__main__":
    main()
