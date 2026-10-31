"""tommy-cs2-maker frozen rule v1 (iteration 1, 2026-10-31). All parameters are constants
(final_rule_constants.json, fitted on BUILD = gameStart in [2026-10-16, 2026-10-21)).

Components (tags in FINAL_RULE.md):
  selection  CS2 moneyline + child_moneyline markets; league score s_meta = (league fills + k*tier rate)/(n + k)
             from BUILD; trade the market iff s_meta >= THR (0.344).
  timing     in-play only: quote from game start to the end of the map / match (presence rule: s_meta * in-play).
  side       maker: both outcomes (BUY orders on each token; pairs merged). Taker side: not decoded (descriptive).
  price      maker BUY orders on whole cents, ladders 1 cent apart; anchor = last public print rounded to the cent.
  size       100 shares per maker order.
  exit       merge pairs, hold the rest to resolution.

evaluate(start_ts, end_ts, intervals=None) -> dict of metrics (per wallet = pooled: one wallet).
Development periods use the local caches in .cache/re/tommy-cs2-maker/; other periods are fetched (Gamma projection,
data-api tapes per kept market, Polygon calldata for the wallet's transactions). Units = markets whose
gameStartTime lies in an interval. Live recordings are not used by v1 (ALLOW_SEALED kept for the contract).
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

ALLOW_SEALED = False
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
H = 1792713600
CACHE = ROOT / ".cache/re/tommy-cs2-maker"
C = json.load(open(HERE / "final_rule_constants.json"))
BIN, NB, INPLAY_MIN = 30, 480, 210


def _auc(score, y) -> float:
    from scipy.stats import rankdata
    s = np.asarray(score, float); y = np.asarray(y).astype(bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def s_meta(league: pd.Series, tier: pd.Series) -> np.ndarray:
    tr = tier.astype(str).str.replace(r"\.0$", "", regex=True).map(C["tier_rate"]).fillna(C["prior"]).astype(float)
    s = league.map(C["league_sum"]).fillna(0).astype(float)
    n = league.map(C["league_n"]).fillna(0).astype(float)
    return ((s + C["k"] * tr) / (n + C["k"])).to_numpy()


def _in(ts: np.ndarray, iv) -> np.ndarray:
    m = np.zeros(len(ts), bool)
    for a, b in iv:
        m |= (ts >= a) & (ts < b)
    return m


def _universe(start, end, iv) -> pd.DataFrame:
    if end <= H and (CACHE / "universe.parquet").exists():
        u = pd.read_parquet(CACHE / "universe.parquet")
    else:  # fetch listing projection (no post-hoc fields kept)
        from fetch_universe import SERIES  # noqa: F401
        from polyrea.adapters.http import shared_client
        h = shared_client(); rows = []
        lo = pd.Timestamp(start - 5 * 86400, unit="s").strftime("%Y-%m-%dT%H:%M:%SZ")
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
                                 "cid": m.get("conditionId"), "smt": m.get("sportsMarketType"), "game_start": m.get("gameStartTime"),
                                 "tokens": m.get("clobTokenIds"), "outcomes": m.get("outcomes")})
            if len(d) < 100:
                break
            off += 100
        u = pd.DataFrame(rows).drop_duplicates("cid")
        gs = pd.to_datetime(u["game_start"].astype(str).str.replace(r"\+00$", "+00:00", regex=True), utc=True, errors="coerce")
        u["gs_ts"] = (gs - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()
    u = u[u["smt"].isin(["moneyline", "child_moneyline"])].copy()
    u["gs_ts"] = pd.to_numeric(u["gs_ts"], errors="coerce")
    u = u[u["gs_ts"].notna()]
    u["gs_ts"] = u["gs_ts"].astype("int64")
    return u[_in(u["gs_ts"].to_numpy(), iv)].reset_index(drop=True)


def _tape(cid: str, gs: int, end: float) -> pd.DataFrame:
    p = CACHE / "tapes" / f"{cid}_tkw.parquet"
    if p.exists():
        return pd.read_parquet(p)
    from polyrea.adapters.polymarket import PolymarketData
    rows, _, _ = PolymarketData().market_trades(cid, start=gs - 3600, end=int(min(gs + 4 * 3600 + 600, end) - 1), taker_only=True)
    return pd.DataFrame(rows)


def _wallet_orders(u: pd.DataFrame, end: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(fills, orders) of the wallet in the universe markets: decoded calldata of its transactions."""
    cids = set(u["cid"])
    if end <= H and (CACHE / "calldata_all.parquet").exists():
        cd = pd.read_parquet(CACHE / "calldata_all.parquet")
        cd = cd[(cd["maker"] == WALLET) & cd["cid"].isin(cids)]
        o = pd.read_parquet(CACHE / "orders.parquet")
        return cd, o[o["cid"].isin(cids)]
    import httpx
    from polyrea.adapters.polymarket import PolymarketData
    from fetch_calldata import rows_of
    pm = PolymarketData(); txs = []
    for r in u.itertuples():
        rows, _, _ = pm.market_trades(r.cid, start=int(r.gs_ts) - 6 * 3600, end=int(end) - 1, taker_only=False)
        txs += [x["transactionHash"] for x in rows if str(x.get("proxyWallet", "")).lower() == WALLET]
    txs = sorted(set(txs)); recs = []
    cli = httpx.Client(timeout=40)
    for i in range(0, len(txs), 40):
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(txs[i:i + 40])]
        for x in cli.post("https://polygon-bor-rpc.publicnode.com", json=body).json():
            if x.get("result"):
                rr = rows_of(x["result"])
                bts = None
                recs += rr
    cd = pd.DataFrame(recs)
    if cd.empty:
        return cd, cd
    tok = {}
    for r in u.itertuples():
        t = json.loads(r.tokens) if isinstance(r.tokens, str) else r.tokens
        for i, x in enumerate(t or []):
            tok[str(x)] = (r.cid, i, r.smt, int(r.gs_ts))
    cd["cid"] = cd["token_id"].map(lambda t: tok.get(str(t), (None,))[0])
    cd["oi"] = cd["token_id"].map(lambda t: tok.get(str(t), (None, -1))[1])
    cd = cd[(cd["maker"] == WALLET) & cd["cid"].notna()]
    cd["bts"] = cd["sign_ms"] / 1000 + 3.0  # block time not fetched here: sign + median latency (descriptive only)
    key = ["salt", "sign_ms", "token_id", "price", "shares"]
    o = cd.assign(role=np.where(cd["idx"] == -1, "taker", "maker")).groupby(key).agg(
        cid=("cid", "first"), oi=("oi", "first"), role=("role", "first"), filled=("fill", "sum")).reset_index()
    o["sign_ts"] = o["sign_ms"] / 1000
    return cd, o


