"""Examiner r1: the wallets' economics on the h1 lot from their on-chain fills (no rule involved): per window complete-set pairing
(pairs = min(up, down) shares; pair cost = avg up + avg down price), locked vs unpaired PnL, fees, taker vs maker PnL per share, and the
50% taker-fee rebate the wallets receive; per day and per wallet. Usage: python an_econ.py OUT_JSON"""
import os, sys, json, glob
ARGS = sys.argv[1:]
ROOT = os.getcwd()
import numpy as np, pandas as pd
EX = f"{ROOT}/.cache/exam/btc5m-bot"
LOT = [(1792713600, 1792800000), (1792886400, 1792972800), (1793059200, 1793145600), (1793232000, 1793318400)]


def main(out_json):
    FL = []
    for p in sorted(glob.glob(f"{EX}/chunks/*_*/fills.parquet")):
        a = int(os.path.basename(os.path.dirname(p)).split("_")[0])
        if any(x <= a < y for x, y in LOT):
            FL.append(pd.read_parquet(p))
    f = pd.concat(FL, ignore_index=True)
    f["pay"] = np.where(f.is_up, f.up_payout, 1 - f.up_payout); f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd
    out = {"fills": int(len(f)), "usdc": round(float(f.usdc.sum()), 1), "shares": round(float(f.shares.sum()), 1)}
    def econ(g):
        w = g.groupby(["cid", "is_up"]).agg(sh=("shares", "sum"), usd=("usdc", "sum")).unstack(fill_value=0.0)
        up_sh, dn_sh = w[("sh", True)] if ("sh", True) in w else 0, w[("sh", False)] if ("sh", False) in w else 0
        up_usd, dn_usd = w[("usd", True)] if ("usd", True) in w else 0, w[("usd", False)] if ("usd", False) in w else 0
        pairs = np.minimum(up_sh, dn_sh)
        with np.errstate(invalid="ignore", divide="ignore"):
            pc = np.where(pairs > 0, up_usd / up_sh + dn_usd / dn_sh, np.nan)
        locked = np.nansum(pairs * (1 - pc))
        return {"windows": int(len(w)), "pnl_before_rebates": round(float(g.pnl.sum()), 1), "usdc": round(float(g.usdc.sum()), 1),
                "return_before_rebates": round(float(g.pnl.sum() / g.usdc.sum()), 5), "fees": round(float(g.fee_usd.sum()), 1),
                "taker_fees": round(float(g[g.role == "T"].fee_usd.sum()), 1),
                "return_with_50pct_taker_fee_rebate": round(float((g.pnl.sum() + 0.5 * g[g.role == "T"].fee_usd.sum()) / g.usdc.sum()), 5),
                "paired_share_of_shares": round(float(2 * pairs.sum() / g.shares.sum()), 4), "share_weighted_pair_cost": round(float(np.nansum(pc * pairs) / pairs.sum()), 4) if pairs.sum() else None,
                "locked_pnl_gross_of_fees": round(float(locked), 1), "unpaired_pnl_gross_of_fees": round(float(g.pnl.sum() + g.fee_usd.sum() - locked), 1),
                "taker_pnl_per_share_after_fees": round(float(g[g.role == "T"].pnl.sum() / g[g.role == "T"].shares.sum()), 5) if (g.role == "T").any() else None,
                "maker_pnl_per_share": round(float(g[g.role == "M"].pnl.sum() / g[g.role == "M"].shares.sum()), 5) if (g.role == "M").any() else None,
                "maker_share_of_usdc": round(float(g[g.role == "M"].usdc.sum() / g.usdc.sum()), 4)}
    out["pool"] = econ(f)
    out["by_wallet"] = {w: econ(g) for w, g in f.groupby("wallet")}
    out["by_day"] = {pd.Timestamp(a, unit="s").strftime("%Y-%m-%d"): econ(f[(f.start_ts >= a) & (f.start_ts < b)]) for a, b in LOT}
    json.dump(out, open(out_json, "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main(ARGS[0])
