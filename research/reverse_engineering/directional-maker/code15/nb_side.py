"""directional-maker iteration 15, T1 (X173 + X175 + X164) and T2 (X168): the non-BTC module's side and sizes.

Pre-registered in NOTES (iteration 15, about 07:27 UTC 11-01). Universe: every cluster BUY trade on the crypto Up/Down
families other than BTC 5m/15m. Rule (no fitting): buy the outcome in the money under the family's reference,
Up iff S(T - 3) > K, with S = Binance spot 1-s close; K = Binance TWAP-60 stand-in (5m/15m/4h, Chainlink TWAP
families), the Binance 1-s open at the hour start (hourly), Gamma priceToBeat (daily). BTC 5m/15m scored the same way
for comparison. Folds: BUILD sample days, STUDY per day, VALIDATE aggregate, development blocks after T0.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code15/nb_side.py
"""
from __future__ import annotations

import json
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
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
import sealed  # noqa: E402

KEY = "directional-maker"
C = ROOT / ".cache/re/directional-maker"
BN = C / "bn1s"
RES = HERE.parent / "results"
ET = ZoneInfo("America/New_York")
WALLETS = {"bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
           "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
SYM = {"btc": "BTCUSDT", "bitcoin": "BTCUSDT", "eth": "ETHUSDT", "ethereum": "ETHUSDT", "sol": "SOLUSDT", "solana": "SOLUSDT",
       "xrp": "XRPUSDT", "bnb": "BNBUSDT", "doge": "DOGEUSDT", "dogecoin": "DOGEUSDT"}
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                      "october", "november", "december"], 1)}
BUILD_DAYS = ["2026-10-08", "2026-10-10", "2026-10-12", "2026-10-14", "2026-10-16", "2026-10-18", "2026-10-20", "2026-10-22"]


def dev_activity() -> pd.DataFrame:
    """BUILD + lot activity on disk, plus the development blocks after T0 (fetched once, cached)."""
    fr = []
    for src in ("", "exam/"):
        for n in WALLETS:
            d = pd.read_parquet(C / f"{src}activity_{n}.parquet")
            d["wallet"] = n
            fr.append(d)
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    now = int(time.time()) - 60
    for a, b in sealed.intervals(KEY, 1793404800, now, sealed=False):
        for n, w in WALLETS.items():
            f = C / f"act15_{n}_{a}_{b}.parquet"
            if f.exists() and b < now - 600:
                d = pd.read_parquet(f)
            else:
                rows, _, _ = pm.activity(w, start=a, end=b - 1)
                d = pd.DataFrame(rows)
                if len(d):
                    d = d[(d.timestamp >= a) & (d.timestamp < b)]
                d.to_parquet(f, index=False)
            if len(d):
                d = d[[c for c in fr[0].columns if c in d.columns and c != "wallet"]].copy()
                d["wallet"] = n
                fr.append(d)
    a = pd.concat(fr, ignore_index=True)
    a = a[a.type == "TRADE"].drop_duplicates(["transactionHash", "asset", "wallet", "size", "timestamp"])
    # every record must belong to a development unit: drop anything whose timestamp is in a sealed block
    a = a[~a.timestamp.map(lambda t: sealed.is_sealed(int(t), KEY))]
    return a


def parse(slug: str):
    """(family, coin, start_ts, length_s) from the slug; None if not a crypto Up/Down window."""
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
        try:
            dt = datetime(int(m[4]), MONTHS[m[2]], int(m[3]), h, 0, tzinfo=ET)
        except ValueError:
            return None
        # ambiguous hour (11-01 1am ET occurs twice): skip
        if dt.utcoffset() != (dt + timedelta(hours=1)).utcoffset() and h == 1:
            return None
        return f"{m[1]}-hourly", m[1], int(dt.timestamp()), 3600
    return None


