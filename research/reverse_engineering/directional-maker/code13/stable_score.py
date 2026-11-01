"""X140 (panel iter12 assumptions P1): the FROZEN rule's functions scored on the stable profitable version.

Sample (pre-registered in fetch_stable.py, 03:55 UTC 11-01): BTC 5m windows starting in the UTC hours 02, 08, 14, 20 of
09-11..10-11 (STUDY-stable 09-11..25, VALIDATE-stable 09-26..10-11), plus the same hours of the October BUILD days
10-12..10-22 as the control fold (tapes already on disk). No refit: the frozen R3 presence model and its activity
baseline (presence3_rule.txt / presence3_activity.txt, BUILD 10-09..26 fit), and R8's public side (decided -> cheaper
token, else the posture; the Binance stand-in digital because Chainlink history is not served before ~10-01).
Reported by fold, by week and per wallet: presence AUC vs the activity baseline (10-s bins, no own state), the public
side per maker BUY fill and at the first fill of each same-outcome run (entry run = the window's first run), the
cheaper-token baseline, the window net-side win share, and the return per $ of the fills held to resolution.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code"))
import lightgbm as lgb  # noqa: E402
from features2 import Spot, build_panel, clean_tape, fair_up  # noqa: E402
import final_rule as fr  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
ST = C / "it13/stable"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
      "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
NAME2ADDR = {v: k for k, v in CL.items()}
HOURS = (2, 8, 14, 20)
FOLDS = {"study_stable": (1789084800, 1790380800), "validate_stable": (1790380800, 1791763200), "october_control": (1791763200, 1792713600)}


def tx_int(h16: pd.Series) -> pd.Series:
    return h16.astype(str).str.slice(0, 15).map(lambda x: int(x, 16) if x and x != "nan" else 0).astype(np.int64)


def load_windows():
    a = pd.read_parquet(ST / "windows.parquet")
    b = pd.read_parquet(C / "windows_5m.parquet")
    b = b[(b.start_ts >= FOLDS["october_control"][0]) & (b.end_ts <= FOLDS["october_control"][1])]
    b = b[((b.start_ts % 86400) // 3600).isin(HOURS)]
    a["up_payout"] = np.nan
    w = pd.concat([a[["cid", "start_ts", "end_ts", "up_token", "down_token", "up_payout"]],
                   b[["cid", "start_ts", "end_ts", "up_token", "down_token", "up_payout"]]], ignore_index=True)
    return w.sort_values("start_ts").reset_index(drop=True)


def load_tapes(w):
    from polyrea.analysis.updown import snap_price
    out = []
    stab = w[w.start_ts < FOLDS["october_control"][0]]
    for r in stab.itertuples(index=False):
        f = ST / f"t_{int(r.start_ts)}.parquet"
        if not f.exists():
            continue
        t = pd.read_parquet(f)
        if t.empty or "price" not in t:
            continue
        t = t[(t.ts >= r.start_ts - fr.PRE) & (t.ts < r.end_ts)]
        out.append(pd.DataFrame({"cid": r.cid, "ts": t.ts.astype(np.int64), "side": t.side.astype(str), "asset": t.asset.astype(str),
                                 "price": t.price.astype(float).map(snap_price).astype(np.float32), "size": t["size"].astype(np.float32),
                                 "wallet": t.wallet.astype(str), "tx": tx_int(t.tx16)}))
    octw = w[w.start_ts >= FOLDS["october_control"][0]]
    for d in sorted(set(octw.start_ts // 86400 * 86400)):
        f = C / f"taker5m_day_{d}.parquet"
        if not f.exists():
            continue
        t = pd.read_parquet(f)
        t = t[t.cid.isin(set(octw.cid))]
        t = t.merge(octw[["cid", "start_ts", "end_ts"]], on="cid")
        t = t[(t.ts >= t.start_ts - fr.PRE) & (t.ts < t.end_ts)]
        out.append(pd.DataFrame({"cid": t.cid.astype(str), "ts": t.ts.astype(np.int64), "side": t.side.astype(str), "asset": t.asset.astype(str),
                                 "price": t.price.astype(np.float32), "size": t["size"].astype(np.float32), "wallet": t.wallet.astype(str).str.lower(),
                                 "tx": fr._txint(t.tx)}))
    tk = pd.concat(out, ignore_index=True)
    for c in ("cid", "asset", "wallet", "side"):
        tk[c] = tk[c].astype(str).astype("category")
    return tk


def load_fills(w):
    h = pd.read_parquet(C / "it12/hist_btc.parquet")
    h = h[h.type == "TRADE"]
    slug2 = {f"btc-updown-5m-{int(s)}": (c, u, d) for s, c, u, d in zip(w.start_ts, w.cid, w.up_token, w.down_token)}
    h = h[h.slug.isin(set(slug2))].copy()
    h["cid"] = h.slug.map(lambda s: slug2[s][0])
    h["token_id"] = [slug2[s][1] if int(o) == 0 else slug2[s][2] for s, o in zip(h.slug, h.outcomeIndex)]
    h["wallet"] = h.w.map(NAME2ADDR)
    h["tx"] = tx_int(h.tx8)
    rows = [h[["wallet", "tx", "token_id", "timestamp", "side", "price", "size", "cid"]].rename(columns={"timestamp": "ts", "size": "shares"})]
    for name, addr in NAME2ADDR.items():
        a = pd.read_parquet(C / f"activity_{name}.parquet")
        a = a[(a.type == "TRADE") & a.conditionId.isin(set(w.cid))]
        a = a[a.timestamp > 1791417542]  # after the end of hist_btc (no double count)
        rows.append(pd.DataFrame({"wallet": addr, "tx": fr._txint(a.transactionHash), "token_id": a.asset.astype(str), "ts": a.timestamp.astype(np.int64),
                                  "side": a.side, "price": a.price.astype(float), "shares": a["size"].astype(float), "cid": a.conditionId}))
    ct = pd.concat(rows, ignore_index=True)
    ct["ts"] = ct.ts.astype(np.int64)
    return ct


def outcomes(w):
    """Up won? from the wallets' own REDEEM rows (usdcSize > 0 on the winning outcome), as in the assumption panel."""
    h = pd.read_parquet(C / "it12/hist_btc.parquet", columns=["type", "slug", "outcomeIndex", "usdcSize", "size"])
    r = h[(h.type == "REDEEM")]
    win = {}
    for s, g in r.groupby("slug"):
        pos = g[g.usdcSize > 0]
        if len(pos):
            win[s] = int(pos.outcomeIndex.mode().iloc[0]) == 0
    out = {}
    for s, c in zip(w.start_ts, w.cid):
        k = f"btc-updown-5m-{int(s)}"
        if k in win:
            out[c] = win[k]
    up = dict(zip(w.cid, w.up_payout))
    for c, v in up.items():
        if c not in out and np.isfinite(v if v is not None else np.nan):
            out[c] = float(v) > 0.5
    return out


