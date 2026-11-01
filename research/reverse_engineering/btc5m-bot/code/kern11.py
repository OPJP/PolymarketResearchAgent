"""Iteration 11 (X60, the 250-ms regime as a natural experiment; follows pmxt11): on a development hour of the pmxt archive inside
the 250-ms taker-delay regime, (1) the crowd's fresh-signed sign-to-match floor from V2 calldata of sampled BTC 5m match txs (match
= the archive's server ms; expected ~D + 35 ms = ~285 ms if D = 250 ms, vs 186-190 ms on 10-31 with D = 150 ms); (2) the cluster's
reaction kernel: directional excess of the Binance USD-M BTCUSDT trade-price move toward the bought outcome over [m - L - 50, m -
L) by lag L, against placebo instants (m +- 5-60 s). Under 'the bot reacts ~100-150 ms after the tick and the order then waits D
before matching', the peak sits ~D + 100-150 ms before the match: ~350-400 ms here vs ~250-300 ms on 10-31 (kernel7, microprice).
Binance archive (data.binance.vision futures/um daily aggTrades, checksum-verified) reduced at once to the hour; the zip is deleted.
Usage: python kern11.py OUT_JSON 2026-08-06T16"""
import os, sys, json, io, time, calendar, hashlib, zipfile
import numpy as np, pandas as pd, httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calldata

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
H = 1792713600
OPS = {"0xc53375ff94e96100f2b30a4b5775db35218d69a9", "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537",
       "0xd84403efd50b49a1d8a7181627e00307e6ea5908"}
URL = "https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{d}.zip"


def r4(x):
    return round(float(x), 4)


def binance_hour(day, t0, t1):
    out = f"{C}/it11/bnf_{day}_{t0}.parquet"
    if os.path.exists(out):
        return pd.read_parquet(out)
    z = f"{C}/it11/tmp_{day}.zip"
    with httpx.stream("GET", URL.format(d=day), timeout=180, follow_redirects=True) as r:
        r.raise_for_status()
        with open(z, "wb") as fh:
            for ch in r.iter_bytes(1 << 20):
                fh.write(ch)
    chk = httpx.get(URL.format(d=day) + ".CHECKSUM", timeout=30).text.split()[0]
    ok = hashlib.sha256(open(z, "rb").read()).hexdigest() == chk
    if not ok:
        os.remove(z); raise RuntimeError("checksum mismatch")
    with zipfile.ZipFile(z) as zz:
        raw = zz.read(zz.namelist()[0])
    os.remove(z)
    df = pd.read_csv(io.BytesIO(raw), header=None, dtype=str)
    df = df[[1, 5]].rename(columns={1: "p", 5: "T"})
    del raw
    df = df[df["T"].str.isdigit()]
    df["T"] = df["T"].astype(np.int64); df["p"] = df["p"].astype(float)
    if df["T"].iloc[0] > 1e14:  # microseconds
        df["T"] //= 1000
    df = df[(df["T"] >= (t0 - 120) * 1000) & (df["T"] < (t1 + 60) * 1000)].reset_index(drop=True)
    df.to_parquet(out)
    return df


