"""Exit / inventory decode (B4, B5, E6): in-play share, pair completion, net inventory paths, final unpaired
inventory vs outcome and vs market price at acquisition. Development data (16 Oct .. H)."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import H, OUT, RES, WALLET, SPLIT  # noqa: E402

def main():
    cd = pd.read_parquet(OUT / "calldata_all.parquet")
    w = cd[cd["maker"] == WALLET].copy()
    w["role"] = np.where(w["idx"] == -1, "taker", "maker")
    w["usd"] = w["fill"] * w["price"]
    m = json.load(open(OUT / "markets_dev.json"))
    win = {}
    for cid, x in m.items():
        op = x.get("outcomePrices"); op = json.loads(op) if isinstance(op, str) else op
        try:
            win[cid] = int(np.argmax([float(v) for v in op])) if op and max(float(v) for v in op) > 0.9 else -1
        except Exception:
            win[cid] = -1
    w["rel"] = w["bts"] - w["gs_ts"]
    res = {"fills": len(w), "usd": round(float(w.usd.sum()), 0)}
    res["share_fills_pregame"] = round(float((w.rel < 0).mean()), 3)
    res["rel_min_quantiles"] = (w.rel / 60).quantile([.01, .05, .25, .5, .75, .95, .99]).round(1).to_dict()
    res["role_usd_share"] = (w.groupby("role").usd.sum() / w.usd.sum()).round(3).to_dict()
    per = []
    for cid, g in w.sort_values("bts").groupby("cid"):
        a = g[g.oi == 0]; b = g[g.oi == 1]
        sa, sb = a.fill.sum(), b.fill.sum()
        ca, cb = a.usd.sum(), b.usd.sum()
        pairs = min(sa, sb)
        avg_a = ca / sa if sa else np.nan; avg_b = cb / sb if sb else np.nan
        net = sa - sb
        # running net inventory (shares of outcome 0 minus outcome 1) and its max abs
        s = np.where(g.oi == 0, g.fill, -g.fill).cumsum()
        wv = win.get(cid, -1)
        payoff = (sa if wv == 0 else 0) + (sb if wv == 1 else 0) if wv >= 0 else np.nan
        per.append({"cid": cid, "gs": g.gs_ts.iloc[0], "smt": g.smt.iloc[0], "sa": sa, "sb": sb, "pairs": pairs,
                    "pair_cost": avg_a + avg_b if sa and sb else np.nan, "net": net, "max_abs_net": np.abs(s).max(),
                    "cost": ca + cb, "payoff": payoff, "pnl": payoff - (ca + cb) if wv >= 0 else np.nan, "win": wv,
                    "n": len(g), "taker_usd": g.loc[g.role == 'taker', 'usd'].sum()})
    p = pd.DataFrame(per)
    p["unpaired"] = p["net"].abs()
    p["unpaired_won"] = np.where(p.win < 0, np.nan, np.where(((p.net > 0) & (p.win == 0)) | ((p.net < 0) & (p.win == 1)), 1, 0))
    res["markets"] = len(p)
    res["pair_cost_wavg"] = round(float((p.pair_cost * p.pairs).sum() / p.pairs[p.pair_cost.notna()].sum()), 4)
    res["pair_cost_q"] = p.pair_cost.quantile([.1, .25, .5, .75, .9]).round(3).to_dict()
    res["paired_share_of_shares"] = round(float(2 * p.pairs.sum() / (p.sa.sum() + p.sb.sum())), 3)
    res["unpaired_over_maxabs_q"] = (p.unpaired / p.max_abs_net.replace(0, np.nan)).quantile([.25, .5, .75]).round(3).to_dict()
    res["unpaired_won_rate"] = round(float(p.unpaired_won.mean()), 3)
    res["pnl_total"] = round(float(p.pnl.sum()), 0)
    res["pnl_locked_pairs"] = round(float((p.pairs * (1 - p.pair_cost)).sum()), 0)
    res["pnl_by_split"] = {"BUILD": round(float(p.loc[p.gs < SPLIT, "pnl"].sum()), 0), "VALIDATE": round(float(p.loc[p.gs >= SPLIT, "pnl"].sum()), 0)}
    res["pnl_by_smt"] = p.groupby("smt").pnl.sum().round(0).to_dict()
    res["share_markets_pnl_pos"] = round(float((p.pnl > 0).mean()), 3)
    res["taker_usd_share"] = round(float(p.taker_usd.sum() / p.cost.sum()), 3)
    p.to_parquet(OUT / "per_market.parquet", index=False)
    json.dump(res, open(RES / "results/inventory.json", "w"), indent=1)
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
