"""Iteration 6, X79 step 4 (mechanics panel iter5 P5): who else runs the 1.5-s "cancel -> wait -> re-post at the same
price" timer? Scan every CS2 book recorded by tommy_cs2_near in the 10-31 14:50-18:00 development block, keeping only
units whose game start lies in a development block (sub records: cid -> [tok0, tok1, gs, slug]; sealed-start units are
dropped before anything is counted). Level changes are rebuilt from snapshots + price changes (server clock). A
"cooldown pair" = a decrease of size d at a whole-cent level with no trade at that book within 150 ms, followed by an
increase of exactly d at the same side and price 1,490-1,530 ms later. Counted per market (traded by the wallet or not,
GRID or not by the listing's slug prefix list from dev_markets) and per size d; control = increases of d at
1,290-1,330 ms and 1,690-1,730 ms (the same pairing at shifted lags).
Output: results/cooldown_siblings.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
import sealed  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
KEY = "tommy-cs2-maker"
OWN0, END = 1793458232, 1793469600


def main():
    tok0 = {}
    meta = {}
    events = defaultdict(list)  # a -> list of (s, side, p, delta)
    trades = defaultdict(list)
    state = {}
    h = int(OWN0 // 3600 * 3600)
    while h < END:
        try:
            for r in live.iter_live("tommy_cs2_near", max(h, OWN0), min(h + 3600, END)):
                k = r.get("k")
                if k == "sub":
                    for cid, v in (r.get("m") or {}).items():
                        try:
                            gs = float(v[2])
                        except Exception:  # noqa: BLE001
                            continue
                        if sealed.is_sealed(gs, KEY):
                            continue  # sealed-start unit: never counted
                        tok0[str(v[0])] = cid
                        meta[cid] = str(v[3]) if len(v) > 3 else ""
                    continue
                a = r.get("a")
                if a not in tok0 or "s" not in r:
                    continue
                s = float(r["s"])
                if k == "x":
                    trades[a].append(s)
                    continue
                if k in ("q", "f"):
                    b = {float(p): float(z) for p, z in (r.get("b") or [])}
                    o = {float(p): float(z) for p, z in (r.get("o") or [])}
                    if a in state:
                        for sd, new, old in (("BUY", b, state[a][0]), ("SELL", o, state[a][1])):
                            for p in set(new) | set(old):
                                d = new.get(p, 0.0) - old.get(p, 0.0)
                                if abs(d) > 1e-9:
                                    events[a].append((s, sd, p, d))
                    state[a] = (b, o)
                elif k == "pc" and a in state:
                    for sd, p, z in r.get("c") or []:
                        p, z = float(p), float(z)
                        book = state[a][0] if sd == "BUY" else state[a][1]
                        d = z - book.get(p, 0.0)
                        if abs(d) > 1e-9:
                            events[a].append((s, sd, p, d))
                        if z == 0:
                            book.pop(p, None)
                        else:
                            book[p] = z
        except Exception as e:  # noqa: BLE001
            print("feed stopped", type(e).__name__, flush=True)
        h += 3600
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    traded = set(dm.loc[dm.wallet_trades > 0, "tok0"].astype(str))
    out_rows = []
    for a, ev in events.items():
        E = pd.DataFrame(ev, columns=["s", "side", "p", "d"]).sort_values("s")
        E = E[(np.abs(E.p * 100 - np.round(E.p * 100)) < 1e-6)]
        tr = np.sort(np.array(trades.get(a, []), float))
        dec = E[E.d < 0]
        inc = E[E.d > 0]
        if dec.empty or inc.empty:
            continue
        inc_key = defaultdict(list)
        for r in inc.itertuples():
            inc_key[(r.side, round(r.p, 2), round(r.d, 2))].append(r.s)
        inc_key = {k: np.sort(np.array(v)) for k, v in inc_key.items()}
        for r in dec.itertuples():
            j = np.searchsorted(tr, r.s - 150)
            if j < len(tr) and tr[j] <= r.s + 150:
                continue  # near a trade: consumption, not a cancel
            key = (r.side, round(r.p, 2), round(-r.d, 2))
            x = inc_key.get(key)
            if x is None:
                continue
            def has(lo, hi):
                i = np.searchsorted(x, r.s + lo)
                return i < len(x) and x[i] < r.s + hi
            out_rows.append({"a": a, "slug": meta.get(tok0[a], ""), "traded": a in traded, "size": round(-r.d, 2),
                             "spike": has(1490, 1530), "ctrl_lo": has(1290, 1330), "ctrl_hi": has(1690, 1730)})
    R = pd.DataFrame(out_rows)
    if not R.empty:
        R.assign(cid=R.a.map(tok0)).to_parquet(OUT / "cooldown_pairs_dev.parquet", index=False)
    res = {"books": int(len(events)), "markets_meta": int(len(meta))}
    if not R.empty:
        g = R.groupby("traded")[["spike", "ctrl_lo", "ctrl_hi"]].sum().astype(int)
        res["by_traded"] = {str(k): v for k, v in g.to_dict("index").items()}
        top = R[R.spike].groupby(["traded", "size"]).size().sort_values(ascending=False).head(15)
        res["spike_by_size_top"] = {f"{'traded' if k[0] else 'untraded'}:{k[1]}": int(v) for k, v in top.items()}
        ctl = R[R.ctrl_lo | R.ctrl_hi].groupby(["traded", "size"]).size()
        res["ctrl_same_sizes"] = {f"{'traded' if k[0] else 'untraded'}:{k[1]}": int(ctl.get(k, 0)) for k in top.index}
        um = R[(~R.traded) & R.spike].groupby("slug").size().sort_values(ascending=False).head(12)
        res["untraded_spike_by_market"] = {str(k): int(v) for k, v in um.items()}
    (RES / "cooldown_siblings.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
