"""Iteration 12, PR12-C (X120 mechanics P2 / X122 mechanics P4: typed orders) and PR12-B (X125 assumptions P2: the band).

Per lot BTC 5m maker BUY fill (it9/volhist_{study,validate}: block second b, token, mid_up at b - 3, Binance v300), joined
to its calldata order (b1_cluster_orders_*: salt, original size, limit), with
  * the real-Chainlink posture (code11/side_inblock.py inputs: T_hat from the taker's signing ms, Chainlink value stamped
    floor((T_hat - 1432) / 1000) from the detached fetch, Gamma strike, 1.4 x v300, mid = last clean print at b - 3) and the
    Binance stand-in posture (volhist S, K) for every fill;
  * the wallet's own inventory in the window before the fill's block second (activity BUY rows, maker + taker);
  * the clean taker net demand for Up over the 30 s before b (code11/entry_flow.py definition).
Types (frozen in NOTES PR12-C before scoring): pairing (original size not a schedule size, within 2% of |own imbalance|,
on the under-held outcome) > deep (limit <= 0.10) > near (|limit - (in-block anchor - 0.01)| <= 0.01) / far (deeper) /
above. Scores per fill and per order (first fill of the order), STUDY case by case and VALIDATE as aggregates.
Band (PR12-B): |e| = |fair_up - mid_up| > h -> posture; else an inside rule (cheaper token or the 30-s taker-flow
complement); (h, inside rule) chosen on STUDY by per-fill accuracy, scored on VALIDATE against the posture on the same fills.
    python code12/typed_side.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import cl_source  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
ADDR = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
        "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
STD = {500, 1000, 250, 125, 100, 62, 50, 12, 300, 40, 200, 2000, 25, 31, 20, 10, 5}
SPLIT_V, HALF_V = 1793059200, 1793232000


def that(sign_ms, bms):
    sign_ms = np.asarray(sign_ms, dtype=float)
    bms = np.asarray(bms, dtype=float)
    ok = np.isfinite(sign_ms) & (sign_ms > 0) & (bms - sign_ms < 60000) & (bms - sign_ms > -1000)
    return np.where(ok, np.clip(np.nan_to_num(sign_ms) + 620, bms - 3000, bms - 1500), bms - 2285)


def load_act():
    acts = []
    for w in ADDR.values():
        a = pd.read_parquet(C / f"exam/activity_{w}.parquet", columns=["timestamp", "type", "side", "outcome", "size", "slug"])
        a["wallet"] = w
        acts.append(a)
    A = pd.concat(acts)
    A = A[(A.type == "TRADE") & (A.side == "BUY") & A.slug.str.contains("btc-updown-5m-", na=False)].copy()
    A["st"] = A.slug.str.split("-").str[-1].astype(int)
    A["isup"] = A.outcome == "Up"
    return A.sort_values("timestamp")


def build():
    ptb = pd.read_parquet(C / "cl/ptb_lot.parquet")
    Kg = dict(zip(ptb.start_ts.astype(int), ptb.ptb.astype(float)))
    clv = cl_source._cache()
    IB = pd.read_parquet(C / "it11" / "inblock_scored_all.parquet")
    IB["txh"] = IB.txh.str.lower()
    IB = IB.drop_duplicates(["txh", "token"]).set_index(["txh", "token"])
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet").set_index("cid")
    A = load_act()
    G = {k: (g.timestamp.to_numpy(), np.cumsum(np.where(g.isup, g["size"], 0.0)), np.cumsum(np.where(g.isup, 0.0, g["size"])))
         for k, g in A.groupby(["wallet", "st"])}
    F = pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["txh"])
    cl_tx = set(F.txh.str.lower())
    for n in ADDR.values():
        cl_tx |= set(pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["transactionHash"]).transactionHash.str.lower())
    frames = []
    for sp, fn in (("study", "b1_takers_study"), ("validate", "b1_takers_valid")):
        v = pd.read_parquet(C / f"it9/volhist_{sp}.parquet", columns=["cid", "txh", "wallet", "b", "st", "en", "is_up", "price", "shares",
                                                                        "mid_up", "v300", "token", "S", "K", "tau"])
        t = pd.read_parquet(C / f"{fn}.parquet", columns=["tx", "sign_ms"])
        t["tx"] = t.tx.str.lower()
        t = t.drop_duplicates("tx").set_index("tx")
        v["txh"] = v.txh.str.lower()
        v["w"] = v.wallet.str.lower().map(ADDR)
        v["T_hat"] = that(v.txh.map(t.sign_ms), v.b.astype(float) * 1000)
        v["cl"] = ((v.T_hat - 1432) // 1000).astype(np.int64).map(lambda s: clv.get(int(s), np.nan))
        v["Kg"] = v.st.map(Kg)
        v["tau_cl"] = np.maximum(v.en - v.T_hat / 1000.0, 1.0)
        key = list(zip(v.txh, v.token.astype(str)))
        a_in = IB["a_in"].reindex(key).to_numpy()
        v["a_tok"] = a_in  # inblock_scored_all a_in is already in the fill token's terms (side_inblock: mid_up = a_in if Up else 1 - a_in)
        o = pd.read_parquet(C / f"b1_cluster_orders_{'study' if sp == 'study' else 'valid'}.parquet",
                            columns=["salt", "w", "token_id", "taker_amount", "lim", "tx", "bts"])
        o["tx"] = o.tx.str.lower()
        o["token_id"] = o.token_id.astype(str)
        o = o.drop_duplicates(["tx", "w", "token_id"])
        v["token"] = v.token.astype(str)
        v = v.merge(o, left_on=["txh", "w", "token"], right_on=["tx", "w", "token_id"], how="left")
        v["orig"] = (v.taker_amount / 1e6).round(2)
        v["oid"] = v.w + ":" + v.salt.astype(str)
        first_b = v.groupby("oid").b.transform("min")
        v["first_b"] = first_b
        # own inventory before the fill's block second and before the order's first fill second
        inv_fill, inv_first = [], []
        for r in v[["w", "st", "b", "first_b"]].itertuples(index=False):
            g = G.get((r.w, int(r.st)))
            if g is None:
                inv_fill.append(0.0)
                inv_first.append(0.0)
                continue
            ts, cu, cd = g
            i = np.searchsorted(ts, r.b, side="left") - 1
            j = np.searchsorted(ts, r.first_b, side="left") - 1
            inv_fill.append(float(cu[i] - cd[i]) if i >= 0 else 0.0)
            inv_first.append(float(cu[j] - cd[j]) if j >= 0 else 0.0)
        v["inv"] = inv_fill
        v["inv_first"] = inv_first
        v["sp"] = sp
        frames.append(v)
    V = pd.concat(frames, ignore_index=True)
    # 30-s clean taker net demand for Up before b
    V["d30"] = 0.0
    days = sorted(set((W.start_ts // 86400 * 86400).astype(int)))
    for day in days:
        T = pd.read_parquet(C / "exam" / f"taker5m_day_{day}.parquet", columns=["cid", "ts", "side", "asset", "size", "tx"])
        T = T[~T.tx.str.lower().isin(cl_tx) & T.cid.isin(set(V.cid))]
        for cid, g in T.groupby("cid"):
            m = (V.cid == cid).to_numpy()
            if not m.any() or cid not in W.index:
                continue
            up = str(W.at[cid, "up_token"])
            g = g.sort_values("ts")
            isu = g.asset.astype(str).to_numpy() == up
            buy = g.side.to_numpy() == "BUY"
            dem = np.where(buy == isu, 1.0, -1.0) * g["size"].to_numpy(float)
            ts = g.ts.to_numpy()
            cs = np.concatenate([[0.0], np.cumsum(dem)])
            bb = V.loc[m, "b"].to_numpy()
            V.loc[m, "d30"] = cs[np.searchsorted(ts, bb, side="left")] - cs[np.searchsorted(ts, bb - 30, side="left")]
    # postures
    x = np.log(V.cl / V.Kg)
    V["f_cl"] = norm.cdf(x / (1.4 * V.v300 * np.sqrt(V.tau_cl)))
    V["f_bn"] = norm.cdf(np.log(V.S / V.K) / (1.4 * V.v300 * np.sqrt(np.maximum(V.tau, 1.0))))
    V["x_cl"] = x
    V["day"] = (V.b // 86400 * 86400).astype(int)
    V.to_parquet(C / "it12" / "typed_fills.parquet")
    return V


def types(V):
    imb = V.inv_first.abs()
    under_up = V.inv_first < 0  # holds more Down -> Up is under-held
    is_pair = (~V.orig.isin(STD)) & (imb > 0) & ((V.orig - imb).abs() <= 0.02 * imb) & ((V.is_up == 1) == under_up)
    deep = V.lim <= 0.10 + 1e-9
    pred = V.a_tok - 0.01
    near = (V.lim - pred).abs() <= 0.0101
    far = V.lim < pred - 0.0101
    t = np.where(is_pair, "pairing", np.where(deep, "deep", np.where(near, "near", np.where(far, "far", np.where(V.a_tok.isna(), "noanchor", "above")))))
    return pd.Series(t, index=V.index)


def acc(pred_up, y_up, m):
    m = m & np.isfinite(pred_up)
    return (round(float((pred_up[m] == y_up[m]).mean()), 4) if m.any() else None), int(m.sum())


def score(V):
    V = V.copy()
    V["type"] = types(V)
    y = (V.is_up == 1).to_numpy()
    mid = V.mid_up.to_numpy()
    p_cl = np.where(np.isfinite(V.f_cl) & np.isfinite(mid), (V.f_cl > mid).astype(float), np.nan)
    p_bn = np.where(np.isfinite(V.f_bn) & np.isfinite(mid), (V.f_bn > mid).astype(float), np.nan)
    cheaper = np.where(np.isfinite(mid), (mid < 0.5).astype(float), np.nan)
    held = np.where(V.inv != 0, (V.inv > 0).astype(float), np.nan)
    under = np.where(V.inv != 0, (V.inv < 0).astype(float), np.nan)
    flowc = np.where(V.d30 != 0, (V.d30 < 0).astype(float), np.nan)
    rules = {"posture_cl": p_cl, "posture_bn": p_bn, "cheaper": cheaper, "own_held": held, "own_under": under, "flow30_complement": flowc}
    first = (V.b == V.first_b).to_numpy() & ~V.duplicated("oid").to_numpy()
    out = {}
    for sp in ("study", "validate"):
        ms = (V.sp == sp).to_numpy()
        rec = {"n_fills": int(ms.sum()), "n_orders": int((ms & first).sum())}
        tshare = V[ms].type.value_counts(normalize=True).round(4).to_dict()
        tshare_o = V[ms & first].type.value_counts(normalize=True).round(4).to_dict()
        rec["type_share_fills"] = tshare
        rec["type_share_orders"] = tshare_o
        for ty in ["ALL", "near", "far", "deep", "pairing", "above", "noanchor"]:
            mt = ms & ((V.type == ty).to_numpy() if ty != "ALL" else True)
            r2 = {}
            for rn, pr in rules.items():
                r2[rn] = {"fill": acc(pr, y, mt), "order": acc(pr, y, mt & first)}
            rec[ty] = r2
        # posture by day (STUDY days individually, VALIDATE days as daily aggregates), near only and all
        byday = {}
        for d, g in V[ms].groupby("day"):
            md = ms & (V.day == d).to_numpy()
            byday[str(pd.to_datetime(d, unit="s").date())] = {
                "all_cl": acc(p_cl, y, md)[0], "near_cl": acc(p_cl, y, md & (V.type == "near").to_numpy())[0],
                "all_bn": acc(p_bn, y, md)[0], "near_bn": acc(p_bn, y, md & (V.type == "near").to_numpy())[0],
                "near_share": round(float((V.type[md] == "near").mean()), 3), "deep_share": round(float((V.type[md] == "deep").mean()), 3),
                "pair_share": round(float((V.type[md] == "pairing").mean()), 3),
                "fav_share": round(float((V.price[md] > 0.5).mean()), 3),
                "fav_share_near": round(float((V.price[md & (V.type == 'near').to_numpy()] > 0.5).mean()), 3)}
        rec["by_day"] = byday
        # de-duplicated decisions (window, token, block second), posture on near rungs
        dd = V[ms].drop_duplicates(["cid", "token", "b"])
        mdd = V.index.isin(dd.index)
        rec["dedup_all_cl"] = acc(p_cl, y, ms & mdd)
        rec["dedup_near_cl"] = acc(p_cl, y, ms & mdd & (V.type == "near").to_numpy())
        out[sp] = rec
    # band (PR12-B) on fills with the real Chainlink posture
    e = np.abs(V.f_cl.to_numpy() - mid)
    band = {}
    for sp in ("study", "validate"):
        ms = (V.sp == sp).to_numpy() & np.isfinite(p_cl)
        bres = {"posture": acc(p_cl, y, ms)}
        for h in (0.01, 0.02, 0.03, 0.05, 0.07, 0.10):
            inside = e <= h
            for nm, ins in (("cheaper", cheaper), ("flow", flowc)):
                pr = np.where(inside, ins, p_cl)
                pr = np.where(np.isfinite(pr), pr, p_cl)
                bres[f"h{h}_{nm}"] = acc(pr, y, ms)
            bres[f"h{h}_outside_posture"] = acc(p_cl, y, ms & ~inside)
            bres[f"h{h}_inside_share"] = round(float(inside[ms].mean()), 4)
        band[sp] = bres
    st_scores = {k: v[0] for k, v in band["study"].items() if k.startswith("h") and ("cheaper" in k or "flow" in k)}
    best = max(st_scores, key=lambda k: st_scores[k])
    hb, nm = float(best.split("_")[0][1:]), best.split("_")[1]
    ms = (V.sp == "validate").to_numpy() & np.isfinite(p_cl)
    inside = e <= hb
    ins = cheaper if nm == "cheaper" else flowc
    pr = np.where(inside, ins, p_cl)
    pr = np.where(np.isfinite(pr), pr, p_cl)
    a = (pr == y).astype(float)
    bb = (p_cl == y).astype(float)
    blk = (V.b // 7200).to_numpy()
    idx = np.nonzero(ms)[0]
    ub = np.unique(blk[idx])
    bi = {u: idx[blk[idx] == u] for u in ub}
    rng = np.random.default_rng(12)
    gs = []
    for _ in range(2000):
        ii = np.concatenate([bi[u] for u in rng.choice(ub, len(ub), replace=True)])
        gs.append(a[ii].mean() - bb[ii].mean())
    band["chosen_on_study"] = best
    band["validate_chosen"] = round(float(a[ms].mean()), 4)
    band["validate_posture"] = round(float(bb[ms].mean()), 4)
    band["validate_gain_ci95"] = [round(float(np.percentile(gs, 2.5)), 4), round(float(np.percentile(gs, 97.5)), 4)]
    band["adopt"] = bool(band["validate_chosen"] - band["validate_posture"] >= 0.02 and band["validate_gain_ci95"][0] > 0)
    # outside-band posture by day at the chosen h (E4 signature: >= 0.85 every day)
    obd = {}
    for d in sorted(V.day.unique()):
        md = (V.day == d).to_numpy() & np.isfinite(p_cl) & ~inside
        obd[str(pd.to_datetime(d, unit="s").date())] = acc(p_cl, y, md)
    band["outside_posture_by_day"] = obd
    out["band"] = band
    return out


def main():
    f = C / "it12" / "typed_fills.parquet"
    V = pd.read_parquet(f) if (len(sys.argv) > 1 and sys.argv[1] == "cached" and f.exists()) else build()
    out = score(V)
    (HERE.parent / "results" / "iter12_typed_side.json").write_text(json.dumps(out, indent=1, default=str))
    for sp in ("study", "validate"):
        r = out[sp]
        print(sp, r["n_fills"], r["n_orders"], "types", r["type_share_fills"])
        for ty in ["ALL", "near", "far", "deep", "pairing", "above"]:
            rr = r[ty]
            print("  ", ty, {k: (v["fill"], v["order"][0]) for k, v in rr.items()})
        print("   dedup", r["dedup_all_cl"], r["dedup_near_cl"])
    b = out["band"]
    print("band study", {k: v for k, v in b["study"].items() if "outside" not in k and "share" not in k})
    print("band chosen", b["chosen_on_study"], "VAL", b["validate_chosen"], "vs", b["validate_posture"], b["validate_gain_ci95"], "adopt", b["adopt"])


if __name__ == "__main__":
    main()
