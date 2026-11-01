"""Iteration 16 (X152 = information P2, X157 = mechanics P2 steps 2-3, X161 critique 2): the ORIGINAL-SIZE decision per operator taker
order. Per wallet, LightGBM P(large) with feature groups added step by step; reported AUC within wallet, scored once on the score days.
Labels: 'osz' = total fill of the order hash > 30.5 (on-chain proxy; precision 1.00, recall 0.63 on calldata orders of 10-20..22);
'cd' = calldata original size >= 90 (exact; calldata_sample + it15 cl_orders + it16 cdfull_*). Menu 30 / 100 from 10-19 on.
Groups: G0 config (arm, window index mod 4, rel, hour, price level), G1 Binance spot at the decision anchor (pre-registration 5
clock, toward o), G2 other venues (USD-M BTC / ETH, OKX, Bybit), G3 Polymarket trades (server clock, m0 - 180), G4 Polymarket book at
the bot's view cut at e = m0 - 230 on the book clock (capture L2 grid, 10-20..22 only), G5 OWN STATE (leg rank, operator net toward o,
own in-flight orders by wallet, operator large net so far). Usage: python size16.py LABEL FITDAYS SCOREDAYS [tag]"""
import os, sys, json, gc
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score as auc

S = os.environ["RE16_SCRATCH"]
LABEL = sys.argv[1]; FIT = sys.argv[2].split(","); SCO = sys.argv[3].split(",")
TAG = sys.argv[4] if len(sys.argv) > 4 else ""
DAYS = sorted(set(FIT + SCO))
KS = [100, 250, 500, 1000, 2000]
fr_cols = ["cid", "wallet", "up", "m", "m0", "rank", "ev", "osz", "start_ts", "day", "rel", "rel_dec", "own_net"]
fr_cols += [f"dec_bs_mic_{k}" for k in KS] + [f"dec_bt_{k}" for k in KS] + [f"k{c}" for c in range(400, 140, -10)]
fr_cols += [f"own_bs_mic_{k}" for k in KS] + [f"own_bt_{k}" for k in KS]
fr_cols += [f"dec_{v}_{k}" for v in ("bf_btc", "bf_eth", "ok_btc", "by_btc") for k in KS]
fr_cols += ["dec_pm_last", "dec_pm_d500", "dec_pm_d3000", "dec_pm_f1", "dec_pm_f5", "dec_pm_dist"]
fr = pd.read_parquet(S + "/it14/dcclock14_frame.parquet", columns=fr_cols)
fr["dd"] = pd.to_datetime(fr.start_ts, unit="s").dt.strftime("%m-%d")
fr = fr[fr.dd.isin(DAYS)].reset_index(drop=True)
pr = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "m", "p_dc14_spot_dec", "p_dc14_spot_own"])
fr = fr.merge(pr, on=["cid", "wallet", "m"], how="left")
# ---------------- labels
if LABEL == "osz":
    fr["large"] = (fr.osz > 30.5).astype(int)
else:
    cols = ["tx", "role", "taker_amt", "maker_amt", "oside"]
    cds = [pd.read_parquet(".cache/re/btc5m-bot/calldata_sample.parquet", columns=cols),
           pd.read_parquet(S + "/it15/cl_orders.parquet", columns=cols)]
    for d in DAYS:
        fn = f"{S}/it16/cdfull_{d}.parquet"
        if os.path.exists(fn):
            cds.append(pd.read_parquet(fn, columns=cols))
    cd = pd.concat(cds, ignore_index=True)
    cd = cd[cd.role == "T"].copy(); cd["tx"] = cd.tx.str.lower()
    cd["orig"] = np.where(cd.oside == 0, cd.taker_amt, cd.maker_amt)
    cd = cd.drop_duplicates("tx")[["tx", "orig"]]
    maps = []
    for d in DAYS:
        fn = f"{S}/it15/l2ord_2026-{d}.parquet"
        if os.path.exists(fn):
            maps.append(pd.read_parquet(fn, columns=["tx", "cid", "wallet", "m"]))
    mp = pd.concat(maps, ignore_index=True); mp["tx"] = mp.tx.str.lower()
    mp = mp.merge(cd, on="tx", how="inner").drop_duplicates(["cid", "wallet", "m"])
    fr = fr.merge(mp[["cid", "wallet", "m", "orig"]], on=["cid", "wallet", "m"], how="left")
    fr = fr[fr.orig.notna()].reset_index(drop=True)
    fr["large"] = (fr.orig >= 90).astype(int)
