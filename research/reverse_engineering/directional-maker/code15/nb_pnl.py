"""iteration 15, T1c: where the non-BTC module's money is (Binance stand-in settlement; development folds only).
Outcome of each window: Up iff S(end) > K on the same Binance series as the strike (hourly/daily exact; Chainlink TWAP
families approximated by the Binance 60-s mean before the end vs the TWAP-60 strike). Return per $ = (payout - p) / p,
size-weighted, by family group x phase x fold, and the opening rule's own replay: buy the in-the-money outcome at the
cluster's fill price (shows whether the open's edge is the strike gap)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from nb_side import Spot, C, RES
a = pd.read_parquet(C / "it15_nb_side.parquet")
sp = Spot()
win = a.drop_duplicates("slug")[["slug", "fam", "sym", "st", "L", "K"]].reset_index(drop=True)
end = (win.st + win.L).to_numpy(np.int64)
se = np.full(len(win), np.nan)
for sym, g in win.groupby("sym"):
    e = end[g.index]
    tw = g.fam.str.contains(r"-(?:5m|15m|4h)$").to_numpy()
    v_tw = sp.twap60(sym, e)            # mean of the 60 s before the end (stand-in for the Chainlink TWAP settlement)
    v_cl = sp.close_at(sym, e - 1)      # Binance close at the end (hourly 1h candle close; daily noon 1m close ~)
    se[g.index] = np.where(tw, v_tw, v_cl)
win["SE"] = se
a = a.merge(win[["slug", "SE"]], on="slug", how="left")
a["win_up"] = np.where(np.isfinite(a.SE) & np.isfinite(a.K), (a.SE >= a.K).astype(float), np.nan)
a = a[a.win_up.notna() & (a.timestamp < 1793520000)]
a["pay"] = np.where(a.up == a.win_up, 1.0, 0.0)
a["cost"] = a.price * a["size"]; a["pnl"] = (a.pay - a.price) * a["size"]
fg = a.fam.str.replace(r"^(eth|sol|xrp|bnb|doge)-(5m|15m)$", r"alt-\2", regex=True).str.replace(r"^\w+-4h$", "4h", regex=True).str.replace(r"^\w+-hourly$", "hourly", regex=True).str.replace(r"^\w+-daily$", "daily", regex=True)
a["fg"] = np.where(a.btc_core, a.fam, fg)
a["fd"] = np.where(a.fold.str.startswith("STUDY"), "STUDY", a.fold)
g = a.groupby(["fg", "fd", "phase"]).agg(n=("pnl", "size"), cost=("cost", "sum"), pnl=("pnl", "sum"), win=("pay", "mean")).reset_index()
g["ret"] = (g.pnl / g.cost).round(4)
g2 = a[~a.btc_core].groupby(["fd", "phase"]).agg(n=("pnl", "size"), cost=("cost", "sum"), pnl=("pnl", "sum"), win=("pay", "mean")).reset_index(); g2["ret"] = (g2.pnl / g2.cost).round(4)
# itm-rule hit vs miss returns on the opening fills
op = a[(~a.btc_core) & (a.phase == "open<20s") & a.rule_ok.notna()]
g3 = op.groupby(["fd", "rule_ok"]).agg(n=("pnl", "size"), cost=("cost", "sum"), pnl=("pnl", "sum")).reset_index(); g3["ret"] = (g3.pnl / g3.cost).round(4)
print(g2.round(3).to_string(index=False)); print(g3.round(3).to_string(index=False))
print(g[g.n >= 40].round(3).to_string(index=False))
(RES / "iter15_nb_pnl.json").write_text(json.dumps({"by_fold_phase": g2.to_dict("records"), "open_by_rule": g3.to_dict("records"), "by_family": g.to_dict("records")}, indent=1, default=float))
