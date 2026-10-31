"""Iteration 8, X56 (panel-assumptions iter7 P3): the tick is the clock, stale liquidity the gate?
100-ms grid over development window time (rel 5..285 s), as lag7. Features at t:
  tick   = signed ten-series microprice composite toward o over [t - 500, t) (lag7.micro_series / mv)
  touch  = ask of o at t from my unthrottled book (Up ask = ba, Down ask = 1 - bb of the Up book; server ms)
  repr   = how the ask of o changed over [t - 500, t): 'same' (unrepriced), 'up' (repriced against the buyer), 'down'
  age    = ms since the ask of o last changed
  act    = other traders' Polymarket trades on the window in [t - 1000, t)
Label: a cluster taker match on o in [t + 100, t + 600) (same window). Hazard tables and interleaved half-split
logistic AUCs: activity, tick, tick x repr x age (+ activity). Also the Polymarket-internal trigger: P(match) after an ask
DROP of o with no tick. Usage: python gate8.py OWN A B VENUE_FEED CLOB_FEED"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6, sealed
from lag7 import micro_series, mv
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score


DESIGN_ONLY = False


def design(tick, rp, age, act, ask):
    """the frozen feature sets of the decision-level hazard (same order as in main)."""
    la = np.log1p(np.nan_to_num(age, nan=1e5) / 100.0)
    return {"activity": np.c_[act, np.log1p(act)].astype(float),
            "activity+gate_only": np.c_[act, np.log1p(act), rp == 0, rp > 0, rp < 0, la, np.abs(ask - 0.5)].astype(float),
            "activity+tick": np.c_[act, np.log1p(act), tick, np.abs(tick), np.clip(tick, 0, None)].astype(float),
            "activity+tick+gate": np.c_[act, np.log1p(act), tick, np.abs(tick), np.clip(tick, 0, None), rp == 0, rp > 0, rp < 0,
                                        np.clip(tick, 0, None) * (rp == 0), np.clip(tick, 0, None) * (rp > 0), la, la * (tick > 0.02),
                                        np.abs(ask - 0.5)].astype(float)}


def raw_touch(feed, a, b):
    rows = []
    for r in L.recs(feed, a - 300, b):
        if r.get("k") == "p" and r.get("bb") is not None and r.get("ba") is not None:
            rows.append((r["s"], r["m"], r["bb"], r["ba"]))
    return pd.DataFrame(rows, columns=["s", "m", "bb", "ba"]).sort_values("s", kind="stable")


def main(own, a, b, vfeed, cfeed):
    d = live6.own_taker(own, a, b)
    tok, books, trades = L.load_books(a, b)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tok[t][1]); tk["is_up"] = tk.token.map(lambda t: tok[t][2])
    tk = tk[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in tk.start], bool)]
    tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()].sort_values("m").drop_duplicates(["tx", "token"])
    tk = tk[(tk.m >= a * 1000) & (tk.m < b * 1000)]
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool)
    S = micro_series(vfeed, a, b); keys = sorted(S)
    R = raw_touch(cfeed, a, b)
    wins = sorted({tok[t][1] for t in tok})
    G = []
    for st in wins:
        if sealed.is_sealed(st, "btc5m-bot"):
            continue
        g = np.arange((st + 5) * 1000, (st + 285) * 1000, 100, dtype=np.int64)
        g = g[(g >= a * 1000 + 5000) & (g < b * 1000)]
        G.append(np.c_[g, np.full(len(g), st)])
    G = np.vstack(G); t = G[:, 0]; st = G[:, 1]
    allc = np.zeros(len(t)); oka = np.zeros(len(t), bool)
    for key in keys:
        r = mv(S, key, t - 500, t); oka |= np.isfinite(r); allc += np.nan_to_num(r)
    # touch per window from the raw book
    askU = np.full(len(t), np.nan); askU5 = np.full(len(t), np.nan); askD = np.full(len(t), np.nan); askD5 = np.full(len(t), np.nan)
    ageU = np.full(len(t), np.nan); ageD = np.full(len(t), np.nan)
    for s0, rg in R.groupby("m"):
        sel = np.where(st == s0)[0]
        if not len(sel):
            continue
        rs = rg.s.to_numpy(np.int64); ba = rg.ba.to_numpy(float); bb = rg.bb.to_numpy(float)
        def at(x, tt):
            i = np.searchsorted(rs, tt, "right") - 1
            o = x[np.clip(i, 0, None)].astype(float); o[i < 0] = np.nan
            return o
        # last change time of each side's price
        chU = np.r_[True, np.diff(ba) != 0]; chD = np.r_[True, np.diff(bb) != 0]
        tU = rs[chU]; tD = rs[chD]
        tt = t[sel]
        askU[sel] = at(ba, tt); askU5[sel] = at(ba, tt - 500)
        askD[sel] = 1 - at(bb, tt); askD5[sel] = 1 - at(bb, tt - 500)
        iU = np.searchsorted(tU, tt, "right") - 1; iD = np.searchsorted(tD, tt, "right") - 1
        ageU[sel] = np.where(iU >= 0, tt - tU[np.clip(iU, 0, None)], np.nan)
        ageD[sel] = np.where(iD >= 0, tt - tD[np.clip(iD, 0, None)], np.nan)
    lab = {}
    for o in (True, False):
        mm = np.sort(m[up == o]); sm = tk.start.to_numpy()[up == o][np.argsort(m[up == o])]
        y = np.zeros(len(t), bool)
        i0 = np.searchsorted(mm, t + 100, "left"); i1 = np.searchsorted(mm, t + 600, "left")
        for j in np.where(i1 > i0)[0]:
            y[j] = (sm[i0[j]:i1[j]] == st[j]).any()
        lab[o] = y
    tr = trades[~trades.tx.isin(set(tk.tx))].copy()
    tr["start"] = tr.token.map(lambda x: tok.get(x, (None, -1))[1])
    nb = np.zeros(len(t))
    for s0, gg in tr.groupby("start"):
        ms = np.sort(gg.s_ms.to_numpy(np.int64)); sel = st == s0
        nb[sel] = np.searchsorted(ms, t[sel], "left") - np.searchsorted(ms, t[sel] - 1000, "left")
    keep = oka & np.isfinite(askU) & np.isfinite(askU5) & np.isfinite(askD) & np.isfinite(askD5)
    Y, TK, RP, AG, ACT, ASK = [], [], [], [], [], []
    for o, sg in ((True, 1.0), (False, -1.0)):
        ak, ak5, ag = (askU, askU5, ageU) if o else (askD, askD5, ageD)
        k = keep & (ak > 0.03) & (ak < 0.97)
        Y.append(lab[o][k]); TK.append(sg * allc[k]); RP.append(np.sign(np.round((ak[k] - ak5[k]) * 100))); AG.append(ag[k]); ACT.append(nb[k]); ASK.append(ak[k])
    y = np.concatenate(Y); tick = np.concatenate(TK); rp = np.concatenate(RP); age = np.concatenate(AG); act = np.concatenate(ACT); ask = np.concatenate(ASK)
    if DESIGN_ONLY:
        return y, design(tick, rp, age, act, ask)
    res = {"interval": [a, b], "grid_points": int(len(y)), "matches": int(len(m)), "base_rate": round(float(y.mean()), 5)}
    tb = pd.cut(tick, [-100, -0.1, -0.02, 0.02, 0.1, 0.5, 100], labels=["<-0.1", "-0.1..-0.02", "flat", "0.02-0.1", "0.1-0.5", ">0.5"])
    rpl = np.where(rp > 0, "up", np.where(rp < 0, "down", "same"))
    tab = pd.DataFrame({"y": y, "tb": tb, "rp": rpl}).groupby(["tb", "rp"], observed=False).y.agg(["mean", "size"])
    res["hazard_tick_x_repr"] = {f"{i[0]}|{i[1]}": [round(float(v["mean"]), 4), int(v["size"])] for i, v in tab.iterrows() if v["size"] > 0}
    ab = pd.cut(age, [-1, 300, 1000, 3000, 10000, 1e12], labels=["<0.3s", "0.3-1s", "1-3s", "3-10s", ">10s"])
    k = (tick > 0.1) & (rpl == "same")
    tab2 = pd.DataFrame({"y": y[k], "ab": ab[k]}).groupby("ab", observed=False).y.agg(["mean", "size"])
    res["hazard_tick_gt0.1_unrepriced_by_age"] = {str(i): [round(float(v["mean"]), 4), int(v["size"])] for i, v in tab2.iterrows()}
    # half-split AUCs (interleaved by grid order)
    half = np.arange(len(y)) % 2 == 0
    la = np.log1p(age / 100.0)
    Xs = {"activity": np.c_[act, np.log1p(act)],
          "tick": np.c_[tick, np.abs(tick), np.clip(tick, 0, None)],
          "activity+tick": np.c_[act, np.log1p(act), tick, np.abs(tick), np.clip(tick, 0, None)],
          "activity+tick+gate": np.c_[act, np.log1p(act), tick, np.abs(tick), np.clip(tick, 0, None), rp == 0, rp > 0, rp < 0,
                                      np.clip(tick, 0, None) * (rp == 0), np.clip(tick, 0, None) * (rp > 0), la, la * (tick > 0.02), np.abs(ask - 0.5)],
          "activity+gate_only": np.c_[act, np.log1p(act), rp == 0, rp > 0, rp < 0, la, np.abs(ask - 0.5)]}
    for nm, X in Xs.items():
        X = np.asarray(X, float)
        lr = LogisticRegression(max_iter=2000).fit(X[half], y[half])
        res[f"auc_{nm}"] = round(float(roc_auc_score(y[~half], lr.predict_proba(X[~half])[:, 1])), 4)
    # Polymarket-internal trigger: ask of o dropped in [t-500, t) with no tick toward o
    for nm, kk in (("ask_down_no_tick", (rp < 0) & (np.abs(tick) <= 0.02)), ("ask_same_no_tick", (rp == 0) & (np.abs(tick) <= 0.02)),
                   ("ask_up_no_tick", (rp > 0) & (np.abs(tick) <= 0.02))):
        res["hazard_" + nm] = [round(float(y[kk].mean()), 4), int(kk.sum())]
    return res


if __name__ == "__main__":
    own, a, b, vf, cf = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
    res = main(own, a, b, vf, cf)
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", f"gate8_{a}.json"), "w"), indent=1)
    print(json.dumps(res, indent=0)[:3500])
