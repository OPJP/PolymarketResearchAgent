"""Iteration 9, X126 (mechanics panel iter8 P4): one broadcast or a sequential sender? Messages = P4e take clusters
(same-token taker BUYs, 500-ms gap; t0 = first P4e signing), 16-22 Oct CS2 (calldata_all + calldata_pub) plus the 10-22
Dota markets (dota_pub). Subscribers = the wallet, group P and group G (BUILD lists, selection_groupP.json). A subscriber
acts on a message if it signs a same-token taker BUY in [t0 - 300, t0 + 1500] ms (the one closest to its median lag).
On messages with >= 3 acting subscribers:
 1. pairwise order consistency (share of shared messages in the pair's majority order) vs a null that draws each
    subscriber's lag independently from its own marginal (200 draws);
 2. common mode: correlation of two subscribers' lag residuals (lag - own median) on the same message vs on shuffled
    messages;
 3. queue load: OLS of each subscriber's lag on the number of P4e clusters in ALL markets in the previous 1 s and on the
    number of other subscribers acting on the message.
Output: results/fanout_structure.json
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
P4E = "0x4ebc2722adc772bde8680792d0a6fdf15499a33d"


def main():
    sg = json.load(open(RES / "selection_groupP.json"))
    GP = set(sg["members"]) - {P4E}
    G = {w for w, v in sg["candidates"].items() if not v["member"] and (v["build_grid_share"] or 0) >= 0.2}
    SUBS = GP | G | {W}
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    parts = [pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)]
    parts += [pd.read_parquet(p, columns=cols) for p in glob.glob(str(OUT / "calldata_pub" / "*.parquet"))]
    parts += [pd.read_parquet(p, columns=cols) for p in glob.glob(str(OUT / "dota_pub" / "*.parquet"))]
    T = pd.concat(parts).drop_duplicates(["tx", "idx"])
    T["maker"] = T.maker.str.lower()
    T["token_id"] = T.token_id.astype(str)
    T = T[(T.idx == -1) & (T.side == 0) & (T.sign_ms > 1.79e12) & (T.sign_ms < 1.7928e12)]
    P = T[T.maker == P4E].sort_values(["token_id", "sign_ms"])
    P["new"] = (P.token_id != P.token_id.shift()) | (P.sign_ms.diff() > 500)
    msgs = P[P.new][["token_id", "sign_ms"]].reset_index(drop=True)
    allp = np.sort(msgs.sign_ms.to_numpy(float))
    S = T[T.maker.isin(SUBS)]
    by = {k: v for k, v in S.groupby("token_id")}
    # first pass: raw lags to get medians
    raw = []
    for i, r in msgs.iterrows():
        v = by.get(r.token_id)
        if v is None:
            continue
        d = v.sign_ms.to_numpy(float) - r.sign_ms
        m = (d >= -300) & (d <= 1500)
        for w_, dd in zip(v.maker.to_numpy()[m], d[m]):
            raw.append((i, w_, dd))
    R = pd.DataFrame(raw, columns=["msg", "who", "lag"])
    med = R.groupby("who").lag.median()
    R["dist"] = (R.lag - R.who.map(med)).abs()
    R = R.sort_values("dist").drop_duplicates(["msg", "who"])
    cnt = R.groupby("who").size()
    keep = cnt[cnt >= 30].index
    R = R[R.who.isin(keep)]
    nact = R.groupby("msg").size()
    M = R[R.msg.isin(nact[nact >= 3].index)].copy()
    res = {"messages": int(len(msgs)), "messages_ge3": int(M.msg.nunique()), "subscribers": {w[:10]: int(n) for w, n in M.groupby("who").size().items()},
           "median_lag_ms": {w[:10]: round(float(v), 1) for w, v in M.groupby("who").lag.median().items()}}
    # 1. order consistency
    piv = M.pivot_table(index="msg", columns="who", values="lag")
    rng = np.random.default_rng(2)
    marg = {w: M.loc[M.who == w, "lag"].to_numpy() for w in piv.columns}
    pairs = []
    cols_ = list(piv.columns)
    for i in range(len(cols_)):
        for j in range(i + 1, len(cols_)):
            a, b = piv[cols_[i]], piv[cols_[j]]
            ok = a.notna() & b.notna()
            n = int(ok.sum())
            if n < 15:
                continue
            obs = float(max((a[ok] < b[ok]).mean(), (a[ok] > b[ok]).mean()))
            nul = []
            for _ in range(200):
                x = rng.choice(marg[cols_[i]], n)
                y = rng.choice(marg[cols_[j]], n)
                nul.append(max((x < y).mean(), (x > y).mean()))
            ra, rb = a[ok] - np.median(marg[cols_[i]]), b[ok] - np.median(marg[cols_[j]])
            cm = float(np.corrcoef(ra, rb)[0, 1]) if ra.std() > 0 and rb.std() > 0 else np.nan
            cm_sh = float(np.mean([np.corrcoef(ra, rng.permutation(rb.to_numpy()))[0, 1] for _ in range(50)]))
            pairs.append({"a": cols_[i][:10], "b": cols_[j][:10], "n": n, "consistency": round(obs, 3), "null_mean": round(float(np.mean(nul)), 3),
                          "null_p95": round(float(np.percentile(nul, 95)), 3), "common_mode_r": round(cm, 3), "shuffled_r": round(cm_sh, 3)})
    Pp = pd.DataFrame(pairs)
    res["pairs"] = pairs
    if len(Pp):
        res["pairs_summary"] = {"n_pairs": int(len(Pp)), "consistency_median": round(float(Pp.consistency.median()), 3),
                                "null_median": round(float(Pp.null_mean.median()), 3), "pairs_ge_0.9": int((Pp.consistency >= 0.9).sum()),
                                "pairs_above_null_p95": int((Pp.consistency > Pp.null_p95).sum()),
                                "common_mode_r_median": round(float(Pp.common_mode_r.median()), 3),
                                "shuffled_r_median": round(float(Pp.shuffled_r.median()), 3)}
    # 3. queue load
    M["t0"] = M.msg.map(msgs.sign_ms)
    M["load1s"] = [int(np.searchsorted(allp, t, side="left") - np.searchsorted(allp, t - 1000, side="left")) for t in M.t0]
    M["nother"] = M.msg.map(M.groupby("msg").size()) - 1
    ql = {}
    for w_, g in M.groupby("who"):
        if len(g) < 30:
            continue
        Z = np.column_stack([np.ones(len(g)), g.load1s.to_numpy(float), g.nother.to_numpy(float)])
        b, *_ = np.linalg.lstsq(Z, g.lag.to_numpy(float), rcond=None)
        e = g.lag.to_numpy(float) - Z @ b
        se = np.sqrt(np.diag(np.linalg.inv(Z.T @ Z)) * e.var())
        ql[w_[:10]] = {"n": int(len(g)), "ms_per_queued_msg": round(float(b[1]), 2), "t_load": round(float(b[1] / se[1]), 2),
                       "ms_per_other_actor": round(float(b[2]), 2), "t_other": round(float(b[2] / se[2]), 2)}
    res["queue_load"] = ql
    print(json.dumps({k: res[k] for k in res if k != "pairs"}, indent=1))
    json.dump(res, open(RES / "fanout_structure.json", "w"), indent=1)


if __name__ == "__main__":
    main()
