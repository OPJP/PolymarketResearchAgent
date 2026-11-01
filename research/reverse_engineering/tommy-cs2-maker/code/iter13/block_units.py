"""Iteration 13: development-unit markets of the current VALIDATE-live block (11-01 06-12 UTC) and the wallet's
trades in them. Only units whose gameStartTime lies in a development block are kept (sealed units are dropped
before anything else is read); wallet trades are requested per kept market only."""
import json, sys, time, os
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from polyrea.adapters.polymarket import PolymarketData, DATA_API  # noqa
import live, sealed  # noqa
KEY = "tommy-cs2-maker"; WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OUT = ROOT / ".cache/re/tommy-cs2-maker"
B0 = int(os.environ.get("TOMMY_BLOCK_START", 1793512800)); B1 = int(os.environ.get("TOMMY_BLOCK_END", 1793534400))
SUF = os.environ.get("TOMMY_BLOCK_SUFFIX", "_v1101a")

def gs_ts(x):
    if isinstance(x, (int, float)) and x == x: return float(x)
    try:
        s = str(x)
        if s.endswith("+00"): s = s + ":00"
        return pd.Timestamp(s).timestamp()
    except Exception: return None

def it(feed, a, b):
    try:
        for r in live.iter_live(feed, a, b): yield r
    except Exception as e:
        print("iter_live stop", feed, type(e).__name__, flush=True)

def main():
    now = time.time(); m = {}
    for r in it("tommy_cs2_near", B0 - 6 * 3600, min(now, B1)):
        if r.get("k") == "sub":
            for cid, v in r["m"].items():
                m[cid] = {"cid": cid, "tok0": str(v[0]), "tok1": str(v[1]), "gs": gs_ts(v[2]), "slug": v[3]}
    df = pd.DataFrame(m.values())
    print("subscribed", len(df), flush=True)
    df = df[df.gs.notna() & (df.gs >= B0) & (df.gs < B1)]
    df = df[~df.gs.map(lambda g: sealed.is_sealed(int(g), KEY))].copy()
    df["event"] = df.slug.str.replace(r"-game\d+$", "", regex=True)
    print("dev-unit markets", len(df), "events", df.event.nunique(), flush=True)
    pm = PolymarketData(); rows = []
    for cid in df.cid:
        off = 0
        while True:
            d, _ = pm.http.get_json(f"{DATA_API}/trades", {"market": cid, "user": WALLET, "takerOnly": "false", "limit": 500, "offset": off},
                                    adapter="data-api.trades", max_age=120)
            d = d or []; rows += d
            if len(d) < 500 or off > 5000: break
            off += 500
    w = pd.DataFrame(rows)
    df["wallet_trades"] = df.cid.map(w.groupby("conditionId").size() if len(w) else {}).fillna(0).astype(int)
    df.to_parquet(OUT / f"dev_markets{SUF}.parquet", index=False)
    if len(w): w.to_parquet(OUT / f"dev_wallet_trades{SUF}.parquet", index=False)
    ev = df.groupby("event").agg(gs=("gs", "min"), n=("cid", "size"), wt=("wallet_trades", "sum")).sort_values("gs")
    ev["gs"] = pd.to_datetime(ev.gs, unit="s").dt.strftime("%H:%M")
    print(ev.to_string())
main()
