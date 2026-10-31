"""Iteration 5 (catalog B1): V2 matchOrders calldata -> every order in each transaction (taker order and maker orders) with
its millisecond signing time, full original size, limit price, salt, signer, signatureType, metadata and builder codes.

- fetch_txs(hashes): batched eth_getTransactionByHash (JSON-RPC batch of BATCH calls per POST, drpc then publicnode),
  polite rate (<= 3 POST/s). Raw inputs are NOT stored anywhere (decoded fields only, per the brief).
- decode(input_hex): matchOrders(bytes32 conditionId, Order takerOrder, Order[] makerOrders, uint256 takerFillAmount,
  uint256[] makerFillAmounts, uint256 takerFeeAmount, uint256[] makerFeeAmounts), selector 0x3c2b4399;
  Order(uint256 salt, address maker, address signer, uint256 tokenId, uint256 makerAmount, uint256 takerAmount,
  uint8 side, uint8 signatureType, uint256 timestamp, bytes32 metadata, bytes32 builder, bytes signature).
CLI: python calldata.py IN_PARQUET(with column tx) OUT_PARQUET  -> one row per order per tx (role T for the taker order)."""
import os, sys, time, json, threading
import numpy as np, pandas as pd, httpx

RPCS = ["https://polygon.drpc.org", "https://polygon-bor-rpc.publicnode.com"]
SEL_MATCH = "3c2b4399"
BATCH = 25
_lock = threading.Lock(); _next = [0.0]
RATE = 3.0


def _wait():
    with _lock:
        now = time.monotonic()
        t = max(now, _next[0]); _next[0] = t + 1.0 / RATE
    if t > now:
        time.sleep(t - now)


def _w(b, i):
    return int.from_bytes(b[i:i + 32], "big")


def _order(b, base):
    f = [_w(b, base + 32 * k) for k in range(12)]
    so = base + f[11]
    slen = _w(b, so)
    return dict(salt=f[0], maker="0x%040x" % f[1], signer="0x%040x" % f[2], token=str(f[3]), maker_amt=f[4] / 1e6,
                taker_amt=f[5] / 1e6, oside=f[6], sig_type=f[7], sign_ms=f[8], metadata="%064x" % f[9],
                builder="%064x" % f[10], sig_len=slen)


def decode(inp: str):
    h = inp[2:] if inp.startswith("0x") else inp
    if h[:8] != SEL_MATCH:
        return None
    b = bytes.fromhex(h[8:])
    cid = "0x%064x" % _w(b, 0)
    t_off = _w(b, 32); m_off = _w(b, 64); tfill = _w(b, 96) / 1e6; mf_off = _w(b, 128); tfee = _w(b, 160) / 1e6; mfee_off = _w(b, 192)
    taker = _order(b, t_off)
    n = _w(b, m_off)
    makers = [_order(b, m_off + 32 + _w(b, m_off + 32 + 32 * i)) for i in range(n)]
    nf = _w(b, mf_off); mfills = [_w(b, mf_off + 32 + 32 * i) / 1e6 for i in range(nf)]
    ne = _w(b, mfee_off); mfees = [_w(b, mfee_off + 32 + 32 * i) / 1e6 for i in range(ne)]
    rows = [dict(cid=cid, role="T", idx=-1, fill_amt=tfill, fee_amt=tfee, n_makers=n, **taker)]
    for i, o in enumerate(makers):
        rows.append(dict(cid=cid, role="M", idx=i, fill_amt=mfills[i] if i < nf else np.nan, fee_amt=mfees[i] if i < ne else np.nan, n_makers=n, **o))
    return rows


def _post(client, body):
    last = None
    for attempt in range(6):
        for url in RPCS:
            _wait()
            try:
                r = client.post(url, json=body, timeout=60)
                if r.status_code == 200:
                    res = r.json()
                    if isinstance(res, list) and all(isinstance(x, dict) and x.get("result") for x in res):
                        return res
                    last = str(res)[:200]
                else:
                    last = f"HTTP {r.status_code} {r.text[:120]}"
            except Exception as e:  # network
                last = repr(e)[:200]
        time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"batch failed: {last}")


def fetch_txs(hashes, threads=2, log_every=50):
    """Yield decoded order rows for each tx hash (batched JSON-RPC)."""
    hashes = list(dict.fromkeys(hashes))
    chunks = [hashes[i:i + BATCH] for i in range(0, len(hashes), BATCH)]
    out = []; done = [0]; t0 = time.time()
    from concurrent.futures import ThreadPoolExecutor
    client = httpx.Client(http2=False)

    def job(ch):
        body = [{"jsonrpc": "2.0", "id": i, "method": "eth_getTransactionByHash", "params": [h]} for i, h in enumerate(ch)]
        try:
            res = _post(client, body)
        except Exception as e:
            print("FAILED chunk", ch[0], e, flush=True)
            return []
        rows = []
        for x in res:
            tx = x["result"]
            dec = decode(tx["input"])
            base = dict(tx=tx["hash"], to=tx["to"], frm=tx["from"], block=int(tx["blockNumber"], 16), sel=tx["input"][2:10], gas_price=int(tx.get("gasPrice", "0x0"), 16) / 1e9,
                        nonce=int(tx["nonce"], 16), tx_index=int(tx["transactionIndex"], 16))
            if dec is None:
                rows.append(dict(base, role="?"))
            else:
                for r in dec:
                    rows.append(dict(base, **r))
        return rows

    with ThreadPoolExecutor(threads) as ex:
        for rows in ex.map(job, chunks):
            out.extend(rows); done[0] += 1
            if done[0] % log_every == 0:
                print(f"{done[0]}/{len(chunks)} batches, {len(out)} rows, {time.time()-t0:.0f}s", flush=True)
    return out


def to_frame(rows):
    df = pd.DataFrame(rows)
    for c in ("salt",):
        if c in df:
            df[c] = df[c].map(lambda v: str(int(v)) if v == v and v is not None else None)
    for c in ("sign_ms",):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    hs = pd.read_parquet(src, columns=["tx"]).tx.drop_duplicates().tolist()
    print(len(hs), "txs", flush=True)
    rows = fetch_txs(hs)
    df = to_frame(rows)
    df.to_parquet(dst, index=False)
    print("DONE", len(df), flush=True)
