"""Iteration 17 (new X177, first step): WHEN and WHERE does XM post its 60-share maker bids in the new regime? For every XM 60-share
maker-first order of 11-01 06:00-09:30 (mkx17_orders.parquet: limit L, outcome, signing ms, first fill), find its POSTING in the
recorded book: the first price change after signing on the level that holds it (Up bid at L for an Up order; Up ask at 1 - L for a
Down order, the mirrored complement bid) whose size rises by 60 +- 0.6, from the unthrottled near-touch channel btc5m_clob_raw2 'p'
records (server ms; only levels near the touch are recorded) and, when absent there, the shared recorder's clob_crypto top-10 levels
('q' / 'f', at most every 200 ms; a rise of >= 59.4 between snapshots). Reports: posting found share, posting time in the window and
after signing, the limit against the touch at posting (bid / ask of the bought outcome), time from posting to first fill, and for the
DS / GF 30-share maker-first orders the same, as a control. Usage: python post60_17.py"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live

S = os.environ["RE16_SCRATCH"] + "/it17"
o = pd.read_parquet(S + "/mkx17_orders.parquet")
win = pd.read_parquet(S + "/post17_windows.parquet")
a0, b0 = int(win.start_ts.min()) - 120, int(win.end_ts.max()) + 10
# near-touch channel: per window start m: arrays (s, side, price, size, bb, ba)
P = {}
for r in live.iter_live("btc5m_clob_raw2", a0, b0):
    if r.get("k") == "p":
        P.setdefault(int(r["m"]), []).append((r["s"], 1 if r["d"] == "B" else -1, round(float(r["p"]), 2), float(r["z"]), r.get("bb"), r.get("ba")))
P = {k: np.array([(a, b, c, d, np.nan if e is None else float(e), np.nan if f is None else float(f)) for a, b, c, d, e, f in v], float) for k, v in P.items()}
for k in P:
    P[k] = P[k][np.argsort(P[k][:, 0], kind="stable")]
# shared recorder top-10 snapshots of the Up token: per token list of (s, {price: size} bids, {price: size} asks)
upt = {str(t): int(s) for t, s in zip(win.up_token, win.start_ts)}
Q = {}
for r in live.iter_live("clob_crypto", a0, b0):
    if r.get("k") in ("q", "f") and str(r.get("a")) in upt:
        Q.setdefault(upt[str(r["a"])], []).append((r.get("s") or r["t"], {round(float(p), 2): float(z) for p, z in (r.get("b") or [])},
                                                     {round(float(p), 2): float(z) for p, z in (r.get("o") or [])}))
rows = []
for x in o.itertuples():
    st = int(x.start_ts); L = round(float(x.limit), 2)
    side, lvl = (1, L) if x.is_up else (-1, round(1 - L, 2))     # Up bid at L, or Up ask at 1 - L
    t_post, src, bb, ba = np.nan, None, np.nan, np.nan
    arr = P.get(st)
    if arr is not None:
        mk = (arr[:, 0] >= x.sign_ms) & (arr[:, 1] == side) & np.isclose(arr[:, 2], lvl)
        idx = np.where(mk)[0]
        prev = None
        # size before the first change after signing = last recorded size at that level before signing (else 0)
        pre = np.where((arr[:, 0] < x.sign_ms) & (arr[:, 1] == side) & np.isclose(arr[:, 2], lvl))[0]
        prev = arr[pre[-1], 3] if len(pre) else None
        for i in idx:
            z = arr[i, 3]
            if prev is not None and abs((z - prev) - x.orig) <= 0.6:
                t_post, src, bb, ba = arr[i, 0], "raw2", arr[i, 4], arr[i, 5]; break
            prev = z
    if np.isnan(t_post) and st in Q:
        snaps = Q[st]; prevz = None
        for (s_, bids, asks) in snaps:
            if s_ < x.sign_ms - 1000:
                prevz = (bids if side == 1 else asks).get(lvl, 0.0); continue
            z = (bids if side == 1 else asks).get(lvl, None)
            if z is not None and prevz is not None and z - prevz >= x.orig - 0.6:
                t_post, src = s_, "clob_crypto"
                bb = max(bids) if bids else np.nan; ba = min(asks) if asks else np.nan; break
            if z is not None:
                prevz = z
    # touch of the bought outcome at posting
    if x.is_up:
        ob, oa = bb, ba
    else:
        ob, oa = (1 - ba if ba == ba else np.nan), (1 - bb if bb == bb else np.nan)
    rows.append({"wallet": x.wallet, "orig": x.orig, "L": L, "is_up": x.is_up, "sign_rel": x.sign_rel, "post_rel": (t_post / 1000.0 - st) if t_post == t_post else np.nan,
                 "post_after_sign_s": (t_post - x.sign_ms) / 1000.0 if t_post == t_post else np.nan, "src": src,
                 "L_minus_bid_c": round((L - ob) * 100, 1) if ob == ob else np.nan, "ask_minus_L_c": round((oa - L) * 100, 1) if oa == oa else np.nan,
                 "post_to_fill_s": (x.first_fill_rel - (t_post / 1000.0 - st)) if t_post == t_post else np.nan})
R = pd.DataFrame(rows)
res = {}
for nm, g in (("XM60", R[(R.wallet == "XM") & (R.orig.round() == 60)]), ("DS30", R[(R.wallet == "DS") & (R.orig.round() == 30)]), ("GF30", R[(R.wallet == "GF") & (R.orig.round() == 30)])):
    f = g[g.post_rel.notna()]
    res[nm] = {"orders": int(len(g)), "posting_found": int(len(f)), "by_source": {str(k): int(v) for k, v in f.src.value_counts().items()}}
    if len(f):
        res[nm].update({"post_rel_q": [round(float(v), 1) for v in f.post_rel.quantile([0.1, 0.25, 0.5, 0.75, 0.9])],
                        "post_after_sign_s_q": [round(float(v), 1) for v in f.post_after_sign_s.quantile([0.1, 0.5, 0.9])],
                        "L_minus_bid_c_top": {str(k): int(v) for k, v in f.L_minus_bid_c.value_counts().head(8).items()},
                        "ask_minus_L_c_top": {str(k): int(v) for k, v in f.ask_minus_L_c.value_counts().head(8).items()},
                        "share_at_or_above_bid": round(float((f.L_minus_bid_c >= 0).mean()), 4),
                        "share_1c_below_ask": round(float((f.ask_minus_L_c == 1).mean()), 4),
                        "post_to_fill_s_q": [round(float(v), 1) for v in f.post_to_fill_s.quantile([0.1, 0.5, 0.9])]})
R.to_parquet(S + "/post60_17.parquet", index=False)
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/post60_17.json", "w"), indent=1)
print(json.dumps(res, indent=1))