def evaluate(start_ts: float, end_ts: float, intervals=None) -> dict:
    iv = [tuple(x) for x in intervals] if intervals else [(start_ts, end_ts)]
    u = _universe(start_ts, end_ts, iv)
    fills, orders = _wallet_orders(u, end_ts)
    traded = set(fills["cid"]) if len(fills) else set()
    u["y"] = u["cid"].isin(traded).astype(int)
    u["s_meta"] = s_meta(u["league"], u["league_tier"])
    bad = set(fills["tx"]) if len(fills) else set()
    pre = {}
    bins = []
    last_p_rows = []
    for r in u.itertuples():
        d = _tape(r.cid, int(r.gs_ts), end_ts)
        if d is None or len(d) == 0:
            pre[r.cid] = (0, 0.0, 0)
            continue
        d = d[~d["transactionHash"].isin(bad)].sort_values("timestamp")
        ts = d["timestamp"].to_numpy(np.int64)
        gs = int(r.gs_ts)
        m = (ts >= gs - 3600) & (ts < gs)
        pre[r.cid] = (int(m.sum()), float((d["price"].astype(float) * d["size"].astype(float))[m].sum()), int(d["proxyWallet"][m].nunique()))
        st = gs + BIN * np.arange(NB)
        st = st[st + BIN <= end_ts]
        i_now = np.searchsorted(ts, st, side="left")
        n120 = i_now - np.searchsorted(ts, st - 120, side="left")
        n600 = i_now - np.searchsorted(ts, st - 600, side="left")
        if len(fills):
            wt = np.sort(fills.loc[fills["cid"] == r.cid, "bts"].to_numpy(float))
            yb = (np.searchsorted(wt, st + BIN, side="left") - np.searchsorted(wt, st, side="left")) > 0
        else:
            yb = np.zeros(len(st), bool)
        el = (st - gs) / 60
        bins.append(pd.DataFrame({"cid": r.cid, "y": yb.astype(int), "rule": r.s_meta * np.where(el <= INPLAY_MIN, 1.0, 0.1),
                                  "act": np.log1p(n120) + 0.1 * np.log1p(n600)}))
        if len(orders):
            om = orders[(orders["cid"] == r.cid) & (orders["role"] == "maker")]
            if len(om):
                p0 = np.where(d["outcomeIndex"].astype(int) == 0, d["price"].astype(float), 1 - d["price"].astype(float))
                k = np.searchsorted(ts, om["sign_ts"].to_numpy(), side="left")
                lp = np.where(k > 0, p0[np.maximum(k - 1, 0)], np.nan)
                lp = np.where(om["oi"].to_numpy() == 0, lp, 1 - lp)
                last_p_rows.append(pd.DataFrame({"price": om["price"].to_numpy(), "anchor": np.round(lp, 2)}))
    out = {"rule_id": "tommy-v1-league-ladder", "markets": int(len(u)), "markets_traded": int(u["y"].sum())}
    # selection
    sm = u["s_meta"].to_numpy(); y = u["y"].to_numpy()
    out["selection_auc"] = round(_auc(sm, y), 4)
    sel = sm >= C["thr"]
    out["selection_recall"] = round(float(y[sel].sum() / max(y.sum(), 1)), 3)
    out["selection_lift"] = round(float(y[sel].mean() / max(y.mean(), 1e-9)), 3) if sel.sum() else None
    pre_df = pd.DataFrame([pre.get(c, (0, 0.0, 0)) for c in u["cid"]], columns=["n", "v", "w"])
    pre_df["event"] = u["event_slug"].to_numpy()
    ev = pre_df.groupby("event")[["n", "v", "w"]].transform("sum")  # event-level pre-game activity (as fitted)
    X = np.column_stack([np.log1p(ev[k].to_numpy(float)) for k in ("n", "v", "w")])
    act = X @ np.array(C["act_coef"]) + C["act_icpt"]
    out["selection_baseline"] = round(_auc(act, y), 4)
    # presence
    if bins:
        bb = pd.concat(bins, ignore_index=True)
        out["presence_auc"] = round(_auc(bb["rule"], bb["y"]), 4)
        out["presence_baseline"] = round(_auc(bb["act"], bb["y"]), 4)
    # coverage: wallet fills of units in the intervals that fall in the rule's universe (CS2 match/map winners)
    out["coverage_fills"] = None  # needs the wallet's fills outside the CS2 universe (Dota 2): filled in NOTES
    # price / size (maker orders)
    if len(orders):
        mo = orders[orders["role"] == "maker"]
        out["size_100_accuracy"] = round(float((mo["shares"] == 100).mean()), 3) if "shares" in mo else None
        if last_p_rows:
            lp = pd.concat(last_p_rows, ignore_index=True).dropna()
            out["price_within_tick"] = round(float((np.abs(lp["price"] - lp["anchor"]) <= 0.001 + 1e-9).mean()), 3)
            out["price_within_cent"] = round(float((np.abs(lp["price"] - lp["anchor"]) <= 0.01 + 1e-9).mean()), 3)
    out["side_accuracy"] = None  # two-sided maker: no side choice at market level (see FINAL_RULE.md)
    out["pnl_corr_pearson"] = None
    out["pnl_corr_spearman"] = None
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    print(json.dumps(evaluate(float(a[0]), float(a[1])), indent=1))