def main(out, hour):
    t0 = calendar.timegm(time.strptime(hour, "%Y-%m-%dT%H")); t1 = t0 + 3600
    assert t1 <= H
    tag = hour.replace("-", "").replace("T", "_")
    Tr = pd.read_parquet(f"{C}/it11/pmxt_{tag}_trades.parquet"); F = pd.read_parquet(f"{C}/it11/pmxt_{tag}_cluster.parquet")
    mk = json.load(open(f"{C}/it11/pmxt_{tag}_markets.json"))
    up_tok = {k: str(v) for k, v in mk["up_tokens"].items()}
    Tr["tx"] = Tr.transaction_hash.str.lower()
    res = {"hour": hour, "archive_trades": int(len(Tr))}
    # (1) crowd fresh-signed floor from calldata of sampled match txs (not operator txs)
    txms = Tr.groupby("tx").ms.min()
    optx = set(F.tx)
    cand = [t for t in txms.index if t not in optx]
    rng = np.random.default_rng(11)
    samp = list(rng.choice(cand, min(250, len(cand)), replace=False))
    cd = calldata.to_frame(calldata.fetch_txs(samp, threads=2, log_every=10 ** 6))
    if len(cd):
        cd["txl"] = cd.tx.str.lower(); cd["m"] = cd.txl.map(txms)
        t = cd[(cd.role == "T") & ~cd.maker.isin(OPS) & (cd.oside == 0) & cd.m.notna()].drop_duplicates(["txl", "maker"])
        dt = (t.m - t.sign_ms).to_numpy(float); dt = dt[(dt > -5000) & (dt < 600000)]
        if len(dt):
            res["crowd_sign_to_match_ms"] = {"n": int(len(dt)), "q01": float(np.percentile(dt, 1)), "q05": float(np.percentile(dt, 5)), "q10": float(np.percentile(dt, 10)),
                                             "q25": float(np.percentile(dt, 25)), "median": float(np.median(dt)), "min_positive": float(dt[dt > 0].min()) if (dt > 0).any() else None,
                                             "share_lt_200": r4((dt < 200).mean()), "share_200_300": r4(((dt >= 200) & (dt < 300)).mean())}
            pw = t.assign(dt=t.m - t.sign_ms).groupby("maker").dt.min()
            res["crowd_per_wallet_min_ms_q10_50"] = [float(np.percentile(pw, 10)), float(np.percentile(pw, 50))] if len(pw) else None
    # (2) cluster kernel
    ft = F[(F.role == "T") & F.m.notna() & (F.w != "W4")].drop_duplicates("tx")
    bt = Tr[Tr.side == "BUY"].sort_values("ms").drop_duplicates("tx")
    ft = ft.merge(bt[["tx", "market", "asset_id"]], on="tx", how="left")
    ft = ft[ft.market.isin(up_tok)]
    ft["up"] = ft.apply(lambda r: str(r.asset_id) == up_tok[r.market], axis=1)
    res["cluster_taker_matches"] = int(len(ft)); res["by_wallet"] = {w: int(n) for w, n in ft.w.value_counts().items()}
    day = time.strftime("%Y-%m-%d", time.gmtime(t0))
    B = binance_hour(day, t0, t1)
    T = B["T"].to_numpy(np.int64); p = B["p"].to_numpy(float)

    def px(t):
        i = np.searchsorted(T, t, "right") - 1
        v = p[np.clip(i, 0, None)]; v = np.where(i >= 0, v, np.nan)
        return v
    m = ft.m.to_numpy(np.int64); sg = np.where(ft.up.to_numpy(bool), 1.0, -1.0)
    pl = m + (rng.choice([-1, 1], len(m)) * rng.uniform(5000, 60000, len(m))).astype(np.int64)
    prof = {}
    for L in range(0, 1001, 25):
        a = np.sign(px(m - L) - px(m - L - 50)) * sg; b = np.sign(px(pl - L) - px(pl - L - 50)) * sg
        prof[L] = [r4(np.nanmean(a)), r4(np.nanmean(b))]
    res["kernel_excess_by_L_ms (cluster, placebo)"] = prof
    best = max(prof.items(), key=lambda kv: kv[1][0] - kv[1][1])
    res["kernel_peak_L_ms"] = int(best[0]); res["kernel_peak_excess_minus_placebo"] = r4(best[1][0] - best[1][1])
    for w, g in ft.groupby("w"):
        mm = g.m.to_numpy(np.int64); ss = np.where(g.up.to_numpy(bool), 1.0, -1.0)
        if len(mm) >= 40:
            pr = {L: r4(np.nanmean(np.sign(px(mm - L) - px(mm - L - 50)) * ss)) for L in range(0, 801, 50)}
            res.setdefault("kernel_by_wallet", {})[w] = {"n": int(len(mm)), "peak_L": int(max(pr, key=pr.get)), "profile": pr}
    # gap floor per wallet (taker matches)
    for w, g in ft.groupby("w"):
        mm = np.sort(g.m.to_numpy(np.int64)); gap = np.diff(mm)
        if len(gap) >= 20:
            res.setdefault("taker_gap_ms", {})[w] = {"n": int(len(mm)), "min": int(gap.min()), "q01": float(np.percentile(gap, 1)), "q05": float(np.percentile(gap, 5)),
                                                    "share_lt_250": r4((gap < 250).mean()), "share_lt_350": r4((gap < 350).mean())}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1)[:5000])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
