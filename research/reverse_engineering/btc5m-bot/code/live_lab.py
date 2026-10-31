"""Iteration 5 (live lab, catalog A7 / B1 / B2): the cluster's orders against the RECORDED Polymarket book (tools/live.py
clob_crypto, development blocks only) and Chainlink RTDS.
Inputs: .cache/re/btc5m-bot/post/own_<a>_<b>.parquet (fetch_dev_post.py), calldata for those txs (calldata.py), live feeds.
For each cluster order fill: the matching-engine time (server ms of the recorded last-trade event with the same tx hash),
the signing time, and the recorded touch of the bought token just before the match.
Usage: python live_lab.py OWN_PARQUET CALLDATA_PARQUET START END"""
import os, sys, json, zlib, bisect
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live, sealed
C = _ROOT + "/.cache/re/btc5m-bot"
W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
ALLOW_SEALED = False


def recs(feed, a, b):
    """iter_live hour by hour, so that a broken gzip member in one hourly file (zlib.error, not caught by iter_live)
    only loses the rest of that file, not the following hours."""
    h = int(a // 3600) * 3600
    while h < b:
        lo, hi = max(a, h), min(b, h + 3600)
        try:
            for r in live.iter_live(feed, lo, hi, allow_sealed=ALLOW_SEALED):
                yield r
        except zlib.error:  # broken member / file being written: keep what was read
            pass
        h += 3600


def load_books(a, b):
    """Up-token touch series per BTC 5m market: dict up_token -> arrays (s_ms, bid, ask, bidsz, asksz); tokens map; trades."""
    tok = {}  # token -> (slug, start, is_up, up_token)
    for r in recs("subs", a - 3600, b):
        if r.get("feed") != "clob_crypto":
            continue
        for slug, tks in r["markets"].items():
            if slug.startswith("btc-updown-5m-"):
                st = int(slug.rsplit("-", 1)[1])
                tok[tks[0]] = (slug, st, True, tks[0]); tok[tks[1]] = (slug, st, False, tks[0])
    books = {}; trades = []
    for r in recs("clob_crypto", a, b):
        k = r.get("k")
        if k in ("q", "f"):
            t = r["a"]
            if t not in tok or not tok[t][2]:
                continue
            bb = max((p for p, z in r["b"]), default=np.nan); ba = min((p for p, z in r["o"]), default=np.nan)
            bz = sum(z for p, z in r["b"] if p == bb) if r["b"] else np.nan; az = sum(z for p, z in r["o"] if p == ba) if r["o"] else np.nan
            books.setdefault(t, []).append((r["s"], r["t"], bb, ba, bz, az))
        elif k == "x":
            t = r["a"]
            if t in tok:
                trades.append((r["s"], r["t"], t, r["p"], r["z"], r["d"], r["h"]))
    for t in books:
        arr = np.array(sorted(books[t]), dtype=float)
        books[t] = arr
    trades = pd.DataFrame(trades, columns=["s_ms", "t_ms", "token", "p", "z", "d", "tx"])
    return tok, books, trades


def touch_before(books, up_token, s_ms, is_up):
    arr = books.get(up_token)
    if arr is None or not len(arr):
        return (np.nan,) * 4
    i = np.searchsorted(arr[:, 0], s_ms, side="left") - 1  # last book record strictly before the match
    if i < 0:
        return (np.nan,) * 4
    _, _, bb, ba, bz, az = arr[i]
    age = s_ms - arr[i, 0]
    if is_up:
        return ba, bb, age, az
    return 1.0 - bb, 1.0 - ba, age, bz  # Down ask = 1 - Up bid


def main(own_path, cd_path, a, b):
    own = pd.read_parquet(own_path)
    own["wal"] = own.owner.map(W)
    cd = pd.read_parquet(cd_path)
    cd = cd[cd.role.isin(["T", "M"])]
    tok, books, trades = load_books(a, b)
    res = {"book_tokens": len(books), "book_records": int(sum(len(v) for v in books.values())), "trades_recorded": int(len(trades)),
           "rec_span": [float(min(v[0, 0] for v in books.values()) / 1000) if books else None, float(max(v[-1, 0] for v in books.values()) / 1000) if books else None]}
    # keep only development windows (start in a development interval) that the recorder covered
    own = own[own.token.isin(tok.keys())].copy()
    own["start_ts"] = own.token.map(lambda t: tok[t][1]); own["is_up"] = own.token.map(lambda t: tok[t][2]); own["up_token"] = own.token.map(lambda t: tok[t][3])
    own = own[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in own.start_ts], dtype=bool)]
    rec_end = res["rec_span"][1] or 0
    own = own[own.ts <= rec_end - 5]
    res["cluster_fills_in_recorded_dev_windows"] = int(len(own))
    # cluster orders in calldata (one row per (tx, order))
    cl = cd[cd.maker.isin(W.keys())].copy()
    cl["wal"] = cl.maker.map(W)
    cl["limit"] = np.where(cl.oside == 0, cl.maker_amt / cl.taker_amt, cl.taker_amt / cl.maker_amt)
    cl["size"] = np.where(cl.oside == 0, cl.taker_amt, cl.maker_amt)
    cl = cl[cl.tx.isin(own.tx)]
    cl = cl.merge(own.drop_duplicates("tx")[["tx", "ts", "start_ts"]], on="tx", how="left")
    cl["is_up"] = cl.token.map(lambda t: tok.get(t, (0, 0, np.nan))[2]); cl["up_token"] = cl.token.map(lambda t: tok.get(t, (0, 0, 0, None))[3])
    # match time from the recorded last-trade events with the same tx hash
    mt = trades.groupby("tx").agg(match_s=("s_ms", "min"), match_recv=("t_ms", "min"))
    cl = cl.merge(mt, left_on="tx", right_index=True, how="left")
    res["share_cluster_orders_with_match_time"] = float(cl.match_s.notna().mean())
    cl["sign_to_match"] = (cl.match_s - cl.sign_ms) / 1000.0
    cl["match_to_block"] = cl.ts - cl.match_s / 1000.0
    cl["recv_minus_server"] = (cl.match_recv - cl.match_s) / 1000.0
    for role in ("T", "M"):
        x = cl[cl.role == role]
        res[f"{role}_n"] = int(len(x))
        for c in ("sign_to_match", "match_to_block", "recv_minus_server"):
            v = x[c].dropna().to_numpy()
            if len(v):
                res[f"{role}_{c}_q"] = {str(k): round(float(np.quantile(v, k)), 3) for k in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)}
    # touch just before the match for taker orders
    tt = cl[(cl.role == "T") & cl.match_s.notna()].copy()
    vals = [touch_before(books, u, s, up) for u, s, up in zip(tt.up_token, tt.match_s, tt.is_up)]
    tt["ask"], tt["bid"], tt["book_age_ms"], tt["ask_sz"] = zip(*vals) if vals else ([], [], [], [])
    tt["lim_minus_ask"] = (tt["limit"] - tt["ask"]).round(4)
    res["T_limit_minus_ask_counts"] = {str(k): int(v) for k, v in tt.lim_minus_ask.value_counts().head(12).items()}
    res["T_limit_eq_ask_share"] = float((tt.lim_minus_ask.abs() < 1e-6).mean()) if len(tt) else None
    res["T_limit_within_tick_share"] = float((tt.lim_minus_ask.abs() <= 0.0100001).mean()) if len(tt) else None
    res["T_book_age_ms_q"] = {str(k): round(float(np.nanquantile(tt.book_age_ms, k)), 1) for k in (0.25, 0.5, 0.75, 0.9)} if len(tt) else None
    # touch at SIGNING time for taker orders: was the limit already the ask when it was signed?
    vals2 = [touch_before(books, u, s, up) for u, s, up in zip(tt.up_token, tt.sign_ms, tt.is_up)]
    tt["ask_sign"], tt["bid_sign"], tt["age_sign"], _ = zip(*vals2) if vals2 else ([], [], [], [])
    tt["lim_minus_ask_sign"] = (tt["limit"] - tt["ask_sign"]).round(4)
    res["T_limit_minus_ask_at_sign_counts"] = {str(k): int(v) for k, v in tt.lim_minus_ask_sign.value_counts().head(12).items()}
    res["T_limit_eq_ask_at_sign_share"] = float((tt.lim_minus_ask_sign.abs() < 1e-6).mean()) if len(tt) else None
    tt.to_parquet(C + "/live_lab_taker_orders.parquet")
    cl.to_parquet(C + "/live_lab_cluster_orders.parquet")
    return res


if __name__ == "__main__":
    own_path, cd_path, a, b = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    res = main(own_path, cd_path, a, b)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_live_lab_iter5.json")
    json.dump(res, open(out, "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:5000])
