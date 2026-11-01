"""X227 exploratory (the pre-registered same-feed gate FAILED, so this is not a verdict): do the operator sibling
0x7d67f01d's Dota value changes on dota2-synaps-hn-2026-11-01 (development block 11-01 06-12) lock to Valve spectator
snapshot events (tommy_dota_rt S records, receive time)? Events: a team's kill count rising between consecutive
snapshots of one match id; building-state changes. Decisions: its maker bursts (50-ms chains) whose top moves. Lag
histogram decision - event in [-60, +60] s (1-s bins) against 1,000 circular shifts of the decision times inside the
recorded span. Output: results/valve_lock_a7.json"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
import sealed  # noqa: E402

RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
OUT = ROOT / ".cache/re/tommy-cs2-maker/iter16"
A7 = "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14"
EV = "dota2-synaps-hn-2026-11-01"
A, B = 1793512800, 1793534400


def main():
    assert not sealed.is_sealed(1793523600, "tommy-cs2-maker")
    snaps = []
    for r in live.iter_live("tommy_dota_rt", A, B):
        if r.get("k") == "S" and r.get("ev") == EV:
            tm = r.get("tm") or []
            k = {int(x[0]): int(x[1]) for x in tm if len(x) >= 2}
            nb = sum(1 for x in (r.get("bd") or []) if len(x) >= 3 and x[2])
            snaps.append((r["t"] / 1000.0, str(r.get("m")), k.get(2, np.nan), k.get(3, np.nan), nb, r.get("gt")))
    S = pd.DataFrame(snaps, columns=["t", "m", "k2", "k3", "nb", "gt"]).sort_values("t")
    ev_t, ev_dir = [], []
    for m, g in S.groupby("m"):
        g = g.drop_duplicates(["k2", "k3", "nb"])
        d2, d3 = g.k2.diff().fillna(0).to_numpy(), g.k3.diff().fillna(0).to_numpy()
        for t, a, b in zip(g.t.to_numpy(), d2, d3):
            if a > 0 or b > 0:
                ev_t.append(t)
                ev_dir.append(np.sign(a - b))
    ev_t = np.array(ev_t)
    cd = pd.read_parquet(OUT / "sfg_calldata.parquet")
    tr = pd.read_parquet(OUT / "sfg_trades.parquet")
    toks = set(tr.loc[tr.event == EV, "asset"].astype(str))
    c = cd[(cd.maker.str.lower() == A7) & (cd.idx >= 0) & cd.token_id.astype(str).isin(toks) & (cd.sign_ms > 1.7e12)]
    c = c.drop_duplicates(["salt", "sign_ms"]).sort_values("sign_ms")
    dec = []
    for tok, g in c.groupby("token_id"):
        s, p = g.sign_ms.to_numpy(float), g.price.to_numpy(float)
        i, last = 0, None
        while i < len(s):
            j = i
            while j + 1 < len(s) and s[j + 1] - s[i] <= 50:
                j += 1
            top = p[i:j + 1].max()
            if last is not None and abs(top - last) >= 0.01 - 1e-9:
                dec.append(s[i] / 1000.0)
            last = top
            i = j + 1
    dec = np.sort(np.array(dec))
    lo, hi = S.t.min(), S.t.max()
    dec = dec[(dec >= lo) & (dec <= hi)]
    bins = np.arange(-60, 61, 1.0)

    def hist(dd):
        lags = (dd[:, None] - ev_t[None, :]).ravel()
        lags = lags[(lags >= -60) & (lags < 60)]
        return np.histogram(lags, bins=bins)[0]
    obs = hist(dec) if len(dec) and len(ev_t) else np.zeros(len(bins) - 1)
    rng = np.random.default_rng(227)
    span = hi - lo
    null = np.array([hist(lo + ((dec - lo + rng.uniform(60, span - 60)) % span)) for _ in range(1000)]) if len(dec) else None
    out = {"snapshots": int(len(S)), "matches": int(S.m.nunique()), "kill_events": int(len(ev_t)), "decisions": int(len(dec)),
           "gate_failed_note": "same_feed_gate.json: G1 lag IQR 69.5 ms > 40, G2 +0.98c < +1c; exploratory only"}
    if null is not None and len(ev_t):
        mu = null.mean(0)
        sd = null.std(0) + 1e-9
        z = (obs - mu) / sd
        k = int(np.argmax(z))
        win = {}
        for a, b in ((-10, 0), (0, 10), (-5, 5), (-30, -10), (10, 30)):
            m_ = (bins[:-1] >= a) & (bins[:-1] < b)
            o_, n_ = obs[m_].sum(), null[:, m_].sum(1)
            win[f"{a}..{b}s"] = {"obs": int(o_), "null_mean": round(float(n_.mean()), 1), "ratio": round(float(o_ / max(n_.mean(), 1e-9)), 2),
                                 "p": round(float((n_ >= o_).mean()), 4)}
        out.update(peak_lag_s=float(bins[k]), peak_z=round(float(z[k]), 2), windows=win)
    (RES / "valve_lock_a7.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
