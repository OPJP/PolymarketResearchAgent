import sys; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from engine import *
F = pickle.load(open(D + 'feat_5m.pkl', 'rb'))['fit']
mills = np.round(F.price * 1000).astype(int); off = (mills % 10 != 0)
print('off-cent share overall', float(off.mean()))
print('off-cent fills by price range:', pd.cut(F.price[off], [0, .04, .1, .5, .9, .96, 1]).value_counts().sort_index().to_dict())
print('all fills by price range:', pd.cut(F.price, [0, .04, .1, .5, .9, .96, 1]).value_counts().sort_index().to_dict())
for nm, c in (('bosona', 'y_b'), ('almach', 'y_a')):
    x = F[F[c] == 1]; m = np.round(x.price * 1000).astype(int) % 10 != 0
    print(nm, 'off-cent', int(m.sum()), 'price range', pd.cut(x.price[m], [0, .04, .1, .5, .9, .96, 1]).value_counts().sort_index().to_dict())
