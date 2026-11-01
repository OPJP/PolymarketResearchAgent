"""iteration 18 (X215, mechanics P1 / assumptions P1): per-day x 5-min UTC slot realised vol of Binance BTCUSDT spot from
1-s klines. rv = sqrt(mean of squared 1-s log returns in the slot) (the same per-second scale as v300 in side_sm /
typed_side), r5 = log return over the slot. Days 08-14..10-07 from the data.binance.vision daily 1s archives (checksum
verified, zip deleted at once); 10-08..10-30 from the cached spot_btc_1s parquet files. Output:
.cache/re/directional-maker/it18/slot_rv.parquet (day, slot, rv, n, r5). Public spot data only."""
import hashlib
import io
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache/re/directional-maker"
OUT = C / "it18" / "slot_rv.parquet"
URL = "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1s/BTCUSDT-1s-{d}.zip"


def table(sec, px, day0):
    sec = np.asarray(sec, np.int64)
    lp = np.log(np.asarray(px, float))
    o = np.argsort(sec)
    sec, lp = sec[o], lp[o]
    r = np.r_[np.nan, np.diff(lp)]
    gap = np.r_[True, np.diff(sec) > 5]
    r[gap] = np.nan
    slot = (sec - day0) // 300
    df = pd.DataFrame({"slot": slot, "r2": r ** 2, "lp": lp, "ok": np.isfinite(r)})
    df = df[(df.slot >= 0) & (df.slot < 288)]
    g = df.groupby("slot")
    rv = np.sqrt(g.r2.sum() / g.ok.sum().clip(lower=1))
    r5 = g.lp.last() - g.lp.first()
    t = pd.DataFrame({"rv": rv, "n": g.ok.sum(), "r5": r5}).reset_index()
    t["day"] = int(day0)
    return t


def from_archive(d: datetime, cl: httpx.Client):
    ds = d.strftime("%Y-%m-%d")
    z = cl.get(URL.format(d=ds), timeout=120)
    z.raise_for_status()
    ck = cl.get(URL.format(d=ds) + ".CHECKSUM", timeout=60)
    ck.raise_for_status()
    want = ck.text.split()[0].strip().lower()
    got = hashlib.sha256(z.content).hexdigest()
    if want != got:
        raise RuntimeError(f"checksum mismatch {ds}")
    with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
        name = zf.namelist()[0]
        raw = pd.read_csv(zf.open(name), header=None, usecols=[0, 4])
    ot = raw[0].to_numpy(np.int64)
    if ot.max() > 1e14:  # microseconds (spot archives from 2025)
        sec = ot // 1_000_000
    else:
        sec = ot // 1000
    return table(sec, raw[4].to_numpy(float), int(d.timestamp()))


def main():
    frames = []
    if OUT.exists():
        frames.append(pd.read_parquet(OUT))
    have = set(frames[0].day.unique()) if frames else set()
    d0 = datetime.fromtimestamp(int(sys.argv[1]), tz=timezone.utc) if len(sys.argv) > 2 else datetime(2026, 8, 14, tzinfo=timezone.utc)
    d1 = datetime.fromtimestamp(int(sys.argv[2]), tz=timezone.utc) if len(sys.argv) > 2 else datetime(2026, 10, 8, tzinfo=timezone.utc)
    with httpx.Client(follow_redirects=True) as cl:
        d = d0
        while d < d1:
            if int(d.timestamp()) not in have:
                for attempt in range(3):
                    try:
                        frames.append(from_archive(d, cl))
                        break
                    except Exception as ex:  # noqa: BLE001
                        print("retry", d.date(), repr(ex)[:120], flush=True)
                print("ok", d.date(), flush=True)
            d += timedelta(days=1)
    a = pd.read_parquet(C / "spot_btc_1s.parquet")
    b = pd.read_parquet(C / "exam" / "spot_btc_1s.parquet")
    s = pd.concat([a, b]).dropna().drop_duplicates("sec").sort_values("sec")
    for day0 in range(1791417600, 1793404800, 86400):  # 10-08 .. 10-30
        if day0 in have:
            continue
        m = (s.sec >= day0) & (s.sec < day0 + 86400)
        if m.sum() > 1000:
            frames.append(table(s.sec[m].to_numpy(), s.px[m].to_numpy(), day0))
    T = pd.concat(frames, ignore_index=True).drop_duplicates(["day", "slot"], keep="last").sort_values(["day", "slot"])
    T.to_parquet(OUT)
    print("days", T.day.nunique(), "rows", len(T), pd.to_datetime(T.day.min(), unit="s"), pd.to_datetime(T.day.max(), unit="s"))


if __name__ == "__main__":
    main()
