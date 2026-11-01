"""X141 (panel iter12 assumptions P2): maker composition near the strike across the September -> October boundary.

Maker rows: it13/makers/m_<start>.parquet (09-11..10-11 stable sample, taker rows dropped with the stable taker-only
tapes) + it12/maker_rows.parquet (10-09..30, the iteration-12 sample; the lot's VALIDATE days enter only as weekly
aggregates). Maker BUY volume (shares x price) by ISO-like week from 09-11 and price bucket (near strike 0.40-0.60 vs the
rest): the cluster's share, the top makers' shares, entrants (share < 0.2% in 09-11..19 and >= 1% in a later week), and
the cluster's near-strike fills held to resolution (return per $) with vs without an entrant's maker row in the same
window in the 60 s before the fill.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
W0 = 1789084800
LOT0, VAL0 = 1792713600, 1793059200


def stable_rows():
    W = pd.read_parquet(C / "it13/stable/windows.parquet").set_index("cid")
    out = []
    for f in sorted(glob.glob(str(C / "it13/makers/m_*.parquet"))):
        st = int(Path(f).stem.split("_")[1])
        d = pd.read_parquet(f)
        if d.empty:
            continue
        tf = C / f"it13/stable/t_{st}.parquet"
        if not tf.exists():
            continue
        T = pd.read_parquet(tf)
        keys = set(T.tx16.astype(str) + "|" + T.wallet.astype(str) + "|" + T.asset.astype(str) + "|" + T.side.astype(str)) if len(T) else set()
        pw = d.proxyWallet.astype(str).str.lower()
        k = d.transactionHash.astype(str).str.lower().str[2:18] + "|" + pw + "|" + d.asset.astype(str) + "|" + d.side.astype(str)
        tk = k.isin(keys).to_numpy()
        d = d[~tk]
        cid = d.cid.iloc[0] if len(d) else None
        if cid is None or cid not in W.index:
            continue
        out.append(pd.DataFrame({"st": np.int64(st), "ts": d.timestamp.astype("int64").to_numpy(), "pw": pw[~tk].to_numpy(),
                                 "buy": (d.side == "BUY").to_numpy(), "price": d.price.astype("float32").to_numpy(),
                                 "size": d["size"].astype("float32").to_numpy(), "is_up": (d.asset.astype(str) == str(W.at[cid, "up_token"])).to_numpy(),
                                 "cid": cid}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def outcomes():
    win = {}
    h = pd.read_parquet(C / "it12/hist_btc.parquet", columns=["type", "slug", "outcomeIndex", "usdcSize"])
    h = h[h.slug.astype(str).str.startswith("btc-updown-5m-")]
    for s, g in h[(h.type == "REDEEM") & (h.usdcSize > 0)].groupby("slug"):
        win[int(s.rsplit("-", 1)[1])] = int(g.outcomeIndex.mode().iloc[0]) == 0
    for f in (C / "windows_5m.parquet", C / "exam/windows_5m.parquet"):
        w = pd.read_parquet(f, columns=["start_ts", "up_payout"])
        for s, u in zip(w.start_ts, w.up_payout):
            if u is not None and np.isfinite(u) and int(s) not in win:
                win[int(s)] = float(u) > 0.5
    return win


def main():
    A = stable_rows()
    B = pd.read_parquet(C / "it12/maker_rows.parquet")
    codes = pd.read_parquet(C / "it12/maker_wallet_codes.parquet")
    B["pw"] = B.wid.map(dict(zip(codes.wid, codes.pw)))
    B = B[B.st >= 1791763200]  # the it12 sample from 10-12 on (the stable sample covers up to 10-11)
    M = pd.concat([A[["st", "ts", "pw", "buy", "price", "size", "is_up"]], B[["st", "ts", "pw", "buy", "price", "size", "is_up"]]], ignore_index=True)
    M = M[M.buy & (M.ts >= M.st) & (M.ts < M.st + 300)].copy()
    M["usd"] = M.price.astype(float) * M["size"].astype(float)
    M["week"] = ((M.st - W0) // (7 * 86400)).astype(int)
    M["near"] = M.price.between(0.40, 0.60)
    M["cl"] = M.pw.isin(CL)
    res = {"stable_windows": int(A.st.nunique()) if len(A) else 0, "it12_windows_from_1012": int(B.st.nunique()), "rows": int(len(M))}
    early = M[M.st < W0 + 9 * 86400]
    tot_e = early.groupby("pw").usd.sum() / early.usd.sum()
    wk = M.groupby(["week", "pw"]).usd.sum() / M.groupby("week").usd.sum()
    later_max = wk.reset_index().query("week >= 2").groupby("pw").usd.max()
    entrants = sorted(set(later_max[later_max >= 0.01].index) - set(tot_e[tot_e >= 0.002].index) - CL)
    res["entrants"] = entrants[:20]
    weeks = {}
    win = outcomes()
    for k, g in M.groupby("week"):
        o = {"windows": int(g.st.nunique())}
        for nm, gg in (("near", g[g.near]), ("tails", g[~g.near])):
            sh = gg.groupby("pw").usd.sum() / gg.usd.sum()
            o[nm] = {"cluster_share": round(float(sh[sh.index.isin(CL)].sum()), 4), "entrants_share": round(float(sh[sh.index.isin(entrants)].sum()), 4),
                     "top5_noncluster": [round(float(x), 4) for x in sh[~sh.index.isin(CL)].sort_values(ascending=False).head(5)],
                     "hhi_noncluster": round(float((sh[~sh.index.isin(CL)] ** 2).sum()), 4)}
        c = g[g.cl & g.near].copy()
        c["upwon"] = c.st.map(win)
        c = c[c.upwon.notna()]
        if len(c):
            won = np.where(c.is_up, c.upwon.astype(bool), ~c.upwon.astype(bool))
            o["cluster_near_return"] = round(float(((won * c["size"]).sum() - c.usd.sum()) / c.usd.sum()), 4)
            ent = g[g.pw.isin(entrants)][["st", "ts"]]
            if len(ent):
                es = {s: np.sort(x.ts.to_numpy()) for s, x in ent.groupby("st")}
                act = np.array([((lambda a: a.size > 0 and np.any((a >= t - 60) & (a < t)))(es.get(s, np.array([])))) for s, t in zip(c.st, c.ts)])
                for nm, m in (("with_entrant", act), ("without_entrant", ~act)):
                    if m.any():
                        cc = c[m]
                        ww = won[m]
                        o["cluster_near_return_" + nm] = [int(m.sum()), round(float(((ww * cc["size"]).sum() - cc.usd.sum()) / cc.usd.sum()), 4)]
        weeks[int(k)] = o
    res["weeks"] = weeks
    # per window: entrants' share of near-strike maker BUY dollars vs the cluster's near-strike return (>= 3 near fills)
    from scipy.stats import spearmanr
    nr = M[M.near].copy()
    nr["upwon"] = nr.st.map(win)
    rows = []
    for st_, g in nr.groupby("st"):
        c = g[g.cl & g.upwon.notna()]
        if len(c) < 3 or c.usd.sum() <= 0:
            continue
        won = np.where(c.is_up, c.upwon.astype(bool), ~c.upwon.astype(bool))
        rows.append((st_, float(g.usd[g.pw.isin(entrants)].sum() / g.usd.sum()), float(((won * c["size"]).sum() - c.usd.sum()) / c.usd.sum())))
    WR = pd.DataFrame(rows, columns=["st", "ent_share", "ret"])
    if len(WR) > 10:
        r_ = spearmanr(WR.ent_share, WR.ret)
        res["per_window_spearman_entrant_share_vs_cluster_near_return"] = [int(len(WR)), float(r_.correlation), float(r_.pvalue)]
        wk_ = pd.DataFrame([(k, v["near"]["entrants_share"], v.get("cluster_near_return")) for k, v in weeks.items()], columns=["k", "e", "r"]).dropna()
        r2 = spearmanr(wk_.e, wk_.r)
        res["per_week_spearman"] = [int(len(wk_)), float(r2.correlation), float(r2.pvalue)]
    (HERE.parent / "results/iter13_x141_makers.json").write_text(json.dumps(res, indent=1, default=float))
    print("per window", res.get("per_window_spearman_entrant_share_vs_cluster_near_return"), "per week", res.get("per_week_spearman"))
    print(json.dumps({k: res[k] for k in ("stable_windows", "it12_windows_from_1012", "rows", "entrants")}, default=float))
    for k, v in weeks.items():
        print(k, v)


if __name__ == "__main__":
    main()
