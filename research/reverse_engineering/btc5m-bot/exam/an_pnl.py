"""Examiner r1: independent re-implementation of the frozen PnL rule (exposure tracker, target mix14 = the flow the frozen code built,
saved by run_eval.py as trk.npz flow3_a) on the h1 lot, with strict fills against other traders' taker BUY prints, plus:
  - conventions: (a) the RE's [s+1, s+3] (info horizon s-1); (slack) [s+3, s+5]: a print stamped T may have matched at T-2, so only
    prints stamped >= s+3 are guaranteed >= 2 s after the information horizon (latency >= 2 s with block-time slack 2 s);
  - capture 1.0 (frozen) and 0.5;
  - per-window rule PnL vs the wallets' per-window PnL (pooled and per wallet; Pearson, Spearman), per half, 2-h block bootstrap CI,
    a rotation null (2,000+ draws, circular shifts of the rule's window series by >= 12 windows) with one-sided p;
  - the rule's return before rebates and with a 50% fee rebate, p-values (2-h block bootstrap and HAC t over 2-h block sums);
  - the wallets' own return on the same windows (before rebates; with the 50% taker-fee rebate).
Usage: python an_pnl.py OUT_JSON"""
import os, sys, json, glob, time
ARGS = sys.argv[1:]
ROOT = os.getcwd()
import numpy as np, pandas as pd
from scipy import stats

EX = f"{ROOT}/.cache/exam/btc5m-bot"; AN = f"{EX}/an"; os.makedirs(AN, exist_ok=True)
LOT = [(1792713600, 1792800000), (1792886400, 1792972800), (1793059200, 1793145600), (1793232000, 1793318400)]
CUT = 1793059200
WAL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
LOTSZ, SLACK, FEE = 10.0, 0.02, 0.07
TAPES = f"{EX}/eval/tapes"


def chunks():
    out = []
    for p in sorted(glob.glob(f"{EX}/chunks/*_*/evaluate.json")):
        a, b = map(int, os.path.basename(os.path.dirname(p)).split("_"))
        if any(x <= a < y for x, y in LOT) or os.environ.get("EXAM_TEST"):
            out.append((a, b, os.path.dirname(p)))
    return out


def tracker(cid, rel, flow, au, ad, prints, pay_up, lo, hi, step, capture):
    """one window; prints[o] = (rel, price, size) of eligible taker BUY prints on outcome o (True = Up), sorted by rel."""
    tgt = np.cumsum(flow); R = 0.0; nxt = -10**9; fills = []
    for i in range(len(rel)):
        s = rel[i]
        if s < nxt:
            continue
        d = tgt[i] - R
        if abs(d) < LOTSZ:
            continue
        o = bool(d > 0); a = au[i] if o else ad[i]
        if not (np.isfinite(a) and 0.05 < a < 0.95):
            continue
        lim = min(a + SLACK, 0.99); left = np.floor(abs(d) / LOTSZ) * LOTSZ
        Rr, Pp, Zz = prints[o]; pay = pay_up if o else 1 - pay_up
        for k in range(np.searchsorted(Rr, s + lo, "left"), np.searchsorted(Rr, s + hi, "right")):
            if Pp[k] <= lim + 1e-9:
                sh = min(left, capture * Zz[k]); left -= sh
                if sh > 0:
                    fills.append((Pp[k], sh, sh * (pay - Pp[k]) - FEE * Pp[k] * (1 - Pp[k]) * sh, o))
                    R += sh if o else -sh
                if left <= 1e-9:
                    break
        nxt = s + step
    return fills


