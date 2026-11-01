"""Control for the lead test (T1): the same quote-lead regression for the other makers in the same markets.
All filled maker orders come from the decoded calldata of every public taker transaction in the wallet's markets
(calldata_all + calldata_pub). For each maker order: x = limit price - last public print (outcome terms) at its
signing time; f_h = public price change over the next h s (prints of that maker's own transactions excluded);
edge = settlement value - price (per share) of its fills; markout60. Development data only."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import H, OUT, RES, TAPES, WALLET, SPLIT  # noqa: E402
from orders import market_meta  # noqa: E402

def load_all():
    parts = sorted((OUT / "calldata_pub").glob("part_*.parquet"))
    pub = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    tape_ts = {}
    allc = pd.read_parquet(OUT / "calldata_all.parquet")
    mm = market_meta()
    pub = pub.merge(mm[["token_id", "cid", "oi", "smt", "gs_ts", "event"]], on="token_id", how="left")
    # block ts for pub txs from the tapes
    tp = pd.read_parquet(OUT / "public_tx_todo.parquet")
    pub["bts"] = pub["tx"].map(dict(zip(tp["tx"], tp["bts"])))
    cols = ["tx", "idx", "maker", "side", "token_id", "price", "shares", "sign_ms", "fill", "cid", "oi", "gs_ts", "bts", "smt"]
    a = pd.concat([allc[cols], pub[cols]], ignore_index=True).drop_duplicates(["tx", "idx"])
    a = a[a["bts"] < H]
    return a

def main():
    a = load_all()
    a = a[a["cid"].notna()].copy()
    a["oi"] = a["oi"].astype(int)
    ok = (a["sign_ms"] > 1.7e12) & (a["sign_ms"] < 1.8e12) & (a["sign_ms"] / 1000 <= a["bts"] + 2)
    res = {"rows": len(a), "valid_sign_share": round(float(ok.mean()), 3)}
    a = a[ok]
    # orders: BUY orders priced in their own token; SELL orders of token t at p are equivalent to BUY of the
    # complement at 1-p: express every order as a BUY of outcome o at q
    a["o"] = np.where(a["side"] == 0, a["oi"], 1 - a["oi"])
    a["q"] = np.where(a["side"] == 0, a["price"], 1 - a["price"])
    m = json.load(open(OUT / "markets_dev.json"))
    win = {}
    for cid, x in m.items():
        op = x.get("outcomePrices"); op = json.loads(op) if isinstance(op, str) else op
        try:
            vals = [float(v) for v in op]; win[cid] = int(np.argmax(vals)) if max(vals) > 0.9 else -1
        except Exception:
            win[cid] = -1
    a["win"] = a["cid"].map(win)
    mk = a[a["idx"] >= 0]
    key = ["maker", "sign_ms", "token_id", "price", "shares", "side"]
    o = mk.groupby(key, sort=False).agg(cid=("cid", "first"), o=("o", "first"), q=("q", "first"), gs=("gs_ts", "first"),
                                       t_fill=("bts", "min"), filled=("fill", "sum"), win=("win", "first")).reset_index()
    o["t"] = o["sign_ms"] / 1000
    o["life"] = o["t_fill"] - o["t"]
    top = o["maker"].value_counts()
    keep = [WALLET] + [x for x in top.index if x != WALLET][:30]
    o = o[o["maker"].isin(keep)]
    txs_of = a.groupby("maker")["tx"].apply(set).to_dict()
    out = []
    for cid, g in o.groupby("cid"):
        p = TAPES / f"{cid}_tkw.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p, columns=["timestamp", "price", "outcomeIndex", "transactionHash"])
        d = d[d["timestamp"] < H].sort_values("timestamp", kind="stable")
        if len(d) == 0:
            continue
        p0all = np.where(d["outcomeIndex"].astype(int) == 0, d["price"].astype(float), 1 - d["price"].astype(float))
        for mkr, gg in g.groupby("maker"):
            keepm = ~d["transactionHash"].isin(txs_of.get(mkr, set())).to_numpy()
            ts = d["timestamp"].to_numpy(np.int64)[keepm]; p0 = p0all[keepm]
            if len(ts) == 0:
                continue
            t = gg["t"].to_numpy(float); oo = gg["o"].to_numpy(int)
            def px(at):
                i = np.searchsorted(ts, at, side="left")
                v = np.where(i > 0, p0[np.maximum(i - 1, 0)], np.nan)
                return np.where(oo == 0, v, 1 - v)
            r = pd.DataFrame({"maker": mkr, "cid": cid, "gs": gg["gs"].to_numpy(), "q": gg["q"].to_numpy(),
                              "last": px(t), "life": gg["life"].to_numpy(), "filled": gg["filled"].to_numpy(),
                              "edge": np.where(gg["win"].to_numpy() >= 0, (gg["win"].to_numpy() == oo).astype(float) - gg["q"].to_numpy(), np.nan),
                              "mko60": px(gg["t_fill"].to_numpy() + 60) - gg["q"].to_numpy()})
            for h in (10, 30, 60, 120):
                r[f"f{h}"] = px(t + h) - r["last"]
            out.append(r)
    x = pd.concat(out, ignore_index=True).dropna(subset=["last"])
    x["x"] = x["q"] - x["last"]
    x.to_parquet(OUT / "maker_compare.parquet", index=False)
    rows = []
    for mkr, s in x.groupby("maker"):
        if len(s) < 300:
            continue
        r = {"maker": mkr[:10], "is_wallet": mkr == WALLET, "n": len(s), "life_med": round(float(s["life"].median()), 1),
             "edge_per_share_c": round(float(np.nanmean(s["edge"]) * 100), 2),
             "edge_usd_wavg_c": round(float(np.nansum(s["edge"] * s["filled"]) / np.nansum(s["q"] * s["filled"]) * 100), 2),
             "mko60_c": round(float(np.nanmean(s["mko60"]) * 100), 2), "x_sd_c": round(float(s["x"].std() * 100), 2)}
        for h in (10, 60, 120):
            mm_ = s[f"f{h}"].notna()
            r[f"corr{h}"] = round(float(np.corrcoef(s.loc[mm_, "x"], s.loc[mm_, f"f{h}"])[0, 1]), 3)
            r[f"b{h}"] = round(float(np.polyfit(s.loc[mm_, "x"], s.loc[mm_, f"f{h}"], 1)[0]), 3)
        rows.append(r)
    t = pd.DataFrame(rows).sort_values("n", ascending=False)
    res["table"] = t.to_dict("records")
    json.dump(res, open(RES / "results/maker_compare.json", "w"), indent=1)
    pd.set_option("display.width", 250)
    print(t.to_string(index=False))

if __name__ == "__main__":
    main()
