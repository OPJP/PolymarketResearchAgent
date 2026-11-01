"""Iteration 17, PRE-REGISTRATION 14 (resting-remainder stream, rest17): data preparation copied from phase17.py.
PRE-REGISTRATION 13 (original phase17 docstring follows) (NOTES.md, written 09:53 UTC 11-01 before this runs): two-phase hazard target for the exposure
tracker. Reuses hazflow14's per-second frame (it14/hazflow14.parquet: h, y per (cid, rel) for 10-17..22) and its tracker harness
(track12.run, variant trk_a) on the 864 windows of 10-20..22, with the it16 taker tapes. mix14 (adopted, reference) vs mix17 (two
phases at 60 s, primary) and mix17b (three phases, reported only). Usage: python phase17.py TAPE_DIR"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import track12

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
TD = sys.argv[1]
Hs = pd.read_parquet(os.environ["RE16_SCRATCH"] + "/it14/hazflow14.parquet")
FIT = {"2026-10-17", "2026-10-18", "2026-10-19"}
fit = Hs.day.isin(FIT).to_numpy()
c0 = float((Hs.h[fit] * Hs.y[fit]).sum() / (Hs.h[fit] ** 2).sum())
res = {"c_mix14_refit": round(c0, 4)}
for nm, edges in (("mix17", [60]), ("mix17b", [60, 180])):
    ph = np.digitize(Hs.rel.to_numpy(), edges)
    X = np.column_stack([Hs.h.to_numpy() * (ph == k) for k in range(len(edges) + 1)])
    cc = np.linalg.lstsq(X[fit], Hs.y.to_numpy()[fit], rcond=None)[0]
    Hs[f"nf_{nm}"] = X @ cc
    res[f"coef_{nm}"] = [round(float(x), 4) for x in cc]
vo = pd.read_parquet(f"{C}/val_outcome_it4b.parquet", columns=["cid", "rel", "nf", "ask_u", "ask_d"]).merge(
    pd.read_parquet(f"{C}/it12/nf12b_val.parquet")[["cid", "rel", "nf12b"]], on=["cid", "rel"], how="left")
S = Hs[~fit].merge(vo, on=["cid", "rel"], how="left").sort_values(["cid", "rel"])
S["avg"] = 0.5 * (S.nf + S.nf12b.fillna(0)); S["mix14"] = 0.5 * S.avg + 0.5 * S.nfhaz
for nm in ("mix17", "mix17b"):
    S[nm] = 0.5 * S.avg + 0.5 * S[f"nf_{nm}"]
g = S.groupby("cid").agg(y=("y", "sum"), mix14=("mix14", "sum"), mix17=("mix17", "sum"), mix17b=("mix17b", "sum"))
res["window_net_r"] = {k: round(float(g.y.corr(g[k])), 4) for k in ("mix14", "mix17", "mix17b")}
res["window_net_spearman"] = {k: round(float(g.y.corr(g[k], method="spearman")), 4) for k in ("mix14", "mix17", "mix17b")}
print(json.dumps(res), flush=True)
winx = pd.read_parquet(f"{C}/windows.parquet").set_index("cid"); cids = S.cid.unique()
fl2 = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "shares", "price", "fee_usd", "cid", "start_ts", "is_up", "up_payout"])
fl2 = fl2[fl2.cid.isin(cids)]
mk_tx = set(fl2.loc[fl2.role == "M", "tx"].str.lower())
parts = [pd.read_parquet(f"{TD}/{c_}.parquet", columns=["proxyWallet", "side", "size", "price", "timestamp", "outcome", "transactionHash"]).assign(cid=c_)
         for c_ in cids if os.path.exists(f"{TD}/{c_}.parquet")]
TA = pd.concat(parts, ignore_index=True); del parts
TA = TA[(TA.side == "BUY") & ~TA.proxyWallet.str.lower().isin(track12.CL)]
TA["rel"] = TA.timestamp - winx.loc[TA.cid, "start_ts"].to_numpy(); TA = TA[(TA.rel >= -2) & (TA.rel <= 305)]
TA["mk"] = TA.transactionHash.str.lower().isin(mk_tx); TA["up"] = TA.outcome == "Up"
TA = TA.sort_values(["cid", "up", "rel"], kind="stable")
tapes = {}
for (c_, o), dd in TA.groupby(["cid", "up"], sort=False):
    tapes.setdefault(c_, {True: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool)), False: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool))})
    tapes[c_][bool(o)] = (dd.rel.to_numpy(np.int64), dd.price.to_numpy(float), dd["size"].to_numpy(float), dd.mk.to_numpy())
fl2["pay"] = np.where(fl2.is_up, fl2.up_payout, 1 - fl2.up_payout); fl2["pnl"] = fl2.shares * (fl2.pay - fl2.price) - fl2.fee_usd
Wp = {w: fl2[fl2.wallet == w].groupby("cid").pnl.sum().reindex(cids).fillna(0) for w in ("GF", "XM", "DS")}
Wp["pool"] = fl2.groupby("cid").pnl.sum().reindex(cids).fillna(0)
blocks = winx.loc[cids, "start_ts"].to_numpy() // 7200
half = winx.loc[cids, "start_ts"].to_numpy() < int(pd.Timestamp("2026-10-21 12:00", tz="UTC").timestamp())
res["n_windows"] = int(len(cids)); res["tapes_found"] = int(len(tapes))


def run_rest(win, vo, tapes, mk_tx, var, ttl, cap_rest=0.5, slack_through=0.02):
    """track12.run (trk_a) + resting remainders: the unfilled part rests as a BUY bid on o at L for ttl s after the taker window and
    fills against later complement taker BUY prints (other traders) at >= 1 - L + slack_through, capturing cap_rest of each print."""
    lot, slack, lo, hi, step, cap, excl = var
    rows = []
    for cid, g in vo.groupby("cid", sort=False):
        if cid not in tapes:
            continue
        pay_up = win.at[cid, "up_payout"]
        nf = g.nf.to_numpy(float); au = g.ask_u.to_numpy(float); ad = g.ask_d.to_numpy(float); rel = g.rel.to_numpy(np.int64)
        tgt = np.cumsum(np.nan_to_num(nf))
        P0 = tapes[cid]
        P = {o: tuple(a[~P0[o][3]] for a in P0[o][:3]) for o in (True, False)} if excl else {o: P0[o][:3] for o in (True, False)}
        used = {o: np.zeros(len(P[o][0])) for o in (True, False)}       # shares of each complement print already taken by resting bids
        rest = []                                                        # [o, L, left, t_from, t_to]
        Rn = 0.0; nxt = 0
        for i in range(len(rel)):
            s = rel[i]
            # resting bids: fill against complement BUY prints in (last checked, s]
            for rb in rest:
                o_, L_, left_, a_, b_ = rb
                if left_ <= 1e-9 or a_ >= min(b_, s):
                    continue
                Rr, Pp, Zz = P[not o_]
                k0, k1 = np.searchsorted(Rr, a_, "right"), np.searchsorted(Rr, min(b_, s), "right")
                pay = pay_up if o_ else 1 - pay_up
                for k in range(k0, k1):
                    if Pp[k] >= 1 - L_ + slack_through - 1e-9:
                        avail = cap_rest * Zz[k] - used[not o_][k]
                        sh = min(left_, max(avail, 0.0))
                        if sh > 0:
                            used[not o_][k] += sh; left_ -= sh
                            rows.append((cid, o_, L_, sh, sh * (pay - L_), "rest"))   # maker fill: no taker fee
                            Rn += sh if o_ else -sh
                        if left_ <= 1e-9:
                            break
                rb[2] = left_; rb[3] = min(b_, s)
            if s < nxt:
                continue
            d = tgt[i] - Rn
            if abs(d) < lot:
                continue
            o = d > 0
            a = au[i] if o else ad[i]
            if not (np.isfinite(a) and 0.05 < a < 0.95):
                continue
            lim = min(a + slack, 0.99)
            q = np.floor(abs(d) / lot) * lot
            Rr, Pp, Zz = P[o]
            k0, k1 = np.searchsorted(Rr, s + lo, "left"), np.searchsorted(Rr, s + hi, "right")
            left = q; pay = pay_up if o else 1 - pay_up
            for k in range(k0, k1):
                if Pp[k] <= lim + 1e-9:
                    sh = min(left, cap * Zz[k]); left -= sh
                    if sh > 0:
                        rows.append((cid, o, Pp[k], sh, sh * (pay - Pp[k]) - FEE * Pp[k] * (1 - Pp[k]) * sh, "take"))
                        Rn += sh if o else -sh
                    if left <= 1e-9:
                        break
            if left > 1e-9 and ttl > 0:
                rest.append([o, lim, left, s + hi, s + hi + ttl])
            nxt = s + step
    return pd.DataFrame(rows, columns=["cid", "up", "price", "shares", "pnl", "kind"])


FEE = track12.FEE
for nm, ttl in (("mix14", 0), ("rest30", 30), ("rest10", 10), ("rest60", 60)):
    v = S[["cid", "rel", "ask_u", "ask_d"]].copy(); v["nf"] = S["mix14"].to_numpy()
    T = run_rest(winx, v, tapes, mk_tx, track12.VARIANTS["trk_a"], ttl)
    rp = T.groupby("cid").pnl.sum().reindex(cids).fillna(0)
    o = {"fills": int(len(T)), "rest_fills": int((T.kind == "rest").sum()), "rest_shares": round(float(T[T.kind == "rest"].shares.sum()), 1),
         "pnl_before_rebates": round(float(T.pnl.sum()), 1), "rest_pnl": round(float(T[T.kind == "rest"].pnl.sum()), 1)}
    for w, wp in Wp.items():
        o[w] = [round(float(rp.corr(wp)), 4), round(float(rp.corr(wp, method="spearman")), 4)]
    x, yy = rp.to_numpy(), Wp["pool"].to_numpy()
    o["pool_halves"] = [round(float(np.corrcoef(x[h], yy[h])[0, 1]), 4) for h in (half, ~half)]
    o["pool_halves_spearman"] = [round(float(pd.Series(x[h]).corr(pd.Series(yy[h]), method="spearman")), 4) for h in (half, ~half)]
    res[f"tracker_{nm}"] = o
    print(nm, json.dumps(o), flush=True)
a, b = res["tracker_mix14"]["pool"], res["tracker_rest30"]["pool"]
res["adopted_rest30"] = bool(b[0] > a[0] and b[1] > a[1])
json.dump(res, open(f"{R}/rest17.json", "w"), indent=1)
print("adopted", res["adopted_rest30"])
