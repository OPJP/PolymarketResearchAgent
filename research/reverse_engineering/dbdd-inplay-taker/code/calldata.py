"""Catalog B1: decode V2 matchOrders calldata (selector 0x3c2b4399) for the wallet's fills.

matchOrders(bytes32 conditionId, Order takerOrder, Order[] makerOrders, uint256 takerFillAmount,
            uint256[] makerFillAmounts, uint256 takerFeeAmount, uint256[] makerFeeAmounts)
Order(uint256 salt, address maker, address signer, uint256 tokenId, uint256 makerAmount, uint256 takerAmount,
      uint8 side, uint8 signatureType, uint256 timestamp(ms), bytes32 metadata, bytes32 builder, bytes signature)

Keeps decoded fields only (no raw input). One row per transaction for the taker order, plus a compact
list of maker orders (maker, side, price, size, signing ms, fill amount).
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE
import pandas as pd, numpy as np
from polyrea.adapters.http import shared_client, HttpError

SEL = '3c2b4399'
RPCS = ('https://polygon-bor-rpc.publicnode.com',)  # drpc free plan rejects batches > 3 (HTTP 500, code 31)


def _w(data, i):
    return int(data[64 * i: 64 * (i + 1)], 16)


def _order(data, off_slot):
    """off_slot: index (in 32-byte words) where the tuple starts."""
    o = off_slot
    f = {
        'salt': _w(data, o), 'maker': '0x' + data[64 * (o + 1) + 24: 64 * (o + 2)],
        'signer': '0x' + data[64 * (o + 2) + 24: 64 * (o + 3)], 'tokenId': str(_w(data, o + 3)),
        'makerAmount': _w(data, o + 4), 'takerAmount': _w(data, o + 5), 'side': _w(data, o + 6),
        'sigType': _w(data, o + 7), 'ts_ms': _w(data, o + 8), 'metadata': data[64 * (o + 9): 64 * (o + 10)],
        'builder': data[64 * (o + 10): 64 * (o + 11)],
    }
    return f


def decode(inp):
    if not inp or inp[2:10] != SEL:
        return None
    d = inp[10:]
    cond = '0x' + d[0:64]
    t_off = _w(d, 1) // 32
    m_off = _w(d, 2) // 32
    taker_fill = _w(d, 3)
    mf_off = _w(d, 4) // 32
    taker_fee = _w(d, 5)
    tk = _order(d, t_off)
    n = _w(d, m_off)
    makers = []
    for k in range(n):
        rel = _w(d, m_off + 1 + k) // 32
        makers.append(_order(d, m_off + 1 + rel))
    nf = _w(d, mf_off)
    mfills = [_w(d, mf_off + 1 + k) for k in range(nf)]
    return cond, tk, makers, taker_fill, mfills, taker_fee


def price_size(o):
    # side 0 = BUY: makerAmount USDC, takerAmount shares; side 1 = SELL: makerAmount shares, takerAmount USDC
    if o['side'] == 0:
        usdc, sh = o['makerAmount'] / 1e6, o['takerAmount'] / 1e6
    else:
        sh, usdc = o['makerAmount'] / 1e6, o['takerAmount'] / 1e6
    return (usdc / sh if sh else np.nan), sh, usdc


def fetch(txs, batch=20, http=None):
    http = http or shared_client()
    out = {}
    for i in range(0, len(txs), batch):
        part = txs[i:i + batch]
        body = [{'jsonrpc': '2.0', 'id': j, 'method': 'eth_getTransactionByHash', 'params': [h]} for j, h in enumerate(part)]
        res = None
        for rpc in RPCS:
            try:
                r, src = http.post_json(rpc, body, adapter='polygon.rpc.tx', max_age=None, max_retries=3)
            except HttpError:
                continue
            if isinstance(r, list) and all(isinstance(x, dict) and x.get('result') for x in r):
                res = r
                break
        if res is None:
            continue
        for x in res:
            out[part[x['id']]] = x['result']
    return out


def rows_from(txmap, wallet):
    trow, mrow = [], []
    for h, tx in txmap.items():
        dec = decode(tx.get('input', ''))
        if dec is None:
            trow.append({'tx': h, 'ok': 0})
            continue
        cond, tk, makers, tfill, mfills, tfee = dec
        p, sh, usdc = price_size(tk)
        trow.append({'tx': h, 'ok': 1, 'block': int(tx['blockNumber'], 16), 'to': tx['to'], 'cid': cond,
                     't_maker': tk['maker'], 't_signer': tk['signer'], 't_token': tk['tokenId'], 't_side': tk['side'],
                     't_sigtype': tk['sigType'], 't_ts_ms': tk['ts_ms'], 't_px': p, 't_sh': sh, 't_usdc': usdc,
                     't_salt': str(tk['salt']), 't_meta': tk['metadata'], 't_builder': tk['builder'],
                     't_fill': tfill / 1e6, 't_fee': tfee / 1e6, 'n_makers': len(makers),
                     'is_wallet_taker': int(tk['maker'].lower() == wallet.lower())})
        for k, mo in enumerate(makers):
            mp, msh, musd = price_size(mo)
            mrow.append({'tx': h, 'k': k, 'm_maker': mo['maker'], 'm_side': mo['side'], 'm_token': mo['tokenId'],
                         'm_px': mp, 'm_sh': msh, 'm_ts_ms': mo['ts_ms'], 'm_fill': (mfills[k] / 1e6 if k < len(mfills) else np.nan),
                         'm_sigtype': mo['sigType'], 'm_builder': mo['builder'][-8:]})
    return pd.DataFrame(trow), pd.DataFrame(mrow)


if __name__ == '__main__':
    W = '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
    r = json.load(open(f'{CACHE}/sample_tx.json'))
    txm = {str(i): x['result'] for i, x in enumerate(r)}
    t, m = rows_from(txm, W)
    pd.set_option('display.width', 250)
    print(t.T)
    print(m)
