"""X172 step 1 (information panel iter-12 P1, historical and clock-free): is the wallet's Dota value a de-margined
bookmaker in-play line? hawk.live archives, per map, the in-play map-winner odds of BetBoom, SpinBetter and Parimatch
(ordered by one site-wide update id, no timestamps; null = suspended).

Units: the wallet's filled maker BUY orders on the Dota map-winner markets of its DEVELOPMENT series (10-22 ty-gl,
10-22 ts8-legion1, 10-31 ty-gl; 10-22 liquid-1win has no hawk page under the guessed slugs), grouped into bursts (same
token, signed within 50 ms; level = highest price), team-A space (y = price on outcome 0, 1 - price on outcome 1),
band edges (<= 0.06 or >= 0.94) excluded.
Model: hidden index k over the provider's non-null updates, non-decreasing in burst time; emission
y ~ N(p_k + mu_token, sigma^2) (p = proportional de-margin, oriented to outcome 0); mu by 3 EM passes. Optional band:
|k/(K-1) - f| <= 0.3, f = the burst's time fraction inside the span of the market's public prints (wallet-free).
Statistics per map: RMS residual and the share within 1c (|res| <= 0.01) at the best path.
Controls: (a) the last public print (wallet transactions excluded, stamped at or before signing) aligned the same way;
(b) the same provider's sequence of another map (best of both orientations: conservative); (c) the reversed sequence.
Pre-game level: the wallet's first burst on the map vs the provider's first (pre-game) line and the last public print.
Output: results/hawk_align.json
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
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import final_rule as F  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
SER = ["dota2-ty-gl-2026-10-22", "dota2-ts8-legion1-2026-10-22", "dota2-ty-gl-2026-10-31"]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def bursts(o: pd.DataFrame) -> pd.DataFrame:
    o = o.sort_values(["token_id", "sign_ms"])
    out = []
    for tok, g in o.groupby("token_id"):
        s = g.sign_ms.to_numpy(np.int64)
        p = g.price.to_numpy(float)
        st = 0
        for i in range(1, len(s) + 1):
            if i == len(s) or s[i] - s[i - 1] > 50:
                out.append((tok, int(s[st]), float(p[st:i].max()), i - st))
                st = i
    return pd.DataFrame(out, columns=["token_id", "sign_ms", "top", "n"]).sort_values("sign_ms").reset_index(drop=True)


def dp_align(y, grp, P, fr=None, band=None, mu=None):
    """Monotone alignment: returns path (index into P), residuals. grp: int group per obs (mu per group)."""
    n, K = len(y), len(P)
    ng = int(grp.max()) + 1
    mu = np.zeros(ng) if mu is None else mu
    for _ in range(3):
        cost = (y[:, None] - P[None, :] - mu[grp][:, None]) ** 2
        if band is not None and fr is not None:
            kk = np.arange(K) / max(K - 1, 1)
            cost = cost + np.where(np.abs(kk[None, :] - fr[:, None]) > band, 1e3, 0.0)
        D = np.empty((n, K))
        B = np.empty((n, K), dtype=np.int64)
        D[0] = cost[0]
        for i in range(1, n):
            cm = np.minimum.accumulate(D[i - 1])
            am = np.maximum.accumulate(np.where(D[i - 1] <= cm, np.arange(K), 0))
            D[i] = cost[i] + cm
            B[i] = am
        path = np.empty(n, dtype=np.int64)
        path[-1] = int(np.argmin(D[-1]))
        for i in range(n - 1, 0, -1):
            path[i - 1] = B[i, path[i]]
        res = y - P[path] - mu[grp]
        for g in range(ng):
            m = grp == g
            if m.any():
                mu[g] = float(np.mean(y[m] - P[path][m]))
    res = y - P[path] - mu[grp]
    return path, res, mu


def stats(res):
    return {"rms_c": round(float(np.sqrt(np.mean(res ** 2))) * 100, 3), "within_1c": round(float(np.mean(np.abs(res) <= 0.0100001)), 3),
            "within_half_c": round(float(np.mean(np.abs(res) <= 0.0050001)), 3), "n": int(len(res))}


def provider_seqs(m: dict, a_is_team1: bool):
    seqs = {}
    for b in m.get("oddsBundles") or []:
        ps = []
        first_is_t1 = bool(b.get("isTeam1First", True))
        for x in b["odds"]:
            o1, o2 = x.get("firstTeamWin"), x.get("secondTeamWin")
            if o1 is None or o2 is None:
                continue
            q1, q2 = 1 / float(o1), 1 / float(o2)
            pt1 = q1 / (q1 + q2) if first_is_t1 else q2 / (q1 + q2)
            ps.append((int(x["id"]), pt1 if a_is_team1 else 1 - pt1, (q1 + q2) - 1))
        if ps:
            seqs[b["oddsProviderCodeName"]] = np.array(ps, float)
    return seqs


def main():
    ud = pd.read_parquet(OUT / "universe_dota.parquet")
    ud = ud[ud.event_slug.isin(SER) & (ud.smt == "child_moneyline")]
    mk, _ = PolymarketData().markets_by_condition(sorted(ud.cid))
    cols = ["tx", "idx", "maker", "token_id", "price", "shares", "sign_ms", "salt"]
    cd = pd.concat([pd.read_parquet(OUT / "calldata_all.parquet", columns=cols), pd.read_parquet(OUT / "calldata_dev.parquet", columns=cols)])
    cd["maker"] = cd.maker.str.lower()
    cd["token_id"] = cd.token_id.astype(str)
    wtx = set(cd.loc[cd.maker == W, "tx"])
    wo = cd[(cd.maker == W) & (cd.idx != -1)].drop_duplicates(["salt", "sign_ms"])
    maps = []
    for ev in SER:
        hk = json.loads((OUT / "hawk" / f"{ev}.json").read_text(encoding="utf-8"))
        t1 = norm(hk["team1"]["name"])
        for r in ud[ud.event_slug == ev].itertuples():
            x = mk.get(r.cid) or {}
            mm = re.search(r"Game (\d)", x.get("question", ""))
            if not mm:
                continue
            num = int(mm.group(1))
            hm = [m for m in hk["matches"] if int(m["number"]) == num]
            if not hm:
                continue
            outs = json.loads(x["outcomes"]) if isinstance(x.get("outcomes"), str) else x.get("outcomes")
            toks = [str(t) for t in (json.loads(x["clobTokenIds"]) if isinstance(x.get("clobTokenIds"), str) else x.get("clobTokenIds"))]
            a_is_t1 = norm(outs[0])[:5] in t1 or t1[:5] in norm(outs[0])
            seqs = provider_seqs(hm[0], a_is_t1)
            o = wo[wo.token_id.isin(toks)]
            if len(o) < 20:
                continue
            b = bursts(o)
            b["y"] = np.where(b.token_id == toks[0], b.top, 1 - b.top)
            b["g"] = np.where(b.token_id == toks[0], 0, 1)
            b = b[(b.top > 0.06) & (b.top < 0.94)].reset_index(drop=True)
            tp = F._tape(r.cid, int(r.gs_ts), F.H if r.gs_ts < F.H else int(r.gs_ts) + 5 * 3600)
            tp = tp[~tp.transactionHash.isin(wtx)].sort_values("timestamp")
            tts = tp.timestamp.to_numpy(float)
            p0 = np.where(tp.outcomeIndex.astype(int) == 0, tp.price.astype(float), 1 - tp.price.astype(float))
            k = np.searchsorted(tts, b.sign_ms.to_numpy() / 1000.0, side="right") - 1
            b["lp"] = np.where(k >= 0, p0[np.clip(k, 0, None)], np.nan)
            b = b[b.lp.notna()].reset_index(drop=True)
            span0, span1 = (tts.min(), tts.max()) if len(tts) else (b.sign_ms.min() / 1e3, b.sign_ms.max() / 1e3)
            b["fr"] = np.clip((b.sign_ms / 1000.0 - span0) / max(span1 - span0, 1.0), 0, 1)
            maps.append({"ev": ev, "num": num, "cid": r.cid, "a_is_t1": bool(a_is_t1), "seqs": seqs, "b": b,
                         "first_print": float(p0[0]) if len(p0) else None})
            print(ev, num, "bursts", len(b), "providers", {k2: len(v) for k2, v in seqs.items()}, "a_is_t1", a_is_t1, flush=True)
    out = {"maps": []}
    pooled = {}
    for mi, M in enumerate(maps):
        b = M["b"]
        y, g, fr = b.y.to_numpy(float), b.g.to_numpy(int), b.fr.to_numpy(float)
        lp = b.lp.to_numpy(float)
        rec = {"event": M["ev"], "map": M["num"], "n_bursts": int(len(b))}
        for prov, S in M["seqs"].items():
            P = S[:, 1]
            for bandname, band in (("free", None), ("band30", 0.3)):
                _, rw, muw = dp_align(y, g, P, fr, band)
                _, rp, _ = dp_align(lp, np.zeros(len(lp), int), P, fr, band)
                _, rr, _ = dp_align(y, g, P[::-1].copy(), fr, band)
                plc = []
                for mj, M2 in enumerate(maps):
                    if mj == mi or M2["ev"] == M["ev"] or prov not in M2["seqs"]:
                        continue
                    P2 = M2["seqs"][prov][:, 1]
                    best = None
                    for PP in (P2, 1 - P2):
                        _, r2, _ = dp_align(y, g, PP, fr, band)
                        s2 = stats(r2)
                        if best is None or s2["rms_c"] < best["rms_c"]:
                            best = s2
                    plc.append(best)
                key = f"{prov}_{bandname}"
                rec[key] = {"wallet": stats(rw), "mu_c": [round(float(v) * 100, 2) for v in muw], "print": stats(rp),
                            "reversed": stats(rr), "placebo_median_rms_c": float(np.median([p["rms_c"] for p in plc])) if plc else None,
                            "placebo_median_within_1c": float(np.median([p["within_1c"] for p in plc])) if plc else None,
                            "K": int(len(P)), "margin_median": round(float(np.median(S[:, 2])), 4)}
                pooled.setdefault(key, []).append(rec[key])
        # pre-game level: first burst vs first provider line vs print
        fb = b.iloc[0]
        pg = {prov: round(float(S[0, 1]), 4) for prov, S in M["seqs"].items()}
        rec["pregame"] = {"first_burst_y": round(float(fb.y), 3), "first_burst_token": int(fb.g), "lp_at_first": round(float(fb.lp), 3),
                          "provider_first_line": pg}
        out["maps"].append(rec)
    summ = {}
    for key, lst in pooled.items():
        summ[key] = {"maps": len(lst),
                     "wallet_rms_c_median": float(np.median([x["wallet"]["rms_c"] for x in lst])),
                     "print_rms_c_median": float(np.median([x["print"]["rms_c"] for x in lst])),
                     "reversed_rms_c_median": float(np.median([x["reversed"]["rms_c"] for x in lst])),
                     "placebo_rms_c_median": float(np.median([x["placebo_median_rms_c"] for x in lst if x["placebo_median_rms_c"] is not None])) if any(x["placebo_median_rms_c"] is not None for x in lst) else None,
                     "wallet_within_1c_pooled": float(np.sum([x["wallet"]["within_1c"] * x["wallet"]["n"] for x in lst]) / np.sum([x["wallet"]["n"] for x in lst])),
                     "print_within_1c_pooled": float(np.sum([x["print"]["within_1c"] * x["print"]["n"] for x in lst]) / np.sum([x["print"]["n"] for x in lst])),
                     "wallet_rms_below_print_maps": int(sum(x["wallet"]["rms_c"] < x["print"]["rms_c"] for x in lst))}
    out["summary"] = summ
    (RES / "hawk_align.json").write_text(json.dumps(out, indent=1))
    for k2, v in summ.items():
        print(k2, v)


if __name__ == "__main__":
    main()
