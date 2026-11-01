"""iteration 17, T5 (pre-registered in NOTES.md 10:57 UTC): the BTC 5m window that starts at the NYSE open (09:30
America/New_York on NYSE trading days) -> the cheaper token. R8 public side vs R8c per fill on the lot's typed fills
(STUDY case by case, VALIDATE aggregate). Also reported: the 13:35 window and the BTC 15m window starting at the open."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"


def nyse_open_utc(day_ts):
    """09:30 America/New_York of the UTC day starting at day_ts, as a UTC timestamp (US DST: 2nd Sunday of March to
    1st Sunday of November); None on weekends."""
    d = datetime.fromtimestamp(day_ts, tz=timezone.utc)
    if d.weekday() >= 5:
        return None
    y = d.year

    def nth_sunday(month, n):
        first = datetime(y, month, 1, tzinfo=timezone.utc)
        off = (6 - first.weekday()) % 7
        return first.timestamp() + (off + 7 * (n - 1)) * 86400

    dst = nth_sunday(3, 2) <= day_ts < nth_sunday(11, 1)
    return int(day_ts + (13 if dst else 14) * 3600 + 1800)


def main():
    V = pd.read_parquet(C / "it12" / "typed_fills.parquet", columns=["st", "en", "is_up", "mid_up", "f_cl", "f_bn", "sp",
                                                                   "day", "price"])
    V = V[(V.en - V.st) == 300].copy()
    y = (V.is_up == 1).to_numpy()
    mid = V.mid_up.to_numpy()
    post = np.where(np.isfinite(V.f_cl) & np.isfinite(mid), V.f_cl > mid, V.f_bn > mid)
    dec = np.abs(mid - 0.5) > 0.4
    cheap = mid < 0.5
    r8 = np.where(dec, cheap, post)
    st = V.st.to_numpy()
    opens = {d: nyse_open_utc(d) for d in np.unique(st // 86400 * 86400)}
    op = np.array([opens[s // 86400 * 86400] is not None and s == opens[s // 86400 * 86400] for s in st])
    op35 = np.array([opens[s // 86400 * 86400] is not None and s == opens[s // 86400 * 86400] + 300 for s in st])
    r8c = np.where(op, cheap, r8)
    ok = np.isfinite(mid)
    out = {}
    for sp in ("study", "validate"):
        ms = (V.sp == sp).to_numpy() & ok
        rec = {"n_all": int(ms.sum()), "r8_all": round(float((r8 == y)[ms].mean()), 4), "r8c_all": round(float((r8c == y)[ms].mean()), 4)}
        for nm, m in (("open", op), ("open+5min", op35)):
            mm = ms & m
            rec[nm] = {"n": int(mm.sum()), "windows": int(len(np.unique(st[mm]))),
                       "r8": round(float((r8 == y)[mm].mean()), 3) if mm.sum() else None,
                       "cheaper": round(float((cheap == y)[mm].mean()), 3) if mm.sum() else None,
                       "posture": round(float((post == y)[mm].mean()), 3) if mm.sum() else None,
                       "mean_price": round(float(V.price.to_numpy()[mm].mean()), 3) if mm.sum() else None}
        if sp == "study":
            rec["open_by_window"] = {str(s): {"n": int((ms & op & (st == s)).sum()),
                                              "cheaper": round(float((cheap == y)[ms & op & (st == s)].mean()), 3),
                                              "r8": round(float((r8 == y)[ms & op & (st == s)].mean()), 3)}
                                     for s in np.unique(st[ms & op])}
        out[sp] = rec
    sig = all(out[sp]["open"]["cheaper"] is not None and out[sp]["open"]["cheaper"] >= 0.75 and
              out[sp]["open"]["cheaper"] - out[sp]["open"]["r8"] >= 0.15 for sp in ("study", "validate"))
    out["signature_met"] = bool(sig)
    out["adopt"] = bool(sig and out["validate"]["r8c_all"] >= out["validate"]["r8_all"])
    out["opens_utc"] = {str(k): v for k, v in opens.items()}
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter17_nyse_open.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
