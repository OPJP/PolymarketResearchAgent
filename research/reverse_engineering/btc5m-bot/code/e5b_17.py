"""Iteration 17, E5 first screen (corrected: GDELT returns daily bins for a 14-day span, so each dated change / outage gets its own
24-h query at 15-min resolution). Per event and query ('polymarket', 'bitcoin'): GDELT DOC 2.0 timelinevolraw over [event - 12 h,
event + 12 h); the event's rank = share of the window's 15-min bins whose volume share is below the max of the 3 bins around the
event (+-15 min). Under no link the ranks are ~U(0, 1); reported: ranks, their mean and a one-sided uniform-sum p. Development time
only (all events before H). Usage: python e5b_17.py"""
import os, sys, json, math
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT)
from polyrea.adapters.http import HttpClient
cl = HttpClient(rates={"api.gdeltproject.org": 0.2}, timeout=60.0, max_retries=3)
EV = {"10-13 14:10 XM share drop": "2026-10-13 14:10", "10-19 01:00 size phase on": "2026-10-19 01:00", "10-19 13:00 size phase off": "2026-10-19 13:00",
      "10-20 19:00 size phase": "2026-10-20 19:00", "10-21 16:00 dispatch phase on": "2026-10-21 16:00", "10-22 13:00 dispatch phase off": "2026-10-22 11:00",
      "outage 10-09 09:35": "2026-10-09 09:35", "outage 10-11 12:35": "2026-10-11 12:35", "outage 10-12 09:15": "2026-10-12 09:15", "outage 10-21 07:15": "2026-10-21 07:15"}
res = {"source": "GDELT DOC 2.0 timelinevolraw, 24-h windows, 15-min bins", "ranks": {}}
for q in ("polymarket", "bitcoin"):
    rk = {}
    for k, v in EV.items():
        t = pd.Timestamp(v)
        a, b = (t - pd.Timedelta(hours=12)).strftime("%Y%m%d%H%M%S"), (t + pd.Timedelta(hours=12)).strftime("%Y%m%d%H%M%S")
        try:
            js, _ = cl.get_json("https://api.gdeltproject.org/api/v2/doc/doc", {"query": q, "mode": "timelinevolraw", "format": "json", "startdatetime": a, "enddatetime": b}, adapter="gdelt", max_age=None)
            d = js.get("timeline", [{}])[0].get("data", [])
            df = pd.DataFrame([{"t": pd.Timestamp(x["date"]).tz_localize(None) if pd.Timestamp(x["date"]).tzinfo else pd.Timestamp(x["date"]), "v": float(x["value"]), "n": float(x.get("norm", 0) or 0)} for x in d])
            if len(df) < 20:
                rk[k] = {"bins": int(len(df)), "rank": None}; continue
            x = (df.v / df.n.where(df.n > 0)).fillna(0).to_numpy()
            i = int(np.searchsorted(df.t.to_numpy(), np.datetime64(t.floor("15min")), "left"))
            ev = float(np.max(x[max(i - 1, 0): i + 2]))
            rk[k] = {"bins": int(len(df)), "rank": round(float((x < ev).mean()), 4)}
        except Exception as e:
            rk[k] = {"error": repr(e)[:200]}
    r = [v["rank"] for v in rk.values() if v.get("rank") is not None]
    n = len(r); s_ = sum(r)
    # Irwin-Hall upper tail for the sum of n uniforms (one-sided: events sit at news peaks)
    p = None
    if n:
        p = sum(((-1) ** j) * math.comb(n, j) * max(n - s_ - j, 0) ** n for j in range(n + 1)) / math.factorial(n)
        p = 1 - p if False else p
        # P(sum >= s_) = P(sum <= n - s_) by symmetry
        p = sum(((-1) ** j) * math.comb(n, j) * max((n - s_) - j, 0) ** n for j in range(n + 1)) / math.factorial(n)
    res["ranks"][q] = rk; res[f"{q}_mean_rank"] = round(float(np.mean(r)), 4) if r else None; res[f"{q}_p_upper"] = round(float(p), 4) if p is not None else None
    print(q, res[f"{q}_mean_rank"], res[f"{q}_p_upper"], {k: v.get("rank", v.get("error", "")) for k, v in rk.items()}, flush=True)
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/e5_17.json", "w"), indent=1, default=str)
