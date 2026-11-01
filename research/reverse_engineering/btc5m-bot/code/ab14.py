"""Iteration 14, X130 (mechanics panel P1): the window-index A/B schedule. Arm B = (start_ts / 300) mod 4 in {1, 2}, arm A otherwise
(also tested: mod 2). Per UTC hour of window start (BUILD 10-02..16 and VALIDATE 10-16..22, all < H): taker orders (fills role T,
one per (tx, wallet, token)), filled shares per order, P(filled >= 45), DS / GF / XM share of orders, orders per window; Welch t per
hour on per-window means (B vs A). Original sizes from the calldata sample hours (BUY takerAmount). Then the share of two13's LARGE
stream that comes from B windows, and the phase map (contiguous hours with |t| >= 4 on the size or the DS-share contrast)."""
import os, json
import numpy as np, pandas as pd
from scipy import stats

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
H = 1792713600


def welch(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or len(b) < 3:
        return None
    t, p = stats.ttest_ind(a, b, equal_var=False)
    return float(t), float(p)


def main():
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "start_ts", "token", "is_up", "shares", "oh", "side"])
    fl = fl[(fl.start_ts < H) & (fl.side == 0)]  # side 0 = BUY (all cluster fills are BUYs)
    t = fl[fl.role == "T"].groupby(["tx", "wallet", "token"], as_index=False).agg(start_ts=("start_ts", "first"), sh=("shares", "sum"))
    t["k4"] = (t.start_ts // 300) % 4
    t["B"] = t.k4.isin([1, 2]).astype(int)
    t["k2"] = (t.start_ts // 300) % 2
    t["hour"] = (t.start_ts // 3600) * 3600
    t["large"] = (t.sh >= 45).astype(float)
    t["ds"] = (t.wallet == "DS").astype(float); t["gf"] = (t.wallet == "GF").astype(float); t["xm"] = (t.wallet == "XM").astype(float)
    W = t.groupby("start_ts").agg(sh=("sh", "mean"), large=("large", "mean"), ds=("ds", "mean"), gf=("gf", "mean"), n=("sh", "size"),
                                  B=("B", "first"), k2=("k2", "first"), hour=("hour", "first")).reset_index()
    rows = []
    for h, g in W.groupby("hour"):
        r = {"hour": int(h), "utc": pd.Timestamp(h, unit="s", tz="UTC").strftime("%m-%d %H"), "windows": int(len(g))}
        a, b = g[g.B == 0], g[g.B == 1]
        for k in ("sh", "large", "ds", "gf", "n"):
            r[f"{k}_A"] = round(float(a[k].mean()), 3) if len(a) else None
            r[f"{k}_B"] = round(float(b[k].mean()), 3) if len(b) else None
            w = welch(b[k], a[k]); r[f"t_{k}"] = round(w[0], 2) if w and np.isfinite(w[0]) else None
        a2, b2 = g[g.k2 == 0], g[g.k2 == 1]
        w = welch(b2.sh, a2.sh); r["t_sh_mod2"] = round(w[0], 2) if w and np.isfinite(w[0]) else None
        rows.append(r)
    D = pd.DataFrame(rows)
    D["size_phase"] = D.t_sh.abs() >= 4
    D["disp_phase"] = D.t_ds.abs() >= 4
    # contiguous phases (allow one-hour gaps)
    def runs(mask):
        out, cur = [], None
        hrs = D.hour.to_numpy(); mk = mask.to_numpy()
        for i, (h, m) in enumerate(zip(hrs, mk)):
            if m:
                if cur and h - cur[1] <= 7200:
                    cur[1] = h; cur[2] += 1
                else:
                    if cur: out.append(cur)
                    cur = [h, h, 1]
        if cur: out.append(cur)
        return [{"from": pd.Timestamp(a, unit="s", tz="UTC").strftime("%m-%d %H"), "to": pd.Timestamp(b, unit="s", tz="UTC").strftime("%m-%d %H"), "flagged_hours": n}
                for a, b, n in out if n >= 3]
    res = {"hours": int(len(D)), "size_phase_hours": int(D.size_phase.sum()), "disp_phase_hours": int(D.disp_phase.sum()),
           "size_phases": runs(D.size_phase), "disp_phases": runs(D.disp_phase),
           "mod2_size_hours_abs_t_ge4": int((D.t_sh_mod2.abs() >= 4).sum())}
    # pooled contrasts inside / outside the flagged phases, VALIDATE and BUILD
    W = W.merge(D[["hour", "size_phase", "disp_phase"]], on="hour")
    for per, sel in (("VALIDATE", W.start_ts >= 1792108800), ("BUILD", W.start_ts < 1792108800)):
        o = {}
        for ph in ("size_phase", "disp_phase"):
            for inside in (True, False):
                g = W[sel & (W[ph] == inside)]
                o[f"{ph}_{'in' if inside else 'out'}"] = {k: [round(float(g[g.B == 0][k].mean()), 3), round(float(g[g.B == 1][k].mean()), 3)] for k in ("sh", "large", "ds", "gf", "n")} | {"windows": int(len(g))}
        res[per] = o
    # original sizes on the calldata sample hours (BUY orders of the three wallets)
    cd = pd.read_parquet(f"{C}/calldata_sample.parquet", columns=["tx", "cid", "role", "maker", "token", "maker_amt", "taker_amt", "oside", "sign_ms"])
    win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "start_ts"])
    WAL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
    cd["w"] = cd.maker.str.lower().map(WAL)
    cd = cd[cd.w.notna() & (cd.oside == 0)].merge(win, on="cid", how="left")
    cd = cd[cd.start_ts.notna() & (cd.start_ts < H)]
    cd["size"] = (cd.taker_amt.astype(float) / 1e6).round(0)
    cd["B"] = ((cd.start_ts // 300) % 4).isin([1, 2]).astype(int)
    cd["hour"] = (cd.start_ts // 3600) * 3600
    cd = cd.drop_duplicates(["tx", "maker", "token", "role", "size"])
    cs = []
    for h, g in cd.groupby("hour"):
        r = {"utc": pd.Timestamp(h, unit="s", tz="UTC").strftime("%m-%d %H"), "orders": int(len(g))}
        for arm in (0, 1):
            vc = g[g.B == arm]["size"].value_counts(normalize=True).head(4)
            r["A" if arm == 0 else "B"] = {str(int(k)): round(float(v), 3) for k, v in vc.items()}
        cs.append(r)
    res["calldata_original_sizes_by_hour_arm"] = cs
    # the LARGE stream of two13 by arm (VALIDATE days)
    sw = f"{C}/it13/streams_win.parquet"
    if os.path.exists(sw):
        S = pd.read_parquet(sw)
        res["streams_win_columns"] = list(S.columns)[:20]
    lg = t[(t.start_ts >= 1792108800)].copy()
    lg["LARGE"] = lg.sh >= 45  # VALIDATE windows: the two13 threshold (taker orders here, not all order hashes)
    lg["day"] = pd.to_datetime(lg.start_ts, unit="s", utc=True).dt.strftime("%m-%d")
    res["LARGE_share_of_shares_from_B_by_day"] = {d: round(float(g[g.LARGE].sh[g[g.LARGE].B == 1].sum() / max(g[g.LARGE].sh.sum(), 1)), 3) for d, g in lg.groupby("day")}
    res["B_share_of_all_taker_shares_by_day"] = {d: round(float(g.sh[g.B == 1].sum() / g.sh.sum()), 3) for d, g in lg.groupby("day")}
    D.to_csv(f"{R}/ab14_hours.csv", index=False)
    json.dump(res, open(f"{R}/ab14.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("calldata_original_sizes_by_hour_arm",)}, indent=1)[:6000])
    for r in cs:
        print(r)


if __name__ == "__main__":
    main()
