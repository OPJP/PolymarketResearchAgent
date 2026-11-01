"""Iteration 6 (X24 = panel-mechanics proposal 1, live part): what quote does the bot lift? For every live development
taker match (live6_events.parquet: tx, server match ms m, quiet flag from 7 trade feeds), the calldata of the tx gives
the maker orders it consumed with their signing ms (V2 order timestamp). Quote age = m - sign_ms of the best-priced
consumed maker order (effective ask), maker identity, whether the quote is a complementary BUY (mint) or a SELL.
Compares quiet and moving matches. Uses calldata.fetch_txs (decoded fields only). Writes results_prey_iter6.json.
Usage: python prey6.py"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calldata as CD
import live6
C = live6.C


def main():
    ev = pd.read_parquet(C + "/live6_events.parquet")
    path = C + "/post/cd6_live.parquet"
    have = pd.read_parquet(path) if os.path.exists(path) else pd.DataFrame(columns=["tx"])
    need = sorted(set(ev.tx) - set(have.tx))
    if need:
        rows = CD.fetch_txs(need, threads=2, log_every=10 ** 9)
        new = CD.to_frame(rows)
        have = pd.concat([have, new]) if len(have) else new
        have.to_parquet(path, index=False)
    cd = have
    cd["px"] = np.where(cd.oside == 0, cd.maker_amt / cd.taker_amt, cd.taker_amt / cd.maker_amt)
    tk = cd[cd.role == "T"][["tx", "token", "maker", "px", "sign_ms"]].rename(columns={"token": "t_token", "maker": "t_maker", "px": "limit", "sign_ms": "t_sign"})
    mk = cd[cd.role == "M"][["tx", "token", "oside", "px", "maker", "sign_ms", "maker_amt", "taker_amt"]].merge(tk, on="tx")
    same = mk.token == mk.t_token
    mk["eff"] = np.where(same & (mk.oside == 1), mk.px, np.where(~same & (mk.oside == 0), 1.0 - mk.px, np.nan))
    mk["comp"] = ~same & (mk.oside == 0)
    best = mk.sort_values(["tx", "eff", "sign_ms"]).drop_duplicates("tx")
    e = ev.merge(best[["tx", "eff", "maker", "sign_ms", "comp", "limit"]], on="tx", how="inner")
    e["age_ms"] = e.m - e.sign_ms
    e["quiet"] = e.quiet_trades8.astype(bool)
    res = {"events": int(len(ev)), "with_calldata": int(len(e))}
    for nm, x in (("all", e), ("quiet", e[e.quiet]), ("moving", e[~e.quiet])):
        a = x.age_ms.to_numpy(float)
        a = a[np.isfinite(a)]
        res[nm] = {"n": int(len(x)), "age_ms_q": {str(q): round(float(np.quantile(a, q)), 0) for q in (0.05, 0.1, 0.25, 0.5, 0.75)} if len(a) else None,
                   "share_age_lt_250": round(float((a < 250).mean()), 4) if len(a) else None, "share_age_lt_500": round(float((a < 500).mean()), 4) if len(a) else None,
                   "share_age_lt_1000": round(float((a < 1000).mean()), 4) if len(a) else None, "share_comp_buy": round(float(x.comp.mean()), 4) if len(x) else None,
                   "limit_eq_best": round(float(((x.limit - x.eff).abs() < 1e-6).mean()), 4) if len(x) else None,
                   "top_makers": {k[:10]: int(v) for k, v in x.maker.value_counts().head(5).items()}}
    # makers whose quotes the bot lifts fresh: age < 500 ms, quiet vs moving
    e.to_parquet(C + "/prey6_events.parquet", index=False)
    return res


if __name__ == "__main__":
    res = main()
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_prey_iter6.json"), "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:3000])
