"""X142 (assumptions panel iter-9 P3), step 1: per-lot base rates and lift ceilings from the LISTING PROJECTION
(listing_proj_iter10.parquet, CS2; listing aggregates for Dota from tier12_listing.json) and the development stratum
traded rates (events_sel: CS2 events of 16-22 Oct; Dota: PARI Universe 3 of 4 on 10-22, other Dota from the v4 table
prior). PGL Masters (the h1 / h2 non-GRID tier-2 league, never seen in development) is bracketed: skipped (0) or traded
like non-GRID tier 3 (0.91). Lift ceiling = 1 / base rate; the recall needed to reach lift 3 at a given precision.
Output: results/lift_ceiling.json
"""
import json
import pandas as pd

ROOT = '.cache/re/tommy-cs2-maker'
RES = 'research/reverse_engineering/tommy-cs2-maker/results'
L = pd.read_parquet(f'{ROOT}/listing_proj_iter10.parquet')
E = pd.read_parquet(f'{ROOT}/events_sel.parquet')
rate = E[~E.grid.astype(bool)].groupby(E.tier.astype(str)).y.mean().to_dict()
t12 = json.load(open(f'{RES}/tier12_listing.json'))
res = {'dev_rates_cs2_nongrid_by_tier': {k: round(v, 3) for k, v in rate.items()}}
for lot in ('h1', 'h2', 'fwd'):
    x = L[L.lot == lot]
    ng = x[~x.grid]
    exp = sum(rate.get(t, 0.0) * n for t, n in ng[~ng.league.isin(['PGL Masters', 'IEM', 'BLAST Rivals'])].tier.value_counts().items())
    big = int(ng.league.isin(['PGL Masters', 'IEM', 'BLAST Rivals']).sum())
    d = t12.get('dota2_lot_mix', {}).get(lot, {})
    dn = int(d.get('events', 0)); dpari = int(d.get('nongrid_by_tier', {}).get('2', 0)); dother = int(d.get('nongrid_by_tier', {}).get('5', 0)) + int(d.get('nongrid_by_tier', {}).get('4', 0))
    dexp = 0.75 * dpari + 0.1 * dother
    N = int(len(x)) + dn
    lo = (exp + dexp) / N
    hi = (exp + dexp + rate.get('3', 0.9) * big) / N
    res[lot] = {'events_cs2': int(len(x)), 'events_dota': dn, 'expected_positives_excl_big': round(exp + dexp, 1),
                'big_nongrid_tier12_events': big, 'base_rate_range': [round(lo, 3), round(hi, 3)],
                'lift_ceiling_range': [round(1 / hi, 2), round(1 / lo, 2)],
                'precision_needed_for_lift3': [round(3 * lo, 3), round(3 * hi, 3)]}
json.dump(res, open(f'{RES}/lift_ceiling.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