def run():
    rows_w, rows_f = [], []
    CONV = {"a": (1, 3, 4), "slack": (3, 5, 6)}
    for a, b, d in chunks():
        win = pd.read_parquet(f"{d}/windows_all.parquet")
        win = win[(win.start_ts >= a) & (win.start_ts < b) & win.up_payout.notna()]
        fills = pd.read_parquet(f"{d}/fills.parquet")
        c = pd.read_parquet(f"{d}/cells.parquet", columns=["cid", "is_up", "rel", "ask_o"])
        up = c[c.is_up].sort_values(["cid", "rel"]).reset_index(drop=True); dn = c[~c.is_up].sort_values(["cid", "rel"]).reset_index(drop=True)
        T = np.load(f"{d}/trk.npz"); keys = sorted(T.files, key=lambda k: int(k[4:].split("_")[0]))
        flows = {k: T[k] for k in keys}
        mix = [k for k in keys if k.startswith("flow3_")]
        flow = flows[mix[0]] if mix else flows[keys[0]]
        src = mix[0] if mix else keys[0]
        mk_tx = set(fills.loc[fills.role == "M", "tx"].str.lower())
        ucid = up.cid.to_numpy(); urel = up.rel.to_numpy().astype(np.int64); au = up.ask_o.to_numpy(float); ad = dn.ask_o.to_numpy(float)
        bounds = np.r_[0, np.flatnonzero(ucid[1:] != ucid[:-1]) + 1, len(ucid)]
        wi = win.set_index("cid")
        fw = fills.assign(pay=np.where(fills.is_up, fills.up_payout, 1 - fills.up_payout))
        fw["pnl"] = fw.shares * (fw.pay - fw.price) - fw.fee_usd
        for j in range(len(bounds) - 1):
            i0, i1 = bounds[j], bounds[j + 1]; cid = ucid[i0]
            if cid not in wi.index:
                continue
            st0 = int(wi.at[cid, "start_ts"]); pu = float(wi.at[cid, "up_payout"])
            tp = f"{TAPES}/{cid}.parquet"
            P = {True: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0)), False: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0))}
            ntape = 0
            if os.path.exists(tp):
                t = pd.read_parquet(tp)
                if len(t) and "side" in t:
                    t = t[(t.side == "BUY") & ~t.proxyWallet.str.lower().isin(WAL) & ~t.transactionHash.str.lower().isin(mk_tx)]
                    t = t.assign(rel=t.timestamp - st0, up=(t.outcome == "Up")); ntape = len(t)
                    for o in (True, False):
                        q = t[t.up == o].sort_values("rel", kind="stable")
                        P[o] = (q.rel.to_numpy(np.int64), q.price.to_numpy(float), q["size"].to_numpy(float))
            ww = fw[fw.cid == cid]
            rec = {"cid": cid, "start_ts": st0, "pay_up": pu, "ntape": ntape, "wallet_pnl": float(ww.pnl.sum()), "wallet_usd": float(ww.usdc.sum()),
                   "wallet_fee": float(ww.fee_usd.sum()), "wallet_taker_fee": float(ww[ww.role == "T"].fee_usd.sum()), "flow_src": src}
            for w in ("GF", "XM", "DS"):
                x = ww[ww.wallet == w]
                rec[f"pnl_{w}"] = float(x.pnl.sum()); rec[f"usd_{w}"] = float(x.usdc.sum()); rec[f"tfee_{w}"] = float(x[x.role == "T"].fee_usd.sum())
            for cv, (lo, hi, step) in CONV.items():
                for cap in (1.0, 0.5):
                    F = tracker(cid, urel[i0:i1], np.nan_to_num(flow[i0:i1].astype(float)), au[i0:i1], ad[i0:i1], P, pu, lo, hi, step, cap)
                    nm = f"{cv}_c{cap}"
                    rec[f"rule_pnl_{nm}"] = float(sum(x[2] for x in F)); rec[f"rule_usd_{nm}"] = float(sum(x[0] * x[1] for x in F))
                    rec[f"rule_fee_{nm}"] = float(sum(FEE * x[0] * (1 - x[0]) * x[1] for x in F)); rec[f"rule_fills_{nm}"] = len(F)
            rows_w.append(rec)
        print("pnl chunk", a, b, len(rows_w), flush=True)
    return pd.DataFrame(rows_w)


def corr2(x, y):
    return [round(float(np.corrcoef(x, y)[0, 1]), 4), round(float(stats.spearmanr(x, y).correlation), 4)]


