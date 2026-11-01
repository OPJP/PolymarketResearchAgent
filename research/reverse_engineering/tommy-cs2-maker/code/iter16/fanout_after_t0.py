"""X230 (assumptions panel iter-15 P4): is the 16-22 Oct fan-out still there after T0? Same computation on both periods.
Clusters: wallet-free taker orders (idx -1) of group P / group G members on one event, chained within 300 ms of the
cluster's first signer, >= 2 distinct members. Per member: share of clusters it is in, its median lag behind the first
signer and the IQR; first-signer counts. Reference: 16-22 Oct (calldata_pub + calldata_all, all CS2 / Dota markets of
the wallet's events, before H). After T0: the decoded development-block txs of iterations 15-16 (iter15/op_calldata,
iter16/sfg_calldata: the operator's and the GRID units of 10-31 12-18 and 11-01 06-12; development units only).
Output: results/fanout_after_t0.json"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
CODE = ROOT / "research/reverse_engineering/tommy-cs2-maker/code"
sys.path.insert(0, str(CODE / "iter4"))
sys.path.insert(0, str(CODE))
from queue_replay import load_record  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
A7 = "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14"
_c = json.load(open(CODE / "final_rule_v5_groupP.json"))
GP = set(_c["members"])
GG = set(_c["group_G"]) if isinstance(_c["group_G"], list) else set()
NAMES = {"0x4ebc2722": "P4e", "0x2005d16a": "RN1", "0x72aaaaf9": "trio1", "0x2529c68d": "trio2", "0xfe8a28be": "trio3"}


def table(tk, ev_col="event"):
    tk = tk[tk.mk.isin(GP | GG | {W, A7})].sort_values("sign_ms")
    rows, firsts = [], []
    for ev, g in tk.groupby(ev_col):
        s, m = g.sign_ms.to_numpy(float), g.mk.to_numpy()
        i = 0
        while i < len(g):
            j = i
            while j + 1 < len(g) and s[j + 1] - s[i] <= 300:
                j += 1
            mem = set(m[i:j + 1]) - {W, A7}
            if len(mem) >= 2:
                firsts.append(m[i][:10])
                seen = set()
                for k in range(i, j + 1):
                    if m[k] in seen:
                        continue
                    seen.add(m[k])
                    rows.append((ev, s[i], m[k][:10], s[k] - s[i]))
                i = j + 1
            else:
                i += 1
    R = pd.DataFrame(rows, columns=["event", "t0", "mk", "lag"])
    ncl = int(R.groupby(["event", "t0"]).ngroups) if len(R) else 0
    out = {"clusters": ncl, "events_with_clusters": int(R.event.nunique()) if len(R) else 0,
           "first_signer": pd.Series(firsts).map(lambda x: NAMES.get(x, x)).value_counts().head(8).to_dict()}
    per = {}
    for mk, g in R.groupby("mk"):
        if len(g) < 3:
            continue
        per[NAMES.get(mk, mk)] = {"in_clusters": int(len(g)), "share_of_clusters": round(len(g) / ncl, 3),
                                  "lag_median_ms": round(float(g.lag.median()), 1),
                                  "lag_iqr_ms": round(float(np.subtract(*np.percentile(g.lag, [75, 25]))), 1),
                                  "lag_nonfirst_median_ms": round(float(g.lag[g.lag > 0].median()), 1) if (g.lag > 0).any() else None}
    out["members"] = dict(sorted(per.items(), key=lambda kv: -kv[1]["in_clusters"]))
    return out


def main():
    # 16-22 Oct reference
    cd, _ = load_record()
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "event"]).drop_duplicates("cid")
    ev_of = dict(zip(o.cid, o.event))
    wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"]).query("maker == @W").tx)
    tk = cd[(cd.idx == -1) & (cd.sign_ms > 1.7e12) & ~cd.tx.isin(wtx)].drop_duplicates("tx").copy()
    tk["event"] = tk.cid.map(ev_of)
    tk = tk[tk.event.notna() & (tk.sign_ms / 1000 < 1792713600)]
    tk["mk"] = tk.maker.str.lower()
    ref = table(tk)
    ref["period"] = "16-22 Oct (before H)"
    # after T0: development-block decodes
    a = pd.read_parquet(OUT / "iter15/op_calldata.parquet")
    b = pd.read_parquet(OUT / "iter16/sfg_calldata.parquet")
    t15 = pd.read_parquet(OUT / "iter15/op_trades.parquet", columns=["asset", "event", "transactionHash", "proxyWallet"])
    t16 = pd.read_parquet(OUT / "iter16/sfg_trades.parquet", columns=["asset", "event", "transactionHash", "proxyWallet"])
    tt = pd.concat([t15, t16], ignore_index=True)
    tok_ev = dict(zip(tt.asset.astype(str), tt.event))
    wtx2 = set(tt.loc[tt.proxyWallet.str.lower() == W, "transactionHash"])
    x = pd.concat([a, b], ignore_index=True).drop_duplicates(["tx", "idx"])
    x = x[(x.idx == -1) & (x.sign_ms > 1.7e12) & ~x.tx.isin(wtx2)].drop_duplicates("tx").copy()
    x["event"] = x.token_id.astype(str).map(tok_ev)
    x = x[x.event.notna()]
    x["mk"] = x.maker.str.lower()
    aft = table(x)
    aft["period"] = "development blocks 10-31 12-18 and 11-01 06-12 (decoded units only)"
    aft["events"] = sorted(x.event.unique().tolist())
    aft["takes_by_member_after_t0"] = {NAMES.get(k[:10], k[:10]): int(v) for k, v in x[x.mk.isin(GP)].mk.value_counts().items()}
    ref["takes_by_member_ref_per_event"] = round(float(tk[tk.mk.isin(GP)].groupby("event").size().mean()), 2)
    out = {"reference": ref, "after_t0": aft}
    (RES / "fanout_after_t0.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
