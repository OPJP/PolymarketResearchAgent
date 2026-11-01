"""iteration 18, T8 = X225 (assumptions panel P2) (pre-registered in NOTES.md 12:56 UTC 11-01): where is the money relative to the
forward / trailing volatility ratio? Units: the cluster's BTC 5m BUY trades (activity of the three accounts; ~90% maker),
windows starting 06-12..10-22 (development, case by case) and the lot 10-23..30 (pooled only). R = P(slot) / rv(previous
slot): the utc_N28 profile of the window's slot (code18/sched_vol.profiles) over the realised 1-s vol of the 300 s before
the window start. Outcome = the Binance proxy (sign of the window's Binance close-to-close log return, it18/slot_rv r5),
checked against the Gamma resolution on BUILD 10-09..22 (windows_5m up_payout). Return per $ = sum(payout x size - usdc)
/ sum(usdc). Table month x R quintile (within month) x cheap (price < 0.5) / favourite, day-block bootstrap for the
October cheap top - bottom quintile difference."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sched_vol as sv  # noqa: E402

C = sv.C
CLW = ("bosona", "almach", "momoney")


def trades():
    fr = []
    for w in CLW:
        for f in (C / f"activity_{w}.parquet", C / "exam" / f"activity_{w}.parquet"):
            a = pd.read_parquet(f, columns=["timestamp", "type", "side", "outcomeIndex", "price", "size", "usdcSize", "slug", "transactionHash"])
            a = a[(a.type == "TRADE") & (a.side == "BUY") & a.slug.str.startswith("btc-updown-5m-")]
            fr.append(a.drop(columns=["transactionHash"]).assign(src=f.name + w))
    h = pd.read_parquet(C / "it12" / "hist_btc.parquet", columns=["timestamp", "type", "side", "outcomeIndex", "price", "size", "usdcSize", "slug", "w"])
    h = h[(h.type == "TRADE") & (h.side == "BUY") & h.slug.astype(str).str.startswith("btc-updown-5m-")]
    fr.append(h.drop(columns=["w"]).assign(src="hist"))
    A = pd.concat(fr, ignore_index=True)
    A["st"] = A.slug.astype(str).str.rsplit("-", n=1).str[1].astype(int)
    # the cached activity overlaps hist (10-07/08) and exam (10-22): keep each window from one source
    A = A.sort_values("src")
    first_src = A.groupby("st").src.transform("first")
    A = A[A.src == first_src]
    return A


def main():
    T = pd.read_parquet(C / "it18" / "slot_rv.parquet")
    Pf = sv.profiles(T)["utc_N28"]
    rv = {(int(d), int(s)): float(v) for d, s, v in zip(T.day, T.slot, T.rv)}
    r5 = {(int(d), int(s)): float(v) for d, s, v in zip(T.day, T.slot, T.r5)}
    A = trades()
    A = A[(A.st >= 1781222400) & (A.st < 1793404800)]  # 06-12 .. 10-30
    W = pd.DataFrame({"st": np.unique(A.st.to_numpy(np.int64))})
    day = W.st // 86400 * 86400
    slot = (W.st - day) // 300
    W["P"] = sv.prof_col(Pf, W.st.to_numpy())
    W["trail"] = [rv.get((int(d - 86400), 287) if s == 0 else (int(d), int(s - 1)), np.nan) for d, s in zip(day, slot)]
    W["R"] = W.P / W.trail
    W["up_won_proxy"] = [(r5.get((int(d), int(s)), np.nan) >= 0) if np.isfinite(r5.get((int(d), int(s)), np.nan)) else np.nan for d, s in zip(day, slot)]
    g = pd.read_parquet(C / "windows_5m.parquet", columns=["start_ts", "up_payout"])
    chk = W.merge(g, left_on="st", right_on="start_ts")
    chk = chk[chk.up_won_proxy.notna()]
    out = {"proxy_vs_gamma_BUILD": {"windows": int(len(chk)), "agree": round(float(((chk.up_won_proxy.astype(float)) == chk.up_payout).mean()), 4)}}
    # exact outcomes: the cluster's own REDEEM rows (usdcSize / size = 1 for the winning outcome, 0 for the losing one),
    # then the Gamma resolution (windows_5m, BUILD and lot), else none (the window is dropped); settlement only
    rd = []
    for w in CLW:
        for f in (C / f"activity_{w}.parquet", C / "exam" / f"activity_{w}.parquet"):
            a = pd.read_parquet(f, columns=["type", "outcomeIndex", "size", "usdcSize", "slug"])
            rd.append(a[(a.type == "REDEEM") & a.slug.str.startswith("btc-updown-5m-")])
    hh = pd.read_parquet(C / "it12" / "hist_btc.parquet", columns=["type", "outcomeIndex", "size", "usdcSize", "slug"])
    rd.append(hh[(hh.type == "REDEEM") & hh.slug.astype(str).str.startswith("btc-updown-5m-")])
    R_ = pd.concat(rd, ignore_index=True)
    R_ = R_[(R_["size"] > 1) & R_.outcomeIndex.isin([0, 1])].copy()
    R_["st"] = R_.slug.astype(str).str.rsplit("-", n=1).str[1].astype(int)
    R_["upw"] = np.where(R_.outcomeIndex == 0, R_.usdcSize / R_["size"] > 0.5, R_.usdcSize / R_["size"] < 0.5).astype(float)
    vote = R_.groupby("st").upw.mean()
    exact = {int(k): float(v > 0.5) for k, v in vote.items() if abs(v - 0.5) > 0.25}
    gw = pd.concat([pd.read_parquet(C / "windows_5m.parquet", columns=["start_ts", "up_payout"]),
                    pd.read_parquet(C / "exam" / "windows_5m.parquet", columns=["start_ts", "up_payout"])])
    gam = {int(a_): float(b_) for a_, b_ in zip(gw.start_ts, gw.up_payout) if b_ in (0.0, 1.0)}
    both = [k for k in exact if k in gam]
    out["redeem_vs_gamma"] = {"windows": len(both), "agree": round(float(np.mean([exact[k] == gam[k] for k in both])), 4) if both else None}
    W["up_won"] = [exact.get(int(x), gam.get(int(x), np.nan)) for x in W.st]
    W["src"] = ["redeem" if int(x) in exact else ("gamma" if int(x) in gam else "none") for x in W.st]
    out["outcome_source_windows"] = W.src.value_counts().to_dict()
    A = A.merge(W[["st", "R", "up_won"]], on="st", how="left")
    A = A[np.isfinite(A.R) & A.up_won.notna()].copy()
    A["pay"] = np.where(A.outcomeIndex == 0, A.up_won.astype(float), 1 - A.up_won.astype(float))
    A["pnl"] = A.pay * A["size"] - A.usdcSize
    A["cheap"] = A.price < 0.5
    A["month"] = pd.to_datetime(A.st, unit="s").dt.strftime("%m")
    A.loc[A.st >= 1792713600, "month"] = "lot"
    A["dayi"] = (A.st // 86400).astype(int)
    tab = {}
    for mth, gm in A.groupby("month"):
        wq = gm.groupby("st").R.first()
        try:
            qs = pd.qcut(wq, 5, labels=False, duplicates="drop")
        except ValueError:
            continue
        gm = gm.assign(q=gm.st.map(qs))
        rec = {"fills": int(len(gm)), "usd": round(float(gm.usdcSize.sum()), 0), "ret": round(float(gm.pnl.sum() / gm.usdcSize.sum()), 4),
               "cheap_share": round(float(gm.cheap.mean()), 3), "R_median": round(float(wq.median()), 3)}
        for q, gq in gm.groupby("q"):
            rr = {}
            for lab, m in (("cheap", gq.cheap), ("fav", ~gq.cheap)):
                x = gq[m]
                rr[lab] = {"fills": int(len(x)), "ret": round(float(x.pnl.sum() / x.usdcSize.sum()), 4) if len(x) and x.usdcSize.sum() > 0 else None}
            rr["all"] = {"fills": int(len(gq)), "ret": round(float(gq.pnl.sum() / gq.usdcSize.sum()), 4), "cheap_share": round(float(gq.cheap.mean()), 3),
                         "usd": round(float(gq.usdcSize.sum()), 0)}
            rec[f"q{int(q)}"] = rr
        if mth == "10":
            rng = np.random.default_rng(0)
            days = gm.dayi.unique()
            diffs = []
            for _ in range(1000):
                ds = rng.choice(days, len(days), replace=True)
                x = pd.concat([gm[gm.dayi == d] for d in ds])
                top = x[(x.q == x.q.max()) & x.cheap]
                bot = x[(x.q == 0) & x.cheap]
                if top.usdcSize.sum() > 0 and bot.usdcSize.sum() > 0:
                    diffs.append(top.pnl.sum() / top.usdcSize.sum() - bot.pnl.sum() / bot.usdcSize.sum())
            rec["oct_cheap_top_minus_bottom_ci90"] = [round(float(np.quantile(diffs, 0.05)), 4), round(float(np.quantile(diffs, 0.95)), 4)]
        tab[mth] = rec
    out["table"] = tab
    # the September -> October change in return per $ by quintile (all fills)
    try:
        ch = {}
        for q in range(5):
            s9 = tab["09"].get(f"q{q}", {}).get("all", {})
            s10 = tab["10"].get(f"q{q}", {}).get("all", {})
            ch[f"q{q}"] = {"sep": s9.get("ret"), "oct": s10.get("ret"), "usd_oct": s10.get("usd")}
        out["sep_to_oct_by_quintile"] = ch
    except KeyError:
        pass
    (HERE.parent / "results" / "iter18_pnl_by_ratio.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1)[:5000])


if __name__ == "__main__":
    main()
