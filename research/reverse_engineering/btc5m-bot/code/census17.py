"""Iteration 17 (X173 step 1 = assumptions P1, X175 = assumptions P3, X165 steps 1-2 = information P2): configuration census of the
NEW routing regime (11-01 06:00-09:30 development windows, code/post17.py) against the capture days 10-20..22 (complete calldata).
Per wallet (DS, GF, XM, W4, W5): taker orders, original-size menu, large share (original >= 90 shares, and >= 60 as a variant), role
mix of fills (maker / taker), maker-first order hashes (maker fills only, no taker fill on the same hash). Events: per (window,
outcome), operator taker orders of the five wallets sorted by match ms m; a new event starts after a 300-ms gap. First-leg carrier
shares by size class, pooled first-leg large share, and the visible five-wallet priority fit (disp16b rule DS > GF > W4 > XM > W5,
H 300 ms) on the new record. Usage: python census17.py"""
import os, sys, json
import numpy as np, pandas as pd

S = os.environ["RE16_SCRATCH"]
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
W5 = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM",
      "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS", "0xd84403efd50b49a1d8a7181627e00307e6ea5908": "W4",
      "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c": "W5"}
WL = ("DS", "GF", "XM", "W4", "W5")


def events(o):
    o = o.sort_values(["cid", "is_up", "m"]).reset_index(drop=True)
    new = (o.cid != o.cid.shift()) | (o.is_up != o.is_up.shift()) | (o.m - o.m.shift() >= 300)
    o["ev"] = new.cumsum(); o["first"] = new.to_numpy()
    o["gap"] = (o.m - o.m.shift()).where(~new)
    return o


def summarize(o, fills, tag, thr=90):
    r = {"taker_orders": {w: int((o.wallet == w).sum()) for w in WL}}
    r["order_share_3w"] = {w: round(float((o.wallet == w).sum() / o.wallet.isin(["DS", "GF", "XM"]).sum()), 4) for w in ("DS", "GF", "XM")}
    r["menu_top"] = {w: {str(int(k)): int(v) for k, v in o[o.wallet == w].orig.round().value_counts().head(6).items()} for w in WL if (o.wallet == w).any()}
    o = o.assign(L=(o.orig >= thr).astype(int))
    r["P_large_by_wallet"] = {w: round(float(o[o.wallet == w].L.mean()), 4) for w in WL if (o.wallet == w).any()}
    r["P_large_pooled_3w"] = round(float(o[o.wallet.isin(["DS", "GF", "XM"])].L.mean()), 4)
    r["P_large_pooled_5w"] = round(float(o.L.mean()), 4)
    e = events(o)
    f1 = e[e["first"]]
    r["first_leg_large_share_5w"] = round(float(f1.L.mean()), 4)
    r["first_leg_carrier_by_class"] = {c: {w: round(float((f1[f1.L == c].wallet == w).mean()), 4) for w in WL} for c in (0, 1)}
    r["n_first_legs"] = {c: int((f1.L == c).sum()) for c in (0, 1)}
    r["legs_per_event"] = round(float(e.groupby("ev").size().mean()), 3)
    fol = e[~e["first"]]
    r["follower_fast_share_lt150"] = round(float((fol.gap < 150).mean()), 4) if len(fol) else None
    r["P_large_fast_follower"] = round(float(fol[fol.gap < 150].L.mean()), 4) if (fol.gap < 150).any() else None
    r["P_large_first_leg_by_wallet"] = {w: round(float(f1[f1.wallet == w].L.mean()), 4) for w in WL if (f1.wallet == w).any()}
    # visible five-wallet priority list DS > GF > W4 > XM > W5, slot 300 ms (disp16b best rule)
    pr = ["DS", "GF", "W4", "XM", "W5"]
    e2 = o.sort_values("m").reset_index(drop=True)
    mm = e2.m.to_numpy(); ww = e2.wallet.to_numpy(); ok = 0
    for i in range(len(e2)):
        j0 = np.searchsorted(mm, mm[i] - 300, "right")
        busy = set(ww[j0:i])
        pick = next((w for w in pr if w not in busy), pr[-1])
        ok += pick == ww[i]
    r["priority5_visible_acc_all"] = round(ok / max(len(e2), 1), 4)
    # role mix of fills and maker-first hashes
    if fills is not None:
        ff = fills[fills.side == 0]
        r["fills_by_role"] = {w: {k: int(v) for k, v in ff[ff.wallet == w].role.value_counts().items()} for w in WL if (ff.wallet == w).any()}
        r["maker_share_of_fills"] = {w: round(float((ff[ff.wallet == w].role == "M").mean()), 4) for w in WL if (ff.wallet == w).any()}
        r["maker_share_of_shares"] = {w: round(float(ff[(ff.wallet == w) & (ff.role == "M")].shares.sum() / max(ff[ff.wallet == w].shares.sum(), 1e-9)), 4) for w in WL if (ff.wallet == w).any()}
        th = set(ff[ff.role == "T"].oh)
        mk = ff[ff.role == "M"]
        r["maker_first_hash_share"] = {w: round(float((~mk[mk.wallet == w].oh.isin(th)).mean()), 4) for w in WL if (mk.wallet == w).any()}
        if "price" in mk:
            r["maker_price_q"] = {w: [round(float(x), 3) for x in mk[mk.wallet == w].price.quantile([0.1, 0.5, 0.9])] for w in WL if (mk.wallet == w).any()}
            r["maker_fill_size_top"] = {w: {str(round(k, 1)): int(v) for k, v in mk[mk.wallet == w].shares.round(1).value_counts().head(5).items()} for w in WL if (mk.wallet == w).any()}
    print(tag, json.dumps(r, default=str), flush=True)
    return r


