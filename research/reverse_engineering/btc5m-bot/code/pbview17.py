"""Iteration 17 (panel iter16 information P3 = X166): is the bot's Polymarket view PolyBolt's price.polymarket or the CLOB market channel?
New-regime record (11-01 06:00-09:30 development windows): operator taker orders (DS / GF / XM / W4) with calldata limit L and size,
match ms m (server). Seen ask a_seen = L - 0 c (small, < 90 shares) or L - 1 c (large) (iteration 16 finding 7). Feeds, both received on
this laptop: btc5m_clob_raw2 'p' (Up-token touch bb / ba after every price change near the touch, server ms s) and btc5m_pb 'b'
(PolyBolt best bid / ask per token, producer ms). Receive times are mapped to the server clock with ONE local offset D(t) = trailing
60-s median of (t - s) of the CLOB records, so PolyBolt keeps its extra delivery lag. For lag Lam = 0..300 ms: the feed's latest state
received (server clock) at or before A - Lam, A = m - 150 (arrival); P(o's ask == a_seen). Discriminating subset: orders whose CLOB
channel shows inside [A - 120, A - 10] an o-ask value that PolyBolt never displays within [A - 400, A + 100] (a CLOB-only transient);
the share of those orders whose a_seen equals such a transient, against the CLOB-side base rate of the same values.
Usage: python pbview17.py"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live

S = os.environ["RE16_SCRATCH"] + "/it17"
W5 = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM",
      "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS", "0xd84403efd50b49a1d8a7181627e00307e6ea5908": "W4",
      "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c": "W5"}
win = pd.read_parquet(S + "/post17_windows.parquet")
cd = pd.read_parquet(S + "/post17_cd.parquet"); xr = pd.read_parquet(S + "/post17_xms.parquet")
cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["tx"] = cd.tx.str.lower(); cd["wallet"] = cd.maker.str.lower().map(W5)
cd = cd[cd.wallet.notna()]
tok = pd.concat([win[["cid", "start_ts", "up_token"]].rename(columns={"up_token": "token"}).assign(is_up=True),
                 win[["cid", "start_ts", "down_token"]].rename(columns={"down_token": "token"}).assign(is_up=False)])
cd = cd.drop(columns=[c for c in ("cid", "start_ts") if c in cd]).merge(tok, on="token", how="inner")
cd["m"] = cd.tx.map(xr.dropna(subset=["s"]).groupby("tx").s.min()); cd = cd[cd.m.notna()].copy()
cd["L"] = (cd.maker_amt / cd.taker_amt).round(2); cd["large"] = cd.taker_amt >= 90
cd["a_seen"] = (cd.L - np.where(cd.large, 0.01, 0.0)).round(2)
a0, b0 = int(win.start_ts.min()) - 60, int(win.end_ts.max()) + 10
C = {}; P = {}; off = []
for r in live.iter_live("btc5m_clob_raw2", a0, b0):
    if r.get("k") == "p" and r.get("bb") is not None and r.get("ba") is not None:
        C.setdefault(int(r["m"]), []).append((r["t"], r["s"], float(r["bb"]), float(r["ba"])))
        off.append((r["t"], r["t"] - r["s"]))
for r in live.iter_live("btc5m_pb", a0, b0):
    if r.get("k") == "b" and r.get("n", 0) == 0:
        try:
            P.setdefault((int(r["m"]), int(r["u"])), []).append((r["t"], float(r["bb"]), float(r["ba"])))
        except (TypeError, ValueError):
            pass
off = np.array(off, float); off = off[np.argsort(off[:, 0])]
sec = (off[:, 0] // 1000).astype(np.int64)
g = pd.Series(off[:, 1]).groupby(sec).median()
full = pd.Series(np.nan, index=np.arange(sec.min(), sec.max() + 1)); full.loc[g.index] = g.values
D = full.rolling(60, min_periods=5).median().ffill().bfill()
toD = lambda t: D.reindex(np.asarray(t, np.int64) // 1000).ffill().bfill().to_numpy()
# per window arrays of o-ask on the server clock (receive mapped), per outcome
feeds = {}
for m_, rows in C.items():
    a = np.array(rows, float); a = a[np.argsort(a[:, 0], kind="stable")]
    rs = a[:, 0] - toD(a[:, 0])
    feeds[("clob", m_, 1)] = (rs, a[:, 3]); feeds[("clob", m_, 0)] = (rs, np.round(1 - a[:, 2], 2))
    feeds[("clob_srv", m_, 1)] = (a[:, 1], a[:, 3]); feeds[("clob_srv", m_, 0)] = (a[:, 1], np.round(1 - a[:, 2], 2))
for (m_, u), rows in P.items():
    a = np.array(rows, float); a = a[np.argsort(a[:, 0], kind="stable")]
    feeds[("pb", m_, u)] = (a[:, 0] - toD(a[:, 0]), np.round(a[:, 2], 2))
LAMS = list(range(0, 301, 10))
res = {"orders": int(len(cd)), "clob_windows": len(C), "pb_tokens": len(P), "D_ms_q": [float(x) for x in np.nanquantile(D.to_numpy(), [0, 0.5, 1])]}
prof = {}
for fd in ("clob", "pb", "clob_srv"):
    for w in ("ALL", "DS", "GF", "XM", "W4"):
        x = cd if w == "ALL" else cd[cd.wallet == w]
        hits = np.zeros(len(LAMS)); n = 0
        for o in x.itertuples():
            k = (fd, int(o.start_ts), int(o.is_up))
            if k not in feeds:
                continue
            ts, ask = feeds[k]; A = o.m - 150
            i = np.searchsorted(ts, A - np.array(LAMS), "right") - 1
            ok = i >= 0
            v = np.where(ok, ask[np.clip(i, 0, len(ask) - 1)], np.nan)
            hits += np.isclose(v, o.a_seen); n += 1
        prof[f"{fd}|{w}"] = {"n": n, "p_match_by_lag": {str(l): round(float(h / max(n, 1)), 4) for l, h in zip(LAMS, hits)},
                             "peak_lag": LAMS[int(np.argmax(hits))], "peak": round(float(hits.max() / max(n, 1)), 4)}
res["profiles"] = prof
# discriminating subset: CLOB-only transients
sub = []; base = []
for o in cd.itertuples():
    kc, kp = ("clob", int(o.start_ts), int(o.is_up)), ("pb", int(o.start_ts), int(o.is_up))
    if kc not in feeds or kp not in feeds:
        continue
    tc, ac = feeds[kc]; tp, ap = feeds[kp]; A = o.m - 150
    inw = (tc >= A - 120) & (tc <= A - 10)
    if not inw.any():
        continue
    shown = set(np.round(ap[(tp >= A - 400) & (tp <= A + 100)], 2))
    cvals = set(np.round(ac[inw], 2))
    trans = cvals - shown
    if trans:
        sub.append({"wallet": o.wallet, "a_seen_in_trans": float(o.a_seen) in {round(v, 2) for v in trans}, "n_trans": len(trans), "n_cvals": len(cvals),
                    "a_seen_in_cvals": float(o.a_seen) in {round(v, 2) for v in cvals}, "a_seen_in_shown": float(o.a_seen) in {round(v, 2) for v in shown}})
sb = pd.DataFrame(sub)
if len(sb):
    res["transient_subset"] = {"orders": int(len(sb)), "a_seen_eq_clob_only_transient": round(float(sb.a_seen_in_trans.mean()), 4),
                               "a_seen_eq_any_clob_value_in_window": round(float(sb.a_seen_in_cvals.mean()), 4),
                               "a_seen_eq_pb_shown_value": round(float(sb.a_seen_in_shown.mean()), 4),
                               "expected_if_clob_reader_uniform_over_window_values": round(float((sb.a_seen_in_cvals * sb.n_trans / sb.n_cvals).mean()), 4),
                               "by_wallet": {w: [round(float(g.a_seen_in_trans.mean()), 4), int(len(g))] for w, g in sb.groupby("wallet")}}
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/pbview17.json", "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in res.items() if k != "profiles"}, indent=1, default=str))
for k, v in prof.items():
    if k.endswith("|ALL") or k.endswith("|DS"):
        print(k, v["n"], "peak", v["peak_lag"], v["peak"], {l: v["p_match_by_lag"][str(l)] for l in (0, 30, 60, 100, 150, 200, 250, 300)})
