"""X204 / X210 (information P1, mechanics P2 of the iteration-14 panel): the operator's GRID-event quotes against the
sports socket's per-round score clock, on development units (10-31 12-18, 11-01 06-12). Pre-registered in NOTES
iteration 15 before the alignment was computed.

Inputs: iter15/socket_rounds.parquet, iter15/op_trades.parquet (grid_socket_data.py); calldata of 0xd2bb9459's fill txs
(publicnode, decoded with fetch_calldata.rows_of; cached in iter15/op_calldata.parquet).
Output: results/grid_socket_clock.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
CODE = ROOT / "research/reverse_engineering/tommy-cs2-maker/code"
sys.path.insert(0, str(CODE))
from fetch_calldata import rows_of  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker/iter15"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
D2 = "0xd2bb94594762beda042e596598800d83f781bd8e"
OPS = {"0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2", D2, "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14",
       "0x10d79cc72df76ea3d6bdc2d54f41dbcbbb18bbf6", "0x52661b8e13158f23d94a9e8302ab0295704c22ac",
       "0x671190333b064b0899b4ac1aec86744b1f82885b"}
GRID_EVENTS = ["cs2-fokus-baks-2026-10-31", "cs2-jjh-bmb-2026-10-31", "cs2-bca-pha-2026-11-01", "cs2-jjh-mzp-2026-11-01"]


def auc(s, y):
    from scipy.stats import rankdata
    s, y = np.asarray(s, float), np.asarray(y, bool)
    k = np.isfinite(s)
    s, y = s[k], y[k]
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return None
    r = rankdata(s)
    return round(float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)), 3)


def decode(txs):
    p = OUT / "op_calldata.parquet"
    have = pd.read_parquet(p) if p.exists() else pd.DataFrame()
    todo = sorted(set(txs) - (set(have.tx) if len(have) else set()))
    recs = []
    cli = httpx.Client(timeout=60)
    for i in range(0, len(todo), 40):
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(todo[i:i + 40])]
        for _ in range(3):
            try:
                r = cli.post("https://polygon-bor-rpc.publicnode.com", json=body).json()
                break
            except Exception:  # noqa: BLE001
                r = []
        for x in r if isinstance(r, list) else []:
            if x.get("result"):
                recs += rows_of(x["result"])
    new = pd.DataFrame(recs)
    if len(new):
        keep = [c for c in ["tx", "block", "idx", "maker", "side", "token_id", "price", "shares", "sign_ms", "fill", "salt"] if c in new.columns]
        new = new[keep]
        have = pd.concat([have, new], ignore_index=True) if len(have) else new
        have.to_parquet(p, index=False)
    return have


def team_paths(ev, tr, cd):
    """Per event: token A / B of each market (outcomes order), operator bursts (V) in team-A space, clean prints."""
    out = []
    for cid, g in tr[tr.event == ev].groupby("cid"):
        outs = json.loads(g.outcomes.iloc[0]) if isinstance(g.outcomes.iloc[0], str) else list(g.outcomes.iloc[0])
        tok = {}
        for a, oi in zip(g.asset.astype(str), g.outcomeIndex.astype(int)):
            tok[a] = oi
        smt = g.smt.iloc[0]
        # clean prints: taker rows of txs without an operator row
        optx = set(g.loc[g.proxyWallet.isin(OPS), "transactionHash"])
        pt = g[g.is_taker_row & ~g.transactionHash.isin(optx)].sort_values("timestamp")
        pA = np.where(pt.outcomeIndex.astype(int) == 0, pt.price.astype(float), 1 - pt.price.astype(float))
        # operator orders (calldata) on this market's tokens
        c = cd[cd.token_id.astype(str).isin(tok) & (cd.maker.str.lower() == D2) & (cd.sign_ms > 1.7e12)].copy()
        c["oi"] = c.token_id.astype(str).map(tok)
        c = c.drop_duplicates(["salt", "sign_ms"]).sort_values("sign_ms")
        out.append({"cid": cid, "smt": smt, "outcomes": outs, "pt_ts": pt.timestamp.to_numpy(float), "pA": pA,
                    "orders": c})
    return out


def bursts(c):
    """Bursts per token: orders chained within 50 ms; top price; returns rows (t_ms, oi, top)."""
    rows = []
    for oi, g in c.groupby("oi"):
        s = g.sign_ms.to_numpy(float)
        p = g.price.to_numpy(float)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and s[j + 1] - s[j] <= 50:
                j += 1
            rows.append((s[i], int(oi), float(p[i:j + 1].max()), j - i + 1))
            i = j + 1
    return pd.DataFrame(rows, columns=["t", "oi", "top", "n"]).sort_values("t")


def value_A(b):
    """Team-A value path from bursts on either token: token-0 top -> V_A = top; token-1 top -> V_A = 1 - top - 0.02
    (pair constant ~0.98 of its tops). Returns arrays (t_s, VA, src_token)."""
    va = np.where(b.oi == 0, b.top, 0.98 - b.top)
    return b.t.to_numpy(float) / 1000.0, va, b.oi.to_numpy()


def step_at(ts, val, t):
    k = np.searchsorted(ts, t, side="right") - 1
    return val[k] if k >= 0 else np.nan


def main():
    s = pd.read_parquet(OUT / "socket_rounds.parquet")
    tr = pd.read_parquet(OUT / "op_trades.parquet")
    d2tx = tr.loc[(tr.proxyWallet == D2) & tr.event.isin(GRID_EVENTS), "transactionHash"].unique()
    cd = decode(d2tx)
    print("decoded rows", len(cd), "d2 orders", int((cd.maker.str.lower() == D2).sum()))
    res = {"events": {}}
    allr = []
    for ev in GRID_EVENTS:
        g = s[s.event == ev].sort_values("t")
        home, away = g.home.iloc[0], g.away.iloc[0]
        g = g[g.score.notna()]
        sc = g.score.str.split("|", expand=True)
        g = g.assign(rs=sc[0], ms=sc[1])
        g = g[g.rs.str.match(r"^\d+-\d+$") & (g.rs != "000-000")]
        ch = g[(g.rs != g.rs.shift()) | (g.ms != g.ms.shift())].copy()
        rr = ch.rs.str.split("-", expand=True).astype(int)
        ch["h"], ch["a"] = rr[0].to_numpy(), rr[1].to_numpy()
        ch["mapn"] = ch.period.str.split("/").str[0].astype(int)
        ch["dh"], ch["da"] = ch.h.diff(), ch.a.diff()
        ch["map_chg"] = ch.mapn != ch.mapn.shift()
        rounds = ch[(~ch.map_chg) & (((ch.dh == 1) & (ch.da == 0)) | ((ch.dh == 0) & (ch.da == 1)))].copy()
        rounds["home_won"] = rounds.dh == 1
        rounds["t_s"] = rounds.t / 1000.0
        rounds["t_prev"] = ch.t.shift().reindex(rounds.index) / 1000.0
        gaps = np.diff(ch.t.to_numpy(float) / 1000.0)
        paths = team_paths(ev, tr, cd)
        info = {"home": home, "away": away, "score_changes": int(len(ch)), "round_ticks": int(len(rounds)),
                "tick_gap_mod_20_2": [round(float(x), 2) for x in np.quantile(np.mod(gaps[gaps < 300], 20.2), [0.1, 0.5, 0.9])] if len(gaps) else None,
                "markets": {}}
        for P in paths:
            outs = P["outcomes"]
            # team A = outcomes[0]; does it match home? (first-word match)
            a_is_home = str(outs[0]).split()[0].lower()[:4] in str(home).lower() or str(home).lower()[:4] in str(outs[0]).lower()
            if P["smt"] == "child_moneyline":
                # map markets: only rounds of the matching map (Map 1 / Map 2 / Map 3 in order of cid listing is unknown):
                pass
            b = bursts(P["orders"]) if len(P["orders"]) else pd.DataFrame(columns=["t", "oi", "top", "n"])
            tV, VA, _ = value_A(b) if len(b) else (np.array([]), np.array([]), np.array([]))
            info["markets"][P["cid"][:10]] = {"smt": P["smt"], "outcomes": outs, "a_is_home": bool(a_is_home), "orders": int(len(P["orders"])),
                                              "bursts": int(len(b)), "prints": int(len(P["pt_ts"]))}
            for r in rounds.itertuples():
                allr.append({"event": ev, "cid": P["cid"], "smt": P["smt"], "mapn": r.mapn, "t": r.t_s, "t_prev": r.t_prev,
                             "A_won": bool(r.home_won == a_is_home), "tV": tV, "VA": VA, "tp": P["pt_ts"], "pA": P["pA"]})
        res["events"][ev] = info
    # map markets: identify which map each child_moneyline is by activity overlap of its prints with the map's rounds
    R = pd.DataFrame(allr)
    keep = []
    for (ev, cid), g in R.groupby(["event", "cid"]):
        if g.smt.iloc[0] == "moneyline":
            keep.append(g)
            continue
        tp = g.tp.iloc[0]
        best, bm = -1, None
        for mp, h in g.groupby("mapn"):
            lo, hi = h.t.min() - 60, h.t.max()
            n = int(((tp >= lo) & (tp <= hi)).sum())
            if n > best:
                best, bm = n, mp
        keep.append(g[g.mapn == bm])
    R = pd.concat(keep, ignore_index=True)

    def winner_change(t_arr, v_arr, a, b, A_won):
        va, vb = step_at(t_arr, v_arr, a), step_at(t_arr, v_arr, b)
        if not (np.isfinite(va) and np.isfinite(vb)):
            return np.nan
        return (vb - va) * (1 if A_won else -1)

    def raw_change(t_arr, v_arr, a, b):
        va, vb = step_at(t_arr, v_arr, a), step_at(t_arr, v_arr, b)
        return vb - va if (np.isfinite(va) and np.isfinite(vb)) else np.nan

    # fit L per event on the clean print only
    Ls = {}
    for ev, g in R.groupby("event"):
        sc_ = {}
        for L in range(0, 62, 2):
            vals = [winner_change(r.tp, r.pA, r.t - L - 20, r.t - L, r.A_won) for r in g.itertuples()]
            vals = [x for x in vals if np.isfinite(x)]
            sc_[L] = float(np.mean(vals)) if vals else -9
        Ls[ev] = max(sc_, key=sc_.get)
        res["events"][ev]["L_fit_print"] = Ls[ev]
        res["events"][ev]["L_profile_print_c"] = {k: round(v * 100, 2) for k, v in sc_.items() if k % 10 == 0}
    rows = []
    for r in R.itertuples():
        L = Ls[r.event]
        e_hi, e_lo = r.t - L, r.t - L - 20
        st = r.t_prev - L + 5 if np.isfinite(r.t_prev) else np.nan
        w = {"mid": (st, e_lo - 5), "end": (e_lo - 5, e_hi + 5), "after": (e_hi + 5, e_hi + 25)}
        rec = {"event": r.event, "smt": r.smt, "A_won": r.A_won, "dur": (e_lo - 5) - st if np.isfinite(st) else np.nan}
        for k, (a, b) in w.items():
            if not (np.isfinite(a) and b > a):
                rec[f"V_{k}"], rec[f"P_{k}"], rec[f"Vr_{k}"], rec[f"Pr_{k}"] = (np.nan,) * 4
                continue
            rec[f"V_{k}"] = winner_change(r.tV, r.VA, a, b, r.A_won)
            rec[f"P_{k}"] = winner_change(r.tp, r.pA, a, b, r.A_won)
            rec[f"Vr_{k}"] = raw_change(r.tV, r.VA, a, b)
            rec[f"Pr_{k}"] = raw_change(r.tp, r.pA, a, b)
        # number of V changes (bursts on either token with a new top) in the mid window
        if np.isfinite(st) and len(r.tV):
            m = (r.tV >= st) & (r.tV < e_lo - 5)
            rec["V_moves_mid"] = int(m.sum())
            m2 = (r.tV >= e_lo - 5) & (r.tV < e_hi + 5)
            rec["V_moves_end"] = int(m2.sum())
        rows.append(rec)
    X = pd.DataFrame(rows)
    X = X[X.dur > 10]
    out = {}
    for name, sub in (("all", X), ("map_books", X[X.smt == "child_moneyline"]), ("match_books", X[X.smt == "moneyline"])):
        o = {"rounds": int(len(sub))}
        for k in ("mid", "end", "after"):
            v, p = sub[f"V_{k}"].dropna(), sub[f"P_{k}"].dropna()
            o[f"V_{k}_c"] = round(float(v.mean() * 100), 2) if len(v) else None
            o[f"P_{k}_c"] = round(float(p.mean() * 100), 2) if len(p) else None
            o[f"n_{k}"] = int(len(v))
        ok = sub["Vr_mid"].notna() & sub["Pr_mid"].notna()
        o["mid_auc_V"] = auc(sub.loc[ok, "Vr_mid"], sub.loc[ok, "A_won"])
        o["mid_auc_P"] = auc(sub.loc[ok, "Pr_mid"], sub.loc[ok, "A_won"])
        o["mid_auc_n"] = int(ok.sum())
        okv = sub["Vr_mid"].notna()
        o["mid_auc_V_all"] = auc(sub.loc[okv, "Vr_mid"], sub.loc[okv, "A_won"])
        tot = sub[["V_mid", "V_end", "V_after"]].dropna()
        if len(tot):
            s_ = tot.clip(lower=None).sum()
            denom = float(s_.abs().sum())
            o["V_share_by_window"] = {k: round(float(s_[f"V_{k}"] / denom), 3) if denom > 0 else None for k in ("mid", "end", "after")}
        if "V_moves_mid" in sub:
            o["V_moves_per_round_mid"] = round(float(sub.V_moves_mid.mean()), 2)
            o["V_moves_per_round_end"] = round(float(sub.V_moves_end.mean()), 2)
            o["mid_window_s"] = round(float(sub.dur.mean()), 1)
        out[name] = o
    res["rounds"] = out
    # G2: within one tick of the last clean print at signing, by token; lead / follow vs >= 2c print moves
    g2 = []
    lf = {"V_then_print_same_dir_10s": 0, "print_then_V_same_dir_10s": 0, "V_changes": 0}
    for ev in GRID_EVENTS:
        for P in team_paths(ev, tr, cd):
            c = P["orders"]
            if not len(c) or not len(P["pt_ts"]):
                continue
            tp, pA = P["pt_ts"], P["pA"]
            k = np.searchsorted(tp, c.sign_ms.to_numpy(float) / 1000.0, side="left") - 1
            lp = np.where(k >= 0, pA[np.maximum(k, 0)], np.nan)
            lp = np.where(c.oi.to_numpy() == 0, lp, 1 - lp)
            g2.append(pd.DataFrame({"p": c.price.to_numpy(float), "a": np.round(lp, 2), "smt": P["smt"]}))
            b = bursts(c)
            for oi, h in b.groupby("oi"):
                tops = h.top.to_numpy()
                tt = h.t.to_numpy() / 1000.0
                for i in range(1, len(h)):
                    d = tops[i] - tops[i - 1]
                    if abs(d) < 0.01 - 1e-9:
                        continue
                    lf["V_changes"] += 1
                    sgn = np.sign(d) * (1 if oi == 0 else -1)  # team-A direction
                    t0 = tt[i]
                    pa = step_at(tp, pA, t0)
                    pb = step_at(tp, pA, t0 + 10)
                    pm = step_at(tp, pA, t0 - 10)
                    if np.isfinite(pa) and np.isfinite(pb) and (pb - pa) * sgn >= 0.02 - 1e-9:
                        lf["V_then_print_same_dir_10s"] += 1
                    if np.isfinite(pa) and np.isfinite(pm) and (pa - pm) * sgn >= 0.02 - 1e-9:
                        lf["print_then_V_same_dir_10s"] += 1
    if g2:
        G = pd.concat(g2).dropna()
        off = (G.p - G.a).round(2)
        res["G2"] = {"orders": int(len(G)), "within_tick_print": round(float((off.abs() <= 0.01 + 1e-9).mean()), 3),
                     "median_offset_c": round(float(off.median() * 100), 1),
                     "within_tick_print_minus1c": round(float(((off + 0.01).abs() <= 0.01 + 1e-9).mean()), 3),
                     "offset_q10_q50_q90_c": [round(float(x * 100), 1) for x in off.quantile([0.1, 0.5, 0.9])],
                     "whole_cent_share": round(float((np.abs(G.p * 100 - np.round(G.p * 100)) < 1e-6).mean()), 3),
                     "lead_follow": lf}
    (RES / "grid_socket_clock.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res["rounds"], indent=1))
    print(json.dumps(res.get("G2"), indent=1))
    print({e: (v["L_fit_print"], v["round_ticks"], v["tick_gap_mod_20_2"]) for e, v in res["events"].items()})


if __name__ == "__main__":
    main()
