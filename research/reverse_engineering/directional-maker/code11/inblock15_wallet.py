"""Iteration 11: BTC 15m R7-price per wallet and per VALIDATE half from the cached blocks of code11/inblock15.py, and the
pooled BTC 5m + 15m per wallet / per half (VALIDATE aggregate).
    python code11/inblock15_wallet.py
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
NAMES = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
         "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
SPLIT_V, HALF_V = 1793059200, 1793232000
F = pd.read_parquet(C / "it11" / "inblock15_sample.parquet")
BL = pd.read_parquet(C / "it11" / "inblock15_blocks.parquet")
pos, blk_of = dict(zip(BL.h, BL.pos)), dict(zip(BL.h, BL.block))
W = pd.read_parquet(C / "t15" / "windows_15m.parquet").set_index("cid")
cl_tx = set(F.txh)
for n in ("bosona", "almach", "momoney"):
    cl_tx |= set(pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["transactionHash"]).transactionHash.str.lower())
rows = []
for day, sd in F.groupby("day"):
    T = pd.read_parquet(C / "t15" / f"taker15m_day_{day}.parquet", columns=["cid", "ts", "side", "asset", "price", "tx"])
    T["tx"] = T.tx.str.lower()
    T = T[T.cid.isin(set(sd.cid)) & ~T.tx.isin(cl_tx)]
    tg = {k: g for k, g in T.groupby("cid")}
    for r in sd.itertuples(index=False):
        if r.cid not in tg or r.cid not in W.index:
            continue
        up = str(W.at[r.cid, "up_token"])
        g = tg[r.cid]
        gts = g.ts.to_numpy()
        o = np.argsort(gts, kind="stable")
        gs, gts = g.iloc[o], gts[o]
        pu = np.where(gs.asset.astype(str).to_numpy() == up, gs.price.to_numpy(float), 1 - gs.price.to_numpy(float))
        isup = str(r.token_id) == up
        b = int(r.ts)
        i = np.searchsorted(gts, b, side="left") - 1
        if i < 0:
            continue
        a_block = pu[i] if isup else 1 - pu[i]
        a_in = a_block
        same = gs[gts == b]
        cpos = pos.get(r.txh)
        if cpos is not None and len(same):
            same = same.assign(p=[pos.get(h) for h in same.tx], bk=[blk_of.get(h) for h in same.tx])
            prev = same[same.p.notna() & (same.bk == blk_of.get(r.txh)) & (same.p < cpos)]
            if len(prev):
                tr = prev[prev.tx == prev.loc[prev.p.idxmax(), "tx"]]
                isu = tr.asset.astype(str).to_numpy() == up
                tu = np.where(isu, tr.price.to_numpy(float), 1 - tr.price.to_numpy(float))
                worst = tu.max() if ((tr.side.to_numpy()[0] == "BUY") == isu[0]) else tu.min()
                a_in = worst if isup else 1 - worst
        rows.append((NAMES.get(r.wallet, r.wallet), b, float(r.price), a_in))
D = pd.DataFrame(rows, columns=["wallet", "b", "price", "a_in"])
D["w"] = np.abs(D.price - np.round(D.a_in - 0.01, 2)) <= 0.0105
S5 = pd.read_parquet(C / "it11" / "inblock_scored_all.parquet")
S5["w"] = np.abs(S5.price - np.round(S5.a_in - 0.01, 2)) <= 0.0105
v15, v5 = D[D.b >= SPLIT_V], S5[S5.split == "validate"]
out = {"btc15m_validate_per_wallet": v15.groupby("wallet").w.mean().round(4).to_dict(),
       "btc15m_validate_halves": [round(float(v15.w[v15.b < HALF_V].mean()), 4), round(float(v15.w[v15.b >= HALF_V].mean()), 4)]}
P = pd.concat([v5[["wallet", "b", "w"]], v15[["wallet", "b", "w"]]])
out["pooled_validate"] = round(float(P.w.mean()), 4)
out["pooled_validate_per_wallet"] = P.groupby("wallet").w.mean().round(4).to_dict()
out["pooled_validate_halves"] = [round(float(P.w[P.b < HALF_V].mean()), 4), round(float(P.w[P.b >= HALF_V].mean()), 4)]
out["pooled_n"] = int(len(P))
print(json.dumps(out, indent=1))
(HERE.parent / "results" / "iter11_inblock_pooled.json").write_text(json.dumps(out, indent=1))
