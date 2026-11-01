"""Iteration 7, X94 follow-up: are the untriggered own pulls (untriggered.py) a dense label of informed events?
(1) Cross-market trigger: drop pulls with a non-own level event on ANY book of the same CS2 event in [-T, 0] ms
    (T = 300 and 1,000 ms) and re-measure the markout. (2) Threat linkage: share of pulls followed by a threatening
    taker order (BUY of the complement token or SELL of the pulled token; calldata_dev, any signer; pack / wallet split)
    signed in [s - 100, s + 3000] ms, against the same detector at shifted times (+-60..600 s within the book), and the
    lead of the pull over that taker's signing. BUILD-live only (10-31 14:50-18:00 UTC).
Output: results/untriggered_pulls2.json
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter7"))
import untriggered as U  # noqa: E402
OUT, RES, WALLET = U.OUT, U.RES, U.WALLET
rng = np.random.default_rng(12)


def main():
    A = pd.read_parquet(OUT / "linked_adds_dev.parquet")
    A["vown"] = (A.owner == "wallet") | (A.F_mkt & (A.in_burst | (A["size"] != 100)))
    books = set(A.a)
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    ev_of = {str(r.tok0): r.event for r in dm.itertuples()}
    tok1 = {str(r.tok0): str(r.tok1) for r in dm.itertuples()}
    E = pd.read_parquet(OUT / "level_events_dev.parquet")
    E = E[E.a.isin(books)].copy()
    E["size"] = E.d.abs().round(2)
    own_sz = {a: set(g["size"]) for a, g in A[A.vown].groupby("a")}
    C = E[E.kind == "cancel"].sort_values(["a", "side", "s"]).reset_index(drop=True)
    C["f"] = [bool(abs(p * 100 - round(p * 100)) < 1e-6) and z in own_sz.get(a, {100.0}) for a, p, z in zip(C.a, C.p, C["size"])]
    multi = np.zeros(len(C), bool)
    for _, g in C[C.f].groupby(["a", "side"]):
        s_, z_, ix = g.s.to_numpy(), g["size"].to_numpy(), g.index.to_numpy()
        for i in range(len(g)):
            if ((np.abs(s_ - s_[i]) <= 5) & (z_ == z_[i])).sum() >= 2:
                multi[ix[i]] = True
    C["vown"] = C.f & (multi | (C["size"] != 100))
    Ad = A[["a", "s", "vown"]].rename(columns={"vown": "own"})
    Cd = C[["a", "s", "vown"]].rename(columns={"vown": "own"})
    Tr = E[E.kind == "cons"][["a", "s"]].assign(own=False)
    nonown = pd.concat([Ad[~Ad.own], Cd[~Cd.own], Tr])
    nonown["ev"] = nonown.a.map(ev_of)
    no_bk = {a: np.sort(g.s.to_numpy(float)) for a, g in nonown.groupby("a")}
    no_ev = {e: np.sort(g.s.to_numpy(float)) for e, g in nonown.groupby("ev")}
    # pull bursts (validated)
    P = []
    for (a, sd), g in C[C.vown].sort_values("s").groupby(["a", "side"]):
        s_ = g.s.to_numpy(float)
        i = 0
        while i < len(g):
            j = i
            while j + 1 < len(g) and s_[j + 1] - s_[i] <= 5:
                j += 1
            P.append({"a": a, "side": sd, "s": s_[i], "n": j - i + 1})
            i = j + 1
    P = pd.DataFrame(P)
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    cd["tok"] = cd.token_id.astype(str)
    tk = cd[cd.idx == -1].drop_duplicates("tx").copy()
    tk["mk"] = tk.maker.str.lower()
    pack = set(pd.read_parquet(OUT / "pack_orders.parquet", columns=["maker"]).maker.str.lower()) - {WALLET}
    tk["cls"] = np.where(tk.mk == WALLET, "wallet", np.where(tk.mk.isin(pack), "pack", "other"))
    # threat for (book a, side): BUY side = token-0 bids -> threat = BUY token1 or SELL token0
    thr = {}
    for a in books:
        t0, t1 = a, tok1[a]
        x = tk[((tk.tok == t1) & (tk.side == 0)) | ((tk.tok == t0) & (tk.side == 1))]
        thr[(a, "BUY")] = x[["sign_ms", "cls", "shares"]].sort_values("sign_ms")
        y = tk[((tk.tok == t0) & (tk.side == 0)) | ((tk.tok == t1) & (tk.side == 1))]
        thr[(a, "SELL")] = y[["sign_ms", "cls", "shares"]].sort_values("sign_ms")
    wt = {}
    for r in tk[tk.cls == "wallet"].itertuples():
        a = r.tok if r.tok in books else next((k for k, v in tok1.items() if v == r.tok), None)
        if a:
            wt.setdefault(ev_of[a], []).append(float(r.sign_ms))
    wt = {k: np.sort(np.array(v)) for k, v in wt.items()}

    def trig(a, s, T, cross):
        x = no_ev.get(ev_of[a]) if cross else no_bk.get(a)
        return x is not None and bool(np.any((x >= s - T) & (x <= s)))

    rows = []
    for r in P.itertuples():
        t = wt.get(ev_of[r.a])
        if t is not None and (np.any((t >= r.s - 2000) & (t <= r.s)) or np.any((t > r.s) & (t <= r.s + 5000))):
            continue
        th = thr[(r.a, r.side)]
        ts = th.sign_ms.to_numpy(float)
        j = np.searchsorted(ts, r.s - 100)
        hit = j < len(ts) and ts[j] <= r.s + 3000
        rows.append({"a": r.a, "side": r.side, "s": r.s, "n": r.n,
                     "trig_bk300": trig(r.a, r.s, 300, False), "trig_ev300": trig(r.a, r.s, 300, True),
                     "trig_ev1000": trig(r.a, r.s, 1000, True), "threat": bool(hit),
                     "threat_cls": th.cls.iloc[j] if hit else None, "lead_ms": float(ts[j] - r.s) if hit else np.nan})
    D = pd.DataFrame(rows)
    M = U.mids_from_feed(books)
    sg = np.where(D.side == "BUY", 1.0, -1.0)
    for h in (2000, 10000):
        D[f"mk{h // 1000}"] = [g_ * (U.mid_at(M[a], s + h) - U.mid_at(M[a], s)) for a, s, g_ in zip(D.a, D.s, sg)]

    def null_threat(sub):
        out = []
        for _ in range(500):
            k = 0
            for r in sub.itertuples():
                sh = rng.uniform(60000, 600000) * rng.choice([-1, 1])
                ts = thr[(r.a, r.side)].sign_ms.to_numpy(float)
                s = r.s + sh
                j = np.searchsorted(ts, s - 100)
                k += int(j < len(ts) and ts[j] <= s + 3000)
            out.append(k / max(len(sub), 1))
        return np.array(out)

    res = {"pulls_kept": int(len(D))}
    for nm, m in (("trig_bk300", D.trig_bk300), ("untrig_bk300", ~D.trig_bk300), ("untrig_ev300", ~D.trig_ev300),
                  ("untrig_ev1000", ~D.trig_ev1000)):
        sub = D[m]
        o = {"n": int(len(sub)), "mk2_mean_c": round(float(sub.mk2.mean() * 100), 3), "mk10_mean_c": round(float(sub.mk10.mean() * 100), 3),
             "threat_share": round(float(sub.threat.mean()), 3),
             "threat_by_cls": sub.threat_cls.value_counts().to_dict(),
             "lead_ms_p25_p50_p75": [round(float(x), 0) for x in np.nanpercentile(sub.lead_ms, [25, 50, 75])] if sub.threat.any() else None}
        nt = null_threat(sub)
        o["threat_null_mean"] = round(float(nt.mean()), 3)
        o["threat_p_greater"] = round(float((nt >= o["threat_share"]).mean()), 4)
        res[nm] = o
    (RES / "untriggered_pulls2.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
