"""Iteration 9, replication of the PnL test-retest ceiling (pnlceil9.py, X69) on the 10-31 DEVELOPMENT blocks (00-06 and
12-18 UTC; windows starting in them), where q = P(fill | decision) was measured live (0.69-0.70, ins9b). Outcomes from Gamma
/events (outcomePrices of development windows, settlement only; every slug asserted development before the request). Per order:
x_d = shares x (payout - price) - fee + 0.5 fee (taker rebate). r = 1 - (1 - q) kappa, kappa = E[sum x_d^2] / Var(window PnL).
Usage: python pnlceil9b.py OUT_JSON"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT); sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import sealed
from polyrea.adapters.polymarket import PolymarketData, GAMMA_API
import pnlceil9

C = _ROOT + "/.cache/re/btc5m-bot"
EX = {"0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"}
W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
BLOCKS = ((1793404800, 1793426400), (1793448000, 1793469600))


def main(out):
    starts = [s for a, b in BLOCKS for s in range(a, b, 300)]
    for s in starts:
        assert not sealed.is_sealed(s, "btc5m-bot"), s
    pm = PolymarketData()
    pay = {}; wst = {}
    slugs = [f"btc-updown-5m-{s}" for s in starts]
    for i in range(0, len(slugs), 25):
        part = slugs[i:i + 25]
        d, _ = pm.http.get_json(f"{GAMMA_API}/events", [("slug", s) for s in part] + [("limit", 50)], adapter="gamma.events", max_age=7 * 86400)
        for e in d or []:
            for m in e.get("markets") or []:
                try:
                    toks = json.loads(m.get("clobTokenIds") or "[]"); px = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
                    outs = json.loads(m.get("outcomes") or "[]")
                except Exception:
                    continue
                if len(toks) == 2 and len(px) == 2 and max(px) > 0.99:
                    for t, p_, o_ in zip(toks, px, outs):
                        pay[str(t)] = p_; wst[str(t)] = int(str(e.get("slug")).rsplit("-", 1)[1])
    print("tokens with outcome", len(pay), flush=True)
    f = pd.concat([pd.read_parquet(C + "/post/own_1793404800_1793426400.parquet"), pd.read_parquet(C + "/it9/own_1231_12_18.parquet")]).drop_duplicates(["tx", "li"])
    f["token"] = f.token.astype(str)
    f["payout"] = f.token.map(pay)
    f = f[f.payout.notna()].copy()
    f["wallet"] = f.owner.map(W); f["role"] = np.where(f.cp.isin(EX), "T", "M")
    f["shares"] = f.tamt / 1e6; f["price"] = f.mamt / f.tamt; f["fee_usd"] = f.fee / 1e6
    f["x"] = f.shares * (f.payout - f.price) - f.fee_usd + 0.5 * f.fee_usd * (f.role == "T")
    f["w"] = f.token.map(wst)
    f = f[f.w.isin(starts)].copy()
    o = f.groupby("oh", sort=False).agg(wallet=("wallet", "first"), w=("w", "min"), x=("x", "sum"), sh=("shares", "sum")).reset_index()
    res = {"windows_with_outcome": int(o.w.nunique()), "orders": int(len(o)), "fills": int(len(f))}
    per = pnlceil9.kappa_stats(o)
    res["pooled"] = pnlceil9.ceiling(per); res["pooled"]["split_half_emp"] = pnlceil9.split_half(o, draws=100)
    res["pooled"]["boot_r_q0.70"] = pnlceil9.boot(per, 0.70, n=1000)
    res["by_wallet"] = {}
    for wl in ("DS", "GF", "XM"):
        pw = pnlceil9.kappa_stats(o, wl)
        res["by_wallet"][wl] = pnlceil9.ceiling(pw); res["by_wallet"][wl]["split_half_emp"] = pnlceil9.split_half(o, wl, draws=100)
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
