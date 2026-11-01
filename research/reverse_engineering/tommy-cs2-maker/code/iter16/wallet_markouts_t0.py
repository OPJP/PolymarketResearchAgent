"""X230 step 3 (assumptions panel iter-15 P4): is the wallet's information still there after T0? Its new-high value
changes (burst top above the previous three tops on the token, 50-ms chains of its maker orders) on the 10-31 12-18
development block (calldata_dev, signing clamped to the block end 18:00 UTC; units started in the block), and the clean
print's move their way at 60 s (data-api taker tape of its markets, wallet txs removed, fetched clamped to 18:00).
Reference: the same statistic on 16-22 Oct (dark_split rows). Output: results/wallet_markouts_t0.json"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import sealed  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
A, B = 1793448000, 1793469600
SP = Path(r"C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/m14/dark_split.parquet")


def newhigh_markouts(orders, tape):
    rows = []
    for tok, g in orders.groupby("token_id"):
        tk = tape[tape.asset.astype(str) == str(tok)]
        cid = tk.cid.iloc[0] if len(tk) else None
        if cid is None:
            continue
        pp = tape[tape.cid == cid].sort_values("timestamp")
        ts = pp.timestamp.to_numpy(float)
        pt = np.where(pp.asset.astype(str) == str(tok), pp.price.astype(float), 1 - pp.price.astype(float))
        s, p = g.sign_ms.to_numpy(float), g.price.to_numpy(float)
        tops, i = [], 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and s[j + 1] - s[i] <= 50:
                j += 1
            tops.append((s[i] / 1000.0, p[i:j + 1].max()))
            i = j + 1
        for k in range(1, len(tops)):
            t0, top = tops[k]
            prev = max(x[1] for x in tops[max(0, k - 3):k])
            if top > prev + 1e-9 and top > tops[k - 1][1] + 1e-9:
                j0 = np.searchsorted(ts, t0, side="right") - 1
                j1 = np.searchsorted(ts, t0 + 60, side="right") - 1
                if j0 >= 0:
                    rows.append(float(pt[j1] - pt[j0]) * 100)
    return np.array(rows)


def main():
    act = pd.read_parquet(OUT / "activity_devblocks.parquet")
    act = act[(act.type == "TRADE") & (act.timestamp >= A) & (act.timestamp < B)]
    cids = act.conditionId.unique().tolist()
    gs = act.groupby("conditionId").gs.first().to_dict() if "gs" in act else {}
    pm = PolymarketData()
    rows = []
    for cid in cids:
        g0 = float(gs.get(cid, A))
        assert not sealed.is_sealed(g0, "tommy-cs2-maker"), cid
        rws, _, _ = pm.market_trades(cid, start=A - 3600, end=B - 1, taker_only=True)
        for x in rws:
            x = dict(x)
            x["cid"] = cid
            rows.append(x)
    T = pd.DataFrame(rows)
    T["proxyWallet"] = T.proxyWallet.str.lower()
    c = pd.read_parquet(OUT / "calldata_dev.parquet")
    wtx = set(c.loc[c.maker.str.lower() == W, "tx"]) | set(T.loc[T.proxyWallet == W, "transactionHash"])
    T = T[(T.timestamp < B) & ~T.transactionHash.isin(wtx)]
    mo = c[(c.maker.str.lower() == W) & (c.idx >= 0) & (c.sign_ms / 1000 >= A) & (c.sign_ms / 1000 < B)].drop_duplicates(["salt", "sign_ms"]).sort_values("sign_ms")
    m = newhigh_markouts(mo, T)
    d = pd.read_parquet(SP).sort_values(["tok", "t"])
    pmax = d.groupby("tok").top.transform(lambda x: x.shift(1).rolling(3, min_periods=1).max())
    nh = d[(d.dtop > 0) & (d.top > pmax + 1e-9)]
    out = {"block": "10-31 12-18", "markets": len(cids), "wallet_maker_orders": int(len(mo)), "new_highs": int(len(m)),
           "mean_m60_c": round(float(m.mean()), 3) if len(m) else None,
           "share_up": round(float((m > 0).mean()), 3) if len(m) else None, "share_down": round(float((m < 0).mean()), 3) if len(m) else None,
           "reference_16_22_oct_all_new_highs": {p: {"n": int(len(g)), "mean_m60_c": round(float(g.m60.mean()), 3)} for p, g in nh.groupby("period")}}
    (RES / "wallet_markouts_t0.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
