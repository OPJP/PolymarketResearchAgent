"""X214 / X205 (assumptions P1, information P2 of the iteration-14 panel): selection at the operator level.

Operator label per CS2 event of 16-22 Oct (events_groupP.parquet, 384 events, BUILD / VALIDATE split as pre-registered)
= the studied wallet traded it OR one of the five sibling accounts did (the assumptions panel's activity lists,
scratchpad p14/sib_events_1016_H.json: data-api activity of 0x7d67f01d, 0x52661b8e, 0x67119033, 0x10d79cc7,
0xd2bb9459 clamped to 10-16..H, development only). Frozen v5 (BUILD constants) scored against both labels; then the
allocation question: among non-GRID operator events, does any listing-time field separate the wallet's events from the
siblings-only ones (BUILD fit, VALIDATE score)?
Output: results/operator_selection.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
CODE = ROOT / "research/reverse_engineering/tommy-cs2-maker/code"
sys.path.insert(0, str(CODE))
import final_rule as fr  # noqa: E402

RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
SIB = Path(r"C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/"
           r"97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/p14/sib_events_1016_H.json")


def stats_for(sc, y, thr):
    sel = sc >= thr
    return {"events": int(len(y)), "positives": int(y.sum()), "auc": round(fr._auc(sc, y), 4),
            "recall": round(float(y[sel].sum() / max(y.sum(), 1)), 3),
            "lift": round(float(y[sel].mean() / max(y.mean(), 1e-9)), 3) if sel.sum() else None,
            "precision": round(float(y[sel].mean()), 3) if sel.sum() else None, "selected": int(sel.sum())}


def main():
    fr.CONSTANTS = "build"
    C = dict(fr.CALL["build"])
    e = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/events_groupP.parquet")
    ev = e.rename(columns={"e_pre_n": "n", "e_pre_v": "v", "e_pre_w": "w"}).copy()
    ev["grid"] = ev["grid"].astype(bool)
    sc4 = fr.selection_score(ev, C)
    sc = fr.selection_score_v5(ev, C, ev["gp72"].to_numpy(float))
    ba = fr.activity_baseline(ev, C)
    thr = fr.V5["build"]["thr"]
    sib = json.load(open(SIB))
    sib_any = set().union(*[set(v) for v in sib.values()])
    ev["y_w"] = ev["y"].astype(int)
    ev["sib"] = ev.event_slug.isin(sib_any)
    ev["y_op"] = ((ev.y_w == 1) | ev.sib).astype(int)
    for k, v in sib.items():
        ev[f"sib_{k}"] = ev.event_slug.isin(set(v))
    ev["v5"] = sc
    out = {"label_counts": {}}
    for sp in ("build", "validate"):
        m = (ev.split == sp).to_numpy()
        for g in (False, True):
            mm = m & (ev.grid.to_numpy() == g)
            out["label_counts"][f"{sp}_grid{int(g)}"] = {"events": int(mm.sum()), "wallet": int(ev.y_w[mm].sum()),
                                                         "operator": int(ev.y_op[mm].sum()),
                                                         "sibling_only": int((ev.sib & (ev.y_w == 0))[mm].sum())}
        o = {}
        for lab in ("y_w", "y_op"):
            y = ev[lab].to_numpy()[m]
            o[lab] = stats_for(sc[m], y, thr)
            o[lab]["baseline_auc"] = round(fr._auc(ba[m], y), 4)
            o[lab]["v4_auc"] = round(fr._auc(sc4[m], y), 4)
            ng = m & ~ev.grid.to_numpy()
            yn = ev[lab].to_numpy()[ng]
            o[lab]["nongrid_only"] = stats_for(sc[ng], yn, thr)
        out[sp] = o
    # allocation among non-GRID operator events: wallet vs sibling-only
    op = ev[(ev.y_op == 1) & ~ev.grid].copy()
    op["to_wallet"] = op.y_w
    op["hour"] = pd.to_datetime(op.gs, unit="s").dt.hour
    op["day"] = pd.to_datetime(op.gs, unit="s").dt.strftime("%m-%d")
    alloc = {"n": int(len(op)), "to_wallet": int(op.to_wallet.sum()),
             "by_day": op.groupby("day").to_wallet.agg(["size", "sum"]).astype(int).to_dict("index"),
             "by_league_sibling_only": op[op.to_wallet == 0].league.value_counts().to_dict(),
             "v5_score_wallet_vs_sibling_auc": round(fr._auc(op.v5, op.to_wallet), 3),
             "gp72_wallet_vs_sibling_auc": round(fr._auc(op.gp72, op.to_wallet), 3),
             "hour_wallet_vs_sibling_auc": round(fr._auc(op.hour, op.to_wallet), 3),
             "tier_counts": op.groupby(["tier", "to_wallet"]).size().astype(int).to_dict()}
    # in-league skips: events of the wallet's BUILD leagues that it did not trade, by who traded them
    lg_w = set(ev[(ev.split == "build") & (ev.y_w == 1)].league)
    sk = ev[ev.league.isin(lg_w) & (ev.y_w == 0) & ~ev.grid]
    alloc["in_league_skips"] = {sp: {"n": int((sk.split == sp).sum()), "sibling_traded": int((sk.sib & (sk.split == sp)).sum()),
                                     "v5_selected": int(((sk.v5 >= thr) & (sk.split == sp)).sum()),
                                     "v5_selected_sibling_traded": int(((sk.v5 >= thr) & sk.sib & (sk.split == sp)).sum())}
                                for sp in ("build", "validate")}
    out["allocation"] = {k: (v if not isinstance(v, dict) else {str(a): b for a, b in v.items()}) for k, v in alloc.items()}
    (RES / "operator_selection.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
