"""Iteration 9: does the decoded posture side rule generalise to the families nobody examined? (scope B1 = X83 and the
side component). Every cluster maker BUY fill on 10-31 12:00-18:00 UTC (development) in ETH / SOL 5m, 15m, 4h and BTC 4h
(Chainlink-settled, recorded by the shared recorder), scored on the match clock exactly like the frozen BTC rule:
Up iff Phi(ln(CL_asset / K) / (sigma sqrt(tau))) > the Up mid of the latest shared-recorder book before the match ms,
CL = the asset's Chainlink report stamped floor((T - 1432)/1000) (shared rtds 'crypto_prices'), K = Gamma priceToBeat,
sigma = 1.4 x v300 (frozen) or v3600 (slow) of the asset's Binance 1-s spot (REST). No parameter is fitted on these
families. Maker role from the V2 calldata. Baselines: cheaper side, favourite, always Up.
    python code9/posture_xfam.py
"""
import glob
import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE.parent / "code4"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import final_rule as F  # noqa: E402
import calldata as CD  # noqa: E402
import live  # noqa: E402
from polyrea.workflows.updown_study import fetch_windows  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
A, B = 1793448000, 1793469600
ASSETS = {"btc": "BTCUSDT", "eth": "ETHUSDT", "sol": "SOLUSDT"}
HOR = {"5m": 300, "15m": 900, "4h": 14400}


