"""Point-in-time features for every taker BUY print, computed only from data with ts <= t - gap.

Polymarket tape timestamps are block times; a decision for a print in block t may only use
prints from blocks <= t - gap (gap >= 1 s; default 2 s) and Kraken seconds available by t - gap.
"""
import pickle, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.pit import TimeSeries
from polyrea.analysis.updown import SpotIndex, fair_up_vectorized

GAP = 2

def implied_up(flow):
    # every taker print implies a price for Up: Up print at q -> q, Down print at q -> 1-q
    return np.where(flow["is_up"].to_numpy(), flow["price"].to_numpy(), 1 - flow["price"].to_numpy())

def build(period, d, gap=GAP, ks=(2, 5, 10, 20, 30, 60)):
    t = d[period]
    prints = t["prints"].copy().reset_index(drop=True)
    flow = t["flow"].copy()
    flow["up_px"] = implied_up(flow)
    # signed flow toward Up in shares*price (usd): BUY Up +, SELL Up -, BUY Down -, SELL Down +
    sgn = np.where(flow["is_up"], 1, -1) * np.where(flow["side"] == "BUY", 1, -1)
    flow["up_usd"] = sgn * flow["size"] * flow["price"]
    ev = t["spot_ev"]; vals = t["spot_vals"]
    spot = SpotIndex(TimeSeries.build("spot", zip(ev.tolist(), vals.tolist()), availability_lag=1))
    feats = []
    for cid, g in prints.groupby("condition_id", sort=False):
        f = flow[flow.condition_id == cid].sort_values("ts", kind="stable")
        fts = f["ts"].to_numpy(); fup = f["up_px"].to_numpy(); fusd = np.cumsum(f["up_usd"].to_numpy())
        tt = g["ts"].to_numpy() - gap
        out = pd.DataFrame(index=g.index)
        idx = np.searchsorted(fts, tt, side="right") - 1  # last print with ts <= t-gap
        up_now = np.where(idx >= 0, fup[np.clip(idx, 0, None)], np.nan)
        cum_now = np.where(idx >= 0, fusd[np.clip(idx, 0, None)], 0.0)
        out["up_last"] = up_now
        out["n_prior"] = idx + 1
        for k in ks:
            j = np.searchsorted(fts, tt - k, side="right") - 1
            up_k = np.where(j >= 0, fup[np.clip(j, 0, None)], np.nan)
            cum_k = np.where(j >= 0, fusd[np.clip(j, 0, None)], 0.0)
            out[f"dup_{k}"] = up_now - up_k
            out[f"flow_{k}"] = cum_now - cum_k
            out[f"nprints_{k}"] = idx - j
            s_now = spot.price_at(tt); s_k = spot.price_at(tt - k)
            out[f"sret_{k}"] = np.log(s_now / s_k)
        feats.append(out)
    F = pd.concat(feats).sort_index()
    P = pd.concat([prints, F], axis=1)
    side = np.where(P["is_up"], 1.0, -1.0)
    # orient everything toward the bought side
    P["px_last_side"] = np.where(P["is_up"], P["up_last"], 1 - P["up_last"])
    P["px_vs_last"] = P["price"] - P["px_last_side"]  # >0: paying above last implied price
    for k in ks:
        P[f"dside_{k}"] = side * P[f"dup_{k}"]
        P[f"fside_{k}"] = side * P[f"flow_{k}"]
        P[f"sside_{k}"] = side * P[f"sret_{k}"]
    P["rel"] = P["ts"] - P["start_ts"]
    # spot fair (latency = gap) as in the recorded study
    fu = fair_up_vectorized(spot, P["start_ts"].to_numpy(), P["end_ts"].to_numpy(), P["ts"].to_numpy() - gap, 60)
    P["fair_side"] = np.where(P["is_up"], fu, 1 - fu)
    P["edge_spot"] = P["fair_side"] - P["price"]
    P["payout_side"] = np.where(P["is_up"], P["up_payout"], 1 - P["up_payout"])
    P["fee_ps"] = P["fee_rate"] * P["price"] * (1 - P["price"])
    return P, spot

if __name__ == "__main__":
    d = pickle.load(open("data.pkl", "rb"))
    out = {}
    for per in ("fit", "test"):
        P, _ = build(per, d)
        out[per] = P
        print(per, P.shape)
    pd.to_pickle(out, "features_taker.pkl")
