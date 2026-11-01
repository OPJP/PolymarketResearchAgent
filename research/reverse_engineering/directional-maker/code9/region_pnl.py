"""Iteration 9 (V9 / D4): where does the cluster's BTC 5m maker PnL come from? Per fill (block-clock tables of
code9/vol_hist.py; VALIDATE aggregate only): region D (Binance reference and the market disagree on the favourite) vs
region A (they agree), and within A favourite vs underdog fills; PnL held to resolution = shares x (payout - price)."""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
C = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker/it9"
for split in ("build", "study", "validate"):
    D = pd.read_parquet(C / f"volhist_{split}.parquet")
    x = np.log(D.S / D.K).to_numpy(); m = D.mid_up.to_numpy(); y = D.is_up.to_numpy() == 1
    pay = np.where(y, D.payout_up.to_numpy(), 1 - D.payout_up.to_numpy())
    pnl = D.shares.to_numpy() * (pay - D.price.to_numpy()); cost = D.shares.to_numpy() * D.price.to_numpy()
    regA = np.sign(x) == np.sign(m - 0.5)
    fav = (m > 0.5) == y
    refside = (x > 0) == y
    def row(lab, g):
        return f"{lab:24s} n={g.sum():6d} cost=${cost[g].sum():9.0f} pnl=${pnl[g].sum():8.0f} ret={pnl[g].sum()/max(cost[g].sum(),1):+.3f}"
    print("==", split, row("all", np.ones(len(D), bool)))
    print("  ", row("D (disagree)", ~regA)); print("  ", row("D, bought ref side", ~regA & refside)); print("  ", row("D, bought mkt fav", ~regA & ~refside))
    print("  ", row("A (agree)", regA)); print("  ", row("A, favourite", regA & fav)); print("  ", row("A, underdog", regA & ~fav))
