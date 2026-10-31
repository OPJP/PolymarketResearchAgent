"""Iteration 10 (panel iter9 mechanics P2 = X78): the trigger unit = a Binance USD-M BTC bookTicker EVENT, scored per event.
Events (btc5m_venues2, exchange ms E): every L1 update that changes the microprice; consecutive same-sign updates within 50 ms
merged into one event at the first update tau; class = PRICE (bid or ask price changed in the event) / DEPLETE (size-only:
the size on the side the microprice moves toward fell) / REFILL (size-only: the opposite side's size rose); magnitude = the
microprice move of the event (bp). For the BTC 5m window live at tau, o = the outcome the move favours (Up if up).
Kept: rel 5..285 s, o's ask in (0.12, 0.88), and no cluster decision on the window in [tau - 600, tau + 150) (clean events).
Label: a cluster DECISION on o (taker match at matching-engine ms, or a located lost-race insertion, it9/ins9b_M) in
[tau + 150, tau + 700) ms. Fit on A (14:55-16:04), scored on C (16:33-17:55): P(decision) by class x magnitude, by whether o's
ask is unchanged at tau + 150 (the bot's 50-150 ms stale view), by OKX / Bybit agreement in [tau - 100, tau], and a logistic
on event features (class, log magnitude, ask unchanged, |ask - 0.5|, agreement, spread) -> out-of-sample AUC; and the
Polymarket-activity baseline (other trades on the window in the previous 1 s, o's ask change over the previous 500 ms).
Usage: python evt10.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9, live6, gate8
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C


def l1(feed, a, b, venue, sym="BTC"):
    rows = []
    for r in L.recs(feed, a - 30, b + 5):
        if r.get("v") == venue and r.get("y") == sym and r.get("b") and r.get("a"):
            rows.append((r.get("E") or r["t"], r["b"], r.get("B") or 0, r["a"], r.get("A") or 0))
    x = np.array(rows, float)
    x = x[np.argsort(x[:, 0], kind="stable")]
    return x


def events(x, merge=50):
    E = x[:, 0].astype(np.int64); b, B, a, A = x[:, 1], x[:, 2], x[:, 3], x[:, 4]
    mic = (b * A + a * B) / np.maximum(A + B, 1e-12)
    d = np.diff(mic); sg = np.sign(d)
    pchg = (np.diff(b) != 0) | (np.diff(a) != 0)
    # size-only: up move by ask size falling = deplete; by bid size rising = refill (mirror for down)
    dA = np.diff(A); dB = np.diff(B)
    dep = np.where(sg > 0, dA < 0, dB < 0)
    out = []; i = 0; n = len(d)
    while i < n:
        if sg[i] == 0:
            i += 1; continue
        j = i; mag = 0.0; anyp = False; ndep = 0; nup = 0
        while j < n and sg[j] == sg[i] and E[j + 1] - E[i + 1] <= merge:
            mag += d[j]; anyp |= pchg[j]; ndep += int(dep[j] and not pchg[j]); nup += 1; j += 1
        cls = "PRICE" if anyp else ("DEPLETE" if ndep * 2 >= nup else "REFILL")
        out.append((E[i + 1], int(sg[i]), mag / mic[i] * 1e4, cls, (a[i] - b[i]) / mic[i] * 1e4))
        i = j
    return pd.DataFrame(out, columns=["tau", "sgn", "bp", "cls", "spread_bp"])


def build(a, b, lost):
    x = l1("btc5m_venues2", a, b, "bf")
    ev = events(x)
    ev = ev[(ev.tau >= a * 1000 + 3000) & (ev.tau < b * 1000 - 1000)].reset_index(drop=True)
    # other venues: last move sign within [tau - 100, tau]
    agree = np.zeros(len(ev))
    for v in ("ok", "by"):
        y = l1("btc5m_venues2", a, b, v)
        if not len(y):
            continue
        T = y[:, 0].astype(np.int64); mic = (y[:, 1] * y[:, 4] + y[:, 3] * y[:, 2]) / np.maximum(y[:, 2] + y[:, 4], 1e-12)
        i0 = np.searchsorted(T, ev.tau.to_numpy() - 100, "right") - 1; i1 = np.searchsorted(T, ev.tau.to_numpy(), "right") - 1
        mv = mic[np.clip(i1, 0, None)] - mic[np.clip(i0, 0, None)]
        agree += (np.sign(mv) == ev.sgn.to_numpy()) & (mv != 0)
    ev["agree"] = agree
    # cluster decisions
    d = live6.own_taker(stale9.OWN, a - 5, b + 5)
    tok, books, trades = L.load_books(a - 5, b + 5)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tok[t][1]); tk["is_up"] = tk.token.map(lambda t: tok[t][2]); tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()]
    lo = lost[(lost.s_ins >= (a - 5) * 1000) & (lost.s_ins < (b + 5) * 1000)]
    dec = pd.concat([pd.DataFrame({"st": tk.start.astype(int), "up": tk.is_up.astype(bool), "s": tk.m.astype(np.int64)}),
                     pd.DataFrame({"st": lo.mstart.astype(int), "up": lo.is_up.astype(bool), "s": lo.s_ins.astype(np.int64)})])
    decg = {k: np.sort(g.s.to_numpy(np.int64)) for k, g in dec.groupby(["st", "up"])}
    decw = {k: np.sort(g.s.to_numpy(np.int64)) for k, g in dec.groupby("st")}
    R = gate8.raw_touch("btc5m_clob_raw2", a, b)
    tch = {m: (g.s.to_numpy(np.int64), g.bb.to_numpy(float), g.ba.to_numpy(float)) for m, g in R.groupby("m")}
    trn = trades[~trades.tx.isin(set(tk.tx))].copy(); trn["st"] = trn.token.map(lambda t: tok.get(t, (None, -1))[1])
    oth = {k: np.sort(g.s_ms.to_numpy(np.int64)) for k, g in trn.groupby("st")}
    tau = ev.tau.to_numpy(np.int64); st = (tau // 300000) * 300; rel = tau / 1000 - st
    up = ev.sgn.to_numpy() > 0
    ask = np.full(len(ev), np.nan); ask150 = np.full(len(ev), np.nan); ask500 = np.full(len(ev), np.nan)
    y = np.zeros(len(ev), bool); clean = np.zeros(len(ev), bool); act = np.zeros(len(ev))
    for i in range(len(ev)):
        T = tch.get(int(st[i]))
        if T is None:
            continue
        rs, bb, ba = T
        def at(t_):
            j = np.searchsorted(rs, t_, "right") - 1
            if j < 0:
                return np.nan
            return ba[j] if up[i] else 1 - bb[j]
        ask[i] = at(tau[i]); ask150[i] = at(tau[i] + 150); ask500[i] = at(tau[i] - 500)
        g = decg.get((int(st[i]), bool(up[i])))
        if g is not None:
            y[i] = np.searchsorted(g, tau[i] + 700) > np.searchsorted(g, tau[i] + 150)
        gw = decw.get(int(st[i]))
        clean[i] = True if gw is None else not (np.searchsorted(gw, tau[i] + 150) > np.searchsorted(gw, tau[i] - 600))
        om = oth.get(int(st[i]))
        if om is not None:
            act[i] = np.searchsorted(om, tau[i]) - np.searchsorted(om, tau[i] - 1000)
    ev["st"] = st; ev["rel"] = rel; ev["ask"] = ask; ev["unch150"] = np.abs(ask150 - ask) < 1e-6; ev["y"] = y; ev["clean"] = clean
    ev["act"] = act; ev["rp"] = np.sign(np.round((ask - ask500) * 100))
    ev = ev[(ev.rel >= 5) & (ev.rel <= 285) & (ev.ask > 0.12) & (ev.ask < 0.88) & ev.clean].reset_index(drop=True)
    return ev


def X(ev, kind):
    lm = np.log10(np.abs(ev.bp.to_numpy()) + 1e-4)
    base = np.c_[ev.act, np.log1p(ev.act), ev.rp == 0, ev.rp > 0, np.abs(ev.ask - 0.5)]
    full = np.c_[base, ev.cls == "PRICE", ev.cls == "DEPLETE", lm, lm * (ev.cls == "PRICE"), ev.unch150, ev.agree, np.clip(ev.spread_bp, 0, 5)]
    return (base if kind == "base" else full).astype(float)


def tab(ev):
    out = {}
    for c, g in ev.groupby("cls"):
        row = {"n": int(len(g)), "P": round(float(g.y.mean()), 4)}
        for lo, hi in ((0, 0.01), (0.01, 0.05), (0.05, 0.2), (0.2, 99)):
            s = (g.bp.abs() >= lo) & (g.bp.abs() < hi)
            if s.sum() >= 20:
                row[f"|bp| {lo}-{hi}"] = [round(float(g.y[s].mean()), 4), int(s.sum())]
        row["ask_unch_at_150"] = [round(float(g.y[g.unch150].mean()), 4), int(g.unch150.sum())] if g.unch150.any() else None
        row["ask_moved_by_150"] = [round(float(g.y[~g.unch150].mean()), 4), int((~g.unch150).sum())] if (~g.unch150).any() else None
        out[c] = row
    out["by_agree"] = {str(int(k)): [round(float(g.y.mean()), 4), int(len(g))] for k, g in ev.groupby("agree")}
    return out


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    a, b = stale9.IV["A"]; c0, c1 = stale9.IV["C"]
    eA = build(a, b, lost); eC = build(c0, c1, lost)
    res = {"events_A": int(len(eA)), "events_C": int(len(eC)), "base_A": round(float(eA.y.mean()), 4), "base_C": round(float(eC.y.mean()), 4),
           "table_A": tab(eA), "table_C": tab(eC)}
    for kind in ("base", "full"):
        XA, XC = X(eA, kind), X(eC, kind)
        mu, sd = XA.mean(0), XA.std(0) + 1e-9
        m = LogisticRegression(max_iter=3000).fit((XA - mu) / sd, eA.y)
        p = m.predict_proba((XC - mu) / sd)[:, 1]
        res[f"auc_C_{kind}"] = round(float(roc_auc_score(eC.y, p)), 4)
        if kind == "full":
            res["coef_full"] = [round(float(c), 3) for c in m.coef_[0]]
            q = np.quantile(p, 0.9)
            res["top10pct_P_C"] = round(float(eC.y[p >= q].mean()), 4)
            # decisions on C reproduced: share of the C decisions (clean-event labels) covered by flagged events at matched volume
            k = int(eC.y.sum()); thr = np.sort(p)[-max(k, 1)]
            res["matched_volume_precision_C"] = round(float(eC.y[p >= thr].mean()), 4)
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x)))


if __name__ == "__main__":
    main(sys.argv[1])
