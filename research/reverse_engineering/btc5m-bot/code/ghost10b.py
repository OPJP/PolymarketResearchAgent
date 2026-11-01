"""Iteration 10, follow-up of ghost10.py (X77): attribution of unfilled lost races (ghost legs) by the fan-out fingerprint.
Every size class at o's old ask (crowd sizes 5/10/20/24/50/64 too) is 4-8x over-represented 0-300 ms after a visible cluster event
on the same token (co-racing on the same trigger), so size and lifetime alone cannot attribute ghosts. XM's small size on 10-31 is
60 shares and a wallet has one in-flight order: an XM ghost leg follows a DS/GF leg but not an XM leg. The share of 0-300-ms
co-occurrences that follow an XM event, for the crowd classes, gives the expected XM-preceded count if a class were crowd only;
the shortfall for the 60-share class is the XM-attributed share. Then XM's decisions per filled 60-share order (lower bound:
partially visible events only).
Usage: python ghost10b.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L, ins9

C = L.C
A, B = 1793458500, 1793469300


def main(out):
    F = pd.read_parquet(C + "/it10/ghost_cand.parquet")
    o, _ = ins9.load_orders(A, B)
    tokmap = {}; txms = {}
    for r in L.recs("btc5m_clob_raw2", A - 600, B + 60):
        k = r.get("k")
        if k == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
        elif k == "x" and r.get("h"):
            h = r["h"].lower(); txms[h] = min(txms.get(h, 10 ** 18), int(r["s"]))
    o["mstart"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0]); o["is_up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.mstart.notna()].copy(); o["mstart"] = o.mstart.astype(int); o["m0"] = o.tx0.str.lower().map(txms)
    Mi = pd.read_parquet(C + "/it9/ins9b_M.parquet"); Mi = Mi[Mi.s_ins.notna()]
    ev = [(int(r.mstart), bool(r.is_up), int(r.m0), r.w) for r in o[(o["first"] == "T") & o.m0.notna()].itertuples()]
    ev += [(int(r.mstart), bool(r.is_up), int(r.s_ins), r.w) for r in Mi.itertuples()]
    E = pd.DataFrame(ev, columns=["m", "up", "s", "w"]).sort_values("s")
    EgW = {k: (g.s.to_numpy(np.int64), g.w.to_numpy()) for k, g in E.groupby(["m", "up"])}
    U = F[~F.known_cluster].copy(); U["zi"] = U.z.round(2); U["up"] = U.bid

    def prev_ev(df, shift=0):
        dt = np.full(len(df), np.nan); wv = np.empty(len(df), object)
        for i, (m, up, s) in enumerate(zip(df.m.to_numpy(), df.up.to_numpy(), df.s.to_numpy(np.int64))):
            g = EgW.get((int(m), bool(up)))
            if g is None:
                continue
            ss, ww = g; j = np.searchsorted(ss + shift, s, "right") - 1
            if j >= 0:
                dt[i] = s - ss[j] - shift; wv[i] = ww[j]
        return dt, wv
    res = {"classes": {}}
    crowd = (5, 10, 20, 24, 50, 64)
    xm_share = []
    for z in crowd + (30, 60, 100):
        g = U[U.zi == z]
        dt, wv = prev_ev(g)
        k = (dt >= 0) & (dt < 300)
        pl = np.mean([np.mean((x >= 0) & (x < 300)) for x in (prev_ev(g, sh)[0] for sh in (-30000, -15000, 15000, 30000))])
        vc = pd.Series(wv[k]).value_counts().to_dict()
        tot = sum(vc.values())
        res["classes"][str(z)] = {"n": int(len(g)), "P(0-300 ms after a cluster event)": round(float(k.mean()), 4), "placebo": round(float(pl), 4),
                                  "preceding_wallet": vc, "XM_preceded_share": round(vc.get("XM", 0) / max(tot, 1), 4),
                                  "cancel_life_med_in_0_300": float(np.nanmedian(g[k & (g.fate == "cancel").to_numpy()].life)) if (k & (g.fate == "cancel").to_numpy()).any() else None}
        if z in crowd:
            xm_share.append(vc.get("XM", 0) / max(tot, 1))
    s_crowd = float(np.mean(xm_share))
    c60 = res["classes"]["60"]
    n_co = sum(c60["preceding_wallet"].values()); n_xm = c60["preceding_wallet"].get("XM", 0)
    crowd_part = n_xm / max(s_crowd, 1e-9)
    xm_ghost_lb = n_co - crowd_part
    xm_vis = o[(o.w == "XM") & (o.Z == 60)]
    res["XM_60"] = {"crowd_XM_preceded_share": round(s_crowd, 4), "co_occurrences_0_300": int(n_co), "XM_preceded": int(n_xm),
                    "crowd_part_est": round(float(crowd_part), 1), "XM_ghost_legs_lower_bound": round(float(xm_ghost_lb), 1),
                    "XM_visible_60_orders": int(len(xm_vis)), "XM_visible_60_T_first": int((xm_vis["first"] == "T").sum()),
                    "XM_decisions_per_filled_60_order_lb": round(float((len(xm_vis) + xm_ghost_lb) / max(len(xm_vis), 1)), 3),
                    "XM_decisions_per_filled_60_order_ub_all_unknown60": round(float((len(xm_vis) + c60["n"]) / max(len(xm_vis), 1)), 3)}
    # the 100-share class, same logic per wallet is not identifiable (all three wallets use 100): report the co-occurrence excess
    c100 = res["classes"]["100"]
    res["note"] = ("crowd classes follow DS:GF:XM visible events about 2.7:1:1; the 60-share class follows XM events far less often, "
                   "as XM's own ghost legs would (one in-flight order per wallet)")
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x)))


if __name__ == "__main__":
    main(sys.argv[1])
