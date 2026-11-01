"""Examiner: build the frozen rule's point-in-time panel on the holdout, one UTC day at a time, with the rule's own
feature code (features2.build_panel, clean tape) and the frozen model files, and save the scored panel.

python exam_panel.py           writes .cache/re/directional-maker/exam/panel_day_<d>.parquet for every holdout day
                               plus fills_holdout.parquet (cluster BTC 5m BUY fills with the tape-inferred role)
Mirrors final_rule.evaluate: windows of the whole holdout in one ordered list, the previous window of each day is
included (for prev_n) except for the first holdout window, whose previous window is development data.
"""
from __future__ import annotations

import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CODE = HERE.parent / "code"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CODE))
from features2 import Spot, build_panel, clean_tape  # noqa: E402
from train2 import SETS  # noqa: E402

H = 1792713600
EX = ROOT / ".cache/re/directional-maker/exam"
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
MODELS = ("all_path_xwin", "activity", "all_path_xwin+own")
KEEP = ["cid", "start_ts", "rel", "side_up", "y", "last_s", "fair_s", "edge_s", "won_s", "hit_s10", "hit_o10", "inv_s", "inv_o",
        "n_in", "sig"]


def txint(x: pd.Series) -> pd.Series:
    def one(h):
        try:
            return int(h, 16)
        except (TypeError, ValueError):
            return 0
    return x.astype(str).str.slice(2, 17).map(one).astype(np.int64)


def cluster_trades(end: int) -> pd.DataFrame:
    fr = []
    for addr, name in CLUSTER.items():
        a = pd.read_parquet(EX / f"activity_{name}.parquet")
        a = a[(a["type"] == "TRADE") & (a["timestamp"] >= H) & (a["timestamp"] < end)]
        fr.append(pd.DataFrame({"wallet": addr, "tx": txint(a["transactionHash"]), "txh": a["transactionHash"].astype(str),
                                "token_id": a["asset"].astype(str), "ts": a["timestamp"].astype(np.int64), "side": a["side"],
                                "price": a["price"].astype(float), "shares": a["size"].astype(float), "cid": a["conditionId"]}))
    return pd.concat(fr, ignore_index=True)


def load_tape(d: int) -> pd.DataFrame:
    t = pd.read_parquet(EX / f"taker5m_day_{d}.parquet")
    t["tx"] = txint(t["tx"])
    return t


def main(lag: int = 0) -> None:
    """lag > 0 (robustness only): every tape print and Binance second is made available `lag` seconds later than the
    rule assumes (timestamps shifted by +lag), labels unchanged; only the scores are saved (panel_lag<lag>_day_*)."""
    w = pd.read_parquet(EX / "windows_5m.parquet").sort_values("start_ts").reset_index(drop=True)
    end = int(w["end_ts"].max())
    spd = pd.read_parquet(EX / "spot_btc_1s.parquet")
    sp = Spot(spd["sec"].to_numpy() + lag, spd["px"].to_numpy())
    ct = cluster_trades(end)
    ctx, cw = set(ct["tx"]), set(CLUSTER)
    toks = set(w["up_token"]) | set(w["down_token"])
    buys_all = ct[(ct["side"] == "BUY") & ct["token_id"].isin(toks)].copy()
    models = {nm: lgb.Booster(model_file=str(CODE / f"presence2_{nm}.txt")) for nm in MODELS}
    days = sorted(set(w["start_ts"] // 86400 * 86400))
    have = {int(f.stem.split("_")[-1]) for f in EX.glob("taker5m_day_*.parquet")}
    fills = []
    for d in days:
        if d not in have:
            print("day", d, "no tape yet", flush=True)
            continue
        wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400)]
        tk = load_tape(d)
        tk = tk[tk["cid"].isin(set(wd["cid"]))]
        if lag:
            tk["ts"] = tk["ts"] + lag
        tok_d = set(wd["up_token"]) | set(wd["down_token"])
        b = buys_all[buys_all["token_id"].isin(tok_d)].copy()
        own_rows = tk[tk["wallet"].isin(cw)]
        taker_pairs = set(zip(own_rows["tx"], own_rows["wallet"]))
        b["role"] = ["taker" if (x, y) in taker_pairs else "maker" for x, y in zip(b["tx"], b["wallet"])]
        fills.append(b)
        mk = b[b["role"] == "maker"]
        clean = clean_tape(tk, ctx, cw)
        out_f = EX / (f"panel_lag{lag}_day_{d}.parquet" if lag else f"panel_day_{d}.parquet")
        if out_f.exists():
            print("day", d, "exists", flush=True)
            continue
        wp = wd
        if d > days[0]:  # previous window (for prev_n), as in one evaluate() call over the holdout
            pw = w[w["start_ts"] == int(wd["start_ts"].min()) - 300]
            pt = load_tape(d - 86400)
            pt = clean_tape(pt[pt["cid"].isin(set(pw["cid"]))], ctx, cw)
            if lag:
                pt["ts"] = pt["ts"] + lag
            wp = pd.concat([pw, wd], ignore_index=True)
            clean = pd.concat([pt, clean], ignore_index=True)
        p = build_panel(wp, sp, clean, mk)
        p = p[p["cid"].isin(set(wd["cid"]))].reset_index(drop=True)
        for nm in MODELS:
            p["p_" + nm] = models[nm].predict(p[SETS[nm]]).astype(np.float32)
        if lag:
            p[["cid", "start_ts", "rel", "side_up", "y"] + ["p_" + nm for nm in MODELS]].to_parquet(EX / f"panel_lag{lag}_day_{d}.parquet", index=False)
        else:
            p.to_parquet(EX / f"panel_day_{d}.parquet", index=False)  # all rule features + scores (selection reuses them)
        print("day", d, "windows", len(wd), "tape", len(tk), "clean", len(clean), "maker", len(mk),
              "taker", int((b["role"] == "taker").sum()), "pos", round(float(p["y"].mean()), 4), flush=True)
        del tk, clean, p
    if not lag and len(have) == len(days):
        pd.concat(fills, ignore_index=True).to_parquet(EX / "fills_holdout.parquet", index=False)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
