"""Iteration 19, X191 out-of-time point (pre-registration 20b, written 11-01 ~14:25 UTC before the run): knee19d's clock-free statistic
E on the first out-of-time decision record (11-01 06:00-09:30, Sunday: CME Globex closed all day until 23:00 UTC). Binance spot trades
from the live lab feed btc5m_bnspot2 by exchange time T only; operator first legs (DS / GF / XM taker BUY orders, 300-ms rule) at the
live lab's server-ms matches (oot17's construction). Prediction (Globex account): E at the closed level, <= 0.65 (capture closed
0.54, open 0.99); reaction peak 250-270 ms. Usage: python oot19b.py IT17_DIR"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live, sealed
from knee19b import events
LAGS = np.arange(-500, 1000, 10)


def main():
    S17 = sys.argv[1]
    win = pd.read_parquet(f"{S17}/post17_windows.parquet"); fl = pd.read_parquet(f"{S17}/post17_fills.parquet"); xr = pd.read_parquet(f"{S17}/post17_xms.parquet")
    assert not any(sealed.is_sealed(int(t), "btc5m-bot") for t in win.start_ts)
    o = fl[(fl.role == "T") & (fl.side == 0) & fl.wallet.isin(["DS", "GF", "XM"])].copy(); o["tx"] = o.tx.str.lower()
    o = o.drop_duplicates(["tx", "wallet", "token"]); o["m"] = o.tx.map(xr.dropna(subset=["s"]).groupby("tx").s.min())
    o = o[o.m.notna()].copy(); o["m"] = o.m.astype(np.int64)
    o = o.sort_values(["cid", "is_up", "m"]); new = (o.cid != o.cid.shift()) | (o.is_up != o.is_up.shift()) | (o.m - o.m.shift() >= 300)
    f = o[new]
    M = f.m.to_numpy(np.int64); Y = np.where(f.is_up.to_numpy(bool), 1, -1)
    a_ts, b_ts = int(win.start_ts.min()) - 120, int(win.end_ts.max()) + 10
    T, p = [], []
    for r in live.iter_live("btc5m_bnspot2", a_ts, b_ts):
        if r.get("k") == "x":
            T.append(r["T"]); p.append(float(r["p"]))
    T = np.asarray(T, np.int64); oo = np.argsort(T, kind="stable"); T = T[oo]; p = np.asarray(p)[oo]
    lo, hi = int(T[0]) + 61000, int(T[-1])
    te, se, iso = events(T, p, int(T[0]), hi)
    k = (te >= lo) & (iso == 1); te, se = te[k], se[k]
    om = np.argsort(M); ms_, ys_ = M[om], Y[om]
    a = np.searchsorted(ms_, te - 500, "left"); b = np.searchsorted(ms_, te + 1000, "left")
    early = peak = 0.0; h = np.zeros(len(LAGS))
    for i in range(len(te)):
        lag = ms_[a[i]:b[i]] - te[i]; sg = np.where(ys_[a[i]:b[i]] == se[i], 1.0, -1.0)
        early += sg[(lag >= 0) & (lag < 230)].sum(); peak += sg[(lag >= 230) & (lag < 320)].sum()
        np.add.at(h, ((lag + 500) // 10).astype(int), sg)
    sm = np.convolve(h, np.ones(3) / 3, "same")
    res = {"prereg": "20b", "first_legs": int(len(f)), "isolated_trade_jumps": int(len(te)), "excess_early_0_230": early, "excess_reaction_230_320": peak,
           "E": round(early / peak, 3) if peak > 0 else None, "peak_lag_ms": int(LAGS[int(np.argmax(sm))]), "prediction_E_le_0.65": bool(peak > 0 and early / peak <= 0.65),
           "trade_msgs": int(len(T))}
    print(json.dumps(res, indent=1))
    json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/oot19b.json", "w"), indent=1)


if __name__ == "__main__":
    main()
