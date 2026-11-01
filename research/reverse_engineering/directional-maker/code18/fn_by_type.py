"""iteration 18, T4 = X226 (assumptions panel P4; pre-registered in NOTES.md 12:50 UTC 11-01): the presence label split
by order type. VALIDATE 10-27..30 (aggregate only): the frozen R3 BTC 5m presence scores (code8/union_val.fam_panel,
rule = presence3_rule, baseline = activity) per (window, side, 10-s bin); each filled cell's fills typed from the lot
calldata (it12/typed_fills: pairing = original size within 2% of the wallet's imbalance on the under-held outcome;
deep = limit <= 0.10; remainder = a later fill of an order already filled in an earlier block second; main = a fresh
schedule-size order; other = the rest). FN = filled cells below the 85th percentile of all cells' rule scores (the E2
definition). Reported: FN share per cell class and the share of all FN cells each class holds."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code8"))
sys.path.insert(0, str(HERE.parent / "code12"))
import union_val as uv  # noqa: E402
from typed_side import types as order_types, STD  # noqa: E402

C = uv.C


def main():
    p, w, f = uv.fam_panel("5m")
    p = p.copy()
    thr = float(np.quantile(p.p_rule, 0.85))
    thr_a = float(np.quantile(p.p_activity, 0.85))
    V = pd.read_parquet(C / "it12" / "typed_fills.parquet")
    V = V[(V.sp == "validate") & ((V.en - V.st) == 300)].copy()
    V["typ"] = order_types(V).to_numpy()
    rem = V.b > V.first_b
    sched = V.orig.isin(list(STD))
    cls = np.where(V.typ == "pairing", "pairing", np.where(V.typ == "deep", "deep", np.where(rem, "remainder",
                   np.where(sched, "main", "other"))))
    V["cls"] = cls
    V["rel"] = ((V.b - V.st) // 10 * 10).astype(int)
    V["side_up"] = (V.is_up == 1).astype(int)
    g = V.groupby(["cid", "side_up", "rel"]).cls.agg(lambda s: tuple(sorted(set(s))))
    own = {"pairing", "deep", "remainder"}

    def cell_class(t):
        st = set(t)
        if "main" in st:
            return "has_main_fresh"
        if st <= own:
            return "own_state_only"
        return "other_mix"
    cc = g.map(cell_class)
    key = list(zip(p.cid.astype(str), p.side_up.astype(int), p.rel.astype(int)))
    cmap = {(str(a), int(b), int(c)): v for (a, b, c), v in cc.items()}
    p["cell_class"] = [cmap.get(k) for k in key]
    pos = p[p.y == 1].copy()
    pos["fn"] = (pos.p_rule < thr).astype(int)
    pos["fn_act"] = (pos.p_activity < thr_a).astype(int)
    out = {"cells": int(len(p)), "filled_cells": int(len(pos)), "typed_cells": int(pos.cell_class.notna().sum()),
           "fn_share_all": round(float(pos.fn.mean()), 4), "fn_share_activity_all": round(float(pos.fn_act.mean()), 4),
           "fill_class_shares": V.cls.value_counts(normalize=True).round(4).to_dict()}
    rows = {}
    nfn = int(pos.fn.sum())
    for k, gg in pos.groupby(pos.cell_class.fillna("untyped")):
        rows[k] = {"cells": int(len(gg)), "fn_share": round(float(gg.fn.mean()), 4), "fn_share_activity": round(float(gg.fn_act.mean()), 4),
                   "share_of_all_fn": round(float(gg.fn.sum() / max(nfn, 1)), 4)}
    out["by_cell_class"] = rows
    # per fill class (cells holding at least one fill of the class)
    pf = {}
    for c in ("main", "pairing", "deep", "remainder", "other"):
        cells = set(map(tuple, V[V.cls == c][["cid", "side_up", "rel"]].astype({"side_up": int, "rel": int}).itertuples(index=False, name=None)))
        m = np.array([(str(a), int(b), int(r)) in cells for a, b, r in zip(pos.cid, pos.side_up, pos.rel)])
        pf[c] = {"cells_with_class": int(m.sum()), "fn_share": round(float(pos.fn[m].mean()), 4) if m.any() else None}
    out["cells_holding_class"] = pf
    own_fn = rows.get("own_state_only", {}).get("share_of_all_fn", 0.0)
    main_fn = rows.get("has_main_fresh", {}).get("fn_share")
    out["reading"] = {"own_state_only_share_of_fn": own_fn, "main_fn_share": main_fn,
                      "signature_met": bool(own_fn >= 0.5 and (main_fn is not None and main_fn <= 0.35))}
    (HERE.parent / "results" / "iter18_fn_by_type.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
