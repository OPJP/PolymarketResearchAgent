import os, sys
SCR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('POLYREA_CACHE_DIR', os.path.join(SCR, 'cache'))
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
AS_OF = 1793318400
WALLETS = {
 'elmcap2': '0xed107a85a4585a381e48c7f7ca4144909e7dd2e5',
 'justaluckydude': '0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705',
 'GoodFallen': '0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6',
 'RN1': '0x2005d16a84ceefa912d4e380cd32e7ff827875ea',
 'dbdd': '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de',
 'b55f': '0xb55fa1296e6ec55d0ce53d93b9237389f11764d4',
 'almach': '0x3725d52f3c252e8374999cc8617292ea2608ad88',
 'bosona': '0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed',
 'Tommy': '0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2',
}
