"""Iteration 5, mechanics panel iter4 P1 steps 1-2 (X57), fast version of engine_check.py (numpy inner loop).

Engine validation: the X44 strict price-time-priority engine replays the wallet's OWN maker orders (price, original size,
post = sign + 24 ms, resting until the match time of its last real fill) on the full matched-order record of its 229
markets (16-22 Oct). In each tx that consumed bids on token Z, the taker's maker-side volume F is re-allocated along the
merged queue {non-wallet maker rows (capacity = real fill, time = signing), our resting orders on Z (capacity =
remaining, time = post)} sorted by bid-equivalent price desc, then time asc.
Scores: share of the wallet's real maker shares assigned to the same tx; phantom shares; maker-only pair cost of the
copy vs the real one (pair-weighted over markets).
Attribution of REAL wallet maker fills: depth behind the tx's best bid-equivalent price (touch / 1c / 2c+), signed
before vs after the taker's signing, taker class (pack / fast followers / rest), share-weighted markouts at +10 / +60 s
(public last print, txs with a wallet order excluded) and settlement edge per share.
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
FAST = {"0x8a80528d", "0xddb6e624", "0x67706ec3", "0x14e72e19", "0xbb8ef638", "0x7c8cc255", "0x72aaaaf9", "0xfe8a28be",
        "0x2529c68d", "0xf1ee4842"}


def main():
    cd, gs = load_record()
    cd = cd[cd.m.notna()].copy()
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "salt"])
    a["salt"] = a.salt.astype(str)
    cd = cd.merge(a, on=["tx", "idx"], how="left")
    o = pd.read_parquet(OUT / "orders.parquet", columns=["salt", "role"])
    wmaker = set(o[o.role == "maker"].salt.astype(str))
    pack = set(pd.read_parquet(OUT / "pack_orders.parquet", columns=["maker"]).maker.str.lower()) - {WALLET}
    pm = pd.read_parquet(OUT / "per_market.parquet", columns=["cid", "win"])
    win = dict(zip(pm.cid, pm.win))
    wtx = set(a.tx)
    V_rows, A_rows = [], []
    for cid, g in cd.groupby("cid"):
        gsm = float(gs.get(cid, 0)) * 1000.0
        g = g.sort_values(["m", "tx", "idx"])
        tx = g.tx.to_numpy(); idx = g.idx.to_numpy(); side = g.side.to_numpy().astype(int); oi = g.oi.to_numpy().astype(int)
        pr = g.price.to_numpy(float); fl = g.fill.to_numpy(float); sg = g.sign_ms.to_numpy(float); mm = g.m.to_numpy(float)
        mk = g.maker.to_numpy(); salt = g.salt.to_numpy().astype(str)
        isw = (mk == WALLET) & np.isin(salt, list(wmaker)) & (idx >= 0)
        if not isw.any():
            continue
        # our orders (wallet maker BUYs): post, end, price, size, token
        wi = np.flatnonzero(isw & (side == 0) & (sg > 1.7e12))
        od = pd.DataFrame({"salt": salt[wi], "oi": oi[wi], "p": pr[wi], "size": g.shares.to_numpy(float)[wi], "sign": sg[wi], "m": mm[wi]})
        od = od.groupby("salt").agg(oi=("oi", "first"), p=("p", "first"), size=("size", "first"), sign=("sign", "first"), end=("m", "max")).reset_index()
        od["post"] = od.sign + POST_MS
        sid_of = {s: i for i, s in enumerate(od.salt)}
        o_oi = od.oi.to_numpy(int); o_p = od.p.to_numpy(float); o_post = od.post.to_numpy(float); o_end = od.end.to_numpy(float)
        rem = od["size"].to_numpy(float).copy()
        # public price path (token 0) for markouts
        tkm = idx == -1
        has_w_tx = set(tx[(mk == WALLET)])
        pub = tkm & ~np.isin(tx, list(has_w_tx))
        pt = mm[pub]; p0 = np.where(oi[pub] == 0, pr[pub], 1 - pr[pub])
        k = np.argsort(pt); pt, p0 = pt[k], p0[k]

        def px(t, z):
            j = int(np.searchsorted(pt, t, side="right")) - 1
            return np.nan if j < 0 else (p0[j] if z == 0 else 1 - p0[j])

        cut = np.flatnonzero(tx[1:] != tx[:-1]) + 1
        for lo, hi in zip(np.r_[0, cut], np.r_[cut, len(g)]):
            ti = np.flatnonzero(idx[lo:hi] == -1)
            if len(ti) == 0:
                continue
            t = lo + ti[0]
            m = mm[t]
            if m < gsm:
                continue
            z = int(oi[t]) if side[t] == 1 else 1 - int(oi[t])
            ms = np.arange(lo, hi)[idx[lo:hi] >= 0]
            beq = np.where((side[ms] == 0) & (oi[ms] == z), pr[ms], np.where((side[ms] == 1) & (oi[ms] != z), 1 - pr[ms], np.nan))
            ok = np.isfinite(beq)
            if not ok.any():
                continue
            ms, beq = ms[ok], beq[ok]
            F = fl[ms].sum()
            w_here = isw[ms]
            real = {}
            for j in np.flatnonzero(w_here):
                s_ = salt[ms[j]]
                real[s_] = real.get(s_, 0.0) + fl[ms[j]]
            # queue
            q_p = list(beq[~w_here]); q_t = list(sg[ms][~w_here]); q_c = list(fl[ms][~w_here]); q_id = [-1] * int((~w_here).sum())
            act = np.flatnonzero((o_oi == z) & (o_post <= m) & (o_end >= m - 1e-6) & (rem > 1e-9))
            for j in act:
                q_p.append(o_p[j]); q_t.append(o_post[j]); q_c.append(rem[j]); q_id.append(j)
            order = np.lexsort((np.array(q_t), -np.array(q_p)))
            left = F
            eng = {}
            for j in order:
                if left <= 1e-9:
                    break
                tk_ = min(q_c[j], left)
                left -= tk_
                if q_id[j] >= 0 and tk_ > 0:
                    eng[q_id[j]] = tk_
            for j, v in eng.items():
                rem[j] -= v
            ids = set(eng) | {sid_of[s] for s in real if s in sid_of}
            for j in ids:
                V_rows.append((cid, m, z, j, real.get(od.salt.iat[j], 0.0), eng.get(j, 0.0), o_p[j]))
            # attribution of real fills
            best = beq.max()
            tsg = sg[t] if 1.7e12 < sg[t] < 1.8e12 else np.nan
            tm = str(mk[t]).lower()
            tcl = "pack" if tm in pack else ("fast" if tm[:10] in FAST else "rest")
            w_ = win.get(cid)
            for j in np.flatnonzero(w_here):
                r = ms[j]
                if side[r] != 0:
                    continue
                pz10, pz60 = px(m + 10000, z), px(m + 60000, z)
                A_rows.append((cid, m, z, beq[j], fl[r], best - beq[j], (sg[r] > tsg) if np.isfinite(tsg) else False, tcl,
                               pz10 - beq[j], pz60 - beq[j], ((1.0 if w_ == z else 0.0) - beq[j]) if w_ is not None else np.nan))
    V = pd.DataFrame(V_rows, columns=["cid", "m", "z", "j", "real", "eng", "p"])
    A = pd.DataFrame(A_rows, columns=["cid", "m", "z", "beq", "fill", "behind", "after_taker", "tclass", "mk10", "mk60", "settle"])
    V["gs"] = V.cid.map(gs).astype(float)
    A["gs"] = A.cid.map(gs).astype(float)
    res = {}
    for sp in ("BUILD", "VALIDATE"):
        v = V[(V.gs < VAL0) if sp == "BUILD" else (V.gs >= VAL0)]
        real = v.real.sum()
        same = np.minimum(v.real, v.eng).sum()
        ph = (v.eng - np.minimum(v.real, v.eng)).sum()
        pcs = {"real": [], "eng": []}
        for cid, h in v.groupby("cid"):
            for col in ("real", "eng"):
                s0 = h[h.z == 0][col].sum(); s1 = h[h.z == 1][col].sum()
                if s0 > 0 and s1 > 0:
                    c0 = (h[h.z == 0][col] * h[h.z == 0].p).sum() / s0
                    c1 = (h[h.z == 1][col] * h[h.z == 1].p).sum() / s1
                    pcs[col].append((c0 + c1, min(s0, s1)))
        res[sp] = {"real_shares": round(float(real), 0), "assigned_same_tx_share": round(float(same / max(real, 1e-9)), 4),
                   "phantom_over_real": round(float(ph / max(real, 1e-9)), 4),
                   "maker_pair_cost_real": round(float(np.average([x[0] for x in pcs["real"]], weights=[x[1] for x in pcs["real"]])), 4),
                   "maker_pair_cost_engine": round(float(np.average([x[0] for x in pcs["eng"]], weights=[x[1] for x in pcs["eng"]])), 4)}
        aa = A[(A.gs < VAL0) if sp == "BUILD" else (A.gs >= VAL0)].copy()
        aa["depth"] = np.where(aa.behind < 0.005, "touch", np.where(aa.behind < 0.015, "1c", "2c+"))
        aa["timing"] = np.where(aa.after_taker.astype(bool), "after", "before")
        tot = aa.fill.sum()
        cls = []
        for (dep, tim, tc), h in aa.groupby(["depth", "timing", "tclass"]):
            w = h.fill.to_numpy()
            def wavg(col):
                x = h[col].to_numpy(float); k = np.isfinite(x)
                return round(float(100 * np.sum(x[k] * w[k]) / max(w[k].sum(), 1e-9)), 2) if k.any() else None
            cls.append({"depth": dep, "timing": tim, "taker": tc, "share": round(float(w.sum() / tot), 4),
                        "mk10_c": wavg("mk10"), "mk60_c": wavg("mk60"), "settle_c": wavg("settle")})
        res[sp]["attribution"] = sorted(cls, key=lambda r: -r["share"])
        for col in ("depth", "timing", "tclass"):
            res[sp][f"by_{col}"] = {k: {"share": round(float(h.fill.sum() / tot), 4),
                                        "mk60_c": round(float(100 * np.nansum(h.mk60 * h.fill) / max(h.fill[h.mk60.notna()].sum(), 1e-9)), 2),
                                        "settle_c": round(float(100 * np.nansum(h.settle * h.fill) / max(h.fill[h.settle.notna()].sum(), 1e-9)), 2)}
                                    for k, h in aa.groupby(col)}
    V.to_parquet(OUT / "engine_check_rows.parquet", index=False)
    A.to_parquet(OUT / "engine_attr_rows.parquet", index=False)
    (RES / "engine_check.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    for sp in ("BUILD", "VALIDATE"):
        print(sp, {k: v for k, v in res[sp].items() if k != "attribution"})
        for r in res[sp]["attribution"][:12]:
            print("   ", r)


if __name__ == "__main__":
    main()
