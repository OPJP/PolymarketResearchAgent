"""What triggers the wallet's informed taker orders (1000/2000-share FAK-like buys, +6% settlement edge)?
For each taker order (sign time t, market M, team X bought): moves of team X's price in M and in the sibling
markets of the same event (match <-> maps) over the previous 5/10/30 s and 'gap' = sibling move - own move;
compared with the same quantities at random control times in the same markets (matched to in-play time).
Public prints only (wallet transactions excluded). Development data."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RES, WALLET, H, TAPES, SPLIT  # noqa: E402

def team_series(cid, outcomes, bad):
    p = TAPES / f"{cid}_tkw.parquet"
    if not p.exists(): return None
    d = pd.read_parquet(p); d = d[(d.timestamp < H) & ~d.transactionHash.isin(bad)].sort_values("timestamp")
    if len(d) == 0: return None
    p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
    return d.timestamp.to_numpy(np.int64), p0, outcomes

def px(ser, at, team):
    ts, p0, outs = ser
    i = np.searchsorted(ts, at, side="left")
    v = np.where(i > 0, p0[np.maximum(i - 1, 0)], np.nan)
    return v if outs[0] == team else 1 - v

def main():
    m = json.load(open(OUT / "markets_dev.json"))
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    bad = set(cd.loc[cd.maker == WALLET, "tx"])
    o = pd.read_parquet(OUT / "orders.parquet")
    meta = {}
    for cid, x in m.items():
        outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
        meta[cid] = {"event": (x.get("slug") or "").rsplit("-game", 1)[0], "outs": outs, "smt": x.get("sportsMarketType")}
    ev_cids = {}
    for cid, v in meta.items(): ev_cids.setdefault(v["event"], []).append(cid)
    ser = {cid: team_series(cid, meta[cid]["outs"], bad) for cid in meta}
    rng = np.random.default_rng(7)
    rows = []
    for kind, sub in (("taker", o[o.role == "taker"]), ("maker", o[o.role == "maker"].sample(3000, random_state=1))):
        for r in sub.itertuples():
            if ser.get(r.cid) is None: continue
            team = meta[r.cid]["outs"][r.oi]
            for ctrl in (False, True):
                t = r.sign_ts if not ctrl else r.sign_ts + rng.uniform(-1800, 1800)
                rec = {"kind": kind, "ctrl": ctrl, "cid": r.cid, "smt": r.smt, "gs": r.gs_ts, "price": r.price}
                for h in (5, 10, 30):
                    rec[f"own{h}"] = float(px(ser[r.cid], np.array([t]), team)[0] - px(ser[r.cid], np.array([t - h]), team)[0])
                    sib = []
                    for c2 in ev_cids[meta[r.cid]["event"]]:
                        if c2 == r.cid or ser.get(c2) is None or team not in meta[c2]["outs"]: continue
                        a = px(ser[c2], np.array([t]), team)[0]; b = px(ser[c2], np.array([t - h]), team)[0]
                        if np.isfinite(a) and np.isfinite(b): sib.append(a - b)
                    rec[f"sib{h}"] = float(np.max(sib)) if sib else np.nan
                    rec[f"sibmin{h}"] = float(np.min(sib)) if sib else np.nan
                rec["own_level"] = float(px(ser[r.cid], np.array([t]), team)[0])
                rows.append(rec)
    x = pd.DataFrame(rows)
    res = {}
    for (kind, ctrl), s in x.groupby(["kind", "ctrl"]):
        k = f"{kind}_{'ctrl' if ctrl else 'real'}"
        res[k] = {"n": len(s)}
        for h in (5, 10, 30):
            res[k][f"own{h}_mean_c"] = round(float(np.nanmean(s[f"own{h}"]) * 100), 2)
            res[k][f"sib{h}_max_mean_c"] = round(float(np.nanmean(s[f"sib{h}"]) * 100), 2)
            res[k][f"share_sib{h}_up2c"] = round(float((s[f"sib{h}"] >= 0.02).mean()), 3)
            res[k][f"share_own{h}_up2c"] = round(float((s[f"own{h}"] >= 0.02).mean()), 3)
            res[k][f"share_own{h}_dn2c"] = round(float((s[f"own{h}"] <= -0.02).mean()), 3)
        res[k]["has_sib"] = round(float(s["sib10"].notna().mean()), 3)
    res["taker_by_smt"] = x[(x.kind == "taker") & ~x.ctrl].smt.value_counts().to_dict()
    x.to_parquet(OUT / "taker_trigger.parquet", index=False)
    json.dump(res, open(RES / "results/taker_trigger.json", "w"), indent=1)
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
