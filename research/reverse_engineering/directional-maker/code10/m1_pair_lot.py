"""Iteration 10 (M1 = X92 and A4 = X100 on the lot): the imbalance pairing bid.
Class (frozen, panel M1): a cluster maker BUY whose calldata original size is not a schedule size and is within 2% of
|own imbalance| (Up minus Down shares the wallet bought in the window before the fill's block second).
(1) side of each class vs the under-held outcome; (2) price rule of the pairing bid: limit price q vs anchors at the
block clock: 1 - held-side VWAP - m, 1 - last own held-side fill price - m; pair cost q + held VWAP; (3) PnL by order
class held to resolution, and the per-window split locked pairs / residual. STUDY (10-23..26) case by case;
VALIDATE (10-27..30) aggregate only."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
     "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
STD = {500, 1000, 250, 125, 100, 62, 50, 12, 300, 40, 200, 2000, 25, 31, 20, 10, 5}


def load_act():
    acts = []
    for w in W.values():
        a = pd.read_parquet(C / f"exam/activity_{w}.parquet",
                            columns=["timestamp", "type", "side", "outcome", "price", "size", "usdcSize", "slug", "transactionHash", "asset"])
        a["wallet"] = w
        acts.append(a)
    A = pd.concat(acts)
    A5 = A[(A.type == "TRADE") & (A.side == "BUY") & A.slug.str.contains("btc-updown-5m-", na=False)].copy()
    A5["st"] = A5.slug.str.split("-").str[-1].astype(int)
    A5["isup"] = A5.outcome == "Up"
    A5["tx"] = A5.transactionHash.str.lower()
    return A5.sort_values("timestamp")


def main():
    A5 = load_act()
    ptb = pd.read_parquet(C / "cl/ptb_lot.parquet")
    fin = {int(s): (1.0 if f > p else 0.0) for s, p, f in zip(ptb.start_ts, ptb.ptb, ptb.final) if np.isfinite(f)}
    out = {}
    for fn, lab, sp in [("b1_cluster_orders_study", "STUDY", "study"), ("b1_cluster_orders_valid", "VALIDATE_aggregate", "validate")]:
        d = pd.read_parquet(C / f"{fn}.parquet", columns=["w", "bts", "taker_amount", "maker_amount", "oside", "role", "tx", "token_id", "lim", "fill_amount"])
        d = d[(d.role == "maker") & (d.oside == 0)].copy()
        d["tx"] = d.tx.str.lower()
        d["token_id"] = d.token_id.astype(str)
        d["orig"] = (d.taker_amount / 1e6).round(2)
        j = A5.drop_duplicates(["tx", "wallet", "asset"])[["tx", "wallet", "st", "isup", "asset"]].copy()
        j["asset"] = j.asset.astype(str)
        d = d.merge(j, left_on=["tx", "w", "token_id"], right_on=["tx", "wallet", "asset"], how="inner")
        G = {k: v for k, v in A5.groupby(["wallet", "st"])}
        inv, vh, lh = [], [], []
        for r in d.itertuples():
            g = G.get((r.wallet, r.st))
            b = g[g.timestamp < r.bts]
            up, dn = b.loc[b.isup, "size"].sum(), b.loc[~b.isup, "size"].sum()
            inv.append(up - dn)
            held = b[b.isup] if up > dn else b[~b.isup]
            hs = held["size"].sum()
            vh.append(held["usdcSize"].sum() / hs if hs > 0 else np.nan)
            lh.append(held["price"].iloc[-1] if len(held) else np.nan)
        d["inv"], d["vwap_held"], d["last_held"] = inv, vh, lh
        d["cls"] = np.where(d.orig.isin(STD), "schedule", "other")
        d["ratio_ok"] = (d.orig / d.inv.abs().replace(0, np.nan) - 1).abs() < 0.02
        d["pair"] = (d.cls == "other") & d.ratio_ok
        d["under"] = np.where(d.inv == 0, np.nan, ((d.inv < 0) == d.isup).astype(float))
        d["win"] = d.st.map(fin)
        d["pay"] = np.where(d.isup, d.win, 1 - d.win)
        grp = np.where(d.pair, "pair", np.where(d.cls == "schedule", "schedule", "other_nonpair"))
        o = {"n": int(len(d)), "share_pair_class": float(d.pair.mean()), "share_other_nonpair": float(((d.cls == "other") & ~d.ratio_ok).mean())}
        o["under_held_by_class"] = {k: float(g.under.mean()) for k, g in d.groupby(grp)}
        p = d[d.pair & d.vwap_held.notna()].copy()
        q = p.lim
        o["pair_price"] = {
            "n": int(len(p)),
            "pair_cost_q_plus_vwap_held_quantiles": {str(x): float((q + p.vwap_held).quantile(x)) for x in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)},
            "q_plus_last_held_quantiles": {str(x): float((q + p.last_held).quantile(x)) for x in (0.1, 0.25, 0.5, 0.75, 0.9)},
            "within_tick_of_1_minus_vwap_held_minus_m": {str(m): float(((q - (1 - p.vwap_held - m)).abs() <= 0.0101).mean()) for m in (0.0, 0.01, 0.02, 0.03, 0.04, 0.05)},
            "within_tick_of_1_minus_last_held_minus_m": {str(m): float(((q - (1 - p.last_held - m)).abs() <= 0.0101).mean()) for m in (0.0, 0.01, 0.02, 0.03, 0.04, 0.05)},
            "share_pair_cost_below_1": float(((q + p.vwap_held) < 1).mean()),
        }
        d["sh"] = d.fill_amount / 1e6
        d["pnl"] = d.sh * (d.pay - d.lim)
        dd = d.dropna(subset=["pay"])
        g2 = np.where(dd.pair, "pair", "nonpair")
        o["pnl_by_class_held_to_resolution"] = {k: {"usd_bought": float((g.sh * g.lim).sum()), "pnl": float(g.pnl.sum()), "ret": float(g.pnl.sum() / (g.sh * g.lim).sum())}
                                                for k, g in dd.groupby(g2)}
        days = (1792713600, 1793059200) if sp == "study" else (1793059200, 1793404800)
        aw = A5[(A5.st >= days[0]) & (A5.st < days[1])].copy()
        aw["win"] = aw.st.map(fin)
        aw = aw.dropna(subset=["win"])
        rows = []
        for (w, st), g in aw.groupby(["wallet", "st"]):
            u, dn = g[g.isup], g[~g.isup]
            su, sd = u["size"].sum(), dn["size"].sum()
            cu, cd = u.usdcSize.sum(), dn.usdcSize.sum()
            m = min(su, sd)
            au, ad = (cu / su if su else 0.0), (cd / sd if sd else 0.0)
            locked = m * (1 - au - ad) if m > 0 else 0.0
            win = g.win.iloc[0]
            total = su * win + sd * (1 - win) - cu - cd
            rows.append((w, st, locked, total - locked, total, cu + cd))
        R = pd.DataFrame(rows, columns=["wallet", "st", "locked", "resid", "total", "cost"])
        o["window_split"] = {"n_windows": int(len(R)), "locked_sum": float(R.locked.sum()), "resid_sum": float(R.resid.sum()),
                             "total_sum": float(R.total.sum()), "cost_sum": float(R.cost.sum()),
                             "var_resid_over_var_total": float(np.var(R.resid) / np.var(R.total)),
                             "var_locked_over_var_total": float(np.var(R.locked) / np.var(R.total)),
                             "corr_total_resid": float(np.corrcoef(R.total, R.resid)[0, 1]),
                             "corr_total_locked": float(np.corrcoef(R.total, R.locked)[0, 1]),
                             "per_wallet": {w: {"locked": float(g.locked.sum()), "resid": float(g.resid.sum())} for w, g in R.groupby("wallet")}}
        out[lab] = o
        if sp == "study":
            d.to_parquet(C / "it10_m1_study.parquet", index=False)
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_m1_pair_lot.json", "w"), indent=1)


if __name__ == "__main__":
    main()
