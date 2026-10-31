"""Check final_rule's tape-based maker/taker role against on-chain OrderFilled roles (VALIDATE)."""
import sys
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import final_rule as fr  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

lo, hi = int(sys.argv[1]), int(sys.argv[2])
pm = PolymarketData()
w = fr._windows(lo, hi)
tk = fr._tapes(w, pm, hi)
f = fr._cluster_maker_fills(lo, hi, w, tk, pm)
ch = pd.read_parquet(HERE.parents[3] / ".cache/re/directional-maker/fills_enriched.parquet")
ch = ch[(ch.ts >= lo) & (ch.ts < hi)]
ch["wallet_addr"] = ch["maker"]
g = ch.groupby(["tx", "token_id", "wallet_addr"])["role"].agg(lambda s: "maker" if (s == "maker").all() else ("taker" if (s == "taker").all() else "mixed")).reset_index()
m = f.merge(g, left_on=["tx", "token_id", "wallet"], right_on=["tx", "token_id", "wallet_addr"], how="left", suffixes=("_tape", "_chain"))
print("activity BTC5m BUY fills", len(f), "matched to chain", m["role_chain"].notna().mean().round(4))
print(pd.crosstab(m["role_tape"], m["role_chain"].fillna("none")))
