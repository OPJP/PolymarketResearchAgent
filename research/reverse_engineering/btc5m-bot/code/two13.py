"""Iteration 13 (X121 = assumptions P1, X118 = mechanics P1 step 0, X120 / X122 = per-wallet ceilings): the two-stream
decomposition of the operator's window net. Stream labels from fills grouped by order hash: LARGE = total filled shares of
the order >= 80 in the 60-share era (windows starting before 10-12 00:00 UTC) and >= 45 later; SMALL otherwise. Per window
and wallet: L, S, T = L + S (signed shares, Up +), PnL. Descriptives on BUILD (10-09..15) and VALIDATE (10-16..22), and
per-wallet ORACLE ceilings of condition 5 on VALIDATE (upper bounds: each pooled stream contains the wallet's own flow).
Writes .cache/re/btc5m-bot/it13/streams_sec.parquet (per (cid, rel) flows yL / yS pooled and per wallet) and
results/two13.json."""
import os, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"
OUT = f"{C}/it13"; os.makedirs(OUT, exist_ok=True)
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
VAL0, H = 1792108800, 1792713600
ERA60_END = 1791763200  # 10-12 00:00 UTC: 60/100 menu before, 30-share menus after
W = ("GF", "XM", "DS")


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    return round(float(np.corrcoef(a[m], b[m])[0, 1]), 4) if m.sum() > 3 else None


