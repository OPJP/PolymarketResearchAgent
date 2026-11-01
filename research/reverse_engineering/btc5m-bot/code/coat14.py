"""Iteration 14, X136 remainder (X101 on the knee clock): is the selection the operator shares with the fast crowd explained by the
knee-clock spot design? Units: the scored hazard bins of 10-20..22 (hazard14_scored.parquet; operator first-leg positives + 1%
negatives, weight 100). Crowd take = a non-operator taker BUY on the same outcome matched in [e + 205, e + 255) (the operator's knee
band; operator txs and W4 / W5 taker txs excluded; diagnostic only, never a rule feature). Weighted logits of crowd take on the
operator take: raw, conditional on logit(P^ full hazard) (the knee-clock design: spot + Polymarket), and conditional on logit(P^
Polymarket-only) (market-only design). The share of the raw log OR explained by each design is reported.
Usage: python coat14.py FRAME_DIR HF_DIR TAPE_DIR"""
import os, sys, json
import numpy as np, pandas as pd
import statsmodels.api as sm

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
W45 = {"0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}


def main():
    D, A, TD = sys.argv[1], sys.argv[2], sys.argv[3]
    S = pd.read_parquet(f"{D}/hazard14_scored.parquet")
    win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "start_ts", "up_token", "down_token"]).set_index("cid")
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "start_ts"])
    excl = set(fl.loc[fl.start_ts >= 1792195200, "tx"].str.lower())
    for cc in S.cid.unique():
        p = f"{TD}/{cc}.parquet"
        if os.path.exists(p):
            d = pd.read_parquet(p, columns=["proxyWallet", "transactionHash"])
            excl |= set(d.loc[d.proxyWallet.str.lower().isin(W45), "transactionHash"].str.lower())
    days = sorted({pd.Timestamp(int(t), unit="s", tz="UTC").strftime("%Y-%m-%d") for t in win.loc[S.cid.unique(), "start_ts"]})
    tr = pd.concat([pd.read_parquet(f"{A}/pm_trades_{d}.parquet", columns=["exchangeTimestampMs", "transactionHash", "tokenId", "tradeSide"]) for d in days])
    tr = tr[(tr.tradeSide == "BUY") & ~tr.transactionHash.str.lower().isin(excl)]
    tr = tr.assign(h=tr.transactionHash.str.lower(), tokenId=tr.tokenId.astype(str)).groupby(["h", "tokenId"], as_index=False).exchangeTimestampMs.min()
    byt = {k: np.sort(g.exchangeTimestampMs.to_numpy(np.int64)) for k, g in tr.groupby("tokenId")}
    crowd = np.zeros(len(S), np.int8)
    for (cc, up), ii in S.groupby(["cid", "up"]).indices.items():
        tk = str(win.at[cc, "up_token"] if up == 1 else win.at[cc, "down_token"])
        T_ = byt.get(tk)
        if T_ is None:
            continue
        e = S.e.to_numpy(np.int64)[ii]
        crowd[ii] = (np.searchsorted(T_, e + 255, "left") > np.searchsorted(T_, e + 205, "left")).astype(np.int8)
    S["crowd"] = crowd
    lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    S["lf"] = lg(S.p_full); S["lp"] = lg(S.p_pm_only)
    res = {"bins": int(len(S)), "operator_positives": int(S.y.sum()), "crowd_positive_bins": int(S.crowd.sum()),
           "P_crowd_given_op_take": round(float(np.average(S.crowd[S.y == 1])), 4), "P_crowd_given_no_take_weighted": round(float(np.average(S.crowd[S.y == 0], weights=S.w[S.y == 0])), 4)}
    fits = {}
    for nm, cols in (("raw", ["y"]), ("cond_knee_design", ["y", "lf"]), ("cond_market_design", ["y", "lp"]), ("cond_both", ["y", "lf", "lp"])):
        X = sm.add_constant(S[cols].astype(float))
        m = sm.GLM(S.crowd.astype(float), X, family=sm.families.Binomial(), freq_weights=S.w).fit()
        fits[nm] = {"logOR_operator_take": round(float(m.params["y"]), 4), "se": round(float(m.bse["y"]), 4)}
    raw = fits["raw"]["logOR_operator_take"]
    for nm in ("cond_knee_design", "cond_market_design", "cond_both"):
        fits[nm]["share_explained"] = round(1 - fits[nm]["logOR_operator_take"] / raw, 4) if raw else None
    res["logit"] = fits
    json.dump(res, open(f"{R}/coat14.json", "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
