"""Iteration 8, X110 (mechanics panel iter7 P4): recover the key that actually signs each order from its ERC-7739
nested signature (signatureType 3 deposit wallets), and compare keys across the wallet's maker / taker legs, days,
regimes and the feed's other subscribers / merge-law siblings. sigType 1 / 2 orders carry the signing EOA in the
`signer` field (plain ECDSA), which is recorded as is.

Pure Python keccak-256 and secp256k1 recovery (no package install). Self-tests: keccak256(b"") and, per order, the
Order struct hash recomputed from the decoded fields must equal the 32-byte `contents` inside the signature.
ERC-7739 (Solady layout): sig = r || s || v || APP_DOMAIN_SEPARATOR || contents || contentsType || uint16(len);
digest = keccak(0x1901 || APP_DOMAIN_SEPARATOR || keccak(TYPEHASH || contents || keccak(name) || keccak(version) ||
chainId || verifyingContract || salt)), TYPEHASH = keccak("TypedDataSign(Order contents,string name,string version,
uint256 chainId,address verifyingContract,bytes32 salt)" || contentsType); (name, version, chainId,
verifyingContract, salt) from the account's eip712Domain() (ERC-5267).
Only (tx, idx, maker, sig_type, signer_field, recovered, ok flags) are stored: .cache/re/tommy-cs2-maker/sig_signers.parquet
Output: results/sig_signers.json
"""
from __future__ import annotations

import glob
import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
RPC = "https://polygon-bor-rpc.publicnode.com"
H = 1792713600
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
TARGETS = {
    "wallet": WALLET, "P4e": "0x4ebc2722adc772bde8680792d0a6fdf15499a33d", "P93": "0x93078b5dd1c34d0f288d2f51b23f1347520d9da3",
    "f1ee4842": "0xf1ee4842fa0c7283632185e42577027452d4519c", "2005d16a": "0x2005d16a84ceefa912d4e380cd32e7ff827875ea",
    "8a80528d": "0x8a80528dce46711a54aa3455c2cc81dea51e11c5", "ddb6e624": "0xddb6e6246546230503f153506ac1e9914978b9b3",
    "f1f2b3c6": "0xf1f2b3c6c5bea42a6664fe3a8395addc1ab28c8d", "52661b8e": "0x52661b8e13158f23d94a9e8302ab0295704c22ac",
    "51dbdd2b": "0x51dbdd2b19427dc8e88bb15a4046a38d8427f9b3",
}

# ---------------- keccak-256 ----------------
RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
      0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
      0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
      0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
      0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
M64 = (1 << 64) - 1


def _rol(x, n):
    n %= 64
    return ((x << n) | (x >> (64 - n))) & M64 if n else x


