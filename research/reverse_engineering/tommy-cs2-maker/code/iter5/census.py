"""Iteration 5, assumptions panel iter4 P1 (X58): a survivorship-free census of informed in-play bursts, 16-22 Oct.

Bursts: in-play BUY taker orders on one token by informed signers (the 9 pack signers and the wallet; pack_orders.parquet
from calldata), single linkage 1 s on signing ms, per (market, token). Kept if the token's public last print (windowed
taker tapes, txs containing any wallet order excluded) moved >= +3c from [first sign - 1 s] to [first sign + 10 s].
Labels (client clocks are uncalibrated historically, so "led" needs a 200-ms margin):
  wallet-led    = the wallet signs first and >= 200 ms before the first other informed signer (or alone);
  wallet-near   = the wallet is in the burst but not led by 200 ms (ties within the clock error);
  wallet-late   = its first order on the token comes after the burst's last order, within 30 s;
  wallet-absent = no wallet take on that token within [first - 1 s, first + 30 s].
Exposure (the wallet's resting bids on the COMPLEMENT are asks on the burst token): its maker fills on the complement
inside the burst's pack transactions, split into stale (signed before the burst's first signing) and in-delay (signed
after it); markouts of those fills at +10 / +30 / +120 s (complement's public price minus fill price, cents/share).
Explore on BUILD (gs < 10-21), report on VALIDATE.
Output: results/census.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0, H = 1792540800, 1792713600


def main():
    po0 = pd.read_parquet(OUT / "pack_orders.parquet")
    PACK = set(po0.maker.str.lower())
    meta = po0.drop_duplicates("token_id")[["token_id", "cid", "oi", "cs2"]]
    ca = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "side", "token_id", "price", "fill", "sign_ms", "cid", "oi", "bts"])
    # NOTE (iteration 5): pack_orders.parquet was built from calldata_pub only, which excludes every tx with a wallet
    # order, so the pack's takes that hit the wallet were missing. Rebuild the informed BUY orders from both records.
    import glob
    cols = ["tx", "idx", "maker", "side", "sign_ms", "shares", "fill", "price", "token_id", "block"]
    pub = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(OUT / "calldata_pub/*.parquet")))])
    pub = pub[(pub.idx == -1) & pub.maker.str.lower().isin(PACK)]
    allt = ca[(ca.idx == -1) & ca.maker.str.lower().isin(PACK)][["tx", "idx", "maker", "side", "sign_ms", "fill", "price", "token_id"]].assign(block=1)
    po = pd.concat([pub, allt], ignore_index=True).drop_duplicates(["tx", "maker", "idx"])
    po["token_id"] = po.token_id.astype(str)
    meta = meta.assign(token_id=meta.token_id.astype(str))
    po = po.merge(meta, on="token_id", how="inner")
    po = po[(po.side == 0) & (po.sign_ms > 1.7e12) & (po.sign_ms < 1.8e12) & po.cs2.astype(bool)].copy()
    po["mk"] = po.maker.str.lower()
    po["is_w"] = po.mk == WALLET
    po["usd"] = po.fill * po.price
    print("informed BUY orders", len(po), "of which in wallet txs", int(po.tx.isin(set(ca.tx)).sum()), flush=True)
    wtx = set(ca.tx)
    wm = ca[(ca.maker == WALLET) & (ca.idx >= 0)]
    wm_by_tx = {tx: g for tx, g in wm.groupby("tx")}
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "gs_ts"]).drop_duplicates("cid")
    gsm = dict(zip(o.cid, o.gs_ts))
    rows = []
    for cid, g in po.groupby("cid"):
        gs = float(gsm.get(cid, np.nan))
        if not np.isfinite(gs):
            continue
        tp = OUT / "tapes" / f"{cid}_tkw.parquet"
        if not tp.exists():
            continue
        d = pd.read_parquet(tp, columns=["timestamp", "price", "outcomeIndex", "transactionHash"])
        d = d[~d.transactionHash.isin(wtx)].sort_values("timestamp")
        pt = d.timestamp.to_numpy(float)
        p0 = np.where(d.outcomeIndex.to_numpy(int) == 0, d.price.to_numpy(float), 1 - d.price.to_numpy(float))

        def px(t, k):
            j = int(np.searchsorted(pt, t, side="right")) - 1
            if j < 0:
                return np.nan
            return p0[j] if k == 0 else 1 - p0[j]

        for k, h in g.groupby("oi"):
            h = h.sort_values("sign_ms")
            s = h.sign_ms.to_numpy(float)
            cut = np.flatnonzero(np.diff(s) > 1000) + 1
            w_all = np.sort(g[(g.oi == k) & g.is_w].sign_ms.to_numpy(float))
            for lo, hi in zip(np.r_[0, cut], np.r_[cut, len(h)]):
                b = h.iloc[lo:hi]
                t0 = float(b.sign_ms.iloc[0]) / 1000.0
                if t0 < gs + 60:
                    continue
                before, after10 = px(t0 - 1, int(k)), px(t0 + 10, int(k))
                if not (np.isfinite(before) and np.isfinite(after10)):
                    continue
                move = after10 - before
                if move < 0.03 - 1e-9:
                    continue
                ws = b[b.is_w].sign_ms.to_numpy(float)
                os_ = b[~b.is_w].sign_ms.to_numpy(float)
                if len(ws):
                    if len(os_) == 0 or ws.min() <= os_.min() - 200:
                        lab = "wallet-led"
                    else:
                        lab = "wallet-near"
                else:
                    last = float(b.sign_ms.iloc[-1])
                    j = np.searchsorted(w_all, t0 * 1000 - 1000)
                    nxt = w_all[j] if j < len(w_all) else np.inf
                    lab = "wallet-late" if nxt <= t0 * 1000 + 30000 else "wallet-absent"
                # exposure: wallet maker fills on the complement inside the burst's non-wallet txs
                comp = 1 - int(k)
                stale = indel = 0.0
                mk = {10: [], 30: [], 120: []}
                for tx in b[~b.is_w].tx.unique():
                    f = wm_by_tx.get(tx)
                    if f is None:
                        continue
                    f = f[(f.oi == comp) & (f.side == 0)]
                    for r in f.itertuples():
                        if r.sign_ms < t0 * 1000:
                            stale += float(r.fill)
                        else:
                            indel += float(r.fill)
                        for hz in (10, 30, 120):
                            pp = px(t0 + hz, comp)
                            if np.isfinite(pp):
                                mk[hz].append((float(r.fill), pp - float(r.price)))
                rows.append({"cid": cid, "gs": gs, "t0": t0, "oi": int(k), "label": lab, "move10": move,
                             "n_orders": int(len(b)), "usd": float(b.usd.sum()), "stale_sh": stale, "indelay_sh": indel,
                             **{f"mk{hz}": (sum(a * b_ for a, b_ in mk[hz]) / sum(a for a, _ in mk[hz])) if mk[hz] else np.nan for hz in (10, 30, 120)},
                             **{f"mkw{hz}": sum(a for a, _ in mk[hz]) for hz in (10, 30, 120)}})
    B = pd.DataFrame(rows)
    B["split"] = np.where(B.gs < VAL0, "BUILD", "VALIDATE")
    res = {}
    for sp, x in B.groupby("split"):
        r = {"bursts_3c": int(len(x)), "label_share": x.label.value_counts(normalize=True).round(3).to_dict(),
             "label_n": x.label.value_counts().to_dict()}
        by = {}
        for lab, y in x.groupby("label"):
            hit = (y.stale_sh + y.indelay_sh) > 0
            by[lab] = {"n": int(len(y)), "move10_median_c": round(float(100 * y.move10.median()), 2),
                       "share_hit_on_complement": round(float(hit.mean()), 3),
                       "stale_shares": round(float(y.stale_sh.sum()), 0), "indelay_shares": round(float(y.indelay_sh.sum()), 0),
                       **{f"markout_{hz}s_c": (round(float(100 * np.nansum(y[f"mk{hz}"] * y[f"mkw{hz}"]) / max(y[f"mkw{hz}"].sum(), 1e-9)), 2)) for hz in (10, 30, 120)}}
            by[lab]["usd_median"] = round(float(y.usd.median()), 1)
        r["by_label"] = by
        res[sp] = r
    B.to_parquet(OUT / "census_bursts.parquet", index=False)
    (RES / "census.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