def main():
    w = load_windows()
    tk = load_tapes(w)
    w = w[w.cid.isin(set(tk.cid.astype(str)))].reset_index(drop=True)
    ct = load_fills(w)
    from polyrea.adapters.spot import binance_seconds
    secs = []
    for a, b in FOLDS.values():
        rows, _ = binance_seconds("btc", a - 7200, b)
        secs.append(np.asarray(rows, dtype=float).reshape(-1, 2))
    S = np.concatenate(secs)
    S = S[np.argsort(S[:, 0])]
    S = S[np.concatenate([[True], np.diff(S[:, 0]) > 0])]
    # Spot needs a contiguous second grid: forward-fill gaps
    t0, t1 = int(S[0, 0]), int(S[-1, 0])
    grid = np.arange(t0, t1 + 1)
    px = pd.Series(S[:, 1], index=S[:, 0].astype(np.int64)).reindex(grid).ffill().to_numpy()
    sp = Spot(grid, px)
    toks = set(w.up_token) | set(w.down_token)
    buys = ct[(ct.side == "BUY") & ct.token_id.isin(toks)].copy()
    own_rows = tk[tk.wallet.astype(str).isin(set(CL))]
    taker_pairs = set(zip(own_rows.tx, own_rows.wallet.astype(str)))
    buys["role"] = ["taker" if (x, y) in taker_pairs else "maker" for x, y in zip(buys.tx, buys.wallet)]
    mk = buys[buys.role == "maker"].copy()
    clean = clean_tape(tk, set(ct.tx), set(CL))
    panel = build_panel(w, sp, clean, mk)
    panel = fr._add_clock(panel)
    for nm in (fr.MODEL, fr.BASELINE):
        m = lgb.Booster(model_file=str(HERE.parent / "code" / f"presence3_{nm}.txt"))
        panel["p_" + nm] = m.predict(panel[fr.FEATS[nm]])
    st_of = dict(zip(w.cid, w.start_ts))
    panel["start"] = panel.cid.map(st_of)
    res = {"windows": int(w.cid.nunique()), "tape_rows": int(len(tk)), "maker_fills": int(len(mk)), "taker_fills": int((buys.role == "taker").sum())}

    def fold_of(t):
        for k, (a, b) in FOLDS.items():
            if a <= t < b:
                return k
        return None
    panel["fold"] = panel.start.map(fold_of)
    pres = {}
    for k, g in panel.groupby("fold"):
        pres[k] = {"windows": int(g.cid.nunique()), "auc": fr._auc(g.y, g["p_" + fr.MODEL]), "auc_activity": fr._auc(g.y, g["p_" + fr.BASELINE]),
                   "pos_rate": float(g.y.mean()), "active_window_share": float(g.groupby("cid").y.max().mean())}
        pres[k]["gain"] = pres[k]["auc"] - pres[k]["auc_activity"]
        pw = {}
        mkf = mk[mk.cid.isin(set(g.cid))]
        for addr, name in CL.items():
            yw = fr._wallet_labels(g, w[w.cid.isin(set(g.cid))], mkf, addr)
            if yw.sum():
                pw[name] = {"auc": fr._auc(yw, g["p_" + fr.MODEL].to_numpy()), "auc_activity": fr._auc(yw, g["p_" + fr.BASELINE].to_numpy())}
        pres[k]["per_wallet"] = pw
    res["presence"] = pres
    # side: R8 public part on the block clock with the Binance stand-in
    up_of = dict(zip(w.cid, w.up_token))
    c2 = clean.copy()
    c2["cid"] = c2.cid.astype(str)
    mids = {}
    for cid, g in c2.groupby("cid"):
        g = g.sort_values("ts", kind="stable")
        isu = g.asset.astype(str).to_numpy() == up_of.get(cid)
        pr = g.price.to_numpy(dtype=float)
        mids[cid] = (g.ts.to_numpy(np.int64), np.where(isu, pr, 1 - pr))
    win = outcomes(w)
    rows = []
    for r in mk.sort_values(["cid", "ts"]).itertuples(index=False):
        if r.cid not in mids:
            continue
        ts_, mu_ = mids[r.cid]
        i = np.searchsorted(ts_, int(r.ts) - 3, side="right") - 1
        if i < 0:
            continue
        rows.append((r.wallet, r.cid, int(st_of[r.cid]), int(st_of[r.cid]) + 300, int(r.token_id == up_of[r.cid]), int(r.ts), float(mu_[i]),
                     float(r.price), float(r.shares)))
    D = pd.DataFrame(rows, columns=["wallet", "cid", "st", "en", "is_up", "ts", "mid_up", "price", "shares"])
    fb, _ = fair_up(sp, D.st.to_numpy(), D.en.to_numpy(), D.ts.to_numpy() - 2)
    D["post"] = fb > D.mid_up.to_numpy()
    D["cheap"] = D.mid_up < 0.5
    D["dec"] = (D.mid_up - 0.5).abs() > 0.4
    D["pub"] = np.where(D.dec, D.cheap, D.post)
    D["y"] = D.is_up == 1
    D["fold"] = D.st.map(fold_of)
    D["week"] = ((D.st - 1789084800) // (7 * 86400)).astype(int)
    D["upwon"] = D.cid.map(win)
    D = D.sort_values(["cid", "ts"], kind="stable")
    D["run"] = (D.groupby("cid").is_up.transform(lambda s: (s != s.shift()).cumsum()))
    first = D.groupby(["cid", "run"]).head(1)

    def sm(g, fr_=None):
        o = {"n": int(len(g)), "public": float((g.pub == g.y).mean()), "posture": float((g.post == g.y).mean()), "cheaper": float((g.cheap == g.y).mean()),
             "favourite": float((~g.cheap == g.y).mean())}
        f1 = first[first.cid.isin(set(g.cid))]
        fe = f1[f1.run == 1]
        fl = f1[f1.run > 1]
        o["per_run_public"] = float((f1.pub == f1.y).mean()) if len(f1) else None
        o["entry_run_public"] = float((fe.pub == fe.y).mean()) if len(fe) else None
        o["entry_run_cheaper"] = float((fe.cheap == fe.y).mean()) if len(fe) else None
        o["later_runs_public"] = float((fl.pub == fl.y).mean()) if len(fl) else None
        o["runs"] = int(len(f1))
        ok = g.upwon.notna()
        if ok.any():
            gg = g[ok]
            won = np.where(gg.is_up == 1, gg.upwon.astype(bool), ~gg.upwon.astype(bool))
            cost = (gg.price * gg.shares).sum()
            o["return_per_dollar"] = float(((won * gg.shares).sum() - cost) / cost) if cost > 0 else None
            wn = gg.assign(sh=np.where(gg.is_up == 1, gg.shares, -gg.shares)).groupby("cid").agg(net=("sh", "sum"), up=("upwon", "first"))
            wn = wn[wn.net != 0]
            o["window_net_side_wins"] = float(((wn.net > 0) == wn.up.astype(bool)).mean()) if len(wn) else None
            o["outcome_coverage"] = float(ok.mean())
        nm = g[~g.dec]
        o["not_decided_n"] = int(len(nm))
        o["not_decided_posture"] = float((nm.post == nm.y).mean()) if len(nm) else None
        return o
    res["side"] = {k: sm(g) for k, g in D.groupby("fold")}
    res["side_by_week"] = {int(k): sm(g) for k, g in D.groupby("week")}
    res["side_per_wallet"] = {k: {CL[a]: sm(g2) for a, g2 in g.groupby("wallet")} for k, g in D.groupby("fold")}
    # presence by week
    panel["week"] = ((panel.start - 1789084800) // (7 * 86400)).astype(int)
    res["presence_by_week"] = {int(k): {"auc": fr._auc(g.y, g["p_" + fr.MODEL]), "auc_activity": fr._auc(g.y, g["p_" + fr.BASELINE]), "windows": int(g.cid.nunique())}
                               for k, g in panel.groupby("week")}
    (HERE.parent / "results/iter13_stable_score.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: res[k] for k in ("windows", "tape_rows", "maker_fills", "taker_fills")}, default=float))
    for k, v in res["presence"].items():
        print("presence", k, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items() if a != "per_wallet"})
    for k, v in res["side"].items():
        print("side", k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items()})
    for k, v in res["side_by_week"].items():
        print("week", k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items() if a in ("n", "public", "cheaper", "entry_run_public", "return_per_dollar", "window_net_side_wins")},
              res["presence_by_week"].get(k))


if __name__ == "__main__":
    main()
