"""Iteration 10: compact daily table of the version scans (results/version10b.json, version10c.json).
Usage: python version10_table.py"""
import os, json
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
for f in ("version10b.json", "version10c.json"):
    p = os.path.join(R, f)
    if not os.path.exists(p):
        continue
    d = json.load(open(p))
    for k, v in d.items():
        if "share_signed_in_bursts" not in v:
            print(k, v); continue
        sizes = {}
        for w, z in v["sizes_top"].items():
            if w == "W4":
                continue
            for s_, n in z.items():
                sizes[s_] = sizes.get(s_, 0) + n
        top = sorted(sizes.items(), key=lambda x: -x[1])[:3]
        print(f"{k:5s} txs/h {v['txs_in_hour']:5d} in_bursts {v['share_signed_in_bursts']:.2f} taker_order_share {v['role_T_share']:.2f} sizes {[(int(float(a)), b) for a, b in top]}")
