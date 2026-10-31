"""Pack event clock (mechanics panel X: round-level events). Public taker orders (calldata, signing ms) of the informed
pack + the wallet's own taker orders, in-play, in the wallet's 220 CS2 markets. Team = bought outcome (BUY token oi -> oi,
SELL token oi -> 1-oi). Clusters per event: single linkage on signing time with gap <= 3 s. Output:
.cache/re/tommy-cs2-maker/pack_clusters.parquet and pack_orders.parquet; summary in results/pack_events.json."""
from __future__ import annotations
import glob, json, re, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import H, OUT, RES, SPLIT, WALLET  # noqa: E402
PACK = {"0x4ebc2722adc772bde8680792d0a6fdf15499a33d": "P4e", "0x93078b5dd1c34d0f288d2f51b23f1347520d9da3": "P93",
        "0xfe8a28be83ba295a9384f72f240d2cfa96bc23ce": "Pfe", "0x2529c68db36ce8aa64c64affe620267744a3548a": "P25",
        "0x72aaaaf9f6b0286e390de5b568af0f99a00c90e0": "P72", "0x2005d16a84ceefa912d4e380cd32e7ff827875ea": "P20",
        "0x8a80528dce46711a54aa3455c2cc81dea51e11c5": "P8a", "0xddb6e6246546230503f153506ac1e9914978b9b3": "Pdd",
        "0xf1ee4842fa0c7283632185e42577027452d4519c": "Pf1", WALLET: "W"}

def markets():
    m = json.load(open(OUT / "markets_dev.json")); rows = []
    for cid, x in m.items():
        toks = x["clobTokenIds"]; toks = json.loads(toks) if isinstance(toks, str) else toks
        mm = re.search(r"(?:Map|Game) (\d)", x.get("question", ""))
        ev = (x.get("events") or [{}])[0].get("slug")
        gs = pd.Timestamp(x["gameStartTime"].replace("+00", "+00:00") if str(x["gameStartTime"]).endswith("+00") else x["gameStartTime"]).timestamp()
        for i, t in enumerate(toks):
            rows.append({"token_id": str(t), "cid": cid, "oi": i, "event": ev, "smt": x.get("sportsMarketType"),
                         "map_no": int(mm.group(1)) if mm and x.get("sportsMarketType") == "child_moneyline" else 0, "gs": gs,
                         "cs2": x.get("question", "").startswith("Counter-Strike")})
    return pd.DataFrame(rows)

def main():
    mk = markets()
    cols = ["tx", "idx", "maker", "side", "sign_ms", "shares", "fill", "price", "token_id", "block"]
    parts = [pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(OUT / "calldata_pub/*.parquet")))]
    d = pd.concat(parts); d = d[(d.idx == -1) & d.maker.isin(PACK)]
    w = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["bts"])
    w = w[(w.idx == -1) & (w.maker == WALLET)]
    d = pd.concat([d, w.drop(columns=["bts"])]).drop_duplicates(["tx", "maker", "idx"])
    d = d[(d.sign_ms > 1.7e12) & (d.sign_ms < 1.8e12)]
    d = d.merge(mk, on="token_id", how="inner")
    d = d[d.cs2 & (d.sign_ms / 1000 >= d.gs) & (d.sign_ms / 1000 < H)]
    d["team"] = np.where(d.side == 0, d.oi, 1 - d.oi)
    d["usd"] = d.fill * np.where(d.side == 0, d.price, 1 - d.price)
    d["who"] = d.maker.map(PACK)
    d = d.sort_values(["event", "sign_ms"]).reset_index(drop=True)
    # cluster per event
    cl = np.zeros(len(d), dtype=np.int64); cid_ = -1; prev_ev = None; prev_t = -1e18
    for i, (ev, t) in enumerate(zip(d.event.to_numpy(), d.sign_ms.to_numpy())):
        if ev != prev_ev or t - prev_t > 3000: cid_ += 1
        cl[i] = cid_; prev_ev, prev_t = ev, t
    d["cluster"] = cl
    d.to_parquet(OUT / "pack_orders.parquet", index=False)
    g = d.groupby("cluster")
    c = pd.DataFrame({"event": g.event.first(), "t0": g.sign_ms.min(), "t1": g.sign_ms.max(), "n": g.size(),
                      "n_who": g.who.nunique(), "has_W": g.who.apply(lambda s: (s == "W").any()),
                      "has_P4e": g.who.apply(lambda s: (s == "P4e").any()),
                      "team_usd0": g.apply(lambda s: s.loc[s.team == 0, "usd"].sum()), "team_usd1": g.apply(lambda s: s.loc[s.team == 1, "usd"].sum()),
                      "maps": g.map_no.apply(lambda s: ",".join(str(x) for x in sorted(set(s)))), "gs": g.gs.min()}).reset_index()
    c["team"] = (c.team_usd1 > c.team_usd0).astype(int)
    c["mixed"] = (c.team_usd0 > 0) & (c.team_usd1 > 0)
    c.to_parquet(OUT / "pack_clusters.parquet", index=False)
    res = {"orders": len(d), "by_who": d.who.value_counts().to_dict(), "clusters": len(c),
           "clusters_with_W": int(c.has_W.sum()), "W_orders": int((d.who == "W").sum()),
           "W_orders_in_cluster_with_other": int(d[d.who == "W"].cluster.map(c.set_index("cluster").n_who).gt(1).sum()),
           "clusters_mixed_team_share": round(float(c.mixed.mean()), 3),
           "clusters_per_event_q": c.groupby("event").size().quantile([.1, .25, .5, .75, .9]).to_dict()}
    # gaps between consecutive clusters (same event), seconds
    c = c.sort_values(["event", "t0"]); gap = c.groupby("event").t0.diff() / 1000
    res["gap_s_q"] = gap.quantile([.05, .1, .25, .5, .75, .9]).round(1).to_dict()
    res["gap_hist"] = np.histogram(gap.dropna().clip(0, 300), bins=[0, 5, 10, 20, 30, 40, 50, 60, 80, 100, 120, 150, 200, 300])[0].tolist()
    # among W orders: who else is in its cluster, and offsets
    wc = d[d.who == "W"].cluster.unique()
    sub = d[d.cluster.isin(wc)]
    t0w = sub[sub.who == "W"].groupby("cluster").sign_ms.min()
    sub = sub.assign(off=(sub.sign_ms - sub.cluster.map(t0w)) / 1000)
    res["offset_vs_W_q"] = {k: s.off.quantile([.1, .25, .5, .75, .9]).round(3).tolist() for k, s in sub[sub.who != "W"].groupby("who") if len(s) > 30}
    res["W_first_in_cluster_share"] = round(float((sub.groupby("cluster").apply(lambda s: s.loc[s.sign_ms.idxmin(), "who"]) == "W").mean()), 3)
    res["W_team_eq_cluster_team"] = round(float((d[d.who == "W"].team.to_numpy() == d[d.who == "W"].cluster.map(c.set_index("cluster").team).to_numpy()).mean()), 3)
    json.dump(res, open(RES / "results/pack_events.json", "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))

if __name__ == "__main__":
    main()
