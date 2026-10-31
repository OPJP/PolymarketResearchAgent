"""Unused data source check: Binance BTCUSDT 1-s klines from the public archive data.binance.vision (reachable from
this host although the Binance API is geo-blocked). (a) Lead-lag of 1-s log returns, Binance vs the Kraken series the
project uses. (b) The btc5m-cluster H4 maker match (signed 2-s spot return toward the bought side, spot L s old)
re-scored with Binance instead of Kraken, for GF/XM/DS and mo-money, FIT and TEST, 100-draw spot-clock-shift null.
A Binance second s is treated as available at s+1 (same availability_lag=1 convention as the Kraken series)."""
import sys, json, pickle, zipfile, glob, io
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
sys.path.insert(0, "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-btc5m-cluster")
import numpy as np, pandas as pd
from grid import Grid
from polyrea.analysis.updown import auc, SpotIndex
from polyrea.pit import TimeSeries
OUT = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/completeness-critic"
frames = []
for f in sorted(glob.glob(f"{OUT}/dl_binance/*.zip")):
    z = zipfile.ZipFile(f)
    with z.open(z.namelist()[0]) as fh:
        df = pd.read_csv(fh, header=None, usecols=[0, 4], names=["ot", "close"])
    frames.append(df)
B = pd.concat(frames).sort_values("ot").drop_duplicates("ot")
bts = (B.ot.to_numpy() // 1_000_000).astype(np.int64); bpx = B.close.to_numpy(float)
bspot = SpotIndex(TimeSeries.build("binance", zip(bts.tolist(), bpx.tolist()), availability_lag=1))
d = pickle.load(open("/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-btc5m-cluster/slim.pkl", "rb"))
W = {"GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9",
     "mo-money": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
res = {"binance_seconds": int(len(bts)), "leadlag": {}, "h4": {}}
for per in ("fit", "test"):
    kspot = Grid(d[per]).spot
    # (a) lead-lag over the sampled blocks
    secs = np.concatenate([np.arange(b[0] if isinstance(b, (tuple, list)) else b, (b[0] if isinstance(b, (tuple, list)) else b) + 7200) for b in d[per]["blocks"]])
    kr = np.diff(np.log(kspot.price_at(secs))); br = np.diff(np.log(bspot.price_at(secs)))
    ok = np.isfinite(kr) & np.isfinite(br)
    kr, br = kr[ok], br[ok]
    cc = {}
    for lag in range(-6, 7):  # corr(binance_t, kraken_{t+lag}); positive lag peak => Binance leads Kraken
        if lag >= 0: a, b = br[: len(br) - lag], kr[lag:]
        else: a, b = br[-lag:], kr[: len(kr) + lag]
        cc[lag] = round(float(np.corrcoef(a, b)[0, 1]), 4)
    res["leadlag"][per] = cc
    print(per, "leadlag corr(binance_t, kraken_t+lag)", cc, flush=True)
    # (b) H4 score with each feed
    P = d[per]["maker_prints"]; P = P[(P.ts - P.start_ts >= 0) & (P.ts - P.start_ts < 300)].reset_index(drop=True)
    side = P.is_up.to_numpy(); ts0 = P.ts.to_numpy()
    def sret(spot, L, sh=0, k=2):
        t = ts0 - L + sh; r = np.log(spot.price_at(t) / spot.price_at(t - k)); return np.where(side, r, -r)
    rng = np.random.default_rng(11)
    shifts = [int(rng.integers(3600, 21600)) * int(rng.choice([-1, 1])) for _ in range(100)]
    res["h4"][per] = {}
    for n, w in W.items():
        y = (P.wallet == w).to_numpy().astype(int)
        r = {"fills": int(y.sum())}
        for feed, spot in (("kraken", kspot), ("binance", bspot)):
            for L in (0, 1, 2, 3, 5):
                a = auc(sret(spot, L), y)
                if L in (2, 3, 5):
                    null = np.array([auc(sret(spot, L, sh=s), y) for s in shifts]); null = null[np.isfinite(null)]
                    r[f"{feed}_L{L}"] = {"auc": round(float(a), 4), "null_max": round(float(null.max()), 4), "perm_p": round(float((1 + (null >= a).sum()) / (1 + len(null))), 4)}
                else:
                    r[f"{feed}_L{L}"] = {"auc": round(float(a), 4)}
        res["h4"][per][n] = r
        print(per, n, json.dumps(r), flush=True)
json.dump(res, open(f"{OUT}/binance_h4.json", "w"), indent=1)
