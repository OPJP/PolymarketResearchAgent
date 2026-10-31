"""Iteration 3, mechanics panel P1 (X19) + P3 (X21): the live-lab clock and the taker trigger on the SERVER clock.

Development-block units only (dev_markets.parquet, gameStartTime in a development block >= T0), wallet markets.
Books: own recorder tommy_cs2_near (f snapshots + pc changes, unthrottled within 5c) where it covers a token,
else the shared clob_wallets (q/f top-10, throttled 200 ms). Every record carries t (laptop receive ms) and s (CLOB
server ms). Trades: x records (s, tx hash h). Orders: calldata_dev (sign_ms = the signer's own clock).
1. Calibration: s(x, first record of the tx) - sign_ms of the taker order, per signer group; laptop offset t - s.
2. Consumed-side near-touch depth (within 3c of the best) around each taker order's signing, indexed by s and by t.
3. The iteration-2 collapse rule (D <= 0.5 x max over [-1.5, -0.4] s, ref >= 200, no trade in 1.5 s) on both clocks:
   share of orders with an event in [sign - 2 s, sign] and in (sign, sign + 1.1 s]; random-time control.
4. Onset of the cancel wave after signing (server clock): first time D <= 0.8 x D(sign) and <= 0.5 x D(sign).
Output: results/server_clock.json
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
T0 = 1793404800
PACK = {"0xfe8a28be83ba295a9384f72f240d2cfa96bc23ce", "0x2529c68db36ce8aa64c64affe620267744a3548a",
        "0x72aaaaf9f6b0286e390de5b568af0f99a00c90e0", "0xf1ee4842fa0c7283632185e42577027452d4519c",
        "0x4ebc2722adc772bde8680792d0a6fdf15499a33d", "0x93078b5dd1c34d0f288d2f51b23f1347520d9da3"}
W = 0.03


def near(L, side):
    if not L:
        return 0.0
    if side == "o":
        b = min(L)
        return sum(z for p, z in L.items() if p <= b + W + 1e-9)
    b = max(L)
    return sum(z for p, z in L.items() if p >= b - W - 1e-9)


def read(feed, tok0, start, end):
    out = []
    h = int(start // 3600 * 3600)
    while h < end:
        try:
            for r in live.iter_live(feed, max(h, start), min(h + 3600, end)):
                if r.get("a") in tok0:
                    out.append(r)
        except Exception as e:  # noqa: BLE001  zlib.error on a damaged member: keep what was read
            print(feed, time.strftime("%H", time.gmtime(h)), "stopped", type(e).__name__, flush=True)
        h += 3600
    return out


def series_shared(recs):
    rows = []
    for r in recs:
        if r["k"] in ("q", "f"):
            b = {float(p): float(z) for p, z in (r.get("b") or [])}
            o = {float(p): float(z) for p, z in (r.get("o") or [])}
            rows.append((r["s"], r["t"], near(b, "b"), near(o, "o"), max(b) if b else np.nan, min(o) if o else np.nan))
    return rows


def series_own(recs):
    rows = []
    bd = od = None
    for r in sorted(recs, key=lambda r: (r["s"], r["t"])):
        if r["k"] == "f":
            bd = {float(p): float(z) for p, z in (r.get("b") or [])}
            od = {float(p): float(z) for p, z in (r.get("o") or [])}
        elif r["k"] == "pc" and bd is not None:
            for side, p, z in r["c"]:
                bk = bd if side == "BUY" else od
                if z == 0:
                    bk.pop(float(p), None)
                else:
                    bk[float(p)] = float(z)
        else:
            continue
        rows.append((r["s"], r["t"], near(bd, "b"), near(od, "o"), max(bd) if bd else np.nan, min(od) if od else np.nan))
    return rows


def events(S, D, trs, frac=0.5, min_ref=200):
    ev = []
    last = -1e18
    for i in range(len(S)):
        lo, hi = np.searchsorted(S, S[i] - 1500), np.searchsorted(S, S[i] - 400, side="right")
        if hi <= lo:
            continue
        ref = D[lo:hi].max()
        if ref < min_ref or D[i] > frac * ref:
            continue
        k = np.searchsorted(trs, S[i] - 1500)
        if k < len(trs) and trs[k] <= S[i]:
            continue
        if S[i] - last < 3000:
            continue
        last = S[i]
        ev.append(S[i])
    return np.array(ev)


def pct(v, qs):
    return [int(np.percentile(v, q)) for q in qs] if len(v) >= 5 else [int(x) for x in v]


def main():
    now = time.time()
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    m = m[m.wallet_trades > 0]
    tok = {}
    for r in m.itertuples():
        tok[r.tok0] = (r.cid, 0, r.tok0)
        tok[r.tok1] = (r.cid, 1, r.tok0)
    tok0 = set(m.tok0)
    sh = read("clob_wallets", tok0, T0 + 12 * 3600, now)
    ow = read("tommy_cs2_near", tok0, T0 + 12 * 3600, now)
    print("records shared", len(sh), "own", len(ow), flush=True)
    xs = {}
    for r in sh + ow:
        if r.get("k") == "x":
            xs.setdefault(((r.get("h") or "").lower(), r["s"], r["a"]), r)
    X = pd.DataFrame([{"h": k[0], "s": k[1], "a": k[2], "t": v["t"]} for k, v in xs.items()])
    X["off"] = X.t - X.s
    X["bucket"] = (X.s // 900000) * 900
    offs = {time.strftime("%H:%M", time.gmtime(k)): [int(np.percentile(v, 5)), int(np.median(v)), int(np.percentile(v, 95)), int(len(v))]
            for k, v in X.groupby("bucket").off}
    ser, own_start = {}, {}
    for a in tok0:
        so = series_own([r for r in ow if r["a"] == a and r["k"] in ("f", "pc")])
        ss = series_shared([r for r in sh if r["a"] == a])
        t_own0 = so[0][0] if so else np.inf
        own_start[a] = t_own0
        rows = [x for x in ss if x[0] < t_own0] + so
        ser[a] = pd.DataFrame(rows, columns=["s", "t", "Db", "Do", "bb", "ba"]).sort_values("s").reset_index(drop=True)
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    d = d[(d.idx == -1) & (d.sign_ms > 1.79e12) & (d.sign_ms < now * 1000 + 5000) & d.token_id.astype(str).isin(tok)].copy()
    d["a"] = d.token_id.astype(str).map(lambda t: tok[t][2])
    d["team"] = [(tok[str(t)][1] if s == 0 else 1 - tok[str(t)][1]) for t, s in zip(d.token_id, d.side)]
    d["grp"] = np.where(d.maker == WALLET, "W", np.where(d.maker.isin(PACK), "pack", "other"))
    d["tx"] = d.tx.str.lower()
    d = d.drop_duplicates(["tx"])
    fx = X.groupby("h").s.min()
    d["match_s"] = d.tx.map(fx)
    cal = {}
    for g, o in d[d.match_s.notna()].groupby("grp"):
        v = (o.match_s - o.sign_ms).to_numpy()
        cal[g] = {"n": int(len(v)), **{f"p{q}": int(np.percentile(v, q)) for q in (5, 10, 25, 50, 75, 90)}}
    per = {}
    for mk_, o in d[d.match_s.notna()].groupby("maker"):
        v = (o.match_s - o.sign_ms).to_numpy()
        if len(v) >= 8:
            per[mk_[:10]] = {"grp": o.grp.iloc[0], "n": int(len(v)), "p10": int(np.percentile(v, 10)), "p50": int(np.median(v)),
                             "p90": int(np.percentile(v, 90))}
    offsets = [-2000, -1500, -1000, -700, -500, -300, -200, -100, 0, 100, 200, 300, 500, 800, 1000, 1040, 1100, 1300, 1500]
    trades_s = {a: np.sort(X[X.a == a].s.to_numpy().astype(float)) for a in tok0}
    trades_t = {a: np.sort(X[X.a == a].t.to_numpy().astype(float)) for a in tok0}
    res = {"laptop_offset_t_minus_s_by_15min_p5_p50_p95_n": offs, "calibration_match_minus_sign_ms": cal, "per_signer": per}
    rng = np.random.default_rng(7)
    for clock in ("s", "t"):
        prof = {g: {o: [] for o in offsets} for g in ("W", "pack", "other")}
        ev_tab = {}
        for a in tok0:
            df = ser[a].sort_values(clock)
            T = df[clock].to_numpy().astype(float)
            trs = trades_s[a] if clock == "s" else trades_t[a]
            for team, col in ((0, "Do"), (1, "Db")):
                D = df[col].to_numpy()
                ev_tab[(a, team)] = (events(T, D, trs), T, D)
        rec = {g: {"pre": [], "post": [], "dt": []} for g in ("W", "pack", "other")}
        for r in d.itertuples():
            e, T, D = ev_tab[(r.a, r.team)]
            if len(T) == 0 or r.sign_ms < T[0] + 2000 or r.sign_ms > T[-1]:
                continue
            i0 = np.searchsorted(T, r.sign_ms - 2000, side="right") - 1
            base = D[i0] if i0 >= 0 else np.nan
            if base and base > 0:
                for o in offsets:
                    i = np.searchsorted(T, r.sign_ms + o, side="right") - 1
                    prof[r.grp][o].append(D[i] / base if i >= 0 else np.nan)
            rec[r.grp]["pre"].append(bool(((e >= r.sign_ms - 2000) & (e <= r.sign_ms)).any()))
            rec[r.grp]["post"].append(bool(((e > r.sign_ms) & (e <= r.sign_ms + 1100)).any()))
            near_e = e[(e >= r.sign_ms - 2000) & (e <= r.sign_ms + 1500)]
            if len(near_e):
                rec[r.grp]["dt"].append(float(near_e[0] - r.sign_ms))
        ctrl = []
        for (a, team), (e, T, D) in ev_tab.items():
            if len(T) < 10:
                continue
            for t in rng.uniform(T[0] + 2000, T[-1], 300):
                ctrl.append(bool(((e >= t - 2000) & (e <= t)).any()))
        res["clock_" + clock] = {
            "profile_median_rel_to_minus2s": {g: {str(o): (round(float(np.nanmedian(v)), 2) if len(v) else None) for o, v in pr.items()}
                                              for g, pr in prof.items()},
            "n_orders": {g: len(v["pre"]) for g, v in rec.items()},
            "event_in_[sign-2s,sign]": {g: round(float(np.mean(v["pre"])), 3) if v["pre"] else None for g, v in rec.items()},
            "event_in_(sign,sign+1.1s]": {g: round(float(np.mean(v["post"])), 3) if v["post"] else None for g, v in rec.items()},
            "first_event_minus_sign_ms_p10_p50_p90": {g: pct(v["dt"], (10, 50, 90)) for g, v in rec.items()},
            "random_time_event_in_prior_2s": round(float(np.mean(ctrl)), 3), "n_random": len(ctrl),
            "events_total": int(sum(len(v[0]) for v in ev_tab.values()))}
    ons = {g: {"to0.8": [], "to0.5": [], "none": 0, "n": 0} for g in ("W", "pack")}
    for r in d[d.grp.isin(["W", "pack"])].itertuples():
        df = ser[r.a]
        T = df.s.to_numpy().astype(float)
        D = (df.Do if r.team == 0 else df.Db).to_numpy()
        if len(T) == 0 or r.sign_ms < T[0] + 2000 or r.sign_ms > T[-1]:
            continue
        i0 = np.searchsorted(T, r.sign_ms, side="right") - 1
        if i0 < 0 or D[i0] < 100:
            continue
        b = D[i0]
        ons[r.grp]["n"] += 1
        j = np.arange(i0 + 1, np.searchsorted(T, r.sign_ms + 1100, side="right"))
        f8 = j[D[j] <= 0.8 * b]
        f5 = j[D[j] <= 0.5 * b]
        if len(f8):
            ons[r.grp]["to0.8"].append(T[f8[0]] - r.sign_ms)
        else:
            ons[r.grp]["none"] += 1
        if len(f5):
            ons[r.grp]["to0.5"].append(T[f5[0]] - r.sign_ms)
    res["wave_onset_after_sign_server_ms"] = {g: {"n": v["n"], "no_0.8_drop_by_1.1s": v["none"],
                                                  "to0.8_p10_p25_p50_p75_p90": pct(v["to0.8"], (10, 25, 50, 75, 90)),
                                                  "to0.5_p10_p50_p90": pct(v["to0.5"], (10, 50, 90))} for g, v in ons.items()}
    res["own_recorder_tokens"] = int(sum(np.isfinite(v) for v in own_start.values()))
    json.dump(res, open(RES / "server_clock.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
