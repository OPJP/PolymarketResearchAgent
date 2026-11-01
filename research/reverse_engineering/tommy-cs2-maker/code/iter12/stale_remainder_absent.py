"""X169 (assumptions panel iter-11 P3, historical step 1): does the stale liquidity at <= an informed limit survive
after the leader's match when the wallet does NOT take? A natural experiment on the census of informed bursts.

Bursts: the iteration-5 census construction (code/iter5/census.py): in-play BUY taker orders on one token by the
informed signers (pack + wallet), single linkage 1 s on signing ms, kept if the public last print moved >= +3c in
10 s; labels wallet-led / wallet-near / wallet-late / wallet-absent.
For each burst: leader = its first order (sign s0, limit L = its price), match m = s0 + 1,040 ms (the in-play delay).
Later takers = every other BUY taker order on the same token (calldata_all + calldata_pub, txs of the burst excluded)
whose match time (sign + 1,040 ms) falls in (m, m + 4 s]. Consumed stale liquidity = their maker legs at an effective
price <= L (SELL makers of the token at p, BUY makers of the complement at 1 - q), split into the wallet's own legs and
everyone else's. Reported per label and 1-s bin: share of bursts with any non-wallet consumption at <= L and the mean
shares, with the burst's own informed consumption at <= L as scale, stratified by move10.
Development data only (16-22 Oct, signed before H).
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0, H = 1792540800, 1792713600
DELAY = 1040.0


def main():
    po0 = pd.read_parquet(OUT / "pack_orders.parquet")
    PACK = set(po0.maker.str.lower())
    meta = po0.drop_duplicates("token_id")[["token_id", "cid", "oi", "cs2"]].assign(token_id=lambda d: d.token_id.astype(str))
    cols = ["tx", "idx", "maker", "side", "sign_ms", "fill", "price", "token_id"]
    ca = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["cid", "oi"])
    pub = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(OUT / "calldata_pub/*.parquet")))])
    allo = pd.concat([ca[cols], pub[cols]], ignore_index=True).drop_duplicates(["tx", "maker", "idx", "token_id", "sign_ms"])
    allo["token_id"] = allo.token_id.astype(str)
    allo["mk"] = allo.maker.str.lower()
    allo = allo[(allo.sign_ms > 1.7e12) & (allo.sign_ms < H * 1000)]
    tok2 = {}
    mk = json.load(open(OUT / "markets_dev.json"))
    for cid, x in mk.items():
        toks = x.get("clobTokenIds"); toks = json.loads(toks) if isinstance(toks, str) else (toks or [])
        if len(toks) == 2:
            tok2[str(toks[0])] = str(toks[1]); tok2[str(toks[1])] = str(toks[0])
    takers = allo[(allo.idx == -1) & (allo.side == 0)].copy()
    makers = allo[allo.idx >= 0].copy()
    mk_by_tx = {tx: g for tx, g in makers.groupby("tx")}
    tk_by_tok = {t: g.sort_values("sign_ms") for t, g in takers.groupby("token_id")}
    # informed orders (census construction)
    po = takers[takers.mk.isin(PACK)].merge(meta, on="token_id", how="inner")
    po = po[po.cs2.astype(bool)].copy()
    po["is_w"] = po.mk == WALLET
    wtx = set(ca.tx)
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "gs_ts"]).drop_duplicates("cid")
    gsm = dict(zip(o.cid, o.gs_ts))
    rows = []
    for cid, g in po.groupby("cid"):
        gs = float(gsm.get(cid, np.nan))
        tp = OUT / "tapes" / f"{cid}_tkw.parquet"
        if not np.isfinite(gs) or not tp.exists():
            continue
        d = pd.read_parquet(tp, columns=["timestamp", "price", "outcomeIndex", "transactionHash"])
        d = d[~d.transactionHash.isin(wtx)].sort_values("timestamp")
        pt = d.timestamp.to_numpy(float)
        p0 = np.where(d.outcomeIndex.to_numpy(int) == 0, d.price.to_numpy(float), 1 - d.price.to_numpy(float))

        def px(t, k):
            j = int(np.searchsorted(pt, t, side="right")) - 1
            return np.nan if j < 0 else (p0[j] if k == 0 else 1 - p0[j])

        for k, hh in g.groupby("oi"):
            hh = hh.sort_values("sign_ms")
            s = hh.sign_ms.to_numpy(float)
            cut = np.flatnonzero(np.diff(s) > 1000) + 1
            w_all = np.sort(g[(g.oi == k) & g.is_w].sign_ms.to_numpy(float))
            for lo, hi in zip(np.r_[0, cut], np.r_[cut, len(hh)]):
                b = hh.iloc[lo:hi]
                t0 = float(b.sign_ms.iloc[0]) / 1000.0
                if t0 < gs + 60:
                    continue
                before, after10 = px(t0 - 1, int(k)), px(t0 + 10, int(k))
                if not (np.isfinite(before) and np.isfinite(after10)) or after10 - before < 0.03 - 1e-9:
                    continue
                ws = b[b.is_w].sign_ms.to_numpy(float); os_ = b[~b.is_w].sign_ms.to_numpy(float)
                if len(ws):
                    lab = "wallet-led" if (len(os_) == 0 or ws.min() <= os_.min() - 200) else "wallet-near"
                else:
                    j = np.searchsorted(w_all, t0 * 1000 - 1000)
                    nxt = w_all[j] if j < len(w_all) else np.inf
                    lab = "wallet-late" if nxt <= t0 * 1000 + 30000 else "wallet-absent"
                tok = str(b.token_id.iloc[0]); comp = tok2.get(tok)
                s0 = float(b.sign_ms.iloc[0]); L = float(b.price.iloc[0]); Lmax = float(b.price.max())
                m = s0 + DELAY
                btx = set(b.tx)

                def legs_at_le(tx, lim):
                    f = mk_by_tx.get(tx)
                    if f is None:
                        return 0.0, 0.0
                    eff = np.where((f.token_id == tok) & (f.side == 1), f.price,
                                   np.where((f.token_id == comp) & (f.side == 0), 1 - f.price, np.nan))
                    ok = np.isfinite(eff) & (eff <= lim + 1e-9)
                    w = (f.mk == WALLET).to_numpy()
                    return float(f.fill.to_numpy()[ok & ~w].sum()), float(f.fill.to_numpy()[ok & w].sum())

                own_nw = own_w = own_wt = 0.0
                wtk = set(b[b.is_w].tx)
                for tx in btx:
                    a_, b_ = legs_at_le(tx, Lmax)
                    own_nw += a_; own_w += b_
                    if tx in wtk:
                        own_wt += a_
                tk = tk_by_tok.get(tok)
                bins_nw = np.zeros(4); bins_w = np.zeros(4); bins_any = np.zeros(4)
                n_later = 0
                if tk is not None:
                    st = tk.sign_ms.to_numpy(float)
                    j0, j1 = np.searchsorted(st, m - DELAY, side="right"), np.searchsorted(st, m + 4000 - DELAY, side="right")
                    for r in tk.iloc[j0:j1].itertuples():
                        if r.tx in btx:
                            continue
                        mt = float(r.sign_ms) + DELAY
                        bi = int((mt - m - 1e-9) // 1000)
                        if bi < 0 or bi > 3:
                            continue
                        a_, b_ = legs_at_le(r.tx, L)
                        bins_nw[bi] += a_; bins_w[bi] += b_; n_later += 1
                rows.append({"cid": cid, "gs": gs, "t0": t0, "oi": int(k), "label": lab, "move10": after10 - before, "L": L,
                             "n_orders": int(len(b)), "own_nw_le": own_nw, "own_w_le": own_w, "own_wtaker_le": own_wt, "n_later": n_later,
                             **{f"nw_b{i}": bins_nw[i] for i in range(4)}, **{f"w_b{i}": bins_w[i] for i in range(4)}})
    B = pd.DataFrame(rows)
    B["split"] = np.where(B.gs < VAL0, "BUILD", "VALIDATE")
    B.to_parquet(OUT / "iter12/stale_remainder_absent.parquet", index=False)
    res = {"bursts": int(len(B)), "label_n": B.label.value_counts().to_dict()}
    B["mv"] = pd.cut(B.move10, [0.0299, 0.05, 0.08, 1.0], labels=["3-5c", "5-8c", ">=8c"])
    for split in ("BUILD", "VALIDATE", "all"):
        X = B if split == "all" else B[B.split == split]
        out = {}
        for lab, y in X.groupby("label"):
            r = {"n": int(len(y)), "burst_own_consumed_le_L_nonwallet_mean": round(float(y.own_nw_le.mean()), 1),
                 "burst_own_consumed_le_L_wallet_mean": round(float(y.own_w_le.mean()), 1)}
            for i in range(4):
                r[f"later_m+{i}-{i + 1}s_share_any_nonwallet"] = round(float((y[f"nw_b{i}"] > 0).mean()), 3)
                r[f"later_m+{i}-{i + 1}s_mean_nonwallet_shares"] = round(float(y[f"nw_b{i}"].mean()), 1)
                r[f"later_m+{i}-{i + 1}s_mean_wallet_maker_shares"] = round(float(y[f"w_b{i}"].mean()), 1)
            by = {}
            for mv, z in y.groupby("mv", observed=True):
                by[str(mv)] = {"n": int(len(z)), "share_any_nonwallet_m+1-3s": round(float(((z.nw_b1 + z.nw_b2) > 0).mean()), 3),
                               "mean_nonwallet_m+1-3s": round(float((z.nw_b1 + z.nw_b2).mean()), 1),
                               "burst_own_nonwallet_mean": round(float(z.own_nw_le.mean()), 1), "burst_own_wallet_mean": round(float(z.own_w_le.mean()), 1)}
            r["by_move10"] = by
            out[lab] = r
        res[split] = out
    # the panel's signature: wallet-absent later consumption at m+2-3 s vs the wallet's own take in matched present bursts
    pres = B[B.label.isin(["wallet-led", "wallet-near"])]
    absn = B[B.label == "wallet-absent"]
    wtake = []
    for mv, z in pres.groupby("mv", observed=True):
        za = absn[absn.mv == mv]
        if len(za) and len(z):
            wtake.append({"move10": str(mv), "present_n": int(len(z)), "absent_n": int(len(za)),
                          "absent_later_m+2-3s_mean": round(float(za.nw_b2.mean()), 1),
                          "absent_later_m+1-4s_mean": round(float((za.nw_b1 + za.nw_b2 + za.nw_b3).mean()), 1),
                          "present_wallet_take_le_L_mean": round(float(z.own_wtaker_le.mean()), 1),
                          "present_burst_take_le_L_mean": round(float(z.own_nw_le.mean()), 1),
                          "present_later_m+1-4s_mean": round(float((z.nw_b1 + z.nw_b2 + z.nw_b3).mean()), 1)})
    res["panel_signature_rows"] = wtake
    (RES / "stale_remainder_absent.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1)[:6000])


if __name__ == "__main__":
    main()
