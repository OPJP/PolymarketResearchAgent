"""Print the size history of given bid levels of a token's recorded book in [a, b) (server ms), plus trades."""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
import livex
tok, a, b = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
levels = [float(x) for x in sys.argv[4].split(",")]
side = sys.argv[5] if len(sys.argv) > 5 else "b"
prev = None
for r in livex.iter_live("clob_crypto", a - 5, b + 5):
    if r.get("a") != tok:
        continue
    s = r.get("s", r["t"]) / 1000
    if not (a <= s < b):
        continue
    if r["k"] in ("q", "f"):
        book = {p: z for p, z in r[side]}
        best = r[side][0][0] if r[side] else None
        cur = tuple(round(book.get(l, 0), 2) for l in levels)
        if cur != prev:
            print(f"{s:.3f} {r['k']} best{side}={best} " + " ".join(f"{l}:{c}" for l, c in zip(levels, cur)))
            prev = cur
    elif r["k"] == "x":
        print(f"{s:.3f} TRADE p={r['p']} z={r['z']} d={r['d']} h={str(r.get('h'))[:12]}")
