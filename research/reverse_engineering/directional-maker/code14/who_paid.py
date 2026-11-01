"""directional-maker iteration 14, X159 (panel iter13 assumptions P4): who paid the profitable version.

Pre-registered sample of iteration 13 (BTC 5m windows of the UTC hours 02/08/14/20; 09-11..10-11 stable version, plus
10-12..22 as the October control; development data only). Every cluster maker BUY fill (cluster trade whose transaction's
taker is not a cluster wallet) is joined to the taker row(s) of the same transaction (data-api taker tape). Taker
populations (fixed before reading the result):
  round_usd   the taker's notional (size x price) within 1% of 1/2/5/10/20/25/50/100/200/250/500/1000 USD
  top20_sep   the 20 taker wallets with the most cluster fill shares in 09-11..10-11 (other than round_usd rows)
  rest        everything else
Reported per week: each population's share of the cluster's maker fill shares and of its held-to-resolution PnL, the
cluster's return against it, and the population's taker volume in the sampled windows; Spearman of the cluster's weekly
return with each population's share.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code14/who_paid.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code13")); sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(ROOT))
import stable_score as ss  # noqa: E402

ROUND = np.array([1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000], float)
CLU = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88",
       "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


def main():
    w = ss.load_windows()
    tk = ss.load_tapes(w)
    ct = ss.load_fills(w)
    win = ss.outcomes(w)
    up_tok = dict(zip(w.cid, w.up_token))
    tk["wallet"] = tk.wallet.astype(str).str.lower()
    tk["cid"] = tk.cid.astype(str)
    taker_tx_cluster = set(tk.loc[tk.wallet.isin(CLU), "tx"])
    f = ct[(ct.side == "BUY") & ~ct.tx.isin(taker_tx_cluster)].copy()
    f = f[f.cid.isin(set(win))]
    f["up"] = [str(t) == str(up_tok[c]) for t, c in zip(f.token_id, f.cid)]
    f["pay"] = [float(win[c] == u) for c, u in zip(f.cid, f.up)]
    f["pnl"] = f.shares * (f.pay - f.price)
    f["cost"] = f.shares * f.price
    tko = tk[~tk.wallet.isin(CLU)].copy()
    tko["notional"] = tko["size"].astype(float) * tko.price.astype(float)
    rel = np.abs(tko.notional.to_numpy()[:, None] / ROUND[None, :] - 1).min(axis=1)
    tko["round_usd"] = rel <= 0.01
    # one taker per transaction (the largest taker row of the tx)
    tko = tko.sort_values("notional", ascending=False).drop_duplicates("tx")
    f = f.merge(tko[["tx", "wallet", "round_usd", "notional", "side"]].rename(columns={"wallet": "taker", "side": "taker_side"}),
                on="tx", how="left")
    f["week"] = pd.to_datetime((f.ts - 1789084800) // (7 * 86400) * (7 * 86400) + 1789084800, unit="s").dt.strftime("%m-%d")
    sep = f[f.ts < 1791763200]
    top = sep[~sep.round_usd.fillna(False).astype(bool)].groupby("taker").shares.sum().sort_values(ascending=False).head(20).index
    f["pop"] = np.where(f.taker.isna(), "unjoined", np.where(f.round_usd.fillna(False).astype(bool), "round_usd",
                                                             np.where(f.taker.isin(set(top)), "top20_sep", "rest")))
    out = {"cluster_maker_buy_fills": int(len(f)), "joined_share": float(f.taker.notna().mean()),
           "windows": int(f.cid.nunique()), "top20": list(top[:20])}
    rows = []
    for wk, g in f.groupby("week"):
        r = {"week": wk, "fills": int(len(g)), "cluster_return": float(g.pnl.sum() / g.cost.sum()), "cluster_pnl": float(g.pnl.sum())}
        for p, gg in g.groupby("pop"):
            r[f"{p}_share_shares"] = float(gg.shares.sum() / g.shares.sum())
            r[f"{p}_share_pnl"] = float(gg.pnl.sum() / g.pnl.sum()) if g.pnl.sum() != 0 else None
            r[f"{p}_return"] = float(gg.pnl.sum() / gg.cost.sum())
            r[f"{p}_pnl"] = float(gg.pnl.sum())
        rows.append(r)
    R = pd.DataFrame(rows)
    out["by_week"] = R.round(4).to_dict("records")
    # market-wide taker volume of each population in the sampled windows (shares), per week
    tko["week"] = pd.to_datetime((tko.ts - 1789084800) // (7 * 86400) * (7 * 86400) + 1789084800, unit="s").dt.strftime("%m-%d")
    tko["pop"] = np.where(tko.round_usd, "round_usd", np.where(tko.wallet.isin(set(top)), "top20_sep", "rest"))
    vol = tko.groupby(["week", "pop"])["size"].sum().unstack().fillna(0)
    out["taker_volume_by_week"] = (vol.div(vol.sum(axis=1), axis=0)).round(4).to_dict("index")
    out["taker_volume_abs_by_week"] = vol.round(0).to_dict("index")
    sp = {}
    for p in ("round_usd", "top20_sep", "rest"):
        c = f"{p}_share_shares"
        if c in R:
            sp[p] = float(pd.Series(R.cluster_return).corr(R[c], method="spearman"))
    out["spearman_weekly_return_vs_share"] = sp
    tot = {}
    for fold, (a, b) in (("sep_stable", (1789084800, 1791763200)), ("oct_control", (1791763200, 1792713600))):
        g = f[(f.ts >= a) & (f.ts < b)]
        tot[fold] = {p: {"share_shares": float(gg.shares.sum() / g.shares.sum()), "share_pnl": float(gg.pnl.sum() / g.pnl.sum()),
                         "return": float(gg.pnl.sum() / gg.cost.sum()), "pnl": float(gg.pnl.sum())} for p, gg in g.groupby("pop")}
        tot[fold]["all"] = {"return": float(g.pnl.sum() / g.cost.sum()), "pnl": float(g.pnl.sum()), "fills": int(len(g))}
    out["by_fold"] = tot
    # the favourite/underdog split by population (cheaper token = bought below 0.5)
    out["cheaper_share_by_pop_fold"] = {fold: f[(f.ts >= a) & (f.ts < b)].assign(ch=lambda d: d.price < 0.5).groupby("pop").ch.mean().round(3).to_dict()
                                        for fold, (a, b) in (("sep_stable", (1789084800, 1791763200)), ("oct_control", (1791763200, 1792713600)))}
    (HERE.parent / "results" / "iter14_who_paid.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if k != "top20"}, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
