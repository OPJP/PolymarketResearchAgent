"""X145 analysis: is SX Bet a usable historical in-play price for the wallet's CS2 events (16-22 Oct, development)?

Inputs: .cache/re/tommy-cs2-maker/sx/ (sx_fetch.py: every SX fill-summary log 10-16..H, the mapped markets, the decoded
maker orders of every esports fill tx). The wallet's Polymarket markets (markets_dev.json: question, outcomes,
gameStartTime), its maker orders (orders.parquet) and the public taker tapes (tapes/<cid>_tkw.parquet).
Measures: (1) SX esports / CS2 coverage of the week (markets, fill txs, maker orders, in-play share); (2) overlap with the
wallet's 80 traded events (team-name + date match); (3) fill density per in-play hour on matched match-winner markets;
(4) on matched in-play fills, the SX maker's implied probability for the Polymarket token vs the wallet's latest maker
order price on that token signed before the SX block time (descriptive, fill-selected) and vs the Polymarket last
public print before it: mean / SD of the gap, share within 1c.
Output: results/sx_secondvenue.json
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
C = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
H = 1792713600


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def sim(a, b):
    return bool(a) and bool(b) and (a in b or b in a or (len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4]))


def main():
    S = pd.read_parquet(C / "sx/sx_fill_summaries.parquet")
    MK = pd.read_parquet(C / "sx/sx_markets.parquet")
    MO = pd.read_parquet(C / "sx/sx_maker_orders.parquet")
    es = MK[MK.sportLabel == "E Sports"].copy()
    cs = es[es.leagueLabel.astype(str).str.startswith("Counter-Strike")].copy()
    out = {"sx_week": {"fill_txs_all_sports": int(S.tx.nunique()), "markets_all_sports": int(S.mh.nunique()),
                       "esports_markets": int(len(es)), "esports_fill_txs": int(S[S.mh.isin(es.marketHash)].tx.nunique()),
                       "cs2_markets": int(len(cs)), "cs2_fill_txs": int(S[S.mh.isin(cs.marketHash)].tx.nunique()),
                       "cs2_leagues": cs.leagueLabel.value_counts().to_dict(), "cs2_types": cs.type.value_counts().to_dict()}}
    St = S.merge(cs[["marketHash", "gameTime", "teamOneName", "teamTwoName", "type", "leagueLabel"]], left_on="mh",
                 right_on="marketHash")
    St["inplay"] = St.ts >= St.gameTime
    out["sx_week"]["cs2_fill_txs_inplay"] = int(St[St.inplay].tx.nunique())
    out["sx_week"]["cs2_fill_usdc"] = round(float(St.amt.sum()), 1)
    # Polymarket side: the wallet's markets (match winner and maps) with team names
    md = json.load(open(C / "markets_dev.json", encoding="utf-8"))
    pm = []
    for cid, m in md.items():
        try:
            outs = json.loads(m.get("outcomes") or "[]")
        except Exception:  # noqa: BLE001
            outs = []
        gs = pd.Timestamp(m.get("gameStartTime")).timestamp() if m.get("gameStartTime") else None
        pm.append({"cid": cid, "q": m.get("question"), "smt": m.get("sportsMarketType"), "o0": outs[0] if outs else None,
                   "o1": outs[1] if len(outs) > 1 else None, "gs": gs, "slug": (m.get("events") or [{}])[0].get("slug")})
    pm = pd.DataFrame(pm)
    pm = pm[pm.smt == "moneyline"]
    # match SX CS2 markets to the wallet's events (team names, game time within 6 h)
    rows = []
    for r in cs.itertuples():
        a, b = norm(r.teamOneName), norm(r.teamTwoName)
        for q in pm.itertuples():
            if q.gs is None or abs(q.gs - float(r.gameTime)) > 6 * 3600:
                continue
            na, nb = norm(q.o0), norm(q.o1)
            if (sim(a, na) and sim(b, nb)) or (sim(a, nb) and sim(b, na)):
                rows.append({"mh": r.marketHash, "cid": q.cid, "slug": q.slug, "sx_type": r.type, "flip": bool(sim(a, nb) and sim(b, na)),
                             "sx_t1": r.teamOneName, "pm_o0": q.o0, "gs": q.gs, "sx_gt": float(r.gameTime)})
    M = pd.DataFrame(rows)
    out["overlap"] = {"sx_cs2_markets_matched_to_wallet_match_markets": int(M.mh.nunique()) if len(M) else 0,
                      "wallet_events_with_sx_market": int(M.slug.nunique()) if len(M) else 0,
                      "wallet_events_total": int(pm.slug.nunique())}
    # per matched market: SX in-play fills and their implied probability for the PM token 0
    o = pd.read_parquet(C / "orders.parquet", columns=["cid", "oi", "sign_ts", "price", "role"])
    o = o[o.role == "maker"]
    comp = []
    dens = []
    for r in M.itertuples():
        sub = MO[(MO.mh == r.mh)].copy()
        sub = sub[sub.ts < H]
        ip = sub[sub.ts >= r.sx_gt]
        dur_h = max(1e-9, (o[o.cid == r.cid].sign_ts.max() - r.gs) / 3600.0) if (o.cid == r.cid).any() else np.nan
        dens.append({"slug": r.slug, "sx_fill_txs_inplay": int(ip.tx.nunique()), "inplay_hours_wallet": round(float(dur_h), 2) if np.isfinite(dur_h) else None})
        for x in ip.itertuples():
            p1 = x.po if x.one == 1 else 1 - x.po  # implied probability of SX outcome one (team one)
            p_tok0 = (1 - p1) if r.flip else p1
            ow = o[(o.cid == r.cid) & (o.oi == 0) & (o.sign_ts <= x.ts)]
            own = float(ow.sort_values("sign_ts").price.iloc[-1]) if len(ow) else np.nan
            ow1 = o[(o.cid == r.cid) & (o.oi == 1) & (o.sign_ts <= x.ts)]
            own1 = float(ow1.sort_values("sign_ts").price.iloc[-1]) if len(ow1) else np.nan
            lp = np.nan
            try:
                t = pd.read_parquet(C / f"tapes/{r.cid}_tkw.parquet", columns=["timestamp", "price", "outcomeIndex", "proxyWallet"])
                t = t[(t.timestamp <= x.ts) & (t.proxyWallet.str.lower() != W)].sort_values("timestamp")
                if len(t):
                    z = t.iloc[-1]
                    lp = float(z.price) if int(z.outcomeIndex) == 0 else 1 - float(z.price)
            except Exception:  # noqa: BLE001
                pass
            comp.append({"slug": r.slug, "ts": int(x.ts), "p_sx_tok0": round(p_tok0, 4), "own_bid_tok0": own,
                         "own_bid_tok1_as_tok0_ask": (1 - own1) if np.isfinite(own1) else np.nan, "pm_last": lp,
                         "stake": float(x.fill), "age_s": float(x.ts - r.gs)})
    Cm = pd.DataFrame(comp)
    out["density"] = dens
    if len(Cm):
        def gap(a, b):
            k = np.isfinite(Cm[a]) & np.isfinite(Cm[b])
            d = (Cm.loc[k, a] - Cm.loc[k, b]) * 100
            return {"n": int(k.sum()), "mean_c": round(float(d.mean()), 2) if k.any() else None,
                    "sd_c": round(float(d.std()), 2) if k.sum() > 1 else None,
                    "within_1c": round(float((d.abs() <= 1.0 + 1e-9).mean()), 3) if k.any() else None}
        out["inplay_fill_comparison"] = {"n_fills": int(len(Cm)), "events": int(Cm.slug.nunique()),
                                         "sx_minus_pm_last": gap("p_sx_tok0", "pm_last"),
                                         "sx_minus_wallet_bid_tok0": gap("p_sx_tok0", "own_bid_tok0"),
                                         "sx_minus_wallet_implied_ask_tok0": gap("p_sx_tok0", "own_bid_tok1_as_tok0_ask"),
                                         "pm_last_minus_wallet_bid_tok0": gap("pm_last", "own_bid_tok0")}
    (RES / "sx_secondvenue.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
