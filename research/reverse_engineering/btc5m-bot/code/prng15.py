"""Iteration 15, assumptions panel P2 (X149 = strong form of X99 / X105): are the operator's salts V8 Math.random() outputs
(xorshift128+, 64-entry cache read last-in-first-out) whose state can be recovered from the filled copies of one ladder level?

salt = round(r * D), r = ToDouble(state0) = (state0 >> 12) / 2^52 ('hi', current V8) or (state0 & (2^52 - 1)) / 2^52 ('lo', old V8),
D = Date.now() within +-DT ms of the order's timestamp field. The copies of one (wallet burst, token, price) are signed in the same
millisecond, i.e. by calls that are close in the call sequence; inside one cache block consecutive calls are consecutive generator
outputs in reverse order, so their generation indices are distinct integers within a small span. For each group with >= 4 distinct
salts, a depth-first search assigns generation offsets in [-P, P] (first salt at 0) and checks GF(2) consistency of the known top
mantissa bits (incremental elimination). A consistent full-rank assignment is then VALIDATED by stepping the recovered state over
+-3000 outputs and counting exact (known-bit) matches of the burst's OTHER filled salts (chance per salt and position ~2^-38).
Synthetic self-test first (same layout, same bit budget). Usage: python -I prng15.py ORDERS.parquet OUT.json [P] [variant] [maxgroups]"""
import sys, json, time, random
import numpy as np, pandas as pd

M64 = (1 << 64) - 1
B = 3000
P = int(sys.argv[3]) if len(sys.argv) > 3 else 12
VAR = sys.argv[4] if len(sys.argv) > 4 else "hi"
MAXG = int(sys.argv[5]) if len(sys.argv) > 5 else 40
DT = int(sys.argv[7]) if len(sys.argv) > 7 else 2


def sym_words(n):
    xs = [[1 << i for i in range(64)], [1 << (64 + i) for i in range(64)]]
    for _ in range(n):
        a, b = xs[-2], xs[-1]
        s = [a[i] ^ (a[i - 23] if i >= 23 else 0) for i in range(64)]           # s = a ^ (a << 23)
        s = [s[i] ^ (s[i + 17] if i + 17 < 64 else 0) for i in range(64)]      # s ^= s >> 17
        s = [s[i] ^ b[i] ^ (b[i + 26] if i + 26 < 64 else 0) for i in range(64)]  # s ^= b ^ (b >> 26)
        xs.append(s)
    return xs


def step_num(s0, s1):
    a, b = s0, s1
    a ^= (a << 23) & M64; a ^= a >> 17; a ^= b; a ^= b >> 26
    return b, a


def known_bits(salt, T):
    lo = ((2 * salt - 1) << 51) // (T + DT)
    hi = ((2 * salt + 1) << 51) // (T - DT)
    hi = min(hi, (1 << 52) - 1); lo = max(lo, 0)
    out = []
    for b in range(51, -1, -1):
        if ((lo >> b) & 1) == ((hi >> b) & 1):
            out.append((b, (lo >> b) & 1))
        else:
            break
    return out


def eqs(word, kb):
    """mantissa bit b -> state0 bit b + 12 ('hi') or b ('lo')."""
    sh = 12 if VAR == "hi" else 0
    return [(word[b + sh], v) for b, v in kb]


class Basis:
    def __init__(self, rows=None):
        self.r = dict(rows) if rows else {}

    def add(self, mask, val):
        while mask:
            hb = mask.bit_length() - 1
            if hb in self.r:
                m2, v2 = self.r[hb]; mask ^= m2; val ^= v2
            else:
                self.r[hb] = (mask, val); return True
        return val == 0

    def solve(self):
        if len(self.r) < 128:
            return None
        sol = 0
        for hb in sorted(self.r):
            m, v = self.r[hb]
            rest = m & ~(1 << hb)
            bit = v ^ (bin(rest & sol).count("1") & 1)
            if bit:
                sol |= 1 << hb
        return sol


def match_bits(x, kb):
    sh = 12 if VAR == "hi" else 0
    return all(((x >> (b + sh)) & 1) == v for b, v in kb)


