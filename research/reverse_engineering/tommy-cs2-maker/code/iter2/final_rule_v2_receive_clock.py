"""tommy-cs2-maker frozen rule v2 (`tommy-v2-grid-league-collapse`, iteration 2, 2026-10-31).

All parameters are constants in final_rule_v2_constants.json:
  "build": fitted on BUILD (gameStart 2026-10-16 .. 10-21), used for the VALIDATE numbers in state.json;
  "exam":  refitted on all development data (10-16 .. 10-23) with the same recipe; used by evaluate() (CONSTANTS).

Components (tags in FINAL_RULE.md):
  selection  unit = CS2 event (all its match / map-winner markets). s_lg = 0 if the event has a GRID series id
             (eventMetadata.gridSeriesId), else the league rate among fitted non-GRID events shrunk (k=3) toward the
             tier rate. score = logistic(log1p pre-game taker prints, USD, distinct wallets in [gs-1h, gs) summed over
             the event's markets; s_lg). Trade the event iff score >= thr (thr = 20th percentile of the fitted
             positives' scores, i.e. fitted recall 0.8).
  timing     maker: quotes from game start (in-play only). taker: fires within ~1 s after a collapse of the near-touch
             depth on one side of the book (other makers cancel, no trade): S_col = 1 - D(t) / max D[t-1.5 s, t-0.4 s]
             on the team's ask side (live books only).
  side       maker: both outcomes. taker: the team whose asks collapsed.
  price      maker: BUY at the best bid (join), whole cents, ladder 1c apart; taker: FAK at best ask + 1c.
  size       maker 100 shares; taker variable (not decoded).
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
    else:
        from polyrea.adapters.http import shared_client
        h = shared_client()
        rows = []
        lo = pd.Timestamp(start - 20 * 86400, unit="s").strftime("%Y-%m-%dT%H:%M:%SZ")
        hi = pd.Timestamp(end, unit="s").strftime("%Y-%m-%dT%H:%M:%SZ")
        off = 0
        while True:
            d, _ = h.get_json("https://gamma-api.polymarket.com/events", {"series_id": "10310", "start_date_min": lo,
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
                    rows.append({"event_slug": e.get("slug"), "league": meta.get("league"), "league_tier": meta.get("leagueTier"),
                                 "grid_series_id": meta.get("gridSeriesId"), "cid": m.get("conditionId"),
                                 "smt": m.get("sportsMarketType"), "game_start": m.get("gameStartTime"),
                                 "tokens": m.get("clobTokenIds"), "outcomes": m.get("outcomes")})
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


def _live_trigger(u, fills, iv) -> dict | None:
    """Taker presence on recorded books (0.5-s bins per market x team): AUC of S_col vs a prints-only baseline."""
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


def evaluate(start_ts: float, end_ts: float, intervals=None) -> dict:
    C = CALL[CONSTANTS]
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
    out = {"rule_id": "tommy-v2-grid-league-collapse", "constants": CONSTANTS, "events": int(len(ev)), "events_traded": int(ev["y"].sum()),
           "markets": int(len(u)), "markets_traded": int(u["y"].sum()), "grid_events": int(ev["grid"].sum()),
           "grid_events_traded": int(ev.loc[ev["grid"], "y"].sum())}
    sc, ba = selection_score(ev, C), activity_baseline(ev, C)
    y = ev["y"].to_numpy()
    out["selection_auc"] = round(_auc(sc, y), 4)
    out["selection_baseline"] = round(_auc(ba, y), 4)
    sel = sc >= C["thr"]
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
            out["price_within_tick"] = round(float((np.abs(a["p"] - a["a"]) <= 0.001 + 1e-9).mean()), 3)
            out["price_within_cent"] = round(float((np.abs(a["p"] - a["a"]) <= 0.01 + 1e-9).mean()), 3)
        out["size_100_accuracy"] = round(float((mo["shares"].round(0) == 100).mean()), 3)
    # outcome: executable generic ladder on the selected events' markets, per-market PnL vs the wallet's
    selected = set(ev.loc[sel, "event_slug"])
    pm = []
    for r in u.itertuples():
        if r.cid not in pay or (r.event_slug not in selected and r.cid not in traded):
            continue
        rp = _replay(tapes.get(r.cid), r.gs_ts, pay[r.cid]) if r.event_slug in selected else 0.0
        f = fills[fills["cid"] == r.cid] if len(fills) else fills
        wp = float((f["fill"] * np.where(f["oi"] == 0, pay[r.cid], 1 - pay[r.cid]) - f["usdc"]).sum()) if len(f) else 0.0
        pm.append((rp, wp))
    if len(pm) >= 5:
        x = pd.DataFrame(pm, columns=["r", "w"])
        out["pnl_corr_pearson"] = round(float(np.corrcoef(x["r"], x["w"])[0, 1]), 3)
        out["pnl_corr_spearman"] = round(float(x["r"].rank().corr(x["w"].rank())), 3)
        out["pnl_markets"] = int(len(x))
    out["side_accuracy"] = None  # two-sided maker at market level; taker side = collapse side (live metric below)
    out["live_trigger"] = _live_trigger(u, fills, iv)
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