def main():
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["oh", "wallet", "role", "shares", "price", "fee_usd", "cid", "start_ts", "rel", "is_up", "up_payout"])
    fl = fl[fl.start_ts < H]
    tot = fl.groupby("oh").shares.sum()
    fl["osz"] = tot.reindex(fl.oh).to_numpy()
    thr = np.where(fl.start_ts < ERA60_END, 80.0, 45.0)
    fl["large"] = fl.osz >= thr
    fl["sg"] = np.where(fl.is_up, 1.0, -1.0) * fl.shares
    fl["pay"] = np.where(fl.is_up, fl.up_payout, 1 - fl.up_payout)
    fl["pnl"] = fl.shares * (fl.pay - fl.price) - fl.fee_usd
    # per-second flows (block-second rel), pooled and per wallet
    g = fl[(fl.rel >= 0) & (fl.rel < 300)].copy()
    g["rel"] = g.rel.astype(np.int64)
    sec = g.assign(yL=np.where(g.large, g.sg, 0.0), yS=np.where(~g.large, g.sg, 0.0)).groupby(["cid", "rel"])[["yL", "yS"]].sum()
    for w in W:
        gw = g[g.wallet == w]
        sw = gw.assign(a=np.where(gw.large, gw.sg, 0.0), b=np.where(~gw.large, gw.sg, 0.0)).groupby(["cid", "rel"])[["a", "b"]].sum()
        sec = sec.join(sw.rename(columns={"a": "yL" + w, "b": "yS" + w}), how="outer")
    sec = sec.fillna(0).astype(np.float32).reset_index()
    sec.to_parquet(f"{OUT}/streams_sec.parquet", index=False)
    # window level
    win = pd.read_parquet(f"{C}/windows.parquet")
    win = win[win.start_ts < H].set_index("cid")
    Y = (2 * win.up_payout - 1).astype(float)
    def wsum(mask, col):
        return fl[mask].groupby("cid")[col].sum().reindex(win.index).fillna(0)
    D = pd.DataFrame(index=win.index)
    D["start_ts"] = win.start_ts
    D["L"] = wsum(fl.large, "sg"); D["S"] = wsum(~fl.large, "sg"); D["N"] = D.L + D.S
    D["P"] = fl.groupby("cid").pnl.sum().reindex(win.index).fillna(0)
    for w in W:
        m = fl.wallet == w
        D["L" + w] = wsum(m & fl.large, "sg"); D["S" + w] = wsum(m & ~fl.large, "sg"); D["T" + w] = D["L" + w] + D["S" + w]
        D["P" + w] = fl[m].groupby("cid").pnl.sum().reindex(win.index).fillna(0)
        D["n" + w] = fl[m].groupby("cid").size().reindex(win.index).fillna(0)
    D["Y"] = Y
    D.to_parquet(f"{OUT}/streams_win.parquet")
    res = {"definition": "large = order total filled shares >= 80 (60-share era, windows < 10-12) else >= 45",
           "share_large_shares": {}, "build": {}, "validate": {}}
    for nm, m in (("build", D.start_ts < VAL0), ("validate", D.start_ts >= VAL0)):
        d = D[m]; o = {}
        o["n_windows"] = int(len(d))
        for a, b in (("DS", "GF"), ("DS", "XM"), ("GF", "XM")):
            o[f"cross_{a}_{b}"] = {k: corr(d[k + a], d[k + b]) for k in ("L", "S", "T")}
        o["within_corr_L_S"] = {w: corr(d["L" + w], d["S" + w]) for w in W}
        o["within_corr_L_S"]["pool"] = corr(d.L, d.S)
        o["sd"] = {k: round(float(d[k].std()), 1) for k in ("L", "S", "N")}
        o["corr_T_w_with_L_w"] = {w: corr(d["T" + w], d["L" + w]) for w in W}
        o["pnl_vs_net_x_outcome"] = {w: corr(d["P" + w], d["T" + w] * d.Y) for w in W}
        o["pnl_vs_net_x_outcome"]["pool"] = corr(d.P, d.N * d.Y)
        res[nm] = o
        ml = fl.start_ts < VAL0 if nm == "build" else fl.start_ts >= VAL0
        res["share_large_shares"][nm] = {w: round(float(fl[ml & (fl.wallet == w) & fl.large].shares.sum() / fl[ml & (fl.wallet == w)].shares.sum()), 3) for w in W}
    # ORACLE ceilings on VALIDATE (upper bounds; loadings fitted on BUILD windows by OLS without intercept)
    b, v = D[D.start_ts < VAL0], D[D.start_ts >= VAL0]
    ceil = {}
    for w in W:
        Xb = np.c_[b.L, b.S]; ab = np.linalg.lstsq(Xb, b["T" + w].to_numpy(), rcond=None)[0]
        # the other wallets' legs only (no own flow): leave-one-out
        Lo, So = b.L - b["L" + w], b.S - b["S" + w]
        ab_o = np.linalg.lstsq(np.c_[Lo, So], b["T" + w].to_numpy(), rcond=None)[0]
        Lv, Sv = v.L - v["L" + w], v.S - v["S" + w]
        # within-wallet (own legs, BUILD loadings): the ceiling if the wallet's OWN streams were known
        ab_w = np.linalg.lstsq(np.c_[b["L" + w], b["S" + w]], b["T" + w].to_numpy(), rcond=None)[0]
        ceil[w] = {
            "T_pool": corr(v["P" + w], v.N * v.Y),
            "L_pool": corr(v["P" + w], v.L * v.Y),
            "aL_bS_pool_BUILDload": corr(v["P" + w], (ab[0] * v.L + ab[1] * v.S) * v.Y), "load_pool": [round(float(x), 3) for x in ab],
            "aL_bS_others_BUILDload": corr(v["P" + w], (ab_o[0] * Lv + ab_o[1] * Sv) * v.Y), "load_others": [round(float(x), 3) for x in ab_o],
            "T_others": corr(v["P" + w], (Lv + Sv) * v.Y),
            "own_T": corr(v["P" + w], v["T" + w] * v.Y),
            "windows_with_fills": int((v["n" + w] > 0).sum()),
        }
    ceil["pool"] = {"T_pool": corr(v.P, v.N * v.Y), "L_pool": corr(v.P, v.L * v.Y)}
    res["oracle_ceilings_validate"] = ceil
    # halves of VALIDATE for the oracle (condition 7 tolerance check)
    half = v.start_ts < (VAL0 + H) // 2
    res["oracle_T_pool_halves"] = {w: [corr(v.loc[m, "P" + w], v.loc[m, "N"] * v.loc[m, "Y"]) for m in (half, ~half)] for w in W}
    json.dump(res, open(f"{R}/two13.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
