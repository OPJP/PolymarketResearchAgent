"""Iteration 9 (assumptions B2 = X84): the settlement-source natural experiment on the Binance-settled BTC hourly markets
of the development block 10-31 12:00-18:00 (8am-1pm ET). Per cluster maker BUY fill (block clock b): mid_up = last clean
print of the market at ts <= b - 3 (data-api tape, prints in cluster transactions removed); Binance fair = Phi(ln(BN(b-3)
/ BN_open) / (sigma sqrt(tau))) with BN_open = Binance BTCUSDT at the hour start (the candle open settles the market);
Chainlink fair = the same with the Chainlink report at b-3 and at the hour start; sigma = v3600 of Binance spot; tau to
the hour end. Scores sign(fair - mid) for both references and their disagreement share (the power of the experiment)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code"))
import cl_source  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
A, B = 1793448000, 1793469600
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


def main():
    act = pd.read_parquet(C / "it9" / "act_1793448000_1793469600.parquet")
    act = act[(act.type == "TRADE") & act.slug.str.contains(r"bitcoin-up-or-down-october-31-2026-\d+(am|pm)-et", regex=True, na=False)].copy()
    act["tx"] = act.transactionHash.str.lower()
    pm = PolymarketData()
    sp = pd.read_parquet(C / "it9" / f"spot1s_rest_{A - 7200}_{B}.parquet").sort_values("sec")
    b0 = int(sp.sec.iloc[0])
    px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan)
    px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    rr = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(rr * rr)]
    rows = []
    for slug, g in act.groupby("slug"):
        hh = slug.rsplit("-", 2)[-2]
        h24 = int(hh[:-2]) % 12 + (12 if hh.endswith("pm") else 0)
        st = int(pd.Timestamp(f"2026-10-31 {h24:02d}:00", tz="US/Eastern").timestamp())
        en = st + 3600
        cid = g.conditionId.iloc[0]
        tr, _, _ = pm.market_trades(cid, st - 600, en, taker_only=True)
        T = pd.DataFrame(tr)
        if not len(T):
            continue
        T["tx"] = T.transactionHash.str.lower()
        T = T[~T.tx.isin(set(act.tx)) & ~T.proxyWallet.str.lower().isin(CLUSTER)].sort_values("timestamp")
        up_tok = None
        for o, a_ in zip(T.outcome, T.asset):
            if str(o).lower() == "up":
                up_tok = str(a_)
                break
        if up_tok is None:
            continue
        pts = T.timestamp.to_numpy()
        pup = np.where(T.asset.astype(str).to_numpy() == up_tok, T.price.astype(float).to_numpy(), 1 - T.price.astype(float).to_numpy())
        bn_open = px[st - 1 - b0]
        stamps = sorted({st} | {int(t) - 3 for t in g.timestamp})
        clv = cl_source.cl_values(stamps, allow_sealed=False, fetch=True, max_requests=200)
        for r in g.itertuples(index=False):
            if r.side != "BUY":
                continue
            bs = int(r.timestamp)
            j = np.searchsorted(pts, bs - 3, side="right") - 1
            if j < 0:
                continue
            i = bs - 3 - b0
            sg = np.sqrt((cs[i + 1] - cs[i + 1 - 3600]) / 3600)
            tau = max(en - (bs - 2), 1.0)
            fb = norm.cdf(np.log(px[i] / bn_open) / (sg * np.sqrt(tau)))
            c0, c1 = clv.get(st), clv.get(bs - 3)
            fc = norm.cdf(np.log(c1 / c0) / (sg * np.sqrt(tau))) if (c0 and c1) else np.nan
            rows.append(dict(slug=slug, b=bs, is_up=int(str(r.asset) == up_tok), mid=float(pup[j]), fb=fb, fc=fc,
                             basis=(c1 - px[i]) if c1 else np.nan))
    D = pd.DataFrame(rows)
    y = D.is_up.to_numpy() == 1
    ok = D.fc.notna().to_numpy()
    out = {"fills": int(len(D)), "markets": int(D.slug.nunique()), "with_chainlink": int(ok.sum()),
           "acc_binance_fair": float(np.mean(((D.fb > D["mid"]).to_numpy() == y)[ok])),
           "acc_chainlink_fair": float(np.mean(((D.fc > D["mid"]).to_numpy() == y)[ok])),
           "refs_disagree_share": float(np.mean(((D.fb > D["mid"]) != (D.fc > D["mid"])).to_numpy()[ok])),
           "cheaper_side": float(np.mean(((D["mid"] < 0.5).to_numpy() == y))), "always_up": float(y.mean()),
           "median_abs_fair_gap": float(np.median(np.abs(D.fb - D.fc)[ok])), "median_cl_minus_bn_usd": float(np.nanmedian(D.basis)),
           "per_market": D.groupby("slug").apply(lambda d: {"n": int(len(d)), "bought_up": float(d.is_up.mean())}).to_dict()}
    print(json.dumps(out, indent=1, default=float))
    (HERE.parent / "results" / "iter9_b2_hourly.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
