"""Iteration 3, X26 / X34 verification: were the 100-share levels cancelled 0-40 ms after the wallet's takes placed by
the wallet's own ladder?

Own recorder (server clock, 10-31 14:50 UTC on), the wallet's CS2 dev-unit markets. Wallet ladder adds = +100 whole-cent
level additions on a token-0 side within +-60 ms of an add confirmed as a wallet maker order (its filled order's price,
added 0-400 ms after its signing; see ladder_decode.py). For every size-100 cancel: the most recent +100 add at the
same (token, side, price) before it; is that add a wallet ladder add? Groups: cancels in [0, 40] ms after a wallet take
on the consumed side, vs all other size-100 cancels. (Censored: ladders whose orders never filled are not anchored, so
the share is a lower bound.) Output: results/cancel_owner_check.json
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, read  # noqa: E402

OWN0 = 1793458232000


def main():
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    m = m[(m.wallet_trades > 0) & m.event.str.startswith("cs2")]
    tok = {}
    for r in m.itertuples():
        tok[r.tok0] = (r.tok0, 0)
        tok[r.tok1] = (r.tok0, 1)
    tok0 = set(m.tok0)
    ow = read("tommy_cs2_near", tok0, OWN0 / 1000, time.time())
    trades = defaultdict(list)
    for r in ow:
        if r["k"] == "x":
            trades[r["a"]].append(r["s"])
    trades = {a: np.sort(np.array(v, float)) for a, v in trades.items()}
    adds = defaultdict(list)   # (a, side, p) -> [s]
    adds_side = defaultdict(list)  # (a, side) -> [(s, p)]
    cancels = []  # (a, side, p, s)
    books = {}
    for r in sorted([r for r in ow if r["k"] in ("f", "pc")], key=lambda r: (r["s"], r["t"])):
        a = r["a"]
        if r["k"] == "f":
            books[a] = ({float(p): float(z) for p, z in r["b"]}, {float(p): float(z) for p, z in r["o"]})
            continue
        if a not in books:
            continue
        bd, od = books[a]
        for side, p, z in r["c"]:
            bk = bd if side == "BUY" else od
            p, z = float(p), float(z)
            dz = round(z - bk.get(p, 0.0), 2)
            whole = abs(p * 100 - round(p * 100)) < 1e-6
            if whole and dz == 100:
                adds[(a, side, round(p, 2))].append(r["s"])
                adds_side[(a, side)].append((r["s"], round(p, 2)))
            if whole and dz == -100:
                tr = trades.get(a, np.array([]))
                k = np.searchsorted(tr, r["s"] - 150)
                if not (k < len(tr) and tr[k] <= r["s"] + 150):
                    cancels.append((a, side, round(p, 2), r["s"]))
            if z == 0:
                bk.pop(p, None)
            else:
                bk[p] = z
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    d = d[(d.sign_ms >= OWN0 + 2000) & (d.sign_ms < 1.8e12) & d.token_id.astype(str).isin(tok)]
    wm = d[(d.idx >= 0) & (d.maker == WALLET)].drop_duplicates(["salt", "sign_ms"])
    # confirmed wallet adds -> wallet bursts (side, time window)
    wb = defaultdict(list)  # (a, side) -> [s_add]
    for r in wm.itertuples():
        a, k = tok[str(r.token_id)]
        side, p0 = ("BUY", round(r.price, 2)) if k == 0 else ("SELL", round(1 - r.price, 2))
        s = np.array(adds.get((a, side, p0), []), float)
        sel = s[(s >= r.sign_ms) & (s <= r.sign_ms + 400)]
        if len(sel):
            wb[(a, side)].append(sel[0])
    wb = {k: np.sort(np.array(v)) for k, v in wb.items()}

    def is_wallet_add(a, side, s_add):
        b = wb.get((a, side))
        if b is None or len(b) == 0:
            return False
        i = np.searchsorted(b, s_add)
        near = [b[j] for j in (i - 1, i) if 0 <= j < len(b)]
        return any(abs(x - s_add) <= 60 for x in near)
    tk = d[(d.idx == -1) & (d.maker == WALLET)].drop_duplicates("tx")
    tk_list = []
    for r in tk.itertuples():
        a, k = tok[str(r.token_id)]
        team = k if r.side == 0 else 1 - k
        tk_list.append((a, "SELL" if team == 0 else "BUY", r.sign_ms))
    res = {"wallet_bursts_confirmed": int(sum(len(v) for v in wb.values())), "size100_cancels": len(cancels)}
    grp = {"after_take": [], "other": []}
    for a, side, p, s in cancels:
        after = any(a == ta and side == ts_ and 0 <= s - st <= 40 for ta, ts_, st in tk_list)
        prev = np.array(adds.get((a, side, p), []), float)
        prev = prev[prev < s]
        if len(prev) == 0:
            continue
        grp["after_take" if after else "other"].append(is_wallet_add(a, side, prev[-1]))
    for g, v in grp.items():
        res[g] = {"n_with_prior_add": len(v), "prior_add_is_wallet_ladder": round(float(np.mean(v)), 3) if v else None}
    json.dump(res, open(RES / "cancel_owner_check.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
