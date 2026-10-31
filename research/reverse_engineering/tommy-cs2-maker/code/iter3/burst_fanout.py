"""Iteration 3, assumptions panel P3 (X28) and P1 (X26) on the server clock.

(a) Bursts and fan-out: the wallet's taker orders grouped per event; an order is 'first' if no own taker order in any
    market of the same event was signed in the previous 2 s. Server-clock collapse events in [sign - 2 s, sign] are
    split by first vs follow-up orders (a follow-up can sit after the wave its own first order provoked).
    Fan-out: orders in two markets of the same event signed within 50 ms (historical, 16-22 Oct calldata_all, and
    the development block).
(b) Fill race (attempt censoring): for every server-clock collapse event in the wallet's markets, the depth left on
    the collapsed side at event + 1.0 s (when a FAK signed ~50 ms before the wave would match) relative to the
    reference; P(wallet order within [-0.3, +0.1] s of the event | depth left >= 30% of the reference) vs < 30%.
Development data only (dev-unit markets; 16-22 Oct). Output: results/burst_fanout.json
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, T0, read, series_own, series_shared, events  # noqa: E402


def main():
    now = time.time()
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    m = m[m.wallet_trades > 0]
    tok = {}
    ev_of = {}
    for r in m.itertuples():
        tok[r.tok0] = (r.cid, 0, r.tok0)
        tok[r.tok1] = (r.cid, 1, r.tok0)
        ev_of[r.tok0] = r.event
    tok0 = set(m.tok0)
    sh = read("clob_wallets", tok0, T0 + 12 * 3600, now)
    ow = read("tommy_cs2_near", tok0, T0 + 12 * 3600, now)
    X = {}
    for r in sh + ow:
        if r.get("k") == "x":
            X.setdefault(((r.get("h") or "").lower(), r["s"], r["a"]), r)
    trades = {a: np.sort(np.array([k[1] for k in X if k[2] == a], dtype=float)) for a in tok0}
    ser = {}
    for a in tok0:
        so = series_own([r for r in ow if r["a"] == a and r["k"] in ("f", "pc")])
        ss = series_shared([r for r in sh if r["a"] == a])
        t0 = so[0][0] if so else np.inf
        ser[a] = pd.DataFrame([x for x in ss if x[0] < t0] + so, columns=["s", "t", "Db", "Do", "bb", "ba"]).sort_values("s").reset_index(drop=True)
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    d = d[(d.idx == -1) & (d.sign_ms > 1.79e12) & (d.sign_ms < now * 1000 + 5000) & d.token_id.astype(str).isin(tok)].drop_duplicates("tx").copy()
    d["a"] = d.token_id.astype(str).map(lambda t: tok[t][2])
    d["team"] = [(tok[str(t)][1] if s == 0 else 1 - tok[str(t)][1]) for t, s in zip(d.token_id, d.side)]
    d["event"] = d.a.map(ev_of)
    w = d[d.maker == WALLET].sort_values("sign_ms").copy()
    prev = []
    for r in w.itertuples():
        e = w[(w.event == r.event) & (w.sign_ms < r.sign_ms) & (w.sign_ms >= r.sign_ms - 2000)]
        prev.append(len(e) > 0)
    w["follow"] = prev
    evt = {}
    for a in tok0:
        df = ser[a]
        S = df.s.to_numpy().astype(float)
        for team, col in ((0, "Do"), (1, "Db")):
            evt[(a, team)] = (events(S, df[col].to_numpy(), trades[a]), S, df[col].to_numpy())
    pre, rows = [], []
    for r in w.itertuples():
        e, S, D = evt[(r.a, r.team)]
        if len(S) == 0 or r.sign_ms < S[0] + 2000 or r.sign_ms > S[-1]:
            continue
        rows.append({"follow": r.follow, "pre": bool(((e >= r.sign_ms - 2000) & (e <= r.sign_ms)).any()),
                     "post": bool(((e > r.sign_ms) & (e <= r.sign_ms + 1100)).any())})
    rr = pd.DataFrame(rows)
    res = {"wallet_orders_with_book": int(len(rr)),
           "first_orders": {"n": int((~rr.follow).sum()), "pre_event": round(float(rr[~rr.follow].pre.mean()), 3),
                            "post_event": round(float(rr[~rr.follow].post.mean()), 3)},
           "follow_up_orders": {"n": int(rr.follow.sum()), "pre_event": round(float(rr[rr.follow].pre.mean()), 3) if rr.follow.any() else None,
                                "post_event": round(float(rr[rr.follow].post.mean()), 3) if rr.follow.any() else None}}
    # fan-out in the dev block
    fo = 0
    for r in w.itertuples():
        o = w[(w.event == r.event) & (w.a != r.a) & ((w.sign_ms - r.sign_ms).abs() <= 50)]
        fo += len(o) > 0
    res["dev_fanout_orders_share"] = round(fo / max(len(w), 1), 3)
    # historical fan-out (16-22 Oct)
    o = pd.read_parquet(OUT / "orders.parquet")
    tk = o[o.role == "taker"] if "role" in o.columns else o[o.is_taker] if "is_taker" in o.columns else None
    res["orders_columns"] = list(o.columns)[:30]
    if tk is not None and "event" in tk.columns:
        tk = tk.sort_values("sign_ms")
        pairs = 0
        gaps = []
        for ev, g in tk.groupby("event"):
            s = g.sign_ms.to_numpy()
            mk = g.cid.to_numpy()
            for i in range(len(s)):
                j = np.searchsorted(s, s[i] - 50)
                for k in range(j, i):
                    if mk[k] != mk[i]:
                        pairs += 1
                        gaps.append(s[i] - s[k])
        res["hist_fanout_pairs_within_50ms"] = pairs
        res["hist_fanout_gap_ms_p50_p90"] = [float(np.percentile(gaps, 50)), float(np.percentile(gaps, 90))] if gaps else None
        res["hist_taker_orders"] = int(len(tk))
    # (b) fill race on server-clock events
    wa = {}
    for r in w.itertuples():
        wa.setdefault((r.a, r.team), []).append(r.sign_ms)
    race = []
    for (a, team), (e, S, D) in evt.items():
        ws = np.array(sorted(wa.get((a, team), [])))
        for t in e:
            lo, hi = np.searchsorted(S, t - 1500), np.searchsorted(S, t - 400, side="right")
            ref = D[lo:hi].max() if hi > lo else np.nan
            i1 = np.searchsorted(S, t + 1000, side="right") - 1
            left = D[i1] / ref if ref and ref > 0 else np.nan
            acted = bool(len(ws) and ((ws >= t - 300) & (ws <= t + 100)).any())
            race.append({"left": left, "acted": acted})
    rc = pd.DataFrame(race)
    rc["hi_left"] = rc.left >= 0.3
    res["race"] = {"events": int(len(rc)), "acted": int(rc.acted.sum()),
                   "P_acted_left_ge_30pct": round(float(rc[rc.hi_left].acted.mean()), 3), "n_left_ge_30pct": int(rc.hi_left.sum()),
                   "P_acted_left_lt_30pct": round(float(rc[~rc.hi_left].acted.mean()), 3), "n_left_lt_30pct": int((~rc.hi_left).sum()),
                   "left_at_plus1s_acted_median": round(float(rc[rc.acted].left.median()), 3) if rc.acted.any() else None,
                   "left_at_plus1s_not_acted_median": round(float(rc[~rc.acted].left.median()), 3)}
    json.dump(res, open(RES / "burst_fanout.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
