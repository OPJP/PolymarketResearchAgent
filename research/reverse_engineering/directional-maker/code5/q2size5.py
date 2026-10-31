"""Q2 (panel X21): size in the outcome metric. Rebuilds R3's per-window rule PnL on a period (same code path as
final_rule.evaluate, local caches of the lot) and correlates it with the wallets' per-window dollar PnL:
  per-share rule (R3 as frozen), x public size_hat (clock: 500 in the weekday US session, else 62; frozen from STUDY),
  x own-state size_hat (largest single cluster BTC 5m fill in the 30 min before the window start; reported separately),
and the ceiling: the wallets' own fills at one share each.
    python q2size5.py <start> <end>    (VALIDATE: aggregate numbers only)
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402

F.CACHE = ROOT / ".cache/re/directional-maker/exam"


def main(a, b):
    import lightgbm as lgb
    from polyrea.adapters.polymarket import PolymarketData
    t0 = time.time()
    pm = PolymarketData()
    w = pd.read_parquet(F.CACHE / "windows_5m.parquet")
    w = w[(w.start_ts >= a) & (w.start_ts < b)].sort_values("start_ts").reset_index(drop=True)
    tk = F._tapes(w, pm, b, True)
    spd = pd.read_parquet(F.CACHE / "spot_btc_1s.parquet")
    spd = spd[(spd["sec"] >= a - 7200) & (spd["sec"] < b)]
    sp = F.Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    ct = F._cluster_trades(a - 3600, b, pm, True)
    toks = set(w["up_token"]) | set(w["down_token"])
    buys = ct[(ct["side"] == "BUY") & ct["token_id"].isin(toks)].copy()
    own_rows = tk[tk["wallet"].isin(set(F.CLUSTER))]
    taker_pairs = set(zip(own_rows["tx"], own_rows["wallet"].astype(str)))
    buys["role"] = ["taker" if (x, y) in taker_pairs else "maker" for x, y in zip(buys["tx"], buys["wallet"])]
    mk = buys[(buys["role"] == "maker") & (buys.ts >= a)]
    clean = F.clean_tape(tk, set(ct["tx"]), set(F.CLUSTER))
    panel = F.build_panel(w, sp, clean, mk)
    panel = F._add_clock(panel)
    m = lgb.Booster(model_file=str(F.HERE / "presence3_rule.txt"))
    panel["p"] = m.predict(panel[F.FEATS["rule"]])
    upset = set(w["up_token"])
    tok2cid = {**dict(zip(w["up_token"], w["cid"])), **dict(zip(w["down_token"], w["cid"]))}
    pay = dict(zip(w["cid"], w["up_payout"]))
    mk2 = mk.assign(c=[tok2cid.get(t) for t in mk["token_id"]], up=mk["token_id"].isin(upset))
    mk2["won"] = [(pay.get(c) if u else 1 - pay.get(c)) if pay.get(c) is not None else np.nan for c, u in zip(mk2["c"], mk2["up"])]
    wal = ((mk2["won"] - mk2["price"]) * mk2["shares"]).groupby(mk2["c"]).sum()
    one_share = (mk2["won"] - mk2["price"]).groupby(mk2["c"]).sum()
    pr = panel.dropna(subset=["won_s"]).copy()
    pr["rule_pnl"] = pr["p"] * (pr["won_s"] - (pr["last_s"].fillna(0.5) - F.PRICE_OFFSET).round(2))
    rule = pr.groupby("cid")["rule_pnl"].sum()
    ws = w.set_index("cid")
    st = pd.to_datetime(ws.start_ts, unit="s")
    us = (st.dt.dayofweek < 5) & (st.dt.hour >= 12) & (st.dt.hour < 21)
    size_pub = pd.Series(np.where(us, 500.0, 62.0), index=ws.index)
    # own state: largest single BTC 5m maker fill of the cluster in the 30 min before the window start
    allb = buys[buys.role == "maker"].sort_values("ts")
    bts, bsz = allb.ts.to_numpy(), allb.shares.to_numpy()
    own = []
    for c, s0 in zip(ws.index, ws.start_ts):
        i, j = np.searchsorted(bts, s0 - 1800), np.searchsorted(bts, s0)
        own.append(bsz[i:j].max() if j > i else np.nan)
    size_own = pd.Series(own, index=ws.index)
    size_own = size_own.fillna(size_own.median())
    j = pd.concat([wal.rename("wallet"), rule.rename("rule"), one_share.rename("one"), size_pub.rename("sp"), size_own.rename("so")], axis=1)
    j = j.dropna(subset=["wallet", "rule"])

    def corr(x, y):
        return {"pearson": float(np.corrcoef(x, y)[0, 1]), "spearman": float(pd.Series(x).corr(pd.Series(y), method="spearman"))}
    res = {"period": [a, b], "windows": int(len(j)), "runtime_s": round(time.time() - t0),
           "rule_per_share": corr(j.rule, j.wallet),
           "rule_x_size_public_clock": corr(j.rule * j.sp, j.wallet),
           "rule_x_size_own_prev30min_maxfill": corr(j.rule * j.so, j.wallet),
           "ceiling_wallet_fills_one_share": corr(j.one.fillna(0), j.wallet),
           "ceiling_one_share_x_size_own": corr(j.one.fillna(0) * j.so, j.wallet),
           "size_pub_share_500": float((j.sp == 500).mean()),
           "corr_size_own_vs_wallet_abs_pnl": float(np.corrcoef(j.so, j.wallet.abs())[0, 1])}
    print(json.dumps(res, indent=1))
    (HERE.parent / "results" / f"iter5_q2size_{a}_{b}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
