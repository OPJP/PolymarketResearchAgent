"""Examiner round 2: truncation / corruption test of the frozen rule's decision inputs on lot f1 (the rule's own code).

(1) Presence (features2.build_panel + presence3_rule / _activity / _own): for the 30 BTC 5m windows drawn from the listing
    in step 0 (seed 20261101), every 10-s bin t is rebuilt from (a) data truncated at t (clean prints with ts >= t,
    Binance seconds >= t and cluster fills with ts >= t deleted) and (b) data corrupted after t (random prices, sizes,
    sides and wallets of every print at/after t, a random-walk spot from t on, fake 500-share cluster fills after t);
    features and predictions must equal the full-data row. Positive control: truncation at t - 1.
(2) Side (side_sm.side_state_machine, counted 'r8c_no_own_state'): for 300 seeded maker fills, the decision at block
    second b is recomputed with prints stamped > b - 3, Binance seconds >= b - 2 and Chainlink stamps > b - 4 deleted, and
    with them corrupted; positive control: prints stamped b - 3 also deleted.
(3) Price on the block clock (last clean print strictly before the fill second - 0.01): truncated / corrupted at b.
(4) Selection print features (dq_last, fair_p of sel2.day_prints): recomputed for 300 seeded prints from data truncated
    at the print (prints with ts >= the print's ts deleted, spot seconds >= ts - 2 deleted).
"""
from __future__ import annotations

import json
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

from r2_common import CLUSTER, EXC, RES, WS

from features2 import Spot, build_panel, fair_up  # noqa: E402
from train2 import SETS  # noqa: E402
import side_sm  # noqa: E402

EV = EXC / "ev"
CODE = WS / "code"
CLOCK = ["hour_utc", "dow", "us_session"]
FEATS = {"rule": SETS["all_path_xwin"] + CLOCK, "activity": SETS["activity"], "own": SETS["all_path_xwin"] + CLOCK + ["inv_s", "inv_o"]}
ALLF = sorted(set(sum(FEATS.values(), [])) - set(CLOCK))


def add_clock(p):
    t = pd.to_datetime(p["start_ts"], unit="s")
    p["hour_utc"] = (t.dt.hour + t.dt.minute / 60).astype(np.float32).to_numpy()
    p["dow"] = t.dt.day_of_week.astype(np.int8).to_numpy()
    p["us_session"] = ((p["dow"] < 5) & (p["hour_utc"] >= 12) & (p["hour_utc"] < 21)).astype(np.int8)
    return p


