"""Examiner round 2: strict-fill replay of the executable rule on lot f1 (my own implementation of the conventions of
EXAM_r1 / code11/replay.py), per-window PnL vs the cluster's, significance, per half and per wallet.

Decision second d in [st + 1, en - 30): mid = last clean Up print stamped <= d (prints in cluster transactions removed).
Side variants:
  'r8c'      : the counted public side R8c at d: decided window (|mid - 0.5| > 0.4) -> the cheaper token (no NYSE-open window
               on this weekend lot); else the Chainlink posture (report stamped d - 2, Gamma priceToBeat, sigma = 1.4 x the
               300-s Binance 1-s vol at d - 2, tau = en - d); Binance stand-in where no report;
  're_exec'  : the reverse engineer's executable version (code11/replay.py 'posture'): Binance digital (S = second d - 2,
               K = mean Binance [st - 60, st), 1.4 x v300) vs mid.
Quote: BUY Q shares at quote_price(mid_s - 0.01) of the chosen outcome, live in (d + L, d + L + 1]; a print stamped T counts
at T - SLACK; fills only on trade-through (taker SELL of the token below q, or taker BUY of the complement above 1 - q);
fill per second = min(Q, through volume). L = 2 (also 5), SLACK = 2, Q = 62 (weekend: the rule's off-session size; also
500), no fees, no rebates. Flow: every taker print except the cluster's own taker rows ('full'; also 'clean').
Wallet: the cluster's maker BUY fills held to resolution, per window (labels from the examiner's activity fetch).
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import ndtr

from r2_common import CLUSTER, EXC, RES

from r2_metrics import chainlink_series, ptb_of  # noqa: E402

EV = EXC / "ev"
CUT = json.loads((RES / "exam_r2_step0.json").read_text())["cut_ts"]
STOP, SLACK = 30, 2


def quote_price(x):
    x = np.asarray(x, dtype=float)
    q01 = np.floor(x / 0.01 + 1e-9) * 0.01
    q001 = np.floor(x / 0.001 + 1e-9) * 0.001
    return np.where((q001 < 0.04) | (q001 > 0.96), q001, q01)


def rv300(px):
    lp = np.log(px)
    r = np.diff(lp, prepend=lp[0])
    cs = np.concatenate([[0.0], np.cumsum(r * r)])
    i = np.arange(len(r))
    lo = np.maximum(i + 1 - 300, 0)
    return np.sqrt((cs[i + 1] - cs[lo]) / np.maximum(i + 1 - lo, 1))


def corr2(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return [float("nan"), float("nan")]
    return [float(np.corrcoef(a, b)[0, 1]), float(stats.spearmanr(a, b).correlation)]


def perm_p(a, b, blocks, n=2000, seed=5):
    """One-sided p of Pearson and Spearman corr(a, b) > null, permuting a within 2-h blocks."""
    rng = np.random.default_rng(seed)
    obs = corr2(a, b)
    a = np.asarray(a, float)
    idx = [np.nonzero(blocks == u)[0] for u in np.unique(blocks)]
    cp, cs = 0, 0
    rb = stats.rankdata(b)
    for _ in range(n):
        aa = a.copy()
        for ii in idx:
            aa[ii] = a[rng.permutation(ii)]
        cp += np.corrcoef(aa, b)[0, 1] >= obs[0]
        cs += np.corrcoef(stats.rankdata(aa), rb)[0, 1] >= obs[1]
    return [(cp + 1) / (n + 1), (cs + 1) / (n + 1)]


def boot_ret(pnl, usd, blocks, n=2000, seed=9):
    rng = np.random.default_rng(seed)
    ub = np.unique(blocks)
    P = pd.Series(pnl).groupby(blocks).sum().reindex(ub).to_numpy()
    U = pd.Series(usd).groupby(blocks).sum().reindex(ub).to_numpy()
    r = []
    for _ in range(n):
        k = rng.integers(0, len(ub), len(ub))
        r.append(P[k].sum() / max(U[k].sum(), 1e-9))
    r = np.array(r)
    return float(np.mean(r <= 0)), [float(np.quantile(r, 0.025)), float(np.quantile(r, 0.975))]


def replay(w, tk, cl_tx, base, px, v3, cl, ptb, L, Q, side, flow, win_len):
    out = {}
    for win in w.itertuples(index=False):
        st, en, up_tok, pay_up = int(win.start_ts), int(win.end_ts), str(win.up_token), win.up_payout
        g = tk.get(win.cid)
        d = np.arange(st + 1, en - STOP)
        nd = len(d)
        if g is None or pay_up is None or not np.isfinite(pay_up) or st - 60 - base < 400 or en - base >= len(px):
            out[win.cid] = (0.0, 0.0, 0.0)
            continue
        ts = g["ts"].to_numpy(np.int64)
        is_up = g["asset"].astype(str).to_numpy() == up_tok
        sell = g["side"].astype(str).to_numpy() == "SELL"
        pr = g["price"].to_numpy(float)
        sz = g["size"].to_numpy(float)
        in_cl = g["tx"].isin(cl_tx).to_numpy()
        own_t = g["wallet"].astype(str).str.lower().isin(set(CLUSTER)).to_numpy()
        pu = np.where(is_up, pr, 1 - pr)
        cm = ~in_cl
        k = np.searchsorted(ts[cm], d, side="right") - 1
        mid = np.where(k >= 0, pu[cm][np.clip(k, 0, None)] if cm.any() else np.nan, np.nan)
        si = d - 2 - base
        sig = 1.4 * v3[si] * np.sqrt(np.maximum(en - d, 1))
        if side == "re_exec":
            K = float(px[st - 60 - base:st - base].mean())
            with np.errstate(divide="ignore", invalid="ignore"):
                f_up = ndtr(np.log(px[si] / K) / np.where(sig > 0, sig, np.nan))
            a_up, a_dn = f_up > mid, f_up < mid
        else:
            K = ptb.get(st, np.nan)
            c = np.array([cl.get(int(x), np.nan) for x in d - 2])
            Kb = float(px[st - 60 - base:st - base].mean())
            with np.errstate(divide="ignore", invalid="ignore"):
                f_cl = ndtr(np.log(c / K) / np.where(sig > 0, sig, np.nan))
                f_bn = ndtr(np.log(px[si] / Kb) / np.where(sig > 0, sig, np.nan))
            f = np.where(np.isfinite(f_cl), f_cl, f_bn)
            dec = np.abs(mid - 0.5) > 0.4
            a_up = np.where(dec, mid < 0.5, f > mid)
            a_dn = np.where(dec, mid > 0.5, f < mid)
        okm = np.isfinite(mid)
        a_up, a_dn = a_up & okm, a_dn & okm
        q_up, q_dn = quote_price(mid - 0.01), quote_price((1 - mid) - 0.01)
        a_up &= np.isfinite(q_up) & (q_up >= 0.001)
        a_dn &= np.isfinite(q_dn) & (q_dn >= 0.001)
        kk = ts - SLACK - L - 1 - (st + 1)
        fm = (kk >= 0) & (kk < nd) & ~own_t & (cm if flow == "clean" else True)
        kf, iuf, sef, prf, szf = kk[fm], is_up[fm], sell[fm], pr[fm], sz[fm]
        buf = ~sef
        qu, qd = q_up[kf], q_dn[kf]
        thr_up = (iuf & sef & (prf < qu - 1e-9)) | (~iuf & buf & (prf > 1 - qu + 1e-9))
        thr_dn = (~iuf & sef & (prf < qd - 1e-9)) | (iuf & buf & (prf > 1 - qd + 1e-9))
        vu = np.bincount(kf[thr_up], weights=szf[thr_up], minlength=nd)
        vd = np.bincount(kf[thr_dn], weights=szf[thr_dn], minlength=nd)
        fu = np.where(a_up, np.minimum(Q, vu), 0.0)
        fd = np.where(a_dn, np.minimum(Q, vd), 0.0)
        pnl = float((fu * (pay_up - np.nan_to_num(q_up))).sum() + (fd * ((1 - pay_up) - np.nan_to_num(q_dn))).sum())
        usd = float((fu * np.nan_to_num(q_up)).sum() + (fd * np.nan_to_num(q_dn)).sum())
        out[win.cid] = (pnl, usd, float(fu.sum() + fd.sum()))
    return out


def main():
    t0 = time.time()
    sp = pd.read_parquet(EV / "spot_btc.parquet").sort_values("sec")
    base = int(sp.sec.iloc[0])
    n = int(sp.sec.iloc[-1]) - base + 1
    px = np.full(n, np.nan)
    px[sp.sec.to_numpy() - base] = sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    v3 = rv300(px)
    cl, _ = chainlink_series()
    A = pd.read_parquet(EXC / "activity_f1_all.parquet")
    cl_tx = set(int(str(h)[2:17], 16) for h in A["tx"].dropna() if str(h).startswith("0x"))
    S = pd.read_parquet(EXC / "side_fills.parquet")  # the examiner's maker BUY fills (BTC 5m)
    res = {}
    for fam in ("5m", "15m"):
        w = pd.read_parquet(EV / ("w5.parquet" if fam == "5m" else "w15.parquet"))
        w["up_token"], w["down_token"] = w["up_token"].astype(str), w["down_token"].astype(str)
        ptb = ptb_of(w) if fam == "5m" else {}
        if fam == "15m":
            from polyrea.workflows.updown_study import fetch_windows
            raw = fetch_windows([f"btc-updown-15m-{int(s)}" for s in w["start_ts"]])
            for m in raw.values():
                st_ = int(str(m.get("slug")).rsplit("-", 1)[1])
                for e in m.get("events") or []:
                    v = (e.get("eventMetadata") or {}).get("priceToBeat")
                    if v is not None:
                        ptb[st_] = float(v)
            tkd = pd.read_parquet(EV / "clean15.parquet")
            flows = ("clean",)
        else:
            tkd = pd.concat([pd.read_parquet(f) for f in EV.glob("sel_tk_*.parquet")], ignore_index=True)
            flows = ("full", "clean")
        tk = {c: g.sort_values("ts", kind="stable") for c, g in tkd.groupby("cid")}
        # cluster per-window maker PnL (examiner labels)
        if fam == "5m":
            pay = dict(zip(w.cid, w.up_payout))
            S["won"] = [pay[c] if u == 1 else 1 - pay[c] for c, u in zip(S.cid, S.is_up)]
            S["pnl"] = (S.won - S.price) * S.shares
            S["usd"] = S.price * S.shares
            wal = S.groupby("cid").pnl.sum()
            walw = {nm: S[S.wallet == nm].groupby("cid").pnl.sum() for ad, nm in CLUSTER.items()}
            wal_usd = float(S.usd.sum())
        else:
            mk15 = pd.read_parquet(EV / "mk15.parquet")
            t2 = {**{t: (c, 1) for t, c in zip(w.up_token, w.cid)}, **{t: (c, 0) for t, c in zip(w.down_token, w.cid)}}
            mk15["cid"] = mk15.token_id.astype(str).map(lambda t: t2[t][0])
            mk15["isu"] = mk15.token_id.astype(str).map(lambda t: t2[t][1])
            pay = dict(zip(w.cid, w.up_payout))
            mk15["pnl"] = (np.where(mk15.isu == 1, mk15.cid.map(pay), 1 - mk15.cid.map(pay)) - mk15.price) * mk15.shares
            mk15["usd"] = mk15.price * mk15.shares
            wal = mk15.groupby("cid").pnl.sum()
            walw = {nm: mk15[mk15.wallet == ad].groupby("cid").pnl.sum() for ad, nm in CLUSTER.items()}
            wal_usd = float(mk15.usd.sum())
        blk = dict(zip(w.cid, (w.start_ts // 7200).astype(int)))
        half = dict(zip(w.cid, np.where(w.start_ts < CUT, "early", "late")))
        R = {"windows": int(len(w)), "wallet_maker_pnl": round(float(wal.sum()), 1), "wallet_maker_usd": round(wal_usd, 0),
             "wallet_maker_return": float(wal.sum() / wal_usd) if wal_usd else None}
        wp = wal.reindex(w.cid).fillna(0.0)
        wb = np.array([blk[c] for c in w.cid])
        # wallet return significance (block bootstrap, windows grouped by 2-h block)
        wu = (S.groupby("cid").usd.sum() if fam == "5m" else mk15.groupby("cid").usd.sum()).reindex(w.cid).fillna(0.0)
        R["wallet_maker_return_p_le0"], R["wallet_maker_return_ci95"] = boot_ret(wp.to_numpy(), wu.to_numpy(), wb)
        for side in ("r8c", "re_exec"):
            for flow in flows:
                for L, Q in ((2, 62.0), (5, 62.0), (2, 500.0)):
                    o = replay(w, tk, cl_tx, base, px, v3, cl, ptb, L, Q, side, flow, 300 if fam == "5m" else 900)
                    D = pd.DataFrame.from_dict(o, orient="index", columns=["pnl", "usd", "sh"])
                    D["wal"] = wp.reindex(D.index).fillna(0.0)
                    D["blk"] = [blk[c] for c in D.index]
                    D["half"] = [half[c] for c in D.index]
                    act = D.index.isin(wal.index)
                    rec = {"pnl": round(float(D.pnl.sum()), 1), "usd": round(float(D.usd.sum()), 0),
                           "return": float(D.pnl.sum() / D.usd.sum()) if D.usd.sum() else None,
                           "windows_with_fills": int((D.sh > 0).sum())}
                    if D.usd.sum():
                        pw = D.pnl.to_numpy()
                        rec["t_per_window"] = float(stats.ttest_1samp(pw, 0).statistic)
                        rec["p_profit_t_one_sided"] = float(stats.ttest_1samp(pw, 0, alternative="greater").pvalue)
                        rec["p_le0_block_boot"], rec["return_ci95"] = boot_ret(D.pnl.to_numpy(), D.usd.to_numpy(), D.blk.to_numpy())
                    if (side, flow, L, Q) == ("r8c", "full" if fam == "5m" else "clean", 2, 62.0) or (side, L, Q) == ("re_exec", 2, 62.0):
                        rec["corr_cluster_windows"] = corr2(D.pnl[act], D.wal[act])
                        rec["corr_all_windows"] = corr2(D.pnl, D.wal)
                        rec["corr_perm_p_cluster_windows"] = perm_p(D.pnl[act].to_numpy(), D.wal[act].to_numpy(), D.blk[act].to_numpy())
                        for h in ("early", "late"):
                            m = act & (D.half == h).to_numpy()
                            rec[f"corr_{h}"] = corr2(D.pnl[m], D.wal[m])
                            rec[f"return_{h}"] = float(D.pnl[(D.half == h)].sum() / max(D.usd[(D.half == h)].sum(), 1e-9))
                            rec[f"pnl_{h}"] = round(float(D.pnl[(D.half == h)].sum()), 1)
                        rec["per_wallet_corr"] = {}
                        for nm, s_ in walw.items():
                            ii = s_.index
                            rec["per_wallet_corr"][nm] = {"all": corr2(D.pnl.reindex(ii).fillna(0), s_),
                                                          **{h: corr2(D.pnl.reindex(ii[[half[c] == h for c in ii]]).fillna(0), s_[[half[c] == h for c in ii]]) for h in ("early", "late")},
                                                          "windows": int(len(ii))}
                        D.to_parquet(EXC / f"replay_{fam}_{side}_{flow}.parquet")
                    R[f"{side}_{flow}_L{L}_Q{int(Q)}"] = rec
                    print(fam, side, flow, L, Q, {k: rec[k] for k in ("pnl", "usd", "return")}, round(time.time() - t0, 1), flush=True)
        R["wallet_maker_pnl_by_half"] = {h: round(float(wp[[half[c] == h for c in wp.index]].sum()), 1) for h in ("early", "late")}
        res[fam] = R
    (RES / "exam_r2_replay.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
