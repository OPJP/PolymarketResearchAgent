"""Iteration 2: outcome metrics on VALIDATE from the presence predictions (val_pred_presence.parquet):
per-window PnL correlation between the rule and the cluster, for (a) the iteration-1 hard proxy (flag p >= 0.30, buy
30 shares at the last implied ask) and (b) a soft proxy (expected position = p * 30 shares at the last implied ask).
Wallet PnL is before rebates: shares * (payout - price) - fee."""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
FEE = 0.07; SH = 30.0; P_THRESH = 0.30


def outcome(cells, fills, win, pcol="p_y"):
    c = cells[np.isfinite(cells.ask_o) & (cells.ask_o > 0.05) & (cells.ask_o < 0.95)].merge(win[["cid", "up_payout"]], on="cid")
    pay = np.where(c.is_up, c.up_payout, 1 - c.up_payout)
    unit = pay - c.ask_o - FEE * c.ask_o * (1 - c.ask_o)
    c["pnl_hard"] = np.where(c[pcol] >= P_THRESH, SH * unit, 0.0); c["usd_hard"] = np.where(c[pcol] >= P_THRESH, SH * c.ask_o, 0.0)
    c["pnl_soft"] = c[pcol] * SH * unit; c["usd_soft"] = c[pcol] * SH * c.ask_o
    c["net_soft"] = np.where(c.is_up, 1, -1) * c[pcol] * SH
    rw = c.groupby("cid")[["pnl_hard", "pnl_soft", "usd_hard", "usd_soft", "net_soft"]].sum()
    f = fills[fills.cid.isin(set(cells.cid))].copy()
    f["pay"] = np.where(f.is_up, f.up_payout, 1 - f.up_payout)
    f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd
    f["net"] = np.where(f.is_up, 1, -1) * f.shares
    ww = f.groupby("cid").agg(pnl=("pnl", "sum"), usd=("usdc", "sum"), net=("net", "sum"))
    b = rw.join(ww, how="outer").fillna(0.0)
    return {
        "windows": int(len(b)),
        "pnl_corr_hard_pearson": round(float(b.pnl_hard.corr(b.pnl)), 4), "pnl_corr_hard_spearman": round(float(b.pnl_hard.corr(b.pnl, method="spearman")), 4),
        "pnl_corr_soft_pearson": round(float(b.pnl_soft.corr(b.pnl)), 4), "pnl_corr_soft_spearman": round(float(b.pnl_soft.corr(b.pnl, method="spearman")), 4),
        "net_position_corr_soft": round(float(b.net_soft.corr(b.net)), 4),
        "rule_return_hard": round(float(b.pnl_hard.sum() / b.usd_hard.sum()), 4), "rule_return_soft": round(float(b.pnl_soft.sum() / b.usd_soft.sum()), 4),
        "wallet_return_before_rebates": round(float(b.pnl.sum() / b.usd.sum()), 4),
    }


if __name__ == "__main__":
    v = pd.read_parquet(f"{C}/val_pred_presence.parquet"); f = pd.read_parquet(f"{C}/fills.parquet"); w = pd.read_parquet(f"{C}/windows.parquet")
    f = f.merge(w[["cid"]], on="cid")
    out = outcome(v, f, w)
    print(out)
    json.dump(out, open(f"{R}/results_outcome_iter2.json", "w"), indent=1)
