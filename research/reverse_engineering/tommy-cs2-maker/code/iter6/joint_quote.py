"""Iteration 6, X81 (assumptions panel iter5 P2, steps 1-2): is the maker quote ONE two-token quote (a mid and a
spread) rather than two independent joins?

10-31 14:50-18:00 development block (BUILD-live), server clock, level_events_dev.parquet (the wallet's 7 dev-unit CS2
token-0 books, both sides: BUY = its bids on token 0, SELL = its bids on token 1 seen as asks at 1 - b on token 0).
Own levels by fingerprint with the wallet's actual maker order sizes in that market (calldata_dev; the X56 step-2 fix)
at whole cents, capped by level size; others' best = best price net of own orders.
At every own add burst (adds within 5 ms, either side) with own levels on both sides after it:
  own pair sum S = own top bid token 0 + own top bid token 1 = mt_buy + (1 - mt_sell);
  others' pair sum = ob_buy + (1 - ob_sell).
Rules for the burst's NON-trigger side top (trigger side = the side the burst added to):
  join: others' best on that side; keep: its own previous top on that side; pair cap: K - trigger-side top (K fitted on
  the first half of the block, scored on the second half).
Output: results/joint_quote.json
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    cd["a"] = cd.token_id.astype(str).map(t0map)
    wm = cd[(cd.idx >= 0) & (cd.maker == WALLET) & cd.a.notna()]
    own_sizes = {a: set(np.round(g.shares.to_numpy(float), 2)) | {100.0} for a, g in wm.groupby("a")}
    E = pd.read_parquet(OUT / "level_events_dev.parquet").sort_values(["a", "s"]).reset_index(drop=True)
    E["own"] = [bool(w) and (round(float(z), 2) in own_sizes.get(a, {100.0})) for a, z, w in zip(E.a, E["size"], E.whole)]
    rows = []
    for a, g in E.groupby("a"):
        lvl = {"BUY": {}, "SELL": {}}
        own = {"BUY": defaultdict(float), "SELL": defaultdict(float)}

        def tops(side):
            ob = mt = None
            for p, z in lvl[side].items():
                net = z - own[side].get(p, 0.0)
                if net > 0.5 and (ob is None or (p > ob if side == "BUY" else p < ob)):
                    ob = p
                if own[side].get(p, 0.0) > 0.5 and (mt is None or (p > mt if side == "BUY" else p < mt)):
                    mt = p
            return ob, mt

        S = g.s.to_numpy(float); SD = g.side.to_numpy(); P = g.p.to_numpy(float); Z = g.z.to_numpy(float)
        D = g.d.to_numpy(float); K = g.kind.to_numpy(); O = g.own.to_numpy()
        burst = None  # (side, start_s, pre_state)
        for i in range(len(g)):
            s, side, p, z, d, k, o = S[i], SD[i], P[i], Z[i], D[i], K[i], O[i]
            if k == "add" and o and burst is None:
                ob_b, mt_b = tops("BUY"); ob_s, mt_s = tops("SELL")
                burst = (side, s, ob_b, mt_b, ob_s, mt_s)
            lvl[side][p] = z
            if z <= 1e-9:
                lvl[side].pop(p, None)
            if k == "add" and o:
                own[side][p] += abs(d)
            elif k == "cancel" and o:
                own[side][p] = max(0.0, own[side][p] - abs(d))
            if p in own[side]:
                own[side][p] = min(own[side][p], lvl[side].get(p, 0.0))
            if burst is not None:
                nxt = i + 1 < len(g) and K[i + 1] == "add" and O[i + 1] and S[i + 1] - s <= 5 and SD[i + 1] == burst[0]
                if not nxt:
                    ob_b, mt_b = tops("BUY"); ob_s, mt_s = tops("SELL")
                    tside, s0, pob_b, pmt_b, pob_s, pmt_s = burst
                    if mt_b is not None and mt_s is not None:
                        rows.append({"a": a, "s": s0, "tside": tside, "mt_buy": mt_b, "mt_sell": mt_s,
                                     "ob_buy": ob_b, "ob_sell": ob_s, "pmt_buy": pmt_b, "pmt_sell": pmt_s,
                                     "pob_buy": pob_b, "pob_sell": pob_s})
                    burst = None
    R = pd.DataFrame(rows)
    R["own_sum"] = R.mt_buy + (1 - R.mt_sell)
    R["oth_sum"] = R.ob_buy + (1 - R.ob_sell)
    res = {"bursts_with_both_sides": int(len(R)),
           "own_pair_sum_q": {str(q): round(float(R.own_sum.quantile(q)), 3) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
           "own_pair_sum_iqr_c": round(float(100 * (R.own_sum.quantile(0.75) - R.own_sum.quantile(0.25))), 1),
           "others_pair_sum_q": {str(q): round(float(R.oth_sum.dropna().quantile(q)), 3) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
           "own_sum_mode_share": R.own_sum.round(2).value_counts(normalize=True).head(6).round(3).to_dict()}
    # non-trigger side top prediction: in token-1 bid terms for the SELL side (1 - p)
    R["other_side"] = np.where(R.tside == "BUY", "SELL", "BUY")
    R["trig_top"] = np.where(R.tside == "BUY", R.mt_buy, 1 - R.mt_sell)
    R["other_top"] = np.where(R.other_side == "BUY", R.mt_buy, 1 - R.mt_sell)
    R["other_join"] = np.where(R.other_side == "BUY", R.pob_buy, 1 - R.pob_sell)
    R["other_keep"] = np.where(R.other_side == "BUY", R.pmt_buy, 1 - R.pmt_sell)
    R = R.sort_values("s").reset_index(drop=True)
    half = R.s.median()
    fit, sc = R[R.s < half], R[R.s >= half]
    Ks = np.round(np.arange(0.90, 1.001, 0.01), 2)
    best_k = max(Ks, key=lambda k: float((np.abs(fit.other_top - (k - fit.trig_top)) <= 0.0101).mean()))
    out = {}
    for nm, x in (("fit_half", fit), ("score_half", sc)):
        o = {"n": int(len(x))}
        for rule, pred in (("join_others_best", x.other_join), ("keep_own_previous_top", x.other_keep),
                           ("pair_cap_K_minus_trigger_top", best_k - x.trig_top),
                           ("min(join, K - trigger)", np.minimum(x.other_join, best_k - x.trig_top))):
            ok = pred.notna()
            o[rule] = {"within_1c": round(float((np.abs(x.other_top[ok] - pred[ok]) <= 0.0101).mean()), 3),
                       "exact": round(float((np.abs(x.other_top[ok] - pred[ok]) <= 0.0001).mean()), 3), "n": int(ok.sum())}
        o["other_side_unchanged_share"] = round(float((np.abs(x.other_top - x.other_keep) <= 0.0001).mean()), 3)
        out[nm] = o
    res["K_fit"] = float(best_k)
    res["non_trigger_side_rules"] = out
    (RES / "joint_quote.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
