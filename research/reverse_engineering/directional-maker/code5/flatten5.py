"""P4 (panel X13): exit by buying the complement. STUDY case by case, VALIDATE aggregate.

For each cluster BTC 5m taker BUY fill: the wallet's own maker inventory in that window just before it (Up and Down
shares bought), whether it buys the side it holds less of, size / imbalance, pair cost (taker price + average cost of
the held side), time in window, and whether a MERGE of that window follows. PnL split of paired shares into
maker-maker pairs and flatten pairs (pairs completed by a taker buy).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache" / "re" / "directional-maker"
OUT = ROOT / "research" / "reverse_engineering" / "directional-maker" / "results"
W = {"bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
     "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}

f = pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["wallet", "txh", "token_id", "ts", "side", "price", "shares", "cid", "role"])
win = pd.read_parquet(C / "exam" / "windows_5m.parquet").set_index("cid")
f = f[f.cid.isin(win.index) & (f.side == "BUY")]
f["start"] = f.cid.map(win.start_ts)
f["up"] = f.token_id == f.cid.map(win.up_token)
f["won"] = np.where(f.up, f.cid.map(win.up_payout), 1 - f.cid.map(win.up_payout))
merges = []
for n, addr in W.items():
    a = pd.read_parquet(C / "exam" / f"activity_{n}.parquet")
    m = a[a.type == "MERGE"][["timestamp", "conditionId", "size"]].assign(wallet=addr)
    merges.append(m)
merges = pd.concat(merges)
mset = {(r.wallet, r.conditionId): r.timestamp for r in merges.itertuples()}

res = {}
for name, (a0, b0) in (("study", (1792713600, 1793059200)), ("validate", (1793059200, 1793404800))):
    g = f[(f.start >= a0) & (f.start < b0)].sort_values(["wallet", "cid", "ts"], kind="stable")
    ev = []
    pnl_rows = []
    for (wal, cid), h in g.groupby(["wallet", "cid"], sort=False):
        up_sh = dn_sh = up_c = dn_c = 0.0
        for r in h.itertuples(index=False):
            if r.role == "taker":
                held_up = up_sh > dn_sh
                gap = abs(up_sh - dn_sh)
                buys_less = (r.up and not held_up) or ((not r.up) and held_up)
                avg_held = (up_c / up_sh if held_up and up_sh else dn_c / dn_sh if dn_sh else np.nan)
                ev.append({"rel": r.ts - r.start, "gap": gap, "size": r.shares, "buys_less": bool(buys_less and gap > 0),
                           "ratio": r.shares / gap if gap > 0 else np.nan, "pair_cost": r.price + avg_held if buys_less else np.nan,
                           "merge_after": (wal, cid) in mset and mset[(wal, cid)] >= r.ts, "won": r.won, "price": r.price})
            if r.up:
                up_sh += r.shares; up_c += r.shares * r.price
            else:
                dn_sh += r.shares; dn_c += r.shares * r.price
        # paired vs directional PnL; paired shares split by whether the pair completion used taker buys
        hm = h[h.role == "maker"]
        mu, md = hm[hm.up].shares.sum(), hm[~hm.up].shares.sum()
        pnl_rows.append({"paired_all": min(up_sh, dn_sh), "paired_maker_only": min(mu, md),
                         "pnl_total": float(((h.won - h.price) * h.shares).sum()),
                         "pnl_taker": float(((h.won - h.price) * h.shares)[h.role == "taker"].sum()),
                         "pair_cost_all": (up_c / up_sh + dn_c / dn_sh) if up_sh and dn_sh else np.nan})
    e = pd.DataFrame(ev)
    p = pd.DataFrame(pnl_rows)
    out = {"taker_buys": int(len(e))}
    if len(e):
        el = e[e.buys_less]
        out.update({"share_buys_side_held_less": float(e.buys_less.mean()),
                    "flatten_n": int(len(el)),
                    "ratio_median": float(el.ratio.median()), "ratio_p25_p75": [float(el.ratio.quantile(.25)), float(el.ratio.quantile(.75))],
                    "exact_size_share(0.98-1.02)": float(el.ratio.between(0.98, 1.02).mean()),
                    "pair_cost_median": float(el.pair_cost.median()), "pair_cost_p10_p90": [float(el.pair_cost.quantile(.1)), float(el.pair_cost.quantile(.9))],
                    "rel_median": float(el.rel.median()), "merge_after_share": float(el.merge_after.mean()),
                    "taker_pnl_usd": float(((e.won - e.price) * e["size"]).sum())})
    out.update({"windows": int(len(p)), "paired_shares_all": float(p.paired_all.sum()), "paired_shares_maker_only": float(p.paired_maker_only.sum()),
                "pnl_total": float(p.pnl_total.sum()), "pnl_from_taker_fills": float(p.pnl_taker.sum())})
    res[name] = out
    print(name, json.dumps(out))
(OUT / "iter5_flatten.json").write_text(json.dumps(res, indent=1))
