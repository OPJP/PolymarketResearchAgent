"""Maker price vs the unthrottled near-touch book of the own recorder (tommy_cs2_near, from 14:50 UTC 10-31; dev units
only). For each wallet maker order (calldata_dev) signed while the book is recorded: best bid of its token at the
signing time (token 1 = 1 - token-0 best ask) and 0.2 s / 1 s earlier; exact share and offsets."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
import sealed  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
KEY, T0 = "tommy-cs2-maker", 1793404800


def main():
    end = time.time() - 30
    subs, state, snaps = {}, {}, []
    for r in live.iter_live("tommy_cs2_near", 1793458232, end):
        k = r.get("k")
        if k == "sub":
            for cid, v in r["m"].items():
                subs[v[0]] = (cid, int(v[2]), v[1])
            continue
        a = r.get("a")
        if a not in subs or subs[a][1] < T0 or sealed.is_sealed(subs[a][1], KEY):
            continue
        if k == "f":
            state[a] = ({float(p): float(z) for p, z in r["b"]}, {float(p): float(z) for p, z in r["o"]})
        elif k == "pc" and a in state:
            bd, od = state[a]
            for sd, p, z in r["c"]:
                bk = bd if sd == "BUY" else od
                if float(z) == 0:
                    bk.pop(float(p), None)
                else:
                    bk[float(p)] = float(z)
        else:
            continue
        if a in state:
            bd, od = state[a]
            snaps.append((r["t"], a, max(bd) if bd else np.nan, min(od) if od else np.nan))
    s = pd.DataFrame(snaps, columns=["t", "a", "bb", "ba"]).sort_values("t")
    tok1 = {v[2]: a for a, v in subs.items()}  # token1 -> token0
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    w = d[(d.maker == WALLET) & (d.idx >= 0) & (d.side == 0) & (d.sign_ms > 1793458300000)].drop_duplicates(["token_id", "price", "sign_ms"])
    rows = []
    for o in w.itertuples():
        t = str(o.token_id)
        if t in subs:
            a, one = t, False
        elif t in tok1:
            a, one = tok1[t], True
        else:
            continue
        g = s[s.a == a]
        tt = g.t.to_numpy()
        out = {"q": o.price}
        for lab, dt in (("now", 0), ("m200", -200), ("m1000", -1000)):
            j = np.searchsorted(tt, o.sign_ms + dt, side="left") - 1
            if j < 0:
                out[lab] = np.nan
                continue
            out[lab] = (1 - g.ba.iloc[j]) if one else g.bb.iloc[j]
        rows.append(out)
    x = pd.DataFrame(rows).dropna()
    res = {"orders": len(x)}
    for lab in ("now", "m200", "m1000"):
        dd = (x.q - x[lab]).round(3)
        res[lab] = {"exact": round(float((dd.abs() < 0.0005).mean()), 3), "within_1c": round(float((dd.abs() <= 0.0105).mean()), 3),
                    "dist": dd.value_counts(normalize=True).head(6).round(3).to_dict()}
    json.dump(res, open(RES / "results/price_join_own.json", "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