def _f(A):
    for rnd in range(24):
        C = [A[x][0] ^ A[x][1] ^ A[x][2] ^ A[x][3] ^ A[x][4] for x in range(5)]
        D = [C[(x - 1) % 5] ^ _rol(C[(x + 1) % 5], 1) for x in range(5)]
        A = [[A[x][y] ^ D[x] for y in range(5)] for x in range(5)]
        B = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                B[y][(2 * x + 3 * y) % 5] = _rol(A[x][y], ROT[x][y])
        A = [[B[x][y] ^ ((~B[(x + 1) % 5][y]) & B[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        A[0][0] ^= RC[rnd]
    return A


def keccak(data: bytes) -> bytes:
    rate = 136
    d = bytearray(data)
    d.append(0x01)
    while len(d) % rate:
        d.append(0)
    d[-1] |= 0x80
    A = [[0] * 5 for _ in range(5)]
    for off in range(0, len(d), rate):
        blk = d[off:off + rate]
        for i in range(rate // 8):
            A[i % 5][i // 5] ^= int.from_bytes(blk[8 * i:8 * i + 8], "little")
        A = _f(A)
    return b"".join(A[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


# ---------------- secp256k1 recovery ----------------
P = 2 ** 256 - 2 ** 32 - 977
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)


def _add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    (x1, y1), (x2, y2) = p1, p2
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if p1 == p2:
        lam = 3 * x1 * x1 * pow(2 * y1, -1, P) % P
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, P) % P
    x3 = (lam * lam - x1 - x2) % P
    return x3, (lam * (x1 - x3) - y1) % P


def _mul(k, pt):
    r = None
    while k:
        if k & 1:
            r = _add(r, pt)
        pt = _add(pt, pt)
        k >>= 1
    return r


def recover(h: bytes, r: int, s: int, v: int) -> str | None:
    if v >= 27:
        v -= 27
    if not (0 < r < N and 0 < s < N) or v not in (0, 1):
        return None
    x = r
    y2 = (pow(x, 3, P) + 7) % P
    y = pow(y2, (P + 1) // 4, P)
    if (y * y) % P != y2:
        return None
    if y % 2 != v:
        y = P - y
    e = int.from_bytes(h, "big") % N
    rinv = pow(r, -1, N)
    Q = _add(_mul(s * rinv % N, (x, y)), _mul((-e * rinv) % N, G))
    if Q is None:
        return None
    pub = Q[0].to_bytes(32, "big") + Q[1].to_bytes(32, "big")
    return "0x" + keccak(pub)[12:].hex()


# ---------------- order decoding with the signature ----------------
ORDER_TYPE = (b"Order(uint256 salt,address maker,address signer,uint256 tokenId,uint256 makerAmount,uint256 takerAmount,"
              b"uint8 side,uint8 signatureType,uint256 timestamp,bytes32 metadata,bytes32 builder)")
ORDER_TH = None


def _orders(inp: str):
    data = bytes.fromhex(inp[10:])
    w = lambda i: int.from_bytes(data[32 * i:32 * i + 32], "big")  # noqa: E731

    def one(off, idx):
        words = [data[off + 32 * k: off + 32 * k + 32] for k in range(12)]
        so = int.from_bytes(words[11], "big")
        ln = int.from_bytes(data[off + so: off + so + 32], "big")
        sig = data[off + so + 32: off + so + 32 + ln]
        return {"idx": idx, "words": words[:11], "maker": "0x" + words[1][12:].hex(), "signer": "0x" + words[2][12:].hex(),
                "sig_type": int.from_bytes(words[7], "big"), "sign_ms": int.from_bytes(words[8], "big"), "sig": sig}
    out = [one(w(1), -1)]
    mo = w(2)
    n = w(mo // 32)
    base = mo + 32
    for k in range(n):
        out.append(one(base + int.from_bytes(data[base + 32 * k: base + 32 * k + 32], "big"), k))
    return out


def eip712_domain(cli, addr):
    r = cli.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": addr, "data": "0x84b0196e"}, "latest"]}).json()
    res = r.get("result")
    if not res or res == "0x":
        return None, r
    d = bytes.fromhex(res[2:])
    w = lambda i: int.from_bytes(d[32 * i:32 * i + 32], "big")  # noqa: E731

    def string(off):
        ln = int.from_bytes(d[off:off + 32], "big")
        return d[off + 32: off + 32 + ln]
    return {"name": string(w(1)), "version": string(w(2)), "chainId": w(3), "vc": d[32 * 4 + 12: 32 * 5],
            "salt": d[32 * 5: 32 * 6]}, None


def main():
    global ORDER_TH
    assert keccak(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470", "keccak self-test"
    ORDER_TH = keccak(ORDER_TYPE)
    rng = np.random.default_rng(8)
    ca = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker", "idx", "sign_ms"])
    fs = sorted(glob.glob(str(OUT / "calldata_pub" / "*.parquet")))
    cp = pd.concat([pd.read_parquet(f, columns=["tx", "maker", "idx", "sign_ms"]) for f in fs])
    allc = pd.concat([ca, cp]).drop_duplicates(["tx", "idx"])
    allc["maker"] = allc.maker.str.lower()
    allc = allc[(allc.sign_ms > 1.7e12) & (allc.sign_ms < H * 1000)]
    picks = []
    w = allc[allc.maker == WALLET]
    for role, sub in (("taker", w[w.idx == -1]), ("maker", w[w.idx >= 0])):
        sub = sub.assign(day=(sub.sign_ms // 86400000))
        for _, g in sub.groupby("day"):  # spread over days
            picks += list(g.tx.drop_duplicates().sample(min(12, g.tx.nunique()), random_state=1))
    for k, a in TARGETS.items():
        if k == "wallet":
            continue
        sub = allc[allc.maker == a]
        sub = sub[sub.idx == -1] if (sub.idx == -1).sum() >= 10 else sub
        picks += list(sub.tx.drop_duplicates().sample(min(15, sub.tx.nunique()), random_state=2))
    tr = pd.read_parquet(OUT / "taker_regime_txs_1001_1015.parquet")
    picks += list(tr.tx.drop_duplicates().sample(min(30, len(tr)), random_state=3))
    picks = list(dict.fromkeys(picks))
    print("txs", len(picks), flush=True)
    cli = httpx.Client(timeout=40, headers={"User-Agent": "polyrea-research"})
    doms, dom_err = {}, {}
    rows = []
    for i in range(0, len(picks), 40):
        part = picks[i:i + 40]
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(part)]
        for attempt in range(6):
            try:
                res = cli.post(RPC, json=body).json()
                if isinstance(res, list):
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(3 + 3 * attempt)
        for x in res:
            t = x.get("result") if isinstance(x, dict) else None
            if not t:
                continue
            inp = t.get("input", "")
            if not inp.startswith("0x3c2b4399"):
                rows.append({"tx": t["hash"], "idx": -9, "maker": (t.get("to") or "").lower(), "sig_type": -1, "selector": inp[:10]})
                continue
            for o in _orders(inp):
                mk = o["maker"].lower()
                row = {"tx": t["hash"], "idx": o["idx"], "maker": mk, "sig_type": o["sig_type"], "sign_ms": o["sign_ms"],
                       "signer_field": o["signer"].lower(), "sig_len": len(o["sig"]), "selector": inp[:10], "to": (t.get("to") or "").lower()}
                sig = o["sig"]
                if o["sig_type"] == 3 and len(sig) >= 65 + 64 + 2:
                    ln = int.from_bytes(sig[-2:], "big")
                    ctype = sig[-2 - ln:-2]
                    app = sig[65:97]
                    contents = sig[97:129]
                    sh = keccak(ORDER_TH + b"".join(o["words"]))
                    row["contents_ok"] = sh == contents
                    row["ctype_ok"] = ctype == ORDER_TYPE
                    row["app_sep"] = app.hex()[:16]
                    if mk not in doms and mk not in dom_err:
                        dm, err = eip712_domain(cli, mk)
                        if dm is None:
                            dom_err[mk] = str(err)[:200]
                        else:
                            doms[mk] = dm
                    dm = doms.get(mk)
                    if dm is not None:
                        th = keccak(b"TypedDataSign(Order contents,string name,string version,uint256 chainId,address verifyingContract,bytes32 salt)" + ctype)
                        st = keccak(th + contents + keccak(dm["name"]) + keccak(dm["version"]) + dm["chainId"].to_bytes(32, "big")
                                    + b"\x00" * 12 + dm["vc"] + dm["salt"])
                        dig = keccak(b"\x19\x01" + app + st)
                        row["recovered"] = recover(dig, int.from_bytes(sig[0:32], "big"), int.from_bytes(sig[32:64], "big"), sig[64])
                elif len(sig) == 65:
                    row["recovered"] = None  # plain ECDSA by signer_field (sigType 1 / 2): the EOA is the signer field
                rows.append(row)
        time.sleep(0.5)
    R = pd.DataFrame(rows)
    R.to_parquet(OUT / "sig_signers.parquet", index=False)
    inv = {v: k for k, v in TARGETS.items()}
    res = {"txs": len(picks), "orders": int(len(R)), "domains": {k: {"name": v["name"].decode(errors="replace"),
                                                                     "version": v["version"].decode(errors="replace"),
                                                                     "chainId": v["chainId"], "verifyingContract": "0x" + v["vc"].hex()}
                                                                 for k, v in list(doms.items())[:5]},
           "domain_errors": dict(list(dom_err.items())[:5]), "selectors": R.selector.value_counts().to_dict()}
    s3 = R[R.sig_type == 3]
    res["sigtype3_orders"] = int(len(s3))
    res["contents_ok_share"] = round(float(s3.contents_ok.mean()), 4) if len(s3) else None
    res["ctype_ok_share"] = round(float(s3.ctype_ok.mean()), 4) if len(s3) else None
    R["key"] = np.where(R.sig_type == 3, R.get("recovered"), R.signer_field)
    per = {}
    for mk, g in R[R.maker.isin(set(TARGETS.values()))].groupby("maker"):
        o = {"orders": int(len(g)), "sig_type": g.sig_type.value_counts().to_dict(), "keys": g.key.value_counts().head(4).to_dict()}
        if mk == WALLET:
            o["keys_taker_leg"] = g[g.idx == -1].key.value_counts().head(4).to_dict()
            o["keys_maker_leg"] = g[g.idx >= 0].key.value_counts().head(4).to_dict()
            g2 = g.assign(day=pd.to_datetime(g.sign_ms, unit="ms").dt.strftime("%m-%d"))
            o["keys_by_day"] = {d: x.key.value_counts().head(2).to_dict() for d, x in g2.groupby("day")}
        per[inv[mk]] = o
    res["per_target"] = per
    # keys shared across makers (any maker in the sampled txs)
    km = R[R.key.notna()].groupby("key").maker.nunique()
    shared = km[km > 1]
    res["keys_shared_by_several_makers"] = {k: sorted(R.loc[R.key == k, "maker"].unique().tolist())[:6] for k in shared.index[:20]}
    res["distinct_makers"] = int(R.maker.nunique())
    res["distinct_keys"] = int(R.key.nunique())
    print(json.dumps(res, indent=1, default=str))
    json.dump(res, open(RES / "sig_signers.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
