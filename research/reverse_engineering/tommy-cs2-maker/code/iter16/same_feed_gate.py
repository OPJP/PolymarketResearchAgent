"""X227 (assumptions panel iter-15 P1): same-feed gate on the operator sibling 0x7d67f01d's development units, then the
frozen live information tests where a recorder holds records of those units. Pre-registered in NOTES iteration 16.

Units: cs2-1win-5s-2026-10-31, dota2-xe-hn-2026-10-31 (10-31 12-18), dota2-synaps-hn-2026-11-01, cs2-the9-5s-2026-11-01
(11-01 06-12); every unit start is checked with sealed.is_sealed; every fetch ends at the block end.
G1: its takes co-sign with wallet-free group-P / group-G takes on the event within +-300 ms, >= 5x a +-30..120-s shifted
    null, >= 3 takes, median lag behind the first group-P/G signer in [0, 150] ms with IQR <= 40 ms.
G2: its new-high value changes move the clean print their way by >= +1c at 60 s (mean, n >= 20).
Output: results/same_feed_gate.json; cache .cache/re/tommy-cs2-maker/iter16/sfg_{trades,calldata}.parquet
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
CODE = ROOT / "research/reverse_engineering/tommy-cs2-maker/code"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CODE / "iter15"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import sealed  # noqa: E402
import grid_socket_clock as g1  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

KEY = "tommy-cs2-maker"
OUT = ROOT / ".cache/re/tommy-cs2-maker/iter16"
OUT.mkdir(exist_ok=True)
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
A7 = "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14"
GP = set(json.load(open(CODE / "final_rule_v5_groupP.json"))["members"])
import ast  # noqa: E402
_g = json.load(open(CODE / "final_rule_v5_groupP.json"))["group_G"]
GG = set(_g if isinstance(_g, list) else ast.literal_eval(_g))
BLOCKS = {"10-31": (1793448000, 1793469600), "11-01": (1793512800, 1793534400)}
EVENTS = {"cs2-1win-5s-2026-10-31": "10-31", "dota2-xe-hn-2026-10-31": "10-31",
          "dota2-synaps-hn-2026-11-01": "11-01", "cs2-the9-5s-2026-11-01": "11-01"}


def markets():
    u = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/universe_t0.parquet")
    u = u[u.event_slug.isin(EVENTS)][["event_slug", "cid", "gs_ts", "outcomes", "tokens"]].copy()
    v = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/dev_markets_v1101a.parquet")
    v = v[v.event.isin(EVENTS)]
    rows = [dict(event_slug=r.event, cid=r.cid, gs_ts=float(r.gs), outcomes=None, tokens=json.dumps([str(r.tok0), str(r.tok1)]))
            for r in v.itertuples()]
    m = pd.concat([u, pd.DataFrame(rows)], ignore_index=True).drop_duplicates("cid")
    m["egs"] = m.groupby("event_slug").gs_ts.transform("min")
    return m


def fetch(m):
    p = OUT / "sfg_trades.parquet"
    if p.exists():
        return pd.read_parquet(p)
    pm = PolymarketData()
    rows = []
    for r in m.itertuples():
        assert not sealed.is_sealed(float(r.egs), KEY), r.event_slug
        a, b = BLOCKS[EVENTS[r.event_slug]]
        assert a <= r.egs < b, (r.event_slug, r.egs)
        for tk in (True, False):
            rws, _, _ = pm.market_trades(r.cid, start=int(r.gs_ts) - 3600, end=int(b) - 1, taker_only=tk)
            for x in rws:
                x = dict(x)
                x.update(cid=r.cid, event=r.event_slug, taker_q=tk)
                rows.append(x)
    t = pd.DataFrame(rows)
    t["proxyWallet"] = t.proxyWallet.str.lower()
    keep = ["proxyWallet", "side", "asset", "outcomeIndex", "size", "price", "timestamp", "transactionHash", "cid", "event", "taker_q"]
    t = t[keep]
    t.to_parquet(p, index=False)
    return t


def decode(txs):
    p = OUT / "sfg_calldata.parquet"
    have = pd.read_parquet(p) if p.exists() else pd.DataFrame()
    todo = sorted(set(txs) - (set(have.tx) if len(have) else set()))
    if todo:
        # reuse the iteration-15 decoder but keep our own cache file
        old = g1.OUT
        g1.OUT = OUT
        tmp = OUT / "op_calldata.parquet"
        if tmp.exists():
            tmp.unlink()
        new = g1.decode(todo)
        g1.OUT = old
        if tmp.exists():
            tmp.unlink()
        have = pd.concat([have, new], ignore_index=True) if len(have) else new
        have.to_parquet(p, index=False)
    return have


def bursts(c):
    rows = []
    for tok, g in c.sort_values("sign_ms").groupby("token_id"):
        s = g.sign_ms.to_numpy(float)
        p = g.price.to_numpy(float)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and s[j + 1] - s[j] <= 50:
                j += 1
            rows.append((s[i], str(tok), float(p[i:j + 1].max()), j - i + 1))
            i = j + 1
    b = pd.DataFrame(rows, columns=["t", "tok", "top", "n"]).sort_values(["tok", "t"])
    b["prev3"] = b.groupby("tok").top.transform(lambda x: x.shift(1).rolling(3, min_periods=1).max())
    b["dtop"] = b.groupby("tok").top.diff()
    return b.sort_values("t")


def main():
    m = markets()
    t = fetch(m)
    tok2cid = {}
    for r in m.itertuples():
        for k in json.loads(r.tokens) if isinstance(r.tokens, str) else list(r.tokens):
            tok2cid[str(k)] = r.cid
    ev_of = dict(zip(m.cid, m.event_slug))
    want = set(t.loc[t.proxyWallet.isin(GP | GG | {A7}), "transactionHash"])
    cd = decode(list(want))
    cd = cd[cd.sign_ms > 1.7e12].copy()
    cd["mk"] = cd.maker.str.lower()
    cd["cid"] = cd.token_id.astype(str).map(tok2cid)
    cd["event"] = cd.cid.map(ev_of)
    cd = cd[cd.event.notna()]
    wtx = set(cd.loc[cd.mk == W, "tx"]) | set(t.loc[t.proxyWallet == W, "transactionHash"])
    tk = cd[cd.idx == -1].drop_duplicates(["tx"])
    out = {"units": {}, "n_trades_rows": int(len(t)), "n_decoded_orders": int(len(cd))}
    rng = np.random.default_rng(16)
    for ev, g in tk.groupby("event"):
        mine = g[g.mk == A7].sign_ms.to_numpy(float)
        oth = g[(g.mk.isin(GP | GG)) & ~g.tx.isin(wtx)]
        os_ = np.sort(oth.sign_ms.to_numpy(float))
        o = {"a7_takes": int(len(mine)), "groupPG_takes": int(len(os_)),
             "groupPG_members": {k[:10]: int(v) for k, v in oth.mk.value_counts().items()}}
        if len(mine) and len(os_):
            def cos(x):
                j = np.searchsorted(os_, x)
                lo = np.abs(x - os_[np.clip(j - 1, 0, len(os_) - 1)])
                hi = np.abs(os_[np.clip(j, 0, len(os_) - 1)] - x)
                return np.minimum(lo, hi) <= 300
            obs = cos(mine)
            nulls = [cos(mine + rng.choice([-1, 1], len(mine)) * rng.uniform(30_000, 120_000, len(mine))).mean() for _ in range(300)]
            lags = []
            for x in mine[obs]:
                w = os_[(os_ >= x - 300) & (os_ <= x + 300)]
                lags.append(x - w.min())
            o.update(cosigned=int(obs.sum()), share=round(float(obs.mean()), 3), null_share=round(float(np.mean(nulls)), 4),
                     ratio=round(float(obs.mean() / max(np.mean(nulls), 1e-9)), 2),
                     lag_ms_median=round(float(np.median(lags)), 1) if lags else None,
                     lag_ms_iqr=round(float(np.subtract(*np.percentile(lags, [75, 25]))), 1) if lags else None,
                     lag_ms_quartiles=[round(float(q), 1) for q in np.percentile(lags, [10, 25, 50, 75, 90])] if lags else None)
        out["units"][ev] = o
    # G2: value changes (new highs) and the clean print 60 s later
    mk = cd[(cd.mk == A7) & (cd.idx >= 0)].drop_duplicates(["salt", "sign_ms"])
    pr = t[t.taker_q & ~t.transactionHash.isin(wtx | set(cd.loc[cd.mk == A7, "tx"]))].copy()
    mk_rows = []
    for cid, g in mk.groupby("cid"):
        b = bursts(g)
        pp = pr[pr.cid == cid].sort_values("timestamp")
        if len(pp) < 5:
            continue
        ts = pp.timestamp.to_numpy(float)
        for tok, bb in b.groupby("tok"):
            # clean print expressed in this token's price
            pt = np.where(pp.asset.astype(str) == tok, pp.price.astype(float), 1 - pp.price.astype(float))
            for r in bb.itertuples():
                if not (r.dtop > 0 and r.top > (r.prev3 if np.isfinite(r.prev3) else 9) + 1e-9):
                    continue
                t0 = r.t / 1000.0
                j0 = np.searchsorted(ts, t0, side="right") - 1
                j1 = np.searchsorted(ts, t0 + 60, side="right") - 1
                if j0 < 0:
                    continue
                mk_rows.append({"event": ev_of.get(cid), "cid": cid, "t": t0, "m60_c": float(pt[j1] - pt[j0]) * 100})
    M = pd.DataFrame(mk_rows)
    out["G2_newhigh"] = {"n": int(len(M)), "mean_m60_c": round(float(M.m60_c.mean()), 3) if len(M) else None,
                         "by_event": {k: {"n": int(len(v)), "mean_m60_c": round(float(v.m60_c.mean()), 3)} for k, v in M.groupby("event")} if len(M) else {}}
    # design of its orders on these units (for the record)
    out["a7_maker_orders"] = int(len(mk))
    out["a7_sizes_top"] = {str(k): int(v) for k, v in mk.shares.round(0).value_counts().head(6).items()}
    pooled = [u for u in out["units"].values() if u.get("a7_takes")]
    cs = sum(u.get("cosigned", 0) for u in pooled)
    na = sum(u["a7_takes"] for u in pooled)
    nl = np.mean([u["null_share"] for u in pooled if u.get("null_share") is not None]) if pooled else np.nan
    out["G1_pooled"] = {"a7_takes": na, "cosigned": cs, "share": round(cs / na, 3) if na else None, "null_share_mean": round(float(nl), 4) if np.isfinite(nl) else None}
    g1_pass = bool(na and cs >= 3 and (cs / na) >= 5 * nl)
    lag_ok = any((u.get("lag_ms_median") is not None and 0 <= u["lag_ms_median"] <= 150 and (u.get("lag_ms_iqr") or 999) <= 40) for u in pooled)
    g2_pass = bool(len(M) >= 20 and M.m60_c.mean() >= 1.0)
    out["gate"] = {"G1_ratio_and_count": g1_pass, "G1_lag_structure": bool(lag_ok), "G2": g2_pass, "pass": bool(g1_pass and lag_ok and g2_pass)}
    M.to_parquet(OUT / "sfg_newhigh_rows.parquet", index=False)
    (RES / "same_feed_gate.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
