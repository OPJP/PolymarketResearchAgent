"""X189 steps 2-4 / X195 (first pass): which feed messages move its value? Informed take clusters (>= 2 distinct
group-P / G takers within 300 ms on any book of the event, wallet-free txs; time = first signature; sign s = team
bought) placed in the print-inferred rounds of iteration 13's X181 machinery (86 CS2 maps of 16-22 Oct with bo3 round
sequences; boundaries from the X171 fit of the PRINT with the true winner sequence). For each cluster inside a round:
match = s points to the round's eventual winner; its value's step s x (V(c + 3 s) - V(c - 1 s)) and the print's
s x (P(c + 5 s) - P(c - 1 s)) (cents), the share of clusters where V moves toward s by >= 1c, by match / non-match and
by position in the round (first 30 s of the segment, last 30 s before the next segment). Under R (V moves on round
results only) non-match clusters do not move V; under K / D (in-round events) they move it toward s.
Output: results/cluster_rounds.json
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
    inf = tk[tk.mk.isin(GP | GG)].sort_values("sign_ms")
    cl = {}
    for ev, g in inf.groupby("event"):
        s, m, tm = g.sign_ms.to_numpy(), g.mk.to_numpy(), g.team.to_numpy()
        i, out = 0, []
        while i < len(g):
            j = i
            while j + 1 < len(g) and s[j + 1] - s[i] <= 300:
                j += 1
            if len(set(m[i:j + 1])) >= 2:
                out.append((s[i] / 1000, float(np.sign(tm[i:j + 1].sum())) or float(tm[i])))
                i = j + 1
            else:
                i += 1
        cl[ev] = np.array(out) if out else np.zeros((0, 2))
    return cl, ev_of


def main():
    CL, EV = clusters_by_cid()
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
        if len(d) < 20:
            continue
        ts = d.timestamp.to_numpy(float)
        pa = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        j = np.searchsorted(ts, tt, side="right") - 1
        ok = j >= 0
        if ok.sum() < 30:
            continue
        y, tok, tt, yp = y[ok], tok[ok], tt[ok], pa[j[ok]]
        fp = R.fit(yp, tok * 0, tt, win[None, :])
        path = fp["path"][0]
        nmaps += 1
        # wallet token offsets: put both tokens on one scale (subtract the per-token median gap to the print)
        off = {s: float(np.median((y - yp)[tok == s])) if (tok == s).any() else 0.0 for s in (0, 1)}
        yc = y - np.array([off[s] for s in tok])
        cc = CL.get(EV.get(cid), np.zeros((0, 2)))
        # map team space: clusters are signed in the map's token-0 team space only if the event's books share the
        # outcome order (they do: Gamma lists the same team order on map and match books)
        for c_t, s in cc:
            if c_t < tt[0] + 5 or c_t > tt[-1] - 5:
                continue
            ib = np.searchsorted(tt, c_t, side="right") - 1
            if ib < 0:
                continue
            k = int(path[ib])
            if k >= len(win):
                continue
            seg = np.where(path == k)[0]
            nxt = np.where(path > k)[0]
            t_next = tt[nxt[0]] if len(nxt) else np.inf
            i_m1 = np.searchsorted(tt, c_t - 1, side="right") - 1
            i_p3 = np.searchsorted(tt, c_t + 3, side="right") - 1
            jp_m1 = np.searchsorted(ts, c_t - 1, side="right") - 1
            jp_p5 = np.searchsorted(ts, c_t + 5, side="right") - 1
            if i_m1 < 0 or jp_m1 < 0:
                continue
            a_won = int(win[k]) == 1
            rk = rounds[k]
            wside = rk.get("winner_clan_side")
            planted = any((tcl.get("team_side") == "T") and (tcl.get("bomb_plants") or 0) > 0 for tcl in (rk.get("game_round_team_clans") or []))
            s_team_side = wside if bool((s > 0) == a_won) else ("T" if wside == "CT" else "CT")
            rows.append({"cid": cid, "build": bool(pd.Timestamp(x.get("gameStartTime")).timestamp() < R.SPLIT), "round": k,
                         "match": bool((s > 0) == a_won), "s": s,
                         "dV": float(s * (yc[i_p3] - yc[i_m1])), "dP": float(s * (pa[jp_p5] - pa[jp_m1])),
                         "early": bool(c_t - tt[seg[0]] <= 30), "late": bool(t_next - c_t <= 30),
                         "end_reason": rk.get("end_reason"), "winner_side": wside, "planted": bool(planted), "toward_T": bool(s_team_side == "T")})
    D = pd.DataFrame(rows)
    out = {"maps": nmaps, "clusters": int(len(D))}
    def summ(g):
        return {"n": int(len(g)), "dV_mean_c": round(float(g.dV.mean() * 100), 3), "dP_mean_c": round(float(g.dP.mean() * 100), 3),
                "V_toward_s_ge1c": round(float((g.dV >= 0.0095).mean()), 3), "V_against_s_ge1c": round(float((g.dV <= -0.0095).mean()), 3),
                "P_toward_s_ge1c": round(float((g.dP >= 0.0095).mean()), 3)}
    if len(D):
        out["share_match_round_winner"] = round(float(D.match.mean()), 3)
        out["match"] = summ(D[D.match])
        out["non_match"] = summ(D[~D.match])
        out["non_match_early"] = summ(D[~D.match & D.early])
        out["non_match_late"] = summ(D[~D.match & D.late])
        out["match_late"] = summ(D[D.match & D.late])
        out["match_early"] = summ(D[D.match & D.early])
        cls = {}
        for (ws, pl), g in D.groupby(["winner_side", "planted"]):
            cls[f"winner_{ws}_planted_{pl}"] = {"clusters": int(len(g)), "share_toward_T": round(float(g.toward_T.mean()), 3),
                                                "toward_T": summ(g[g.toward_T]), "toward_CT": summ(g[~g.toward_T])}
        out["by_winner_side_and_plant"] = cls
        out["by_end_reason"] = {str(k): {"clusters": int(len(g)), "share_toward_T": round(float(g.toward_T.mean()), 3),
                                         "share_match": round(float(g.match.mean()), 3)} for k, g in D.groupby("end_reason")}
        out["by_split"] = {nm: {"match": summ(g[g.match]), "non_match": summ(g[~g.match]), "share_match": round(float(g.match.mean()), 3)}
                           for nm, g in (("BUILD", D[D.build]), ("VALIDATE", D[~D.build]))}
    (RES / "cluster_rounds.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
