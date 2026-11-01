"""Iteration 11: score R7-price (in-block execution-order anchor) against R3's block clock on the pre-registered
sample (code11/inblock_fetch.py). STUDY numbers may be read per fill; VALIDATE only as aggregates.
    python code11/inblock_score.py [all]   (all = every lot BTC 5m maker BUY fill, code11/inblock_fetch_all.py)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
SPLIT_V = 1793059200
NAMES = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
         "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}


def main(mode="sample"):
    S = pd.read_parquet(C / "it11" / ("inblock_all_sample.parquet" if mode == "all" else "inblock_sample.parquet"))
    BL = pd.read_parquet(C / "it11" / ("inblock_blocks_all.parquet" if mode == "all" else "inblock_blocks.parquet"))
    pos = dict(zip(BL.h, BL.pos))
    blk_of = dict(zip(BL.h, BL.block))
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet").set_index("cid")
    F = pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["txh"])
    cl_tx = set(F.txh.str.lower())
    for n in ("bosona", "almach", "momoney"):
        cl_tx |= set(pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["transactionHash"]).transactionHash.str.lower())
    rows = []
    S["day"] = (S.ts // 86400 * 86400).astype(int)
    for day, sd in S.groupby("day"):
        p = C / "exam" / f"taker5m_day_{day}.parquet"
        T = pd.read_parquet(p, columns=["cid", "ts", "side", "asset", "price", "tx"])
        T["tx"] = T.tx.str.lower()
        T = T[T.cid.isin(set(sd.cid)) & ~T.tx.isin(cl_tx)]
        tg = {k: g for k, g in T.groupby("cid")}
        for r in sd.itertuples(index=False):
            if r.cid not in tg:
                continue
            up = str(W.at[r.cid, "up_token"])
            g = tg[r.cid]
            isup = str(r.token_id) == up
            gts = g.ts.to_numpy()
            o = np.argsort(gts, kind="stable")
            gts = gts[o]
            pu = np.where(g.asset.astype(str).to_numpy() == up, g.price.to_numpy(float), 1 - g.price.to_numpy(float))[o]
            b = int(r.ts)
            i = np.searchsorted(gts, b, side="left") - 1
            a_block = (pu[i] if isup else 1 - pu[i]) if i >= 0 else np.nan
            # same-second clean transactions ordered by in-block position
            same = g.iloc[o][(gts == b)]
            cpos = pos.get(r.txh, None)
            a_in, src = a_block, "block"
            a_first = a_block
            if cpos is not None and len(same):
                same = same.assign(p=[pos.get(h, None) for h in same.tx], blk=[blk_of.get(h, None) for h in same.tx])
                prev = same[same.p.notna() & (same.blk == blk_of.get(r.txh)) & (same.p < cpos)]
                if len(prev):
                    last_tx = prev.loc[prev.p.idxmax(), "tx"]
                    tr = prev[prev.tx == last_tx]
                    tu = np.where(tr.asset.astype(str).to_numpy() == up, tr.price.to_numpy(float), 1 - tr.price.to_numpy(float))
                    sides = tr.side.to_numpy()
                    isu = tr.asset.astype(str).to_numpy() == up
                    # taker's worst price, mapped to Up: taker buys Up -> max Up; sells Up -> min Up; buys Down -> min Up; sells Down -> max Up
                    up_dir = np.where((sides == "BUY") == isu, 1, -1)
                    worst = tu.max() if up_dir[0] > 0 else tu.min()
                    a_in = worst if isup else 1 - worst
                    a_first = tu[0] if isup else 1 - tu[0]
                    src = "inblock"
            rows.append(dict(split=r.split, wallet=NAMES.get(r.wallet, r.wallet), txh=r.txh, token=str(r.token_id), b=b, price=float(r.price), a_block=a_block,
                             a_in=a_in, a_first=a_first, src=src, has_pos=cpos is not None, n_same=int(len(same))))
    D = pd.DataFrame(rows).dropna(subset=["a_block"])
    D.to_parquet(C / "it11" / ("inblock_scored_all.parquet" if mode == "all" else "inblock_scored.parquet"))

    def within(a, off=0.01):
        return (np.abs(D.price.to_numpy() - np.round(a - off, 2)) <= 0.0105)
    D["w_block"] = within(D.a_block.to_numpy())
    D["w_in"] = within(D.a_in.to_numpy())
    D["w_first"] = within(D.a_first.to_numpy())
    D["w_in_last"] = within(D.a_in.to_numpy(), 0.0)
    D["exact_in"] = np.abs(D.price - np.round(D.a_in - 0.01, 2)) < 0.0005
    out = {}
    rng = np.random.default_rng(7)
    for sp, d in D.groupby("split"):
        blocks = (d.b // 7200).to_numpy()
        ub = np.unique(blocks)
        gains = []
        idx = {u: np.nonzero(blocks == u)[0] for u in ub}
        gin, gbl = d.w_in.to_numpy(), d.w_block.to_numpy()
        for _ in range(2000):
            pick = np.concatenate([idx[u] for u in rng.choice(ub, len(ub), replace=True)])
            gains.append(gin[pick].mean() - gbl[pick].mean())
        gains = np.array(gains)
        out[sp] = {"fills": int(len(d)), "inblock_anchor_share": round(float((d.src == "inblock").mean()), 4),
                   "cluster_tx_position_found": round(float(d.has_pos.mean()), 4),
                   "block_clock_within_tick": round(float(d.w_block.mean()), 4),
                   "inblock_within_tick": round(float(d.w_in.mean()), 4),
                   "inblock_first_row_within_tick": round(float(d.w_first.mean()), 4),
                   "inblock_last_print_no_offset_within_tick": round(float(d.w_in_last.mean()), 4),
                   "inblock_exact": round(float(d.exact_in.mean()), 4),
                   "gain": round(float(d.w_in.mean() - d.w_block.mean()), 4),
                   "gain_ci95_2h_blocks": [round(float(np.quantile(gains, 0.025)), 4), round(float(np.quantile(gains, 0.975)), 4)],
                   "n_2h_blocks": int(len(ub)),
                   "per_wallet_inblock": {w: round(float(g.w_in.mean()), 4) for w, g in d.groupby("wallet")},
                   "per_wallet_block": {w: round(float(g.w_block.mean()), 4) for w, g in d.groupby("wallet")}}
        if sp == "validate":
            h1 = d.b < 1793232000
            out[sp]["halves_inblock"] = [round(float(d.w_in[h1].mean()), 4), round(float(d.w_in[~h1].mean()), 4)]
    out["criterion"] = "adopt if VALIDATE inblock >= block + 0.03 and gain CI lower bound > 0 (pre-registered 00:43 UTC)"
    out["adopted"] = bool(out.get("validate", {}).get("gain", 0) >= 0.03 and out.get("validate", {}).get("gain_ci95_2h_blocks", [0])[0] > 0)
    (HERE.parent / "results" / ("iter11_inblock_price_all.json" if mode == "all" else "iter11_inblock_price.json")).write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "sample")
