"""X179 (mechanics panel iter-12 P4): does one V8 Math.random() stream draw the salts of the wallet AND its 5-share
same-process accounts? Co-signed bursts (a wallet maker burst, same token, signed within 50 ms, plus the sibling orders
signed 0-10 ms after its first order on that token), merged in signing order (wallet first, then sibling; ties by
price both ways). GF(2) consistency of salt = round(U x sign_ms) as V8 xorshift128+ outputs (code/iter7/v8salt_lib.py,
both mantissa conventions, DT 0 / 3 ms) at strides k = 1..6 (k generator positions between consecutive orders),
forward and reverse (LIFO cache) order. A hit needs a consistent system with >= 20 redundant equations. Control: the
same test on mismatched pairs (wallet burst + the sibling orders of another co-signed burst).
Output: results/salt_merged.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter7"))
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
SIB = ["0x52661b8e13158f23d94a9e8302ab0295704c22ac", "0x671190333b064b0899b4ac1aec86744b1f82885b", "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14"]


def groups():
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["idx", "maker", "token_id", "price", "sign_ms", "salt"])
    cd["maker"] = cd.maker.str.lower()
    cd["token_id"] = cd.token_id.astype(str)
    o = cd[cd.idx != -1].drop_duplicates(["maker", "salt", "sign_ms"]).copy()
    o["salt_i"] = o.salt.astype("int64")
    w = o[o.maker == W]
    s = o[o.maker.isin(SIB)]
    sb = {t: g.sort_values("sign_ms") for t, g in s.groupby("token_id")}
    out = []
    for tok, g in w.sort_values("sign_ms").groupby("token_id"):
        if tok not in sb:
            continue
        ss = sb[tok]
        t = g.sign_ms.to_numpy(np.int64)
        st = 0
        for i in range(1, len(t) + 1):
            if i == len(t) or t[i] - t[i - 1] > 50:
                gw = g.iloc[st:i]
                gs = ss[(ss.sign_ms >= t[st]) & (ss.sign_ms <= t[i - 1] + 10)]
                if len(gs):
                    out.append((gw[["salt_i", "sign_ms", "price"]].values.tolist(), gs[["salt_i", "sign_ms", "price"]].values.tolist()))
                st = i
    return out


def test(seq, V):
    kb = [V.known_bits(int(sa), int(tm)) for sa, tm, _ in seq]
    n = len(seq)
    for k in range(1, 7):
        pos = [i * k for i in range(n)]
        if max(pos) >= len(V.xs):
            continue
        for order in (list(range(n)), list(range(n - 1, -1, -1))):
            eqs = []
            for j, p_ in zip(order, pos):
                eqs += V.eqs_for(p_, kb[j])
            ok, red = V.solve(eqs)
            if ok and red >= 20:
                return k, red
    return None


def main():
    G = groups()
    res = {"co_bursts": len(G)}
    rng = np.random.default_rng(3)
    for variant in ("hi", "lo"):
        for DT in (0, 3):
            sys.argv = ["x", variant, str(DT), "5", "0"]
            if "v8salt_lib" in sys.modules:
                del sys.modules["v8salt_lib"]
            import v8salt_lib as V  # noqa: E402
            hits = tried = ctl_hits = ctl_tried = 0
            for i, (gw, gs) in enumerate(G):
                seq = sorted(gw, key=lambda r: (r[1], -r[2])) + sorted(gs, key=lambda r: (r[1], -r[2]))
                if len(seq) < 3 or len(seq) > 8:
                    continue
                tried += 1
                if test(seq, V):
                    hits += 1
                j = int(rng.integers(len(G)))
                if j != i:
                    seq2 = sorted(gw, key=lambda r: (r[1], -r[2])) + sorted(G[j][1], key=lambda r: (r[1], -r[2]))
                    if 3 <= len(seq2) <= 8:
                        ctl_tried += 1
                        if test(seq2, V):
                            ctl_hits += 1
            res[f"{variant}_DT{DT}"] = {"tried": tried, "hits": hits, "control_tried": ctl_tried, "control_hits": ctl_hits}
            print(variant, DT, res[f"{variant}_DT{DT}"], flush=True)
    # salt scale: share of salts below their sign time (ms-scale generator)
    (RES / "salt_merged.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
