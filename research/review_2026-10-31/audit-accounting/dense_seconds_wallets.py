"""For all 19 dense seconds: rows kept by the code (default-limit page) vs the full second; whose rows were dropped."""
import _env, sqlite3, zlib, json, re, collections
from polyrea.adapters.http import HttpClient
from polyrea.adapters.polymarket import activity_key
db = sqlite3.connect('file:' + _env.SCR + '/cache/http.sqlite?mode=ro', uri=True)
http = HttpClient()
studied = {v: k for k, v in _env.WALLETS.items()}
studied.update({'0x3048d65321be3497164cdfc2996f94f98a2e7537': 'MoneyForWhiskas', '0xc53375ff94e96100f2b30a4b5775db35218d69a9': 'dangerously'})
tot_kept = tot_true = 0
lost_by = collections.Counter(); lost_buy_by = collections.Counter(); taker_rows_lost = 0
for url, body in db.execute("select url, body from responses where url like 'https://data-api.polymarket.com/trades%' and url like '%offset=%' and url not like '%limit=%'"):
    q = dict(re.findall(r'([a-zA-Z]+)=([^&]+)', url.split('?', 1)[1]))
    kept = json.loads(zlib.decompress(body))
    full = []
    for off in range(0, 5001, 500):
        rows, _ = http.get_json('https://data-api.polymarket.com/trades', {'market': q['market'], 'takerOnly': q['takerOnly'], 'start': q['start'], 'end': q['end'], 'limit': 500, 'offset': off}, adapter='audit', max_age=None)
        full += rows
        if len(rows) < 500: break
    tk, _ = http.get_json('https://data-api.polymarket.com/trades', {'market': q['market'], 'takerOnly': 'true', 'start': q['start'], 'end': q['end'], 'limit': 500}, adapter='audit', max_age=None)
    lost = collections.Counter(activity_key(r) + ((r.get('proxyWallet') or '').lower(),) for r in full) - collections.Counter(activity_key(r) + ((r.get('proxyWallet') or '').lower(),) for r in kept)
    tot_kept += len(kept); tot_true += len(full)
    for k, v in lost.items():
        lost_by[studied.get(k[-1], 'other')] += v
        if k[3] == 'BUY': lost_buy_by[studied.get(k[-1], 'other')] += v
print(f'19 dense seconds: kept {tot_kept} of {tot_true} rows ({1 - tot_kept / tot_true:.0%} dropped)')
print('dropped rows by wallet:', dict(lost_by.most_common()))
print('dropped BUY rows by wallet:', dict(lost_buy_by.most_common()))
