"""iteration 18, T16 = X221 light form (information panel I17-2, step 2 only; pre-registered in NOTES.md 13:22 UTC 11-01):
does the paying crowd buy what the page displays? BUILD 10-09..15 BTC 5m windows; crowd = taker BUY prints of wallets that
are neither HFT takers (code/hft_takers3.json) nor cluster accounts. Display (point in time, Binance stand-in): D(t) =
S(t - 1) - K, K = Binance mean of [st - 60, st), S = Binance 1-s close; the displayed winner = Up iff D > 0; a crossing =
a sign change of D inside the window. Per crowd buy: bought the displayed winner? bought the favourite (price > 0.5)?
by seconds since the last crossing ([0, 10), [10, 30), [30, 300), none yet). Reading: in [0, 10) s after a crossing the
displayed-winner share exceeds the favourite share by >= 0.05 with a window-bootstrap 95% interval above 0 -> the crowd
trades on the display (beyond the price); else not shown."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
from features2 import Spot  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
D0, D1 = 1791504000, 1792108800


def main():
    hft = json.loads((HERE.parent / "code" / "hft_takers3.json").read_text())
    hft = {w.lower() for w in (hft if isinstance(hft, list) else hft.get("wallets", hft.keys()))}
    W = pd.read_parquet(C / "windows_5m.parquet")
    W = W[(W.start_ts >= D0) & (W.start_ts < D1)]
    up = dict(zip(W.cid, W.up_token.astype(str)))
    st_of = dict(zip(W.cid, W.start_ts))
    s = pd.read_parquet(C / "spot_btc_1s.parquet").dropna().drop_duplicates("sec").sort_values("sec")
    sp = Spot(s.sec.to_numpy(np.int64), s.px.to_numpy(float))
    rows = []
    for day in range(D0, D1, 86400):
        T = pd.read_parquet(C / f"taker5m_day_{day}.parquet", columns=["cid", "ts", "side", "asset", "price", "wallet"])
        T = T[(T.side == "BUY") & T.cid.isin(set(W.cid)) & ~T.wallet.str.lower().isin(hft | CLUSTER)]
        for cid, g in T.groupby("cid"):
            st = int(st_of[cid])
            K = float(sp.mean(np.array([st - 60]), np.array([st]))[0])
            secs = np.arange(st, st + 300)
            Dser = sp.last(secs - 1) - K  # displayed value at second t uses the close of t - 1 (published ~1 s later)
            sg = np.sign(Dser)
            cross = np.flatnonzero((sg[1:] != sg[:-1]) & (sg[1:] != 0) & (sg[:-1] != 0)) + 1
            ct = secs[cross]
            for t, a, p in zip(g.ts.to_numpy(np.int64), g.asset.astype(str).to_numpy(), g.price.to_numpy(float)):
                if t < st or t >= st + 300:
                    continue
                d = Dser[t - st]
                if d == 0:
                    continue
                isup = a == up[cid]
                j = np.searchsorted(ct, t, side="right") - 1
                since = (t - ct[j]) if j >= 0 else -1
                rows.append((cid, int(isup == (d > 0)), int(p > 0.5), since))
    R = pd.DataFrame(rows, columns=["cid", "disp", "fav", "since"])
    R["bin"] = np.where(R.since < 0, "none", np.where(R.since < 10, "0-10", np.where(R.since < 30, "10-30", "30-300")))
    out = {"crowd_buys": int(len(R)), "windows": int(R.cid.nunique())}
    rng = np.random.default_rng(0)
    for b, g in R.groupby("bin"):
        rec = {"n": int(len(g)), "displayed_winner_share": round(float(g.disp.mean()), 4), "favourite_share": round(float(g.fav.mean()), 4),
               "diff": round(float(g.disp.mean() - g.fav.mean()), 4)}
        cids = g.cid.unique()
        gg = {c: x for c, x in g.groupby("cid")}
        boots = []
        for _ in range(500):
            pick = rng.choice(cids, len(cids), replace=True)
            x = pd.concat([gg[c] for c in pick])
            boots.append(x.disp.mean() - x.fav.mean())
        rec["diff_ci95"] = [round(float(np.quantile(boots, 0.025)), 4), round(float(np.quantile(boots, 0.975)), 4)]
        out[b] = rec
    r0 = out.get("0-10", {})
    out["reading_met"] = bool(r0 and r0["diff"] >= 0.05 and r0["diff_ci95"][0] > 0)
    (HERE.parent / "results" / "iter18_display_crowd.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
