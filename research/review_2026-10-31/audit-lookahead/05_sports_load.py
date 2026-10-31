"""Rebuild run_sports_study's internals (same functions, same order) and pickle them."""
import pickle, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd
from polyrea.adapters.polymarket import PolymarketData
from polyrea.workflows.sports_study import load_games, game_prints, scoring_events

wallet = sys.argv[1]; max_games = int(sys.argv[2]); role = sys.argv[3] if len(sys.argv) > 3 else "taker"
pm = PolymarketData(); t0 = time.time()
loaded = load_games(wallet, 30, None, max_games, 11, pm)
games, markets = loaded["games"], loaded["markets"]
print("games matched", len(games), "in", round(time.time() - t0, 1), "s", flush=True)
with ThreadPoolExecutor(6) as ex:
    frames = list(ex.map(lambda e: game_prints(e, markets, wallet, pm, role), games))
events = {e["event_slug"]: scoring_events(e["game"]) for e in games}
split = int(np.median([e["start"] for e in games]))
fit_slugs = [e["event_slug"] for e in games if e["start"] < split]
test_slugs = [e["event_slug"] for e in games if e["start"] >= split]
allp = pd.concat(frames, ignore_index=True)
allp = allp[allp["side_kind"].notna()]
print("fit", len(fit_slugs), "test", len(test_slugs), "prints", len(allp), "wallet prints", int(allp["is_wallet"].sum()), "t", round(time.time() - t0, 1), flush=True)
pickle.dump({"allp": allp, "events": events, "fit": fit_slugs, "test": test_slugs, "starts": {e["event_slug"]: e["start"] for e in games}, "split": split},
            open(Path(__file__).parent / "data" / f"sports_{wallet[:10]}_{role}_{max_games}.pkl", "wb"))
