"""Examiner round 2: the rule's frozen price R7 per fill (live match clock where the shared recorder has the fill's
trade, else the in-block execution order: code/inblock_price.py, the rule's own code) on the lot's BTC 5m and 15m maker
fills, split by half and wallet; the trivial anchors on the same clocks (last print, and on the match clock the touch and
touch minus a tick from r2_metrics)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from r2_common import CLUSTER, EXC, RES

import inblock_price  # noqa: E402

EV = EXC / "ev"
CUT = json.loads((RES / "exam_r2_step0.json").read_text())["cut_ts"]


def main():
    A = pd.read_parquet(EXC / "activity_f1_all.parquet")
    txh = {}
    for h in A.tx.dropna().unique():
        try:
            txh[int(str(h)[2:17], 16)] = h
        except ValueError:
            pass
    out = {}
    for fam, wf, cf, mf in (("5m", "w5", "clean5", "mk5"), ("15m", "w15", "clean15", "mk15")):
        w = pd.read_parquet(EV / f"{wf}.parquet")
        clean = pd.read_parquet(EV / f"{cf}.parquet")
        mk = pd.read_parquet(EV / f"{mf}.parquet")
        clean["tx"] = clean["tx"].astype(np.int64)
        res, preds = inblock_price.price_inblock(mk, w, clean, txh, CLUSTER, return_preds=True)
        P = preds.assign(wallet=mk["wallet"].to_numpy()[: len(preds)] if len(preds) == len(mk) else None)
        # align predictions to fills by (full tx, token)
        mk2 = mk.assign(fh=mk["tx"].map(txh).fillna("").astype(str), token_id=mk["token_id"].astype(str))
        m = mk2.merge(preds.drop_duplicates(["tx", "token_id"]).rename(columns={"tx": "fh"}), on=["fh", "token_id"], how="left")
        st = dict(zip(w.up_token.astype(str), w.start_ts)) | dict(zip(w.down_token.astype(str), w.start_ts))
        m["st"] = m.token_id.map(st)
        m["half"] = np.where(m.st < CUT, "early", "late")
        m["ok_in"] = np.abs(m.price - m.pred_block) <= 0.0105
        rec = {"pooled_inblock": float(m.ok_in.mean()), "n": int(len(m)), "rule_report": res}
        if fam == "5m":
            F = pd.read_parquet(EXC / "price_fills.parquet")[["tx", "is_up", "price", "pred_match", "anchor_last_match", "touch_bid", "half", "wallet"]]
            F = F.rename(columns={"tx": "fh"})
            inv = {v: k for k, v in CLUSTER.items()}
            F["addr"] = F.wallet.map(inv)
            F["token_id"] = None
            mm = m.merge(F[["fh", "addr", "pred_match"]].drop_duplicates(["fh", "addr"]), left_on=["fh", "wallet"], right_on=["fh", "addr"], how="left")
            mm["r7"] = np.where(mm.pred_match.notna(), mm.pred_match, mm.pred_block)
            mm["ok7"] = np.abs(mm.price - mm.r7) <= 0.0105
            rec["r7"] = {"pooled": float(mm.ok7.mean()), "match_share": float(mm.pred_match.notna().mean()),
                         "halves": {h: float(mm.ok7[mm.half == h].mean()) for h in ("early", "late")},
                         "per_wallet": {nm: float(mm.ok7[mm.wallet == ad].mean()) for ad, nm in CLUSTER.items()},
                         "per_wallet_half": {f"{nm}_{h}": float(mm.ok7[(mm.wallet == ad) & (mm.half == h)].mean()) for ad, nm in CLUSTER.items() for h in ("early", "late")},
                         "inblock_by_half": {h: float(mm.ok_in[mm.half == h].mean()) for h in ("early", "late")}}
        else:
            rec["halves"] = {h: float(m.ok_in[m.half == h].mean()) for h in ("early", "late")}
            rec["per_wallet_half"] = {f"{nm}_{h}": float(m.ok_in[(m.wallet == ad) & (m.half == h)].mean()) for ad, nm in CLUSTER.items() for h in ("early", "late")}
        out[fam] = rec
        print(fam, json.dumps({k: v for k, v in rec.items() if k != "rule_report"}, default=str), flush=True)
    (RES / "exam_r2_price_r7.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