class Spot:
    """per-symbol Binance spot 1-s klines (all available days concatenated): archive days, spot_btc_1s, REST blocks."""

    def __init__(self):
        self.cache = {}

    def arr(self, sym: str):
        if sym in self.cache:
            return self.cache[sym]
        fr = [pd.read_parquet(f) for f in sorted(BN.glob(f"{sym}_*.parquet"))]
        if sym == "BTCUSDT":
            d = pd.read_parquet(C / "spot_btc_1s.parquet")
            fr.append(pd.DataFrame({"sec": d.sec, "open": d.px, "close": d.px}))
        d = pd.concat(fr).drop_duplicates("sec").sort_values("sec") if fr else pd.DataFrame({"sec": [], "open": [], "close": []})
        self.cache[sym] = (d.sec.to_numpy(np.int64), d.open.to_numpy(float), d.close.to_numpy(float))
        return self.cache[sym]

    def close_at(self, sym, secs):
        """close of the last 1-s kline at or before each second (NaN if none within 30 s)."""
        sec, _, cl = self.arr(sym)
        secs = np.asarray(secs, np.int64)
        if not len(sec):
            return np.full(len(secs), np.nan)
        i = np.searchsorted(sec, secs, side="right") - 1
        ok = (i >= 0) & (secs - sec[np.clip(i, 0, None)] <= 30)
        return np.where(ok, cl[np.clip(i, 0, None)], np.nan)

    def open_at(self, sym, secs):
        """open of the first 1-s kline at or after each second (NaN if none within 5 s)."""
        sec, op, _ = self.arr(sym)
        secs = np.asarray(secs, np.int64)
        if not len(sec):
            return np.full(len(secs), np.nan)
        i = np.clip(np.searchsorted(sec, secs, side="left"), 0, len(sec) - 1)
        ok = (sec[i] >= secs) & (sec[i] - secs <= 5)
        return np.where(ok, op[i], np.nan)

    def twap60(self, sym, starts):
        starts = np.asarray(starts, np.int64)
        grid = starts[:, None] + np.arange(-60, 0)[None, :]
        v = self.close_at(sym, grid.ravel()).reshape(grid.shape)
        n = np.isfinite(v).sum(1)
        with np.errstate(invalid="ignore"):
            m = np.nanmean(np.where(np.isfinite(v), v, np.nan), axis=1)
        return np.where(n >= 50, m, np.nan)


def fold(t: int) -> str:
    day = time.strftime("%Y-%m-%d", time.gmtime(t))
    if t >= 1793404800:
        return "dev_after_T0"
    if day >= "2026-10-27":
        return "VALIDATE"
    if day >= "2026-10-23":
        return "STUDY_" + day[5:]
    if day in BUILD_DAYS:
        return "BUILD"
    return "BUILD_other"


