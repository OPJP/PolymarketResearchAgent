"""X204 / X210 robustness (after the pre-registered pass in grid_socket_clock.py): (a) a clean mid window that starts 25 s
after the previous tick (drops the previous round's after-move), (b) the autocorrelation placebo (the PREVIOUS round's
winner as the label), (c) an event-cluster bootstrap of AUC(V) - AUC(print), (d) the ladder fingerprint of 0xd2bb9459's
GRID orders (burst sizes, slot gaps, sizes, band). Output: results/grid_socket_clock2.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grid_socket_clock as g1  # noqa: E402

OUT = g1.OUT
RES = g1.RES


def main():
    s = pd.read_parquet(OUT / "socket_rounds.parquet")
    tr = pd.read_parquet(OUT / "op_trades.parquet")
    cd = pd.read_parquet(OUT / "op_calldata.parquet")
    L_fit = {k: v["L_fit_print"] for k, v in json.load(open(RES / "grid_socket_clock.json"))["events"].items()}
    rows, fp = [], []
    for ev in g1.GRID_EVENTS:
        g = s[s.event == ev].sort_values("t")
        home = g.home.iloc[0]
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
        ch["t_prev"] = ch.t.shift() / 1000.0
        rd = ch[(~ch.map_chg) & (((ch.dh == 1) & (ch.da == 0)) | ((ch.dh == 0) & (ch.da == 1)))].copy()
        rd["home_won"] = rd.dh == 1
        rd["prev_home_won"] = rd.home_won.shift()
        L = L_fit[ev]
        for P in g1.team_paths(ev, tr, cd):
            outs = P["outcomes"]
            a_is_home = str(outs[0]).split()[0].lower()[:4] in str(home).lower() or str(home).lower()[:4] in str(outs[0]).lower()
            c = P["orders"]
            b = g1.bursts(c) if len(c) else pd.DataFrame(columns=["t", "oi", "top", "n"])
            if len(c):
                for _, h in c.groupby("oi"):
                    fp.append(h.assign(smt=P["smt"]))
            tV, VA, _ = g1.value_A(b) if len(b) else (np.array([]), np.array([]), np.array([]))
            tp, pA = P["pt_ts"], P["pA"]
            # which map does a child market belong to: the map whose ticks overlap its prints most
            if P["smt"] == "child_moneyline":
                best, bm = -1, None
                for mp, h in rd.groupby("mapn"):
                    n = int(((tp >= h.t.min() / 1000 - 60) & (tp <= h.t.max() / 1000)).sum())
                    if n > best:
                        best, bm = n, mp
                rds = rd[rd.mapn == bm]
            else:
                rds = rd
            for r in rds.itertuples():
                t = r.t / 1000.0
                st = r.t_prev - L + 25
                en = t - L - 25
                if not (np.isfinite(st) and en - st > 10):
                    continue
                A_won = bool(r.home_won == a_is_home)
                pw = r.prev_home_won
                A_prev = None if pd.isna(pw) else bool(pw == a_is_home)
                rows.append({"event": ev, "smt": P["smt"], "A_won": A_won, "A_prev": A_prev,
                             "dV": g1.step_at(tV, VA, en) - g1.step_at(tV, VA, st) if len(tV) else np.nan,
                             "dP": g1.step_at(tp, pA, en) - g1.step_at(tp, pA, st) if len(tp) else np.nan})
    X = pd.DataFrame(rows)
    out = {}
    rng = np.random.default_rng(0)
    for name, sub in (("all", X), ("map_books", X[X.smt == "child_moneyline"]), ("match_books", X[X.smt == "moneyline"])):
        ok = sub.dV.notna() & sub.dP.notna()
        q = sub[ok]
        o = {"rounds": int(len(q)), "auc_V": g1.auc(q.dV, q.A_won), "auc_P": g1.auc(q.dP, q.A_won),
             "dV_winner_c": round(float((q.dV * np.where(q.A_won, 1, -1)).mean() * 100), 2) if len(q) else None,
             "dP_winner_c": round(float((q.dP * np.where(q.A_won, 1, -1)).mean() * 100), 2) if len(q) else None}
        qp = q[q.A_prev.notna()]
        o["placebo_prev_winner"] = {"rounds": int(len(qp)), "auc_V": g1.auc(qp.dV, qp.A_prev.astype(bool)),
                                    "auc_P": g1.auc(qp.dP, qp.A_prev.astype(bool)),
                                    "same_winner_as_prev": round(float((qp.A_prev.astype(bool) == qp.A_won).mean()), 3) if len(qp) else None}
        # partial: V's change residualized on the print's, AUC for the round winner
        if len(q) >= 20:
            beta = np.polyfit(q.dP, q.dV, 1)[0] if q.dP.std() > 0 else 0.0
            o["auc_V_resid_given_P"] = g1.auc(q.dV - beta * q.dP, q.A_won)
            o["beta_V_on_P"] = round(float(beta), 3)
            evs = q.event.unique()
            diffs = []
            for _ in range(2000):
                pick = rng.choice(evs, len(evs))
                bb = pd.concat([q[q.event == e] for e in pick])
                a1, a2 = g1.auc(bb.dV, bb.A_won), g1.auc(bb.dP, bb.A_won)
                if a1 is not None and a2 is not None:
                    diffs.append(a1 - a2)
            if diffs:
                o["auc_diff_ci95_event_boot"] = [round(float(np.quantile(diffs, 0.025)), 3), round(float(np.quantile(diffs, 0.975)), 3)]
        out[name] = o
    F = pd.concat(fp) if fp else pd.DataFrame()
    fpo = {}
    if len(F):
        F = F.sort_values("sign_ms")
        fpo["orders"] = int(len(F))
        fpo["sizes_top"] = {str(k): int(v) for k, v in F.shares.round(0).value_counts().head(8).items()}
        fpo["band_share_0.05_0.95"] = round(float(((F.price >= 0.05 - 1e-9) & (F.price <= 0.95 + 1e-9)).mean()), 3)
        fpo["whole_cent"] = round(float((np.abs(F.price * 100 - np.round(F.price * 100)) < 1e-6).mean()), 3)
        # bursts on a token within 50 ms: size distribution and slot gaps
        bs, gaps = [], []
        for oi, h in F.groupby("oi"):
            sgn = h.sign_ms.to_numpy(float)
            pr = h.price.to_numpy(float)
            i = 0
            while i < len(sgn):
                j = i
                while j + 1 < len(sgn) and sgn[j + 1] - sgn[j] <= 50:
                    j += 1
                bs.append(j - i + 1)
                if j > i:
                    gaps += list(np.round(np.diff(np.sort(pr[i:j + 1])[::-1]) * -100, 1))
                i = j + 1
        fpo["burst_size_counts"] = {str(k): int(v) for k, v in pd.Series(bs).value_counts().sort_index().head(8).items()}
        fpo["slot_gap_c_counts"] = {str(k): int(v) for k, v in pd.Series(gaps).value_counts().head(6).items()}
    out["fingerprint_d2bb_grid"] = fpo
    (RES / "grid_socket_clock2.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
