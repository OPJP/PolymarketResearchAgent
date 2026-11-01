"""Iteration 12, PR12-E (X126 assumptions P3 = X115 information I11-2 = X121 mechanics P3, light form): who holds the
favourite side? Maker rows of the pre-registered sample (code12/fetch_makers.py: BTC 5m windows starting at 02, 08, 14,
20 UTC, 10-09..30), compacted by code12/maker_compact.py (taker rows removed with the taker-only tape). Maker BUY shares
per (day, 6-h block, wallet, favourite = price > 0.5), rows stamped in [start - 300, start + 300). VALIDATE days
(10-27..30) enter only through per-block aggregates.
    python code12/maker_shares.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"
CL = {"0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
      "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona"}


def rho(a, b):
    a, b = pd.Series(a), pd.Series(b)
    ok = a.notna() & b.notna()
    return round(float(spearmanr(a[ok], b[ok])[0]), 3) if ok.sum() > 8 else None


def main():
    M = pd.read_parquet(C / "it12" / "maker_rows.parquet")
    codes = pd.read_parquet(C / "it12" / "maker_wallet_codes.parquet")
    cl_ids = set(codes[codes.pw.isin(set(CL))].wid)
    M = M[M.buy & (M.ts >= M.st - 300) & (M.ts < M.st + 300)].copy()
    M["day"] = (M.st // 86400 * 86400).astype("int64")
    M["blk"] = ((M.st % 86400) // 21600).astype("int8")
    M["fav"] = M.price > 0.5
    M["clu"] = M.wid.isin(cl_ids)
    tot = M.groupby(["day", "blk", "fav"])["size"].sum().unstack(fill_value=0.0)
    clu = M[M.clu].groupby(["day", "blk", "fav"])["size"].sum().unstack(fill_value=0.0).reindex(tot.index, fill_value=0.0)
    B = pd.DataFrame({"mkt_fav": tot[True] / (tot[True] + tot[False]), "clu_fav": clu[True] / (clu[True] + clu[False]).replace(0, np.nan),
                      "clu_sh_fav": clu[True] / tot[True], "clu_sh_und": clu[False] / tot[False],
                      "clu_vol": clu[True] + clu[False], "tot_vol": tot[True] + tot[False]})
    B = B[B.clu_vol > 0].copy()
    B["clu_rel"] = np.log(B.clu_sh_fav.clip(1e-5) / B.clu_sh_und.clip(1e-5))
    oth = M[~M.clu]
    vol = oth.groupby("wid")["size"].sum().sort_values(ascending=False)
    top = list(vol.index[:30])
    res = {"maker_buy_rows": int(len(M)), "blocks": int(len(B)), "n_makers": int(M.wid.nunique()),
           "cluster_share_of_maker_buy_volume": round(float(B.clu_vol.sum() / B.tot_vol.sum()), 4),
           "top10_other_share": round(float(vol.iloc[:10].sum() / M["size"].sum()), 4),
           "cluster_fav_share_overall": round(float(M[M.clu & M.fav]["size"].sum() / M[M.clu]["size"].sum()), 4),
           "market_fav_share_overall": round(float(M[M.fav]["size"].sum() / M["size"].sum()), 4)}
    lo = lambda p: np.log(p / (1 - p))  # noqa: E731
    y = lo(B.clu_fav.clip(0.01, 0.99))
    res["decomposition"] = {
        "note": "log odds(cluster fav share) = log(cluster share of fav-side maker volume / cluster share of und-side) + log odds(market maker fav share)",
        "var_cluster_logodds": round(float(np.var(y)), 4), "var_relative_share_term": round(float(np.var(B.clu_rel)), 4),
        "var_market_term": round(float(np.var(lo(B.mkt_fav))), 4),
        "rho_clufav_vs_clu_sh_fav": rho(B.clu_fav, B.clu_sh_fav), "rho_clufav_vs_clu_sh_und": rho(B.clu_fav, B.clu_sh_und),
        "rho_clufav_vs_mkt_fav": rho(B.clu_fav, B.mkt_fav),
        "cv_clu_sh_fav": round(float(B.clu_sh_fav.std() / B.clu_sh_fav.mean()), 3), "cv_clu_sh_und": round(float(B.clu_sh_und.std() / B.clu_sh_und.mean()), 3)}
    comp = []
    totf = tot.loc[B.index, True]
    for w in top:
        g = oth[oth.wid == w].groupby(["day", "blk", "fav"])["size"].sum().unstack(fill_value=0.0).reindex(B.index, fill_value=0.0)
        for c in (True, False):
            if c not in g:
                g[c] = 0.0
        sh_fav = g[True] / totf
        own_fav = g[True] / (g[True] + g[False]).replace(0, np.nan)
        comp.append({"wid": int(w), "wallet": codes.set_index("wid").pw.get(w, "")[:10], "vol_share": round(float(vol[w] / M["size"].sum()), 4),
                     "own_fav_share": round(float(g[True].sum() / max(g[True].sum() + g[False].sum(), 1e-9)), 3),
                     "rho_shfav_vs_clufav": rho(sh_fav, B.clu_fav), "rho_ownfav_vs_clufav": rho(own_fav, B.clu_fav),
                     "blocks_active": int(own_fav.notna().sum())})
    res["top_competitors"] = comp
    othb = oth.groupby(["day", "blk", "fav"])["size"].sum().unstack(fill_value=0.0).reindex(B.index, fill_value=0.0)
    B["oth_fav"] = othb[True] / (othb[True] + othb[False])
    tk = oth[oth.wid.isin(top[:10])].groupby(["day", "blk", "fav"])["size"].sum().unstack(fill_value=0.0).reindex(B.index, fill_value=0.0)
    B["top10_sh_fav"] = tk[True] / totf
    res["rho_clufav_vs_others_fav"] = rho(B.clu_fav, B.oth_fav)
    res["rho_clufav_vs_top10_sh_fav"] = rho(B.clu_fav, B.top10_sh_fav)
    # daily cycle: does a large maker share the cluster's daily favourite-share series?
    cday = B.groupby(level=0).clu_fav.mean()
    dd = {}
    for w in top[:15]:
        g = oth[oth.wid == w].groupby(["day", "fav"])["size"].sum().unstack(fill_value=0.0)
        if True not in g or False not in g:
            continue
        s = (g[True] / (g[True] + g[False])).reindex(cday.index)
        r_ = rho(s, cday)
        if r_ is not None:
            dd[str(int(w))] = r_
    res["daily_cycle_rho_top15"] = dd
    D = B.groupby(level=0).agg(clu_fav=("clu_fav", "mean"), mkt_fav=("mkt_fav", "mean"), oth_fav=("oth_fav", "mean"),
                               clu_sh_fav=("clu_sh_fav", "mean"), clu_sh_und=("clu_sh_und", "mean"), top10_sh_fav=("top10_sh_fav", "mean"))
    D.index = [str(pd.to_datetime(d, unit="s").date()) for d in D.index]
    res["by_day"] = D.round(4).to_dict(orient="index")
    # STUDY/BUILD vs VALIDATE aggregates
    lotv = B.index.get_level_values(0) >= 1793059200
    res["halves"] = {"build_study": B[~lotv][["clu_fav", "mkt_fav", "oth_fav", "clu_sh_fav", "clu_sh_und", "top10_sh_fav"]].mean().round(4).to_dict(),
                     "validate_aggregate": B[lotv][["clu_fav", "mkt_fav", "oth_fav", "clu_sh_fav", "clu_sh_und", "top10_sh_fav"]].mean().round(4).to_dict()}
    (HERE.parent / "results" / "iter12_maker_shares.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k not in ("top_competitors", "by_day")}, indent=1))
    for r in comp[:12]:
        print(r)
    print(pd.DataFrame(res["by_day"]).T.to_string())


if __name__ == "__main__":
    main()
