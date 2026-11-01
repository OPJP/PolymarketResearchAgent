"""X229 step 1 (iteration 16): copy of iteration-15 decided_early.py with TOMMY_CLOCK_ANCHOR=printmatch, i.e. every
wallet-free taker print re-stamped at its CLOB match, min(block, taker sign + 1.04 s) when 0 <= block - sign <= 5 s.
X209 (mechanics panel iter-14 P1): decided-early rounds. Copy of iter14/round_clock.py (same tracker, same
windows, anchor set from TOMMY_CLOCK_ANCHOR, default print) that also stores, per round with both ends snapped, the bo3
end class (CT_elim_T / T_elim_CT = the last kill ends the round; defuse_after_T_wiped / bombed_CT_alive = decided before
the official end; others), deaths per side, plants, and V's / the print's winner-signed changes in finer windows
around the anchor e_r (mid, -10..-1, -1..+4, +4..+20, +20..+40 s). R predicts a smaller before-anchor share of V's
move in decided-early rounds than in elimination rounds; K predicts no class difference.
Output: .cache/re/tommy-cs2-maker/iter15/decided_early_rows.parquet, results/decided_early_{anchor}.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter12"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter2"))
import round_markov_fit as R  # noqa: E402
from polyrea.adapters.http import shared_client  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
GUARDS = (10, 20, 30, 45)
import os as _os
WLO, WHI = (float(v) for v in _os.environ.get("TOMMY_CLOCK_WIN", "15,30").split(","))
ANCHOR = _os.environ.get("TOMMY_CLOCK_ANCHOR", "print")
EARLY = (30, 60)  # early windows: last burst within E s after the round's first burst (and before the guard-free end)  # seconds before the print-inferred end of the round (the next segment's first burst)


def auc(s, y):
    s, y = np.asarray(s, float), np.asarray(y, int)
    if y.min() == y.max():
        return np.nan
    from scipy.stats import rankdata
    r = rankdata(s)
    n1 = y.sum()
    n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter4"))
from queue_replay import load_record  # noqa: E402
GG = {"0xf1ee4842fa0c7283632185e42577027452d4519c", "0x8a80528dce46711a54aa3455c2cc81dea51e11c5",
      "0xddb6e6246546230503f153506ac1e9914978b9b3", "0x7c8cc25556ef9c0962b41d0ebb74d2fd17a42d81",
      "0x67706ec33d1bc5ed0db5cf0681b74b57b64ec3bd", "0xc70974218b9c6570f7701cd6fafc04ed490fbda9"}


_SIGN = None


def restamp(d):
    """match-time stamp of each print: min(block, taker sign + 1.04 s) if 0 <= block - sign <= 5 s, else the block."""
    global _SIGN
    if _SIGN is None:
        cd0, _ = load_record()
        tk0 = cd0[(cd0.idx == -1) & (cd0.sign_ms > 1.7e12)].drop_duplicates("tx")
        _SIGN = dict(zip(tk0.tx, tk0.sign_ms.astype(float) / 1000.0))
    s = d.transactionHash.map(_SIGN).astype(float).to_numpy()
    b = d.timestamp.astype(float).to_numpy()
    ok = np.isfinite(s) & (b - s >= 0) & (b - s <= 5)
    m = np.where(ok, np.minimum(b, s + 1.04), b)
    d = d.assign(timestamp=m, restamped=ok)
    return d.sort_values("timestamp")


def clusters_by_cid():
    GP = set(json.load(open(RES / "selection_groupP.json"))["members"])
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "event"]).drop_duplicates("cid")
    ev_of = dict(zip(o.cid, o.event))
    wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx"]).tx)
    cd, _ = load_record()
    tk = cd[(cd.idx == -1) & ~cd.tx.isin(wtx)].drop_duplicates("tx")
    tk = tk[(tk.sign_ms > 1.7e12) & tk.cid.isin(set(o.cid))].copy()
    tk["event"] = tk.cid.map(ev_of)
    tk["mk"] = tk.maker.str.lower()
    tk["team"] = np.where(tk.side == 0, np.where(tk.oi == 0, 1, -1), np.where(tk.oi == 0, -1, 1))
    inf = tk[tk.mk.isin(GP if ANCHOR == "takes" else (GP | GG))].sort_values("sign_ms")
    cl = {}
    for ev, g in inf.groupby("event"):
        s, m, tm = g.sign_ms.to_numpy(), g.mk.to_numpy(), g.team.to_numpy()
        i, out = 0, []
        while i < len(g):
            j = i
            while j + 1 < len(g) and s[j + 1] - s[i] <= 300:
                j += 1
            if len(set(m[i:j + 1])) >= (1 if ANCHOR == "takes" else 2):
                out.append((s[i] / 1000, float(np.sign(tm[i:j + 1].sum())) or float(tm[i])))
                i = j + 1
            else:
                i += 1
        cl[ev] = np.array(out) if out else np.zeros((0, 2))
    return cl, ev_of


def main():
    CL, EV = clusters_by_cid()
    snaps_all = []
    h = shared_client()
    slugs = R.bo3_maps(h)
    mk = json.load(open(OUT / "markets_dev.json"))
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "price", "cid", "oi", "role"])
    o = o[(o.role == "maker") & (o.sign_ms / 1000 < R.H)]
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    bad = set(cd.loc[cd.maker == R.WALLET, "tx"])
    rows = []
    nmaps = 0
    for cid, x in mk.items():
        if x.get("sportsMarketType") != "child_moneyline" or not x.get("question", "").startswith("Counter-Strike"):
            continue
        mm = re.search(r"Map (\d)", x["question"])
        if not mm:
            continue
        mapno = int(mm.group(1))
        oo = o[o.cid == cid].sort_values("sign_ms")
        if len(oo) < 30:
            continue
        outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
        a, b = R.norm(outs[0])[:6], R.norm(outs[1])[:6]
        a_6, b_6 = a, b
        cand = [s for s in slugs if a in R.norm(s) and b in R.norm(s)]
        if not cand:
            continue
        g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{cand[0]}", {"with": "games"}, adapter="bo3gg.match", max_age=None)
        gm = [yy for yy in (g.get("games") or []) if yy.get("number") == mapno]
        if not gm:
            continue
        r, _ = h.get_json(f"https://api.bo3.gg/api/v1/games/{gm[0]['id']}/rounds", {}, adapter="bo3gg.rounds", max_age=None)
        rounds = r.get("game_rounds") if isinstance(r, dict) else None
        if not rounds or len(rounds) < 13:
            continue
        rounds = sorted(rounds, key=lambda z: z["round_number"])
        wn = [R.norm(z.get("winner_clan_name")) for z in rounds]
        fa, fb = R.norm(outs[0]), R.norm(outs[1])
        isa = np.array([(w[:6] == a) or (len(w) >= 3 and (w in fa or fa in w)) for w in wn])
        isb = np.array([(w[:6] == b) or (len(w) >= 3 and (w in fb or fb in w)) for w in wn])
        if (isa & isb).any() or (isa | isb).mean() < 0.95 or isa.sum() == 0 or isb.sum() == 0:
            continue
        win = isa.astype(int)
        oo = oo.assign(tok=oo.oi.astype(int))
        oo = oo[(oo.price > 0.06) & (oo.price < 0.94)]
        if len(oo) < 30:
            continue
        oo = oo.sort_values(["tok", "sign_ms"])
        newb = (oo.tok.diff() != 0) | (oo.sign_ms.diff() > R.BURST_MS)
        oo["bid"] = newb.cumsum()
        bb = oo.groupby("bid").agg(sign_ms=("sign_ms", "min"), price=("price", "max"), tok=("tok", "first")).sort_values("sign_ms")
        y = np.where(bb.tok == 0, bb.price, 1 - bb.price).astype(float)
        tok = bb.tok.to_numpy(int)
        tt = bb.sign_ms.to_numpy() / 1000.0
        tp = R.TAPES / f"{cid}_tkw.parquet"
        if not tp.exists():
            continue
        d = pd.read_parquet(tp)
        d = d[(d.timestamp < R.H) & ~d.transactionHash.isin(bad)].sort_values("timestamp")
        if ANCHOR == "printmatch":
            d = restamp(d)
        if len(d) < 20:
            continue
        ts = d.timestamp.to_numpy(float)
        pa = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        j = np.searchsorted(ts, tt, side="right") - 1
        ok = j >= 0
        if ok.sum() < 30:
            continue
        y, tok, tt, yp = y[ok], tok[ok], tt[ok], pa[j[ok]]
        path = None  # the print HMM is not needed for the snapped clock
        nmaps += 1
        # wallet token offsets: put both tokens on one scale (subtract the per-token median gap to the print)
        off = {s: float(np.median((y - yp)[tok == s])) if (tok == s).any() else 0.0 for s in (0, 1)}
        yc = y - np.array([off[s] for s in tok])
        cc = CL.get(EV.get(cid), np.zeros((0, 2)))
        if ANCHOR in ("print", "printmatch"):
            dpp = np.diff(pa, prepend=np.nan)
            jj = np.where(np.abs(dpp) >= 0.02 - 1e-9)[0]
            cc = np.column_stack([ts[jj], np.sign(dpp[jj])]) if len(jj) else np.zeros((0, 2))
        if len(cc) < 5:
            continue
        dur = np.array([float(z.get("round_duration") or 0) / 1e9 for z in rounds])
        wsign = np.where(win == 1, 1.0, -1.0)

        def track(ws, G):
            ct, cs = cc[:, 0], cc[:, 1]
            e = np.full(len(ws), np.nan)
            snapped = np.zeros(len(ws), bool)
            c0 = np.where((cs == ws[0]) & (ct >= tt[0] - 300) & (ct <= tt[0] + 2400))[0]
            if not len(c0):
                return e, snapped
            e[0], snapped[0] = ct[c0[0]], True
            for r in range(1, len(ws)):
                pred = e[r - 1] + dur[r] + G
                cand = np.where((cs == ws[r]) & (ct >= pred - WLO) & (ct <= pred + WHI) & (ct > e[r - 1] + 20))[0]
                if len(cand):
                    e[r], snapped[r] = ct[cand[0]], True
                else:
                    e[r] = pred
            return e, snapped
        best = None
        for G in (0.0, 10.0, 20.0, 30.0):
            e, sn = track(wsign, G)
            if best is None or sn.sum() > best[1].sum():
                best = (e, sn, G)
        e, sn, G = best
        e_pl, sn_pl = track(wsign[::-1].copy(), G)
        snaps_all.append({"cid": cid, "rounds": int(len(win)), "snapped": int(sn.sum()), "snapped_placebo": int(sn_pl.sum()), "G": G})
        for r in range(1, len(win)):
            if not (sn[r] and sn[r - 1]):
                continue
            a, z = e[r - 1], e[r]
            if z - a < 30:
                continue

            def lv(t, arr_t, arr_v):
                j = np.searchsorted(arr_t, t, side="right") - 1
                return arr_v[j] if j >= 0 else np.nan
            pts = {"s": a + 10, "m": z - 10, "l": z - 1, "e": z + 4, "f": z + 20, "g": z + 40}
            rr_ = rounds[r]
            tcl = {q_.get("team_side"): q_ for q_ in (rr_.get("game_round_team_clans") or [])}
            ctd = tcl.get("CT", {}).get("death")
            ttd = tcl.get("T", {}).get("death")
            pl_ = tcl.get("T", {}).get("bomb_plants")
            er_ = rr_.get("end_reason")
            cls_ = "other"
            if er_ == "CTWin" and ttd == 5:
                cls_ = "CT_elim_T"
            elif er_ == "TerroristsWin" and ctd == 5:
                cls_ = "T_elim_CT"
            elif er_ == "BombDefused" and ttd == 5:
                cls_ = "defuse_after_T_wiped"
            elif er_ == "BombDefused":
                cls_ = "defuse_T_alive"
            elif er_ == "TargetBombed" and ctd is not None and ctd < 5:
                cls_ = "bombed_CT_alive"
            elif er_ == "TargetBombed":
                cls_ = "bombed_CT_wiped"
            elif er_ == "TargetSaved":
                cls_ = "time_out"
            V = {k: lv(v, tt, yc) for k, v in pts.items()}
            P = {k: lv(v, ts, pa) for k, v in pts.items()}
            ws_ = wsign[r]
            rows.append({"cid": cid, "build": bool(pd.Timestamp(x.get("gameStartTime")).timestamp() < R.SPLIT), "r": r, "A_won": int(win[r]),
                         "dV_mid": ws_ * (V["m"] - V["s"]), "dV_late": ws_ * (V["l"] - V["m"]), "dV_end": ws_ * (V["e"] - V["l"]), "dV_after": ws_ * (V["f"] - V["e"]),
                         "dP_mid": ws_ * (P["m"] - P["s"]), "dP_late": ws_ * (P["l"] - P["m"]), "dP_end": ws_ * (P["e"] - P["l"]), "dP_after": ws_ * (P["f"] - P["e"]),
                         "rawV_mid": V["m"] - V["s"], "rawP_mid": P["m"] - P["s"], "len": z - a,
                         "dV_post": ws_ * (V["g"] - V["f"]), "dP_post": ws_ * (P["g"] - P["f"]), "cls": cls_, "end_reason": er_,
                         "ct_dead": ctd, "t_dead": ttd, "plants": pl_, "dur_bo3": float(dur[r]), "a": float(a), "z": float(z), "A_won_prev": int(win[r - 1]),
                         "eqA": next((float(q_.get("equipment_value") or 0) for q_ in (rr_.get("game_round_team_clans") or []) if R.norm(q_.get("clan_name"))[:6] == a_6), np.nan),
                         "eqB": next((float(q_.get("equipment_value") or 0) for q_ in (rr_.get("game_round_team_clans") or []) if R.norm(q_.get("clan_name"))[:6] == b_6), np.nan)})
    S = pd.DataFrame(snaps_all)
    D = pd.DataFrame(rows)
    out = {"maps_tracked": int(len(S)), "rounds": int(S.rounds.sum()) if len(S) else 0, "snapped": int(S.snapped.sum()) if len(S) else 0,
           "snapped_placebo_reversed": int(S.snapped_placebo.sum()) if len(S) else 0, "G_counts": S.G.value_counts().to_dict() if len(S) else {},
           "rounds_with_both_ends_snapped": int(len(D))}
    if len(D):
        out["round_len_s_median"] = round(float(D.len.median()), 1)
        for k in ("mid", "late", "end", "after"):
            out[f"V_{k}_mean_c"] = round(float(D[f"dV_{k}"].mean() * 100), 3)
            out[f"P_{k}_mean_c"] = round(float(D[f"dP_{k}"].mean() * 100), 3)
        tot = sum(out[f"V_{k}_mean_c"] for k in ("mid", "late", "end", "after"))
        out["V_share_mid_late_end_after"] = [round(out[f"V_{k}_mean_c"] / tot, 3) if tot else None for k in ("mid", "late", "end", "after")]
        y = D.A_won.to_numpy()
        out["auc_mid_V"] = round(auc(D.rawV_mid.fillna(0), y), 4)
        out["auc_mid_P"] = round(auc(D.rawP_mid.fillna(0), y), 4)
        out["by_split"] = {nm: {"rounds": int(len(g)), "auc_mid_V": round(auc(g.rawV_mid.fillna(0), g.A_won.to_numpy()), 4),
                                "auc_mid_P": round(auc(g.rawP_mid.fillna(0), g.A_won.to_numpy()), 4),
                                "V_mid_late_end_after_c": [round(float(g[f"dV_{k}"].mean() * 100), 3) for k in ("mid", "late", "end", "after")]}
                           for nm, g in (("BUILD", D[D.build]), ("VALIDATE", D[~D.build]))}
    (OUT / "iter15").mkdir(exist_ok=True)
    D.to_parquet(OUT / "iter15" / f"decided_early_rows_{ANCHOR}.parquet", index=False)
    (RES / f"decided_early_clock_{ANCHOR}_{WLO:g}_{WHI:g}.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
