"""Iteration 17 (X169 'if false' branch; X176 step 1; X173 step 2): (A) the size state's free draws per window on the complete record of
10-20..22: the seed (first large order of a window): its time, its side vs the dc14 side of the same order, vs the window's final large
net; flips (a large order against S) per window and their dc14 agreement; binary entropy of the seed side given dc14. (B) class-keyed
routing: priority-slot dispatchers on visible occupancy (a wallet is busy with a match in (m - H, m)), one priority order per size
class, fit (best order x H) on 10-20 and scored once on 10-21..22, against the size-blind best rule on the same orders.
Usage: python seed17.py"""
import os, sys, json, itertools
import numpy as np, pandas as pd

S = os.environ["RE16_SCRATCH"]
DAYS = ["10-20", "10-21", "10-22"]
W3 = ("DS", "GF", "XM")
cols = ["tx", "role", "taker_amt", "oside"]
cds = [pd.read_parquet(".cache/re/btc5m-bot/calldata_sample.parquet", columns=cols), pd.read_parquet(S + "/it15/cl_orders.parquet", columns=cols)]
cds += [pd.read_parquet(f"{S}/it16/cdfull_{d}.parquet", columns=cols) for d in DAYS]
cd = pd.concat(cds); cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["tx"] = cd.tx.str.lower(); cd = cd.drop_duplicates("tx")
mp = pd.concat([pd.read_parquet(f"{S}/it15/l2ord_2026-{d}.parquet", columns=["tx", "cid", "wallet", "m"]) for d in DAYS])
mp["tx"] = mp.tx.str.lower(); mp = mp.merge(cd[["tx", "taker_amt"]], on="tx", how="left").drop_duplicates(["cid", "wallet", "m"])
p = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "osz", "start_ts", "p_dc14_spot_own"])
p["dd"] = pd.to_datetime(p.start_ts, unit="s").dt.strftime("%m-%d")
p = p[p.dd.isin(DAYS)].merge(mp[["cid", "wallet", "m", "taker_amt"]], on=["cid", "wallet", "m"], how="left")
p = p[p.taker_amt.notna()].copy(); p["L"] = (p.taker_amt >= 90).astype(int)
p["sg"] = np.where(p.up == 1, 1, -1); p["sh"] = np.where(p.p_dc14_spot_own > 0.5, 1, -1)
p = p.sort_values(["start_ts", "m"]).reset_index(drop=True)
res = {"orders": int(len(p))}
# ---------------- (A) seed and flips
rows = []
for st, g in p.groupby("start_ts"):
    lg = g[g.L == 1]
    if not len(lg):
        rows.append({"st": st, "has": 0}); continue
    sg = lg.sg.to_numpy(); sh = lg.sh.to_numpy(); rel = lg.m.to_numpy() / 1000.0 - st
    flips = int((sg[1:] != sg[:-1]).sum())
    fl_idx = np.where(sg[1:] != sg[:-1])[0] + 1
    net = float((g.sg * g.L * g.osz).sum())
    rows.append({"st": st, "has": 1, "seed_t": rel[0], "seed_ok_dc14": int(sg[0] == sh[0]), "flips": flips,
                 "flip_ok_dc14": float((sg[fl_idx] == sh[fl_idx]).mean()) if len(fl_idx) else np.nan,
                 "final_S": int(sg[-1]), "seed_side": int(sg[0]), "net_sign": int(np.sign(net)), "n_large": int(len(lg)),
                 "large_ok_dc14": float((sg == sh).mean())})
