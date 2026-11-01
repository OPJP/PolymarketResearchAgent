"""X221 (information panel iter-15 P3, the key-free part of X219): vendor fingerprint from pre-game messages.
Pre-registered in NOTES iteration 16. 16-22 Oct (before H), wallet-free taker orders of group P / group G members on the
books of the wallet's events (calldata record). Cluster = >= 2 distinct members signing within 300 ms of the first.
Rate per minute by time to the event's scheduled start, against a null that shifts each member's take times by an
independent +-30..60 s (200 draws); concentration: share of each event's pre-start clusters in its busiest 3-min window.
LLF-like iff pre-start rate >= 3x null AND >= half of the clusters of the events with any sit in one 3-min window 5-30
min before the start. Output: results/pregame_clusters.json"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
CODE = ROOT / "research/reverse_engineering/tommy-cs2-maker/code"
sys.path.insert(0, str(CODE / "iter4"))
sys.path.insert(0, str(CODE))
from queue_replay import load_record  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
_c = json.load(open(CODE / "final_rule_v5_groupP.json"))
MEM = set(_c["members"]) | (set(_c["group_G"]) if isinstance(_c["group_G"], list) else set())
BINS = [(-3600, -1800), (-1800, -900), (-900, -300), (-300, 0), (0, 300), (300, 1800)]


def clusters(s, m):
    o = np.argsort(s)
    s, m = s[o], m[o]
    out, i = [], 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] - s[i] <= 0.3:
            j += 1
        if len(set(m[i:j + 1])) >= 2:
            out.append(s[i])
            i = j + 1
        else:
            i += 1
    return np.array(out)


def main():
    cd, _ = load_record()
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "event"]).drop_duplicates("cid")
    ev_of = dict(zip(o.cid, o.event))
    E = pd.read_parquet(OUT / "events_sel_bo3.parquet", columns=["event_slug", "gs"])
    gs_of = dict(zip(E.event_slug, E.gs.astype(float)))
    wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"]).query("maker == @W").tx)
    tk = cd[(cd.idx == -1) & (cd.sign_ms > 1.7e12) & ~cd.tx.isin(wtx)].drop_duplicates("tx").copy()
    tk["mk"] = tk.maker.str.lower()
    tk = tk[tk.mk.isin(MEM)]
    tk["event"] = tk.cid.map(ev_of)
    tk["gs"] = tk.event.map(gs_of)
    tk = tk[tk.gs.notna()]
    tk["rel"] = tk.sign_ms / 1000.0 - tk.gs
    tk = tk[(tk.rel >= -3600) & (tk.rel < 1800) & (tk.sign_ms / 1000 < 1792713600)]
    rng = np.random.default_rng(221)
    obs = {b: 0 for b in BINS}
    nul = {b: [] for b in BINS}
    per_event = []
    for ev, g in tk.groupby("event"):
        s, m = g.rel.to_numpy(float), g.mk.to_numpy()
        c = clusters(s, m)
        for b in BINS:
            obs[b] += int(((c >= b[0]) & (c < b[1])).sum())
        pre = c[(c < 0) & (c >= -3600)]
        if len(pre):
            best = max(int(((pre >= x) & (pre < x + 180)).sum()) for x in pre)
            win_ok = any((((pre >= x) & (pre < x + 180)).sum() >= len(pre) / 2) and (-1800 <= x <= -300) for x in pre)
            per_event.append({"event": ev, "pre_clusters": int(len(pre)), "busiest_3min_share": round(best / len(pre), 3),
                              "half_in_one_window_5_30min": bool(win_ok), "first_pre_cluster_min": round(float(pre.min()) / 60, 1)})
    # null draws are per event; sum event means
    out = {"events": int(tk.event.nunique()), "takes": int(len(tk)), "takes_pre_start": int((tk.rel < 0).sum()),
           "bins": {}}
    for b in BINS:
        mins = (b[1] - b[0]) / 60.0
        # each event contributes len(nul) draws in order; average per draw index is not aligned, so use the mean count
        n_mean = float(np.sum([np.mean(nul[b][i::1]) for i in range(1)])) if nul[b] else 0.0
        out["bins"][f"{b[0] // 60}..{b[1] // 60} min"] = {"clusters": obs[b], "null_mean_total": None, "per_min": round(obs[b] / mins, 3)}
    # recompute the null properly: per event, mean of its draws; summed over events
    out["note"] = "null_mean_total computed below per event"
    ev_null = {b: 0.0 for b in BINS}
    for ev, g in tk.groupby("event"):
        s, m = g.rel.to_numpy(float), g.mk.to_numpy()
        acc = {b: [] for b in BINS}
        for _ in range(100):
            sh = s.copy()
            for mm in set(m):
                k = m == mm
                sh[k] = s[k] + rng.choice([-1, 1]) * rng.uniform(30, 60)
            cc = clusters(sh, m)
            for b in BINS:
                acc[b].append(((cc >= b[0]) & (cc < b[1])).sum())
        for b in BINS:
            ev_null[b] += float(np.mean(acc[b]))
    for b in BINS:
        k = f"{b[0] // 60}..{b[1] // 60} min"
        out["bins"][k]["null_mean_total"] = round(ev_null[b], 2)
        out["bins"][k]["ratio"] = round(obs[b] / ev_null[b], 2) if ev_null[b] > 0 else None
    P = pd.DataFrame(per_event)
    pre_obs = sum(obs[b] for b in BINS if b[1] <= 0)
    pre_null = sum(ev_null[b] for b in BINS if b[1] <= 0)
    out["pre_start"] = {"clusters": pre_obs, "null": round(pre_null, 2), "ratio": round(pre_obs / pre_null, 2) if pre_null else None,
                        "events_with_pre_clusters": int(len(P)),
                        "share_events_half_in_one_window_5_30min": round(float(P.half_in_one_window_5_30min.mean()), 3) if len(P) else None,
                        "busiest_3min_share_median": round(float(P.busiest_3min_share.median()), 3) if len(P) else None,
                        "first_pre_cluster_min_quartiles": [round(float(q), 1) for q in np.percentile(P.first_pre_cluster_min, [25, 50, 75])] if len(P) else None}
    out["llf_like"] = bool(out["pre_start"]["ratio"] and out["pre_start"]["ratio"] >= 3 and len(P) and P.half_in_one_window_5_30min.mean() >= 0.5)
    out["per_event_top"] = P.sort_values("pre_clusters", ascending=False).head(10).to_dict("records") if len(P) else []
    (RES / "pregame_clusters.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