def rest_1s(sym, a, b):
    f = C / "it9" / f"spot1s_{sym}_{a}_{b}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    out, t = [], a
    with httpx.Client(timeout=20) as c:
        while t < b:
            for k in range(5):
                try:
                    r = c.get("https://api.binance.com/api/v3/klines", params={"symbol": sym, "interval": "1s", "startTime": t * 1000,
                                                                                "endTime": min(t + 1000, b) * 1000 - 1, "limit": 1000})
                    if r.status_code == 429:
                        time.sleep(2 + 2 * k)
                        continue
                    out += [(int(x[0]) // 1000, float(x[4])) for x in r.json()]
                    break
                except Exception:  # noqa: BLE001
                    time.sleep(1 + k)
            t += 1000
            time.sleep(0.08)
    d = pd.DataFrame(out, columns=["sec", "px"]).drop_duplicates("sec")
    d.to_parquet(f)
    return d


def rtds_dev(a, b):
    """Shared 'rtds' records from the development folder with a tolerant gzip-member reader (tools/live.py iter_live
    raised zlib 'invalid block type' on a file being written); the sealed calendar is applied per record."""
    import calendar
    import sealed as _sealed
    sys.path.insert(0, str(HERE.parent / "code5"))
    import rawread
    for p in sorted((ROOT / ".cache/live/dev/rtds").glob("*.jsonl.gz")):
        hour = calendar.timegm(time.strptime(p.name[:11], "%Y%m%dT%H"))
        if hour + 3600 <= a or hour >= b:
            continue
        for chunk in rawread._members(p.read_bytes()):
            for line in chunk.split(bytes([10])):
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                t = r.get("t", 0) / 1000.0
                if a <= t < b and not _sealed.future_block_sealed(t):
                    yield r


def main():
    act = pd.read_parquet(C / "it9" / "act_1793448000_1793469600.parquet")
    act = act[(act.type == "TRADE") & (act.side == "BUY")].copy()
    act["fam"] = act.slug.str.extract(r"^(btc|eth|sol)-updown-(5m|15m|4h)-\d+$").apply(lambda r: f"{r[0]}_{r[1]}" if isinstance(r[0], str) else None, axis=1)
    act = act[act.fam.notna() & ~act.fam.isin(["btc_5m", "btc_15m"])].copy()
    act["tx"] = act.transactionHash.str.lower()
    act["wallet"] = act.wallet.str.lower()
    print("fills (all roles)", len(act), act.fam.value_counts().to_dict(), flush=True)
    # maker role from calldata
    cd = pd.concat([pd.read_parquet(p, columns=["tx", "maker", "role"]) for p in glob.glob(str(C / "calldata" / "*1031_*.parquet")) +
                    glob.glob(str(C / "calldata" / "it9sw_*.parquet")) + glob.glob(str(C / "calldata" / "it9xf_*.parquet"))])
    cd["tx"], cd["maker"] = cd.tx.str.lower(), cd.maker.str.lower()
    need = sorted(set(act.tx) - set(cd.tx))
    print("calldata missing", len(need), flush=True)
    if need:
        rows = []
        for h, tx in CD.fetch_txs(need, batch=25, pause=0.2, client=httpx.Client(timeout=30)):
            if tx is None:
                continue
            d = CD.decode(tx.get("input", ""))
            if d is None:
                continue
            for i, o in enumerate([d["taker"]] + d["makers"]):
                rows.append({"tx": h.lower(), "maker": str(o.get("maker", "")).lower(), "role": "taker" if i == 0 else "maker"})
        nd = pd.DataFrame(rows)
        nd.to_parquet(C / "calldata" / f"it9xf_{A}_{B}.parquet")
        cd = pd.concat([cd, nd])
    mk = set(zip(cd.tx[cd.role == "maker"], cd.maker[cd.role == "maker"]))
    act = act[[(t, w) in mk for t, w in zip(act.tx, act.wallet)]].copy()
    print("maker fills", len(act), act.fam.value_counts().to_dict(), flush=True)
    # windows, tokens, strikes
    slugs = sorted(set(act.slug))
    raw = fetch_windows(slugs)
    win = {}
    for m in raw.values():
        try:
            ids = json.loads(m["clobTokenIds"]) if isinstance(m["clobTokenIds"], str) else m["clobTokenIds"]
            outs = json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
        except (KeyError, ValueError, TypeError):
            continue
        slug = str(m.get("slug"))
        st = int(slug.rsplit("-", 1)[1])
        hor = slug.split("-")[2]
        K = None
        for e in m.get("events") or []:
            K = (e.get("eventMetadata") or {}).get("priceToBeat") or K
        up = [str(t) for t, o in zip(ids, outs) if str(o).lower() == "up"][0]
        win[slug] = dict(st=st, en=st + HOR[hor], up=up, K=float(K) if K else None, asset=slug.split("-")[0])
    toks = {v["up"] for v in win.values()}
    match_ms, books = {}, {}
    for r in F._iter_live_xq(A - 120, B + 120, toks):
        if r.get("k") == "x":
            h = str(r.get("h", "")).lower()
            if h and h not in match_ms:
                match_ms[h] = int(r.get("s") or r.get("t"))
        elif r.get("k") == "q" and str(r.get("a")) in toks:
            b_, o_ = r.get("b") or [], r.get("o") or []
            if b_ and o_:
                books.setdefault(str(r["a"]), []).append((int(r.get("s") or r.get("t")), (max(float(x[0]) for x in b_) + min(float(x[0]) for x in o_)) / 2))
    bk = {t: np.array(sorted(v)) for t, v in books.items()}
    clv = {a: {} for a in ASSETS}
    for r in rtds_dev(A - 300, B + 60):
        try:
            j = json.loads(r["m"])
        except (ValueError, KeyError, TypeError):
            continue
        if j.get("topic") != "crypto_prices":
            continue
        pl = j.get("payload") or {}
        a_ = str(pl.get("symbol", "")).split("/")[0]
        if a_ in clv:
            for x in pl.get("data") or []:
                clv[a_].setdefault(int(x["timestamp"]) // 1000, float(x["value"]))
    spot = {}
    for a_, sym in ASSETS.items():
        d = rest_1s(sym, A - 7200, B).sort_values("sec")
        b0 = int(d.sec.iloc[0])
        px = np.full(int(d.sec.iloc[-1]) - b0 + 1, np.nan)
        px[d.sec.astype(int).to_numpy() - b0] = d.px.to_numpy()
        px = pd.Series(px).ffill().to_numpy()
        rr = np.r_[0.0, np.diff(np.log(px))]
        spot[a_] = (b0, np.r_[0.0, np.cumsum(rr * rr)])
    rows = []
    for r in act.itertuples(index=False):
        wv = win.get(r.slug)
        T = match_ms.get(r.tx)
        if wv is None or T is None or wv["K"] is None or wv["up"] not in bk:
            continue
        bb = bk[wv["up"]]
        i = np.searchsorted(bb[:, 0], T, side="left") - 1
        if i < 0 or T - bb[i, 0] > 10000:
            continue
        c = clv[wv["asset"]].get((T - 1432) // 1000)
        if c is None:
            continue
        b0, cs = spot[wv["asset"]]
        k = T // 1000 - 1 - b0
        v300 = np.sqrt((cs[k + 1] - cs[k + 1 - 300]) / 300)
        v3600 = np.sqrt((cs[k + 1] - cs[k + 1 - 3600]) / 3600)
        tau = max(wv["en"] - T / 1000, 1.0)
        x = np.log(c / wv["K"])
        rows.append(dict(fam=r.fam, wallet=r.wallet, st=wv["st"], T=T, is_up=int(str(r.asset) == wv["up"]), mid=float(bb[i, 1]),
                         f_frz=norm.cdf(x / (1.4 * v300 * np.sqrt(tau))), f_slow=norm.cdf(x / (v3600 * np.sqrt(tau))),
                         ratio=v300 / v3600, regA=int(np.sign(x) == np.sign(bb[i, 1] - 0.5))))
    D = pd.DataFrame(rows)
    D.to_parquet(C / "it9" / f"posture_xfam_{A}_{B}.parquet")
    out = {"maker_fills": int(len(act)), "scored": int(len(D))}
    for lab, g in [("all", np.ones(len(D), bool))] + [(f, (D.fam == f).to_numpy()) for f in sorted(D.fam.unique())] + \
            [("non-BTC", ~D.fam.str.startswith("btc").to_numpy()), ("burst>1.5", (D.ratio > 1.5).to_numpy())]:
        y = D.is_up.to_numpy()[g] == 1
        if len(y) < 5:
            continue
        m = D.mid.to_numpy()[g]
        out[lab] = {"n": int(len(y)), "windows": int(D[g].st.nunique()), "frozen": round(float(np.mean((D.f_frz.to_numpy()[g] > m) == y)), 3),
                    "slow": round(float(np.mean((D.f_slow.to_numpy()[g] > m) == y)), 3), "cheaper": round(float(np.mean((m < 0.5) == y)), 3),
                    "favourite": round(float(np.mean((m > 0.5) == y)), 3), "always_up": round(float(y.mean()), 3),
                    "regionD_share": round(float(1 - D.regA.to_numpy()[g].mean()), 3)}
    names = {k_.lower(): v_ for k_, v_ in F.CLUSTER.items()}
    for w_, nm in names.items():
        g = (D.wallet == w_).to_numpy()
        if g.sum() >= 5:
            y = D.is_up.to_numpy()[g] == 1
            out[f"wallet {nm}"] = {"n": int(g.sum()), "frozen": round(float(np.mean((D.f_frz.to_numpy()[g] > D.mid.to_numpy()[g]) == y)), 3),
                                   "slow": round(float(np.mean((D.f_slow.to_numpy()[g] > D.mid.to_numpy()[g]) == y)), 3)}
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter9_posture_xfam.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
