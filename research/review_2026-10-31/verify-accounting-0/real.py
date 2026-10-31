"""Real data: as-coded vs sign-correct per-market settled PnL for wallets that sell,
using the frozen as_of recorded in research/wallets/<w>/profile.json."""
import json, sys
import numpy as np, pandas as pd
from polyrea.workflows.investigate import load_window
from polyrea.analysis.profile import per_market_decomposition, summarize_profile, price_bucket_calibration, timing_features, resolution_info

W = {"TommyLeePeeca": "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2",
     "elmcap2": "0xed107a85a4585a381e48c7f7ca4144909e7dd2e5",
     "RN1": "0x2005d16a84ceefa912d4e380cd32e7ff827875ea",
     "justaluckydude": "0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705"}
names = sys.argv[1:] or list(W)
reb = json.load(open("research/stage_a/rebate_dependence.json"))

def corrected(trades, markets):
    rows = []
    for cid, g in trades.groupby("condition_id"):
        m = markets.get(cid) or {}
        res = resolution_info(m)
        toks = json.loads(m.get("clobTokenIds") or "[]") if m else []
        if not (res["resolved"] and len(toks) == 2):
            continue
        pay = [res["payout"].get(str(toks[0]), 0.0), res["payout"].get(str(toks[1]), 0.0)]
        b = g[g.side == "BUY"]; s = g[g.side == "SELL"]
        bq = b.groupby("outcome_index")["size"].sum(); bc = b.groupby("outcome_index")["usdc"].sum()
        sq = s.groupby("outcome_index")["size"].sum(); sc = s.groupby("outcome_index")["usdc"].sum()
        BQ = [float(bq.get(k, 0)) for k in (0, 1)]; BC = [float(bc.get(k, 0)) for k in (0, 1)]
        SQ = [float(sq.get(k, 0)) for k in (0, 1)]; SC = [float(sc.get(k, 0)) for k in (0, 1)]
        net = [BQ[k] - SQ[k] for k in (0, 1)]
        pnl = sum(net[k] * pay[k] for k in (0, 1)) - (sum(BC) - sum(SC))
        # decomposition on positions actually held (avg buy cost), realized on sells vs avg buy cost
        avg = [BC[k] / BQ[k] if BQ[k] else np.nan for k in (0, 1)]
        realized = sum(SC[k] - SQ[k] * (avg[k] if BQ[k] else 0.0) for k in (0, 1))
        h = [max(net[k], 0.0) for k in (0, 1)]
        pairs = min(h)
        locked = pairs * (1 - avg[0] - avg[1]) if pairs > 0 else 0.0
        rs = 0 if h[0] > h[1] else 1
        rq = abs(h[0] - h[1])
        resid = rq * (pay[rs] - avg[rs]) if rq > 0 else 0.0
        rows.append(dict(cid=cid, pnl=pnl, realized=realized, locked=locked, resid=resid,
                         neg_net=any(n < -1e-6 for n in net), has_sell=len(s) > 0))
    return pd.DataFrame(rows)

for name in names:
    w = W[name]
    prof = json.load(open(f"research/wallets/{w}/profile.json"))
    as_of = prof["subject"]["as_of"]
    win = load_window(w, days=30, as_of=as_of)
    tr, mk = win["trades"], win["markets"]
    pm = per_market_decomposition(tr, mk)
    summ = summarize_profile(tr, pm, timing_features(tr, mk))
    rec = prof["derived"]["profile"]
    sells = tr[tr.side == "SELL"]
    print(f"== {name} ({w[:10]}) as_of={as_of} fills={len(tr)} sells={len(sells)} ({len(sells)/len(tr):.2%}) "
          f"bought ${tr[tr.side=='BUY'].usdc.sum():,.0f} sold ${sells.usdc.sum():,.0f}")
    print(f"  recorded profile.json: settled_pnl {rec['settled_pnl']:,.0f} locked {rec['settled_locked_pnl']:,.0f} resid {rec['settled_residual_pnl']:,.0f}")
    print(f"  recomputed as coded  : settled_pnl {summ['settled_pnl']:,.0f} locked {summ['settled_locked_pnl']:,.0f} resid {summ['settled_residual_pnl']:,.0f}")
    c = corrected(tr, mk)
    print(f"  sign-correct (net held): pnl {c.pnl.sum():,.0f} = realized-from-sells {c.realized.sum():,.0f} + locked {c.locked.sum():,.0f} + resid {c.resid.sum():,.0f}"
          f" | resolved mkts {len(c)}, with sells {int(c.has_sell.sum())}, net-short (sold pre-window shares) {int(c.neg_net.sum())}")
    if name in reb:
        r = reb[name]
        print(f"  user-pnl series: position_pnl {r['position_pnl']:,.0f} (economic {r['economic_pnl']:,.0f}, fees {r['fees_paid']:,.0f})")
    print(f"  series pnl_series_window (economic) {prof['observed']['pnl_series_window']:,.0f}; income {prof['observed']['income_window']}")
    if len(sells):
        cal_all = price_bucket_calibration(tr, mk)
        cal_buy = price_bucket_calibration(tr[tr.side == "BUY"], mk)
        cb = {round(b["price_lo"], 1): b for b in cal_buy}
        print("  calibration bucket: win_rate as coded (recorded) vs buys only")
        recc = {round(b["price_lo"], 1): b for b in prof["derived"]["price_calibration"]}
        for b in cal_all:
            lo = round(b["price_lo"], 1)
            print(f"    {lo:.1f}-{lo+0.1:.1f}: coded {b['win_rate']:.3f} (recorded {recc.get(lo,{}).get('win_rate',float('nan')):.3f}) shares {b['shares']:,.0f} | buys-only {cb.get(lo,{}).get('win_rate',float('nan')):.3f} shares {cb.get(lo,{}).get('shares',0):,.0f}")
    sys.stdout.flush()