res = {}
# ---- new regime: 11-01 06:00-09:30
P = S + "/it17"
fl = pd.read_parquet(P + "/post17_fills.parquet"); cd = pd.read_parquet(P + "/post17_cd.parquet"); xr = pd.read_parquet(P + "/post17_xms.parquet")
win = pd.read_parquet(P + "/post17_windows.parquet")
cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["tx"] = cd.tx.str.lower(); cd["wallet"] = cd.maker.str.lower().map(W5)
cd = cd[cd.wallet.notna()]
tok = pd.concat([win[["cid", "start_ts", "up_token"]].rename(columns={"up_token": "token"}).assign(is_up=True),
                 win[["cid", "start_ts", "down_token"]].rename(columns={"down_token": "token"}).assign(is_up=False)])
cd = cd.drop(columns=[c for c in ("cid", "start_ts") if c in cd]).merge(tok, on="token", how="inner")
cd["m"] = cd.tx.map(xr.dropna(subset=["s"]).groupby("tx").s.min())
cd = cd[cd.m.notna()].copy(); cd["orig"] = cd.taker_amt; cd["limit"] = cd.maker_amt / cd.taker_amt
fl["wallet"] = fl.owner.str.lower().map(W5)
res["new_regime_11-01_06_0930"] = summarize(cd[["cid", "is_up", "m", "wallet", "orig", "limit", "start_ts"]], fl, "NEW")
res["new_regime_11-01_06_0930_thr60"] = {"P_large_by_wallet_ge60": {w: round(float((cd[cd.wallet == w].orig >= 60).mean()), 4) for w in WL if (cd.wallet == w).any()}}
res["new_regime_windows"] = int(win.cid.nunique())
# ---- capture days 10-20..22 (complete calldata; l2ord maps tx -> (cid, wallet, m)); W4 / W5 have no calldata there (taker tapes only)
rows = []
for d in ("10-20", "10-21", "10-22"):
    c = pd.read_parquet(f"{S}/it16/cdfull_2026-{d}.parquet" if os.path.exists(f"{S}/it16/cdfull_2026-{d}.parquet") else f"{S}/it16/cdfull_{d}.parquet",
                        columns=["tx", "role", "taker_amt", "maker_amt", "oside", "maker"])
    c = c[(c.role == "T") & (c.oside == 0)].copy(); c["tx"] = c.tx.str.lower(); c["wallet"] = c.maker.str.lower().map(W5)
    mp = pd.read_parquet(f"{S}/it15/l2ord_2026-{d}.parquet", columns=["tx", "cid", "wallet", "m", "is_up", "start_ts"])
    mp["tx"] = mp.tx.str.lower()
    x = mp.merge(c[["tx", "wallet", "taker_amt", "maker_amt"]], on=["tx", "wallet"], how="inner").drop_duplicates(["tx", "wallet", "cid", "is_up"])
    x["day"] = d; rows.append(x)
cap = pd.concat(rows); cap["orig"] = cap.taker_amt
f2 = pd.read_parquet(_ROOT + "/.cache/re/btc5m-bot/fills.parquet", columns=["wallet", "role", "side", "start_ts", "shares", "price", "oh"] if True else None)
f2 = f2[(f2.start_ts >= 1792454400) & (f2.start_ts < 1792713600)]
res["capture_10-20_22"] = summarize(cap[["cid", "is_up", "m", "wallet", "orig", "start_ts"]], f2.assign(side=0) if "side" not in f2 else f2, "CAP")
for d in ("10-20", "10-21", "10-22"):
    res[f"capture_{d}_first_leg_large_share_3w"] = round(float(events(cap[cap.day == d].assign(L=(cap[cap.day == d].orig >= 90).astype(int)))
                                                               .query("first").L.mean()), 4)
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/census17.json", "w"), indent=1, default=str)
print("saved")
