"""Minimal activity sequences that expose build_ledger accounting errors (expected vs. coded open capital)."""
import _env
from polyrea.analysis.ledger import build_ledger
def row(ts, typ, size=0, usdc=0, side=None, asset='', price=0, cid='C', oi=None):
    return dict(timestamp=ts, type=typ, size=size, usdcSize=usdc, side=side, asset=asset, price=price, conditionId=cid, outcomeIndex=oi, transactionHash=f'0x{ts}')
def level(led):
    s = led.exposure_series(); return float(s.iloc[-1]) if len(s) else 0.0
cases = {
 '1 SPLIT 100 -> MERGE 100 -> SPLIT 100 -> MERGE 100 (expect 0)': [row(1, 'SPLIT', 100, 100), row(2, 'MERGE', 100, 100), row(3, 'SPLIT', 100, 100), row(4, 'MERGE', 100, 100)],
 '2 SPLIT 100, sell both legs at 0.5 (expect 0)': [row(1, 'SPLIT', 100, 100), row(2, 'TRADE', 100, 50, 'SELL', 'Y', .5, oi=0), row(3, 'TRADE', 100, 50, 'SELL', 'N', .5, oi=1)],
 '3 SPLIT 100, hold to resolution (t=10), never redeem (expect 0 after t=10)': [row(1, 'SPLIT', 100, 100), row(20, 'REWARD', 0, 1, cid='')],
 '4 SPLIT 100 + BUY 100 YES@0.6, MERGE 100 (expect 60 left: 100 YES)': [row(1, 'SPLIT', 100, 100), row(2, 'TRADE', 100, 60, 'BUY', 'Y', .6, oi=0), row(3, 'MERGE', 100, 100)],
}
res_ts = {'C': 10}
for name, rows in cases.items():
    led = build_ledger('0xw', rows, res_ts if name.startswith('3') else {})
    print(f'{name:75s} coded open capital {level(led):7.2f}   raw cum {sum(e[1] for e in led.exposure_events):8.2f}')
