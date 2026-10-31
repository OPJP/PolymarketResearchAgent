"""Explicit (hand-written, few-parameter) scores vs the wallet: within-market selection AUC on BUILD and VALIDATE."""
import sys, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker/code')
import numpy as np, pandas as pd
from evalkit import selection_report, within_auc

CACHE = '/home/user/PolymarketResearchAgent/.cache/re/dbdd-inplay-taker'
OUT = '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker'
F = pd.read_parquet(f'{CACHE}/feats.parquet')
F = F[F.period.isin(['BUILD', 'VALIDATE'])]
F = F[F.groupby('cid').is_wallet.transform('max').astype(bool)].reset_index(drop=True)
lq = np.log1p(F.quiet.clip(0, 1e5))
RULES = {
    'R1_quiet': lq,
    'R2_quiet_plus_flow60': lq + 1.0 * (F.flow60 > 0) + 0.5 * (F.mv30 > 0),
    'R3_quiet_flow_contra900': lq + 1.0 * (F.flow60 > 0) + 0.5 * (F.mv30 > 0) + 0.5 * (F.mv900 < 0),
    'R4_flow60_sign': (F.flow60 > 0).astype(float) + 0.001 * lq,
    'R5_mv10_pos': (F.mv10 > 0).astype(float) + 0.001 * lq,
}
res = {}
for nm, s in RULES.items():
    F['score'] = s.to_numpy()
    res[nm] = {p: selection_report(F[F.period == p], n_perm=0) for p in ['BUILD', 'VALIDATE']}
    print(nm, {p: (round(r['auc'], 4), round(r['recall'], 3), round(r['lift'], 2)) for p, r in res[nm].items()}, flush=True)
json.dump(res, open(f'{OUT}/explicit_rules_result.json', 'w'), indent=1, default=float)
