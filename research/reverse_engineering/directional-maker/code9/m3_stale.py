"""Iteration 9 (mechanics M3 = X81): are the cluster's paid fills stale takers on the Chainlink publish clock?
Every match of 10-31 15:20-15:40 UTC (development; all-match calldata of iteration 6: 5,528 taker orders with their
signing ms) in BTC 5m / 15m. Publish clock (no dy_rtds before 17:29): report S is taken as published at S + 1,083 ms (the
median relay delay measured on 17:29-18:00). For each taker order: u = the token it is short (SELL of u, or BUY of the
complement = a mint with a maker BUY of u); S_sign = the latest report published before its signing ms; S_pub = the
latest report published before match - 150 ms; stale iff S_pub > S_sign; dfair = fair_u(CL[S_pub]) - fair_u(CL[S_sign])
(Gamma strike, slow sigma v3600 of Binance spot). Label: a cluster maker order in the transaction. Reports P(label) by
staleness x sign of dfair, by taker signatureType, and the cluster's fill return by class (held to resolution)."""
import glob
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
import final_rule as F  # noqa: E402
import cl_source  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
a, b = 1793460000, 1793461200
PUB = 1083


def main():
    cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "allmatch1793460000_*.parquet"))])
    cd["tx"] = cd.tx.str.lower()
    cd["maker"] = cd.maker.str.lower()
    cl_tx = set(cd.loc[(cd.role == "maker") & cd.maker.isin(F.CLUSTER), "tx"])
    tk = cd[cd.role == "taker"].copy()
    tk = tk[~tk.maker.isin(F.CLUSTER)]
    xs = pd.concat([pd.read_parquet(p, columns=["h", "s"]) for p in glob.glob(str(C / "it6" / "x_*.parquet"))])
    xs["h"] = xs.h.str.lower()
    mms = xs.groupby("h").s.min()
    tk["T"] = tk.tx.map(mms)
    tk = tk.dropna(subset=["T"])
    w = pd.concat([F._windows(a - 900, b + 900), F._windows15(a - 900, b + 900)], ignore_index=True)
    w["up_token"], w["down_token"] = w.up_token.astype(str), w.down_token.astype(str)
    ptb = F._ptb_any(w)
    info = {}
    for r in w.itertuples(index=False):
        tag = "15m" if r.end_ts - r.start_ts == 900 else "5m"
        K = ptb.get((tag, int(r.start_ts)))
        info[r.up_token] = (int(r.start_ts), int(r.end_ts), 1, r.down_token, K, float(getattr(r, "up_payout", np.nan)))
        info[r.down_token] = (int(r.start_ts), int(r.end_ts), 0, r.up_token, K, float(getattr(r, "up_payout", np.nan)))
    tk["token_id"] = tk.token_id.astype(str)
    tk = tk[tk.token_id.isin(info)]
    clv = cl_source._live(a - 300, b + 300, False)
    sp = pd.read_parquet(C / "it9" / f"spot1s_rest_{1793448000 - 7200}_{1793469600}.parquet").sort_values("sec")
    b0 = int(sp.sec.iloc[0])
    px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan)
    px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    rr = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(rr * rr)]
    rows = []
    for r in tk.itertuples(index=False):
        st, en, isup, comp, K, upay = info[r.token_id]
        if K is None or not r.sign_ms or r.sign_ms <= 0:
            continue
        u_is_up = isup if r.oside == 1 else 1 - isup  # SELL token -> short token; BUY token -> short the complement
        T = int(r.T)
        s_sign = int((r.sign_ms - PUB) // 1000)
        s_pub = int((T - 150 - PUB) // 1000)
        c0, c1 = clv.get(s_sign), clv.get(s_pub)
        if c0 is None or c1 is None:
            continue
        i = T // 1000 - 1 - b0
        sg = np.sqrt((cs[i + 1] - cs[i + 1 - 3600]) / 3600)
        tau = max(en - T / 1000, 1.0)
        f0 = norm.cdf(np.log(c0 / K) / (sg * np.sqrt(tau)))
        f1 = norm.cdf(np.log(c1 / K) / (sg * np.sqrt(tau)))
        df = (f1 - f0) if u_is_up else (f0 - f1)
        rows.append(dict(tx=r.tx, T=T, lat=T - r.sign_ms, stale=int(s_pub > s_sign), dfair=df, sig_type=int(r.sig_type),
                         y=int(r.tx in cl_tx), u_up=u_is_up, upay=upay))
    D = pd.DataFrame(rows)
    out = {"matches": int(len(D)), "base_rate": float(D.y.mean()), "stale_share": float(D.stale.mean()),
           "median_latency_ms_cluster": float(D.lat[D.y == 1].median()), "median_latency_ms_other": float(D.lat[D.y == 0].median())}
    cls = np.select([D.stale == 0, D.dfair > 0.005, D.dfair < -0.005], ["fresh", "stale_up", "stale_down"], "stale_flat")
    D["cls"] = cls
    out["by_class"] = {c: {"n": int((cls == c).sum()), "p_cluster": float(D.y[cls == c].mean()),
                           "lift": float(D.y[cls == c].mean() / D.y.mean())} for c in ("fresh", "stale_flat", "stale_up", "stale_down")}
    names = {0: "EOA", 1: "proxy(Magic)", 2: "Safe", 3: "type3"}
    out["by_sigtype"] = {}
    for s_, nm in names.items():
        g = D.sig_type == s_
        if g.sum() < 50:
            continue
        out["by_sigtype"][nm] = {c: {"n": int((g & (cls == c)).sum()), "p_cluster": float(D.y[g & (cls == c)].mean()) if (g & (cls == c)).any() else None}
                                 for c in ("fresh", "stale_flat", "stale_up", "stale_down")}
    # cluster fill return by class: the cluster bought u (the taker's short); payout of u
    cf = D[D.y == 1].copy()
    cf["pay_u"] = np.where(cf.u_up == 1, cf.upay, 1 - cf.upay)
    out["cluster_fills_win_rate_by_class"] = {c: {"n": int((cf.cls == c).sum()), "u_won": float(cf.pay_u[cf.cls == c].mean()) if (cf.cls == c).any() else None}
                                             for c in ("fresh", "stale_flat", "stale_up", "stale_down")}
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter9_m3_stale.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
