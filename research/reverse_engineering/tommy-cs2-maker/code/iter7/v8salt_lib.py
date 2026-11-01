"""Copied from the iteration-6 mechanics panel scratchpad (v8salt.py: GF(2) consistency test of ladder-burst salts as
V8 xorshift128+ outputs, salt = round(U x T)), with L = 40 symbolic outputs so strides up to 8 fit (iteration 7, X96)."""
"""Panel feasibility check: are the wallet's salts consecutive V8 Math.random() outputs (xorshift128+)?

salt = round(Math.random() * T), T ~ sign_ms. Known top bits of each output's 52-bit mantissa give linear
equations over GF(2) in the 128-bit state; a group of >= 4 orders of one ladder burst over-determines it.
Read-only on the strategy's development calldata (before H).
"""
import itertools, sys
import pandas as pd

MASK64 = (1 << 64) - 1
W = '0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
VARIANT = sys.argv[1] if len(sys.argv) > 1 else 'hi'   # 'hi': state0 >> 12 (new V8); 'lo': state0 & mantissa (old V8)
DT = int(sys.argv[2]) if len(sys.argv) > 2 else 0
MAXN = int(sys.argv[3]) if len(sys.argv) > 3 else 5
GAPS = int(sys.argv[4]) if len(sys.argv) > 4 else 0
WHO = sys.argv[5].lower() if len(sys.argv) > 5 else W

# symbolic words: list of 64 masks (bit i), masks over 128 unknowns
def var_word(off):
    return [1 << (off + i) for i in range(64)]

def shl(w, k):
    return [0] * k + w[:64 - k]

def shr(w, k):
    return w[k:] + [0] * k

def xor(a, b):
    return [x ^ y for x, y in zip(a, b)]

L = 40
xs = [var_word(0), var_word(64)]
for k in range(L):
    a, b = xs[-2], xs[-1]
    s1 = xor(a, shl(a, 23))
    s1 = xor(s1, shr(s1, 17))
    s1 = xor(s1, b)
    s1 = xor(s1, shr(b, 26))
    xs.append(s1)


def known_bits(salt, T):
    # r in [(salt-0.5)/T, (salt+1)/(T-DT)] ; mantissa m = floor(r * 2^52)
    lo = ((2 * salt - 1) << 51) // T            # floor((salt-0.5)*2^52/T)
    hi = ((salt + 1) << 52) // (T - DT)
    if hi >= (1 << 52):
        hi = (1 << 52) - 1
    # common prefix of lo and hi (52-bit numbers)
    n = 0
    for b in range(51, -1, -1):
        if ((lo >> b) & 1) == ((hi >> b) & 1):
            n += 1
        else:
            break
    bits = []  # (mantissa bit index, value)
    for b in range(51, 51 - n, -1):
        bits.append((b, (lo >> b) & 1))
    return bits


def eqs_for(pos, bits):
    out = []
    w = xs[pos]
    for b, v in bits:
        sb = b + 12 if VARIANT == 'hi' else b   # state0 bit index
        out.append((w[sb], v))
    return out


def solve(eqs):
    piv = {}
    red = 0
    for m, v in eqs:
        while m:
            h = m.bit_length() - 1
            if h in piv:
                pm, pv = piv[h]
                m ^= pm
                v ^= pv
            else:
                piv[h] = (m, v)
                break
        else:
            if v:
                return False, red
            red += 1
    return True, red


def main():
    d = pd.read_parquet('.cache/re/tommy-cs2-maker/calldata_all.parquet', columns=['maker', 'sign_ms', 'salt', 'price', 'token_id'])
    w = d[d.maker.str.lower() == WHO].copy()
    w['salt_i'] = w.salt.astype('int64')
    o = w.drop_duplicates('salt_i').sort_values('sign_ms').reset_index(drop=True)
    o['grp'] = (o.sign_ms.diff() > 3).cumsum()
    tried = hits = 0
    hit_red = []
    for g, gr in o.groupby('grp'):
        n = len(gr)
        if n < 4 or n > MAXN:
            continue
        kb = [known_bits(int(s), int(t)) for s, t in zip(gr.salt_i, gr.sign_ms)]
        tried += 1
        found = None
        npos = n + GAPS
        for posset in itertools.combinations(range(npos), n):
            for perm in itertools.permutations(range(n)):
                eqs = []
                for j, p in zip(perm, posset):
                    eqs += eqs_for(p, kb[j])
                ok, red = solve(eqs)
                if ok and red >= 8:
                    found = (perm, posset, red, len(eqs))
                    break
            if found:
                break
        if found:
            hits += 1
            hit_red.append(found[2])
            if hits <= 5:
                pr = gr.price.tolist()
                print('HIT grp', g, 'n', n, 'perm', found[0], 'pos', found[1], 'redundant', found[2], 'eqs', found[3],
                      'prices', [pr[i] for i in found[0]])
    print(f'variant {VARIANT} DT {DT} maxn {MAXN} gaps {GAPS}: groups tried {tried}, consistent (>=8 redundant) {hits}')


if __name__ == '__main__':
    main()