def same(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return (a == b) | (np.isnan(a) & np.isnan(b))


def corrupt_tape(cl, t, rng, keep_le=False):
    c = cl.copy()
    m = (c["ts"] > t) if keep_le else (c["ts"] >= t)
    n = int(m.sum())
    if n:
        c.loc[m, "price"] = rng.uniform(0.01, 0.99, n).round(2).astype(np.float32)
        c.loc[m, "size"] = rng.uniform(1, 2000, n).astype(np.float32)
        c.loc[m, "side"] = rng.choice(["BUY", "SELL"], n)
        c.loc[m, "wallet"] = [f"0x{rng.integers(0, 2**62):016x}" for _ in range(n)]
    return c


def main():
    t0 = time.time()
    rng = np.random.default_rng(20261101)
    step0 = json.loads((RES / "exam_r2_step0.json").read_text())
    w = pd.read_parquet(EV / "w5.parquet").sort_values("start_ts").reset_index(drop=True)
    w["up_token"], w["down_token"] = w["up_token"].astype(str), w["down_token"].astype(str)
    clean = pd.read_parquet(EV / "clean5.parquet")
    mk = pd.read_parquet(EV / "mk5.parquet")
    spd = pd.read_parquet(EV / "spot_btc.parquet")
    sec_all, px_all = spd["sec"].to_numpy(), spd["px"].to_numpy()
    models = {nm: lgb.Booster(model_file=str(CODE / f"presence3_{nm}.txt")) for nm in FEATS}
    res = {"presence": {"windows": 0, "rows": 0, "trunc_feature_mismatch": 0, "corrupt_feature_mismatch": 0, "trunc_pred_mismatch": 0,
                        "corrupt_pred_mismatch": 0, "control_feature_mismatch": 0, "control_pred_mismatch": 0, "bad_features": {}}}
    R = res["presence"]
    starts = set(step0["truncation_sample_starts"])
    for i in range(1, len(w)):
        s0 = int(w.loc[i, "start_ts"])
        if s0 not in starts:
            continue
        pair = w.iloc[[i - 1, i]].reset_index(drop=True)
        cid = pair.loc[1, "cid"]
        cl = clean[clean["cid"].isin(set(pair["cid"]))]
        ok = (sec_all >= s0 - 7200) & (sec_all < s0 + 400)
        sec, px = sec_all[ok], px_all[ok]
        full = add_clock(build_panel(pair, Spot(sec, px), cl, mk))
        full = full[full["cid"] == cid].reset_index(drop=True)
        for nm in FEATS:
            full["p_" + nm] = models[nm].predict(full[FEATS[nm]])
        R["windows"] += 1
        for rel in range(0, 300, 10):
            t = s0 + rel
            variants = {}
            ks = sec < t
            variants["trunc"] = build_panel(pair, Spot(sec[ks], px[ks]), cl[cl["ts"] < t], mk[mk["ts"] < t])
            pxc = px.copy()
            j = np.nonzero(sec >= t)[0]
            if len(j):
                pxc[j] = px[j[0] - 1] * np.exp(np.cumsum(rng.normal(0, 3e-4, len(j))))
            fake = mk.iloc[:0].copy()
            fake = pd.DataFrame({"wallet": list(CLUSTER)[0], "tx": 1, "token_id": [pair.loc[1, "up_token"], pair.loc[1, "down_token"]] * 3,
                                 "ts": t + rng.integers(0, 300 - rel, 6), "side": "BUY", "price": 0.5, "shares": 500.0, "cid": cid, "role": "maker"})
            variants["corrupt"] = build_panel(pair, Spot(sec, pxc), corrupt_tape(cl, t, rng), pd.concat([mk, fake], ignore_index=True))
            kc = sec < t - 1
            variants["control"] = build_panel(pair, Spot(sec[kc], px[kc]), cl[cl["ts"] < t - 1], mk[mk["ts"] < t - 1])
            for vn, pv in variants.items():
                pv = add_clock(pv[(pv["cid"] == cid)].reset_index(drop=True))
                row = pv[pv["rel"] == rel]
                fr_ = full[full["rel"] == rel]
                bad = [f for f in ALLF if not same(row[f].to_numpy(), fr_[f].to_numpy()).all()]
                predbad = False
                for nm in FEATS:
                    if not same(models[nm].predict(row[FEATS[nm]]), fr_["p_" + nm].to_numpy()).all():
                        predbad = True
                key = {"trunc": "trunc", "corrupt": "corrupt", "control": "control"}[vn]
                if bad:
                    R[f"{key}_feature_mismatch"] += 1
                    if vn != "control":
                        for f in bad:
                            R["bad_features"][f] = R["bad_features"].get(f, 0) + 1
                if predbad:
                    R[f"{key}_pred_mismatch"] += 1
            R["rows"] += 1
    print("presence", R, round(time.time() - t0, 1), flush=True)

    # ---- (2) side R8c, single-fill calls of the rule's own side_state_machine
    import cl_source
    cl_source.CLDIR = EXC / "cl"
    clv_all = {}
    from r2_metrics import chainlink_series, ptb_of
    clv_all, _ = chainlink_series()
    ptb = ptb_of(w)
    pick = rng.choice(len(mk), size=min(300, len(mk)), replace=False)
    sres = {"n": 0, "trunc_mismatch": 0, "corrupt_mismatch": 0, "control_mismatch": 0, "no_decision": 0}
    tok2cid = {**dict(zip(w.up_token, w.cid)), **dict(zip(w.down_token, w.cid))}
    for k in pick:
        f1 = mk.iloc[[k]]
        cid = tok2cid.get(str(f1["token_id"].iloc[0]))
        b = int(f1["ts"].iloc[0])
        w1 = w[w["cid"] == cid]
        c1 = clean[clean["cid"] == cid]
        s0 = int(w1["start_ts"].iloc[0])
        ok = (sec_all >= s0 - 7200) & (sec_all < s0 + 400)
        sec, px = sec_all[ok], px_all[ok]

        def run(cl_tape, sp_sec, sp_px, cl_vals):
            o = side_sm.side_state_machine(f1, mk[mk["token_id"].isin(set(w1.up_token) | set(w1.down_token))], w1, cl_tape,
                                           Spot(sp_sec, sp_px), {}, CLUSTER, ptb=ptb, cl_values=lambda s: cl_vals)
            return o.get("r8c_no_own_state") if o.get("n") else None
        full = run(c1, sec, px, clv_all)
        if full is None:
            sres["no_decision"] += 1
            continue
        sres["n"] += 1
        tr_cl = {s: v for s, v in clv_all.items() if s <= b - 4}
        ks = sec < b - 2
        trunc = run(c1[c1["ts"] <= b - 3], sec[ks], px[ks], tr_cl)
        pxc = px.copy()
        j = np.nonzero(sec >= b - 2)[0]
        if len(j):
            pxc[j] = px[j[0] - 1] * np.exp(np.cumsum(rng.normal(0, 3e-4, len(j))))
        co_cl = {s: (v if s <= b - 4 else v * (1 + rng.normal(0, 0.01))) for s, v in clv_all.items()}
        corr = run(corrupt_tape(c1, b - 3, rng, keep_le=True), sec, pxc, co_cl)
        ctrl = run(c1[c1["ts"] <= b - 4], sec[ks], px[ks], tr_cl)
        sres["trunc_mismatch"] += int(trunc != full)
        sres["corrupt_mismatch"] += int(corr != full)
        sres["control_mismatch"] += int(ctrl != full)
    res["side_r8c"] = sres
    print("side", sres, round(time.time() - t0, 1), flush=True)

    # ---- (3) price, block clock
    upset = set(w.up_token)
    c2 = clean.merge(w[["cid", "up_token"]], on="cid")
    c2["up_px"] = np.where(c2["asset"].astype(str) == c2["up_token"], c2["price"], 1 - c2["price"])
    by = {c: g.sort_values("ts", kind="stable") for c, g in c2.groupby("cid")}
    pres_ = {"n": 0, "trunc_mismatch": 0, "corrupt_mismatch": 0}
    for k in pick:
        r = mk.iloc[k]
        g = by.get(tok2cid.get(str(r.token_id)))
        if g is None:
            continue
        b = int(r.ts)

        def pred(gg):
            ts_, pu = gg["ts"].to_numpy(), gg["up_px"].to_numpy()
            i = np.searchsorted(ts_, b, side="left") - 1
            return None if i < 0 else round((pu[i] if str(r.token_id) in upset else 1 - pu[i]) - 0.01, 2)
        f = pred(g)
        if f is None:
            continue
        pres_["n"] += 1
        pres_["trunc_mismatch"] += int(pred(g[g["ts"] < b]) != f)
        gc = g.copy()
        m = gc["ts"] >= b
        gc.loc[m, "up_px"] = rng.uniform(0.01, 0.99, int(m.sum()))
        pres_["corrupt_mismatch"] += int(pred(gc) != f)
    res["price_block_clock"] = pres_

    # ---- (4) selection print features
    sel = {"n": 0, "dq_last_mismatch": 0, "fair_p_mismatch": 0}
    tes = sorted(EV.glob("sel_te_*.parquet"))
    if tes:
        te = pd.concat([pd.read_parquet(f) for f in tes], ignore_index=True)
        sp_full = Spot(sec_all, px_all)
        mk_tx = set(pd.read_pickle(EV / "sel_mk_tx.pkl"))
        tk = pd.concat([pd.read_parquet(f) for f in EV.glob("sel_tk_*.parquet")], ignore_index=True)
        tk = tk[~tk["wallet"].str.lower().isin(set(CLUSTER))]
        tk = tk.merge(w[["cid", "up_token"]], on="cid")
        tk["up_px"] = np.where(tk["asset"].astype(str) == tk["up_token"], tk["price"], 1 - tk["price"])
        tk["cleanp"] = ~tk["tx"].isin(mk_tx)
        byt = {c: g.sort_values("ts", kind="stable") for c, g in tk.groupby("cid")}
        for k in rng.choice(len(te), size=min(300, len(te)), replace=False):
            r = te.iloc[k]
            g = byt.get(r["cid"])
            if g is None:
                continue
            g = g[(g["ts"] < r["ts"]) & g["cleanp"]]  # truncated at the print
            lu = g["up_px"].to_numpy()[-1] if len(g) else np.nan
            ls = lu if r["side_up"] == 1 else 1 - lu
            dq = np.float32(r["q"] - ls)
            ks = sec_all < int(r["ts"]) - 2
            f, _ = fair_up(Spot(sec_all[ks], px_all[ks]), np.array([r["start_ts"]]), np.array([r["end_ts"]]), np.array([r["ts"] - 2]))
            fp = np.float32(f[0] if r["side_up"] == 1 else 1 - f[0])
            sel["n"] += 1
            sel["dq_last_mismatch"] += int(not same([dq], [r["dq_last"]])[0])
            sel["fair_p_mismatch"] += int(not (abs(float(fp) - float(r["fair_p"])) < 1e-5 or (np.isnan(fp) and np.isnan(r["fair_p"]))))
        del sp_full
    res["selection_print_features"] = sel
    res["secs"] = round(time.time() - t0, 1)
    (RES / "exam_r2_truncation.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
