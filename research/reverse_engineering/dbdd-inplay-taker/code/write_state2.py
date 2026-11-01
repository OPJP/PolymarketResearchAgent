"""Bring state.json to the 2026-11-01 brief format and record iteration 2.

Reads the iteration-1 state.json, keeps its hypotheses and legacy studies, and adds: catalog (A-E + X items),
dimensions (E1), indicators (legacy rows + this iteration's), components with tags, target_metrics, live_lab,
sealed_from. Results of this iteration are read from results/iter2_*.json when present.
"""
import sys, os, json, glob, time
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import ROOT
import indicators as ind

WS = os.path.join(ROOT, 'research', 'reverse_engineering', 'dbdd-inplay-taker')
st = json.load(open(os.path.join(WS, 'state.json')))
R = {}
for f in glob.glob(os.path.join(WS, 'results', 'iter2_*.json')):
    R[os.path.basename(f)[6:-5]] = json.load(open(f))


def g(key, *path, default=None):
    x = R.get(key)
    for p in path:
        if not isinstance(x, dict) or p not in x:
            return default
        x = x[p]
    return x


# ------------------------------------------------------------------ catalog
C = {}


def cat(i, status, evidence):
    C[i] = {'status': status, 'evidence': evidence}


cat('A1', 'not_applicable', 'Sports markets settle on the official result through UMA; no settlement feed exists before the '
    'result, so it cannot drive in-play decisions. Score feeds are covered by A5.')
cat('A2', 'not_applicable', 'No crypto markets in the traded universe (Gamma families of all 14,441 markets traded since '
    '2026-09-21: sports and esports only).')
cat('A3', 'not_applicable', 'Same as A2: no crypto or derivatives-linked markets traded.')
cat('A4', 'open', 'Same-event Polymarket markets: iteration 1 sibling-move features had low gain; iteration 2 live-book test '
    'of sibling moves before decisions: see results/iter2_live_books.json. Cross-market fair-value consistency (X2) open.')
cat('A4b', 'open', 'Kalshi sports markets as an earlier or sharper venue: not fetched yet.')
cat('A5', 'open', 'ESPN soccer goals tested (iteration 1 + iteration 2 at signing-time resolution). A5a sports websocket: '
    'iteration 2 live test (results/iter2_sports_ws.json). League feeds (MLB statsapi, NHL, NBA) and esports feeds (bo3.gg, '
    'liquipedia) not tried.')
cat('A6', 'open', 'News/social for in-play sports: low prior; not tried.')
cat('A7', 'tried', 'Tape state (quiet, flow, moves, prints so far) in iteration 1 (R-LGB-PUB-1, R1-R5); iteration 2: recorded '
    'books at signing time (live_books).')
cat('A8', 'open', 'Operational events (engine restarts, pauses) vs activity swings: not tried.')
cat('B1', 'tried', 'Iteration 2: decoded V2 matchOrders calldata for the wallet fills (results/iter2_b1.json): signing ms, '
    'limit price, order USDC, fill ratio, maker quotes hit.')
cat('B2', 'not_applicable', '100% taker: the wallet never rests orders (B1: its order is the takerOrder in every decoded '
    'transaction). The maker quotes it hits are analysed under X2/C3.')
cat('B3', 'tried', 'For a taker the limit price is the decision price: iteration 2 B1 shows limit == best ask (touch) for '
    'nearly all orders; fair value cannot be read from the limit. Inverse fit moved to the stake (size) instead (open).')
cat('B4', 'open', 'MERGE rows exist in the history (4,446 in iteration 1); both tokens bought in 23.6% of markets. Not analysed.')
cat('B5', 'open', 'Inventory and risk conditioning of side/size: not tried.')
cat('B6', 'open', 'TAKER_REBATE rows (143 in history); Gold taker tier. Rebate share of PnL not computed.')
cat('B7', 'ruled_out', 'Taker only: 0 REWARD rows among 509,053 activity rows (iteration 1 type counts); liquidity rewards '
    'need resting orders.')
cat('B8', 'open', 'holdingRewardsEnabled not checked for its markets.')
cat('B9', 'not_applicable', 'Maker rebate pool share needs maker fills; the wallet has none (B1, 100% taker).')
cat('C1', 'open', 'B1: every order is signed by one EOA 0x74ba1dfa460c2e51487bc7ac7dff87621fb43ae9 (signatureType 1, '
    'POLY_PROXY). Other proxies signed by the same EOA not searched yet.')
cat('C2', 'open', 'Iteration 1 found a 21-wallet co-trading cluster acting in both orders. Strong form (X1) open.')
cat('C3', 'tried', 'B1 maker side of its fills: counterparties and the age of the quotes it hits (results/iter2_b1.json).')
cat('C4', 'open', 'Change points over the whole history not run (history re-fetch only from 2026-09-21 this iteration).')
cat('C5', 'open', 'Hour-of-day profile and reaction delays vs human: partly in iteration 2 (signing latency).')
cat('C6', 'open', 'Combos/RFQ: not checked.')
cat('C7', 'open', 'Self-matching: B1 maker wallets checked against the wallet (results/iter2_b1.json self_match).')
cat('C8', 'tried', 'B1 fingerprint: salts ~1e17-1e19 (64-bit random, not the TypeScript round(random*Date.now()) ~1e12 nor '
    'py-clob-client round(time*random) ~1e9), no builder or metadata codes, signatureType 1, integer-USDC FAK orders. '
    'GitHub bot search not done.')
cat('D1', 'tried', 'Unit of decision = one signed FAK order (B1), timed at its signing ms (iteration 2).')
cat('D2', 'open', 'Hazard/survival and state-machine models not tried; only LightGBM on print populations.')
cat('D3', 'open', 'Order-by-order replay against the recorded books not built.')
cat('D4', 'open', 'PnL decomposition by component not done beyond per-family PnL (iteration 1).')
for e in ['E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E7']:
    cat(e, 'open', '')
C['E1']['evidence'] = 'Inventory written in iteration 2 (state.json dimensions), one or more entries per family.'
C['E2']['evidence'] = 'Iteration 2: residual shape from B1 + live books (NOTES Missing dimensions); out-of-fold refit of a ' \
                      'selection model on BUILD tapes not yet redone (tapes re-fetched for a sample only).'
C['E3']['evidence'] = 'First screen pre-registered in NOTES (iteration 2); run status in results/iter2_e3_*.json.'
cat('X1', 'open', 'Reviewer lead 2026-10-31: strong-form copy trading (same token and side, fixed size ratio, 0-30 s lag). '
    'Test in results/iter2_copy.json.')
cat('X2', 'open', 'Reviewer lead 2026-10-31: stale-quote sniping against a fair value made consistent across the same event '
    "(moneyline, draw, totals ladder). Iteration 2: age of hit quotes vs other takers' (B1), book state at signing (live).")
cat('X3', 'open', "Reviewer lead 2026-10-31: Polymarket sports websocket soccer minutes and scores as the trigger. "
    'Iteration 2 live test.')
for k, v in (R.get('catalog_updates') or {}).items():
    C[k] = v
st['catalog'] = C
open_items = sorted(k for k, v in C.items() if v['status'] == 'open')
json.dump(open_items, open(os.path.join(WS, 'results', 'catalog_open.json'), 'w'))
print('catalog open', len(open_items), open_items)
json.dump(st, open(os.path.join(WS, 'state.json'), 'w'), indent=1)
