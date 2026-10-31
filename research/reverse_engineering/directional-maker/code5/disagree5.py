"""I5 (panel X17): in windows where the Binance proxy outcome differs from the real (Chainlink TWAP-60) outcome, does the
cluster's late net side follow the real outcome? Outcomes are labels for description only; nothing is fitted.

Proxy outcome: Binance 1-s TWAP over [end-60, end) >= TWAP over [start-60, start). Cluster net = Up minus Down shares
bought (maker and taker BUY fills) before end - 30 s. Market side = the side whose last clean print before end - 30 s is
above 0.5. Periods: BUILD (old split, 2026-10-09..22), STUDY (10-23..26) case by case, VALIDATE (10-27..30) aggregate.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache" / "re" / "directional-maker"
OUT = ROOT / "research" / "reverse_engineering" / "directional-maker" / "results"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


def spot_twap(sp_sec, sp_px, a, b):
    i, j = np.searchsorted(sp_sec, a), np.searchsorted(sp_sec, b)
    return sp_px[i:j].mean() if j > i else np.nan


def run(windows, spot, fills, tapes, name):
    sp = spot.sort_values("sec")
    s_sec, s_px = sp.sec.to_numpy(), sp.px.to_numpy().astype(float)
    fills = fills[fills.side == "BUY"]
    fb = {c: g for c, g in fills.groupby("cid")}
    out = []
    for w in windows.itertuples(index=False):
        k0 = spot_twap(s_sec, s_px, w.start_ts - 60, w.start_ts)
        k1 = spot_twap(s_sec, s_px, w.end_ts - 60, w.end_ts)
        if not np.isfinite(k0) or not np.isfinite(k1) or w.up_payout not in (0.0, 1.0):
            continue
        proxy_up = k1 >= k0
        g = fb.get(w.cid)
        net = 0.0
        if g is not None:
            g = g[g.ts < w.end_ts - 30]
            net = g.loc[g.token_id == w.up_token, "shares"].sum() - g.loc[g.token_id == w.down_token, "shares"].sum()
        mside = np.nan
        tp = tapes.get(w.cid)
        if tp is not None and len(tp):
            tp = tp[tp.ts < w.end_ts - 30]
            if len(tp):
                last = tp.iloc[-1]
                upx = last.price if last.asset == w.up_token else 1 - last.price
                mside = 1.0 if upx > 0.5 else 0.0
        margin = (k1 - k0) / k0 * 1e4
        out.append((w.cid, bool(w.up_payout == 1.0), proxy_up, net, mside, margin))
    df = pd.DataFrame(out, columns=["cid", "real_up", "proxy_up", "net", "mside", "margin_bp"])
    dis = df[df.real_up != df.proxy_up]
    act = dis[dis.net != 0]
    near = df[df.margin_bp.abs() <= df.margin_bp.abs().quantile(0.1)]
    near_act = near[near.net != 0]
    res = {"period": name, "windows": int(len(df)), "proxy_agree": float((df.real_up == df.proxy_up).mean()),
           "disagree_windows": int(len(dis)), "disagree_with_cluster_net": int(len(act)),
           "cluster_follows_real": float(((act.net > 0) == act.real_up).mean()) if len(act) else None,
           "cluster_follows_proxy": float(((act.net > 0) == act.proxy_up).mean()) if len(act) else None,
           "market_follows_real_in_disagree": float((dis.dropna(subset=["mside"]).mside == dis.dropna(subset=["mside"]).real_up).mean()) if len(dis) else None,
           "near_strike_windows_with_net": int(len(near_act)),
           "near_cluster_follows_real": float(((near_act.net > 0) == near_act.real_up).mean()) if len(near_act) else None,
           "near_market_follows_real": float((near.dropna(subset=["mside"]).mside == near.dropna(subset=["mside"]).real_up).mean()),
           "all_cluster_follows_real": float(((df[df.net != 0].net > 0) == df[df.net != 0].real_up).mean())}
    return res


def main():
    res = []
    # lot (STUDY case by case + VALIDATE aggregate)
    w = pd.read_parquet(C / "exam" / "windows_5m.parquet")
    sp = pd.read_parquet(C / "exam" / "spot_btc_1s.parquet")
    f = pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["cid", "token_id", "ts", "side", "shares"])
    for name, (a, b) in (("study", (1792713600, 1793059200)), ("validate", (1793059200, 1793404800))):
        ww = w[(w.start_ts >= a) & (w.start_ts < b)]
        tapes = {}
        for d in range(a, b, 86400):
            t = pd.read_parquet(C / "exam" / f"taker5m_day_{d}.parquet", columns=["cid", "ts", "asset", "price", "wallet", "tx"])
            t = t[~t.wallet.isin(CL)]
            for c, g in t.groupby("cid", sort=False):
                tapes[c] = g.sort_values("ts", kind="stable")
        res.append(run(ww, sp, f[(f.ts >= a - 600) & (f.ts < b + 600)], tapes, name))
        print(json.dumps(res[-1]))
    # BUILD (old split) from the pre-H caches
    w = pd.read_parquet(C / "windows_5m.parquet")
    sp = pd.read_parquet(C / "spot_btc_1s.parquet")
    fills = pd.read_parquet(C / "cluster_btc5m_fills.parquet")
    print(fills.columns.tolist()[:20])
    if "shares" in fills.columns and "cid" in fills.columns:
        res.append(run(w, sp, fills[["cid", "token_id", "ts", "side", "shares"]], {}, "build_pre_H"))
        print(json.dumps(res[-1]))
    (OUT / "iter5_disagree.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
