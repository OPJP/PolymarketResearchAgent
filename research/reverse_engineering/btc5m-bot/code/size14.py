"""Iteration 14, X132 step 1-3 (compact): is the ORIGINAL order size a response to the knee-clock spot move? Calldata sample hours on
10-17..22 (original size = BUY takerAmount in shares, taker-role cluster orders), joined to the decision-clock frame (dcfit14_pred +
dcclock14_frame features) through the capture match ms of the tx. Large = original size above the (day, arm) modal size (arm B =
(start/300) mod 4 in {1, 2}). Univariate AUCs within wallet: |250-ms / 100-ms spot microprice return| at the knee anchor, the signed
return toward the bought outcome, |p - 0.5| (the old-anchor-free Polymarket last price), rel; and the share of large by arm.
Usage: python size14.py FRAME_DIR HF_DIR"""
import os, sys, json
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
WAL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}


def main():
    D, A = sys.argv[1], sys.argv[2]
    X = pd.read_parquet(f"{D}/dcclock14_frame.parquet", columns=["cid", "wallet", "up", "m", "rank", "day", "rel", "start_ts", "own_bs_mic_100", "own_bs_mic_250", "own_bs_mic_500", "own_pm_last"])
    cd = pd.read_parquet(f"{C}/calldata_sample.parquet", columns=["tx", "cid", "role", "maker", "token", "taker_amt", "oside"])
    cd["wallet"] = cd.maker.str.lower().map(WAL)
    cd = cd[cd.wallet.notna() & (cd.oside == 0) & (cd.role == "T")].copy()
    mt = pd.concat([pd.read_parquet(f"{A}/pm_trades_{d}.parquet", columns=["exchangeTimestampMs", "transactionHash"]) for d in sorted(X.day.unique())])
    mt = mt.assign(h=mt.transactionHash.str.lower()).groupby("h").exchangeTimestampMs.min()
    cd["m"] = cd.tx.str.lower().map(mt)
    cd = cd[cd.m.notna()].copy(); cd["m"] = cd.m.astype(np.int64)
    win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "up_token"])
    cd = cd.merge(win, on="cid", how="left"); cd["up"] = (cd.token.astype(str) == cd.up_token.astype(str)).astype(int)
    J = cd.merge(X, on=["cid", "wallet", "up", "m"], how="inner").drop_duplicates(["tx", "wallet", "token"])
    J["size"] = J.taker_amt.astype(float).round(0)
    J["arm"] = ((J.start_ts // 300) % 4).isin([1, 2]).astype(int)
    mode = J.groupby(["day", "arm"])["size"].agg(lambda x: x.value_counts().idxmax())
    J["mode"] = mode.reindex(pd.MultiIndex.from_arrays([J.day, J.arm])).to_numpy()
    J["large"] = (J["size"] > J["mode"]).astype(int)
    sg = np.where(J.up == 1, 1.0, -1.0)
    J["abs250"] = J.own_bs_mic_250.abs(); J["abs100"] = J.own_bs_mic_100.abs(); J["tow250"] = J.own_bs_mic_250 * sg
    J["dist"] = (J.own_pm_last - 0.5).abs()
    res = {"orders_joined": int(len(J)), "calldata_taker_orders": int(len(cd)), "size_by_day_arm": {f"{d}|{a}": g["size"].value_counts().head(4).to_dict() for (d, a), g in J.groupby(["day", "arm"])},
           "large_share_by_day_arm": {f"{d}|{a}": round(float(g.large.mean()), 3) for (d, a), g in J.groupby(["day", "arm"])}}
    auc = {}
    for w in ("ALL", "DS", "GF", "XM"):
        g = J if w == "ALL" else J[J.wallet == w]
        if g.large.nunique() < 2:
            continue
        o = {"n": int(len(g)), "large": int(g.large.sum())}
        for k in ("abs250", "abs100", "tow250", "dist", "rel"):
            v = g[k].to_numpy(); ok = np.isfinite(v)
            o[k] = round(float(roc_auc_score(g.large[ok], v[ok])), 4) if g.large[ok].nunique() == 2 else None
        o["first_legs_abs250"] = round(float(roc_auc_score(g.large[g["rank"] == 0], g.abs250[g["rank"] == 0].fillna(0))), 4) if g[g["rank"] == 0].large.nunique() == 2 else None
        auc[w] = o
    res["auc_large_original"] = auc
    json.dump(res, open(f"{R}/size14.json", "w"), indent=1)
    print(json.dumps(res)[:3000])


if __name__ == "__main__":
    main()
