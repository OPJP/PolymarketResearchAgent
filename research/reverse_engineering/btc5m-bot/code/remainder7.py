"""Iteration 7 (catalog X35 = panel-mechanics iter6 P1): the REMAINDER lifecycle of the bot's taker orders (cancel / TTL /
fill-and-kill). Data: the B1 calldata sample (11 whole development hours; every cluster order with its signed size and
limit and its fill amounts in the sampled txs), and for the VALIDATE hours the full taker tapes (other traders' prints).
Per cluster order (maker, salt): filled share = sum of fill amounts / size (fill_amt is in the order's makerAmount units,
i.e. USDC for a BUY: shares = fill_amt / limit... converted with the order's own price); a taker-first order "leaves a
remainder" when its taker fill is < 99% of the size. For remainders:
- lower bound of the removal time = its last fill (a later maker fill shows the remainder was still resting);
- upper bound = the first OTHER-trader taker BUY print on the same outcome at <= limit - 0.01 after its last fill (an ask
  below a resting bid of the bot is impossible, so the remainder was gone by then).
Usage: python remainder7.py TAPE_DIR"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
OUT = _ROOT + "/research/reverse_engineering/btc5m-bot/results/remainder7.json"
CL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}


def q(x, ps=(10, 25, 50, 75, 90)):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    return {f"p{p}": round(float(np.percentile(x, p)), 2) for p in ps} if len(x) else None


def main(tape_dir):
    cd = pd.read_parquet(f"{C}/calldata_sample.parquet")
    txs = pd.read_parquet(f"{C}/calldata_sample_txs.parquet").set_index("tx").ts
    cd["ts"] = cd.tx.map(txs)
    cd["maker"] = cd.maker.str.lower()
    c = cd[cd.maker.isin(CL) & (cd.oside == 0)].copy()
    c["oid"] = c.maker + ":" + c.salt
    c["size"] = c.taker_amt.astype(float); c["limit"] = c.maker_amt / c.taker_amt
    c["sh"] = c.fill_amt / c["limit"]  # BUY: fill_amt in USDC (makerAmount units)
    c = c.sort_values(["ts", "tx_index", "idx"])
    g = c.groupby("oid", sort=False)
    o = g.agg(wal=("maker", lambda s: CL[s.iloc[0]]), size=("size", "first"), limit=("limit", "first"), token=("token", "first"), cid=("cid", "first"),
              role0=("role", "first"), ts0=("ts", "first"), ts_last=("ts", "last"), n=("tx", "size"), sh=("sh", "sum")).reset_index()
    first_sh = g.sh.first().to_numpy()
    o["first_share"] = first_sh / o["size"]
    o["filled_share"] = o.sh / o["size"]
    tk = o[o.role0 == "T"].copy()
    res = {"orders": int(len(o)), "taker_first": int(len(tk)), "sanity_filled_share_max": round(float(o.filled_share.max()), 3)}
    rem = tk[tk.first_share < 0.99]
    res["taker_first_with_remainder_share"] = round(float(len(rem) / len(tk)), 4)
    res["remainder_ever_fills_again_share"] = round(float((rem.n > 1).mean()), 4)
    res["remainder_size_share_median"] = round(float((1 - rem.first_share).median()), 3)
    res["fill_span_s_when_refilled"] = q((rem.ts_last - rem.ts0)[rem.n > 1])
    res["by_size"] = {str(int(s)): {"n": int(len(x)), "with_remainder": round(float((x.first_share < 0.99).mean()), 4),
                                    "refill_given_rem": round(float((x[x.first_share < 0.99].n > 1).mean()), 4) if (x.first_share < 0.99).any() else None}
                      for s, x in tk.groupby("size") if len(x) >= 50}
    res["by_wallet"] = {w: {"with_remainder": round(float((x.first_share < 0.99).mean()), 4), "refill_given_rem": round(float((x[x.first_share < 0.99].n > 1).mean()), 4)}
                        for w, x in tk.groupby("wal")}
    # maker-only orders: how long after signing their first fill comes
    mk = o[o.role0 == "M"]
    res["maker_first_orders"] = int(len(mk))
    # upper bound of the removal time from the tapes (VALIDATE hours only)
    win = pd.read_parquet(f"{C}/windows.parquet")[["cid", "start_ts", "up_token", "down_token"]]
    tokup = dict(zip(win.up_token, [True] * len(win))); tokup.update(dict(zip(win.down_token, [False] * len(win))))
    ub = []; cens = 0; nrem = 0
    for cid, gg in rem.groupby("cid"):
        p = f"{tape_dir}/{cid}.parquet"
        if not os.path.exists(p):
            continue
        d = pd.read_parquet(p)
        d = d[(d.side == "BUY") & ~d.proxyWallet.str.lower().isin(CL)]
        for r in gg.itertuples():
            nrem += 1
            is_up = tokup.get(r.token)
            if is_up is None:
                continue
            dd = d[(d.outcome == ("Up" if is_up else "Down")) & (d.timestamp > r.ts_last) & (d.price <= r.limit - 0.0099)]
            if len(dd):
                ub.append(float(dd.timestamp.min() - r.ts_last))
            else:
                cens += 1
    res["upper_bound_removal_s_after_last_fill"] = {"n_remainders_with_tape": nrem, "n_bounded": len(ub), "censored_no_cheaper_print": cens,
                                                    "quantiles": q(ub), "share_le_3s": round(float(np.mean(np.array(ub) <= 3)), 4) if ub else None,
                                                    "share_le_10s": round(float(np.mean(np.array(ub) <= 10)), 4) if ub else None}
    json.dump(res, open(OUT, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
