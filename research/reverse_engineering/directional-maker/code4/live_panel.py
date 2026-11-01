"""Live lab (development blocks only, through livex.iter_live): per (BTC 5m window, side, 10-s bin) book features at
the bin start from the recorder's clob_crypto Up-token book, plus the cluster's maker BUY fills in the bin as label.
Prepared in iteration 4 for the quote-state paradigm (is the cluster's bid at the top of the book?).

python live_panel.py START END   -> .cache/re/directional-maker/live_panel_<START>_<END>.parquet
Features (side s; Down book = mirror of the Up book): best bid / ask of s, spread, depth at the best bid and within
2 ticks, depth at the best ask, book updates in the last 10 s, age of the current best bid level, best-bid change over
10 s. Point-in-time: the last book snapshot with server time < bin start."""
import glob, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import livex  # noqa
C = HERE.parents[3] / ".cache/re/directional-maker"


def side_book(bids, asks, up):
    if up:
        return [(p, z) for p, z in bids], [(p, z) for p, z in asks]
    return [(round(1 - p, 3), z) for p, z in asks], [(round(1 - p, 3), z) for p, z in bids]


def main(a, b):
    sys.path.insert(0, str(HERE.parent / "code"))
    import final_rule  # Gamma listings (tokens) through the polyrea adapters
    wl = final_rule._windows(a, b)
    subs = {int(r.start_ts): [r.up_token, r.down_token] for r in wl.itertuples()}
    starts = sorted(s for s in subs if a <= s and s + 300 <= b)
    want = {subs[s][0]: s for s in starts}
    snaps = {t: [] for t in want}
    for r in livex.iter_live("clob_crypto", a - 60, b):
        if r["k"] in ("q", "f") and r["a"] in want:
            snaps[r["a"]].append((r.get("s", r["t"]) / 1000.0, r["b"], r["o"]))
    acts = sorted(glob.glob(str(C / "live_activity_*.parquet")))
    act = pd.concat([pd.read_parquet(p) for p in acts]).drop_duplicates(["transactionHash", "asset", "w", "size"]) if acts else pd.DataFrame()
    rows = []
    for tok, st in want.items():
        sn = snaps[tok]
        if not sn:
            continue
        ts = np.array([x[0] for x in sn])
        down_tok = subs[st][1]
        for up in (True, False):
            fills = act[(act.type == "TRADE") & (act.side == "BUY") & (act.asset == (tok if up else down_tok))] if len(act) else act
            for rel in range(0, 300, 10):
                t = st + rel
                i = np.searchsorted(ts, t) - 1
                if i < 0:
                    continue
                bb, aa = side_book(sn[i][1], sn[i][2], up)
                j = np.searchsorted(ts, t - 10) - 1
                bb10 = side_book(sn[j][1], sn[j][2], up)[0] if j >= 0 else []
                best_b = bb[0][0] if bb else np.nan
                k = i
                while k > 0:
                    b2 = side_book(sn[k - 1][1], sn[k - 1][2], up)[0]
                    if not b2 or b2[0][0] != best_b:
                        break
                    k -= 1
                y = int(((fills.timestamp >= t) & (fills.timestamp < t + 10)).sum() > 0) if len(fills) else 0
                rows.append({"start_ts": st, "rel": rel, "side_up": int(up), "best_bid": best_b,
                             "best_ask": aa[0][0] if aa else np.nan, "spread": (aa[0][0] - best_b) if (aa and bb) else np.nan,
                             "depth_best_bid": bb[0][1] if bb else 0.0, "depth_bid_2t": sum(z for p, z in bb if p >= best_b - 0.02 + 1e-9),
                             "depth_best_ask": aa[0][1] if aa else 0.0, "updates_10s": int(i - max(j, 0)),
                             "best_bid_age": t - sn[k][0], "best_bid_chg10": best_b - (bb10[0][0] if bb10 else np.nan), "y": y})
    d = pd.DataFrame(rows)
    d.to_parquet(C / f"live_panel_{a}_{b}.parquet")
    print("bins", len(d), "windows", d.start_ts.nunique() if len(d) else 0, "positives", int(d.y.sum()) if len(d) else 0)
    if len(d) and d.y.sum():
        print(d.groupby("y")[["spread", "depth_best_bid", "updates_10s", "best_bid_age", "best_bid"]].median().round(3).to_string())


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
