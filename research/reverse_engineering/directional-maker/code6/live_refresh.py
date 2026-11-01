"""Iteration 6: refresh the cluster's live activity (development block only) and the calldata of its live txs.
    python code6/live_refresh.py <start_ts> [<end_ts>]
Writes live_activity_<a>_<b>.parquet (code4/live_activity.py) and calldata/live1031_*.parquet (code4/fetch_calldata)."""
import subprocess, sys, time, glob
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PY = sys.executable
a = int(sys.argv[1]); b = int(sys.argv[2]) if len(sys.argv) > 2 else int(time.time())
subprocess.run([PY, str(HERE.parent / "code4" / "live_activity.py"), str(a), str(b)], check=True, cwd=ROOT)
C = ROOT / ".cache/re/directional-maker"
act = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))])
act = act[(act.type == "TRADE") & (act.timestamp >= a) & (act.timestamp < b)]
tmp = C / f"live_txs_it6_{a}_{b}.parquet"
pd.DataFrame({"txh": act.transactionHash.str.lower(), "ts": act.timestamp}).drop_duplicates().to_parquet(tmp)
sys.path.insert(0, str(HERE.parent / "code4"))
import fetch_calldata as F
F.main(str(tmp), "live1031", a, b)
print("done", len(act))
