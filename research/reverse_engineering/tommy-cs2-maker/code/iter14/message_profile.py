"""X189 step 1 / X195 (first pass, historical): its value and the clean print on the feed's own clock. Event-locked
profiles around informed take clusters (>= 2 distinct group-P / group-G members' taker orders on any book of the
event within 300 ms, wallet-free transactions; cluster time = first sign ms = feed time; sign = team bought).

For each cluster c with sign s, and each of the event's books the wallet quotes (map and match), the signed level
s x (X(c + tau) - X(c - 60 s)) for tau in -60..+60 s, X = its value (latest own maker burst top at or before the time,
in team-A space, per-token median offset to the print removed) or X = the clean print (wallet transactions excluded,
block time). Averages over clusters with both values defined, BUILD and VALIDATE separately, with the share of the
total signed move of V in (-60, +60] s that happens before the cluster (tau <= -1 s), at it ((-1, +3] s) and after it.
Diagnostic of when V moves relative to the feed's messages (R: a step at the message; K: a ramp before it); cluster
sign times are feed time, not public. Output: results/message_profile.json
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
SPLIT, H = 1792540800, 1792713600
GG = {"0xf1ee4842fa0c7283632185e42577027452d4519c", "0x8a80528dce46711a54aa3455c2cc81dea51e11c5",
      "0xddb6e6246546230503f153506ac1e9914978b9b3", "0x7c8cc25556ef9c0962b41d0ebb74d2fd17a42d81",
      "0x67706ec33d1bc5ed0db5cf0681b74b57b64ec3bd", "0xc70974218b9c6570f7701cd6fafc04ed490fbda9"}
TAU = np.array([-60, -45, -30, -20, -15, -10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 15, 20, 30, 45, 60], float)


def main():
    GP = set(json.load(open(RES / "selection_groupP.json"))["members"])
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "price", "cid", "oi", "event", "role", "token_id", "gs_ts"])
    o = o[(o.role == "maker") & o.event.notna() & (o.price > 0.06) & (o.price < 0.94)]
    o = o.sort_values(["token_id", "sign_ms"]).reset_index(drop=True)
    o["burst"] = (o.groupby("token_id").sign_ms.diff().fillna(1e12) > 50).cumsum()
    b = o.groupby("burst").agg(t=("sign_ms", "min"), top=("price", "max"), cid=("cid", "first"), oi=("oi", "first"),
                               event=("event", "first"), gs=("gs_ts", "first")).reset_index()
    b["t"] = b.t / 1000
    b["A"] = np.where(b.oi == 0, b.top, 1 - b.top)
    wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx"]).tx)
    cd, _ = load_record()
    tk = cd[(cd.idx == -1) & ~cd.tx.isin(wtx)].drop_duplicates("tx")
    ev_of = dict(zip(o.cid, o.event))
    tk = tk[(tk.sign_ms > 1.7e12) & tk.cid.isin(set(o.cid))].copy()
    tk["event"] = tk.cid.map(ev_of)
    tk["mk"] = tk.maker.str.lower()
    tk["team"] = np.where(tk.side == 0, np.where(tk.oi == 0, 1, -1), np.where(tk.oi == 0, -1, 1))
    inf = tk[tk.mk.isin(GP | GG)].sort_values("sign_ms")
    cl = []
    for ev, g in inf.groupby("event"):
        s, m, tm = g.sign_ms.to_numpy(), g.mk.to_numpy(), g.team.to_numpy()
        i = 0
        while i < len(g):
            j = i
            while j + 1 < len(g) and s[j + 1] - s[i] <= 300:
                j += 1
            if len(set(m[i:j + 1])) >= 2:
                sg = float(np.sign(tm[i:j + 1].sum())) or float(tm[i])
                cl.append((ev, s[i] / 1000, sg))
                i = j + 1
            else:
                i += 1
    cl = pd.DataFrame(cl, columns=["event", "t", "s"])
    res = {"clusters": int(len(cl))}
    prof = {"BUILD": {"V": [], "P": []}, "VALIDATE": {"V": [], "P": []}}
    for cid, g in b.groupby("cid"):
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if not p.exists() or len(g) < 20:
            continue
        d = pd.read_parquet(p, columns=["timestamp", "price", "outcomeIndex", "transactionHash"])
        d = d[~d.transactionHash.isin(wtx)].sort_values("timestamp")
        if len(d) < 20:
            continue
        ts = d.timestamp.to_numpy(float)
        pa = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        g = g.sort_values("t")
        tt, A, oi = g.t.to_numpy(), g.A.to_numpy(), g.oi.to_numpy()
        j = np.searchsorted(ts, tt, side="right") - 1
        ok = j >= 0
        off = {z: float(np.median((A - pa[np.maximum(j, 0)])[ok & (oi == z)])) if (ok & (oi == z)).any() else 0.0 for z in (0, 1)}
        Ac = A - np.array([off[z] for z in oi])
        per = "BUILD" if g.gs.iloc[0] < SPLIT else "VALIDATE"
        c = cl[cl.event == g.event.iloc[0]]
        c = c[(c.t > tt[0] + 60) & (c.t < tt[-1] - 60)]
        for r in c.itertuples():
            q = r.t + TAU
            iv = np.searchsorted(tt, q, side="right") - 1
            ip = np.searchsorted(ts, q, side="right") - 1
            iv0 = np.searchsorted(tt, r.t - 60, side="right") - 1
            ip0 = np.searchsorted(ts, r.t - 60, side="right") - 1
            if iv0 < 0 or ip0 < 0 or (iv < 0).any() or (ip < 0).any():
                continue
            prof[per]["V"].append(r.s * (Ac[iv] - Ac[iv0]))
            prof[per]["P"].append(r.s * (pa[ip] - pa[ip0]))
    for per in prof:
        V, P = np.array(prof[per]["V"]), np.array(prof[per]["P"])
        if len(V) == 0:
            continue
        mv, mp = V.mean(0) * 100, P.mean(0) * 100
        i_m1, i_p3 = int(np.where(TAU == -1)[0][0]), int(np.where(TAU == 3)[0][0])
        tot = mv[-1]
        res[per] = {"clusters_used": int(len(V)), "tau_s": TAU.tolist(), "V_signed_cents": [round(x, 3) for x in mv],
                    "P_signed_cents": [round(x, 3) for x in mp],
                    "V_share_before_-1s": round(float(mv[i_m1] / tot), 3) if tot else None,
                    "V_share_at_-1_to_+3s": round(float((mv[i_p3] - mv[i_m1]) / tot), 3) if tot else None,
                    "V_share_after_+3s": round(float((tot - mv[i_p3]) / tot), 3) if tot else None,
                    "P_total_cents": round(float(mp[-1]), 3), "V_total_cents": round(float(tot), 3),
                    "V_frac_moved_toward_s_by_+3s": round(float(np.mean(V[:, i_p3] - V[:, i_m1] > 0.005)), 3),
                    "V_frac_moved_toward_s_before_-1s": round(float(np.mean(V[:, i_m1] > 0.005)), 3),
                    "P_frac_moved_toward_s_by_+3s": round(float(np.mean(P[:, i_p3] - P[:, i_m1] > 0.005)), 3)}
        print(per, json.dumps(res[per]), flush=True)
    (RES / "message_profile.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