def main():
    a = dev_activity()
    a = a[a.side == "BUY"].copy()
    P = a.slug.map(lambda s: parse(str(s)))
    a = a[P.notna()].copy()
    P = P[P.notna()]
    a["fam"] = [p[0] for p in P]
    a["coin"] = [p[1] for p in P]
    a["st"] = [p[2] for p in P]
    a["L"] = [p[3] for p in P]
    a = a[a.coin.isin(SYM.keys())]
    # units belong to the block in which they start: drop every unit that started in a sealed block (iteration-15 fix)
    a = a[~a.st.map(lambda s: sealed.is_sealed(int(s), KEY))]
    a["sym"] = a.coin.map(SYM)
    a["fold"] = a.timestamp.astype(int).map(fold)
    a = a[a.fold != "BUILD_other"]
    a["up"] = (a.outcome.astype(str).str.lower() == "up").astype(float)
    a.loc[~a.outcome.astype(str).str.lower().isin(["up", "down"]), "up"] = np.nan
    a = a[a.up.notna()]
    a["btc_core"] = a.fam.isin(["btc-5m", "btc-15m"])
    print("trades", len(a), a.groupby("fold").size().to_dict(), flush=True)
    sp = Spot()
    S = np.full(len(a), np.nan)
    K = np.full(len(a), np.nan)
    a = a.reset_index(drop=True)
    # strikes per window
    win = a.drop_duplicates("slug")[["slug", "fam", "sym", "st", "L"]].reset_index(drop=True)
    kw = np.full(len(win), np.nan)
    for sym, g in win.groupby("sym"):
        tw = g[g.fam.str.contains(r"-(?:5m|15m|4h)$")]
        if len(tw):
            kw[tw.index] = sp.twap60(sym, tw.st.to_numpy())
        hr = g[g.fam.str.endswith("-hourly")]
        if len(hr):
            kw[hr.index] = sp.open_at(sym, hr.st.to_numpy())
    dl = win[win.fam.str.endswith("-daily")]
    if len(dl):
        from polyrea.workflows.updown_study import fetch_windows
        raw = fetch_windows(sorted(set(dl.slug)))
        kd = {}
        for m in raw.values():
            for e in m.get("events") or []:
                v = (e.get("eventMetadata") or {}).get("priceToBeat")
                if v is not None:
                    kd[m["slug"]] = float(v)
        kw[dl.index] = dl.slug.map(kd).to_numpy(float)
    kmap = dict(zip(win.slug, kw))
    a["K"] = a.slug.map(kmap)
    for sym, g in a.groupby("sym"):
        S[g.index] = sp.close_at(sym, g.timestamp.to_numpy(np.int64) - 3)
    a["S"] = S
    a["sec_in"] = a.timestamp - a.st
    a["phase"] = np.where(a.sec_in < 20, "open<20s", "later")
    a["itm_up"] = np.where(np.isfinite(a.S) & np.isfinite(a.K) & (a.S != a.K), (a.S > a.K).astype(float), np.nan)
    a["rule_ok"] = (a.itm_up == a.up).astype(float).where(a.itm_up.notna())
    a["mktfav_ok"] = (a.price > 0.5).astype(float).where(a.price != 0.5)
    a["cheap_ok"] = (a.price < 0.5).astype(float).where(a.price != 0.5)
    a["upalways_ok"] = a.up
    a["usd"] = a.usdcSize.astype(float)
    sc = a[a.rule_ok.notna()]
    print("scored", len(sc), "of", len(a), flush=True)

    def agg(g):
        return pd.Series({"n": len(g), "rule": g.rule_ok.mean(), "mktfav": g.mktfav_ok.mean(), "cheap": g.cheap_ok.mean(),
                          "up": g.upalways_ok.mean(), "usd": g.usd.sum()})
    out = {}
    nb = sc[~sc.btc_core]
    out["nonbtc_by_fold_phase"] = nb.groupby(["fold", "phase"]).apply(agg).round(4).reset_index().to_dict("records")
    out["nonbtc_by_fold"] = nb.groupby(["fold"]).apply(agg).round(4).reset_index().to_dict("records")
    fgroup = nb.fam.str.replace(r"^(eth|sol|xrp|bnb|doge)-(5m|15m)$", r"alt-\2", regex=True)
    fgroup = fgroup.str.replace(r"^\w+-4h$", "4h", regex=True).str.replace(r"^\w+-hourly$", "hourly", regex=True).str.replace(r"^\w+-daily$", "daily", regex=True)
    nb = nb.assign(fgroup=fgroup)
    out["nonbtc_by_fgroup_fold_phase"] = nb.groupby(["fgroup", "fold", "phase"]).apply(agg).round(4).reset_index().to_dict("records")
    out["btc_core_by_fold_phase"] = sc[sc.btc_core].groupby(["fam", "fold", "phase"]).apply(agg).round(4).reset_index().to_dict("records")
    # per wallet (non-BTC, all phases)
    out["nonbtc_by_wallet_fold"] = nb.groupby(["wallet", "fold"]).apply(agg).round(4).reset_index().to_dict("records")
    # per market (one-sided markets: >= 70% of shares on one outcome): the rule's side at the market's first fill
    mk = []
    for slug, g in nb.groupby("slug"):
        sh_up = g.loc[g.up == 1, "size"].sum() / g["size"].sum()
        g0 = g.sort_values("timestamp").iloc[0]
        mk.append((slug, g0.fold, g0.fgroup, sh_up, float(g.up.iloc[0]), g0.itm_up, g0.price, len(g)))
    M = pd.DataFrame(mk, columns=["slug", "fold", "fgroup", "sh_up", "first_up", "itm_up", "p0", "n"])
    M["one_sided"] = (M.sh_up >= 0.7) | (M.sh_up <= 0.3)
    M["maj_up"] = (M.sh_up > 0.5).astype(float)
    M["rule_ok"] = (M.itm_up == M.maj_up).astype(float)
    M["mktfav_ok"] = ((M.p0 > 0.5) == (M.first_up == 1)) == (M.maj_up == M.first_up)
    out["markets_by_fold"] = M[M.one_sided].groupby("fold").agg(n=("slug", "size"), rule=("rule_ok", "mean"), one_sided_share=("one_sided", "size")).round(4).reset_index().to_dict("records")
    out["one_sided_share"] = M.groupby("fold").one_sided.mean().round(3).to_dict()
    # T2 size table: modal fill size per family and session (US session 12-21 UTC weekdays)
    hr = pd.to_datetime(a.timestamp, unit="s")
    a["session"] = np.where((hr.dt.hour >= 12) & (hr.dt.hour < 21) & (hr.dt.dayofweek < 5), "US", "off")
    tab = []
    for (fam, ses), g in a[~a.btc_core].groupby(["fam", "session"]):
        if len(g) < 30:
            continue
        vc = g["size"].round(2).value_counts()
        tab.append({"fam": fam, "session": ses, "n": len(g), "mode": float(vc.index[0]), "mode_share": round(float(vc.iloc[0] / len(g)), 3),
                    "second": float(vc.index[1]) if len(vc) > 1 else None,
                    "per_wallet_mode": {w: float(x["size"].round(2).mode().iloc[0]) for w, x in g.groupby("wallet")}})
    out["size_table"] = tab
    a.to_parquet(C / "it15_nb_side.parquet", index=False)
    (RES / "iter15_nb_side.json").write_text(json.dumps(out, indent=1, default=float))
    for k in ("nonbtc_by_fold_phase", "nonbtc_by_fold", "markets_by_fold", "one_sided_share"):
        print(k)
        print(pd.DataFrame(out[k]).to_string() if isinstance(out[k], list) else out[k])


if __name__ == "__main__":
    main()
