"""Iteration 9 (also BTC 15m: python code9/vol_hist.py <split> 15m) (panels iter8: information I8-1/I8-2 = X74/X75, mechanics M1 = X79): which volatility does the posture
use? Historical replication on the block clock, BTC 5m.

Unit: every cluster maker BUY fill in a BTC 5m window. Predicted side: Up iff Phi(ln(S/K) / (k sigma sqrt(tau))) >
mid_up, with (block clock, point-in-time at b - 2 where b is the fill's block second)
  S = Binance spot 1-s close of second b - 3 (the lot's Chainlink stream is smooth: Chainlink fair vs Binance fair corr
      0.988, iteration 7, so Binance stands in for the report here; the basis cancels because K is Binance too),
  K = mean Binance spot over [st - 60, st) (TWAP-60 strike),
  tau = en - (b - 2) (>= 1 s),
  mid_up = the last clean print of the window (ts <= b - 3; prints in any cluster transaction removed), Down prints
      mapped to 1 - p,
  sigma = the pre-registered family below, from Binance spot 1-s log returns ending at second b - 3.
Family (pre-registered in NOTES iteration 9 before this ran): realised v_L, L in {120, 300, 900, 1800, 3600, 7200};
EWMA half-life {300, 900, 1800, 3600}; min(1.4 v300, c v3600) c in {1.0, 1.4}; v3600 frozen at the window open; scale
k in {0.8, 1.0, 1.2, 1.4}.
Writes one per-fill table per split (BUILD, STUDY, VALIDATE). VALIDATE (10-27..30) is aggregate only: this script
prints nothing per fill.
    python code9/vol_hist.py build|study|validate
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import lfilter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache" / "re" / "directional-maker"
OUTD = C / "it9"
OUTD.mkdir(parents=True, exist_ok=True)
CLUSTER = ["0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"]
SPLITS = {"build": (1791504000, 1792713600), "study": (1792713600, 1793059200), "validate": (1793059200, 1793404800)}


def load_spot():
    a = pd.read_parquet(C / "spot_btc_1s.parquet")
    b = pd.read_parquet(C / "exam" / "spot_btc_1s.parquet")
    s = pd.concat([a, b]).drop_duplicates("sec").sort_values("sec")
    base = int(s.sec.iloc[0])
    n = int(s.sec.iloc[-1]) - base + 1
    px = np.full(n, np.nan)
    px[s.sec.to_numpy() - base] = s.px.to_numpy()
    idx = np.where(~np.isnan(px), np.arange(n), 0)
    np.maximum.accumulate(idx, out=idx)
    return base, px[idx]


def vol_tables(px):
    lp = np.log(px)
    r = np.diff(lp, prepend=lp[0])
    r2 = r * r
    cs = np.concatenate([[0.0], np.cumsum(r2)])  # cs[i+1] = sum r2[0..i]
    out = {}

    def rv(L):
        i = np.arange(len(r))
        lo = np.maximum(i + 1 - L, 0)
        return np.sqrt((cs[i + 1] - cs[lo]) / np.maximum(i + 1 - lo, 1))
    for L in (120, 300, 900, 1800, 3600, 7200):
        out[f"v{L}"] = rv(L).astype(np.float32)
    for hl in (300, 900, 1800, 3600):
        lam = 0.5 ** (1.0 / hl)
        zi = [lam * np.mean(r2[:3600])]
        e, _ = lfilter([1 - lam], [1, -lam], r2, zi=zi)
        out[f"e{hl}"] = np.sqrt(e).astype(np.float32)
    return out


def main(split, fam_="5m"):
    a, b = SPLITS[split]
    base, px = load_spot()
    V = vol_tables(px)
    if fam_ == "15m":
        f = pd.read_parquet(C / "p15" / "cluster_btc15m_fills.parquet")
        f["txh"] = f.tx.astype(str).str.lower()
        w = pd.read_parquet(C / "t15" / "windows_15m.parquet")
        tape_dir = C / "t15"
        acts = [C / f"activity_{n}.parquet" for n in ("bosona", "almach", "momoney")] + [C / "exam" / f"activity_{n}.parquet" for n in ("bosona", "almach", "momoney")]
    elif split == "build":
        f = pd.read_parquet(C / "cluster_btc5m_fills.parquet")
        f["txh"] = f.tx.str.lower()
        w = pd.read_parquet(C / "windows_5m.parquet")
        tape_dir, acts = C, [C / f"activity_{n}.parquet" for n in ("bosona", "almach", "momoney")]
    else:
        f = pd.read_parquet(C / "exam" / "fills_holdout.parquet")
        f["txh"] = f.txh.str.lower()
        w = pd.read_parquet(C / "exam" / "windows_5m.parquet")
        tape_dir, acts = C / "exam", [C / "exam" / f"activity_{n}.parquet" for n in ("bosona", "almach", "momoney")]
    f = f[(f.role == "maker") & (f.side == "BUY") & (f.ts >= a) & (f.ts < b)].copy()
    cl_tx = set(f.txh)
    for p in acts:
        g = pd.read_parquet(p, columns=["transactionHash"])
        cl_tx |= set(g.transactionHash.str.lower())
    w = w.set_index("cid")
    rows = []
    for day in range(a, b, 86400):
        p = tape_dir / (f"taker15m_day_{day}.parquet" if fam_ == "15m" else f"taker5m_day_{day}.parquet")
        if not p.exists():
            print("missing tape", p.name, flush=True)
            continue
        t = pd.read_parquet(p, columns=["cid", "ts", "asset", "price", "tx"])
        t = t[~t.tx.str.lower().isin(cl_tx)]
        fd = f[(f.ts >= day) & (f.ts < day + 86400)]
        tg = {k: g.sort_values("ts", kind="stable") for k, g in t.groupby("cid")}
        for cid, g in fd.groupby("cid"):
            if cid not in w.index or cid not in tg:
                continue
            ww = w.loc[cid]
            st, en, up = int(ww.start_ts), int(ww.end_ts), str(ww.up_token)
            tp = tg[cid]
            pts = tp.ts.to_numpy()
            pup = np.where(tp.asset.astype(str).to_numpy() == up, tp.price.to_numpy(float), 1.0 - tp.price.to_numpy(float))
            i0 = st - 60 - base
            if i0 < 3700:
                continue
            K = float(px[i0:st - base].mean())
            for r in g.itertuples(index=False):
                bs = int(r.ts)
                j = np.searchsorted(pts, bs - 3, side="right") - 1
                if j < 0 or pts[j] < st - 60:
                    continue
                ii = bs - 3 - base
                rec = dict(day=day, wallet=r.wallet, cid=cid, txh=str(r.txh), token=str(r.token_id), st=st, en=en, b=bs, is_up=int(str(r.token_id) == up),
                           price=float(r.price), shares=float(r.shares), mid_up=float(pup[j]), age=int(bs - pts[j]),
                           S=float(px[ii]), K=K, tau=float(max(en - (bs - 2), 1)),
                           v3600_open=float(V["v3600"][st - 1 - base]), payout_up=float(ww.up_payout))
                for k_, arr in V.items():
                    rec[k_] = float(arr[ii])
                rows.append(rec)
        print(split, pd.to_datetime(day, unit="s").date(), len(rows), flush=True)
    D = pd.DataFrame(rows)
    D.to_parquet(OUTD / (f"volhist15_{split}.parquet" if fam_ == "15m" else f"volhist_{split}.parquet"))
    print("saved", len(D), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "5m")
