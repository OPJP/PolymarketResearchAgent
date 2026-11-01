"""Iteration 8 (panel iter7 mechanics critique 4): the fill side scored per fill with the posture rule.

Development live block 10-31 14:06-16:30 UTC, BTC 5m, every cluster maker BUY fill with a server match ms (shared/own
trade stream). Predicted side at the match ms T: the outcome whose Chainlink edge over the Polymarket mid is larger,
i.e. Up iff e_up = digital fair of Up from the Chainlink report stamped floor((T - 1432)/1000) (true strike, R3 vol) -
Up mid (touch just before T) > 0. No fitted parameter. Baselines (market-only): futures edge sign, cheaper side, the side
whose bid the previous clean print hit, always-Up. Split: at-touch fills (fill price >= the token's best bid just before
T) vs deeper fills; live BUILD (< 15:00) vs live VALIDATE (>= 15:00). Also per window: in windows with >= 70% of the
cluster's shares on one side, the side with the larger time-averaged Chainlink edge over the window's first 240 s.
    python code8/fill_side.py 1793455600 1793464202
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
sys.path.insert(0, str(HERE.parent / "code6"))
from pres_live import load_ref, CL  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
SPLIT = 1793458800
D_CL = 1432


def main(a, b):
    x = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet")
    x = x[x.w.str.contains("btc-updown-")].sort_values("s", kind="stable")
    x["h"] = x.h.str.lower()
    cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet"))])
    cd["maker"] = cd.maker.str.lower()
    cd["tx"] = cd.tx.str.lower()
    acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))]).drop_duplicates(
        subset=["transactionHash", "asset", "w", "size", "price"])
    acts["tx"] = acts.transactionHash.str.lower()
    mk_tx = set(cd.loc[(cd.role == "maker") & cd.maker.isin(CL), "tx"])
    fills = acts[(acts.type == "TRADE") & (acts.side == "BUY") & acts.tx.isin(mk_tx) & acts.slug.str.contains("btc-updown-(?:5m|15m)", na=False, regex=True)].copy()
    ms = x.drop_duplicates("h").set_index("h").s
    fills["ms"] = fills.tx.map(ms)
    fills = fills.dropna(subset=["ms"])
    allcl = set(cd.loc[cd.maker.isin(CL), "tx"]) | set(acts.tx)
    d = x.d.astype(str).str.upper().str[0]
    x["s_up"] = ((x.ai == 0) & (d == "S")) | ((x.ai == 1) & (d == "B"))
    xc = x[~x.h.isin(allcl)].drop_duplicates("h")
    tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
    fu, cl, tw = load_ref(a, b)
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))
    cls = np.array(sorted(cl))
    clv = np.array([cl[k] for k in cls])
    rows = []
    for slug, g in fills.groupby("slug"):
        st = int(slug.split("-")[-1])
        L = 900 if "-15m-" in slug else 300
        K_c = tw.get(st)
        if K_c is None or st < a - (600 if L == 900 else 0):
            continue
        K_f = ms_sec[np.searchsorted(sec, st - 60):np.searchsorted(sec, st)].mean()
        tg = tch[tch.w == slug].sort_values("s")
        ts_, bb_, ba_ = tg.s.to_numpy(), tg.bb.to_numpy(), tg.ba.to_numpy()
        xg = xc[xc.w == slug]
        xs, xup = xg.s.to_numpy(), xg.s_up.to_numpy()

        def ed(T):
            jj = np.searchsorted(sec, T // 1000)
            sig = np.std(r1[max(jj - 300, 0):jj]) * 1.4
            tau = max(st + L - T / 1000, 1.0)
            i = np.searchsorted(ts_, T - 1, side="right") - 1
            i1 = np.searchsorted(ts_, T - 1000, side="right") - 1
            if i < 0 or i1 < 0 or not sig > 0:
                return None
            mid = (bb_[i] + ba_[i]) / 2
            mid1 = (bb_[i1] + ba_[i1]) / 2
            fcs = {}
            for D in (700, 1083, 1432, 2000, 3000):
                k = np.searchsorted(cls, (T - D) // 1000, side="right") - 1
                fcs[D] = norm.cdf(np.log(clv[k] / K_c) / (sig * np.sqrt(tau))) if k >= 0 else np.nan
            k = np.searchsorted(cls, (T - D_CL) // 1000, side="right") - 1
            fcs["z"] = np.log(clv[k] / K_c) / (sig * np.sqrt(tau)) if k >= 0 else np.nan
            fmid = fm[max(np.searchsorted(fs, T, side="right") - 1, 0)]
            ff = norm.cdf(np.log(fmid / K_f) / (sig * np.sqrt(tau)))
            return fcs, ff - mid, mid, bb_[i], ba_[i], mid1

        for r in g.itertuples():
            T = int(r.ms)
            e = ed(T)
            if e is None:
                continue
            fcs, e_f, mid, bbu, bau, mid1 = e
            e_cl = fcs[D_CL] - mid
            up = r.outcome == "Up"
            bb_tok = bbu if up else 1 - bau
            j = np.searchsorted(xs, T, side="left") - 1
            prev_sold_up = bool(xup[j]) if j >= 0 else None
            lastp = None
            if j >= 0:
                xr = xg.iloc[j]
                lastp = float(xr.p) if int(xr.ai) == 0 else 1 - float(xr.p)
            bts = int(r.timestamp)
            fcb, midb = np.nan, np.nan
            kb = np.searchsorted(cls, bts - 3, side="right") - 1
            jb = np.searchsorted(xs, (bts - 2) * 1000, side="left") - 1
            if kb >= 0 and jb >= 0:
                jjb = np.searchsorted(sec, bts - 2)
                sgb = np.std(r1[max(jjb - 300, 0):jjb]) * 1.4
                taub = max(st + L - (bts - 2), 1.0)
                fcb = norm.cdf(np.log(clv[kb] / K_c) / (sgb * np.sqrt(taub))) if sgb > 0 else np.nan
                xr2 = xg.iloc[jb]
                midb = float(xr2.p) if int(xr2.ai) == 0 else 1 - float(xr2.p)
            rows.append(dict(st=st, fam="15m" if L == 900 else "5m", T=T, up=int(up), shares=float(r.size), price=float(r.price),
                             bts=bts, e_cl_block=fcb - midb,
                             e_cl=e_cl, e_f=e_f, mid=mid, at_touch=int(float(r.price) >= bb_tok - 1e-9), prev_sold_up=prev_sold_up,
                             wallet=str(getattr(r, "w", "")), **{f"e_cl_D{D}": fcs[D] - mid for D in fcs if D != "z"}, zcl=fcs["z"],
                             e_cl_mid1s=fcs[D_CL] - mid1, e_cl_lastprint=(fcs[D_CL] - lastp) if lastp is not None else np.nan))
        # window-level posture: time-averaged CL edge over the first 240 s
    D = pd.DataFrame(rows)
    out = {"fills": int(len(D)), "windows": int(D.st.nunique())}

    def acc(sub):
        if not len(sub):
            return None
        y = sub.up.to_numpy() == 1
        r = {"n": int(len(sub)), "chainlink_edge_sign": round(float(((sub.e_cl > 0) == y).mean()), 3),
             "futures_edge_sign": round(float(((sub.e_f > 0) == y).mean()), 3),
             "cheaper_side": round(float(((sub.mid < 0.5) == y).mean()), 3),
             "always_up": round(float(y.mean()), 3)}
        ps = sub.dropna(subset=["prev_sold_up"])
        r["prev_print_sold_side"] = round(float((ps.prev_sold_up.astype(bool).to_numpy() == (ps.up.to_numpy() == 1)).mean()), 3) if len(ps) else None
        return r
    for fam in ("5m", "15m"):
        F = D[D.fam == fam]
        o = {}
        for nm, sub in (("all", F), ("live_build", F[F["T"] < SPLIT * 1000]), ("live_validate", F[F["T"] >= SPLIT * 1000]),
                        ("validate_at_touch", F[(F["T"] >= SPLIT * 1000) & (F.at_touch == 1)]),
                        ("validate_deeper", F[(F["T"] >= SPLIT * 1000) & (F.at_touch == 0)])):
            o[nm] = acc(sub)
        V = F[F["T"] >= SPLIT * 1000]
        yv = V.up.to_numpy() == 1
        o["validate_variants"] = {c: round(float(((V[c] > 0) == yv)[V[c].notna()].mean()), 3) for c in V.columns if c.startswith("e_cl_")}
        o["validate_per_wallet"] = {wn: round(float(((g.e_cl > 0) == (g.up == 1)).mean()), 3) for wn, g in V.groupby("wallet")}
        o["validate_n_per_wallet"] = {wn: int(len(g)) for wn, g in V.groupby("wallet")}
        o["by_30min"] = {str(int(k)): [round(float(((g.e_cl > 0) == (g.up == 1)).mean()), 3), int(len(g))]
                         for k, g in F.groupby(F["T"] // 1800000 * 1800)}
        out[fam] = o
    # share-weighted per window: one-sided windows (>= 70% of shares on one side); predicted = sign of the share-weighted
    # mean Chainlink edge at the cluster's own fills is own-presence-conditioned, so use the time-average over seconds
    D.to_parquet(C / "it6" / f"fill_side_{a}_{b}.parquet", index=False)
    (HERE.parent / "results" / f"iter8_fill_side_{a}_{b}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