W = pd.DataFrame(rows); Wl = W[W.has == 1]
pa = float(Wl.seed_ok_dc14.mean())
hb = lambda q: float(-(q * np.log2(q) + (1 - q) * np.log2(1 - q))) if 0 < q < 1 else 0.0
res["A_seed"] = {"windows": int(len(W)), "with_large": int(len(Wl)), "seed_t_q": [round(float(x), 1) for x in Wl.seed_t.quantile([0.1, 0.25, 0.5, 0.75, 0.9])],
                 "seed_side_eq_dc14": round(pa, 4), "seed_side_entropy_bits_given_dc14": round(hb(1 - pa), 3),
                 "large_orders_side_eq_dc14": round(float(Wl.large_ok_dc14.mean()), 4),
                 "flips_per_window_mean": round(float(Wl.flips.mean()), 3), "flips_q": [int(x) for x in Wl.flips.quantile([0.25, 0.5, 0.75, 0.9])],
                 "flip_side_eq_dc14": round(float(Wl.flip_ok_dc14.mean()), 4),
                 "final_S_eq_seed": round(float((Wl.final_S == Wl.seed_side).mean()), 4),
                 "final_large_net_sign_eq_seed": round(float((Wl.net_sign == Wl.seed_side).mean()), 4),
                 "final_large_net_sign_eq_final_S": round(float((Wl.net_sign == Wl.final_S).mean()), 4),
                 "share_windows_no_flip": round(float((Wl.flips == 0).mean()), 4)}
print(json.dumps(res["A_seed"]), flush=True)
# ---------------- (B) class-keyed priority dispatchers on visible occupancy
q = p.sort_values("m").reset_index(drop=True)
mm = q.m.to_numpy(); ww = q.wallet.to_numpy(); LL = q.L.to_numpy(); dd = q.dd.to_numpy()


def busy_sets(H):
    j0 = np.searchsorted(mm, mm - H, "right")
    out = []
    for i in range(len(q)):
        out.append(frozenset(ww[j0[i]:i]))     # matches in (m - H, m) strictly before i in sort order (same-ms ties counted)
    return out


orders = list(itertools.permutations(W3))
B = {}
for H in (150, 200, 300, 400):
    bs = busy_sets(H)
    pick = {o_: np.array([next((w for w in o_ if w not in b), o_[-1]) for b in bs]) for o_ in orders}
    B[H] = pick
fit = dd == "10-20"; sco = ~fit
best_blind = max(((H, o_) for H in B for o_ in orders), key=lambda k: (B[k[0]][k[1]][fit] == ww[fit]).mean())
best_cls = {c: max(((H, o_) for H in B for o_ in orders), key=lambda k: (B[k[0]][k[1]][fit & (LL == c)] == ww[fit & (LL == c)]).mean()) for c in (0, 1)}
acc_blind = float((B[best_blind[0]][best_blind[1]][sco] == ww[sco]).mean())
pred_cls = np.where(LL == 1, B[best_cls[1][0]][best_cls[1][1]], B[best_cls[0][0]][best_cls[0][1]])
acc_cls = float((pred_cls[sco] == ww[sco]).mean())
res["B_dispatch"] = {"size_blind_best_fit10-20": [best_blind[0], list(best_blind[1])], "size_blind_acc_10-21_22": round(acc_blind, 4),
                     "class_best_fit10-20": {str(c): [best_cls[c][0], list(best_cls[c][1])] for c in (0, 1)},
                     "class_keyed_acc_10-21_22": round(acc_cls, 4),
                     "class_keyed_acc_by_class": {str(c): round(float((pred_cls[sco & (LL == c)] == ww[sco & (LL == c)]).mean()), 4) for c in (0, 1)},
                     "size_blind_acc_by_class": {str(c): round(float((B[best_blind[0]][best_blind[1]][sco & (LL == c)] == ww[sco & (LL == c)]).mean()), 4) for c in (0, 1)},
                     "always_DS": round(float((ww[sco] == "DS").mean()), 4)}
xm = sco & (LL == 1)
pr = pred_cls[xm] == "XM"; tr = ww[xm] == "XM"
res["B_dispatch"]["XM_in_large_class_precision_recall"] = [round(float((pr & tr).sum() / max(pr.sum(), 1)), 4), round(float((pr & tr).sum() / max(tr.sum(), 1)), 4)]
print(json.dumps(res["B_dispatch"]), flush=True)
json.dump(res, open("research/reverse_engineering/btc5m-bot/results/seed17.json", "w"), indent=1, default=str)