def rot_null(x, y, n=4000, seed=5, min_shift=12):
    obs = np.corrcoef(x, y)[0, 1]; obs_s = stats.spearmanr(x, y).correlation
    rng = np.random.default_rng(seed); N = len(x); v, vs = [], []; min_shift = min(min_shift, max(1, N // 4))
    ry = stats.rankdata(y); rx = stats.rankdata(x)
    for _ in range(n):
        k = int(rng.integers(min_shift, N - min_shift))
        v.append(np.corrcoef(np.roll(x, k), y)[0, 1]); vs.append(np.corrcoef(np.roll(rx, k), ry)[0, 1])
    v, vs = np.array(v), np.array(vs)
    return {"pearson_p": round(float(((v >= obs).sum() + 1) / (n + 1)), 5), "spearman_p": round(float(((vs >= obs_s).sum() + 1) / (n + 1)), 5),
            "null_pearson_mean_sd": [round(float(v.mean()), 4), round(float(v.std()), 4)], "draws": n}


def block_boot_corr(x, y, blocks, n=2000, seed=12):
    ub = np.unique(blocks); idx = {u: np.where(blocks == u)[0] for u in ub}; rng = np.random.default_rng(seed); bp, bs = [], []
    for _ in range(n):
        ii = np.concatenate([idx[u] for u in rng.choice(ub, len(ub))])
        bp.append(np.corrcoef(x[ii], y[ii])[0, 1]); bs.append(stats.spearmanr(x[ii], y[ii]).correlation)
    return {"pearson_ci95": [round(float(np.nanquantile(bp, 0.025)), 4), round(float(np.nanquantile(bp, 0.975)), 4)],
            "spearman_ci95": [round(float(np.nanquantile(bs, 0.025)), 4), round(float(np.nanquantile(bs, 0.975)), 4)]}


def ret_test(pnl, usd, blocks, n=4000, seed=13):
    """return = sum pnl / sum usd; one-sided p of return <= 0 by 2-h block bootstrap, and HAC-free t over block sums."""
    ub = np.unique(blocks); P = np.array([pnl[blocks == u].sum() for u in ub]); U = np.array([usd[blocks == u].sum() for u in ub])
    rng = np.random.default_rng(seed); bs = []
    for _ in range(n):
        k = rng.integers(0, len(ub), len(ub)); bs.append(P[k].sum() / max(U[k].sum(), 1e-9))
    bs = np.array(bs); t = P.mean() / (P.std(ddof=1) / np.sqrt(len(P))) if P.std() > 0 else np.nan
    return {"return": round(float(P.sum() / max(U.sum(), 1e-9)), 5), "pnl": round(float(P.sum()), 1), "usd": round(float(U.sum()), 1),
            "p_return_le_0_block_bootstrap": round(float((bs <= 0).mean()), 5), "ci95": [round(float(np.quantile(bs, 0.025)), 5), round(float(np.quantile(bs, 0.975)), 5)],
            "t_block_sums": round(float(t), 3), "p_t_one_sided_gt_0": round(float(stats.t.sf(t, len(P) - 1)), 5) if np.isfinite(t) else None, "blocks": int(len(ub))}


def main(out_json):
    t0 = time.time()
    W = run(); W.to_parquet(f"{AN}/pnl_windows.parquet", index=False)
    W = W.sort_values("start_ts").reset_index(drop=True)
    blocks = W.start_ts.to_numpy() // 7200; half = W.start_ts.to_numpy() < CUT
    res = {"windows": int(len(W)), "flow_source": W.flow_src.value_counts().to_dict(), "windows_without_tape": int((W.ntape == 0).sum())}
    for nm in ("a_c1.0", "a_c0.5", "slack_c1.0", "slack_c0.5"):
        x = W[f"rule_pnl_{nm}"].to_numpy()
        r = {"fills": int(W[f"rule_fills_{nm}"].sum()), "pooled": corr2(x, W.wallet_pnl.to_numpy()),
             "halves": [corr2(x[m], W.wallet_pnl.to_numpy()[m]) for m in (half, ~half)],
             "by_wallet": {w: corr2(x, W[f"pnl_{w}"].to_numpy()) for w in ("GF", "XM", "DS")},
             "by_wallet_halves": {w: [corr2(x[m], W[f"pnl_{w}"].to_numpy()[m]) for m in (half, ~half)] for w in ("GF", "XM", "DS")}}
        if nm in ("a_c1.0", "slack_c1.0"):
            r["rotation_null"] = rot_null(x, W.wallet_pnl.to_numpy())
            r["block_bootstrap"] = block_boot_corr(x, W.wallet_pnl.to_numpy(), blocks)
            r["rotation_null_by_wallet"] = {w: rot_null(x, W[f"pnl_{w}"].to_numpy(), n=2000) for w in ("GF", "XM", "DS")}
        usd = W[f"rule_usd_{nm}"].to_numpy(); fee = W[f"rule_fee_{nm}"].to_numpy()
        r["return_before_rebates"] = ret_test(x, usd, blocks)
        r["return_with_50pct_fee_rebate"] = ret_test(x + 0.5 * fee, usd, blocks)
        r["return_halves_before_rebates"] = [ret_test(x[m], usd[m], blocks[m]) for m in (half, ~half)]
        res[nm] = r
        print(nm, r["pooled"], r["return_before_rebates"]["return"], round(time.time() - t0), flush=True)
    wp = W.wallet_pnl.to_numpy(); wu = W.wallet_usd.to_numpy(); wf = W.wallet_taker_fee.to_numpy()
    res["wallet_own"] = {"pooled_before_rebates": ret_test(wp, wu, blocks), "pooled_with_50pct_taker_fee_rebate": ret_test(wp + 0.5 * wf, wu, blocks),
                         "halves_before_rebates": [ret_test(wp[m], wu[m], blocks[m]) for m in (half, ~half)],
                         "by_wallet": {w: {"before_rebates": ret_test(W[f"pnl_{w}"].to_numpy(), W[f"usd_{w}"].to_numpy(), blocks),
                                           "with_50pct_taker_fee_rebate": ret_test(W[f"pnl_{w}"].to_numpy() + 0.5 * W[f"tfee_{w}"].to_numpy(), W[f"usd_{w}"].to_numpy(), blocks)}
                                       for w in ("GF", "XM", "DS")},
                         "by_day_before_rebates": {time.strftime("%Y-%m-%d", time.gmtime(a)): round(float(wp[(W.start_ts >= a) & (W.start_ts < b)].sum()), 1) for a, b in LOT},
                         "by_day_taker_fees": {time.strftime("%Y-%m-%d", time.gmtime(a)): round(float(wf[(W.start_ts >= a) & (W.start_ts < b)].sum()), 1) for a, b in LOT}}
    res["rule_by_day_a_c1.0"] = {time.strftime("%Y-%m-%d", time.gmtime(a)): ret_test(W["rule_pnl_a_c1.0"].to_numpy()[(W.start_ts >= a) & (W.start_ts < b)],
                                                                                  W["rule_usd_a_c1.0"].to_numpy()[(W.start_ts >= a) & (W.start_ts < b)],
                                                                                  blocks[(W.start_ts >= a) & (W.start_ts < b)]) for a, b in LOT}
    res["elapsed_s"] = round(time.time() - t0)
    json.dump(res, open(out_json, "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main(ARGS[0])
