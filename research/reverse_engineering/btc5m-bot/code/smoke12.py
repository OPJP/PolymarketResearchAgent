"""Iteration 12 smoke test of the frozen exposure tracker inside final_rule.py on the whole VALIDATE week, built from
the cached development cells (same pipeline as evaluate) with the it4b netflow taken from val_outcome_it4b.parquet
(frozen iteration-4 predictions) and nf12b recomputed through final_rule._nf12b_flow. Compares with track12_avg.json.
Usage: python smoke12.py TAPE_DIR"""
import os, sys, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import final_rule as fr
import nf12 as nf12mod
import spot as spotmod
C = _ROOT + "/.cache/re/btc5m-bot"
VAL0, H = 1792108800, 1792713600
W0, W1 = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (VAL0, H)  # optional window-start filter
t0 = time.time()
fr.tf.TAPE_DIR = sys.argv[1]
sp = spotmod.Spot(path=f"{C}/binance_1s.parquet")
need = ["cid", "start_ts", "is_up"] + nf12mod.SPOT + nf12mod.TAPE
parts = []
for fn in sorted(os.listdir(f"{C}/cells")):
    d0 = int(fn[:-8])
    if VAL0 <= d0 < H:
        parts.append(pd.read_parquet(f"{C}/cells/{fn}", columns=need))
cells = pd.concat(parts, ignore_index=True); del parts
cells = cells[(cells.start_ts >= W0) & (cells.start_ts + 300 <= W1)].reset_index(drop=True)
up, dn = fr._pairs(cells)
win = pd.read_parquet(f"{C}/windows.parquet")
win = win[(win.start_ts >= W0) & (win.end_ts <= W1) & win.up_payout.notna()].sort_values("start_ts").reset_index(drop=True)
fills = pd.read_parquet(f"{C}/fills.parquet")
fills = fills[(fills.start_ts >= W0) & (fills.start_ts + 300 <= W1)]
vo = pd.read_parquet(f"{C}/val_outcome_it4b.parquet", columns=["cid", "rel", "nf"])
nf4 = vo.set_index(["cid", "rel"]).nf.reindex(pd.MultiIndex.from_arrays([up.cid.to_numpy(), up.rel.to_numpy().astype(np.int64)])).fillna(0).to_numpy()
f12 = fr._nf12b_flow(cells, sp, up)
ref = pd.read_parquet(f"{C}/it12/nf12b_val.parquet").set_index(["cid", "rel"]).nf12b.reindex(pd.MultiIndex.from_arrays([up.cid.to_numpy(), up.rel.to_numpy().astype(np.int64)])).to_numpy()
print("nf12b max abs diff vs training-script predictions", float(np.nanmax(np.abs(f12 - ref))), "corr", float(np.corrcoef(f12, np.nan_to_num(ref))[0, 1]), round(time.time() - t0), flush=True)
flow = fr.TRK_W_IT4B * nf4 + fr.TRK_W_NF12B * f12
r = fr._strict_tracker(up, dn, flow, win, fills, "a")
print(json.dumps({k: v for k, v in r.items() if k != "note"}), round(time.time() - t0), flush=True)
json.dump(r, open(_ROOT + f"/research/reverse_engineering/btc5m-bot/results/smoke12{'' if (W0, W1) == (VAL0, H) else '_slice'}.json", "w"), indent=1)
