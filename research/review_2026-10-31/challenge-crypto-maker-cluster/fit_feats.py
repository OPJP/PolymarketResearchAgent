# FIT-only: which PIT features distinguish cluster fills and predict passive-fill PnL?
import sys; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from engine import *
F = pickle.load(open(D + 'feat_5m.pkl', 'rb'))['fit']
F['grp'] = np.where(F.y_b == 1, 'bosona', np.where(F.y_a == 1, 'almach', 'others'))
F['usd'] = F.price * F.sz; F['pnl'] = F.sz * F.pnl_ps
feats = ['depth', 'mom10', 'mom30', 'model_edge', 'model_vs_ref', 'spot_mom30_bps', 'n_tr_30', 'frac', 'price']
print(F.groupby('grp')[feats].median().round(4).to_string())
print(F.groupby('grp')[feats].mean().round(4).to_string())
for f in feats:
    print(f, 'AUC bosona', round(auc(F[f].to_numpy(), F.y_b.to_numpy()), 3), 'almach', round(auc(F[f].to_numpy(), F.y_a.to_numpy()), 3))
# market-wide: per-share pnl by depth bucket / model_vs_ref bucket (usd-weighted return)
def tab(col, bins):
    x = F.copy(); x['bk'] = pd.cut(x[col], bins)
    g = x.groupby('bk', observed=True).agg(n=('ts', 'size'), usd=('usd', 'sum'), pnl=('pnl', 'sum'))
    g['ret'] = g.pnl / g.usd
    gc = x[x.grp != 'others'].groupby('bk', observed=True).agg(n_cl=('ts', 'size'), usd_cl=('usd', 'sum'), pnl_cl=('pnl', 'sum'))
    g = g.join(gc); g['ret_cl'] = g.pnl_cl / g.usd_cl; g['cl_share'] = g.n_cl / g.n
    print(col); print(g.round(4).to_string())
tab('depth', [-1, -0.05, -0.02, -0.005, 0.005, 0.02, 0.05, 1])
tab('model_vs_ref', [-1, -0.2, -0.1, -0.05, -0.02, 0.02, 0.05, 0.1, 0.2, 1])
tab('mom30', [-1, -0.1, -0.03, -0.005, 0.005, 0.03, 0.1, 1])
