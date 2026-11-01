"""Iteration 12, X117 (a) (information I11-4): Deribit front-expiry ATM implied vol per 6-h block as the engine's sigma
source. history.deribit.com public/get_last_trades_by_currency_and_time (kind option, BTC), 10-09..30 (development + the
released lot; VALIDATE blocks only as block aggregates). Front expiry = the nearest expiry >= 1 h after the trade (Deribit
expiries settle 08:00 UTC); ATM = strike within 2% of the index. Per block: median IV (annualised %), converted to a
per-sqrt-second vol. Compared with (1) the block favourite share F_b of the cluster's BTC 5m BUY fills (it12/hist_blocks)
and its realised vol, and (2) the per-block best multiplier k_b of iteration 11 (iter11_k_by_day.json by_block, real
Chainlink, lot) through sd(log(k_b x rv_b / iv_b)) vs sd(log k_b).
    python code12/deribit_iv.py
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import HttpClient  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
URL = "https://history.deribit.com/api/v2/public/get_last_trades_by_currency_and_time"
D0, D1 = 1791504000, 1793404800
MON = {m: i + 1 for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def expiry_ts(name):
    m = re.match(r"BTC-(\d{1,2})([A-Z]{3})(\d{2})-(\d+)-([CP])", name)
    if not m:
        return None, None
    d, mo, y, k = int(m.group(1)), MON[m.group(2)], 2000 + int(m.group(3)), float(m.group(4))
    return int(pd.Timestamp(year=y, month=mo, day=d, hour=8, tz="UTC").timestamp()), k


def main():
    h = HttpClient()
    rows = []
    for b0 in range(D0, D1, 21600):
        t = b0 * 1000
        end = (b0 + 21600) * 1000
        n = 0
        while t < end and n < 40:
            d, _ = h.get_json(URL, {"currency": "BTC", "kind": "option", "start_timestamp": t, "end_timestamp": end - 1, "count": 1000, "sorting": "asc"},
                              adapter="deribit.history", max_age=None)
            r = d.get("result", {}) if isinstance(d, dict) else {}
            tr = r.get("trades", [])
            n += 1
            for x in tr:
                ex, k = expiry_ts(x.get("instrument_name", ""))
                if ex is None:
                    continue
                ts = x["timestamp"] / 1000
                if ex - ts < 3600 or not x.get("iv"):
                    continue
                rows.append((b0, ts, ex, k, float(x["index_price"]), float(x["iv"])))
            if not tr or not r.get("has_more"):
                break
            t = int(tr[-1]["timestamp"]) + 1
    T = pd.DataFrame(rows, columns=["blk", "ts", "ex", "k", "idx", "iv"])
    T["atm"] = (T.k / T.idx - 1).abs() <= 0.02
    front = T.groupby("blk").ex.transform("min")
    F = T[T.atm & (T.ex == front)]
    iv = F.groupby("blk").iv.median()
    Bk = pd.read_parquet(C / "it12" / "hist_blocks.parquet")
    df = pd.DataFrame({"iv": iv}).join(Bk[["F", "rv", "n"]], how="inner")
    df["iv_s"] = df.iv / 100 / np.sqrt(365 * 86400)
    out = {"blocks": int(len(df)), "trades": int(len(T)), "front_atm_trades": int(len(F)),
           "spearman_F_vs_log_iv": round(float(df.F.corr(np.log(df.iv), method="spearman")), 3),
           "spearman_F_vs_log_rv": round(float(df.F.corr(np.log(df.rv), method="spearman")), 3),
           "spearman_iv_vs_rv": round(float(np.log(df.iv).corr(np.log(df.rv), method="spearman")), 3)}
    try:
        kb = json.loads((HERE.parent / "results" / "iter11_k_by_day.json").read_text())["by_block"]
        recs = []
        for key, v in kb.items():
            ts_ = pd.Timestamp(f"2026-{key[:5]} {key[6:8]}:00", tz="UTC").timestamp()
            bk = v.get("best_k") if isinstance(v, dict) else None
            if bk:
                recs.append((int(ts_), float(bk)))
        K = pd.DataFrame(recs, columns=["blk", "k"]).set_index("blk").join(df, how="inner")
        if len(K) > 5:
            out["k_blocks"] = int(len(K))
            out["sd_log_k"] = round(float(np.log(K.k).std()), 3)
            out["sd_log_k_rv_over_iv"] = round(float(np.log(K.k * K.rv / K.iv_s).std()), 3)
            out["spearman_k_vs_log_iv"] = round(float(K.k.corr(np.log(K.iv), method="spearman")), 3)
    except Exception as ex:  # noqa: BLE001
        out["k_join_error"] = repr(ex)[:200]
    lot = df.index >= 1793059200
    out["mean_iv_build_study"] = round(float(df.iv[~lot].mean()), 2)
    out["mean_iv_validate_aggregate"] = round(float(df.iv[lot].mean()), 2)
    (HERE.parent / "results" / "iter12_deribit_iv.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
