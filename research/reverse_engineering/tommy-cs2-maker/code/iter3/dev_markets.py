"""Dev-unit market list (iteration 3): every CS2 match / map-winner market the own recorder (tommy_cs2_near)
subscribed, plus the wallet's dev-unit markets of iteration 2, keeping only units whose gameStartTime is in a
development block at or after T0 (sealed units are dropped before anything else is read). For each kept market:
the wallet's trades in it (data-api /trades?user&market, takerOnly=false), so no sealed unit's wallet activity is
ever requested. Output: .cache/re/tommy-cs2-maker/dev_markets.parquet, dev_wallet_trades.parquet"""
import json, sys, time
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from polyrea.adapters.polymarket import PolymarketData, DATA_API  # noqa
import live, sealed  # noqa
KEY = "tommy-cs2-maker"; WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"; T0 = 1793404800
OUT = ROOT / ".cache/re/tommy-cs2-maker"

def gs_ts(x):
    if isinstance(x, (int, float)) and x == x:
        return float(x)
    try:
        s = str(x)
        if s.endswith("+00"): s = s + ":00"
        return pd.Timestamp(s).timestamp()
    except Exception:
        return None

def main():
    now = time.time()
    m = {}
    for r in live.iter_live("tommy_cs2_near", T0, now):
        if r.get("k") == "sub":
            for cid, v in r["m"].items():
                m[cid] = {"cid": cid, "tok0": str(v[0]), "tok1": str(v[1]), "gs": gs_ts(v[2]), "slug": v[3]}
    a = pd.read_parquet(OUT / "activity_devblocks.parquet")
    pm = PolymarketData()
    extra = sorted(set(a.conditionId) - set(m))
    if extra:
        mk, _ = pm.markets_by_condition(extra)
        for cid, x in mk.items():
            t = x["clobTokenIds"]; t = json.loads(t) if isinstance(t, str) else t
            m[cid] = {"cid": cid, "tok0": str(t[0]), "tok1": str(t[1]), "gs": gs_ts(x.get("gameStartTime")), "slug": x.get("slug")}
    df = pd.DataFrame(m.values())
    n0 = len(df)
    df = df[df.gs.notna() & (df.gs >= T0)]
    df = df[~df.gs.map(lambda g: sealed.is_sealed(int(g), KEY))].copy()
    df["event"] = df.slug.str.replace(r"-game\d+$", "", regex=True)
    print("markets subscribed", n0, "dev-unit", len(df), "events", df.event.nunique(), flush=True)
    rows = []
    for cid in df.cid:
        off = 0
        while True:
            d, _ = pm.http.get_json(f"{DATA_API}/trades", {"market": cid, "user": WALLET, "takerOnly": "false", "limit": 500, "offset": off},
                                    adapter="data-api.trades", max_age=300)
            d = d or []
            rows += d
            if len(d) < 500 or off > 5000: break
            off += 500
    w = pd.DataFrame(rows)
    df["wallet_trades"] = df.cid.map(w.groupby("conditionId").size() if len(w) else {}).fillna(0).astype(int)
    df.to_parquet(OUT / "dev_markets.parquet", index=False)
    if len(w):
        for c in w.columns:
            if w[c].dtype == object: w[c] = w[c].astype(str)
        w.to_parquet(OUT / "dev_wallet_trades.parquet", index=False)
    g = df.groupby("event").agg(gs=("gs", "min"), mk=("cid", "size"), wt=("wallet_trades", "sum")).sort_values("gs")
    g["gs"] = pd.to_datetime(g.gs, unit="s").dt.strftime("%m-%d %H:%M")
    print(g.to_string())

if __name__ == "__main__":
    main()