def search(group, words, others):
    """group: list of (salt, T); returns list of (offsets, n_validated)."""
    kbs = [known_bits(s, T) for s, T in group]
    order = sorted(range(len(group)), key=lambda i: -len(kbs[i]))
    kbs = [kbs[i] for i in order]
    n = len(kbs); found = []
    offs = list(range(-P, P + 1))

    def dfs(k, basis, used):
        if k == n:
            sol = basis.solve()
            if sol is not None:
                found.append((tuple(used), sol))
            return
        for o in offs:
            if o in used:
                continue
            b2 = Basis(basis.r); ok = True
            for m, v in eqs(words[B + o], kbs[k]):
                if not b2.add(m, v):
                    ok = False; break
            if ok:
                dfs(k + 1, b2, used + [o])
            if len(found) > 50:
                return

    b0 = Basis()
    for m, v in eqs(words[B], kbs[0]):
        b0.add(m, v)
    dfs(1, b0, [0])
    res = []
    for used, sol in found[:20]:
        s0, s1 = sol & M64, sol >> 64
        xs = [s0, s1]
        for _ in range(2 * B):
            xs.append(step_num(xs[-2], xs[-1])[1])
        hits = 0
        for s, T in others:
            kb = known_bits(s, T)
            if any(match_bits(xs[j], kb) for j in range(2, len(xs))):
                hits += 1
        res.append({"offsets": list(used), "validated": hits, "n_others": len(others)})
    return res


def selftest(words):
    """synthetic: copies at consecutive calls inside a 64-block (reverse generation order), sparse filled subset."""
    out = []
    for trial in range(6):
        s0, s1 = random.getrandbits(64), random.getrandbits(64)
        xs = [s0, s1]
        for _ in range(2 * B + 10):
            xs.append(step_num(xs[-2], xs[-1])[1])
        T = 1792400000000 + random.randint(0, 10 ** 8)
        sh = 12 if VAR == "hi" else 0
        def salt_at(j, D):
            r = ((xs[j] >> sh) & ((1 << 52) - 1)) / 2 ** 52
            return round(r * D)
        base = B + random.randint(-3, 3)
        pos = sorted(random.sample(range(0, 10), 5))      # 5 filled copies among 10 consecutive calls
        group = [(salt_at(base - p, T + random.randint(-1, 1)), T) for p in pos]   # LIFO: decreasing generation index
        others = [(salt_at(base - 40 - 3 * q, T + 5), T + 5) for q in range(8)]
        t0 = time.time(); r = search(group, words, others)
        out.append({"trial": trial, "true_offsets": [-(p - pos[0]) for p in pos], "found": r[:3], "s": round(time.time() - t0, 1)})
        print(out[-1], flush=True)
    return out


def main():
    t0 = time.time()
    words = sym_words(2 * B + P + 5)
    print("words", round(time.time() - t0, 1), "s", flush=True)
    rep = {"P": P, "variant": VAR, "DT": DT}
    rep["selftest"] = selftest(words) if DT <= 2 else "skipped"
    u = pd.read_parquet(sys.argv[1])
    u["salt_i"] = u.salt.apply(int)
    u["T"] = u.sign_ms.astype(np.int64)
    g = u.groupby(["b", "token", "px"])
    grp = [(k, x) for k, x in g if x.salt_i.nunique() >= 4]
    grp.sort(key=lambda kx: -kx[1].salt_i.nunique())
    real = []
    for k, x in grp[:MAXG]:
        x = x.drop_duplicates("salt_i")
        group = list(zip(x.salt_i.tolist()[:6], x["T"].tolist()[:6]))
        ob = u[(u.b == k[0]) & ~u.salt_i.isin(x.salt_i)].drop_duplicates("salt_i")
        others = list(zip(ob.salt_i.tolist()[:40], ob["T"].tolist()[:40]))
        t1 = time.time(); r = search(group, words, others)
        real.append({"burst": int(k[0]), "px": float(k[2]), "n": len(group), "w": x.w.iloc[0], "n_found": len(r),
                     "best_validated": max([z["validated"] for z in r], default=None), "n_others": len(others), "s": round(time.time() - t1, 1)})
        print(real[-1], flush=True)
        if time.time() - t0 > float(sys.argv[6] if len(sys.argv) > 6 else 1500):
            break
    rep["real"] = real
    rep["real_groups_tested"] = len(real)
    rep["real_consistent"] = sum(1 for z in real if z["n_found"] > 0)
    rep["real_validated"] = sum(1 for z in real if (z["best_validated"] or 0) > 0)
    json.dump(rep, open(sys.argv[2], "w"), indent=1)
    print("DONE", json.dumps({k: v for k, v in rep.items() if k not in ("selftest", "real")}))


if __name__ == "__main__":
    main()
