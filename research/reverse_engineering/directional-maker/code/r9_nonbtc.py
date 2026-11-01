"""directional-maker iteration 15: R9 reporting block (not counted) for the crypto families outside BTC 5m/15m.

Called by final_rule.evaluate() as res['r9_nonbtc_module']. It describes the module that carries the idle weekend
blocks (iteration 15, code15/nb_side.py): every cluster BUY trade on {eth, sol, xrp, bnb, doge}-updown-{5m, 15m},
<coin>-updown-4h, <coin>-up-or-down-<date>-<h>-et (hourly, Binance 1h candle) and <coin>-up-or-down-on-<date> (daily,
Binance noon-ET 1m close), scored with frozen, unfitted side rules:
  - itm (public, sigma-free): buy the outcome in the money, Up iff S(T - 3) > K; S = Binance spot 1-s close; K = the
    Binance TWAP-60 stand-in over [st - 60, st - 1] for the Chainlink TWAP families (5m/15m/4h), the Binance 1-s open at
    st for hourly, Gamma priceToBeat for daily; reported for the opening fills (T - st < 20 s) and for all fills;
  - posture_public_k0.7 (public, iteration 15 T1d): buy s iff Phi(ln(S/K) / (0.7 x sigma300 sqrt(tau))) of s exceeds the
    price of s implied by the last clean taker print stamped <= T - 2 (dailies skipped); VALIDATE opening fills 0.866;
  - posture_fillprice (description, NOT public: uses the fill's own price as the market price): buy s iff
    Phi(ln(S/K) / (1.0 x sigma300 sqrt(tau))) of s exceeds the fill price; sigma300 = the symbol's 300-s 1-s log-return sd;
  - baselines: market favourite (fill price > 0.5), cheaper token, always-Up.
It also reports scope: the share of the cluster's trades and dollars in R8's universe (BTC 5m + 15m) and in the
all-family universe, pooled, per wallet and per examiner-style half (window start before / after the median listed
start of the period).
Spot seconds inside sealed blocks are never loaded unless allow_sealed (units are filtered by window start).
"""
from __future__ import annotations

import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CACHE = ROOT / ".cache/re/directional-maker/bn1s_eval"
KEY = "directional-maker"
ET = ZoneInfo("America/New_York")
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
SYM = {"btc": "BTCUSDT", "bitcoin": "BTCUSDT", "eth": "ETHUSDT", "ethereum": "ETHUSDT", "sol": "SOLUSDT", "solana": "SOLUSDT",
       "xrp": "XRPUSDT", "bnb": "BNBUSDT", "doge": "DOGEUSDT", "dogecoin": "DOGEUSDT"}
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                      "october", "november", "december"], 1)}
OPEN_S = 20
K_POSTURE = 1.0
K_PUBLIC = 0.7          # iteration 15 T1d: opening posture against the last public print (VALIDATE 0.866, STUDY 0.924)
PUBLIC_PRICE = True
PRICES_HISTORY = True   # iteration 16 X185: long families vs the CLOB prices-history minute mid (reported)


def parse(slug: str):
    m = re.match(r"^(\w+)-updown-(5m|15m|4h)-(\d+)$", slug)
    if m:
        return f"{m[1]}-{m[2]}", m[1], int(m[3]), {"5m": 300, "15m": 900, "4h": 14400}[m[2]]
    m = re.match(r"^([a-z]+)-up-or-down-on-([a-z]+)-(\d+)-(\d{4})$", slug)
    if m:
        end = datetime(int(m[4]), MONTHS[m[2]], int(m[3]), 12, 0, tzinfo=ET)
        st = end - timedelta(days=1)
        return f"{m[1]}-daily", m[1], int(st.timestamp()), int(end.timestamp() - st.timestamp())
    m = re.match(r"^([a-z]+)-up-or-down-([a-z]+)-(\d+)-(\d{4})-(\d+)(am|pm)-et$", slug)
    if m:
        h = int(m[5]) % 12 + (12 if m[6] == "pm" else 0)
        dt = datetime(int(m[4]), MONTHS[m[2]], int(m[3]), h, 0, tzinfo=ET)
        if h == 1 and dt.utcoffset() != (dt + timedelta(hours=1)).utcoffset():
            return None  # the repeated 1am ET hour of the DST fall-back
        return f"{m[1]}-hourly", m[1], int(dt.timestamp()), 3600
    return None


