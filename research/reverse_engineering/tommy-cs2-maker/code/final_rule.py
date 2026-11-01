"""tommy-cs2-maker frozen rule v5 (`tommy-v5-grid-league-dota-groupP`, iteration 9, 2026-11-01) = v4 with the selection score
combined with group-P coverage (X127, adopted under the criterion pre-registered in NOTES iteration 9): score =
logistic(a * logit(v4 score) + b * log1p(gp72) + c), gp72 = distinct members of group P (P4e, 0x2005d16a and the slow trio,
fixed on BUILD; final_rule_v5_groupP.json) with a public taker print in another event of the same league that started in
the previous 72 h, prints stamped before the event's game start (point-in-time, wallet-independent); threshold = 20th
percentile of the fitted positives. In development runs (ALLOW_SEALED False) earlier events that started in a sealed
period are skipped, so gp72 is under-counted on forward development blocks; the examiner counts every earlier event.
Every other component is v4's.

v4 docstring follows.
tommy-cs2-maker frozen rule v4 (`tommy-v4-grid-league-dota`, iteration 8, 2026-11-01) = v3 (`tommy-v3-grid-league-upstream`,
iteration 3) with the rule universe widened to Dota 2 (Gamma series 10309: the wallet's Dota module since 10-22 is 15-54%
of its fills) and scope item 1 computed on the lot (`coverage_fills`, `coverage_abs_pnl` from `_coverage()`). The Dota 2
league table (`final_rule_v4_dota.json`) uses the v3 recipe on the same periods; every CS2 constant is unchanged.

Selection constants are unchanged from v2 (final_rule_v2_constants.json):
  "build": fitted on BUILD (gameStart 2026-10-16 .. 10-21), used for the VALIDATE numbers in state.json;
  "exam":  refitted on all development data (10-16 .. 10-23) with the same recipe; used by evaluate() (CONSTANTS).

Iteration-3 changes: (1) the v2 taker book trigger is RETRACTED: it read the recorder's laptop receive clock, which
runs 0.9-1.4 s behind the CLOB server; on the server clock the cancel wave starts a median 51 ms AFTER the wallet signs.
evaluate() now reports a server-clock diagnostic (live_taker_diagnostic_server_clock) and makes no taker-timing claim.
(2) price_within_tick uses the in-play tick (0.01 for mid-range prices). (3) size rule: CS2 100 shares, Dota 2 10.

Components (tags in FINAL_RULE.md):
  selection  unit = CS2 event (all its match / map-winner markets). s_lg = 0 if the event has a GRID series id
             (eventMetadata.gridSeriesId), else the league rate among fitted non-GRID events shrunk (k=3) toward the
             tier rate. score = logistic(log1p pre-game taker prints, USD, distinct wallets in [gs-1h, gs) summed over
             the event's markets; s_lg). Trade the event iff score >= thr (thr = 20th percentile of the fitted
             positives' scores, i.e. fitted recall 0.8).
  timing     maker: quotes from game start (in-play only). taker: NOT decoded; its decisions precede every public
             Polymarket trace (book, trades, sports socket) on the server clock: an unobserved in-round game feed.
  side       maker: both outcomes. taker: the team that just gained in-round (from the unobserved feed).
  price      maker: BUY near the best bid, whole cents (the in-play tick), ladder 1c apart; taker: FAK at best ask + 0-2c.
  size       maker 100 shares in CS2 markets, 10 shares in Dota 2 markets; taker variable (not decoded).
  exit       never sells; merge pairs; hold the residual.

evaluate(start_ts, end_ts, intervals=None) -> dict (one wallet: per wallet = pooled). Units = events whose earliest
gameStartTime lies in an interval. Live inputs (books) come from iter_live(..., allow_sealed=ALLOW_SEALED); they exist
only from 2026-10-31 on, so the taker-trigger metric is None on the historical lots.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))

ALLOW_SEALED = False
CONSTANTS = "exam"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
H = 1792713600
CACHE = ROOT / ".cache/re/tommy-cs2-maker"
CALL = json.load(open(HERE / "final_rule_v2_constants.json"))
# v4 (iteration 8, X112): Dota 2 league table fitted with the v3 recipe on the same periods (build: 10-16..10-20,
# exam: 10-16..H); the CS2 coefficients, prior, tier rates and threshold are unchanged.
DOTA = json.load(open(HERE / "final_rule_v4_dota.json"))
SERIES = ("10310", "10309")
BIN, NB, INPLAY_MIN = 30, 480, 210
COL_FRAC, COL_MINREF, COL_BIN = 0.5, 200, 500
ACT = ["n", "v", "w"]


def _auc(score, y) -> float:
    from scipy.stats import rankdata
    s = np.asarray(score, float)
    y = np.asarray(y).astype(bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _in(ts, iv):
    ts = np.asarray(ts, float)
    m = np.zeros(len(ts), bool)
    for a, b in iv:
        m |= (ts >= a) & (ts < b)
    return m


def _gs(s):
    s = str(s)
    if s.endswith("+00"):
        s += ":00"
    try:
        return pd.Timestamp(s).tz_convert("UTC").timestamp() if pd.Timestamp(s).tzinfo else pd.Timestamp(s, tz="UTC").timestamp()
    except Exception:  # noqa: BLE001
        return np.nan


def _universe(start, end, iv) -> pd.DataFrame:
    """Market rows (listing projection only): event, league, tier, grid id, cid, smt, gs_ts, tokens, outcomes."""
    if end <= H and (CACHE / "universe.parquet").exists():
        u = pd.read_parquet(CACHE / "universe.parquet")
        em = pd.read_parquet(CACHE / "events_meta.parquet")[["event_slug", "grid_series_id"]]
        u = u.merge(em, on="event_slug", how="left")
        u["series"] = "10310"
        if (CACHE / "universe_dota.parquet").exists():  # v4 (iteration 8, X112): Dota 2 universe (series 10309)
            ud = pd.read_parquet(CACHE / "universe_dota.parquet")
            ud = ud[pd.to_numeric(ud["gs_ts"], errors="coerce") < H]
            u = pd.concat([u, ud[[c for c in ud.columns if c in set(u.columns) | {"grid_series_id", "series"}]]],
                          ignore_index=True)
    else:
        from polyrea.adapters.http import shared_client
        h = shared_client()
        rows = []
        lo = pd.Timestamp(start - 20 * 86400, unit="s").strftime("%Y-%m-%dT%H:%M:%SZ")
        hi = pd.Timestamp(end, unit="s").strftime("%Y-%m-%dT%H:%M:%SZ")
        for series in SERIES:  # v4: CS2 (10310) and Dota 2 (10309)
            off = 0
            while True:
                d, _ = h.get_json("https://gamma-api.polymarket.com/events", {"series_id": series, "start_date_min": lo,
                                  "start_date_max": hi, "limit": 100, "offset": off}, adapter="gamma.events", max_age=3600)
                if not d:
                    break
                for e in d:
                    meta = e.get("eventMetadata") or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:  # noqa: BLE001
                            meta = {}
                    for m in e.get("markets") or []:
                        rows.append({"series": series, "event_slug": e.get("slug"), "league": meta.get("league"),
                                     "league_tier": meta.get("leagueTier"), "grid_series_id": meta.get("gridSeriesId"),
                                     "cid": m.get("conditionId"), "smt": m.get("sportsMarketType"),
                                     "game_start": m.get("gameStartTime"), "tokens": m.get("clobTokenIds"),
                                     "outcomes": m.get("outcomes")})
                if len(d) < 100:
                    break
                off += 100
        u = pd.DataFrame(rows).drop_duplicates("cid")
        u["gs_ts"] = u["game_start"].map(_gs)
    u = u[u["smt"].isin(["moneyline", "child_moneyline"])].copy()
    u["gs_ts"] = pd.to_numeric(u["gs_ts"], errors="coerce")
    u = u[u["gs_ts"].notna()]
    u["gs_ts"] = u["gs_ts"].astype("int64")
    egs = u.groupby("event_slug")["gs_ts"].transform("min")
    return u[_in(egs.to_numpy(), iv)].reset_index(drop=True)


def _tape(cid, gs, end) -> pd.DataFrame:
    p = CACHE / "tapes" / f"{cid}_tkw.parquet"
    if p.exists() and end <= H:
        return pd.read_parquet(p)
    from polyrea.adapters.polymarket import PolymarketData
    rows, _, _ = PolymarketData().market_trades(cid, start=gs - 3600, end=int(min(gs + 4 * 3600 + 600, end) - 1), taker_only=True)
    return pd.DataFrame(rows)


def _wallet_fills(u, end) -> pd.DataFrame:
    """Wallet fills in the universe: cid, oi, shares, usdc, bts, tx, role, sign_ms, price (decoded calldata)."""
    cids = set(u["cid"])
    if end <= H and (CACHE / "calldata_all.parquet").exists():
        cd = pd.read_parquet(CACHE / "calldata_all.parquet")
        cd = cd[(cd["maker"] == WALLET) & cd["cid"].isin(cids)].copy()
        cd["role"] = np.where(cd["idx"] == -1, "taker", "maker")
        cd["usdc"] = cd["fill"] * cd["price"]
        return cd
    import httpx
    from polyrea.adapters.polymarket import PolymarketData
    from fetch_calldata import rows_of
    pm = PolymarketData()
    txs = []
    for r in u.itertuples():
        rows, _, _ = pm.market_trades(r.cid, start=int(r.gs_ts) - 6 * 3600, end=int(end) - 1, taker_only=False)
        txs += [x["transactionHash"] for x in rows if str(x.get("proxyWallet", "")).lower() == WALLET]
    txs = sorted(set(txs))
    recs = []
    cli = httpx.Client(timeout=40)
    for i in range(0, len(txs), 40):
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(txs[i:i + 40])]
        for x in cli.post("https://polygon-bor-rpc.publicnode.com", json=body).json():
            if x.get("result"):
                recs += rows_of(x["result"])
    cd = pd.DataFrame(recs)
    if cd.empty:
        return cd
    tok = {}
    for r in u.itertuples():
        t = json.loads(r.tokens) if isinstance(r.tokens, str) else r.tokens
        for i, x in enumerate(t or []):
            tok[str(x)] = (r.cid, i)
    cd["cid"] = cd["token_id"].map(lambda t: tok.get(str(t), (None,))[0])
    cd["oi"] = cd["token_id"].map(lambda t: tok.get(str(t), (None, -1))[1])
    cd = cd[(cd["maker"] == WALLET) & cd["cid"].notna()].copy()
    cd["bts"] = cd["sign_ms"] / 1000 + 3.0
    cd["role"] = np.where(cd["idx"] == -1, "taker", "maker")
    cd["usdc"] = cd["fill"] * cd["price"]
    return cd


def _payouts(u, end) -> dict:
    """Outcome-0 payout per market, settlement only (never a feature)."""
    out = {}
    if end <= H and "res_outcome_prices" in u:
        for cid, r in zip(u["cid"], u["res_outcome_prices"]):
            try:
                out[cid] = float(json.loads(r)[0])
            except Exception:  # noqa: BLE001
                pass
        return out
    from polyrea.adapters.polymarket import PolymarketData
    mk, _ = PolymarketData().markets_by_condition(sorted(u["cid"]))
    for cid, x in mk.items():
        try:
            out[cid] = float(json.loads(x.get("outcomePrices"))[0])
        except Exception:  # noqa: BLE001
            pass
    return out


def selection_score(ev: pd.DataFrame, C: dict) -> np.ndarray:
    tier = ev["tier"].astype(str).str.replace(r"\.0$", "", regex=True)
    tr = tier.map(C["tier_rate"]).fillna(C["prior"]).astype(float)
    s = ev["league"].map(C["league_sum"]).fillna(0).astype(float)
    n = ev["league"].map(C["league_n"]).fillna(0).astype(float)
    slg = np.where(ev["grid"].to_numpy(), 0.0, ((s + C["k"] * tr) / (n + C["k"])).to_numpy())
    X = np.column_stack([np.log1p(ev[c].fillna(0).to_numpy(float)) for c in ACT] + [slg])
    z = X @ np.array(C["coef"]) + C["icpt"]
    return 1 / (1 + np.exp(-z))


V5 = json.load(open(HERE / "final_rule_v5_groupP.json"))  # v5 (iteration 9, X127): group-P coverage constants
V5_MEMBERS = set(V5["members"])  # fixed on BUILD: P4e, 0x2005d16a and the slow trio (<= 2% of BUILD prints in GRID events)


def _gp72(ev: pd.DataFrame, u: pd.DataFrame, tapes: dict, start: float, end: float, iv) -> np.ndarray:
    """v5 feature (point-in-time, wallet-independent): distinct group-P members with a taker print in ANOTHER event of
    the same league whose game start lies in [gs - 72 h, gs), prints stamped before gs. Earlier events come from the
    listing (projection) and their public taker tapes; in development runs (ALLOW_SEALED False) events that started in a
    sealed period are skipped (never loaded)."""
    hrs = 3600 * V5.get("hours", 72)
    lo, hi = min(a for a, _ in iv), max(b for _, b in iv)
    try:
        ux = _universe(lo - hrs, hi, [(lo - hrs, hi)])
    except Exception:  # noqa: BLE001
        ux = u
    egs = ux.groupby("event_slug")["gs_ts"].transform("min")
    ux = ux.assign(egs=egs.to_numpy())
    if not ALLOW_SEALED:
        try:
            import sealed as _sealed
            keep = [not _sealed.is_sealed(float(g), "tommy-cs2-maker") if g >= H else True for g in ux["egs"]]
            ux = ux[np.array(keep, bool)]
        except Exception:  # noqa: BLE001
            ux = ux[ux["egs"] < H]
    pr = {}  # event -> list of (member, ts)
    for r in ux.itertuples():
        d = tapes.get(r.cid)
        if d is None:
            try:
                d = _tape(r.cid, int(r.gs_ts), end)
            except Exception:  # noqa: BLE001
                d = None
        if d is None or len(d) == 0 or "proxyWallet" not in d:
            continue
        w = d["proxyWallet"].astype(str).str.lower()
        m = w.isin(V5_MEMBERS)
        if m.any():
            pr.setdefault(r.event_slug, []).extend(zip(w[m], d["timestamp"].astype("int64")[m]))
    eg = ux.groupby("event_slug").agg(gs=("egs", "min"), league=("league", "first")).reset_index()
    by_lg = {lg: g for lg, g in eg.groupby("league")}
    out = []
    for r in ev.itertuples():
        g = by_lg.get(r.league)
        ss = set()
        if g is not None:
            prev = g[(g["gs"] >= r.gs - hrs) & (g["gs"] < r.gs) & (g["event_slug"] != r.event_slug)]
            for e2 in prev["event_slug"]:
                ss |= {w_ for w_, t in pr.get(e2, []) if t < r.gs}
        out.append(len(ss))
    return np.array(out, float)


def selection_score_v5(ev: pd.DataFrame, C: dict, gp: np.ndarray) -> np.ndarray:
    s = np.clip(selection_score(ev, C), 1e-6, 1 - 1e-6)
    P = V5[CONSTANTS]
    z = P["coef"][0] * np.log(s / (1 - s)) + P["coef"][1] * np.log1p(gp) + P["icpt"]
    return 1 / (1 + np.exp(-z))


def activity_baseline(ev: pd.DataFrame, C: dict) -> np.ndarray:
    X = np.column_stack([np.log1p(ev[c].fillna(0).to_numpy(float)) for c in ACT])
    return X @ np.array(C["act_coef"]) + C["act_icpt"]


def _replay(d, gs, pay0, delta=0.0, levels=1, req=10, lat=2, size=100.0):
    """Executable two-sided ladder on the public taker tape (strict trade-through fills); per-market settlement PnL."""
    if d is None or len(d) < 5:
        return 0.0
    ts = d["timestamp"].to_numpy(float)
    oi = d["outcomeIndex"].astype(int).to_numpy()
    side = d["side"].to_numpy()
    pr = d["price"].astype(float).to_numpy()
    sz = d["size"].astype(float).to_numpy()
    p0 = np.where(oi == 0, pr, 1 - pr)
    sh, cost = np.zeros(2), 0.0
    for t0 in np.arange(max(gs, ts[0]), ts[-1], req):
        k = np.searchsorted(ts, t0 - lat, side="right") - 1
        lo, hi = np.searchsorted(ts, t0, side="right"), np.searchsorted(ts, t0 + req, side="right")
        if k < 0 or hi <= lo:
            continue
        for o, fair in ((0, p0[k]), (1, 1 - p0[k])):
            top = np.floor((fair - delta) * 100 + 1e-9) / 100
            for lv in range(levels):
                q = round(top - 0.01 * lv, 2)
                if q < 0.01 or q > 0.99:
                    continue
                m = slice(lo, hi)
                thr = ((oi[m] == o) & (side[m] == "SELL") & (pr[m] < q - 1e-9)) | ((oi[m] != o) & (side[m] == "BUY") & (pr[m] > 1 - q + 1e-9))
                f = min(size, float(sz[m][thr].sum()))
                if f > 0:
                    sh[o] += f
                    cost += f * q
    return float(sh[0] * pay0 + sh[1] * (1 - pay0) - cost)


def _live_diag(u, fills, iv) -> dict | None:
    """Iteration-3 replacement of the v2 book trigger (which was a receive-clock artefact). Diagnostic only, no
    decision rule: on the CLOB SERVER clock (record field s), for each wallet taker order with a recorded book, is
    there a near-touch depth collapse on the consumed side in [sign - 2 s, sign] (before its decision) or in
    (sign, sign + 1.1 s] (during its 1-s in-play delay)? Random-time control on the same books. Also the wallet's
    clock calibration: server match time (first x record of its tx) minus sign_ms."""
    try:
        import live
    except Exception:  # noqa: BLE001
        return None
    tok0, team_of = {}, {}
    for r in u.itertuples():
        t = json.loads(r.tokens) if isinstance(r.tokens, str) else r.tokens
        if t and len(t) == 2:
            tok0[str(t[0])] = r.cid
            team_of[str(t[0])] = (r.cid, 0)
            team_of[str(t[1])] = (r.cid, 1)
    if not tok0 or not len(fills):
        return None
    lo, hi = min(a for a, b in iv), max(b for a, b in iv) + 5 * 3600

    def near(L, side):
        if not L:
            return 0.0
        if side == "o":
            b = min(L)
            return sum(z for p, z in L.items() if p <= b + 0.03 + 1e-9)
        b = max(L)
        return sum(z for p, z in L.items() if p >= b - 0.03 - 1e-9)

    ser, xs = {}, {}
    own_first = {}
    for feed in ("tommy_cs2_near", "clob_wallets"):
        state = {}
        h = int(lo // 3600 * 3600)
        while h < hi:
            try:
                for r in live.iter_live(feed, h, min(h + 3600, hi), allow_sealed=ALLOW_SEALED):
                    a = r.get("a")
                    if a not in tok0 or "s" not in r:
                        continue
                    k = r.get("k")
                    if k == "x":
                        xs.setdefault(((r.get("h") or "").lower(), a), r["s"])
                        continue
                    if feed == "clob_wallets" and r["s"] >= own_first.get(a, 1e18):
                        continue
                    if k in ("q", "f"):
                        b = {float(p): float(z) for p, z in (r.get("b") or [])}
                        o = {float(p): float(z) for p, z in (r.get("o") or [])}
                        state[a] = (b, o)
                    elif k == "pc" and a in state:
                        bd, od = state[a]
                        for sd, p, z in r.get("c") or []:
                            book = bd if sd == "BUY" else od
                            if float(z) == 0:
                                book.pop(float(p), None)
                            else:
                                book[float(p)] = float(z)
                    else:
                        continue
                    bd, od = state[a]
                    ser.setdefault(a, []).append((r["s"], near(bd, "b"), near(od, "o")))
                    if feed == "tommy_cs2_near":
                        own_first[a] = min(own_first.get(a, r["s"]), r["s"])
            except Exception:  # noqa: BLE001  (damaged hour member: keep what was read)
                pass
            h += 3600
    if not ser:
        return None
    tr = {}
    for (hsh, a), s in xs.items():
        tr.setdefault(a, []).append(s)
    tr = {a: np.sort(np.array(v, float)) for a, v in tr.items()}

    def events(S, D, trs):
        ev, last = [], -1e18
        for i in range(len(S)):
            l1, h1 = np.searchsorted(S, S[i] - 1500), np.searchsorted(S, S[i] - 400, side="right")
            if h1 <= l1:
                continue
            ref = D[l1:h1].max()
            if ref < COL_MINREF or D[i] > COL_FRAC * ref:
                continue
            k = np.searchsorted(trs, S[i] - 1500)
            if k < len(trs) and trs[k] <= S[i]:
                continue
            if S[i] - last < 3000:
                continue
            last = S[i]
            ev.append(S[i])
        return np.array(ev)

    evt = {}
    for a, rows in ser.items():
        x = np.array(sorted(rows))
        S = x[:, 0]
        for team, col in ((0, 2), (1, 1)):
            evt[(tok0[a], team)] = (events(S, x[:, col], tr.get(a, np.array([]))), S)
    tk = fills[fills["role"] == "taker"].drop_duplicates("tx")
    pre, post, cal = [], [], []
    for r in tk.itertuples():
        team = r.oi if r.side == 0 else 1 - r.oi
        e, S = evt.get((r.cid, team), (None, None))
        if e is None or len(S) == 0 or r.sign_ms < S[0] + 2000 or r.sign_ms > S[-1]:
            continue
        pre.append(bool(((e >= r.sign_ms - 2000) & (e <= r.sign_ms)).any()))
        post.append(bool(((e > r.sign_ms) & (e <= r.sign_ms + 1100)).any()))
    for r in tk.itertuples():
        for (hsh, a), s in ((k_, v_) for k_, v_ in xs.items() if k_[0] == str(r.tx).lower()):
            cal.append(s - r.sign_ms)
            break
    rng = np.random.default_rng(7)
    ctrl = []
    for (cid, team), (e, S) in evt.items():
        if len(S) < 10:
            continue
        for t in rng.uniform(S[0] + 2000, S[-1], 200):
            ctrl.append(bool(((e >= t - 2000) & (e <= t)).any()))
    return {"taker_orders_with_book": len(pre),
            "collapse_in_2s_before_sign": round(float(np.mean(pre)), 3) if pre else None,
            "collapse_in_1.1s_after_sign": round(float(np.mean(post)), 3) if post else None,
            "random_time_collapse_in_prior_2s": round(float(np.mean(ctrl)), 3) if ctrl else None,
            "match_minus_sign_ms_p10_p50_p90": [int(np.percentile(cal, q)) for q in (10, 50, 90)] if len(cal) >= 3 else None}


LIVE_VIEW_MS = 100.0   # frozen (iteration 6): the book is read 100 ms before the order's signing
PAIR_CAP = 0.99        # frozen (iteration 6): own pair sum cap (own top bid token 0 + own top bid token 1), joint_quote.json
# iteration 7 re-freeze (before any 11-01 06-12 record exists): the size fingerprint behind "own levels removed" is
# 76.5% precise on calldata-linked adds (single 100-share adds 51%); with a validated label the join scores 0.419, the
# plain touch (full-book best bid) 0.471 on the same 172 BUILD-live orders. Primary live price = the touch.
LIVE_PRICE_PRIMARY = "touch"


def _live_price(u, fills, iv) -> dict | None:
    """Iteration 6, frozen live price rule for the future-block lots (the historical lots have no books).

    For every maker order of the wallet (calldata; one row per order) whose market's token-0 book was recorded
    (tommy_cs2_near, else clob_wallets; read through iter_live with ALLOW_SEALED), on the CLOB server clock:
      others' best bid on the order's token at sign_ms - LIVE_VIEW_MS, with the wallet's own levels removed by
      fingerprint (whole-cent level changes whose size equals one of its maker order sizes in that market; own amount
      capped by the level size);  rule J = that price;  rule JC = min(J, PAIR_CAP - its own top bid on the other
      token) when it has one. Token 1 bids are the SELL side of the token-0 book at 1 - p.
    Reports the share within one in-play tick (0.01; 0.001 near 0 / 1) for J, JC and the last trade price on the same
    rows. Own levels are the wallet's own book (declared own state) and are used only to remove its orders."""
    try:
        import live
    except Exception:  # noqa: BLE001
        return None
    if not len(fills):
        return None
    tok = {}
    for r in u.itertuples():
        t = json.loads(r.tokens) if isinstance(r.tokens, str) else r.tokens
        if t and len(t) == 2:
            tok[r.cid] = (str(t[0]), str(t[1]))
    mo = fills[(fills["role"] == "maker") & fills["cid"].isin(tok)].copy()
    if "salt" in mo:
        mo = mo.drop_duplicates(["salt", "sign_ms"])
    mo = mo[(mo["sign_ms"] > 1.7e12) & (mo["sign_ms"] < 1.8e12)]
    if mo.empty:
        return None
    sizes = {c: set(np.round(g["shares"].astype(float).to_numpy(), 2)) | {100.0} for c, g in mo.groupby("cid")}
    a2c = {v[0]: c for c, v in tok.items()}
    q = {}
    for r in mo.itertuples():
        q.setdefault(tok[r.cid][0], []).append((float(r.sign_ms) - LIVE_VIEW_MS, int(r.oi), round(float(r.price), 3)))
    for a in q:
        q[a].sort()
    lo, hi = min(a for a, b in iv), max(b for a, b in iv) + 5 * 3600
    rows = []
    seen_tok = set()
    for feed in ("tommy_cs2_near", "clob_wallets"):
        need = {a for a in q if a not in seen_tok}
        if not need:
            break
        st = {}
        qi = {a: 0 for a in need}
        last_trade = {}
        h = int(lo // 3600 * 3600)

        def answer(a, upto):
            b, o, ob, oo = st[a]
            qa = q[a]
            while qi[a] < len(qa) and qa[qi[a]][0] < upto:
                t, oi, price = qa[qi[a]]
                qi[a] += 1
                if oi == 0:
                    oth = [p for p, z in b.items() if z - ob.get(p, 0.0) > 0.5]
                    J = max(oth) if oth else None
                    own_other = [p for p, z in oo.items() if z > 0.5]
                    other_top = (1 - min(own_other)) if own_other else None
                else:
                    oth = [p for p, z in o.items() if z - oo.get(p, 0.0) > 0.5]
                    J = (1 - min(oth)) if oth else None
                    own_other = [p for p, z in ob.items() if z > 0.5]
                    other_top = max(own_other) if own_other else None
                # iteration 7 (re-frozen before any VALIDATE-live record exists): the touch = full-book best bid on the
                # order's token (own levels included, no attribution needed); BUILD-live 0.471 vs join 0.424
                TB = (max(b) if b else None) if oi == 0 else ((1 - min(o)) if o else None)
                if J is None and TB is None:
                    continue
                JC = None if J is None else (min(J, PAIR_CAP - other_top) if other_top is not None else J)
                lt = last_trade.get(a)
                lt = None if lt is None else (lt if oi == 0 else 1 - lt)
                rows.append((None if J is None else round(J, 3), None if JC is None else round(JC, 3), lt, price,
                             None if TB is None else round(TB, 3)))

        while h < hi:
            try:
                for r in live.iter_live(feed, h, min(h + 3600, hi), allow_sealed=ALLOW_SEALED):
                    a = r.get("a")
                    if a not in need or "s" not in r:
                        continue
                    s = float(r["s"])
                    if a in st:
                        answer(a, s)
                    k = r.get("k")
                    if k == "x":
                        try:
                            last_trade[a] = float(r.get("p"))  # token-0 book: token-0 price
                        except Exception:  # noqa: BLE001
                            pass
                        continue
                    own_sz = sizes.get(a2c.get(a), {100.0})
                    if k in ("q", "f"):
                        b = {float(p): float(z) for p, z in (r.get("b") or [])}
                        o = {float(p): float(z) for p, z in (r.get("o") or [])}
                        ob = {p: min(v, b.get(p, 0.0)) for p, v in (st[a][2].items() if a in st else [])}
                        oo = {p: min(v, o.get(p, 0.0)) for p, v in (st[a][3].items() if a in st else [])}
                        st[a] = (b, o, ob, oo)
                        seen_tok.add(a)
                    elif k == "pc" and a in st:
                        b, o, ob, oo = st[a]
                        for sd, p, z in r.get("c") or []:
                            p, z = float(p), float(z)
                            book, own = (b, ob) if sd == "BUY" else (o, oo)
                            d = z - book.get(p, 0.0)
                            whole = abs(p * 100 - round(p * 100)) < 1e-6
                            if whole and round(abs(d), 2) in own_sz:
                                own[p] = own.get(p, 0.0) + d if d > 0 else max(0.0, own.get(p, 0.0) + d)
                            if z == 0:
                                book.pop(p, None)
                            else:
                                book[p] = z
                            if p in own:
                                own[p] = min(own[p], book.get(p, 0.0))
            except Exception:  # noqa: BLE001  (damaged hour member: keep what was read)
                pass
            h += 3600
        for a in need:
            if a in st:
                answer(a, 1e18)
    if not rows:
        return {"n_orders": 0}
    R = pd.DataFrame(rows, columns=["J", "JC", "lt", "p", "TB"])
    for c_ in ("J", "JC", "lt", "TB"):
        R[c_] = pd.to_numeric(R[c_], errors="coerce")

    def wt(pred):
        ok = pred.notna()
        x, pp = R.loc[ok, "p"].to_numpy(float), pred[ok].to_numpy(float)
        tick = np.where((pp >= 0.04) & (pp <= 0.96), 0.01, 0.001)
        return round(float((np.abs(x - pp) <= tick + 1e-9).mean()), 3) if ok.any() else None

    return {"n_orders": int(len(R)), "price_within_tick_live_join": wt(R["J"]),
            "price_within_tick_live_join_capped": wt(R["JC"]), "price_within_tick_live_last_trade": wt(R["lt"]),
            "price_within_tick_live_touch": wt(R["TB"]),
            "exact_live_join": round(float((np.abs(R["p"] - R["J"].astype(float)) <= 0.0001)[R["J"].notna()].mean()), 3),
            "n_orders_join": int(R["J"].notna().sum()),
            "exact_live_touch": round(float((np.abs(R["p"] - R["TB"].astype(float)) <= 0.0001)[R["TB"].notna()].mean()), 3) if R["TB"].notna().any() else None,
            "primary": LIVE_PRICE_PRIMARY, "view_ms": LIVE_VIEW_MS, "pair_cap": PAIR_CAP}


def _live_trigger(u, fills, iv) -> dict | None:
    """RETRACTED in iteration 3 (kept for the record, not called): v2 taker presence on recorded books indexed by the
    laptop's receive time t, which runs 0.9-1.4 s behind the CLOB server; on the server clock the collapse follows the
    wallet's signing (median wave onset +51 ms), so S_col read the future."""
    try:
        import live
    except Exception:  # noqa: BLE001
        return None
    tok0, team_of = {}, {}
    for r in u.itertuples():
        t = json.loads(r.tokens) if isinstance(r.tokens, str) else r.tokens
        if t and len(t) == 2:
            tok0[str(t[0])] = r.cid
            team_of[str(t[0])] = (r.cid, 0)
            team_of[str(t[1])] = (r.cid, 1)
    if not tok0:
        return None
    lo, hi = min(a for a, b in iv), max(b for a, b in iv) + 5 * 3600

    def summ(b, o):
        bb = max((p for p, z in b), default=np.nan)
        ba = min((p for p, z in o), default=np.nan)
        return bb, ba, sum(z for p, z in b if p >= bb - 0.03 - 1e-9), sum(z for p, z in o if p <= ba + 0.03 + 1e-9)

    per_feed = {}
    for feed in ("tommy_cs2_near", "tommy_cs2_books", "clob_wallets"):
        recs, trades = [], []
        state = {}  # own recorder: rebuild books from snapshots ("f") and price changes ("pc"), throttled to 100 ms
        last_emit = {}
        h = int(lo // 3600 * 3600)
        while h < hi:
            try:
                for r in live.iter_live(feed, h, min(h + 3600, hi), allow_sealed=ALLOW_SEALED):
                    a = r.get("a")
                    if a not in tok0:
                        continue
                    k = r.get("k")
                    if k in ("q", "f"):
                        b = [(float(p), float(z)) for p, z in (r.get("b") or [])]
                        o = [(float(p), float(z)) for p, z in (r.get("o") or [])]
                        if feed != "clob_wallets":
                            state[a] = ({p: z for p, z in b}, {p: z for p, z in o})
                        recs.append((r["t"], a, *summ(b, o)))
                    elif k == "pc" and a in state:
                        bd, od = state[a]
                        for sd, p, z in r.get("c") or []:
                            book = bd if sd == "BUY" else od
                            if float(z) == 0:
                                book.pop(float(p), None)
                            else:
                                book[float(p)] = float(z)
                        if r["t"] - last_emit.get(a, 0) >= 100:
                            recs.append((r["t"], a, *summ(list(bd.items()), list(od.items()))))
                            last_emit[a] = r["t"]
                    elif k == "x":
                        trades.append((r["t"], a, float(r.get("z") or 0)))
            except Exception:  # noqa: BLE001
                pass
            h += 3600
        per_feed[feed] = (recs, trades)
    # per token: use the own all-market recorder where it has data, else the shared recorder
    own_recs = per_feed["tommy_cs2_near"][0] + per_feed["tommy_cs2_books"][0]
    own_trades = per_feed["tommy_cs2_near"][1] + per_feed["tommy_cs2_books"][1]
    own_first = {}
    for t_, a_, *_ in own_recs:
        own_first[a_] = min(own_first.get(a_, t_), t_)
    recs = own_recs + [x for x in per_feed["clob_wallets"][0] if x[0] < own_first.get(x[1], 1e18)]
    trades = own_trades + [x for x in per_feed["clob_wallets"][1] if x[0] < own_first.get(x[1], 1e18)]
    if not recs:
        return None
    bk = pd.DataFrame(recs, columns=["t", "a", "bb", "ba", "Db", "Do"]).sort_values("t")
    tr = pd.DataFrame(trades, columns=["t", "a", "z"]).sort_values("t")
    tk = fills[fills["role"] == "taker"] if len(fills) else fills
    rows = []
    for a_, b in bk.groupby("a"):
        tt = b["t"].to_numpy()
        if len(tt) < 50:
            continue
        trt = tr[tr["a"] == a_]["t"].to_numpy()
        trz = tr[tr["a"] == a_]["z"].to_numpy()
        bins = np.arange(tt[0] + 2000, tt[-1], COL_BIN)
        j = np.searchsorted(tt, bins, side="right") - 1
        l1 = np.searchsorted(tt, bins - 1500)
        h1 = np.searchsorted(tt, bins - 400, side="right")
        n2 = np.searchsorted(trt, bins) - np.searchsorted(trt, bins - 2000)
        n10 = np.searchsorted(trt, bins) - np.searchsorted(trt, bins - 10000)
        cz = np.concatenate([[0], np.cumsum(trz)])
        z10 = cz[np.searchsorted(trt, bins)] - cz[np.searchsorted(trt, bins - 10000)]
        notr = (np.searchsorted(trt, bins) - np.searchsorted(trt, bins - 1500)) == 0
        cid = tok0[a_]
        for col, team in (("Do", 0), ("Db", 1)):
            D = b[col].to_numpy()
            ref = np.array([D[x:y].max() if y > x else np.nan for x, y in zip(l1, h1)])
            with np.errstate(divide="ignore", invalid="ignore"):
                s_col = np.where((ref >= COL_MINREF) & notr, np.clip(1 - D[j] / ref, 0, 1), 0.0)
            px = b["ba"].to_numpy()[j] if team == 0 else 1 - b["bb"].to_numpy()[j]
            if len(tk):
                q = tk[(tk["cid"] == cid)]
                tm = np.where(q["side"] == 0, q["oi"], 1 - q["oi"])
                ws = q["sign_ms"].to_numpy()[tm == team]
            else:
                ws = np.array([])
            y = np.zeros(len(bins), bool)
            k = np.searchsorted(bins, ws, side="right") - 1
            y[k[(k >= 0) & (k < len(bins))]] = True
            rows.append(pd.DataFrame({"y": y, "s_col": np.nan_to_num(s_col), "n2": n2, "n10": n10, "z10": z10, "px": px}))
    if not rows:
        return None
    x = pd.concat(rows, ignore_index=True)
    x = x[np.isfinite(x["px"])]
    if x["y"].sum() == 0:
        return {"bins": int(len(x)), "positives": 0}
    from sklearn.linear_model import LogisticRegression
    Xb = np.column_stack([np.log1p(x["n2"]), np.log1p(x["n10"]), np.log1p(x["z10"]), x["px"], x["px"] ** 2])
    base = LogisticRegression(max_iter=3000).fit(Xb, x["y"]).predict_proba(Xb)[:, 1]  # in-sample baseline (generous to it)
    return {"bins": int(len(x)), "positives": int(x["y"].sum()), "taker_presence_auc_S_col": round(_auc(x["s_col"], x["y"]), 4),
            "taker_presence_baseline_insample": round(_auc(base, x["y"]), 4)}


def _coverage(u, iv, end, pay) -> dict:
    """Scope item 1 (iteration 8, X112): share of the wallet's fills (TRADE rows) and of its absolute settlement PnL
    in the lot's units that the rule universe (CS2 + Dota 2 match / map-winner markets) covers. Units = markets whose
    event (or, outside the universe, the market itself) starts in an interval. Settlement values only settle PnL."""
    ucid = set(u["cid"])
    if end <= H and (CACHE / "activity_dev.parquet").exists():
        a = pd.read_parquet(CACHE / "activity_dev.parquet")
    elif not ALLOW_SEALED and (CACHE / "activity_devblocks.parquet").exists():
        a = pd.read_parquet(CACHE / "activity_devblocks.parquet")  # development units only (cached, may be partial)
    else:
        from polyrea.adapters.polymarket import PolymarketData
        rows, _, _ = PolymarketData().activity(WALLET, start=int(min(x[0] for x in iv)) - 6 * 3600,
                                               end=int(min(max(x[1] for x in iv) + 8 * 3600, end + 8 * 3600)))
        a = pd.DataFrame(rows)
    if a is None or len(a) == 0:
        return {"coverage_fills": None, "coverage_abs_pnl": None}
    a = a[a["type"] == "TRADE"].copy()
    for c in ("size", "usdcSize"):
        a[c] = a[c].astype(float)
    a["outcomeIndex"] = a["outcomeIndex"].astype(int)
    egs = u.groupby("event_slug")["gs_ts"].transform("min")
    gs = dict(zip(u["cid"], egs))
    pay = dict(pay)
    miss = sorted(set(a["conditionId"]) - set(gs))
    if miss:
        from polyrea.adapters.polymarket import PolymarketData
        mk, _ = PolymarketData().markets_by_condition(miss)
        for cid, x in mk.items():
            gs[cid] = _gs(x.get("gameStartTime") or x.get("eventStartTime") or x.get("startDate"))
            try:
                pay.setdefault(cid, float(json.loads(x.get("outcomePrices"))[0]))  # settlement only
            except Exception:  # noqa: BLE001
                pass
    a["gs"] = a["conditionId"].map(gs).astype(float)
    a = a[a["gs"].notna() & _in(a["gs"].to_numpy(), iv)]
    if len(a) == 0:
        return {"coverage_fills": None, "coverage_abs_pnl": None}
    a["p0"] = a["conditionId"].map(pay).astype(float)
    a["val"] = a["size"] * np.where(a["outcomeIndex"] == 0, a["p0"], 1 - a["p0"])
    g = a.groupby("conditionId").agg(f=("size", "size"), usd=("usdcSize", "sum"), val=("val", "sum"))
    g["pnl"] = (g["val"] - g["usd"]).abs()
    inu = g.index.isin(list(ucid))
    return {"coverage_fills": round(float(g.loc[inu, "f"].sum() / g["f"].sum()), 4),
            "coverage_abs_pnl": round(float(g.loc[inu, "pnl"].sum() / max(g["pnl"].sum(), 1e-9)), 4),
            "coverage_markets": int(len(g)), "coverage_markets_in_universe": int(inu.sum()),
            "coverage_fills_cs2_only": round(float(g.loc[g.index.isin(list(set(u.loc[u["series"] == "10310", "cid"]))), "f"].sum()
                                                   / g["f"].sum()), 4) if "series" in u else None}


def evaluate(start_ts: float, end_ts: float, intervals=None) -> dict:
    C = dict(CALL[CONSTANTS])
    C["league_sum"] = {**C["league_sum"], **DOTA[CONSTANTS]["league_sum"]}  # v4: Dota 2 leagues, same recipe
    C["league_n"] = {**C["league_n"], **DOTA[CONSTANTS]["league_n"]}
    iv = [tuple(x) for x in intervals] if intervals else [(start_ts, end_ts)]
    u = _universe(start_ts, end_ts, iv)
    fills = _wallet_fills(u, end_ts)
    traded = set(fills["cid"]) if len(fills) else set()
    bad = set(fills["tx"]) if len(fills) else set()
    pay = _payouts(u, end_ts)
    pre, tapes = {}, {}
    for r in u.itertuples():
        d = _tape(r.cid, int(r.gs_ts), end_ts)
        if d is None or len(d) == 0:
            pre[r.cid] = (0, 0.0, 0)
            continue
        d = d[~d["transactionHash"].isin(bad)].sort_values("timestamp")
        tapes[r.cid] = d
        ts = d["timestamp"].to_numpy(np.int64)
        m = (ts >= r.gs_ts - 3600) & (ts < r.gs_ts)
        pre[r.cid] = (int(m.sum()), float((d["price"].astype(float) * d["size"].astype(float))[m].sum()), int(d["proxyWallet"][m].nunique()))
    u[["n", "v", "w"]] = pd.DataFrame([pre.get(c, (0, 0.0, 0)) for c in u["cid"]], index=u.index)
    u["y"] = u["cid"].isin(traded).astype(int)
    u["grid"] = u["grid_series_id"].notna() if "grid_series_id" in u else False
    ev = u.groupby("event_slug").agg(y=("y", "max"), n=("n", "sum"), v=("v", "sum"), w=("w", "sum"), league=("league", "first"),
                                     tier=("league_tier", "first"), grid=("grid", "max"), gs=("gs_ts", "min")).reset_index()
    if "series" not in u:
        u["series"] = "10310"
    u["series"] = u["series"].fillna("10310").astype(str)
    dser = dict(zip(u["event_slug"], u["series"]))
    out = {"rule_id": "tommy-v5-grid-league-dota-groupP", "constants": CONSTANTS, "events": int(len(ev)), "events_traded": int(ev["y"].sum()),
           "markets": int(len(u)), "markets_traded": int(u["y"].sum()), "grid_events": int(ev["grid"].sum()),
           "grid_events_traded": int(ev.loc[ev["grid"], "y"].sum())}
    sc4, ba = selection_score(ev, C), activity_baseline(ev, C)
    y = ev["y"].to_numpy()
    # v5 (iteration 9, X127): v4 score + group-P coverage of the league in the previous 72 h (pre-registered adoption)
    gp = _gp72(ev, u, tapes, start_ts, end_ts, iv)
    sc = selection_score_v5(ev, C, gp)
    out["selection_auc_v4"] = round(_auc(sc4, y), 4)
    out["gp72_events_gt0"] = int((gp > 0).sum())
    out["selection_auc"] = round(_auc(sc, y), 4)
    out["selection_baseline"] = round(_auc(ba, y), 4)
    sel = sc >= V5[CONSTANTS]["thr"]
    out["selection_recall"] = round(float(y[sel].sum() / max(y.sum(), 1)), 3)
    out["selection_lift"] = round(float(y[sel].mean() / max(y.mean(), 1e-9)), 3) if sel.sum() else None
    rng = np.random.default_rng(0)
    g = []
    for _ in range(4000):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        g.append(_auc(sc[i], y[i]) - _auc(ba[i], y[i]))
    g = np.array(g)
    out["selection_gain"] = round(out["selection_auc"] - out["selection_baseline"], 4)
    out["selection_gain_ci95"] = [round(float(np.quantile(g, 0.025)), 4), round(float(np.quantile(g, 0.975)), 4)] if len(g) else None
    out["selection_gain_p_le0"] = round(float((g <= 0).mean()), 4) if len(g) else None
    for tname, code in (("cs2", "10310"), ("dota2", "10309")):  # v4: per-title selection (subsets of the pooled score)
        mt = ev["event_slug"].map(dser).fillna("10310").to_numpy() == code
        if mt.sum() and y[mt].min() != y[mt].max():
            out[f"selection_{tname}"] = {"events": int(mt.sum()), "traded": int(y[mt].sum()), "auc": round(_auc(sc[mt], y[mt]), 4),
                                         "baseline": round(_auc(ba[mt], y[mt]), 4),
                                         "recall": round(float(y[mt & sel].sum() / max(y[mt].sum(), 1)), 3),
                                         "lift": round(float(y[mt & sel].mean() / max(y[mt].mean(), 1e-9)), 3) if (mt & sel).sum() else None}
        elif mt.sum():
            out[f"selection_{tname}"] = {"events": int(mt.sum()), "traded": int(y[mt].sum()), "selected": int((mt & sel).sum())}
    # presence (fill per market x 30-s bin): event score x in-play, vs prints-only baseline (co-occurrence check)
    esc = dict(zip(ev["event_slug"], sc))
    bins = []
    for r in u.itertuples():
        d = tapes.get(r.cid)
        if d is None:
            continue
        ts = d["timestamp"].to_numpy(np.int64)
        st = r.gs_ts + BIN * np.arange(NB)
        st = st[st + BIN <= end_ts]
        i_now = np.searchsorted(ts, st, side="left")
        n120 = i_now - np.searchsorted(ts, st - 120, side="left")
        n600 = i_now - np.searchsorted(ts, st - 600, side="left")
        wt = np.sort(fills.loc[fills["cid"] == r.cid, "bts"].to_numpy(float)) if len(fills) else np.array([])
        yb = (np.searchsorted(wt, st + BIN, side="left") - np.searchsorted(wt, st, side="left")) > 0
        el = (st - r.gs_ts) / 60
        bins.append(pd.DataFrame({"y": yb.astype(int), "rule": esc[r.event_slug] * np.where(el <= INPLAY_MIN, 1.0, 0.1),
                                  "act": np.log1p(n120) + 0.1 * np.log1p(n600)}))
    if bins:
        bb = pd.concat(bins, ignore_index=True)
        out["presence_auc"] = round(_auc(bb["rule"], bb["y"]), 4)
        out["presence_baseline"] = round(_auc(bb["act"], bb["y"]), 4)
    # price: maker orders vs last public print (historical anchor); live join-the-bid is reported in NOTES
    if len(fills):
        mo = fills[fills["role"] == "maker"].drop_duplicates(["salt", "sign_ms"]) if "salt" in fills else fills[fills["role"] == "maker"]
        anc = []
        for cid, g2 in mo.groupby("cid"):
            d = tapes.get(cid)
            if d is None or len(d) == 0:
                continue
            ts = d["timestamp"].to_numpy(float)
            p0 = np.where(d["outcomeIndex"].astype(int) == 0, d["price"].astype(float), 1 - d["price"].astype(float))
            k = np.searchsorted(ts, g2["sign_ms"].to_numpy() / 1000, side="left")
            lp = np.where(k > 0, p0[np.maximum(k - 1, 0)], np.nan)
            lp = np.where(g2["oi"].to_numpy() == 0, lp, 1 - lp)
            anc.append(pd.DataFrame({"p": g2["price"].to_numpy(), "a": np.round(lp, 2)}))
        if anc:
            a = pd.concat(anc).dropna()
            # in-play tick: 0.01 until a map is decided (first sub-cent resting order median price 0.999), so the
            # tick in force at signing is 0.01 for mid-range prices and 0.001 near 0 / 1 (iteration-3 correction)
            tick = np.where((a["a"] >= 0.04) & (a["a"] <= 0.96), 0.01, 0.001)
            out["price_within_tick"] = round(float((np.abs(a["p"] - a["a"]) <= tick + 1e-9).mean()), 3)
            out["price_exact_last_print"] = round(float((np.abs(a["p"] - a["a"]) <= 0.001 + 1e-9).mean()), 3)
            out["price_within_cent"] = round(float((np.abs(a["p"] - a["a"]) <= 0.01 + 1e-9).mean()), 3)
        out["size_100_accuracy"] = round(float((mo["shares"].round(0) == 100).mean()), 3)
        # size rule v3: CS2 markets 100 shares, Dota 2 markets 10 shares (all 10-share maker orders are Dota 2)
        evs = dict(zip(u["cid"], u["event_slug"]))
        want = np.where(mo["cid"].map(evs).fillna("").str.startswith("dota2"), 10, 100)
        out["size_rule_accuracy"] = round(float((mo["shares"].round(0).to_numpy() == want).mean()), 3)
    # outcome: executable generic ladder on the selected events' markets, per-market PnL vs the wallet's
    selected = set(ev.loc[sel, "event_slug"])
    pm = []
    for r in u.itertuples():
        if r.cid not in pay or (r.event_slug not in selected and r.cid not in traded):
            continue
        rp = (_replay(tapes.get(r.cid), r.gs_ts, pay[r.cid], size=10.0 if str(r.series) == "10309" else 100.0)
              if r.event_slug in selected else 0.0)
        f = fills[fills["cid"] == r.cid] if len(fills) else fills
        wp = float((f["fill"] * np.where(f["oi"] == 0, pay[r.cid], 1 - pay[r.cid]) - f["usdc"]).sum()) if len(f) else 0.0
        dt = tapes.get(r.cid)
        npr = int((dt["timestamp"].to_numpy(np.int64) >= r.gs_ts).sum()) if dt is not None and len(dt) else 0
        pm.append((rp, wp, npr, r.cid in traded))
    if len(pm) >= 5:
        x = pd.DataFrame(pm, columns=["r", "w", "prints", "traded"])
        out["pnl_corr_pearson"] = round(float(np.corrcoef(x["r"], x["w"])[0, 1]), 3)
        out["pnl_corr_spearman"] = round(float(x["r"].rank().corr(x["w"].rank())), 3)
        out["pnl_markets"] = int(len(x))
        # iteration 6 (X82): co-occurrence baseline for the outcome item = a "c x in-play public prints" pseudo-PnL
        # (wallet txs excluded); its correlation with the wallet's PnL does not depend on c. Reported on the same
        # markets and on the wallet's traded markets, with the rule's partial correlation given log prints.
        out["pnl_baseline_prints_pearson"] = round(float(np.corrcoef(x["prints"], x["w"])[0, 1]), 3)
        out["pnl_baseline_prints_spearman"] = round(float(x["prints"].rank().corr(x["w"].rank())), 3)
        xt = x[x["traded"]]
        if len(xt) >= 5:
            out["pnl_baseline_prints_traded_pearson"] = round(float(np.corrcoef(xt["prints"], xt["w"])[0, 1]), 3)
            out["pnl_baseline_prints_traded_spearman"] = round(float(xt["prints"].rank().corr(xt["w"].rank())), 3)
        z = np.c_[np.ones(len(x)), np.log1p(x["prints"].to_numpy(float))]
        ry = x["w"].to_numpy(float) - z @ np.linalg.lstsq(z, x["w"].to_numpy(float), rcond=None)[0]
        rx = x["r"].to_numpy(float) - z @ np.linalg.lstsq(z, x["r"].to_numpy(float), rcond=None)[0]
        out["pnl_corr_partial_given_prints"] = round(float(np.corrcoef(rx, ry)[0, 1]), 3) if rx.std() > 0 else None
    out["side_accuracy"] = None  # two-sided maker at market level; the taker side comes from an unobserved feed
    out["live_trigger"] = None  # v2 book trigger retracted (receive-clock artefact); see live_taker_diagnostic
    out["live_taker_diagnostic_server_clock"] = _live_diag(u, fills, iv)
    out["live_price"] = _live_price(u, fills, iv)
    try:
        out.update(_coverage(u, iv, end_ts, pay))
    except Exception as e:  # noqa: BLE001
        out["coverage_error"] = repr(e)[:200]
    # one wallet: per-wallet metrics equal the pooled ones
    core = {k: v for k, v in out.items() if k not in ("rule_id", "constants")}
    out["per_wallet"] = {WALLET: core}
    out["pooled"] = core
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) > 2:
        CONSTANTS = a[2]
    print(json.dumps(evaluate(float(a[0]), float(a[1])), indent=1, default=str))
