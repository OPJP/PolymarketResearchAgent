"""iteration 17, T14 = E5 (pre-registered in NOTES.md 11:29 UTC): daily selection (module-on share, BTC 5m fill count)
vs GDELT 'bitcoin' news volume and the Fear & Greed index (previous day = point in time)."""
import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
D0, D1 = 1785542400, 1792627200  # 2026-08-01 .. 2026-10-22 (inclusive days start)


def gdelt():
    f = C / "it17_gdelt_bitcoin.json"
    if f.exists():
        return json.loads(f.read_text())
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    p = {"query": "bitcoin", "mode": "timelinevol", "format": "json", "startdatetime": "20260801000000",
         "enddatetime": "20261022235959"}
    r = httpx.get(url, params=p, timeout=60, headers={"User-Agent": "polyrea/0.1 (research)"})
    out = {"status": r.status_code, "ctype": r.headers.get("content-type"), "text": r.text[:200000]}
    f.write_text(json.dumps(out))
    return out


def fng():
    f = C / "it17_fng.json"
    if f.exists():
        return json.loads(f.read_text())
    r = httpx.get("https://api.alternative.me/fng/", params={"limit": 200, "format": "json"}, timeout=30)
    out = {"status": r.status_code, "text": r.text}
    f.write_text(json.dumps(out))
    return out


def main():
    res = {}
    g = gdelt()
    res["gdelt_status"] = [g["status"], g.get("ctype")]
    gd = None
    try:
        j = json.loads(g["text"])
        rows = j["timeline"][0]["data"]
        gd = pd.DataFrame([(pd.Timestamp(x["date"]).tz_localize(None) if pd.Timestamp(x["date"]).tzinfo else pd.Timestamp(x["date"]), float(x["value"])) for x in rows], columns=["t", "v"])
        gd["day"] = (gd.t.astype("datetime64[s]").astype("int64") // 86400 * 86400).astype(int)
        gd = gd.groupby("day").v.mean()
        res["gdelt_points"] = int(len(rows))
    except Exception as ex:  # noqa: BLE001
        res["gdelt_error"] = repr(ex)[:200] + " | " + g["text"][:200]
    time.sleep(1)
    fg = fng()
    res["fng_status"] = fg["status"]
    fd = None
    try:
        j = json.loads(fg["text"])
        fd = pd.Series({int(x["timestamp"]) // 86400 * 86400: float(x["value"]) for x in j["data"]}).sort_index()
        res["fng_points"] = int(len(fd))
    except Exception as ex:  # noqa: BLE001
        res["fng_error"] = repr(ex)[:200]
    h = pd.read_parquet(C / "it12" / "hist_btc.parquet", columns=["timestamp", "side", "slug"])
    h = h[h.slug.astype(str).str.startswith("btc-updown-5m-") & (h.side == "BUY")]
    st = h.slug.str.rsplit("-", n=1).str[1].astype(int)
    h = h.assign(st=st, day=(st // 86400 * 86400))
    # cached activity after 10-08 for BUILD days 10-09..22
    acts = []
    for nm in ("almach", "bosona", "momoney"):
        a = pd.read_parquet(C / f"activity_{nm}.parquet", columns=["timestamp", "type", "side", "slug"])
        a = a[(a.type == "TRADE") & (a.side == "BUY") & a.slug.astype(str).str.startswith("btc-updown-5m-")]
        acts.append(a)
    a = pd.concat(acts)
    sa = a.slug.str.rsplit("-", n=1).str[1].astype(int)
    a = a.assign(st=sa, day=(sa // 86400 * 86400))
    allf = pd.concat([h[["st", "day"]], a[["st", "day"]]])
    allf = allf[(allf.day >= D0) & (allf.day <= D1) & (allf.st < 1792713600)]
    daily = allf.groupby("day").agg(fills=("st", "size"), win=("st", "nunique"))
    daily["on_share"] = daily.win / 288.0
    days = pd.Index(range(D0, D1 + 86400, 86400))
    daily = daily.reindex(days).fillna(0)
    res["n_days"] = int(len(daily))
    res["on_share_mean"] = round(float(daily.on_share.mean()), 3)
    ind = {}
    if gd is not None:
        gg = gd.reindex(days)
        ind["gdelt_prev"] = gg.shift(1)
        ind["gdelt_same"] = gg
    if fd is not None:
        ff = fd.reindex(days)
        ind["fng_prev"] = ff.shift(1)
        ind["fng_same"] = ff
        ind["abs_dfng_prev"] = ff.diff().abs().shift(1)
    out = {}
    for k, x in ind.items():
        for y in ("on_share", "fills"):
            m = x.notna().to_numpy() & daily[y].notna().to_numpy()
            if m.sum() > 10:
                rho, p = spearmanr(x.to_numpy()[m], daily[y].to_numpy()[m])
                out[f"{k}~{y}"] = [round(float(rho), 3), round(float(p), 4), int(m.sum())]
    res["spearman"] = out
    res["reading_met"] = any(v[0] is not None and abs(v[0]) >= 0.30 and v[1] < 0.01 for k, v in out.items() if "_prev" in k)
    print(json.dumps(res, indent=1))
    (HERE.parent / "results" / "iter17_e5_daily.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
