"""Quote placement from the live lab (post-T0 development blocks, development units only).

For each RN1 maker order (decoded calldata, unique salt) in a development unit: the recorded book of its market
(first token; the second token's book is 1 - price with sides swapped) just before its signing time, and the
book changes after it (posting latency: when a level at its price grows by about its size).
Writes results/live_quotes_<a>.json.
Usage: python live_quotes.py <block_start_ts>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import live  # noqa: E402
from common import C, R, W  # noqa: E402

ALLOW_SEALED = False


def load_books(a, b, first_tokens):
    rows = []
    import zlib

    def gen():
        for h in range(a, b, 3600):  # per hour: tools/live.py iter_live does not catch zlib.error on a corrupt file
            try:
                yield from live.iter_live("clob_wallets", h, h + 3600, allow_sealed=ALLOW_SEALED)
            except zlib.error as e:
                print("corrupt live file in hour", h, str(e)[:60], flush=True)
    for r in gen():
        if r.get("k") not in ("q", "f") or r.get("a") not in first_tokens:
            continue
        bids = r.get("b") or []
        asks = r.get("o") or []
        rows.append((r["a"], r["t"], r.get("s"), json.dumps(bids[:10]), json.dumps(asks[:10]),
                     bids[0][0] if bids else np.nan, asks[0][0] if asks else np.nan,
                     bids[0][1] if bids else np.nan, asks[0][1] if asks else np.nan))
    return pd.DataFrame(rows, columns=["tok", "t", "s", "bids", "asks", "bb", "ba", "bbz", "baz"])


def main(a):
    b = a + 6 * 3600
    od = pd.read_parquet(C / "live" / f"orders_{a}.parquet")
    un = pd.read_parquet(C / "live" / f"units_{a}.parquet")
    toks = {}
    for _, u in un.iterrows():
        try:
            tk = json.loads(u["clobTokenIds"])
        except (TypeError, ValueError):
            continue
        if len(tk) == 2:
            toks[u["conditionId"]] = tk
    od["is_rn1"] = od["maker"].str.lower() == W
    rm = od[od["is_rn1"] & (od["role"] == "maker")].drop_duplicates("salt").copy()
    rm["px"] = np.where(rm["side"] == 0, rm["maker_amount"] / rm["taker_amount"], rm["taker_amount"] / rm["maker_amount"])
    rm["shares"] = np.where(rm["side"] == 0, rm["taker_amount"], rm["maker_amount"]) / 1e6
    rm["first_tok"] = rm["cond"].map(lambda c: toks.get(c, [None, None])[0])
    rm["is_first"] = rm["token_id"] == rm["first_tok"]
    first_tokens = set(rm["first_tok"].dropna())
    bk = load_books(a, b, first_tokens)
    out = {"block": a, "rn1_maker_orders": int(len(rm)), "markets": int(rm["cond"].nunique()), "book_records": int(len(bk)),
           "markets_with_book": int(len(set(bk["tok"]) & first_tokens))}
    res = []
    for tok, g in rm.groupby("first_tok"):
        bt = bk[bk["tok"] == tok].copy()
        if bt.empty:
            continue
        bt["t"] = bt["s"].fillna(bt["t"]).astype("float64")  # server time (the recorder's clock lags ~1 s)
        bt = bt.sort_values("t").reset_index(drop=True)
        tt = bt["t"].to_numpy()
        for _, o in g.iterrows():
            ts = o["sign_ms"]
            i = np.searchsorted(tt, ts, side="right") - 1
            if i < 0:
                continue
            row = bt.iloc[i]
            # frame of the first token: RN1 BUY on the first token = a bid at px; BUY on the second = an ask at 1-px
            if o["is_first"]:
                lvl, best_same, best_opp = o["px"], row["bb"], row["ba"]
                off = lvl - best_same  # >0 improves the bid
            else:
                lvl, best_same, best_opp = 1 - o["px"], row["ba"], row["bb"]
                off = best_same - lvl  # >0 improves the ask
            spread = row["ba"] - row["bb"]
            # posting latency: first later record whose same-side level at lvl grows by >= 50% of the size
            side_key = "bids" if o["is_first"] else "asks"
            def size_at(rec):
                for p, z in json.loads(rec[side_key]):
                    if abs(p - lvl) < 1e-6:
                        return z
                return 0.0
            z0 = size_at(row)
            lat = np.nan
            for j in range(i + 1, min(i + 60, len(bt))):
                if bt.iloc[j]["t"] - ts > 10000:
                    break
                if size_at(bt.iloc[j]) - z0 >= 0.5 * o["shares"]:
                    lat = bt.iloc[j]["t"] - ts
                    break
            res.append({"cond": o["cond"], "sign_ms": ts, "px": o["px"], "shares": o["shares"], "is_first": bool(o["is_first"]),
                        "book_age_ms": ts - row["t"], "bb": row["bb"], "ba": row["ba"], "spread": spread, "off": off,
                        "at_or_inside": bool(off >= -1e-9), "post_lat_ms": lat, "z_same_before": z0,
                        "opp_gap": (best_opp - lvl) if o["is_first"] else (lvl - best_opp)})
    df = pd.DataFrame(res)
    df.to_parquet(C / "live" / f"quote_vs_book_{a}.parquet", index=False)
    if len(df):
        fresh = df[df["book_age_ms"] < 5000]
        out["n_aligned"] = int(len(df))
        out["n_fresh_book"] = int(len(fresh))
        out["off_ticks_dist"] = {str(k): int(v) for k, v in (fresh["off"] / 0.01).round().clip(-5, 5).value_counts().sort_index().items()}
        out["spread_ticks_dist"] = {str(k): int(v) for k, v in (fresh["spread"] / 0.01).round().clip(0, 10).value_counts().sort_index().items()}
        out["opp_gap_ticks_dist"] = {str(k): int(v) for k, v in (fresh["opp_gap"] / 0.01).round().clip(-3, 10).value_counts().sort_index().items()}
        out["post_lat_ms"] = {str(q): float(fresh["post_lat_ms"].quantile(q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
        out["post_lat_found_share"] = float(fresh["post_lat_ms"].notna().mean())
        out["shares_q"] = {str(q): float(fresh["shares"].quantile(q)) for q in (0.1, 0.5, 0.9)}
    print(json.dumps(out, indent=1))
    json.dump(out, open(R / "results" / f"live_quotes_{a}.json", "w"), indent=1)


if __name__ == "__main__":
    main(int(sys.argv[1]))
