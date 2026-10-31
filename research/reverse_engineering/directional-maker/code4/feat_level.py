"""Queue-mechanics features (iteration 4): age of the current bid level on side s and how often it changed, from the
clean taker tape (prints that hit a bid on s: taker SELL s or taker BUY the other token). Point-in-time: prints with
ts < bin start. Output: .cache/re/directional-maker/level_feats.parquet keyed by (cid, side_up, rel)."""
import glob, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache/re/directional-maker"
W = ["0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"]
NAMES = ["bosona", "almach", "momoney"]
REL = np.arange(0, 300, 10)


def cluster_txs():
    s = set()
    for n in NAMES:
        for p in (C / f"activity_{n}.parquet", C / f"exam/activity_{n}.parquet"):
            if p.exists():
                s |= set(pd.read_parquet(p, columns=["transactionHash"]).transactionHash)
    return s


def main():
    ctx = cluster_txs()
    wins = pd.concat([pd.read_parquet(C / "windows_5m.parquet", columns=["cid", "start_ts", "up_token"]),
                      pd.read_parquet(C / "exam/windows_5m.parquet", columns=["cid", "start_ts", "up_token"])]).drop_duplicates("cid")
    wmap = wins.set_index("cid")
    files = sorted(glob.glob(str(C / "taker5m_day_*.parquet"))) + sorted(glob.glob(str(C / "exam/taker5m_day_*.parquet")))
    out = []
    for f in files:
        t = pd.read_parquet(f, columns=["cid", "ts", "side", "asset", "price", "wallet", "tx"])
        t = t[~t.tx.isin(ctx) & ~t.wallet.isin(W) & t.cid.isin(wmap.index)]
        t = t.join(wmap, on="cid")
        is_up = (t.asset == t.up_token).to_numpy(); buy = (t.side.astype(str) == "BUY").to_numpy()
        t["up_px"] = np.where(is_up, t.price, 1 - t.price).round(3)
        t["hit_up_bid"] = (is_up & ~buy) | (~is_up & buy)
        for cid, g in t.sort_values("ts", kind="stable").groupby("cid", sort=False):
            st = int(g.start_ts.iloc[0]); tb = st + REL
            for s_up in (1, 0):
                h = g[g.hit_up_bid == bool(s_up)]
                ts = h.ts.to_numpy(); px = h.up_px.to_numpy() if s_up else (1 - h.up_px.to_numpy()).round(3)
                n = len(ts)
                if n == 0:
                    age = np.full(len(REL), np.nan); ch10 = np.zeros(len(REL)); ch30 = np.zeros(len(REL)); lv = np.full(len(REL), np.nan)
                else:
                    chg = np.concatenate([[True], px[1:] != px[:-1]])
                    run_start_ts = pd.Series(np.where(chg, ts, np.nan)).ffill().to_numpy()
                    cum = np.cumsum(chg)
                    i = np.searchsorted(ts, tb, side="left") - 1
                    ok = i >= 0
                    age = np.where(ok, tb - run_start_ts[np.clip(i, 0, n - 1)], np.nan)
                    lv = np.where(ok, px[np.clip(i, 0, n - 1)], np.nan)
                    def cnt(k):
                        j = np.searchsorted(ts, tb - k, side="left") - 1
                        a = np.where(i >= 0, cum[np.clip(i, 0, n - 1)], 0); b = np.where(j >= 0, cum[np.clip(j, 0, n - 1)], 0)
                        return a - b
                    ch10, ch30 = cnt(10), cnt(30)
                out.append(pd.DataFrame({"cid": cid, "side_up": s_up, "rel": REL, "lvl_age": age.astype(np.float32),
                                         "lvl_px": lv.astype(np.float32), "lvl_ch10": ch10.astype(np.float32), "lvl_ch30": ch30.astype(np.float32)}))
        print(Path(f).name, flush=True)
    pd.concat(out, ignore_index=True).to_parquet(C / "level_feats.parquet")


if __name__ == "__main__":
    main()
