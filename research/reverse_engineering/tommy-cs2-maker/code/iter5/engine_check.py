"""Iteration 5, mechanics panel iter4 P1 steps 1-2 (X57): validate the X44 queue engine on the wallet's OWN maker
orders, then attribute its maker margin by fill class.

Engine (strict price-time priority on the full matched-order record of its 229 markets, 16-22 Oct; calldata_all +
calldata_pub; match time m = min(block, taker sign + 1,040 ms) as in X44):
  * "ours" = every wallet maker order (price, original size, signing time); it rests from post = sign + 24 ms (live post
    latency) until the match time of its last real fill.
  * In each public tx that consumed bids on token Z, the taker's volume F (sum of all maker fills) is re-allocated along
    the merged queue: non-wallet maker rows (capacity = their real fill, time = their signing) and our resting orders on
    Z (capacity = remaining size, time = post), sorted by bid-equivalent price desc, then time asc.
  * Score: share of the wallet's real maker shares the engine assigns to the same tx; phantom shares (assigned where the
    wallet got nothing); maker-only pair cost of the copy vs the real maker-only pair cost.
Attribution (real fills): depth behind the tx's best bid-equivalent price (0 / 1c / 2c+), signed before vs after the
taker signed, taker class (pack = the 9 pack signers, fast followers from followers.json, rest), markouts at +10 / +60 s
(public last print of Z from the windowed taker tapes, txs with a wallet order excluded), per split.
Output: results/engine_check.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter4"))
from queue_replay import load_record  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0, H = 1792540800, 1792713600
POST_MS = 24.0


def main():
    cd, gs = load_record()
    cd = cd[cd.m.notna()].copy()
    o = pd.read_parquet(OUT / "orders.parquet", columns=["salt", "role", "cid", "token_id", "gs_ts"])
    wmaker_salts = set(o[o.role == "maker"].salt.astype(str))
    cd["salt"] = pd.read_parquet(OUT / "calldata_all.parquet", columns=["salt"]).salt.astype(str).reindex(cd.index) if False else None
    # salts: re-read with tx/idx keys (load_record dropped the column)
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "salt"])
    a["salt"] = a.salt.astype(str)
    cd = cd.merge(a, on=["tx", "idx"], how="left", suffixes=("", "_a"))
    cd["salt"] = cd["salt_a"] if "salt_a" in cd else cd["salt"]
    pack = set(pd.read_parquet(OUT / "pack_orders.parquet", columns=["maker"]).maker.str.lower()) - {WALLET}
    try:
        fol = json.load(open(RES / "followers.json"))
        fast = set()
        for k in ("fast_followers", "followers_1622", "top_followers"):
            v = fol.get(k)
            if isinstance(v, list):
                for x in v:
                    if isinstance(x, dict) and x.get("maker"):
                        fast.add(x["maker"].lower())
                    elif isinstance(x, str):
                        fast.add(x.lower())
    except Exception:  # noqa: BLE001
        fast = set()
    fast |= {"0x8a80528d", "0xddb6e624", "0x67706ec3", "0x14e72e19", "0xbb8ef638", "0x7c8cc255", "0x72aaaaf9", "0xfe8a28be", "0x2529c68d", "0xf1ee4842", "0x93078b5d"}

    def tclass(addr):
        a_ = str(addr).lower()
        if a_ in pack or a_[:10] in {"0x4ebc2722", "0x93078b5d"}:
            return "pack"
        if a_[:10] in fast:
            return "fast"
        return "rest"

    rows_val, rows_attr = [], []
    tok_px = {}
    for cid, g in cd.groupby("cid"):
        g = g.sort_values(["m", "tx", "idx"])
        gsm = float(gs.get(cid, 0)) * 1000.0
        # wallet maker orders of this market: rest window [sign+24, last real fill m]
        wm = g[(g.idx >= 0) & (g.maker == WALLET) & g.salt.isin(wmaker_salts)]
        if wm.empty:
            continue
        ords = wm.groupby("salt").agg(oi=("oi", "first"), side=("side", "first"), p=("price", "first"), size=("shares", "first"),
                                      sign=("sign_ms", "first"), end=("m", "max")).reset_index()
        ords = ords[(ords.side == 0) & (ords.sign > 1.7e12)]
        ords["post"] = ords.sign + POST_MS
        rem = dict(zip(ords.salt, ords["size"].astype(float)))
        o_by_tok = {0: ords[ords.oi == 0], 1: ords[ords.oi == 1]}
        # public last-print series for markouts (token-0 price), txs without any wallet order
        has_w = g.groupby("tx").maker.apply(lambda s: (s == WALLET).any())
        tk = g[g.idx == -1].drop_duplicates("tx")
        pub = tk[~tk.tx.map(has_w).fillna(False).astype(bool)]
        p0 = np.where(pub.oi.to_numpy(int) == 0, pub.price.to_numpy(float), 1 - pub.price.to_numpy(float))
        pt = pub.m.to_numpy(float)
        ordp = np.argsort(pt)
        pt, p0 = pt[ordp], p0[ordp]

        def px_at(t, z):
            j = int(np.searchsorted(pt, t, side="right")) - 1
            if j < 0:
                return np.nan
            return p0[j] if z == 0 else 1 - p0[j]

        for tx, h in g.groupby("tx", sort=False):
            t = h[h.idx == -1]
            if t.empty:
                continue
            t = t.iloc[0]
            m = float(t.m)
            if m < gsm:
                continue
            z = int(t.oi) if int(t.side) == 1 else 1 - int(t.oi)
            mk = h[h.idx >= 0]
            beq = np.where((mk.side.to_numpy() == 0) & (mk.oi.to_numpy() == z), mk.price.to_numpy(float),
                           np.where((mk.side.to_numpy() == 1) & (mk.oi.to_numpy() != z), 1 - mk.price.to_numpy(float), np.nan))
            ok = np.isfinite(beq)
            if not ok.any():
                continue
            mk = mk[ok]
            beq = beq[ok]
            F = float(mk.fill.sum())
            isw = (mk.maker == WALLET).to_numpy() & mk.salt.isin(wmaker_salts).to_numpy()
            real_w = dict(zip(mk.salt[isw], mk.fill[isw].astype(float)))
            best = float(beq.max())
            # queue: non-wallet rows + our resting orders on z
            q = [(float(b), float(s), float(f), None) for b, s, f, w in zip(beq, mk.sign_ms.to_numpy(float), mk.fill.to_numpy(float), isw) if not w]
            oz = o_by_tok[z]
            act = oz[(oz.post <= m) & (oz.end >= m - 1e-6)]
            for r in act.itertuples():
                if rem.get(r.salt, 0) > 1e-9:
                    q.append((float(r.p), float(r.post), rem[r.salt], r.salt))
            q.sort(key=lambda x: (-x[0], x[1]))
            left = F
            eng = {}
            for b, s, cap, sid in q:
                if left <= 1e-9:
                    break
                take = min(cap, left)
                left -= take
                if sid is not None and take > 0:
                    eng[sid] = take
            for sid, v in eng.items():
                rem[sid] -= v
            for sid in set(eng) | set(real_w):
                rows_val.append((cid, tx, m, z, sid, real_w.get(sid, 0.0), eng.get(sid, 0.0),
                                 float(ords.loc[ords.salt == sid, "p"].iloc[0]) if (ords.salt == sid).any() else np.nan))
            # attribution of real wallet fills
            tsg = float(t.sign_ms) if 1.7e12 < float(t.sign_ms) < 1.8e12 else np.nan
            for b, s, f_, w, sid in zip(beq, mk.sign_ms.to_numpy(float), mk.fill.to_numpy(float), isw, mk.salt):
                if not w:
                    continue
                pz = px_at(m + 10000, z)
                pz60 = px_at(m + 60000, z)
                rows_attr.append((cid, m, z, b, f_, round(best - b, 4), (s > tsg) if np.isfinite(tsg) else None, tclass(t.maker),
                                  pz - b if np.isfinite(pz) else np.nan, pz60 - b if np.isfinite(pz60) else np.nan))
    V = pd.DataFrame(rows_val, columns=["cid", "tx", "m", "z", "salt", "real", "eng", "p"])
    A = pd.DataFrame(rows_attr, columns=["cid", "m", "z", "beq", "fill", "behind", "after_taker", "tclass", "mk10", "mk60"])
    V["gs"] = V.cid.map(gs).astype(float)
    A["gs"] = A.cid.map(gs).astype(float)
    res = {}
    for sp, sel in (("BUILD", V.gs < VAL0), ("VALIDATE", V.gs >= VAL0)):
        v = V[sel]
        real = v.real.sum()
        same = np.minimum(v.real, v.eng).sum()
        phantom = (v.eng - np.minimum(v.real, v.eng)).sum()
        # pair cost per market (maker-only, real vs engine)
        pcs = []
        for cid, h in v.groupby("cid"):
            for col in ("real", "eng"):
                s0 = h[h.z == 0][col].sum(); s1 = h[h.z == 1][col].sum()
                c0 = (h[h.z == 0][col] * h[h.z == 0].p).sum(); c1 = (h[h.z == 1][col] * h[h.z == 1].p).sum()
                if s0 > 0 and s1 > 0:
                    pcs.append((cid, col, c0 / s0 + c1 / s1, min(s0, s1)))
        P = pd.DataFrame(pcs, columns=["cid", "col", "pc", "pairs"])
        res[sp] = {"real_shares": round(float(real), 1), "assigned_same_tx_share": round(float(same / max(real, 1e-9)), 4),
                   "phantom_share_of_real": round(float(phantom / max(real, 1e-9)), 4),
                   "engine_total_over_real": round(float(v.eng.sum() / max(real, 1e-9)), 4),
                   "pair_cost_weighted_real": round(float(np.average(P[P.col == 'real'].pc, weights=P[P.col == 'real'].pairs)), 4) if (P.col == 'real').any() else None,
                   "pair_cost_weighted_engine": round(float(np.average(P[P.col == 'eng'].pc, weights=P[P.col == 'eng'].pairs)), 4) if (P.col == 'eng').any() else None,
                   "phantom_fill_mean_price": round(float(np.average(v.p, weights=np.maximum(v.eng - np.minimum(v.real, v.eng), 0) + 1e-12)), 4)}
        a = A[(A.gs < VAL0) if sp == "BUILD" else (A.gs >= VAL0)]
        a = a.assign(depth=np.where(a.behind < 0.005, "touch", np.where(a.behind < 0.015, "1c", "2c+")),
                     timing=np.where(a.after_taker.astype("boolean").fillna(False), "after_taker", "before_taker"))
        cls = []
        for (dep, tim, tc), h in a.groupby(["depth", "timing", "tclass"]):
            w = h.fill
            cls.append({"depth": dep, "timing": tim, "taker": tc, "shares": round(float(w.sum()), 0),
                        "share_of_shares": round(float(w.sum() / a.fill.sum()), 4),
                        "mk10_c": round(float(100 * np.average(h.mk10.fillna(0), weights=w * h.mk10.notna())), 2) if (h.mk10.notna() & (w > 0)).any() else None,
                        "mk60_c": round(float(100 * np.average(h.mk60.fillna(0), weights=w * h.mk60.notna())), 2) if (h.mk60.notna() & (w > 0)).any() else None})
        res[sp]["attribution"] = sorted(cls, key=lambda r: -r["shares"])
    V.to_parquet(OUT / "engine_check_rows.parquet", index=False)
    A.to_parquet(OUT / "engine_attr_rows.parquet", index=False)
    (RES / "engine_check.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    for sp in ("BUILD", "VALIDATE"):
        print(sp, {k: v for k, v in res[sp].items() if k != "attribution"})
        for r in res[sp]["attribution"][:14]:
            print("   ", r)


if __name__ == "__main__":
    main()
