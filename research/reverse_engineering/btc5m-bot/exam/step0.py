"""Examiner r1, step 0: sufficiency from LISTING METADATA only (no fills, no outcomes, no tapes).
Run with POLYREA_CACHE_DIR=.cache/exam/btc5m-bot. Writes results/exam_r1_step0.json.
- lot h1 intervals from tools/sealed.py
- listed BTC 5m windows per lot day (Gamma; only cid / start / end / tokens are read here)
- halves split by listing start time (earlier / later), before any fill is read
- seeded sample for the truncation test (seed 20261101), drawn from the listing."""
import os, sys, json, time
assert os.environ.get("POLYREA_CACHE_DIR", "").replace("\\", "/").endswith(".cache/exam/btc5m-bot"), "set POLYREA_CACHE_DIR"
ROOT = os.getcwd()
sys.path.insert(0, ROOT); sys.path.insert(0, f"{ROOT}/research/reverse_engineering/tools")
import numpy as np, pandas as pd
import sealed as S
from polyrea.workflows.updown_study import fetch_windows, window_slugs

KEY = "btc5m-bot"
LOT = [(1792713600, 1792800000), (1792886400, 1792972800), (1793059200, 1793145600), (1793232000, 1793318400)]
out = {"lot": "h1", "intervals": LOT}
try:
    iv = S.intervals(KEY, 1792713600, 1793404800, sealed=True)
    out["sealed_intervals_10_23_to_10_31"] = [list(map(int, x)) for x in iv]
except Exception as e:
    out["sealed_intervals_error"] = repr(e)[:200]
rows = []
for a, b in LOT:
    slugs = window_slugs("btc", "5m", a, b)
    mk = fetch_windows(slugs)
    for cid, m in mk.items():
        st = pd.Timestamp(m.get("eventStartTime")).timestamp() if m.get("eventStartTime") else None
        en = pd.Timestamp(m.get("endDate")).timestamp() if m.get("endDate") else None
        rows.append({"cid": cid, "slug": m.get("slug"), "start_ts": int(st) if st else None, "end_ts": int(en) if en else None})
    print(time.strftime("%Y-%m-%d", time.gmtime(a)), "slugs", len(slugs), "listed", len(mk), flush=True)
L = pd.DataFrame(rows).dropna().drop_duplicates("cid").sort_values("start_ts").reset_index(drop=True)
L = L[np.any([(L.start_ts >= a) & (L.start_ts < b) for a, b in LOT], axis=0)].reset_index(drop=True)
out["windows_listed"] = int(len(L))
out["windows_expected"] = 4 * 288
out["by_day"] = {time.strftime("%Y-%m-%d", time.gmtime(a)): int(((L.start_ts >= a) & (L.start_ts < b)).sum()) for a, b in LOT}
mid = len(L) // 2
cut = int(L.start_ts.iloc[mid])
out["halves"] = {"rule": "windows sorted by listed start time; earlier half = first n/2", "cut_start_ts": cut,
                 "first": [int(L.start_ts.iloc[0]), int(L.start_ts.iloc[mid - 1])], "second": [cut, int(L.start_ts.iloc[-1])],
                 "n_first": int(mid), "n_second": int(len(L) - mid)}
rng = np.random.default_rng(20261101)
pick = np.sort(rng.choice(len(L), 12, replace=False))
samp = L.iloc[pick][["cid", "slug", "start_ts"]].copy()
samp["decision_rels"] = [sorted(rng.choice(np.arange(5, 295), 20, replace=False).tolist()) for _ in range(len(samp))]
out["truncation_sample"] = {"seed": 20261101, "windows": samp.to_dict("records")}
# power statement (listing only): per-window correlation SE at n windows (iid), and at 2-h blocks
n = len(L)
out["power"] = {"windows": n, "two_hour_blocks": int(len(np.unique(L.start_ts // 7200))),
                "se_r_at_0.5_iid": round((1 - 0.25) / np.sqrt(n), 4), "se_r_at_0.5_iid_half": round((1 - 0.25) / np.sqrt(n / 2), 4),
                "note": "iid SE of a Pearson r near 0.5; blocks inflate it; the AUC SE on ~10^5 positive block seconds is < 0.002"}
os.makedirs("research/reverse_engineering/btc5m-bot/results", exist_ok=True)
L.to_parquet(".cache/exam/btc5m-bot/lot_listing.parquet", index=False)
json.dump(out, open("research/reverse_engineering/btc5m-bot/results/exam_r1_step0.json", "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in out.items() if k != "truncation_sample"}, indent=1, default=str))
