"""Iteration 2: (F) the opening decision (first fills in the first seconds) vs public state at the start;
(G) how the three wallets split the work (window index, side, time in window)."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up
from panel2 import OUT, WALLETS
VAL0 = 1792108800
f = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
f = f[f["role"] == "maker"]
w = pd.read_parquet(OUT / "windows_5m.parquet")
tu = dict(zip(w["up_token"], w["cid"])); td = dict(zip(w["down_token"], w["cid"]))
f["cid"] = [tu.get(t) or td.get(t) for t in f["token_id"]]; f["is_up"] = f["token_id"].isin(tu.keys())
f = f.merge(w[["cid", "start_ts", "end_ts", "up_payout"]], on="cid"); f["rel"] = f["ts"] - f["start_ts"]
spd = pd.read_parquet(OUT / "spot_btc_1s.parquet"); sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
res = {}
# (F) first fill of each window within 6 s of the start
fi = f.sort_values("ts").groupby("cid").first().reset_index()
early = fi[fi["rel"] <= 6].copy()
st = early["start_ts"].to_numpy()
strike = sp.mean(st - 60, st)
s_open = sp.last(st)            # last second before the start (published at start)
s_dec = sp.last(early["ts"].to_numpy() - 2)
fu0, _ = fair_up(sp, st, early["end_ts"].to_numpy(), st)
early["val"] = early["start_ts"] >= VAL0
early["r_strike_open"] = np.log(s_open / strike) * 1e4
early["up_rule_open"] = s_open > strike
early["up_rule_dec"] = s_dec > strike
early["fair0"] = fu0
for k, g in early.groupby("val"):
    kk = "validate" if k else "build"
    big = g[np.abs(g["r_strike_open"]) > 3]
    res[f"F_{kk}"] = {"n_first_fill_le6s": len(g), "share_of_active_windows": float(len(g) / max(1, (fi["start_ts"] >= VAL0).sum() if k else (fi["start_ts"] < VAL0).sum())),
                      "side==sign(spot_open - strike)": float((g["is_up"] == g["up_rule_open"]).mean()),
                      "side==sign(spot_at_fill-2 - strike)": float((g["is_up"] == g["up_rule_dec"]).mean()),
                      "same, |gap|>3bp": float((big["is_up"] == big["up_rule_open"]).mean()), "n_big": len(big),
                      "first_wins": float((g["is_up"] == (g["up_payout"] > 0.5)).mean()),
                      "median_price": float(g["price"].median()),
                      "corr(price, fair_open_s)": float(np.corrcoef(g["price"], np.where(g["is_up"], g["fair0"], 1 - g["fair0"]))[0, 1])}
# (G) wallets
f["widx"] = (f["start_ts"] // 300).astype(np.int64)
fw = f.sort_values("ts").groupby("cid").agg(first_wallet=("wallet", "first"), widx=("widx", "first"), nw=("wallet", "nunique"),
                                             start_ts=("start_ts", "first"))
for k, g in fw.groupby(fw["start_ts"] >= VAL0):
    kk = "validate" if k else "build"
    ct = pd.crosstab(g["widx"] % 3, g["first_wallet"].str[:6], normalize="index").round(2)
    res[f"G_{kk}"] = {"n_wallets_per_window": g["nw"].value_counts(normalize=True).round(3).to_dict(),
                      "first_wallet_share": g["first_wallet"].str[:6].value_counts(normalize=True).round(3).to_dict(),
                      "first_wallet_by_widx_mod3": ct.to_dict()}
fs = f.assign(val=f["start_ts"] >= VAL0)
res["G_side_by_wallet"] = {str(k): v for k, v in fs.groupby(["val", fs["wallet"].str[:6]])["is_up"].mean().round(3).to_dict().items()}
res["G_rel_median_by_wallet"] = {str(k): v for k, v in fs.groupby(["val", fs["wallet"].str[:6]])["rel"].median().to_dict().items()}
# within a window, do wallets act in sequence (one after another) or interleave? share of consecutive fills by the same wallet
fs = fs.sort_values(["cid", "ts"])
same = (fs["wallet"].values[1:] == fs["wallet"].values[:-1]) & (fs["cid"].values[1:] == fs["cid"].values[:-1])
cont = fs["cid"].values[1:] == fs["cid"].values[:-1]
res["G_next_fill_same_wallet"] = float(same.sum() / cont.sum())
# null: shuffle wallets within window
rng = np.random.default_rng(0)
sh = fs.groupby("cid")["wallet"].transform(lambda x: rng.permutation(x.values)).values
res["G_next_fill_same_wallet_null"] = float(((sh[1:] == sh[:-1]) & cont).sum() / cont.sum())
print(json.dumps(res, indent=1, default=str))
