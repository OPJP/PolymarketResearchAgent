"""Primary metric (pre-registered): presence AUC over (market, 60-s bin) cells with >= 1 public taker print.

Cells: every market of the sampled events (tape_sample_<p0>_<p1>.json), bins in [gameStart-2h, gameStart+5h]
with >= 1 taker print (any wallet) in the bin. Label: RN1 has >= 1 maker row in the bin.
Features use only rows with ts < bin start, never RN1's rows and never rows of transactions RN1 is in.
Feature sets:
  ACT  (activity-only baseline): other traders' prints and timing, time in game, price level.
  LIST (ACT + listing metadata): sportsMarketType, family, secondsDelay, negRisk, rfqEnabled, event size.
  FULL (LIST + sibling-market activity + pair-price structure).
Writes .cache/re/rn1-inplay-maker/cells_<p0>_<p1>.parquet.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import C, W, parse_ts  # noqa: E402

BIN = 60
ACT = ["n_tk_1", "n_tk_5", "n_tk_15", "n_tk_60", "v_tk_5", "v_tk_15", "since_tk", "n_mk_5", "n_mk_15", "nw_tk_15",
       "p_last", "p_dist", "rng_5", "rng_15", "jmp_1", "jmp_5", "t_rel", "since_open"]
LIST = ["smt", "fam", "delay", "negrisk", "rfq", "n_mk_event", "is_main", "line_abs"]
FULL = ["ev_tk_5", "ev_tk_15", "ev_jmp_5", "pair_sum", "p_tok_gap", "since_jmp3"]
SPREAD = ["eff_spread_5", "n_lvls_5", "last_dir"]  # tape proxies of the quoted spread (added in iteration 1)
SMT = {"moneyline": 1, "totals": 2, "spreads": 3, "soccer_exact_score": 4, "first_half_totals": 5, "soccer_halftime_result": 6,
       "both_teams_to_score": 7, "child_moneyline": 8, "soccer_team_totals": 9, "map_handicap": 10}
FAMS = {"atp": 1, "wta": 2, "nfl": 3, "cfb": 4, "cs2": 5, "nba": 6, "mlb": 7, "nhl": 8, "lol": 9, "dota2": 10, "val": 11}


def fam_code(slug):
    p = str(slug).split("-")[0]
    return FAMS.get(p, 0)


def market_cells(cid, tokens, gst, tp, meta):
    """tp: tape rows of this market (all wallets)."""
    a, b = gst - 7200, gst + 5 * 3600
    tp = tp[(tp["ts"] >= a) & (tp["ts"] < b)]
    if tp.empty:
        return None
    rn_tx = set(tp.loc[tp["wallet"] == W, "tx"])
    lab_ts = tp.loc[(tp["wallet"] == W) & (tp["role"] == "maker"), "ts"].to_numpy()
    all_tk_ts = tp.loc[tp["role"] == "taker", "ts"].to_numpy()
    ft = tp[~tp["tx"].isin(rn_tx)]
    tk = ft[ft["role"] == "taker"].sort_values("ts")
    mk = ft[ft["role"] == "maker"].sort_values("ts")
    bins = np.unique((all_tk_ts - a) // BIN)
    if len(bins) == 0:
        return None
    t = a + bins * BIN  # bin starts
    tk_ts = tk["ts"].to_numpy()
    p0 = np.where(tk["outcome"].to_numpy() == 0, tk["price"].to_numpy(), 1 - tk["price"].to_numpy())
    vol = (tk["price"] * tk["size"]).to_numpy()
    mk_ts = mk["ts"].to_numpy()
    out = {"cid": cid, "t": t, "y": np.isin(t, a + np.unique((lab_ts - a) // BIN) * BIN).astype(np.int8)}

    def cnt(ts, w, h):
        return np.searchsorted(ts, t, side="left") - np.searchsorted(ts, t - h, side="left") if w is None else \
            (np.concatenate([[0], np.cumsum(w)])[np.searchsorted(ts, t, side="left")] -
             np.concatenate([[0], np.cumsum(w)])[np.searchsorted(ts, t - h, side="left")])
    for m in (1, 5, 15, 60):
        out[f"n_tk_{m}"] = cnt(tk_ts, None, m * 60)
    out["v_tk_5"] = cnt(tk_ts, vol, 300)
    out["v_tk_15"] = cnt(tk_ts, vol, 900)
    out["n_mk_5"] = cnt(mk_ts, None, 300)
    out["n_mk_15"] = cnt(mk_ts, None, 900)
    i_last = np.searchsorted(tk_ts, t, side="left") - 1
    if len(tk_ts) == 0:
        return None
    out["since_tk"] = np.where(i_last >= 0, t - tk_ts[np.maximum(i_last, 0)], 99999.0)
    pl = np.where(i_last >= 0, p0[np.maximum(i_last, 0)], np.nan)
    out["p_last"] = pl
    out["p_dist"] = np.abs(pl - 0.5)
    # price ranges and jumps from causal series
    s = pd.Series(p0, index=pd.to_datetime(tk_ts, unit="s"))
    for m in (5, 15):
        lo = np.searchsorted(tk_ts, t - m * 60, side="left")
        hi = np.searchsorted(tk_ts, t, side="left")
        rng = np.full(len(t), np.nan)
        for k in range(len(t)):
            if hi[k] > lo[k]:
                seg = p0[lo[k]:hi[k]]
                rng[k] = seg.max() - seg.min()
        out[f"rng_{m}"] = rng
    for m in (1, 5):
        j = np.searchsorted(tk_ts, t - m * 60, side="left") - 1
        prev = np.where(j >= 0, p0[np.maximum(j, 0)], np.nan)
        out[f"jmp_{m}"] = np.abs(pl - prev)
    # distinct taker wallets in 15 min
    tw = tk["wallet"].to_numpy()
    lo = np.searchsorted(tk_ts, t - 900, side="left")
    hi = np.searchsorted(tk_ts, t, side="left")
    out["nw_tk_15"] = np.array([len(set(tw[l:h])) for l, h in zip(lo, hi)])
    out["t_rel"] = (t - gst) / 60.0
    first = tk_ts[0] if len(tk_ts) else a
    out["since_open"] = (t - first) / 60.0
    # time since a 3-cent move between consecutive prints (causal)
    dp = np.abs(np.diff(p0, prepend=p0[0] if len(p0) else 0))
    jts = tk_ts[dp >= 0.03]
    jj = np.searchsorted(jts, t, side="left") - 1
    out["since_jmp3"] = np.where(jj >= 0, t - jts[np.maximum(jj, 0)], 99999.0) if len(jts) else np.full(len(t), 99999.0)
    # tape proxies of the spread: last taker-buy minus last taker-sell price (outcome-0 frame) within 5 min
    dirs = np.where(((tk["outcome"].to_numpy() == 0) & (tk["side"].to_numpy() == "BUY")) |
                    ((tk["outcome"].to_numpy() == 1) & (tk["side"].to_numpy() == "SELL")), 1, -1)
    eff = np.full(len(t), np.nan)
    nlv = np.zeros(len(t))
    ldir = np.zeros(len(t))
    lo5 = np.searchsorted(tk_ts, t - 300, side="left")
    hi5 = np.searchsorted(tk_ts, t, side="left")
    for k in range(len(t)):
        if hi5[k] > lo5[k]:
            seg_p, seg_d = p0[lo5[k]:hi5[k]], dirs[lo5[k]:hi5[k]]
            nlv[k] = len(np.unique(np.round(seg_p, 3)))
            ldir[k] = seg_d[-1]
            bu, se = seg_p[seg_d == 1], seg_p[seg_d == -1]
            if len(bu) and len(se):
                eff[k] = bu[-1] - se[-1]
    out["eff_spread_5"] = eff
    out["n_lvls_5"] = nlv
    out["last_dir"] = ldir
    # pair structure: last print price of each token
    lt = []
    for o in (0, 1):
        sub = tk[tk["outcome"] == o]
        ts_o = sub["ts"].to_numpy()
        pr_o = sub["price"].to_numpy()
        io = np.searchsorted(ts_o, t, side="left") - 1
        lt.append(np.where(io >= 0, pr_o[np.maximum(io, 0)], np.nan) if len(ts_o) else np.full(len(t), np.nan))
    out["pair_sum"] = lt[0] + lt[1]
    out["p_tok_gap"] = np.abs(lt[0] - (1 - lt[1]))
    df = pd.DataFrame(out)
    for k, v in meta.items():
        df[k] = v
    return df, tk_ts, p0


def event_cells(e, tp):
    """Cells of one event (gamma event dict, its tape rows). Used by build() and by final_rule.evaluate()."""
    out_rows = []
    mkts = [m for m in (e.get("markets") or []) if m.get("conditionId") in set(tp["cid"])]
    allm = e.get("markets") or []
    ev_parts, ev_tk = [], []
    for m in mkts:
        try:
            tokens = json.loads(m.get("clobTokenIds") or "[]")
        except ValueError:
            continue
        gst = parse_ts(m.get("gameStartTime")) or parse_ts(e.get("startTime")) or parse_ts(m.get("endDate"))
        if gst is None or len(tokens) != 2:
            continue
        smt = m.get("sportsMarketType")
        line = m.get("line")
        try:
            line = abs(float(line)) if line not in (None, "") else -1.0
        except (TypeError, ValueError):
            line = -1.0
        meta = {"smt": SMT.get(smt, 0), "fam": fam_code(e.get("slug")), "delay": float(m.get("secondsDelay") or 0),
                "negrisk": int(bool(m.get("negRisk"))), "rfq": int(bool(m.get("rfqEnabled"))), "n_mk_event": len(allm),
                "is_main": int(smt == "moneyline"), "line_abs": line, "event": e.get("slug"), "gst": gst}
        r = market_cells(m["conditionId"], tokens, gst, tp[tp["cid"] == m["conditionId"]], meta)
        if r is None:
            continue
        df, tk_ts, p0s = r
        ev_parts.append(df)
        ev_tk.append((tk_ts, p0s))
    if not ev_parts:
        return []
    # sibling (event-level, other markets) activity
    allts = np.sort(np.concatenate([x[0] for x in ev_tk])) if ev_tk else np.array([])
    for i, df in enumerate(ev_parts):
        t = df["t"].to_numpy()
        own = ev_tk[i][0]
        for m in (5, 15):
            tot = np.searchsorted(allts, t, side="left") - np.searchsorted(allts, t - m * 60, side="left")
            mine = np.searchsorted(own, t, side="left") - np.searchsorted(own, t - m * 60, side="left")
            df[f"ev_tk_{m}"] = tot - mine
        # max 5-min jump across sibling markets
        jm = np.zeros(len(t))
        for k, (ts_k, p_k) in enumerate(ev_tk):
            if k == i or len(ts_k) == 0:
                continue
            a1 = np.searchsorted(ts_k, t, side="left") - 1
            a0 = np.searchsorted(ts_k, t - 300, side="left") - 1
            v = np.where((a1 >= 0) & (a0 >= 0), np.abs(p_k[np.maximum(a1, 0)] - p_k[np.maximum(a0, 0)]), 0)
            jm = np.maximum(jm, v)
        df["ev_jmp_5"] = jm
        out_rows.append(df)
    return out_rows


def build(p0, p1, files=None):
    sample = []
    files = files or sorted(C.glob(f"tape_sample_{p0}_{p1}*.json"))  # the pre-registered sample and the extra disjoint ones
    for g in files:
        sample += [x for x in json.load(open(g))["sample"] if x not in sample]
    rows = []
    for slug in sample:
        f = C / "tapes" / f"{slug}.parquet"
        g = C / "gamma" / f"{slug}.json"
        if not f.exists() or not g.exists():
            continue
        e = json.load(open(g))
        tp = pd.read_parquet(f)
        if e is None or tp.empty:
            continue
        rows += event_cells(e, tp)
    cells = pd.concat(rows, ignore_index=True)
    cells.to_parquet(C / f"cells_{p0}_{p1}.parquet", index=False)
    return cells


if __name__ == "__main__":
    p0, p1 = int(sys.argv[1]), int(sys.argv[2])
    names = sys.argv[3:]  # optional sample-file names (e.g. tape_sample_<p0>_<p1>.json) to restrict the build
    c = build(p0, p1, [C / n for n in names] or None)
    print(len(c), c["y"].mean().round(4), c["event"].nunique(), c["cid"].nunique())
