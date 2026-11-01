"""Iteration 14, X128 step 2 (compact): does a sequential follower leg (150-300 ms after the previous leg of the same event) depend on the
previous leg's fill outcome? Previous-leg outcome from fills: 'remainder rested' = the taker order's hash later has maker-role fills
(the unfilled part rested at the limit and was hit), else 'no resting fill' (fully filled at the match, or a remainder that was
cancelled unfilled). Also P(any follower within 0-300 ms). Units: the decision-clock frame (10-17..22), joined to fills through the
capture match ms of the tx. Usage: python follow14.py FRAME_DIR HF_DIR"""
import os, sys, json
import numpy as np, pandas as pd

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"


def main():
    D, A = sys.argv[1], sys.argv[2]
    P = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "ev", "rank", "day", "osz"])
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "token", "oh", "cid", "is_up", "start_ts", "shares"])
    fl = fl[fl.start_ts >= 1792195200]
    mk_oh = set(fl.loc[fl.role == "M", "oh"])
    T = fl[fl.role == "T"].groupby(["tx", "wallet", "token"], as_index=False).agg(cid=("cid", "first"), up=("is_up", "first"), oh=("oh", "first"), sh=("shares", "sum"))
    mt = pd.concat([pd.read_parquet(f"{A}/pm_trades_{d}.parquet", columns=["exchangeTimestampMs", "transactionHash"]) for d in sorted(P.day.unique())])
    mt = mt.assign(h=mt.transactionHash.str.lower()).groupby("h").exchangeTimestampMs.min()
    T["m"] = T.tx.str.lower().map(mt); T = T[T.m.notna()].copy(); T["m"] = T.m.astype(np.int64); T["up"] = T.up.astype(int)
    T["rested"] = T.oh.isin(mk_oh).astype(int)
    J = P.merge(T[["cid", "wallet", "up", "m", "rested", "sh"]], on=["cid", "wallet", "up", "m"], how="left").sort_values(["ev", "m"]).reset_index(drop=True)
    J["next_gap"] = J.groupby("ev").m.shift(-1) - J.m
    J["seq_next"] = ((J.next_gap >= 150) & (J.next_gap < 300)).astype(int)
    J["fan_next"] = (J.next_gap < 60).astype(int)
    J["any_next"] = (J.next_gap < 300).astype(int)
    res = {"orders": int(len(J)), "joined": int(J.rested.notna().sum())}
    for lab, g in (("rested_remainder", J[J.rested == 1]), ("no_resting_fill", J[J.rested == 0])):
        res[lab] = {"n": int(len(g)), "P_seq_follower_150_300": round(float(g.seq_next.mean()), 4), "P_fanout_follower_lt60": round(float(g.fan_next.mean()), 4),
                    "P_any_follower_lt300": round(float(g.any_next.mean()), 4), "median_filled_shares": float(g.sh.median())}
    # within wallet and for first legs only
    res["first_legs"] = {lab: {"n": int(len(g)), "P_seq": round(float(g.seq_next.mean()), 4), "P_any": round(float(g.any_next.mean()), 4)}
                         for lab, g in (("rested", J[(J["rank"] == 0) & (J.rested == 1)]), ("not_rested", J[(J["rank"] == 0) & (J.rested == 0)]))}
    res["by_wallet"] = {w: {lab: round(float(g[g.wallet == w].seq_next.mean()), 4) for lab, g in (("rested", J[J.rested == 1]), ("not_rested", J[J.rested == 0]))} for w in ("DS", "GF", "XM")}
    json.dump(res, open(f"{R}/follow14.json", "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
