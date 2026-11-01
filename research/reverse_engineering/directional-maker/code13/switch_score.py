"""X142 (panel iter12 assumptions P3): the settlement switches as a natural experiment for the engine's late-window fair.

Sample: code13/fetch_switch.py (BTC 5m windows of the UTC hours 02, 08, 14, 20 of 07-31..08-20). Regime per window from
its own Gamma listing (cryptoMarketConfig: twapEnabled / twapLookbackSeconds; spot otherwise).
(1) Withdrawal with a tape control: per regime, the cluster's share of maker BUY dollars in the last 30 s and the median
    seconds left at its last fill per window, against the market's (all clean taker prints) share of dollars in the last
    30 s and seconds left at the last print.
(2) The late fair: for every cluster maker BUY fill with 0 < end - ts <= 90, three fairs of the bought outcome from
    Binance 1-s (published by ts - 1; Gamma priceToBeat strike; sigma = 1.4 x 300-s realised vol): spot digital (settles
    on S(end)), TWAP-30 lock-in, TWAP-60 lock-in (observed part of the average + remaining spot). Edge = fair - the last
    clean print of that outcome before the fill second. Per regime: the share of late fills with positive edge under each
    fair, and the MAD of the fill price to each fair.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE))
from features2 import Spot, clean_tape  # noqa: E402
from stable_score import tx_int, CL, NAME2ADDR  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
SW = C / "it13/switch"


def regime(cmc):
    try:
        c = json.loads(cmc) if isinstance(cmc, str) else (cmc or {})
    except ValueError:
        c = {}
    if not c or c in ("None", None) or not c.get("twapEnabled"):
        return "spot"
    return f"twap{int(c.get('twapLookbackSeconds') or 0)}"


def lockin_fair(sp, K, end, t, L, sig):
    """P(settlement >= K): spot (L = 0) or the TWAP over [end - L, end), given Binance seconds published by t."""
    St = sp.last(t)
    r = np.clip(end - t, 0, None).astype(float)
    if L == 0:
        sd = St * sig * np.sqrt(np.maximum(r, 1e-9))
        return norm.cdf((St - K) / sd)
    ts = end - L
    before = t < ts
    a_known = sp.mean(ts, np.maximum(t, ts + 1))
    rr = np.minimum(r, L)
    mean_in = ((L - rr) * a_known + rr * St) / L
    sd_in = St * sig * (rr / L) * np.sqrt(np.maximum(rr, 1e-9) / 3.0)
    sd_b = St * sig * np.sqrt(np.clip(ts - t, 0, None) + L / 3.0)
    mean = np.where(before, St, mean_in)
    sd = np.where(before, sd_b, sd_in)
    return norm.cdf((mean - K) / np.maximum(sd, 1e-9))


def main():
    w = pd.read_parquet(SW / "windows.parquet")
    w["reg"] = w.cmc.map(regime)
    from polyrea.analysis.updown import snap_price
    tk = []
    for r in w.itertuples(index=False):
        f = SW / f"t_{int(r.start_ts)}.parquet"
        if not f.exists():
            continue
        t = pd.read_parquet(f)
        if t.empty or "price" not in t:
            continue
        t = t[(t.ts >= r.start_ts - 120) & (t.ts < r.end_ts)]
        tk.append(pd.DataFrame({"cid": r.cid, "ts": t.ts.astype(np.int64), "side": t.side, "asset": t.asset.astype(str),
                                "price": t.price.astype(float).map(snap_price), "size": t["size"].astype(float), "wallet": t.wallet.astype(str),
                                "tx": tx_int(t.tx16)}))
    tk = pd.concat(tk, ignore_index=True)
    w = w[w.cid.isin(set(tk.cid))].reset_index(drop=True)
    h = pd.read_parquet(C / "it12/hist_btc.parquet")
    h = h[(h.type == "TRADE") & h.slug.isin(set(w.slug))].copy()
    s2 = w.set_index("slug")
    h["cid"] = h.slug.map(s2.cid)
    h["token_id"] = np.where(h.outcomeIndex.astype(int) == 0, h.slug.map(s2.up_token), h.slug.map(s2.down_token))
    h["wallet"] = h.w.map(NAME2ADDR)
    h["ts"] = h.timestamp.astype(np.int64)
    h["tx"] = tx_int(h.tx8)
    own = tk[tk.wallet.isin(set(CL))]
    tp = set(zip(own.tx, own.wallet))
    h["role"] = ["taker" if (a, b) in tp else "maker" for a, b in zip(h.tx, h.wallet)]
    mk = h[(h.side == "BUY") & (h.role == "maker")].copy()
    clean = clean_tape(tk, set(h.tx), set(CL))
    meta = w.set_index("cid")
    mk["end"] = mk.cid.map(meta.end_ts)
    mk["reg"] = mk.cid.map(meta.reg)
    mk["usd"] = mk.price * mk["size"]
    res = {"windows": int(len(w)), "regimes": w.reg.value_counts().to_dict(), "maker_fills": int(len(mk)),
           "regime_switch_dates": {g: [int(x.start_ts.min()), int(x.start_ts.max())] for g, x in w.groupby("reg")}}
    # (1) withdrawal with the tape control
    clean = clean.merge(w[["cid", "end_ts", "reg"]], on="cid")
    clean["usd"] = clean.price * clean["size"]
    wd = {}
    for g in sorted(set(w.reg)):
        m = mk[mk.reg == g]
        c = clean[(clean.reg == g) & (clean.ts >= clean.end_ts - 300)]
        last_m = m.groupby("cid").ts.max()
        last_c = c.groupby("cid").ts.max()
        wd[g] = {"cluster_usd_share_last30": float(m.usd[m.end - m.ts <= 30].sum() / m.usd.sum()) if len(m) else None,
                 "cluster_median_s_left_at_last_fill": float((m.groupby("cid").end.first() - last_m).median()) if len(m) else None,
                 "market_usd_share_last30": float(c.usd[c.end_ts - c.ts <= 30].sum() / c.usd.sum()) if len(c) else None,
                 "market_median_s_left_at_last_print": float((c.groupby("cid").end_ts.first() - last_c).median()) if len(c) else None,
                 "cluster_fills": int(len(m)), "windows": int(m.cid.nunique())}
    res["withdrawal"] = wd
    # (2) late fairs
    from polyrea.adapters.spot import binance_seconds
    rows, _ = binance_seconds("btc", int(w.start_ts.min()) - 3600, int(w.end_ts.max()) + 60)
    a = np.asarray(rows, dtype=float).reshape(-1, 2)
    sp = Spot(a[:, 0].astype(np.int64), a[:, 1])
    late = mk[(mk.end - mk.ts > 0) & (mk.end - mk.ts <= 90)].copy()
    late["K"] = late.cid.map(meta.ptb).astype(float)
    late = late[late.K.notna()]
    up_of = meta.up_token.to_dict()
    late["is_up"] = late.token_id == late.cid.map(up_of)
    c2 = clean.copy()
    c2["up_px"] = np.where(c2.asset.astype(str) == c2.cid.map(up_of), c2.price, 1 - c2.price)
    by = {c: (g.ts.to_numpy(np.int64), g.up_px.to_numpy(float)) for c, g in c2.sort_values("ts").groupby("cid")}
    mid = []
    for r in late.itertuples(index=False):
        ts_, px_ = by.get(r.cid, (np.array([], dtype=np.int64), np.array([])))
        i = np.searchsorted(ts_, int(r.ts), side="left") - 1
        mid.append(px_[i] if i >= 0 else np.nan)
    late["mid_up"] = mid
    t = late.ts.to_numpy(np.int64) - 1
    sig = sp.sigma(t, look=300) * 1.4
    en = late.end.to_numpy(np.int64)
    stt = en - 300
    out = {}
    # Binance-consistent strikes (the Chainlink priceToBeat carries a ~$50 basis to Binance BTCUSDT): spot regime =
    # the last Binance second before the start; TWAP-L regime = the Binance mean over [start - L, start)
    for nm, L in (("spot", 0), ("twap30", 30), ("twap60", 60)):
        K = sp.last(stt) if L == 0 else sp.mean(stt - L, stt)
        fu = lockin_fair(sp, K, en, t, L, sig)
        late["f_" + nm] = np.where(late.is_up, fu, 1 - fu)
    late["mkt"] = np.where(late.is_up, late.mid_up, 1 - late.mid_up)
    for g, x in late.groupby("reg"):
        x = x[x.mkt.notna()]
        o = {"n": int(len(x)), "windows": int(x.cid.nunique())}
        for nm in ("spot", "twap30", "twap60"):
            o[nm] = {"pos_edge_share": float((x["f_" + nm] > x.mkt).mean()), "mad_fill": float((x["f_" + nm] - x.price).abs().mean())}
        # per window best fair by MAD (windows with >= 3 late fills)
        best = []
        for c, y in x.groupby("cid"):
            if len(y) >= 3:
                best.append(min(("spot", "twap30", "twap60"), key=lambda n: (y["f_" + n] - y.price).abs().mean()))
        o["best_fair_share"] = pd.Series(best).value_counts(normalize=True).round(3).to_dict() if best else {}
        out[g] = o
    res["late_fair"] = out
    # by day: positive-edge share of TWAP-60 minus spot
    late["day"] = (late.ts // 86400 * 86400).astype(int)
    res["late_by_day"] = {int(d): {"reg": x.reg.mode().iloc[0], "n": int(len(x)), "spot": round(float((x.f_spot > x.mkt).mean()), 3),
                                   "twap30": round(float((x.f_twap30 > x.mkt).mean()), 3), "twap60": round(float((x.f_twap60 > x.mkt).mean()), 3)}
                          for d, x in late[late.mkt.notna()].groupby("day")}
    (HERE.parent / "results/iter13_switch_score.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: res[k] for k in ("windows", "regimes", "maker_fills", "regime_switch_dates", "withdrawal", "late_fair")}, indent=1, default=float))
    for d, v in res["late_by_day"].items():
        print(pd.Timestamp(d, unit="s").date(), v)


if __name__ == "__main__":
    main()
