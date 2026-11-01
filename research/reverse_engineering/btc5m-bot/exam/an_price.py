"""Examiner r1: PRICE component on the h1 lot from the decoded calldata samples that evaluate() drew (1,500 cluster txs per chunk, seed
11 inside the frozen code). Rule (frozen): limit = the touch (best effective ask consumed by the same match) -- the trivial touch anchor,
measured on the match itself, not a point-in-time forecast. Reported against the other trivial anchors: touch + 1 tick, touch - 1 tick,
and the last implied ask from others' prints at s - 1 (cells ask_o). Pooled, per half, per wallet, per original order size; plus the share
of the wallets' fills (and USDC) that are maker fills, which no price rule of the frozen code covers. Usage: python an_price.py OUT_JSON"""
import os, sys, json, glob
ARGS = sys.argv[1:]
ROOT = os.getcwd()
import numpy as np, pandas as pd

EX = f"{ROOT}/.cache/exam/btc5m-bot"
LOT = [(1792713600, 1792800000), (1792886400, 1792972800), (1793059200, 1793145600), (1793232000, 1793318400)]
CUT = 1793059200
WAL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}


def main(out_json):
    TK, FL = [], []
    for p in sorted(glob.glob(f"{EX}/chunks/*_*/evaluate.json")):
        d = os.path.dirname(p); a, b = map(int, os.path.basename(d).split("_"))
        if not any(x <= a < y for x, y in LOT) or not os.path.exists(f"{d}/calldata.parquet"):
            continue
        cd = pd.read_parquet(f"{d}/calldata.parquet")
        fills = pd.read_parquet(f"{d}/fills.parquet")
        FL.append(fills[["wallet", "role", "usdc", "shares", "ts", "tx", "cid", "is_up", "rel", "price"]])
        cd["px"] = np.where(cd.oside == 0, cd.maker_amt / cd.taker_amt, cd.taker_amt / cd.maker_amt)
        tk = cd[(cd.role == "T") & cd.maker.str.lower().isin(WAL)].copy()
        mk = cd[cd.role == "M"][["tx", "token", "oside", "px"]].merge(tk[["tx", "token"]].rename(columns={"token": "t_token"}), on="tx")
        same = mk.token == mk.t_token
        mk["eff"] = np.where(same & (mk.oside == 1), mk.px, np.where(~same & (mk.oside == 0), 1.0 - mk.px, np.nan))
        g = mk.groupby("tx").agg(best=("eff", "min"))
        tk = tk.join(g, on="tx")
        tk["wallet"] = tk.maker.str.lower().map(WAL)
        tk["size0"] = np.where(tk.oside == 0, tk.taker_amt, tk.maker_amt)
        ts = fills.drop_duplicates("tx").set_index("tx")[["ts", "cid", "is_up", "rel"]]
        tk = tk.join(ts, on="tx", rsuffix="_f")
        c = pd.read_parquet(f"{d}/cells.parquet", columns=["cid", "is_up", "rel", "ask_o"]).set_index(["cid", "is_up", "rel"])
        tk = tk.join(c, on=["cid_f", "is_up", "rel"]) if "cid_f" in tk else tk.join(c, on=["cid", "is_up", "rel"])
        TK.append(tk[["tx", "wallet", "px", "best", "size0", "ts", "ask_o", "oside"]])
    T = pd.concat(TK, ignore_index=True); F = pd.concat(FL, ignore_index=True)
    T = T[T.best.notna() & (T.oside == 0)]
    half = T.ts.to_numpy() < CUT
    def w1(x, ref):
        ok = np.isfinite(ref)
        return round(float((np.abs(x[ok] - ref[ok]) <= 0.0100001).mean()), 4) if ok.any() else None
    def block(m):
        x = T.px.to_numpy()[m]; t = T.best.to_numpy()[m]; a = T.ask_o.to_numpy()[m]
        return {"n": int(m.sum()), "rule_touch_within_1tick": w1(x, t), "rule_touch_exact": round(float((np.abs(x - t) < 1e-6).mean()), 4) if m.any() else None,
                "anchor_touch_plus_1tick": w1(x, t + 0.01), "anchor_touch_minus_1tick": w1(x, t - 0.01), "anchor_last_implied_ask_s_minus_1": w1(x, a),
                "share_limit_above_touch_by_2c_or_more": round(float(((x - t) > 0.0150001).mean()), 4) if m.any() else None}
    res = {"pooled": block(np.ones(len(T), bool)), "first_half": block(half), "second_half": block(~half),
           "by_wallet": {w: {"all": block(T.wallet.to_numpy() == w), "first_half": block((T.wallet.to_numpy() == w) & half), "second_half": block((T.wallet.to_numpy() == w) & ~half)} for w in ("GF", "XM", "DS")},
           "by_size": {str(int(s)): block(np.round(T.size0.to_numpy()) == s) for s in (30, 60, 100) if (np.round(T.size0.to_numpy()) == s).any()}}
    res["maker_share_of_fills"] = {w: {"fills": round(float((g.role == "M").mean()), 4), "usdc": round(float(g[g.role == "M"].usdc.sum() / g.usdc.sum()), 4)} for w, g in F.groupby("wallet")}
    res["maker_share_of_fills"]["pool"] = {"fills": round(float((F.role == "M").mean()), 4), "usdc": round(float(F[F.role == "M"].usdc.sum() / F.usdc.sum()), 4)}
    json.dump(res, open(out_json, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(ARGS[0])
