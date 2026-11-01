"""Iteration 9 (mechanics M4 = X82): salt-counter forensics of the 10-31 16:53 UTC BTC 5m switch-off (development
block 12-18). For every cluster fill transaction (all markets) in [15:50, 18:00), the V2 calldata gives each cluster
order's per-wallet sequential salt. Per wallet: salt against block time before and after the last BTC 5m trade (slope =
signed orders per second, jump at the switch). A running controller that stops signing BTC 5m orders keeps the counter
continuous and lowers the slope by BTC 5m's share; a restart resets or jumps it; a gate after signing leaves the slope
unchanged. Writes results/iter9_m4_salt.json."""
import glob
import json
import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code4"))
import calldata as CD  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
OUT = C / "calldata"
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
     "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "mo-money"}
A, B = 1793465400, 1793469600  # 15:50-18:00


def main():
    act = pd.read_parquet(C / "it9" / "act_1793448000_1793469600.parquet")
    act = act[(act.type == "TRADE") & (act.timestamp >= A) & (act.timestamp < B)].copy()
    act["tx"] = act.transactionHash.str.lower()
    ts_of = act.groupby("tx").timestamp.min().to_dict()
    have = set()
    rows = []
    for p in glob.glob(str(OUT / "*1031_*.parquet")) + glob.glob(str(OUT / "it9sw_*.parquet")):
        d = pd.read_parquet(p)
        d["tx"] = d.tx.str.lower()
        d = d[d.tx.isin(ts_of)]
        have |= set(d.tx)
        rows.append(d)
    need = [h for h in sorted(ts_of, key=ts_of.get) if h not in have]
    print("txs", len(ts_of), "have", len(have), "fetch", len(need), flush=True)
    new = []
    if need:
        cl = httpx.Client(timeout=30)
        for h, tx in CD.fetch_txs(need, batch=25, pause=0.2, client=cl):
            if tx is None:
                continue
            d = CD.decode(tx.get("input", ""))
            if d is None:
                continue
            for i, o in enumerate([d["taker"]] + d["makers"]):
                r = dict(o)
                r.update(tx=h.lower(), block=int(tx["blockNumber"], 16), role="taker" if i == 0 else "maker", idx=i)
                new.append(r)
        if new:
            nd = pd.DataFrame(new)
            for c in ("maker_amount", "taker_amount", "sign_ms"):
                if c in nd:
                    nd[c] = pd.to_numeric(nd[c], errors="coerce").astype("float64")
            nd["salt"] = nd["salt"].astype(str)
            nd.to_parquet(OUT / f"it9sw_{A}_{B}.parquet")
            rows.append(nd)
    D = pd.concat(rows, ignore_index=True)
    D["maker"] = D.maker.str.lower()
    D = D[D.maker.isin(W)].copy()
    D["salt"] = pd.to_numeric(D.salt.astype(str), errors="coerce")
    D["ts"] = D.tx.map(ts_of)
    D = D.dropna(subset=["salt", "ts"]).drop_duplicates(subset=["maker", "salt"])
    b5 = act[act.slug.str.startswith("btc-updown-5m", na=False)]
    t_off = int(b5.timestamp.max())
    out = {"t_last_btc5m_trade": t_off, "t_last_btc5m_utc": pd.to_datetime(t_off, unit="s").strftime("%H:%M:%S")}
    for w, nm in W.items():
        g = D[D.maker == w].sort_values("ts")
        g = g[g.salt < g.salt.median() * 100]  # drop random (non-counter) salts if any
        pre = g[(g.ts >= t_off - 1800) & (g.ts <= t_off)]
        post = g[(g.ts > t_off) & (g.ts <= t_off + 3600)]
        rec = {"orders": int(len(g)), "pre_n": int(len(pre)), "post_n": int(len(post))}
        if len(pre) >= 5 and len(post) >= 5:
            bp = np.polyfit(pre.ts - t_off, pre.salt, 1)
            bq = np.polyfit(post.ts - t_off, post.salt, 1)
            rec.update(slope_pre=float(bp[0]), slope_post=float(bq[0]), jump_at_switch=float(bq[1] - bp[1]),
                       resid_sd_pre=float(np.std(pre.salt - np.polyval(bp, pre.ts - t_off))),
                       resid_sd_post=float(np.std(post.salt - np.polyval(bq, post.ts - t_off))),
                       last_pre=(int(pre.ts.iloc[-1]), float(pre.salt.iloc[-1])), first_post=(int(post.ts.iloc[0]), float(post.salt.iloc[0])),
                       monotone_share=float(np.mean(np.diff(g.salt.to_numpy()) >= 0)))
        out[nm] = rec
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter9_m4_salt.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
