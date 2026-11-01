"""Iteration 19, X198 (mechanics panel iter18 P3 step 1): is the per-decision size class an exchangeable coin inside the register?

PRE-REGISTRATION 19 (written 11-01 ~13:40 UTC, before the first run). Record: it18/sib_frame.parquet (73,577 operator taker orders of
10-20..22 with exact calldata classes L = original >= 90, the operator's true within-window state S / E, slot, true side sg).
Strata: wallet x UTC hour x slot x S-relation (none / with / against, from sg and S) x E tercile (S != 0 orders; S = 0 is its own
class). Null: permute L within strata, 2,000 draws (keeps every stratum's class rate). Statistics (one-sided, observed > null):
 Q1 lag-1 same-class rate of consecutive orders of the same wallet in the same window (ordered by m);
 Q2 the same over the pooled operator sequence of a window (all three wallets);
 Q3 Q1 restricted to pairs less than 2 s apart, and Q4 pairs 2 s or more apart;
 Q5 the number of large-class runs per (wallet, window) (fewer runs than the null = clustering).
Reading: if every p > 0.01 the class is exchangeable given the strata (a private i.i.d. coin per decision; condition 5's size term is
then capped by the expectation ceiling already measured, true-state PnL-proxy Spearman 0.566 / 0.706). If not, there is a further
state (a burst or a sub-window regime) to decode, and its size is reported as the excess same-class rate.
Usage: python exch19.py SCRATCH_DIR"""
import sys, json, os
import numpy as np, pandas as pd

R = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))


def main():
    S = sys.argv[1]
    p = pd.read_parquet(f"{S}/it18/sib_frame.parquet", columns=["wallet", "m", "start_ts", "L", "S", "E", "slot", "sg"])
    p = p.sort_values(["start_ts", "m"], kind="stable").reset_index(drop=True)
    relS = np.where(p.S == 0, 0, np.where(p.sg == p.S, 1, 2))
    et = np.full(len(p), -1)
    nz = p.S.to_numpy() != 0
    q = np.quantile(p.E[nz], [1 / 3, 2 / 3])
    et[nz] = np.digitize(p.E[nz], q)
    hr = (p.m // 3600000) % 24
    strat = pd.factorize(pd.Series(p.wallet.astype(str) + "|" + hr.astype(str) + "|" + p.slot.astype(str) + "|" + relS.astype(str) + "|" + et.astype(str)))[0]
    L = p.L.to_numpy().astype(np.int8)
    W = p.wallet.to_numpy(); st = p.start_ts.to_numpy(); m = p.m.to_numpy(np.int64)
    # pairs: same wallet same window consecutive
    q1 = []
    for (w, s), g in p.groupby(["wallet", "start_ts"], sort=False):
        ix = g.index.to_numpy()
        if len(ix) > 1:
            q1.append(np.column_stack([ix[:-1], ix[1:]]))
    P1 = np.concatenate(q1)
    gap1 = m[P1[:, 1]] - m[P1[:, 0]]
    q2 = []
    for s, g in p.groupby("start_ts", sort=False):
        ix = g.index.to_numpy()
        if len(ix) > 1:
            q2.append(np.column_stack([ix[:-1], ix[1:]]))
    P2 = np.concatenate(q2)
    short = gap1 < 2000
    grp = pd.factorize(pd.Series(W.astype(str)) + "|" + pd.Series(st.astype(str)))[0]
    order = np.lexsort((m, grp))

    def stats(Lx):
        s1 = Lx[P1[:, 0]] == Lx[P1[:, 1]]
        s2 = Lx[P2[:, 0]] == Lx[P2[:, 1]]
        lo = Lx[order]; gg = grp[order]
        start_run = (lo == 1) & ((np.r_[True, gg[1:] != gg[:-1]]) | (np.r_[0, lo[:-1]] == 0))
        return np.array([s1.mean(), s2.mean(), s1[short].mean(), s1[~short].mean(), start_run.sum()], float)
    obs = stats(L)
    rng = np.random.default_rng(19)
    # within-stratum permutation
    sp = np.argsort(strat, kind="stable")
    null = []
    for _ in range(2000):
        o_ = np.lexsort((rng.random(len(L)), strat))
        Lp = np.empty_like(L); Lp[sp] = L[o_]
        null.append(stats(Lp))
    null = np.asarray(null)
    names = ["Q1_same_wallet_lag1_same_class", "Q2_pooled_lag1_same_class", "Q3_Q1_gap_lt_2s", "Q4_Q1_gap_ge_2s", "Q5_large_runs"]
    res = {"prereg": "19", "orders": int(len(p)), "strata": int(strat.max() + 1), "pairs_Q1_Q2": [int(len(P1)), int(len(P2))], "short_pairs": int(short.sum())}
    for i, nm in enumerate(names):
        if nm == "Q5_large_runs":
            pv = float(((null[:, i] <= obs[i]).sum() + 1) / (len(null) + 1))
        else:
            pv = float(((null[:, i] >= obs[i]).sum() + 1) / (len(null) + 1))
        res[nm] = {"observed": round(float(obs[i]), 5), "null_mean": round(float(null[:, i].mean()), 5), "null_q99": round(float(np.quantile(null[:, i], 0.99 if nm != "Q5_large_runs" else 0.01)), 5),
                   "excess": round(float(obs[i] - null[:, i].mean()), 5), "p_one_sided": pv}
    # per wallet Q1
    res["per_wallet_Q1"] = {}
    for w in ("DS", "GF", "XM"):
        mk = W[P1[:, 0]] == w
        o = float((L[P1[mk, 0]] == L[P1[mk, 1]]).mean())
        res["per_wallet_Q1"][w] = {"pairs": int(mk.sum()), "observed": round(o, 4), "large_rate": round(float(L[W == w].mean()), 4)}
    res["exchangeable_at_0.01"] = bool(all(res[n]["p_one_sided"] > 0.01 for n in names))
    print(json.dumps(res, indent=1), flush=True)
    json.dump(res, open(f"{R}/exch19.json", "w"), indent=1)


if __name__ == "__main__":
    main()