def _group(fam: str) -> str:
    if fam in ("btc-5m", "btc-15m"):
        return fam
    if re.match(r"^(eth|sol|xrp|bnb|doge|hype)-(5m|15m)$", fam):
        return "alt-" + fam.split("-")[1]
    return fam.split("-")[-1]  # 4h / hourly / daily


def _spot(sym: str, a: int, b: int, ok_ranges) -> pd.DataFrame:
    """Binance spot 1-s klines (sec, open, close) over [a, b) restricted to ok_ranges (REST, cached per hour)."""
    import httpx
    CACHE.mkdir(parents=True, exist_ok=True)
    fr = []
    with httpx.Client(timeout=30) as c:
        for h in range(a - a % 3600, b, 3600):
            lo, hi = max(h, a), min(h + 3600, b)
            for x, y in ok_ranges:
                x, y = max(lo, x), min(hi, y)
                if x >= y:
                    continue
                f = CACHE / f"{sym}_{x}_{y}.parquet"
                if f.exists():
                    fr.append(pd.read_parquet(f)); continue
                rows, t = [], x * 1000
                while t < y * 1000:
                    r = c.get("https://api.binance.com/api/v3/klines", params={"symbol": sym, "interval": "1s", "startTime": t,
                                                                                "endTime": y * 1000 - 1, "limit": 1000})
                    if r.status_code != 200:
                        time.sleep(2); continue
                    j = r.json()
                    if not j:
                        break
                    rows += [(int(q[0]) // 1000, float(q[1]), float(q[4])) for q in j]
                    t = int(j[-1][0]) + 1000
                    time.sleep(0.1)
                d = pd.DataFrame(rows, columns=["sec", "open", "close"])
                if y < time.time() - 120:
                    d.to_parquet(f, index=False)
                fr.append(d)
    if not fr:
        return pd.DataFrame(columns=["sec", "open", "close"])
    return pd.concat(fr).drop_duplicates("sec").sort_values("sec")


def report(start_ts: int, end_ts: int, intervals=None, allow_sealed: bool = False) -> dict:
    sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
    import sealed
    from scipy.stats import norm
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    rows = []
    # development mode never requests activity inside sealed blocks (fetch only the development intervals of the period)
    spans = [(start_ts, end_ts)] if allow_sealed else sealed.intervals(KEY, start_ts, end_ts, sealed=False)
    for addr, name in CLUSTER.items():
        act = []
        for x0, x1 in spans:
            part, _, _ = pm.activity(addr, start=int(x0), end=int(x1) - 1)
            act += part
        for r in act:
            if r.get("type") != "TRADE" or not (start_ts <= int(r["timestamp"]) < end_ts):
                continue
            rows.append({"wallet": name, "ts": int(r["timestamp"]), "slug": str(r.get("slug") or ""), "side": r.get("side"),
                         "outcome": str(r.get("outcome") or ""), "price": float(r.get("price") or 0), "size": float(r.get("size") or 0),
                         "usd": float(r.get("usdcSize") or 0), "cid": str(r.get("conditionId") or ""), "asset": str(r.get("asset") or ""),
                         "tx": str(r.get("transactionHash") or "").lower()})
    a = pd.DataFrame(rows)
    if not len(a):
        return {"n": 0}
    P = a.slug.map(parse)
    a = a[P.notna()].copy(); P = P[P.notna()]
    a["fam"] = [p[0] for p in P]; a["coin"] = [p[1] for p in P]; a["st"] = [p[2] for p in P]; a["L"] = [p[3] for p in P]
    keep = np.ones(len(a), bool)
    if intervals:
        keep &= np.array([any(x <= s < y for x, y in intervals) for s in a.st])
    if not allow_sealed:
        keep &= ~a.st.map(lambda s: sealed.is_sealed(int(s), KEY)).to_numpy() & ~a.ts.map(lambda s: sealed.is_sealed(int(s), KEY)).to_numpy()
    a = a[keep & (a.side == "BUY")].reset_index(drop=True)
    if not len(a):
        return {"n": 0}
    a["group"] = a.fam.map(_group)
    out = {"n": int(len(a)), "families": a.groupby("group").size().to_dict()}
    # scope (trades and dollars; |PnL| needs resolutions and is in the tape evaluation)
    med = float(np.median(a.drop_duplicates("slug").st))
    a["half"] = np.where(a.st < med, "earlier", "later")
    u1 = a.group.isin(["btc-5m", "btc-15m"])
    out["scope"] = {"R8_universe_trades": round(float(u1.mean()), 4),
                    "R8_universe_usd": round(float(a.loc[u1, "usd"].sum() / max(a.usd.sum(), 1e-9)), 4),
                    "all_family_universe": 1.0,
                    "per_half": {h: {"R8_trades": round(float(u1[a.half == h].mean()), 4),
                                     "R8_usd": round(float(a.loc[u1 & (a.half == h), "usd"].sum() / max(a.loc[a.half == h, "usd"].sum(), 1e-9)), 4)}
                                 for h in ("earlier", "later")},
                    "per_wallet_R8_trades": {w: round(float(u1[a.wallet == w].mean()), 4) for w in CLUSTER.values()}}
    nb = a[~u1 & a.coin.isin(SYM.keys())].copy()
    nb = nb[nb.outcome.str.lower().isin(["up", "down"])].reset_index(drop=True)
    if not len(nb):
        out["nonbtc"] = {"n": 0}
        return out
    nb["sym"] = nb.coin.map(SYM)
    # point-in-time spot ranges: development blocks only unless allow_sealed
    lo = int(min(nb.st.min() - 120, nb.ts.min() - 400)); hi = int(nb.ts.max() + 5)
    ok = [(lo, hi)] if allow_sealed else sealed.intervals(KEY, lo, hi, sealed=False)
    S = np.full(len(nb), np.nan); K = np.full(len(nb), np.nan); SG = np.full(len(nb), np.nan)
    daily = nb[nb.group == "daily"]
    kd = {}
    if len(daily):
        from polyrea.workflows.updown_study import fetch_windows
        for m in fetch_windows(sorted(set(daily.slug))).values():
            for e in m.get("events") or []:
                v = (e.get("eventMetadata") or {}).get("priceToBeat")
                if v is not None:
                    kd[m["slug"]] = float(v)
    for sym, g in nb.groupby("sym"):
        need_lo = int(min(g.ts.min() - 400, g[g.group != "daily"].st.min() - 120 if (g.group != "daily").any() else g.ts.min() - 400))
        d = _spot(sym, need_lo, int(g.ts.max()) + 5, ok)
        if not len(d):
            continue
        sec, op, cl = d.sec.to_numpy(np.int64), d.open.to_numpy(float), d.close.to_numpy(float)

        def close_at(t):
            t = np.asarray(t, np.int64); i = np.searchsorted(sec, t, side="right") - 1
            good = (i >= 0) & (t - sec[np.clip(i, 0, None)] <= 30)
            return np.where(good, cl[np.clip(i, 0, None)], np.nan)
        t3 = g.ts.to_numpy(np.int64) - 3
        S[g.index] = close_at(t3)
        st = g.st.to_numpy(np.int64)
        tw = g.group.isin(["alt-5m", "alt-15m", "4h"]).to_numpy()
        grid = st[:, None] + np.arange(-60, 0)[None, :]
        v = close_at(grid.ravel()).reshape(grid.shape)
        with np.errstate(invalid="ignore"):
            k_tw = np.where(np.isfinite(v).sum(1) >= 50, np.nanmean(v, axis=1), np.nan)
        i = np.clip(np.searchsorted(sec, st, side="left"), 0, max(len(sec) - 1, 0))
        k_hr = np.where((sec[i] >= st) & (sec[i] - st <= 5), op[i], np.nan)
        K[g.index] = np.where(tw, k_tw, np.where(g.group == "hourly", k_hr, g.slug.map(kd).to_numpy(float)))
        gl = t3[:, None] + np.arange(-300, 1)[None, :]
        lv = np.log(close_at(gl.ravel()).reshape(gl.shape))
        with np.errstate(invalid="ignore"):
            SG[g.index] = np.nanstd(np.diff(lv, axis=1), axis=1)
    nb["S"], nb["K"], nb["sig"] = S, K, SG
    up = (nb.outcome.str.lower() == "up").to_numpy(float)
    itm = np.where(np.isfinite(S) & np.isfinite(K) & (S != K), (S > K).astype(float), np.nan)
    nb["itm_ok"] = np.where(np.isfinite(itm), (itm == up).astype(float), np.nan)
    tau = np.maximum(nb.st + nb.L - nb.ts, 1).to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        Fu = norm.cdf(np.log(S / K) / (K_POSTURE * SG * np.sqrt(tau)))
    Fs = np.where(up == 1, Fu, 1 - Fu)
    nb["post_fp_ok"] = np.where(np.isfinite(Fs), (Fs > nb.price.to_numpy()).astype(float), np.nan)
    # iteration 15 T1d: the market price of the bought outcome from the last clean taker print stamped <= T - 2 (data-api
    # taker tape; transactions holding a cluster trade dropped; the other token mapped to 1 - p); dailies skipped (long tapes)
    ppub = np.full(len(nb), np.nan)
    if PUBLIC_PRICE:
        from concurrent.futures import ThreadPoolExecutor
        ctx = {c: set(g.tx) for c, g in a.groupby("cid")}
        mk = nb[nb.group != "daily"].drop_duplicates("cid")[["cid", "st", "L"]]

        def _tape(row):
            try:
                rr, _, _ = pm.market_trades(row[0], start=int(row[1]) - 3600, end=int(row[1] + row[2]) + 60, taker_only=True)
            except Exception:  # noqa: BLE001
                return row[0], []
            return row[0], [(int(x["timestamp"]), str(x.get("asset")), float(x["price"]), str(x.get("transactionHash", "")).lower()) for x in rr]
        with ThreadPoolExecutor(3) as ex:
            tapes = dict(ex.map(_tape, mk.itertuples(index=False, name=None)))
        for cid, g in nb[nb.group != "daily"].groupby("cid"):
            rr = sorted((x for x in tapes.get(cid, []) if x[3] not in ctx.get(cid, set())), key=lambda x: x[0])
            if not rr:
                continue
            tsv = np.array([x[0] for x in rr], np.int64); pv = np.array([x[2] for x in rr], float); av = [x[1] for x in rr]
            kk = np.searchsorted(tsv, g.ts.to_numpy(np.int64) - 2, side="right") - 1
            for j, k_, asset in zip(g.index, kk, g.asset):
                if k_ >= 0:
                    ppub[j] = pv[k_] if av[k_] == asset else 1 - pv[k_]
    with np.errstate(invalid="ignore", divide="ignore"):
        Fu7 = norm.cdf(np.log(S / K) / (K_PUBLIC * SG * np.sqrt(tau)))
    Fs7 = np.where(up == 1, Fu7, 1 - Fu7)
    nb["posture_public_ok"] = np.where(np.isfinite(Fs7) & np.isfinite(ppub), (Fs7 > ppub).astype(float), np.nan)
    nb["mktfav_public_ok"] = np.where(np.isfinite(ppub) & (ppub != 0.5), (ppub > 0.5).astype(float), np.nan)
    # iteration 16 X185 (reported): the long families (hourly, daily, 4h) against the CLOB prices-history minute mid of the
    # bought token (a point stamped t = the mean book mid of [t - 60, t); the last point stamped <= T - 1), posture k 1.0
    # (later daily fills 0.74-0.75 on STUDY / VALIDATE, market favourite from the same mid 0.51-0.59).
    pmid = np.full(len(nb), np.nan)
    if PRICES_HISTORY:
        try:
            from concurrent.futures import ThreadPoolExecutor
            lg = nb[nb.group.isin(["hourly", "daily", "4h"])]
            toks = lg.groupby(lg.asset.astype(str)).agg(st=("st", "first"), L=("L", "first")).reset_index()

            def _ph(row):
                try:
                    pts, _ = pm.price_history(str(row[0]), int(row[1]) - 600, int(row[1] + row[2]) + 60, fidelity_minutes=1)
                except Exception:  # noqa: BLE001
                    return str(row[0]), []
                return str(row[0]), sorted(pts)
            with ThreadPoolExecutor(3) as ex:
                hist = dict(ex.map(_ph, toks.itertuples(index=False, name=None)))
            for tok, g in lg.groupby(lg.asset.astype(str)):
                pts = hist.get(tok) or []
                if not pts:
                    continue
                tsv = np.array([x[0] for x in pts], np.int64); pv = np.array([x[1] for x in pts], float)
                kk = np.searchsorted(tsv, g.ts.to_numpy(np.int64) - 1, side="right") - 1
                okk = (kk >= 0) & (g.ts.to_numpy(np.int64) - tsv[np.clip(kk, 0, None)] <= 600)
                pmid[g.index] = np.where(okk, pv[np.clip(kk, 0, None)], np.nan)
        except Exception as ex:  # noqa: BLE001
            out["prices_history_error"] = repr(ex)[:200]
    nb["posture_ph_ok"] = np.where(np.isfinite(Fs) & np.isfinite(pmid), (Fs > pmid).astype(float), np.nan)
    nb["mktfav_ph_ok"] = np.where(np.isfinite(pmid) & (pmid != 0.5), (pmid > 0.5).astype(float), np.nan)
    nb["mktfav_ok"] = np.where(nb.price != 0.5, (nb.price > 0.5).astype(float), np.nan)
    nb["cheap_ok"] = np.where(nb.price != 0.5, (nb.price < 0.5).astype(float), np.nan)
    nb["up_ok"] = up
    nb["phase"] = np.where(nb.ts - nb.st < OPEN_S, "open", "later")

    def agg(g):
        return {"n": int(len(g)), "itm": _m(g.itm_ok), "posture_public_k0.7": _m(g.posture_public_ok), "mktfav_public": _m(g.mktfav_public_ok),
                "n_public": int(g.posture_public_ok.notna().sum()), "posture_fillprice": _m(g.post_fp_ok), "mktfav": _m(g.mktfav_ok),
                "cheaper": _m(g.cheap_ok), "always_up": _m(g.up_ok), "usd": round(float(g.usd.sum()), 1),
                "posture_prices_history_k1.0": _m(g.posture_ph_ok), "mktfav_prices_history": _m(g.mktfav_ph_ok),
                "n_prices_history": int(g.posture_ph_ok.notna().sum())}
    res = {"all": agg(nb), "open": agg(nb[nb.phase == "open"]), "later": agg(nb[nb.phase == "later"]),
           "by_group_phase": {f"{k[0]}|{k[1]}": agg(g) for k, g in nb.groupby(["group", "phase"])},
           "per_wallet": {w: agg(g) for w, g in nb.groupby("wallet")},
           "per_half": {h: agg(g) for h, g in nb.groupby("half")},
           "size_modes": {f: g["size"].round(2).value_counts().head(3).to_dict() for f, g in nb.groupby("fam") if len(g) >= 10}}
    out["nonbtc"] = res
    out["note"] = ("reported, not counted (iteration 15): itm is a public sigma-free rule; posture_fillprice uses the fill's own "
                   "price as the market price and is a description only; Binance spot is a stand-in for the Chainlink TWAP "
                   "families (same basis on S and K)")
    return out


def _m(x):
    x = pd.Series(x).dropna()
    return round(float(x.mean()), 4) if len(x) else None