sg = np.where(fr.up == 1, 1.0, -1.0)
print("orders", len(fr), "large share by wallet/day", fr.groupby(["wallet", "dd"]).large.mean().unstack().round(3).to_dict(), flush=True)
# ---------------- features
G = {}
fr["arm"] = (((fr.start_ts // 300) % 4).isin([1, 2])).astype(int); fr["wi4"] = (fr.start_ts // 300) % 4
fr["hour"] = pd.to_datetime(fr.start_ts, unit="s").dt.hour
po = np.where(fr.up == 1, fr.dec_pm_last, 1 - fr.dec_pm_last)  # Polymarket last price of the bought outcome
fr["p_o"] = po; fr["pdist"] = np.abs(po - 0.5)
G["G0"] = ["arm", "wi4", "rel_dec", "hour", "p_o", "pdist"]
for k in KS:
    fr[f"t_mic_{k}"] = fr[f"dec_bs_mic_{k}"] * sg; fr[f"a_mic_{k}"] = np.abs(fr[f"dec_bs_mic_{k}"])
    fr[f"t_bt_{k}"] = fr[f"dec_bt_{k}"] * sg
    fr[f"o_mic_{k}"] = fr[f"own_bs_mic_{k}"] * sg; fr[f"o_bt_{k}"] = fr[f"own_bt_{k}"] * sg   # the leg's OWN anchor (m - 260)
for c in range(400, 140, -10):
    fr[f"t_k{c}"] = fr[f"k{c}"] * sg
fr["conf"] = np.abs(2 * fr.p_dc14_spot_dec - 1); fr["pdc_o"] = np.where(fr.up == 1, fr.p_dc14_spot_dec, 1 - fr.p_dc14_spot_dec)
G["G1"] = [f"t_mic_{k}" for k in KS] + [f"a_mic_{k}" for k in KS] + [f"t_bt_{k}" for k in KS] + [f"t_k{c}" for c in (400, 350, 300, 280, 260, 240, 220, 200, 180, 150)] + ["conf", "pdc_o"] + [f"o_mic_{k}" for k in KS] + [f"o_bt_{k}" for k in KS]
for v in ("bf_btc", "bf_eth", "ok_btc", "by_btc"):
    for k in KS:
        fr[f"t_{v}_{k}"] = fr[f"dec_{v}_{k}"] * sg
G["G2"] = [f"t_{v}_{k}" for v in ("bf_btc", "bf_eth", "ok_btc", "by_btc") for k in KS]
fr["t_pm_d500"] = fr.dec_pm_d500 * sg; fr["t_pm_d3000"] = fr.dec_pm_d3000 * sg
G["G3"] = ["t_pm_d500", "t_pm_d3000", "dec_pm_f1", "dec_pm_f5", "dec_pm_dist"]
# G6: digital fair value / edge at the decision (strike = Gamma priceToBeat, known at the window start; S = Binance 1-s close of the
# second ending >= 1 s before the decision anchor m0 - 260; sigma = std of 1-s log returns over the previous 300 s)
from scipy.stats import norm
ptb = pd.read_parquet(".cache/re/btc5m-bot/ptb.parquet", columns=["start", "priceToBeat"]).drop_duplicates("start").set_index("start").priceToBeat
b1 = pd.read_parquet(".cache/re/btc5m-bot/binance_1s.parquet").sort_values("sec")
bsec = b1.sec.to_numpy(np.int64); bcl = b1.close.to_numpy(float); lr = np.r_[0.0, np.diff(np.log(bcl))]
csum = np.cumsum(lr); csq = np.cumsum(lr ** 2)
td = (fr.m0.to_numpy() - 260) / 1000.0
js = np.searchsorted(bsec, np.floor(td) - 2, "right") - 1
ok = js >= 300
Sx = np.where(ok, bcl[np.clip(js, 0, len(bcl) - 1)], np.nan)
j0 = np.clip(js - 300, 0, len(bcl) - 1); j1 = np.clip(js, 0, len(bcl) - 1)
mu = (csum[j1] - csum[j0]) / 300.0; var = (csq[j1] - csq[j0]) / 300.0 - mu ** 2
sig = np.sqrt(np.maximum(var, 1e-12))
K = fr.start_ts.map(ptb).to_numpy(float)
tau = np.maximum((fr.start_ts.to_numpy() + 300) - td, 1.0)
z_up = np.log(Sx / K) / (sig * np.sqrt(tau))
fr["z_o"] = z_up * sg; fr["abs_z"] = np.abs(z_up); fr["fv_o"] = norm.cdf(fr.z_o)
fr["edge_o"] = fr.fv_o - fr.p_o; fr["sig300"] = sig * 1e4; fr["tau"] = tau; fr["lnSK_o"] = np.log(Sx / K) * 1e4 * sg
# predicted Polymarket move in cents from the recent Binance move through the digital option's delta: 100 phi(z) r / (sigma sqrt(tau))
phi = norm.pdf(z_up)
for k in KS:
    fr[f"dp_dec_{k}"] = 100 * phi * fr[f"t_mic_{k}"].to_numpy() / (sig * 1e4 * np.sqrt(tau))
    fr[f"dp_own_{k}"] = 100 * phi * fr[f"o_mic_{k}"].to_numpy() / (sig * 1e4 * np.sqrt(tau))
fr["delta_c_per_bp"] = 100 * phi / (sig * 1e4 * np.sqrt(tau))
G["G6"] = ["z_o", "abs_z", "fv_o", "edge_o", "sig300", "tau", "lnSK_o", "delta_c_per_bp"] + [f"dp_dec_{k}" for k in KS] + [f"dp_own_{k}" for k in KS]
print("G6 coverage", round(float(np.isfinite(fr.edge_o).mean()), 3), flush=True)
# G4: capture L2 grid (50 ms), o and complement, cut at e = m0 - 230 (book clock; the bot's view ~m0 - 205)
gb = {}
for d in DAYS:
    fn = f"{S}/it15/l2grid_2026-{d}.parquet"
    if not os.path.exists(fn):
        continue
    tk = pd.read_parquet(f"{S}/it15/l2tok_2026-{d}.parquet"); gd = pd.read_parquet(fn, columns=["best", "c0", "c2", "c4"])
    n = len(tk); ng = len(gd) // n
    arr = {c: gd[c].to_numpy().reshape(n, ng).astype(np.float32) for c in ("best", "c0", "c2", "c4")}
    for i, r in enumerate(tk.itertuples()):
        gb[(r.cid, int(r.is_up))] = (int(r.start_ts), {c: arr[c][i] for c in arr})
    del gd, arr; gc.collect()
CUT = 230
have_book = len(gb) > 0 and all(os.path.exists(f"{S}/it15/l2grid_2026-{d}.parquet") for d in DAYS)
if have_book:
    book = {f"{s}_{c}_{x}": np.full(len(fr), np.nan, np.float32) for s in ("o", "x") for c in ("best", "c0", "c2", "c4") for x in (0, 100, 250, 500, 1000)}
    for (cid, up), g in fr.groupby(["cid", "up"]):
        for s, u in (("o", int(up)), ("x", 1 - int(up))):
            key = (cid, u)
            if key not in gb:
                continue
            st, A = gb[key]
            for x in (0, 100, 250, 500, 1000):
                t = g.m0.to_numpy() - CUT - x; k = ((t - (st * 1000 - 60000)) // 50).astype(np.int64)
                ok = (k >= 0) & (k < 7200); kk = np.clip(k, 0, 7199)
                for c in ("best", "c0", "c2", "c4"):
                    v = A[c][kk].astype(np.float32); v[~ok] = np.nan; book[f"{s}_{c}_{x}"][g.index.to_numpy()] = v
    for k, v in book.items():
        fr[k] = v
    # G4o: the same book features at the leg's OWN anchor (m - 230 on the book clock), for follow-up legs (rank >= 1)
    booko = {f"q{s}_{c}_{x}": np.full(len(fr), np.nan, np.float32) for s in ("o", "x") for c in ("best", "c0", "c2", "c4") for x in (0, 100, 250, 500, 1000)}
    for (cid, up), g in fr.groupby(["cid", "up"]):
        for s, u in (("o", int(up)), ("x", 1 - int(up))):
            key = (cid, u)
            if key not in gb:
                continue
            st, A = gb[key]
            for x in (0, 100, 250, 500, 1000):
                t = g.m.to_numpy() - CUT - x; k = ((t - (st * 1000 - 60000)) // 50).astype(np.int64)
                ok = (k >= 0) & (k < 7200); kk = np.clip(k, 0, 7199)
                for c in ("best", "c0", "c2", "c4"):
                    v = A[c][kk].astype(np.float32); v[~ok] = np.nan; booko[f"q{s}_{c}_{x}"][g.index.to_numpy()] = v
    for k, v in booko.items():
        fr[k] = v
    for s in ("o", "x"):
        for x in (100, 250, 500, 1000):
            fr[f"q{s}_best_d{x}"] = fr[f"q{s}_best_0"] - fr[f"q{s}_best_{x}"]
            fr[f"q{s}_c4_r{x}"] = fr[f"q{s}_c4_0"] / np.where(fr[f"q{s}_c4_{x}"] > 0, fr[f"q{s}_c4_{x}"], np.nan)
    G["G4o"] = [f"q{s}_{c}_0" for s in ("o", "x") for c in ("best", "c0", "c2", "c4")] +                [f"q{s}_best_d{x}" for s in ("o", "x") for x in (100, 250, 500, 1000)] + [f"q{s}_c4_r{x}" for s in ("o", "x") for x in (100, 250, 500, 1000)]
    for s in ("o", "x"):
        for c in ("c0", "c2", "c4"):
            for x in (100, 250, 500, 1000):
                fr[f"{s}_{c}_r{x}"] = fr[f"{s}_{c}_0"] / np.where(fr[f"{s}_{c}_{x}"] > 0, fr[f"{s}_{c}_{x}"], np.nan)
        for x in (100, 250, 500, 1000):
            fr[f"{s}_best_d{x}"] = fr[f"{s}_best_0"] - fr[f"{s}_best_{x}"]
    G["G4"] = [f"{s}_{c}_0" for s in ("o", "x") for c in ("best", "c0", "c2", "c4")] + \
              [f"{s}_{c}_r{x}" for s in ("o", "x") for c in ("c0", "c2", "c4") for x in (100, 250, 500, 1000)] + \
              [f"{s}_best_d{x}" for s in ("o", "x") for x in (100, 250, 500, 1000)]
# G5 own state: leg rank, operator net toward o (fills <= m - 2 s), own in-flight orders (matches in (m - 150, m) and (m - 300, m)),
# operator LARGE net toward o so far in the window (orders with osz > 30.5 matched before m - 2000)
fr["t_own_net"] = fr.own_net * sg
al = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "m", "up", "osz"])
mv = fr.m.to_numpy()
for w in ("DS", "GF", "XM"):
    a = np.sort(al.m[al.wallet == w].to_numpy())
    for lo in (150, 300):
        fr[f"busy_{w}_{lo}"] = (np.searchsorted(a, mv, "left") - np.searchsorted(a, mv - lo, "right")).astype(np.float32)
aa = np.sort(al.m.to_numpy())
for lo in (300, 1000, 3000):
    fr[f"nop_{lo}"] = (np.searchsorted(aa, mv, "left") - np.searchsorted(aa, mv - lo, "right")).astype(np.float32)
al["lg"] = (al.osz > 30.5) * np.where(al.up == 1, 1.0, -1.0) * al.osz
lgn = np.zeros(len(fr), np.float32)
idx = {cid: g.sort_values("m") for cid, g in al.groupby("cid")}
for cid, g in fr.groupby("cid"):
    h = idx.get(cid)
    if h is None:
        continue
    mm = h.m.to_numpy(); cs = np.cumsum(h.lg.to_numpy())
    j = np.searchsorted(mm, g.m.to_numpy() - 2000, "right") - 1
    lgn[g.index.to_numpy()] = np.where(j >= 0, cs[np.clip(j, 0, len(cs) - 1)], 0.0)
fr["t_large_net"] = lgn * sg
G["G5"] = ["rank", "t_own_net", "t_large_net"] + [f"busy_{w}_{lo}" for w in ("DS", "GF", "XM") for lo in (150, 300)] + [f"nop_{lo}" for lo in (300, 1000, 3000)]
P = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=40, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
         lambda_l2=1.0, max_bin=63, verbose=-1, seed=7)
G["G5a"] = ["t_own_net", "t_large_net"]   # inventory-type own state (admissible with disclosure)
pub = ["G0", "G1", "G2", "G3", "G6"]
steps = [("G0", ["G0"]), ("G0+1", ["G0", "G1"]), ("G0-3", ["G0", "G1", "G2", "G3"]), ("G6only", ["G6"]), ("PUB", pub)]
if "G4" in G:
    steps += [("G4only", ["G4"]), ("PUB+G4", pub + ["G4"]), ("G4o_only", ["G4o"]), ("PUB+G4+G4o", pub + ["G4", "G4o"])]
steps += [("G5a_only", ["G5a"]), ("PUB+G5a", pub + ["G5a"])]
if "G4" in G:
    steps += [("PUB+G4+G4o+G5a", pub + ["G4", "G4o", "G5a"])]
steps += [("G5only", ["G5"]), ("PUB+G5", pub + ["G5"])]
fr["isGF"] = (fr.wallet == "GF").astype(int); fr["isXM"] = (fr.wallet == "XM").astype(int)
fit = fr.dd.isin(FIT).to_numpy(); sco = fr.dd.isin(SCO).to_numpy()
if os.environ.get("SIZE16_SEED") == "1":
    seed = (fr.t_large_net == 0).to_numpy() & (lgn == 0)
    fit = fit & seed; sco = sco & seed
    print("SEED subset: fit", int(fit.sum()), "score", int(sco.sum()), flush=True)
res = {"label": LABEL, "fit": FIT, "score": SCO, "n_fit": int(fit.sum()), "n_score": int(sco.sum()), "auc": {}, "top": {}}
preds = {}
for w in ("DS", "GF", "XM", "ALL"):
    mw = np.ones(len(fr), bool) if w == "ALL" else (fr.wallet == w).to_numpy()
    for nm, gs in steps:
        cols = sum([G[g] for g in gs], [])
        if w == "ALL":
            cols = cols + ["isGF", "isXM"]
        a, b = fit & mw, sco & mw
        if fr.large[a].nunique() < 2 or fr.large[b].nunique() < 2:
            continue
        m = lgb.train(P, lgb.Dataset(fr.loc[a, cols].astype(np.float32), fr.large[a]), 300)
        p = m.predict(fr.loc[b, cols].astype(np.float32))
        res["auc"][f"{w}|{nm}"] = round(float(auc(fr.large[b], p)), 4)
        if nm in ("PUB", "PUB+G4", "PUB+G4+G4o", "PUB+G5a", "PUB+G4+G4o+G5a", "G5only", "G6only", "G4o_only"):
            imp = pd.Series(m.feature_importance("gain"), index=cols).sort_values(ascending=False)
            res["top"][f"{w}|{nm}"] = {k: round(float(v / imp.sum()), 3) for k, v in imp.head(8).items()}
        preds[f"{w}|{nm}"] = (np.where(b)[0], p)
    res["n_large_score_" + w] = int(fr.large[sco & mw].sum())
    res["n_score_" + w] = int((sco & mw).sum())
print(json.dumps(res, indent=1))
json.dump(res, open(f"research/reverse_engineering/btc5m-bot/results/size16_{LABEL}{TAG}.json", "w"), indent=1)
out = fr.loc[sco, ["cid", "wallet", "m", "m0", "up", "start_ts", "osz", "large"] + (["orig"] if "orig" in fr else [])].copy()
for k, (ii, p) in preds.items():
    s = pd.Series(np.nan, index=fr.index); s.iloc[ii] = p; out["p|" + k] = s[sco].to_numpy()
out.to_parquet(f"{S}/it16/size16_pred_{LABEL}{TAG}.parquet", index=False)
