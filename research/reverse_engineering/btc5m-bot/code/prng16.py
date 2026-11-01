"""Iteration 16 (X163 step 2, assumptions panel P4): are the salts V8 Math.random outputs of a PER-SIGNER generator whose calls run
ACROSS cents (parallel signers, each with its own isolate), rather than nearby calls of one generator per copy group (prng15, rejected)?
Chains: one (wallet, token, signing burst, size) with >= MINC distinct cents that carry exactly one observed salt each (complete
calldata of 10-20..22 + samples). Layout hypotheses: the signer makes M Math.random calls per order and signs one order per cent in
sign_ms order (M = 1..4); V8's 64-entry cache is read last-in-first-out with an unknown phase k0 (0..63) of the chain's first call.
For each hypothesis the generation offsets of every salt follow; the known top mantissa bits (salt = round(r x Date.now()), Date.now()
within +-2 ms of the order's timestamp) give GF(2) equations on the 128-bit state; with > 128 independent equations a random hypothesis
is inconsistent with probability ~1 - 2^-(excess), so any consistent full-rank hypothesis is a recovery (then checked on held-out salts).
Synthetic self-test on the same layout first. Usage: python -I prng16.py OUT.json"""
import os, sys, json, time, random, glob
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0], "x", sys.argv[1] if len(sys.argv) > 1 else "prng16.json", "12", "hi"]
import prng15 as P15   # sym_words, Basis, known_bits, eqs, step_num (variant 'hi', DT = 2)

S = os.environ["RE16_SCRATCH"]
OUT = sys.argv[2]
MINC = 6; MAXCH = 300; SPAN = 1200
WM = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}


def gen_offsets(calls, k0):
    """relative generation offset of each call index (call 0 reads cache[k0]; cache read downwards; refill = next 64 generations)."""
    out = []
    for c in calls:
        if c <= k0:
            out.append(-c)
        else:
            b = (c - k0 - 1) // 64 + 1; i = (c - k0 - 1) % 64
            out.append(64 * b + 63 - i - k0)
    return out


def consistent(words, salts, Ts, offs, base):
    bs = P15.Basis(); neq = 0
    for s, T, o in zip(salts, Ts, offs):
        kb = P15.known_bits(s, T)
        for m, v in P15.eqs(words[base + o], kb):
            neq += 1
            if not bs.add(m, v):
                return False, neq, len(bs.r)
    return True, neq, len(bs.r)


def main():
    t0 = time.time()
    base = SPAN // 2
    words = P15.sym_words(SPAN + 10)
    print("words", round(time.time() - t0, 1), flush=True)
    # ---- self-test: one generator, M calls per order, sparse observed cents, random phase
    st = []
    for trial in range(4):
        s0, s1 = random.getrandbits(64), random.getrandbits(64)
        xs = [s0, s1]
        for _ in range(SPAN + 20):
            xs.append(P15.step_num(xs[-2], xs[-1])[1])
        M = random.choice([1, 2, 3]); k0 = random.randint(0, 63)
        cents = sorted(random.sample(range(0, 60), 8)); calls = [M * c for c in cents]
        offs = gen_offsets(calls, k0)
        T = 1792400000000 + random.randint(0, 10 ** 8)
        salts = [round((((xs[base + o] >> 12) & ((1 << 52) - 1)) / 2 ** 52) * (T + int(1.66 * c))) for o, c in zip(offs, cents)]
        Ts = [T + int(1.66 * c) for c in cents]
        hits = []
        for Mh in (1, 2, 3, 4):
            for kh in range(64):
                ok, neq, rk = consistent(words, salts, Ts, gen_offsets([Mh * c for c in cents], kh), base)
                if ok and rk >= 128:
                    hits.append((Mh, kh))
        st.append({"M": M, "k0": k0, "hits": hits[:5]})
        print("selftest", st[-1], flush=True)
    # ---- real chains
    cols = ["tx", "role", "maker", "token", "maker_amt", "taker_amt", "oside", "sign_ms", "salt"]
    fs = glob.glob(S + "/it16/cdfull_*.parquet") + [".cache/re/btc5m-bot/calldata_sample.parquet", S + "/it15/cl_orders.parquet"]
    c = pd.concat([pd.read_parquet(f, columns=cols) for f in fs], ignore_index=True)
    c["w"] = c.maker.str.lower().map(WM); c = c[c.w.notna() & (c.oside == 0)].drop_duplicates("salt").copy()
    c["salt_i"] = c.salt.apply(int); c["T"] = c.sign_ms.astype(np.int64)
    c["px"] = np.round(100 * c.maker_amt / c.taker_amt).astype(int); c["sz"] = c.taker_amt.round().astype(int)
    c = c.sort_values(["w", "token", "T"])
    c["gap"] = c.groupby(["w", "token"]).T.diff(); c["burst"] = ((c.gap > 300) | c.gap.isna()).cumsum()
    chains = []
    for (b, sz), g in c.groupby(["burst", "sz"]):
        per = g.groupby("px").salt_i.nunique()
        single = per[per == 1].index
        h = g[g.px.isin(single)].sort_values("T")
        if h.px.nunique() >= MINC:
            chains.append(h)
    chains.sort(key=lambda h: -len(h))
    print("orders", len(c), "chains", len(chains), flush=True)
    res = {"selftest": st, "n_chains": len(chains), "tested": 0, "recovered": [], "per_chain": []}
    for h in chains[:MAXCH]:
        h = h.head(10)
        # call order = sign order; cent distance from the first signed cent in signing direction
        px = h.px.to_numpy(); d = np.abs(px - px[0])
        if len(set(d.tolist())) < len(d):
            continue
        salts = h.salt_i.tolist(); Ts = h["T"].tolist()
        found = []
        for Mh in (1, 2, 3, 4):
            calls = [int(Mh * x) for x in d]
            if max(calls) > SPAN // 2 - 70:
                continue
            for kh in range(64):
                ok, neq, rk = consistent(words, salts, Ts, gen_offsets(calls, kh), base)
                if ok and rk >= 128:
                    found.append((Mh, kh, neq))
        res["tested"] += 1
        res["per_chain"].append({"w": h.w.iloc[0], "n": len(h), "span_c": int(d.max()), "found": found[:3]})
        if found:
            res["recovered"].append(res["per_chain"][-1])
        if time.time() - t0 > 600:
            break
    print("tested", res["tested"], "recovered", len(res["recovered"]), round(time.time() - t0), "s", flush=True)
    json.dump(res, open(OUT, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
