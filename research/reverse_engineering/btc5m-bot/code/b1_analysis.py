"""Iteration 5 (B1): what the calldata says about the cluster's orders. Input: calldata_sample.parquet (calldata.py) for 11
sampled whole hours (7 VALIDATE days, 4 BUILD days), fills.parquet (block ts per tx), gamma_meta (window start per token).
Outputs results_b1_iter5.json."""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
VAL0 = 1792108800


def q(x, qs=(0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99)):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    return {str(k): round(float(np.quantile(x, k)), 3) for k in qs} if len(x) else {}


def load(path=C + "/calldata_sample.parquet"):
    d = pd.read_parquet(path)
    d = d[d.role.isin(["T", "M"])].copy()
    f = pd.read_parquet(C + "/fills.parquet", columns=["tx", "ts"]).drop_duplicates("tx")
    d = d.merge(f, on="tx", how="left")
    g = pd.read_parquet(C + "/gamma_meta.parquet", columns=["tokens", "start"])
    rows = []
    for t, s in zip(g.tokens, g.start):
        tk = json.loads(t); st = int(pd.Timestamp(s).timestamp())
        rows += [(tk[0], st, True), (tk[1], st, False)]
    tm = pd.DataFrame(rows, columns=["token", "start_ts", "is_up"])
    d = d.merge(tm, on="token", how="left")
    d["wal"] = d.maker.map(W)
    d["sign_s"] = d.sign_ms / 1000.0
    d["gap"] = d.ts - d.sign_s
    d["rel_sign"] = d.sign_s - d.start_ts
    d["rel_fill"] = d.ts - d.start_ts
    d["limit"] = np.where(d.oside == 0, d.maker_amt / d.taker_amt, d.taker_amt / d.maker_amt)
    d["size"] = np.where(d.oside == 0, d.taker_amt, d.maker_amt)
    d["val"] = d.ts >= VAL0
    return d


def main():
    d = load()
    cl = d[d.wal.notna()].copy()
    oth = d[d.wal.isna()]
    res = {"n_rows": int(len(d)), "n_txs": int(d.tx.nunique()), "n_cluster_rows": int(len(cl))}
    # order identity (maker, salt)
    cl["oid"] = cl.maker + ":" + cl.salt.astype(str)
    res["cluster_role_counts"] = cl.role.value_counts().to_dict()
    res["cluster_sides"] = cl.oside.value_counts().to_dict()
    res["cluster_sig_type"] = cl.sig_type.value_counts().to_dict()
    res["cluster_sig_len"] = cl.sig_len.value_counts().head(5).to_dict()
    res["cluster_metadata_nonzero"] = float((cl.metadata != "0" * 64).mean())
    res["cluster_builder_nonzero"] = float((cl.builder != "0" * 64).mean())
    res["others_builder_nonzero"] = float((oth.builder != "0" * 64).mean())
    res["cluster_builder_top"] = cl.builder.value_counts().head(3).to_dict()
    # gap between signing and block, by role
    for role in ("T", "M"):
        for w in ("GF", "XM", "DS"):
            x = cl[(cl.role == role) & (cl.wal == w)]
            res[f"gap_{role}_{w}"] = q(x.gap)
        res[f"gap_{role}_others"] = q(oth[oth.role == role].gap)
        res[f"gap_{role}_cluster_neg_share"] = float((cl[cl.role == role].gap < -0.5).mean())
    # signing time relative to the window
    res["rel_sign_T"] = q(cl[cl.role == "T"].rel_sign)
    res["rel_sign_M"] = q(cl[cl.role == "M"].rel_sign)
    res["share_signed_before_open_T"] = float((cl[cl.role == "T"].rel_sign < 0).mean())
    res["share_signed_before_open_M"] = float((cl[cl.role == "M"].rel_sign < 0).mean())
    # per order: one row per (maker, salt)
    o = cl.sort_values("ts").groupby("oid").agg(wal=("wal", "first"), sign_s=("sign_s", "first"), first_ts=("ts", "min"), last_ts=("ts", "max"),
                                                 roles=("role", lambda r: "".join(sorted(set(r)))), nfill=("tx", "size"), size=("size", "first"),
                                                 limit=("limit", "first"), start_ts=("start_ts", "first"), is_up=("is_up", "first"), token=("token", "first"),
                                                 salt=("salt", "first"), val=("val", "first"))
    o["gap_first"] = o.first_ts - o.sign_s
    o["rel_sign"] = o.sign_s - o.start_ts
    res["n_orders"] = int(len(o))
    res["orders_by_roles"] = o.roles.value_counts().to_dict()
    res["order_sizes_top"] = {str(k): int(v) for k, v in o["size"].round(2).value_counts().head(10).items()}
    for r in ("T", "M", "MT"):
        res[f"order_gap_first_{r}"] = q(o[o.roles == r].gap_first)
    # batches: orders sharing a sign ms (same wallet / any wallet)
    o["sign_ms"] = (o.sign_s * 1000).round().astype("int64")
    same = o.groupby(["wal", "sign_ms"]).size()
    res["orders_per_sign_ms_same_wallet"] = {str(k): int(v) for k, v in same.value_counts().sort_index().head(10).items()}
    anyw = o.groupby("sign_ms").wal.nunique()
    res["sign_ms_shared_across_wallets_share"] = float((anyw > 1).mean())
    # sign ms phase (ms within second) and second within minute
    res["sign_ms_phase_hist10"] = np.histogram(o.sign_ms % 1000, bins=10, range=(0, 1000))[0].tolist()
    # salt check: salt / sign_ms (TS clob-client: round(Math.random() * Date.now()))
    sr = o.salt.astype(float) / o.sign_ms.astype(float)
    res["salt_over_signms"] = q(sr, (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0))
    res["salt_over_signms_gt1_share"] = float((sr > 1.0).mean())
    # limit vs fill price for taker orders: does it pay its limit (= the ask at signing) or better?
    tk = cl[cl.role == "T"].copy()
    tk["fill_px"] = tk.fill_amt / np.where(tk.oside == 0, 1.0, 1.0)  # USDC paid by the taker (BUY: fill_amt in USDC)
    # price improvement: compare the limit with the makers' prices in the same tx (complementary BUY at 1-p or SELL at p)
    mk = d[d.role == "M"].copy()
    mk["px_equiv"] = np.where(mk.oside == 0, 1.0 - mk.limit, mk.limit)  # price of the taker's token implied by each maker
    mk_same = mk[["tx", "token", "oside", "limit"]]
    best = d[d.role == "M"].groupby("tx").apply(lambda g: np.nan).rename("x")
    return res, cl, o


if __name__ == "__main__":
    res, cl, o = main()
    o.to_parquet(C + "/b1_orders_sample.parquet")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_b1_iter5.json")
    json.dump(res, open(out, "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:7000])
