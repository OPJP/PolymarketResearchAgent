# Re-walk each of the 19 seconds with limit=500 (what the ascending path does), through an
# HttpClient whose cache is a scratchpad COPY, so the repo cache is untouched.
import json, sys
from pathlib import Path
from collections import Counter
from polyrea.adapters.http import HttpClient, HttpError
from polyrea.adapters.polymarket import DATA_API, PAGE, activity_key
W = Path(sys.argv[1])
http = HttpClient(cache_dir=W / "cache")
walks = json.load(open(W / "walks.json"))
out = []
tot_true = tot_kept = 0
for w in sorted(walks, key=lambda r: r['ts']):
    rows = []
    off = 0
    npages = 0
    while off <= 5000:
        try:
            page, _ = http.get_json(f"{DATA_API}/trades", {"market": w['market'], "takerOnly": "false", "start": w['ts'], "end": w['ts'], "limit": PAGE, "offset": off}, adapter="verify", max_age=None)
        except HttpError as e:
            print("HTTP", e.status, "at offset", off); break
        npages += 1
        rows.extend(page)
        if len(page) < PAGE: break
        off += PAGE
    # what the code kept: the cached no-limit offset=0 page
    kept, _ = http.get_json(f"{DATA_API}/trades", {"market": w['market'], "takerOnly": "false", "start": w['ts'], "end": w['ts'], "offset": 0}, adapter="verify", max_age=None)
    kc = Counter(activity_key(r) for r in kept); tc = Counter(activity_key(r) for r in rows)
    kept_subset = not (kc - tc)
    missing = tc - kc
    miss_rows = [r for r in rows if missing[activity_key(r)] > 0 and not missing.subtract({activity_key(r):1})]
    sides = Counter(r.get('side') for r in miss_rows)
    ts_ok = all(r['timestamp'] == w['ts'] for r in rows)
    print(f"{w['ts']} {w['market'][:12]} true={len(rows)} pages={npages} kept={len(kept)} kept_subset={kept_subset} all_on_ts={ts_ok} missing={sum(missing.values())} sides={dict(sides)}")
    tot_true += len(rows); tot_kept += len(kept)
    out.append(dict(ts=w['ts'], market=w['market'], true=len(rows), kept=len(kept), missing_rows=miss_rows))
print(f"TOTAL: {len(walks)} seconds, true rows {tot_true}, kept {tot_kept}, dropped {tot_true-tot_kept} ({(tot_true-tot_kept)/tot_true:.1%})")
allmiss = [r for o in out for r in o['missing_rows']]
print("missing by side:", Counter(r.get('side') for r in allmiss))
json.dump(out, open(W / "recount.json", "w"))
