"""E3-1 (pre-registered in NOTES iteration 14): event-state indicator screen against the wallet's maker re-pricing
decisions, with tools/indicators.py (event_study / screen, BH over the joint family), BUILD screen and VALIDATE
confirmation of survivors (one-sided alpha 0.01, Holm).

Decisions: first order of each own maker burst (orders on one token chained within 50 ms; filled orders, B1 sign
times) whose top differs from the previous burst top on that token; sign = team-A direction of the change.
Units: every market the wallet traded (map / match books), [game start, last own fill + 600 s), each on its own
shifted timeline (offset k x 1e6 s); strata = title x book.
Indicators: I1 informed_take, I2 informed_cluster, I3 print_jump_2c, I4 print_jump_3sigma, I5 other_book_jump,
I6 print_after_silence (definitions in NOTES). Lag ranges +-2 s (0.25-s bins), +-60 s (1-s), +-600 s (5-s).
Output: results/e3_screen.json (+ ledger rows for state.json indicators)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter4"))
import indicators as ind  # noqa: E402
from queue_replay import load_record  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
SPLIT, H = 1792540800, 1792713600
GG = {"0xf1ee4842fa0c7283632185e42577027452d4519c", "0x8a80528dce46711a54aa3455c2cc81dea51e11c5",
      "0xddb6e6246546230503f153506ac1e9914978b9b3", "0x7c8cc25556ef9c0962b41d0ebb74d2fd17a42d81",
      "0x67706ec33d1bc5ed0db5cf0681b74b57b64ec3bd", "0xc70974218b9c6570f7701cd6fafc04ed490fbda9"}
RANGES = [("pm2s", 2.0, 0.25), ("pm60s", 60.0, 1.0), ("pm600s", 600.0, 5.0)]


def build(period):
    GP = set(json.load(open(RES / "selection_groupP.json"))["members"])
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "price", "cid", "oi", "event", "smt", "role", "token_id", "gs_ts", "first_fill_ts", "last_fill_ts"])
    o = o[(o.role == "maker") & o.event.notna()]
    o = o[(o.gs_ts >= 1792108800) & (o.gs_ts < SPLIT)] if period == "BUILD" else o[(o.gs_ts >= SPLIT) & (o.gs_ts < H)]
    o = o.sort_values(["token_id", "sign_ms"]).reset_index(drop=True)
    o["burst"] = (o.groupby("token_id").sign_ms.diff().fillna(1e12) > 50).cumsum()
    b = o.groupby("burst").agg(t=("sign_ms", "min"), top=("price", "max"), tok=("token_id", "first"), cid=("cid", "first"),
                               oi=("oi", "first"), event=("event", "first"), smt=("smt", "first")).reset_index()
    b = b.sort_values(["tok", "t"])
    b["dtop"] = b.groupby("tok").top.diff()
    b = b[b.dtop.notna() & (b.dtop.abs() > 1e-9)]
    b["sign"] = np.sign(b.dtop) * np.where(b.oi == 0, 1, -1)
    mk = o.groupby("cid").agg(gs=("gs_ts", "first"), end=("last_fill_ts", "max"), event=("event", "first"), smt=("smt", "first")).reset_index()
    mk["end"] = mk.end + 600
    mk["off"] = np.arange(len(mk)) * 1e6
    mk["title"] = np.where(mk.event.str.startswith("dota2"), "dota2", "cs2")
    mk["book"] = np.where(mk.smt == "moneyline", "match", "map")
    off = dict(zip(mk.cid, mk.off))
    # informed takes (wallet-free txs)
    cd, _ = load_record()
    wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx"]).tx)
    tk = cd[(cd.idx == -1) & ~cd.tx.isin(wtx)].drop_duplicates("tx")
    tk = tk[(tk.sign_ms > 1.7e12) & tk.cid.isin(set(o.cid))].copy()
    ev_of = dict(zip(o.cid, o.event))
    tk["event"] = tk.cid.map(ev_of)
    tk["mk"] = tk.maker.str.lower()
    tk["team"] = np.where(tk.side == 0, np.where(tk.oi == 0, 1, -1), np.where(tk.oi == 0, -1, 1))
    gp = tk[tk.mk.isin(GP)]
    inf = tk[tk.mk.isin(GP | GG)].sort_values("sign_ms")
    cl_rows = []
    for ev, g in inf.groupby("event"):
        s, m, tm = g.sign_ms.to_numpy(), g.mk.to_numpy(), g.team.to_numpy()
        i = 0
        while i < len(g):
            j = i
            while j + 1 < len(g) and s[j + 1] - s[i] <= 300:
                j += 1
            if len(set(m[i:j + 1])) >= 2:
                cl_rows.append((ev, s[i] / 1000, float(np.sign(tm[i:j + 1].sum())) or float(tm[i])))
                i = j + 1
            else:
                i += 1
    cl = pd.DataFrame(cl_rows, columns=["event", "t", "sign"])
    # clean prints
    pr = {}
    for cid in mk.cid:
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p, columns=["timestamp", "price", "outcomeIndex", "transactionHash"])
        d = d[~d.transactionHash.isin(wtx)].sort_values("timestamp")
        pa = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        pr[cid] = (d.timestamp.to_numpy(float), pa)
    units, strata = [], []
    dec_t, dec_s = [], []
    E = {k: ([], []) for k in ("I1_informed_take", "I2_informed_cluster", "I3_print_jump_2c", "I4_print_jump_3sigma",
                                "I5_other_book_jump", "I6_print_after_silence")}
    ev_cids = mk.groupby("event").cid.apply(list).to_dict()
    for r in mk.itertuples():
        a, z = r.gs + r.off, r.end + r.off
        if z - a < 600:
            continue
        units.append((a, z))
        strata.append(f"{r.title}_{r.book}")
        bb = b[b.cid == r.cid]
        tt = bb.t.to_numpy() / 1000 + r.off
        k = (tt >= a) & (tt < z)
        dec_t.append(tt[k]); dec_s.append(bb.sign.to_numpy()[k])

        def add(name, ts, sg):
            ts = np.asarray(ts, float) + r.off
            sg = np.asarray(sg, float) if sg is not None else np.ones(len(ts))
            kk = (ts >= a) & (ts < z)
            E[name][0].append(ts[kk]); E[name][1].append(sg[kk])
        g1 = gp[gp.event == r.event]
        add("I1_informed_take", g1.sign_ms.to_numpy() / 1000, g1.team.to_numpy())
        c1 = cl[cl.event == r.event]
        add("I2_informed_cluster", c1.t.to_numpy(), c1.sign.to_numpy())
        if r.cid in pr:
            ts, pa = pr[r.cid]
            dp = np.diff(pa, prepend=np.nan)
            j2 = np.abs(dp) >= 0.02 - 1e-9
            add("I3_print_jump_2c", ts[j2], np.sign(dp[j2]))
            t = ind.grid(r.gs, r.end, 1.0)
            x = ind.asof(t, ts, pa)
            ets, esg = ind.jumps(t, x, horizon=10, k=3.0, refractory_s=10)
            add("I4_print_jump_3sigma", ets, esg)
            gap = np.diff(ts, prepend=-np.inf)
            add("I6_print_after_silence", ts[gap >= 60], None)
        oth = [c for c in ev_cids.get(r.event, []) if c != r.cid and c in pr and (mk.set_index("cid").loc[c, "book"] != r.book)]
        o_t, o_s = [], []
        for c in oth:
            ts, pa = pr[c]
            dp = np.diff(pa, prepend=np.nan)
            j2 = np.abs(dp) >= 0.02 - 1e-9
            o_t.append(ts[j2]); o_s.append(np.sign(dp[j2]))
        if o_t:
            add("I5_other_book_jump", np.concatenate(o_t), np.concatenate(o_s))
    dec_t, dec_s = np.concatenate(dec_t), np.concatenate(dec_s)
    o_ = np.argsort(dec_t)
    inds = {}
    for k, (ts, sg) in E.items():
        ts, sg = np.concatenate(ts) if ts else np.array([]), np.concatenate(sg) if sg else np.array([])
        oo = np.argsort(ts)
        inds[k] = (ts[oo], sg[oo] if k != "I6_print_after_silence" else None)
    return dec_t[o_], dec_s[o_], np.array(units), np.array(strata), inds


def run(period, names=None, ranges=RANGES, n_null=400):
    dt, ds, units, strata, inds = build(period)
    if names is not None:
        inds = {k: v for k, v in inds.items() if k in names}
    out = {"period": period, "decisions": int(len(dt)), "units": int(len(units)),
           "events": {k: int(len(v[0])) for k, v in inds.items()}}
    rows = []
    for tag, L, bs in ranges:
        rr = ind.screen(dt, inds, units, max_lag_s=L, bin_s=bs, n_null=n_null, strata=strata, decision_sign=ds)
        for r in rr:
            r["range"] = tag
        rows += rr
        print(period, tag, [(r["name"][:14], round(r["p_link"], 4), r["shape_peak_lag_s"], r.get("signed_p_link")) for r in rr], flush=True)
    ps = [r["p_link"] for r in rows] + [r["signed_p_link"] for r in rows if r["signed_p_link"] is not None]
    qs = ind.bh(ps)
    i = 0
    for r in rows:
        r["q_bh_family"] = float(qs[i]); i += 1
    for r in rows:
        if r["signed_p_link"] is not None:
            r["signed_q_bh_family"] = float(qs[i]); i += 1
    out["rows"] = rows
    return out


def main():
    res = {"build": run("BUILD")}
    surv = sorted({(r["name"], r["range"]) for r in res["build"]["rows"]
                   if r["q_bh_family"] <= 0.10 or (r.get("signed_q_bh_family") is not None and r["signed_q_bh_family"] <= 0.10)})
    res["survivors"] = [list(x) for x in surv]
    if surv:
        vals = []
        for tag, L, bs in RANGES:
            names = [n for n, rg in surv if rg == tag]
            if names:
                v = run("VALIDATE", names, ranges=[(tag, L, bs)], n_null=1000)
                vals += v["rows"]
        p = [min(r["p_link"], r["signed_p_link"]) if r.get("signed_p_link") is not None else r["p_link"] for r in vals]
        hp = ind.holm(p)
        for r, x in zip(vals, hp):
            r["holm_p"] = float(x)
            r["confirmed_alpha_0.01"] = bool(x <= 0.01)
        res["validate"] = vals
    (RES / "e3_screen.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res["survivors"]))


if __name__ == "__main__":
    main()
