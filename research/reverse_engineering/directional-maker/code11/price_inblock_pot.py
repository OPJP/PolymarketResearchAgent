"""Iteration 11 (information panel I10-1 = X101, price part): how much of the block-clock price error comes from earlier
trades in the same block? STUDY (10-23..26) case by case; VALIDATE aggregate only.
For each cluster maker BUY fill at block second b: block anchor = last clean print (token-mapped) stamped < b;
same-second clean prints of the market (stamped == b) in the data-api row order; oracle = any of them within a tick.
    python code11/price_inblock_pot.py
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
SPLIT_V = 1793059200
W = pd.read_parquet(C / "exam" / "windows_5m.parquet").set_index("cid")
F = pd.read_parquet(C / "exam" / "fills_holdout.parquet")
F = F[(F.role == "maker") & (F.side == "BUY") & F.cid.isin(W.index)].copy()
F["txh"] = F.txh.str.lower()
cl_tx = set(F.txh)
for n in ("bosona", "almach", "momoney"):
    cl_tx |= set(pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["transactionHash"]).transactionHash.str.lower())
res = {}
rows = []
for day in sorted(set((W.start_ts // 86400 * 86400).astype(int))):
    T = pd.read_parquet(C / "exam" / f"taker5m_day_{day}.parquet", columns=["cid", "ts", "asset", "price", "tx"])
    T["rowpos"] = np.arange(len(T))
    T = T[~T.tx.str.lower().isin(cl_tx)]
    fd = F[(F.ts >= day) & (F.ts < day + 86400 + 600)]
    tg = {k: g for k, g in T.groupby("cid")}
    for cid, g in fd.groupby("cid"):
        if cid not in tg:
            continue
        up = str(W.at[cid, "up_token"])
        tp = tg[cid]
        tts = tp.ts.to_numpy()
        o = np.argsort(tts, kind="stable")
        tts = tts[o]
        pup = np.where(tp.asset.astype(str).to_numpy() == up, tp.price.to_numpy(float), 1 - tp.price.to_numpy(float))[o]
        rp = tp.rowpos.to_numpy()[o]
        for r in g.itertuples(index=False):
            b = int(r.ts)
            isup = str(r.token_id) == up
            i = np.searchsorted(tts, b, side="left") - 1
            if i < 0:
                continue
            a0 = pup[i] if isup else 1 - pup[i]
            e0 = abs(r.price - round(a0 - 0.01, 2)) <= 0.0105
            j0, j1 = np.searchsorted(tts, b, side="left"), np.searchsorted(tts, b, side="right")
            same = pup[j0:j1] if isup else 1 - pup[j0:j1]
            srp = rp[j0:j1]
            ok_any = bool(np.any(np.abs(r.price - np.round(same - 0.01, 2)) <= 0.0105)) if len(same) else False
            if len(same):
                kf, kl = np.argmin(srp), np.argmax(srp)
                e_first = abs(r.price - round(same[kf] - 0.01, 2)) <= 0.0105
                e_last = abs(r.price - round(same[kl] - 0.01, 2)) <= 0.0105
            else:
                e_first = e_last = e0
            rows.append((day, b, int(e0), len(same), int(ok_any or e0), int(e_first), int(e_last), r.wallet))
    print(day, len(rows), flush=True)
D = pd.DataFrame(rows, columns=["day", "b", "e0", "n_same", "oracle", "e_first", "e_last", "wallet"])
for sp, m in (("study", D.day < SPLIT_V), ("validate", D.day >= SPLIT_V)):
    d = D[m]
    hs = d.n_same > 0
    res[sp] = {"fills": int(len(d)), "block_anchor_within_tick": round(float(d.e0.mean()), 4),
               "share_with_same_second_clean_print": round(float(hs.mean()), 4),
               "block_anchor_within_tick_when_same_second": round(float(d.e0[hs].mean()), 4),
               "oracle_block_or_any_same_second": round(float(d.oracle.mean()), 4),
               "same_second_first_row_order": round(float(d.e_first.mean()), 4),
               "same_second_last_row_order": round(float(d.e_last.mean()), 4)}
print(json.dumps(res, indent=1))
(HERE.parent / "results" / "iter11_price_inblock_potential.json").write_text(json.dumps(res, indent=1))
