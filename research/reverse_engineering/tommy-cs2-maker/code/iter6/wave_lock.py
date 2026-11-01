"""Iteration 6, X78 (mechanics panel iter5 P4) + X80 step 2 (assumptions panel iter5 P1): at the pack's informed takes
WITHOUT a wallet take, are the wallet's pulls locked to the public cancel wave (book reader: u - w tight, slope ~1 on
w - p) or to the event (its own feed: u - p tight, independent of w)?

Server clock, own recorder tommy_cs2_near, 10-31 14:50-18:00 UTC development block (BUILD-live), token-0 books of the
wallet's dev-unit CS2 markets. For each pack BUY FAK (signing p, match m) with no wallet take within +-3 s:
  w = first NON-own cancel on the consumed side in (p, m)
  u = first OWN-size cancel on the consumed side in [p - 300, m) (own sizes = the wallet's maker order sizes in that
      market from calldata_dev, whole cents)
Regress u - p on w - p (events with both after p), permutation null for the correlation (u shuffled across events),
and report the hit rate of the wallet's maker orders in the pack's tx by (wave, pull) class. Reference: the wallet's
own takes (u - p known ~14 ms); busy-phase control: retail BUY FAKs far from informed takes.
Output: results/wave_lock.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OWN0, END = 1793458232, 1793469600
rng = np.random.default_rng(6)


def nearest_gap(x, s):
    if x is None or len(x) == 0:
        return 1e18
    j = np.searchsorted(x, s)
    a = abs(x[j] - s) if j < len(x) else 1e18
    b = abs(x[j - 1] - s) if j > 0 else 1e18
    return min(a, b)


def first_after(arr, lo, hi):
    if arr is None:
        return None
    j = np.searchsorted(arr, lo)
    return float(arr[j]) if j < len(arr) and arr[j] < hi else None


def match_times(t0map):
    mt = {}
    h = int(OWN0 // 3600 * 3600)
    while h < END:
        try:
            for r in live.iter_live("tommy_cs2_near", max(h, OWN0), min(h + 3600, END)):
                if r.get("k") == "x" and str(r.get("a")) in t0map and r.get("h"):
                    hh = str(r["h"]).lower()
                    mt[hh] = min(mt.get(hh, 1e18), int(r["s"]))
        except Exception as e:  # noqa: BLE001
            print("feed stopped", type(e).__name__, flush=True)
        h += 3600
    return mt


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    mt = match_times(t0map)
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    cd["tok"] = cd.token_id.astype(str)
    cd["a"] = cd.tok.map(t0map)
    wm = cd[(cd.idx >= 0) & (cd.maker == WALLET) & cd.a.notna()]
    own_sizes = {a: set(np.round(g.shares.to_numpy(float), 2)) | {100.0} for a, g in wm.groupby("a")}
    E = pd.read_parquet(OUT / "level_events_dev.parquet")
    E = E[E.kind == "cancel"].copy()
    E["own"] = [bool(w) and (round(float(z), 2) in own_sizes.get(a, {100.0}))
                for a, z, w in zip(E.a, E["size"], E.whole)]
    own_c = {k: np.sort(g.s.to_numpy(float)) for k, g in E[E.own].groupby(["a", "side"])}
    oth_c = {k: np.sort(g.s.to_numpy(float)) for k, g in E[~E.own].groupby(["a", "side"])}
    tk = cd[cd.idx == -1].drop_duplicates("tx").copy()
    tk = tk[tk.a.notna() & (tk.sign_ms > 1.7e12) & (tk.sign_ms < 1.8e12)]
    tk["m"] = tk.tx.str.lower().map(mt)
    tk = tk[tk.m.notna() & (tk.sign_ms >= OWN0 * 1000) & (tk.sign_ms < END * 1000)].copy()
    tk["cside"] = np.where((tk.side == 0) == (tk.tok == tk.a), "SELL", "BUY")
    pack = set(pd.read_parquet(OUT / "pack_orders.parquet", columns=["maker"]).maker.str.lower()) - {WALLET}
    pack |= {"0x72aaaaf9", "0xfe8a28be", "0x2529c68d", "0xf1ee4842", "0x93078b5d"}
    tk["mk"] = tk.maker.str.lower()
    is_pack = tk.mk.isin(pack) | tk.mk.str[:10].isin(pack)
    w_t = {a: np.sort(g.sign_ms.to_numpy(float)) for a, g in tk[tk.mk == WALLET].groupby("a")}
    inf_t = {a: np.sort(g.sign_ms.to_numpy(float)) for a, g in tk[is_pack | (tk.mk == WALLET)].groupby("a")}
    wm_tx = set(cd[(cd.idx >= 0) & (cd.maker == WALLET)].tx)
    cnt = tk.mk.value_counts()
    groups = {"wallet_takes": tk[(tk.mk == WALLET) & (tk.side == 0)]}
    po = tk[is_pack & (tk.side == 0)]
    groups["pack_only"] = po[[nearest_gap(w_t.get(r.a), r.sign_ms) > 3000 for r in po.itertuples()]]
    rt = tk[(tk.side == 0) & tk.mk.map(cnt).le(20) & ~is_pack & (tk.mk != WALLET)]
    groups["retail_control"] = rt[[nearest_gap(inf_t.get(r.a), r.sign_ms) > 3000 for r in rt.itertuples()]]
    res = {}
    for nm, g in groups.items():
        rows = []
        for r in g.itertuples():
            k = (r.a, r.cside)
            p, m = float(r.sign_ms), float(r.m)
            u = first_after(own_c.get(k), p - 300, m)
            w = first_after(oth_c.get(k), p, m)
            oc = oth_c.get(k)
            n100 = int(np.searchsorted(oc, p + 100) - np.searchsorted(oc, p)) if oc is not None else 0
            n300 = int(np.searchsorted(oc, p + 300) - np.searchsorted(oc, p)) if oc is not None else 0
            rows.append({"p": p, "m": m, "u": u, "w": w, "hit": r.tx in wm_tx, "n100": n100, "n300": n300})
        df = pd.DataFrame(rows)
        if df.empty:
            res[nm] = {"n": 0}
            continue
        has_u = df.u.notna()
        has_w = df.w.notna()
        out = {"n": int(len(df)), "delay_ms_p50": float(np.median(df.m - df.p)),
               "share_pull": round(float(has_u.mean()), 3), "share_wave": round(float(has_w.mean()), 3),
               "n_both": int((has_u & has_w).sum())}
        both = df[has_u & has_w].copy()
        both["up"] = both.u - both.p
        both["wp"] = both.w - both.p
        both["uw"] = both.u - both.w
        aft = both[both.up >= 0]
        out["both_pull_after_p"] = int(len(aft))
        if len(aft) >= 5:
            sl = np.polyfit(aft.wp, aft.up, 1)[0]
            cr = float(np.corrcoef(aft.wp, aft.up)[0, 1])
            null = np.array([np.corrcoef(aft.wp, rng.permutation(aft.up.to_numpy()))[0, 1] for _ in range(2000)])
            out["slope_up_on_wp"] = round(float(sl), 3)
            out["corr_up_wp"] = round(cr, 3)
            out["corr_perm_p_one_sided"] = round(float((null >= cr).mean()), 4)
            out["u_minus_p_ms_p25_p50_p75"] = [round(float(x), 1) for x in np.percentile(aft.up, [25, 50, 75])]
            out["u_minus_w_ms_p25_p50_p75"] = [round(float(x), 1) for x in np.percentile(aft.uw, [25, 50, 75])]
            out["w_minus_p_ms_p25_p50_p75"] = [round(float(x), 1) for x in np.percentile(aft.wp, [25, 50, 75])]
            out["iqr_u_minus_p"] = round(float(np.subtract(*np.percentile(aft.up, [75, 25]))), 1)
            out["iqr_u_minus_w"] = round(float(np.subtract(*np.percentile(aft.uw, [75, 25]))), 1)
            out["share_u_0_30ms_after_w"] = round(float(((aft.uw >= 0) & (aft.uw < 30)).mean()), 3)
            out["share_u_30_200ms_after_w"] = round(float(((aft.uw >= 30) & (aft.uw < 200)).mean()), 3)
            out["share_u_before_w"] = round(float((aft.uw < 0).mean()), 3)
        cls = {"pull_and_wave": has_u & has_w, "wave_no_pull": ~has_u & has_w,
               "pull_no_wave": has_u & ~has_w, "neither": ~has_u & ~has_w}
        out["n_by_class"] = {k: int(v.sum()) for k, v in cls.items()}
        out["wallet_hit_rate_by_class"] = {k: (round(float(df[v].hit.mean()), 3) if v.any() else None)
                                           for k, v in cls.items()}
        # does the wave's size decide whether it pulls? (pull after p within the delay window vs none)
        pulled = df.u.notna() & (df.u >= df.p)
        out["wave_size_by_pull"] = {"pulled_n100_mean": round(float(df[pulled].n100.mean()), 2) if pulled.any() else None,
                                    "not_pulled_n100_mean": round(float(df[~pulled].n100.mean()), 2) if (~pulled).any() else None,
                                    "pulled_n300_mean": round(float(df[pulled].n300.mean()), 2) if pulled.any() else None,
                                    "not_pulled_n300_mean": round(float(df[~pulled].n300.mean()), 2) if (~pulled).any() else None}
        try:
            from sklearn.metrics import roc_auc_score
            if pulled.any() and (~pulled).any():
                out["wave_size_by_pull"]["auc_n100"] = round(float(roc_auc_score(pulled, df.n100)), 3)
                out["wave_size_by_pull"]["auc_n300"] = round(float(roc_auc_score(pulled, df.n300)), 3)
        except Exception:  # noqa: BLE001
            pass
        res[nm] = out
    (RES / "wave_lock.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
